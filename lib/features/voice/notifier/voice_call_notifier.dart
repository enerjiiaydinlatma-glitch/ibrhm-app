import "dart:async";
import "dart:convert";
import "dart:io";
import "dart:math";

import "package:camera/camera.dart";
import "package:flutter/foundation.dart";
import "package:flutter/widgets.dart";
import "package:flutter_riverpod/flutter_riverpod.dart";
import "package:flutter_soloud/flutter_soloud.dart";
import "package:record/record.dart";
import "package:wakelock_plus/wakelock_plus.dart";
import "package:web_socket_channel/web_socket_channel.dart";

import "../../chat/notifier/chat_notifier.dart";
import "../models/voice_call_state.dart";
import "mic_level_notifier.dart";

/// GECICI TESHIS ARACI (2. kez eklendi - donma tekrarladi). Release
/// build'de console gorunmuyor, o yuzden her riskli native cagridan
/// HEMEN ONCE diske senkron, flush edilmis bir satir yaziyoruz - donma
/// o cagrinin TAM ICINDE olsa bile "cagriya girildi" satiri diskte kalir.
/// Bu sefer addAudioDataStream de dahil (once bunu loglamamistik).
final File _voiceDebugLogFile = File(
  "${Directory.systemTemp.path}\\aura_voice_debug.log",
);

void _voiceDebugLog(String message) {
  try {
    _voiceDebugLogFile.writeAsStringSync(
      "${DateTime.now().toIso8601String()} $message\n",
      mode: FileMode.append,
      flush: true,
    );
  } catch (_) {}
}

/// Ham PCM16 (little-endian, mono) ses parcasindan 0.0-1.0 arasi bir
/// ses seviyesi hesaplar (RMS - root-mean-square). 3000 bolen degeri
/// keyfi degil - normal konusma sesinin PCM16'daki tipik RMS araligina
/// gore secildi (tam 32768 max genlige gore normalize edilseydi normal
/// konusma neredeyse hic gorunmezdi).
double _computeMicLevel(List<int> pcm16Bytes) {
  if (pcm16Bytes.length < 2) return 0.0;
  int sumSquares = 0;
  int sampleCount = 0;
  for (var i = 0; i + 1 < pcm16Bytes.length; i += 2) {
    var sample = pcm16Bytes[i] | (pcm16Bytes[i + 1] << 8);
    if (sample >= 32768) sample -= 65536;
    sumSquares += sample * sample;
    sampleCount++;
  }
  if (sampleCount == 0) return 0.0;
  final rms = sqrt(sumSquares / sampleCount);
  return (rms / 3000).clamp(0.0, 1.0);
}

/// Aura ile gercek zamanli, tam serbest (interrupt edilebilir) sesli
/// gorusme. Chat ekranindan hicbir zaman ayrilmaz - bir Notifier olarak
/// yasar, ChatScreen sadece kucuk bir durum cubugu (VoiceCallBar) render
/// eder. Konusulan sozler turn_complete ile birlikte donen transkript
/// uzerinden chatProvider'a (ayni mesaj listesine) ekleniyor - yazili ve
/// sesli mesajlar tek bir akista birlesiyor.
class VoiceCallNotifier extends Notifier<VoiceCallState>
    with WidgetsBindingObserver {
  static const _wsBase = "wss://aura-backend-production-bc9c.up.railway.app";

  final AudioRecorder _recorder = AudioRecorder();
  WebSocketChannel? _channel;
  StreamSubscription<Uint8List>? _micSubscription;
  AudioSource? _playbackSource;
  // play()'in dondurdugu "calma ornegi". Kullanici raporu: ilk tur hep
  // sesli, sonraki turlarda veri hatasiz akiyor ama ses duyulmuyordu.
  // Once getIsValidVoiceHandle ile kontrol denendi ama HER ZAMAN true
  // donuyordu (dokumana gore "valid" hem "playing" hem "paused"
  // sayiliyor - handle "gecersiz" olmuyordu, sadece PAUSED takiliyordu).
  // Sonrasinda elle getPause/setPause polling denendi (once her parcada,
  // sonra throttled) ama ikisi de ya kesik ses ya eksik tespit
  // uretiyordu. Kok cozum artik setBufferStream'in resmi `onBuffering`
  // callback'i (bkz. _connect()) - motorun KENDI "tamponluyorum"
  // sinyaline dayanan, tahmine degil kanita dayali bir tetikleyici.
  SoundHandle? _playbackHandle;
  bool _resumingPlayback = false;
  // TESHIS (2026-08-24, onBuffering eklendikten SONRA): 2. turda ses
  // sessiz kalirken teshis logu onBuffering'in HIC TETIKLENMEDIGINI
  // gosterdi (yani motor "duraklatildi" bile demiyordu) - demek ki
  // "paused" teorisi bu sefer yanlisti, handle muhtemelen dogrudan
  // GECERSIZ/BITMIS hale geliyor. Her turun ILK ses parcasinda (bu
  // bayrakla isaretlenen, chunk basina degil tur basina TEK SEFER)
  // handle'in hala gecerli olup olmadigi kontrol ediliyor - gecersizse
  // play() ile TAZE bir handle aliniyor (ayni source uzerinde), gecerli
  // ama PAUSED ise setPause(false) deneniyor.
  bool _awaitingFirstChunkOfTurn = true;
  String? _token;

  // Uzun gorusme destegi: sunucudan "reconnect_needed" (Gemini Live'in
  // ~15dk sinirina yaklastigini haber veren GoAway) sinyali gelince
  // buraya yazilir, bir sonraki _connect() cagrisinda WS URL'ine eklenip
  // TUKETILIR (sonra null'a doner) - boylece Gemini tarafinda konusma
  // baglami mumkun oldugunca korunarak sorunsuzca yeniden baglanilir.
  String? _pendingResumptionHandle;

  // Yanki koruma: donanim AEC'i olmadan (kulaksiz/hoparlorle kullanimda)
  // Aura'nin sesi mikrofona sizip Gemini'nin "kullanici konusuyor" sanip
  // kendi kendini kesmesine (ve bu hizli kesinti dongusunun SoLoud'u
  // kilitleyip tum uygulamayi dondurmesine) yol aciyordu. Aura konusurken
  // mikrofonu sunucuya GONDERMEYEREK bu dongude kesilir - konusma hala
  // dogal sirayla akar, sadece Aura'nin sozu bu sirada kesilemez.
  //
  // BULUNDU (2026-08-24, kullanicinin "sozunu kesemiyorum" sikayeti
  // sonrasi arastirma): `record` paketinin RecordConfig'inde zaten
  // `echoCancel`/`autoGain`/`noiseSuppress` alanlari var ve bunlar
  // platform-native yanki iptaline BAGLI (web: getUserMedia
  // echoCancellation constraint'i; Android: AcousticEchoCanceler/
  // NoiseSuppressor/AutomaticGainControl ses efektleri; iOS: AVAudioSession
  // - ucu paket kaynagindan dogrulandi) - biz bunlari HIC ACMAMIŞTIK
  // (varsayilan false). Bu platformlarda GERCEK donanim/OS yanki iptali
  // varken, kendi kaba "konusurken mikrofonu tamamen kapat" cozumumuze
  // hic gerek yok VE bu tam olarak "sozunu kesememe" sikayetinin sebebiydi.
  // Windows'ta (record_windows kaynaginda AEC/ses efekti bulunamadi -
  // dogrulandi) hala gercek bir donanim AEC'i yok, o platformda eski
  // (guvenli ama kesintisiz) tam-susturma davranisi KORUNUYOR.
  /// UI icin: kamera hazir olunca CameraPreview(bunu) render eder. Henuz
  /// hazir degilse (ya da goruntulu gorusme degilse/kamera hic yoksa) null.
  CameraController? get cameraController => _cameraController;

  bool get _hasNativeEchoCancellation {
    if (kIsWeb) return true;
    try {
      return Platform.isAndroid || Platform.isIOS || Platform.isMacOS;
    } catch (_) {
      return false;
    }
  }

  bool _muteMic = false;
  Timer? _unmuteTimer;
  int _audioChunkCounter = 0;

  // GORUNTULU GORUSME (2026-09-04, kullanici istegi: "canli kamera acilsin
  // sesli ve goruntulu konussun"). BILEREK ana ses durum makinesinden
  // TAMAMEN izole tutuldu - burada olusabilecek HERHANGI bir hata (kamera
  // izni, donanim, format) sesli aramanin GERI KALANINI (mikrofon/SoLoud)
  // hicbir sekilde etkilememeli, tipki WakelockPlus'in "kritik degil"
  // felsefesiyle ayni (bkz. yukarida _connect() icindeki WakelockPlus
  // try/catch yorumu). CameraController BILEREK immutable VoiceCallState'in
  // DISINDA - UI, hazir olunca `cameraController` getter'iyla dogrudan okur.
  CameraController? _cameraController;
  Timer? _frameTimer;
  bool _videoRequested = false;
  // _startVideoCapture'in USTUSTE calismasini engeller. BULUNDU (2026-09-05,
  // kullanici gercek Android/Chrome testi - "kamerada donma var, kendimi
  // goremiyorum" + ekran goruntusu): kamera istegi ESKIDEN _connect()'in
  // SONUNDA (mikrofon izni + WakelockPlus + SoLoud init + WebSocket + mic
  // stream'in HEPSINDEN sonra) yapiliyordu - o noktada tarayicinin "gecici
  // kullanici etkilesimi" penceresi (dokunustan ~5sn sonra kapanir) coktan
  // gecmis oluyor, mobil Chrome getUserMedia(video) istegini ya sessizce
  // reddediyor ya da izin dialogunu hic gostermiyor. Artik kamera istegi
  // startCall()'in EN BASINDA, dokunusun hemen ardindan, ses zinciriyle
  // PARALEL yapiliyor.
  bool _videoCaptureStarting = false;
  // primeCamera() bu arama denemesi icin cagrildi mi? startCall bunu gorup
  // kamerayi TEKRAR denemez / cameraFailed'i sifirlamaz (prime zaten sonucu
  // belirledi). endCall/_cleanup'ta sifirlaniyor.
  bool _cameraPrimeAttempted = false;
  // takePicture() cagrisi zaten devam ederken USTUSTE ikinci bir cagri
  // atmamak icin (bazi platformlarda/donanimlarda "capture already in
  // progress" hatasi/kilitlenmesine yol acabiliyor) - bkz. _sendVideoFrame.
  bool _captureInFlight = false;

  // BULUNDU (2026-08-24, kullanici raporu + ekran goruntusu: bir "user"
  // baloncugunda Aura'nin BIR ONCEKI cumlesi BIREBIR AYNI sekilde
  // beliriyordu): eski sabit "turn_complete'ten 500ms sonra ac" mantigi
  // YANLIS varsayima dayaliydi - Gemini turn_complete'i "tum sesi
  // URETTIM" anlaminda gonderiyor, "hoparlorden CALINDI" degil. Veri
  // agdan hizli gelip SoLoud tamponunda BIRIKMIS olabilir, hoparlorden
  // fiziksel olarak calinmasi hala saniyeler surebilir - 500ms bu sure
  // dolmadan mikrofonu aciyordu, Aura'nin kendi sesi mikrofona sizip
  // Gemini'ye "yeni kullanici sesi" olarak gidiyor, Gemini de kendi
  // soyledigi cumleyi bal gibi transkript ediyordu (TTS sesi net oldugu
  // icin ASR'nin bunu dogru okumasi kolay - iste bu yuzden "user" mesaji
  // Aura'nin cumlesiyle harfiyen ayniydi). Fix: sabit sure yerine
  // SoLoud'un GERCEK calma pozisyonunu (getPosition) izleyip, o tura ait
  // TUM ses verisi fiilen calininca mikrofonu aciyoruz - bkz.
  // _scheduleUnmuteWhenPlaybackCatchesUp().
  int _bufferedDurationMs = 0;
  static const int _pcmBytesPerMs = 48; // 24000 Hz * 1 kanal * 2 bayt / 1000
  Timer? _unmuteCheckTimer;

  // Beklenmedik baglanti kopmasi (Gemini konjesyonu, gecici ag sorunu vb.)
  // durumunda kullaniciyi elle "tekrar dene" tusuna basmaya zorlamadan
  // OTOMATIK olarak yeniden baglanmayi dener. Gercekten baglanamiyor
  // olma ihtimaline karsi (backend cokmus vb.) sonsuz donguye girmesin
  // diye bir ust sinir var - o noktada kullaniciya hata gosterilir.
  int _autoRetryCount = 0;
  static const int _maxAutoRetries = 3;
  bool _reconnecting = false;

  // Masaustunde pencere GERCEKTEN gizlendiginde (paused/hidden - Flutter
  // motorunu askiya alan durum) doldurulur; resumed'da "ne kadar sure
  // askidaydik" bunun uzerinden olculur. inactive (sadece odak kaybi,
  // motor askiya ALINMAZ) bunu doldurmaz - o yuzden kisa odak degisimleri
  // gereksiz yeniden baglanma tetiklemez. resumed islenince null'a doner.
  DateTime? _desktopHiddenAt;
  // resumed olayi kisa araliyla birden fazla tetiklenebilir - askidan-
  // donus yeniden baglanmasi zaten calisirken ikinciyi baslatma.
  bool _resumeReconnectInFlight = false;

  // Sunucu "limit_reached" gonderip baglantiyi kendi kapattiginda,
  // hemen ardindan gelen onDone/onError'un OTOMATIK yeniden baglanmayi
  // tetiklememesi icin - aksi halde ayni gunluk limite tekrar carpip
  // sonsuz bir "baglan->reddedil" donguye girer.
  bool _limitReached = false;

  // KRITIK BULUNAN BUG (teshis loguyla kanitlandi): endCall()/retry()
  // _channel.sink.close()'u cagirdiginda, bu WebSocket'in onDone
  // callback'ini tetikliyor - ama state HENUZ idle'a cevrilmemis
  // oluyor (state ancak _cleanup() bittikten SONRA degisiyor). Bu
  // yuzden _handleUnexpectedDisconnect() bunu "beklenmedik kopma"
  // saniyor ve OTOMATIK YENIDEN BAGLANMAYI tetikleyip IKINCI, cakisan
  // bir _cleanup() cagrisi baslatiyor - iki es zamanli cleanup ayni
  // native SoLoud motoruna dokununca setDataIsEnded()/deinit() kilitlenip
  // TUM UYGULAMAYI donduruyordu. Bu bayrak, KENDI kapatmamizi (endCall/
  // retry) ayirt edip _handleUnexpectedDisconnect'in bu durumda hic
  // calismamasini saglar.
  bool _intentionalClose = false;

  // GERI ALINDI (bkz. asagidaki not): "her tur icin taze source" denemesi
  // teshis logunda KANITLANMIS sekilde play()'in senkron FFI on-yuzunde
  // kilitleniyordu (2. play() cagrisinda) - buyuk ihtimalle her turda
  // BIRIKEN, hic dispose edilmeyen source'lar SoLoud'un native "aktif
  // ses" limitine (maxActiveVoiceCountReached) carpiyordu. flutter_soloud
  // kutuphanesinin KENDI resmi WebSocket ornegi
  // (github.com/alnitak/flutter_soloud, example/lib/buffer_stream/websocket.dart)
  // TEK bir AudioSource + TEK bir play() cagrisi kullanip yeni "tur"lari
  // resetBufferStream() ile yonetiyor - asagidaki kod artik bu resmi
  // deseni izliyor.

  @override
  VoiceCallState build() {
    // BULUNDU (2026-08-25, kullanici kaniti: iPhone/Safari'de gorusme
    // 3-4. turda sessizce kesildi). Railway sunucu loglari o oturumu
    // TAMAMEN SAGLIKLI gosteriyordu (6 tur, dogru interrupted sinyalleri)
    // - baglanti ISTEMCI tarafindan koptu (kod 1005, "abnormal closure").
    // Bu, sunucu tarafinda bugun duzelttigimiz Gemini-askida-kalma
    // sinifindan FARKLI bir sorun: telefon ekrani kilitlenince/Safari
    // sekme arka plana alininca (ya da hucresel/wifi gecisinde) uzun
    // omurlu WebSocket baglantisi OS/tarayici tarafindan sessizce
    // kesiliyor olabilir - uygulamanin bundan hicbir haberi yoktu.
    // Fix: uygulama arka plana alinirsa (AppLifecycleState.paused/hidden)
    // aktif bir gorusmeyi KENDIMIZ, acikca ve anlasilir bir mesajla
    // sonlandiriyoruz - zombi bir baglantinin sessizce olup gitmesini
    // beklemek yerine.
    WidgetsBinding.instance.addObserver(this);
    ref.onDispose(() {
      WidgetsBinding.instance.removeObserver(this);
      _unmuteTimer?.cancel();
      _unmuteCheckTimer?.cancel();
      _micSubscription?.cancel();
      _channel?.sink.close();
      WakelockPlus.disable();
      _frameTimer?.cancel();
      _cameraController?.dispose();
    });
    return const VoiceCallState();
  }

  // Kasitli: taban sinifin parametre adi "state", ama Riverpod'un kendi
  // Notifier.state getter/setter'iyla (bu sinifta her yerde kullanilan)
  // karisir - yeniden adlandirmak lint'i susturur ama gercek bir
  // belirsizlik/hata riski yaratirdi.
  @override
  // ignore: avoid_renaming_method_parameters
  void didChangeAppLifecycleState(AppLifecycleState lifecycleState) {
    // KOD INCELEMESI BULGUSU (2026-08-25): "connecting" durumu BILEREK
    // haric tutuldu. _connect() icindeki mikrofon izni istegi (OS'in
    // kendi izin dialogu) uygulamayi GECICI olarak "paused" durumuna
    // sokuyor - bu, kullanicinin gercekten uzaklastigi bir arka-plana-
    // alma degil. "connecting" aktif sayilirsa, HERKESIN ilk sesli
    // aramasi (izin dialogu acilir acilmaz) yanlislikla "arka plana
    // alindi" denip iptal ediliyordu.
    final isActiveCall =
        state.status == VoiceCallStatus.listening ||
        state.status == VoiceCallStatus.auraSpeaking;
    if (!isActiveCall) {
      return;
    }
    if (lifecycleState == AppLifecycleState.paused ||
        lifecycleState == AppLifecycleState.hidden) {
      // BULUNDU (2026-09-02, kullanici Windows testi + teshis logu): pencere
      // arkada kalinca/ortulunce Flutter masaustunde motoru + Dart
      // timer'larini askiya aliyor (AppLifecycleState.hidden + Win11 arka
      // plan kisiti). Log kaniti: 78sn hicbir sey yok, sonra birikmis ses
      // bir anda bosaliyor. Ama WebSocket KOPMUYOR - mobildeki gibi
      // gorusmeyi bitirmek yanlis olur (mobilde WS OS tarafindan sessizce
      // olduruluyor, o yuzden orada bitiriyoruz). Masaustunde gorusmeyi
      // KORU; geri donuldugunde (resumed) ne kadar askidaydik
      // (_desktopHiddenAt) 8sn'yi asiyorsa temiz yeniden baglan.
      if (_isDesktopPlatform) {
        _desktopHiddenAt = DateTime.now();
        _voiceDebugLog(
          "masaustu: pencere gizlendi ($lifecycleState) - gorusme korunuyor",
        );
        return;
      }
      _voiceDebugLog(
        "uygulama arka plana alindi ($lifecycleState) - aktif gorusme "
        "sonlandiriliyor",
      );
      unawaited(_endCallDueToBackground());
    } else if (lifecycleState == AppLifecycleState.resumed) {
      // Masaustunde GERCEK bir askiya-alinmadan (paused/hidden) donuldu VE
      // uzun surdu ise: kuyrukta bekleyen bayat sesi (birikmis
      // addAudioDataStream patlamasi) calmak yerine sessizce yeniden
      // baglaniyoruz. Ayni desen laptop uyku/uyanma + kisa ag kopmasini da
      // kapsar. NOT: sadece odak kaybi (inactive) _desktopHiddenAt'i
      // DOLDURMAZ - o yuzden kisa alt-tab'lar gereksiz yeniden baglanma
      // tetiklemez (onceki surumun bug'i: "son sunucu mesajindan beri"
      // olcuyordu, sessiz bir gorusmede odak donusu bile reconnect ediyordu).
      // _reconnectForSessionRefresh: _autoRetryCount'u artirmiyor, elde
      // resumption_handle varsa Gemini baglamini korur, yoksa taze baglanir.
      final hiddenAt = _desktopHiddenAt;
      _desktopHiddenAt = null;
      if (_isDesktopPlatform &&
          hiddenAt != null &&
          !_resumeReconnectInFlight &&
          !_reconnecting &&
          !_intentionalClose) {
        // !_reconnecting: pencere gizliyken WS koptuysa _reconnectAfterDelay
        // zaten devrede (masaustunde timer'lar askidayken bekliyor). resumed
        // olunca hem o devam eder hem burasi tetiklenir - ikisi ayni anda
        // _cleanup()+_connect() calistirirsa bu dosyanin butun savastigi
        // "iki es zamanli cleanup -> donma" sinifi geri gelir.
        final suspended = DateTime.now().difference(hiddenAt);
        if (suspended > const Duration(seconds: 8)) {
          _resumeReconnectInFlight = true;
          _voiceDebugLog(
            "masaustu: ${suspended.inSeconds}sn askidan donuldu - "
            "bayat ses yerine yeniden baglaniliyor",
          );
          unawaited(
            _reconnectForSessionRefresh().whenComplete(
              () => _resumeReconnectInFlight = false,
            ),
          );
        }
      }
    }
  }

  /// kIsWeb + Platform guard'li - sesli gorusme web'de de kosuyor.
  bool get _isDesktopPlatform {
    if (kIsWeb) return false;
    try {
      return Platform.isWindows || Platform.isLinux || Platform.isMacOS;
    } catch (_) {
      return false;
    }
  }

  /// endCall() gibi temizler, ama state'i sessizce idle'a dondurmek
  /// yerine kullaniciya NEDEN bittigini soyleyen bir hata mesaji birakir
  /// - uygulamaya geri donduğunde "neden kesildi?" diye sormasin diye.
  Future<void> _endCallDueToBackground() async {
    // KOD INCELEMESI BULGUSU (2026-08-25): _cleanup() icindeki
    // _channel.sink.close() cagrisinin onDone/onError callback'i HEMEN
    // degil, event loop'un SONRAKI bir turunda tetikleniyor - o ana
    // kadar _intentionalClose zaten false'a donmus oluyordu, bu yuzden
    // _handleUnexpectedDisconnect butun guard'lari gecip bu KASITLI
    // sonlandirmayi "beklenmedik kopma" sanip OTOMATIK YENIDEN
    // BAGLANIYORDU - arka plana alinmis/kilitli telefonda mikrofonu
    // ve ucretli Gemini oturumunu sessizce yeniden aciyordu. _limitReached
    // (idle_timeout ile ayni desen) bu geciken onDone'un otomatik
    // yeniden baglanmasini KESIN olarak engelliyor.
    _limitReached = true;
    _intentionalClose = true;
    await _cleanup();
    _intentionalClose = false;
    state = state.copyWith(
      status: VoiceCallStatus.error,
      errorMessage:
          "Görüşme, uygulama arka plana alındığı için sonlandırıldı. "
          "Tekrar aramak için dokun.",
    );
  }

  Future<void> startCall(String token, {bool video = false}) async {
    _voiceDebugLog("===== startCall() (video=$video) =====");
    _audioChunkCounter = 0;
    _bufferedDurationMs = 0;
    _token = token;
    _autoRetryCount = 0;
    _limitReached = false;
    _awaitingFirstChunkOfTurn = true;
    // Kamera paketinin Windows/Linux/macOS destegi yok (bkz. chat_screen.dart
    // _isDesktop ile ayni ilke) - masaustunde istense bile sessizce
    // sesli-only'ye duser, kullaniciyi hatayla karsilamiyoruz.
    _videoRequested = video && !_isDesktopPlatform;
    // primeCamera() zaten cagrildiysa (mobil web'de dokunus icinden) onun
    // sonucunu (cameraReady / cameraFailed) KORU - sifirlama, tekrar deneme.
    state = state.copyWith(
      status: VoiceCallStatus.connecting,
      videoEnabled: _videoRequested,
      cameraReady: _cameraPrimeAttempted ? state.cameraReady : false,
      cameraFailed: _cameraPrimeAttempted ? state.cameraFailed : false,
      cameraOff: false,
    );
    // KRITIK (bkz. _videoCaptureStarting yorumu): prime edilmediyse kamera
    // istegini BURADA, dokunusun hemen ardindan, ses baglantisiyla PARALEL
    // baslat. _sendVideoFrame zaten _channel yoksa kare gondermeyi atliyor.
    if (_videoRequested && !_cameraPrimeAttempted && !state.cameraFailed) {
      unawaited(_startVideoCapture());
    }
    await _connect();
  }

  Future<void> _connect() async {
    // BULUNDU (2026-08-24, web/Safari testi): bu kontrol hicbir try/catch
    // icinde degildi - Safari'nin mikrofon izin API'si masaustu
    // tarayicilardan/Windows'tan farkli davranabiliyor (bazen throw
    // ediyor, bazen sessizce false donuyor). Ayrica TUM hata dallarinda
    // errorMessage hic set edilmiyordu - kullaniciya sadece jenerik
    // "Baglanti sorunu" gorunuyordu, hangi adimin basarisiz oldugu
    // (izin mi, ses motoru mu, sunucu mu, mikrofon akisi mi) hic
    // belli olmuyordu. Artik her adim ayirt edilebilir bir mesaj birakiyor.
    bool hasMicPermission;
    try {
      hasMicPermission = await _recorder.hasPermission();
    } catch (e) {
      _voiceDebugLog("hasPermission() HATASI: $e");
      state = state.copyWith(
        status: VoiceCallStatus.error,
        errorMessage: "Mikrofon izni kontrol edilemedi: $e",
      );
      return;
    }
    if (!hasMicPermission) {
      _voiceDebugLog("mikrofon izni yok");
      state = state.copyWith(
        status: VoiceCallStatus.error,
        errorMessage:
            "Mikrofon izni verilmedi. Tarayıcı/telefon ayarlarından "
            "mikrofon iznini kontrol et.",
      );
      return;
    }

    try {
      await WakelockPlus.enable();
    } catch (e) {
      // Ekranin acik kalmasi kritik degil - gorusmeyi bu yuzden iptal etme.
      _voiceDebugLog("WakelockPlus.enable() HATASI (yoksayildi): $e");
    }

    try {
      if (!SoLoud.instance.isInitialized) {
        _voiceDebugLog("init() cagriliyor");
        await SoLoud.instance.init();
        _voiceDebugLog("init() tamamlandi");
      }

      // Resmi flutter_soloud WebSocket ornegindeki desen: TEK bir
      // AudioSource, TEK bir play() cagrisi - tum gorusme boyunca.
      _voiceDebugLog("setBufferStream() cagriliyor");
      _playbackSource = SoLoud.instance.setBufferStream(
        sampleRate: 24000,
        channels: Channels.mono,
        format: BufferType.s16le,
        bufferingType: BufferingType.preserved,
        // 0 verilirse, play() bos tamponla cagrildiginda akis aninda
        // "bitti" sayilip duruyor - veri gelmeden once. Kucuk bir deger
        // hem dusuk gecikme saglar hem bu erken-bitis sorununu onler.
        // 0.3s -> 0.5s (2026-08-24) -> 0.8s (2026-09-02). Kullanici hala
        // "seste degisme/kekeleme" bildirdi; teshis logu tur ORTASINDA
        // `onBuffering ... hala PAUSED` gosterdi - yani ag+Gemini sesi
        // patlamali geliyor, 0.5s'lik tampon payi bazi bosluklari hala
        // kapatamiyor. Payi 0.8s'ye cikardik: ilk sese kadarki gecikme
        // ~0.3s artar (kabul edilebilir), ama tur ici kuru-tampon
        // duraklamalari belirgin azalmali.
        bufferingTimeNeeds: 0.8,
        // BULUNDU (paket kaynagi + resmi ornek incelendi, bkz. pub cache
        // flutter_soloud-3.5.4/example/lib/buffer_stream/websocket.dart):
        // motorun KENDISI, tampon tukenip otomatik duraklattiginda VE
        // yeterli veri birikip otomatik devam ettirdiginde bu callback'i
        // cagiriyor - resmi ornek elle getPause/setPause polling'i HIC
        // YAPMIYOR, sadece bu sinyali dinliyor. Bizim onceki "her parcada
        // veya throttled 300ms'de bir kontrol et" yaklasimimiz TAHMINE
        // dayaliydi; bu ise motorun "su an tamponluyorum" dedigi GERCEK
        // ani yakalar - hem daha az gereksiz cagri (dusuk kesinti riski)
        // hem kesin teshis (log, bir sonraki testte auto-resume'un
        // gercekten calisip calismadigini kesin gosterecek).
        onBuffering: (isBuffering, handle, time) {
          _voiceDebugLog(
            "onBuffering: isBuffering=$isBuffering handle=$handle time=$time",
          );
          if (!isBuffering) return;
          // Motor tamponlamaya basladi (tampon tukendi, muhtemelen turlar
          // arasi bosluk). Dokumantasyona gore bufferingTimeNeeds (0.3s)
          // kadar YENI veri birikince motor KENDISI devam ettirmeli - ama
          // onceki testlerde bu otomatik devam etme GUVENILIR calismadi.
          // Guvenlik agi: bufferingTimeNeeds'den biraz fazla bir sure
          // sonra hala duraklamis mi diye TEK SEFER kontrol edip, oyleyse
          // elle devam ettiriyoruz. NOT: bunu onBuffering callback'inin
          // ICINDE SENKRON yapmiyoruz - motor muhtemelen bu callback'i
          // kendi ic isleminin ORTASINDA cagiriyor, bu oturumda senkron
          // native cagrilarin motor mesguken kilitlenebildigini defalarca
          // kanitladik (play/disposeSource/setDataIsEnded/deinit) - o
          // yuzden Timer ile erteleyip motorun o anki islemini bitirmesine
          // firsat taniyoruz.
          Timer(const Duration(milliseconds: 400), () {
            final h = _playbackHandle;
            if (h == null) return;
            try {
              if (SoLoud.instance.getPause(h)) {
                _voiceDebugLog(
                  "onBuffering guvenlik agi: hala PAUSED, setPause(false)",
                );
                SoLoud.instance.setPause(h, false);
              }
            } catch (e) {
              _voiceDebugLog("onBuffering guvenlik agi HATASI: $e");
            }
          });
        },
      );
      _voiceDebugLog("play() cagriliyor");
      // flutter_soloud 4.x'te play() artik SENKRON (SoundHandle donuyor,
      // Future<SoundHandle> degil) - 4.1.4/4.1.7 degisiklik gunlugune gore
      // bu, motorun kendi mutex'i tutulurken callback tetiklenmesinden
      // kaynaklanan "wedged engine"/deinit() takilma sinifi hatalarin kok
      // duzeltmesinin bir parcasi. await kaldirildi (artik gereksiz).
      _playbackHandle = SoLoud.instance.play(_playbackSource!);
      _voiceDebugLog("play() tamamlandi (handle=$_playbackHandle)");
    } catch (e) {
      debugPrint("SoLoud baslatma hatasi: $e");
      _voiceDebugLog("baslatma HATASI: $e");
      state = state.copyWith(
        status: VoiceCallStatus.error,
        errorMessage: "Ses motoru başlatılamadı: $e",
      );
      return;
    }

    final resumptionHandle = _pendingResumptionHandle;
    _pendingResumptionHandle = null;
    final handleQuery = resumptionHandle != null
        ? "&resumption_handle=${Uri.encodeQueryComponent(resumptionHandle)}"
        : "";
    final videoQuery = _videoRequested ? "&video=1" : "";
    final uri = Uri.parse(
      "$_wsBase/api/voice?token=$_token$handleQuery$videoQuery",
    );

    try {
      _channel = WebSocketChannel.connect(uri);
      _channel!.stream.listen(
        _handleServerMessage,
        onError: (e) {
          debugPrint("Sesli baglanti hatasi: $e");
          _handleUnexpectedDisconnect();
        },
        onDone: () {
          _handleUnexpectedDisconnect();
        },
      );
    } catch (e) {
      debugPrint("WebSocket baglanti hatasi: $e");
      state = state.copyWith(
        status: VoiceCallStatus.error,
        errorMessage: "Sunucuya bağlanılamadı: $e",
      );
      return;
    }

    try {
      final micStream = await _recorder.startStream(
        RecordConfig(
          encoder: AudioEncoder.pcm16bits,
          sampleRate: 16000,
          numChannels: 1,
          // BULUNDU: bu ucu daha once hic acilmamisti (varsayilan false) -
          // web/Android/iOS'ta platform-native yanki iptalini/otomatik
          // kazanci/gurultu bastirmayi etkinlestiriyor (bkz. _muteMic
          // aciklamasi, kaynak dogrulandi). Windows'ta desteklenmiyor,
          // zararsizca yoksayilir.
          echoCancel: true,
          autoGain: true,
          noiseSuppress: true,
        ),
      );

      _micSubscription = micStream.listen((chunk) {
        if (_muteMic) return;
        _channel?.sink.add(chunk);
        // Kullanici istegi (2026-08-26): sesli gorusme ekrani "sade"ydi -
        // artik ufak bir dalga gostergesi var. BILEREK ayri, hafif bir
        // provider'a yaziliyor (bkz. mic_level_notifier.dart) - ana
        // durumun (voiceCallProvider) icine konsaydi, chat_screen.dart'in
        // TUM mesaj listesi saniyede ~10 kez yeniden cizilirdi.
        ref.read(micLevelProvider.notifier).update(_computeMicLevel(chunk));
      });
    } catch (e) {
      debugPrint("Mikrofon akis hatasi: $e");
      state = state.copyWith(
        status: VoiceCallStatus.error,
        errorMessage: "Mikrofon akışı başlatılamadı: $e",
      );
      return;
    }

    state = state.copyWith(status: VoiceCallStatus.listening);

    // Kamera zaten acildiysa (primeCamera / startCall'daki erken cagri) ama
    // kare gonderme timer'i henuz baslamadiysa (o an _channel yoktu) burada
    // baslat. Kamera henuz acilmadiysa (nadir) burada dene.
    if (_videoRequested && !state.cameraFailed) {
      if (_cameraController != null) {
        _ensureFrameTimer();
      } else {
        unawaited(_startVideoCapture());
      }
    }
  }

  void _ensureFrameTimer() {
    if (_frameTimer != null || _cameraController == null) return;
    _frameTimer = Timer.periodic(
      const Duration(milliseconds: 1400),
      (_) => unawaited(_sendVideoFrame()),
    );
  }

  /// iOS Safari (ve mobil web genel): getUserMedia SADECE kullanici
  /// hareketinin (tap) KENDI cagri yiginindan tetiklenirse calisir - araya
  /// giren await/microtask/navigation bu zinciri koparabiliyor, ve o
  /// zaman izin dialogu hic gorunmuyor. Bu yuzden kamera izni ekrana
  /// GECMEDEN once, dogrudan buton tikin icinde ("_startVideoCall" ->
  /// buradan) isteniyor. Native/Android'de zararsiz - sadece kamerayi
  /// biraz erken hazirlar.
  Future<void> primeCamera() async {
    if (_isDesktopPlatform) return;
    _videoRequested = true;
    _cameraPrimeAttempted = true;
    await _startVideoCapture(startFrames: false);
  }

  /// Kamerayi acar (on kamera tercih edilir) ve dusuk-hizli (~0.7 kare/sn)
  /// periyodik JPEG karelerini AYNI sesli WebSocket uzerinden Gemini Live
  /// oturumuna yollar (bkz. aura_voice.py relay_client_to_gemini - JSON
  /// {"type":"video_frame","data": base64}). HICBIR ADIMDA ana sesli
  /// aramayi BLOKLAMAZ/BOZMAZ - herhangi bir hata burada sessizce
  /// yutulur, kullanici sesli aramaya (kamerasiz) devam edebilir.
  Future<void> _startVideoCapture({bool startFrames = true}) async {
    if (_videoCaptureStarting || _cameraController != null) return;
    _videoCaptureStarting = true;
    try {
      // BULUNDU (2026-09-05, gercek iOS Safari testi + ekran goruntuleri):
      // primeCamera dokunus-icinden cagrilinca iOS ARTIK izin dialogunu
      // gosteriyor (once hic gostermiyordu). Ama web'de availableCameras()
      // ve initialize()'in ikisi de getUserMedia'yi tetikliyor ve izin
      // dialogu ACIKKEN cagri blokta bekliyor. Kisa timeout (6/7sn)
      // kullanici dialogu Turkce okuyup "Izin ver"e BASMADAN once firliyor
      // -> cameraFailed; sonra izin verilse bile is bitmis oluyordu. Ustelik
      // iki dialog ust uste geliyor (kamera + mikrofon). Cozum: timeout'lar
      // SADECE gercekten asili kalan (ne onay ne ret donen) cagriyi
      // yakalamak icin var - kullanici dialogu icin BOL sure taniyoruz
      // (30 / 45sn). Bu sirada ekran "frozen" degil; kullanici zaten
      // dialogla ugrasiyor.
      final cameras = await availableCameras().timeout(
        const Duration(seconds: 30),
      );
      if (cameras.isEmpty) {
        _voiceDebugLog("video: kullanilabilir kamera yok");
        state = state.copyWith(cameraFailed: true);
        return;
      }
      final front = cameras.firstWhere(
        (c) => c.lensDirection == CameraLensDirection.front,
        orElse: () => cameras.first,
      );
      // low: kucuk/hizli JPEG karesi yeterli (Gemini'ye giden 0.7fps'lik
      // durgun kareler icin yuksek cozunurluk gereksiz maliyet/gecikme).
      final controller = CameraController(
        front,
        ResolutionPreset.low,
        enableAudio: false,
      );
      // izin dialogu initialize() icinde de acilabilir ve kullanici
      // cevaplayana kadar burada beklenir - bu yuzden sure BOL (45sn):
      // iki ust uste dialogu okuyup onaylamak icin fazlasiyla yeterli,
      // ama gercekten asili kalan (hic cozulmeyen) bir cagriyi da sonsuza
      // dek beklemez - sonucta kullaniciya bir cameraFailed garanti eder.
      await controller.initialize().timeout(const Duration(seconds: 45));
      // Bu sirada gorusme zaten bitmis olabilir (kullanici hizlica
      // endCall() bastiysa) - o durumda yeni acilan kamerayi hemen kapat.
      // NOT: primeCamera (startFrames=false) DAHA arama baslamadan cagrildigi
      // icin status HALA idle olur - o durumda dispose ETME, kamera arama
      // baslayana kadar hazir beklesin.
      if (startFrames && state.status == VoiceCallStatus.idle) {
        await controller.dispose();
        return;
      }
      _cameraController = controller;
      state = state.copyWith(cameraReady: true);
      _voiceDebugLog("video: kamera hazir (${front.lensDirection})");

      // Kare gonderme timer'i: normalde SADECE arama akisinda (startFrames).
      // Ama iOS'ta kullanici izin dialogunu YAVAS onayladiysa prime hala
      // devam ederken _connect() bitmis, ve o an _cameraController null
      // oldugu icin timer'i baslatamamis olabilir (_connect sonu ->
      // _startVideoCapture() cagirir ama ust guard'dan doner). Bu yuzden
      // prime bitiminde de: arama artik aktifse ve kanal varsa timer'i
      // BURADA baslat - yoksa onizleme acilir ama Aura'ya hic kare gitmez.
      if (startFrames ||
          (_channel != null && state.status != VoiceCallStatus.idle)) {
        _ensureFrameTimer();
      }
    } catch (e) {
      // BULUNDU (2026-09-04, gercek testte kanitlandi): burada eskiden
      // sadece debug loguna yazip SESSIZCE vazgeciliyordu - kullaniciya
      // hicbir geri bildirim gitmiyordu, ekran sonsuza dek "Kamera
      // aciliyor..." yaziyordu (izin reddedildiginde/donanim yoksa).
      // Mikrofon tarafinin (_connect() basindaki hasMicPermission kontrolu)
      // AKSINE net bir mesaj yoktu. cameraFailed artik video_call_screen.dart'a
      // "beklemeyi birak, kullaniciya soyle" sinyali veriyor - CAGRIYI
      // SONLANDIRMIYOR (ses hala calisir, sadece kamera onizlemesi yerine
      // anlasilir bir mesaj gosterilir).
      _voiceDebugLog("video: baslatma HATASI (sesli devam ediyor): $e");
      state = state.copyWith(cameraFailed: true);
    } finally {
      _videoCaptureStarting = false;
    }
  }

  /// video_call_screen.dart'taki "Kamerayi tekrar dene" tusundan cagrilir -
  /// izni sonradan verip tekrar denemek isteyen kullanici icin. Cagriyi
  /// yeniden baslatmaz, sadece kamerayi tekrar acmayi dener.
  Future<void> retryCamera() async {
    if (!_videoRequested || _cameraController != null) return;
    state = state.copyWith(cameraFailed: false, cameraReady: false);
    await _startVideoCapture();
  }

  /// Kamerayi kullanici ISTEGIYLE kapatir/acar - hem alt yaridaki
  /// dokunustan hem sesli komuttan ("kamerayi kapat" / "kamerayi ac")
  /// cagrilir. Sesli aramayi HIC etkilemez, sadece video katmanini.
  /// 2026-09-05, kullanici sorusu: "kolunu kullanamayan biri kamerayi
  /// nasil kapatacak" -> sesle ya da tek dokunusla.
  Future<void> toggleCameraByUser({required bool off}) async {
    if (_isDesktopPlatform || !_videoRequested) return;
    if (off) {
      if (state.cameraOff) return;
      state = state.copyWith(cameraOff: true, cameraReady: false);
      await _stopVideoCapture();
      // _stopVideoCapture _videoRequested'a dokunmaz ama _cameraPrimeAttempted'i
      // sifirlar - tekrar acilabilmesi icin niyeti geri koyuyoruz.
      _videoRequested = true;
    } else {
      if (!state.cameraOff && _cameraController != null) return;
      state = state.copyWith(
        cameraOff: false,
        cameraFailed: false,
        cameraReady: false,
      );
      await _startVideoCapture();
    }
  }

  /// Sesli görüşmede turn_complete ile gelen NIHAI kullanici transkriptini
  /// kucuk bir komut sozlugune karsi kontrol eder. Eslesirse ilgili yan
  /// etkiyi yapar (su an sadece kamera ac/kapa). Konusmayi ENGELLEMEZ -
  /// soz yine sohbet balonuna duser, Aura da normalde yanit verir; sadece
  /// istemci tarafi bir aksiyon eklenir. Video istenmediyse hic calismaz.
  void _maybeHandleVoiceCommand(String userText) {
    if (_isDesktopPlatform || !_videoRequested) return;
    final t = _foldTr(userText);
    // Cok uzun cumlelerde (kullanici kamerayi ANLATIYOR ama komut vermiyor)
    // yanlis tetiklememek icin kisa tutuyoruz.
    if (t.split(RegExp(r"\s+")).length > 6) return;
    final subject =
        t.contains("kamera") || t.contains("goruntu") || t.contains("video");
    if (!subject) return;
    final wantsOff =
        t.contains("kapat") || t.contains("kapan") || t.contains("durdur");
    final wantsOn =
        t.contains(" ac") ||
        t.startsWith("ac") ||
        t.contains("acar mi") ||
        t.contains("acsana") ||
        t.contains("geri ac");
    if (wantsOff && !state.cameraOff) {
      _voiceDebugLog("sesli komut: kamera kapat ('$userText')");
      unawaited(toggleCameraByUser(off: true));
    } else if (wantsOn && !wantsOff && state.cameraOff) {
      _voiceDebugLog("sesli komut: kamera ac ('$userText')");
      unawaited(toggleCameraByUser(off: false));
    }
  }

  /// Turkce'ye duyarli, aksan-katlayan kucuk normalize edici - SADECE
  /// sesli komut eslestirmesi icin (backend'deki genel fold'un istemci
  /// karsiligi degil, ona ihtiyac da yok).
  String _foldTr(String s) {
    var r = s.toLowerCase().trim();
    const map = {
      "ı": "i",
      "i̇": "i",
      "İ": "i",
      "ş": "s",
      "ğ": "g",
      "ü": "u",
      "ö": "o",
      "ç": "c",
      "â": "a",
      "î": "i",
      "û": "u",
    };
    map.forEach((k, v) => r = r.replaceAll(k, v));
    return r;
  }

  Future<void> _sendVideoFrame() async {
    final controller = _cameraController;
    if (controller == null ||
        !controller.value.isInitialized ||
        _captureInFlight ||
        _channel == null) {
      return;
    }
    _captureInFlight = true;
    try {
      final file = await controller.takePicture();
      final bytes = await file.readAsBytes();
      _channel?.sink.add(
        jsonEncode({"type": "video_frame", "data": base64Encode(bytes)}),
      );
    } catch (e) {
      _voiceDebugLog("video: kare gonderme HATASI (yoksayildi): $e");
    } finally {
      _captureInFlight = false;
    }
  }

  Future<void> _stopVideoCapture() async {
    _frameTimer?.cancel();
    _frameTimer = null;
    _videoCaptureStarting = false;
    _cameraPrimeAttempted = false;
    final controller = _cameraController;
    _cameraController = null;
    _captureInFlight = false;
    if (controller != null) {
      try {
        await controller.dispose();
      } catch (e) {
        _voiceDebugLog("video: controller.dispose() HATASI (yoksayildi): $e");
      }
    }
  }

  /// Kullanicinin "deklanşor" tusuna basmasiyla cagrilir - o anki kareyi
  /// TAM kalitede yakalayip mevcut, kanitlanmis fotograf-analiz hattina
  /// (chatProvider.sendFileForAnalysis -> /api/analyze) yollar. Boylece
  /// "fotograf cekebilsin, Aura efekt yapabilsin" istegi SIFIR yeni backend
  /// kodu ve SIFIR yeni mahremiyet yuzeyiyle karsilanir - AuraImageReveal
  /// animasyonu ve iki katmanli (nesnel+duygusal) analiz zaten oradan gelir.
  Future<bool> captureAndAnalyzePhoto() async {
    final controller = _cameraController;
    if (controller == null || !controller.value.isInitialized) return false;
    try {
      final file = await controller.takePicture();
      final bytes = await file.readAsBytes();
      await ref
          .read(chatProvider.notifier)
          .sendFileForAnalysis(bytes, mimeType: "image/jpeg");
      return true;
    } catch (e) {
      _voiceDebugLog("video: deklansor HATASI: $e");
      return false;
    }
  }

  void _handleServerMessage(dynamic message) {
    // Sunucudan gelen HERHANGI bir mesaj, baglantinin saglikli oldugunun
    // kaniti - otomatik yeniden baglanma sayacini sifirla ki uzun bir
    // gorusmede araya sikisan birkac ayri, gecici kopma toplam hakkı
    // tuketmesin.
    _autoRetryCount = 0;

    if (message is List<int>) {
      // Aura'nin sesi hoparlorden cikmaya baslayacak. Gercek donanim/OS
      // yanki iptali OLAN platformlarda (bkz. _hasNativeEchoCancellation)
      // mikrofonu HIC susturmuyoruz - boylece kullanici Aura'nin sozunu
      // GERCEKTEN kesebiliyor (sunucu zaten "interrupted" sinyalini
      // isliyor, bkz. asagida). AEC'siz platformlarda (Windows) eski
      // guvenli tam-susturma davranisi korunuyor.
      _unmuteTimer?.cancel();
      _unmuteCheckTimer?.cancel();
      if (!_hasNativeEchoCancellation) {
        _muteMic = true;
      }
      _bufferedDurationMs += (message.length / _pcmBytesPerMs).round();

      try {
        if (_playbackSource != null) {
          final handle = _playbackHandle;

          if ((_awaitingFirstChunkOfTurn || handle == null) &&
              !_resumingPlayback) {
            _awaitingFirstChunkOfTurn = false;
            var needsFreshHandle = handle == null;
            var needsUnpause = false;

            if (handle != null) {
              try {
                final valid = SoLoud.instance.getIsValidVoiceHandle(handle);
                _voiceDebugLog(
                  "tur basi kontrol - handle=$handle valid=$valid",
                );
                if (!valid) {
                  needsFreshHandle = true;
                } else {
                  final paused = SoLoud.instance.getPause(handle);
                  _voiceDebugLog("tur basi kontrol - paused=$paused");
                  needsUnpause = paused;
                }
              } catch (e) {
                _voiceDebugLog("tur basi durum kontrolu HATASI: $e");
              }
            }

            if (needsFreshHandle) {
              // Handle ya hic yok, ya da gecersiz/bitmis - play()'i
              // TEKRAR cagirip ayni source uzerinde TAZE bir handle
              // aliniyor (source'un kendisi hic dispose edilmiyor). Yeni
              // handle'in konumu (getPosition) 0'dan baslayacagi icin
              // tur-suresi sayacimizi da esitliyoruz - aksi halde
              // _scheduleUnmuteWhenPlaybackCatchesUp eski, artik gecersiz
              // handle'a ait birikmis bir sureyle kiyaslayip mikrofonu
              // gereksiz yere uzun sure kapali tutabilirdi.
              _bufferedDurationMs = 0;
              _resumingPlayback = true;
              _voiceDebugLog("handle yok/gecersiz - play() ile yenileniyor");
              // flutter_soloud 4.x'te play() artik senkron - eskiden
              // Future donduugu icin unawaited(...then/catchError...) ile
              // sarilmisti, artik duz bir try/catch yeterli.
              try {
                final newHandle = SoLoud.instance.play(_playbackSource!);
                _playbackHandle = newHandle;
                _resumingPlayback = false;
                _voiceDebugLog(
                  "play() (yenileme) tamamlandi (handle=$newHandle)",
                );
              } catch (e) {
                _resumingPlayback = false;
                _voiceDebugLog("play() (yenileme) HATASI: $e");
              }
            } else if (needsUnpause && handle != null) {
              try {
                _voiceDebugLog("tur basi setPause(false) cagriliyor");
                SoLoud.instance.setPause(handle, false);
              } catch (e) {
                _voiceDebugLog("tur basi setPause HATASI: $e");
              }
            }
          }

          _audioChunkCounter++;
          _voiceDebugLog("addAudioDataStream #$_audioChunkCounter cagriliyor");
          SoLoud.instance.addAudioDataStream(
            _playbackSource!,
            Uint8List.fromList(message),
          );
          _voiceDebugLog("addAudioDataStream #$_audioChunkCounter tamamlandi");
        }
      } catch (e) {
        debugPrint("SoLoud playback hatasi: $e");
        _voiceDebugLog("addAudioDataStream HATASI: $e");
      }

      if (state.status != VoiceCallStatus.auraSpeaking) {
        state = state.copyWith(status: VoiceCallStatus.auraSpeaking);
      }
      return;
    }

    try {
      final data = jsonDecode(message as String) as Map<String, dynamic>;
      final type = data["type"];

      if (type == "limit_reached") {
        _limitReached = true;
        state = state.copyWith(
          status: VoiceCallStatus.error,
          errorMessage: data["message"] as String?,
        );
        // KOD INCELEMESI BULGUSU (2026-08-25): sunucu kendi tarafini
        // zaten kapatiyor, ama _limitReached=true oldugu icin
        // _handleUnexpectedDisconnect'in onDone/onError'da yapacagi
        // guard erken return ediyor - yani mikrofon/soket/wakelock'u
        // BURADA BIZ temizlemezsek hicbir zaman temizlenmiyorlardi
        // (mikrofon acik kaliyor, kapali sink'e yazmaya devam edip
        // sessiz hatalar uretiyordu).
        unawaited(_cleanup());
      } else if (type == "error") {
        // Sunucu tarafinda Gemini Live bir turda tikanip kaldiginda
        // (gercek kullanici kanitiyla bulundu: mikrofon aciktan, ikinci
        // soru sorulunca hicbir yanit gelmeden oturum askida kaliyordu)
        // backend artik sessizce sonsuza dek beklemek yerine oturumu
        // kapatip bu sinyali yolluyor. _limitReached'i BILEREK set etmiyoruz
        // - bu, gunluk limit gibi kalici degil GECICI bir Gemini sorunu,
        // bu yuzden asagidaki _handleUnexpectedDisconnect kendi otomatik
        // yeniden baglanma mantigini (birkac deneme) calistirabilsin.
        _voiceDebugLog("sunucudan error sinyali: ${data["message"]}");
        state = state.copyWith(
          status: VoiceCallStatus.error,
          errorMessage: data["message"] as String?,
        );
      } else if (type == "idle_timeout") {
        // Kullanici uzun sure sessiz kaldi, sunucu gorusmeyi kendisi
        // nazikce sonlandirdi. Bu bir hata degil - _limitReached'i
        // (otomatik yeniden baglanmayi ENGELLEMEK icin, gunluk limitle
        // AYNI mekanizmayi kullanarak) BILEREK set ediyoruz: kullanici
        // zaten konusmuyordu, hemen yeniden baglanip sessizce beklemenin
        // bir anlami yok.
        _limitReached = true;
        _voiceDebugLog("sunucudan idle_timeout sinyali: ${data["message"]}");
        state = state.copyWith(
          status: VoiceCallStatus.error,
          errorMessage: data["message"] as String?,
        );
        // limit_reached ile ayni sebep: _limitReached=true oldugundan
        // _handleUnexpectedDisconnect erken donuyor, temizligi burada
        // biz yapmazsak mikrofon/soket acik kaliyordu.
        unawaited(_cleanup());
      } else if (type == "reconnect_needed") {
        // Gemini Live'in ~15dk oturum sinirina yaklasildi (GoAway).
        // Kullaniciya "hata" gibi gostermeden, elimizdeki devam-etme
        // tokeniyle SORUNSUZCA yeniden baglaniyoruz - bu _autoRetryCount'u
        // ARTIRMIYOR (bir basarisizlik degil, dogal bir oturum tazelemesi).
        _pendingResumptionHandle = data["resumption_handle"] as String?;
        _voiceDebugLog(
          "sunucudan reconnect_needed sinyali (uzun gorusme tazeleniyor, "
          "handle mevcut=${_pendingResumptionHandle != null})",
        );
        unawaited(_reconnectForSessionRefresh());
      } else if (type == "interrupted") {
        _voiceDebugLog("interrupted alindi (chunk #$_audioChunkCounter)");
        _awaitingFirstChunkOfTurn = true;
        // KRITIK BULUNAN 4. DONMA (teshis loguyla kanitlandi, ayni desenin
        // dorduncu tekrari - bkz. play()/setDataIsEnded()/deinit()): log
        // TAM OLARAK "resetBufferStream() cagriliyor" satirindan sonra
        // kesildi, "tamamlandi" hic gelmedi. Tetikleyici: kullanici Aura'nin
        // sozunu KESEREK konusmaya basladi, ve bu resetBufferStream() bir
        // ONCEKI addAudioDataStream() cagrisindan sadece 49ms sonra
        // geldi - motorun kendi ic ses-mixleme thread'i o veriyi hala
        // islerken resetBufferStream() ayni kaynagin ic durumunu degistirmeye
        // calisip kilitlenmis olmali. Onceki testlerde bu cagri hep guvenli
        // gorunmustu (senkron ama "hafif" sayilmisti) - meger SADECE
        // addAudioDataStream ile YAKIN ZAMANLI cagrildiginda risk varmis.
        // FIX: play()/deinit() gibi TAMAMEN kaldirmak yerine (bu cagri hala
        // gerekli - kesilen sozun kalintisini temizliyor), diger "riskli"
        // cagrilarda oldugu gibi kucuk bir Timer ile erteleyip motorun o
        // anki islemini bitirmesine firsat taniyoruz.
        if (_playbackSource != null) {
          final sourceAtInterrupt = _playbackSource!;
          Timer(const Duration(milliseconds: 120), () {
            if (_playbackSource != sourceAtInterrupt) {
              // Bu sirada gorusme bitmis/yeniden baslamis olabilir -
              // artik gecerli olmayan bir source'a dokunma.
              return;
            }
            try {
              _voiceDebugLog("resetBufferStream() cagriliyor (ertelenmis)");
              SoLoud.instance.resetBufferStream(sourceAtInterrupt);
              _voiceDebugLog("resetBufferStream() tamamlandi");
            } catch (e) {
              debugPrint("resetBufferStream hatasi: $e");
              _voiceDebugLog("resetBufferStream HATASI: $e");
            }
          });
        }
        // resetBufferStream() calinmamis kuyrugu ve pozisyonu sifirladi -
        // bizim tur-suresi sayacimizi da esitliyoruz.
        _bufferedDurationMs = 0;
        _scheduleUnmuteWhenPlaybackCatchesUp();
        state = state.copyWith(
          status: VoiceCallStatus.listening,
          liveAssistantText: "",
        );
      } else if (type == "partial_transcript") {
        final role = data["role"] as String?;
        final text = (data["text"] as String?) ?? "";
        if (role == "user") {
          state = state.copyWith(liveUserText: text);
        } else if (role == "assistant") {
          state = state.copyWith(liveAssistantText: text);
        }
      } else if (type == "turn_complete") {
        _voiceDebugLog("turn_complete alindi (chunk #$_audioChunkCounter)");
        _awaitingFirstChunkOfTurn = true;
        final userText = (data["user_text"] as String?)?.trim();
        final assistantText = (data["assistant_text"] as String?)?.trim();

        final chatNotifier = ref.read(chatProvider.notifier);
        if (userText != null && userText.isNotEmpty) {
          chatNotifier.addUserMessage(userText);
          // Sesli komut sozlugu (su an: kamera ac/kapa). Konusmayi
          // engellemez - soz balona dustu, Aura da yanit verecek; sadece
          // istemci tarafi bir aksiyon EKLER.
          _maybeHandleVoiceCommand(userText);
        }
        if (assistantText != null && assistantText.isNotEmpty) {
          chatNotifier.addAssistantMessage(assistantText);
        }

        // Ayni source gorusme boyunca yasamaya devam ediyor - bir sonraki
        // turun sesi de dogrudan addAudioDataStream ile ayni akisa eklenir.
        _scheduleUnmuteWhenPlaybackCatchesUp();
        state = state.copyWith(
          status: VoiceCallStatus.listening,
          liveUserText: "",
          liveAssistantText: "",
        );
      }
    } catch (_) {
      // sesle ilgisi olmayan/parse edilemeyen kontrol mesaji - yoksay
    }
  }

  /// ESKI YONTEM (artik sadece handle yokken / getPosition basarisiz
  /// olunca YEDEK olarak kullaniliyor): sabit 500ms bekleyip mikrofonu
  /// acar. Gercek kalan ses suresini bilmedigi icin (bkz.
  /// _scheduleUnmuteWhenPlaybackCatchesUp) YANLIS pozitif/negatif
  /// verebilir - o yuzden artik ana yol degil, sadece guvenlik agi.
  void _scheduleUnmute() {
    _unmuteTimer?.cancel();
    _unmuteTimer = Timer(const Duration(milliseconds: 500), () {
      _muteMic = false;
    });
  }

  /// Mikrofonu, Aura'nin sesi hoparlorden GERCEKTEN bitene kadar acmaz.
  ///
  /// KOK SEBEP (2026-08-24, kullanici raporu: bir "user" baloncugunda
  /// Aura'nin bir onceki cumlesi harfiyen tekrar ediyordu): turn_complete
  /// sadece "Gemini tum sesi URETTI" demek, "hoparlorden CALINDI" degil.
  /// Ag + SoLoud tamponu veriyi gercek zamanin ONUNDE alabiliyor - yani
  /// turn_complete geldiginde hala saniyelerce calinmamis ses kuyrukta
  /// olabilir. Sabit bir gecikme (eski _scheduleUnmute) bunu bilemez.
  ///
  /// Bunun yerine, bu tur icin EKLENEN toplam ses suresini (_bufferedDurationMs,
  /// 24kHz/mono/s16le PCM byte sayisindan hesaplaniyor) SoLoud'un GERCEK
  /// calma pozisyonuyla (getPosition, BufferingType.preserved icin
  /// gecerli konum bilgisi verir) karsilastirip, ikisi esitlenene (kuyruk
  /// fiilen tukenene) kadar kisa araliklarla tekrar tekrar kontrol eder.
  /// Donanim/OS ses mikser gecikmesi icin kucuk bir ek pay birakilir.
  /// getPosition basarisiz olursa ya da handle yoksa, sonsuza kadar
  /// mikrofonu kapali birakmamak icin eski sabit-sureli yonteme duser.
  void _scheduleUnmuteWhenPlaybackCatchesUp() {
    _unmuteTimer?.cancel();
    _unmuteCheckTimer?.cancel();

    final handle = _playbackHandle;
    if (handle == null) {
      _voiceDebugLog("unmute-check: handle yok, eski sabit sureye donuluyor");
      _scheduleUnmute();
      return;
    }

    final deadline = DateTime.now().add(const Duration(seconds: 15));

    void check() {
      int remainingMs;
      try {
        final positionMs = SoLoud.instance.getPosition(handle).inMilliseconds;
        remainingMs = _bufferedDurationMs - positionMs;
      } catch (e) {
        _voiceDebugLog(
          "unmute-check getPosition HATASI, mikrofon aciliyor: $e",
        );
        _muteMic = false;
        return;
      }

      if (remainingMs <= 150 || DateTime.now().isAfter(deadline)) {
        // BULUNDU (2026-09-02, kullanici raporu: "bazen kendi sesini
        // dinleyip cevap veriyor" + Windows teshis logu: mikrofon
        // turn_complete'ten sadece ~150-380ms sonra aciliyordu):
        // getPosition() SoLoud'un cozme imlecini biliyor ama OS'in ses
        // cikis tamponunu + hoparlor gecikmesini GORMUYOR. Donanim AEC'i
        // OLAN platformlarda bu sorun degil (mikrofon zaten Aura konusurken
        // de acik, native yanki iptali hallediyor). AEC'siz platformlarda
        // (Windows) ise "kuyruk tukendi" dedigimiz anda Aura'nin son
        // kelimeleri hala hoparlorden cikiyor olabilir - mikrofonu o an
        // acinca kendi sesi sizip Gemini'ye "yeni kullanici sesi" gidiyor,
        // Aura kendi cumlesine cevap veriyor. Cozum: bu platformlarda
        // kuyruk-tukendi kontrolu gectikten SONRA da mikrofonu hemen acma,
        // OS/hoparlor tamponu bosalsin diye biraz daha bekle.
        if (!_hasNativeEchoCancellation) {
          _voiceDebugLog(
            "unmute-check: kuyruk tukendi (kalan=${remainingMs}ms) - "
            "non-AEC platform, OS ses tamponu icin +500ms bekleniyor",
          );
          _unmuteTimer?.cancel();
          _unmuteTimer = Timer(const Duration(milliseconds: 500), () {
            _voiceDebugLog(
              "unmute-check: ek gecikme doldu - mikrofon aciliyor",
            );
            _muteMic = false;
          });
          return;
        }
        _voiceDebugLog(
          "unmute-check: kuyruk tukendi (kalan=${remainingMs}ms) - "
          "mikrofon aciliyor",
        );
        _muteMic = false;
        return;
      }

      // BULUNDU (2026-08-24, log kaniti: bu dongu 15sn tavana kadar HICBIR
      // SEY yapmadan bekleyip "sure doldu" diye zorla acmisti - o turun
      // geri kalaninda ses hic gelmemisti): kalan sure > 0 oldugu halde
      // motor sessizce PAUSED'a dusup pozisyonu HIC ILERLETMIYOR olabilir
      // (onBuffering tetiklenmeden, tur ortasinda). Eskiden bu dongu SADECE
      // pozisyonu izleyip pasif bekliyordu - artik her kontrolde PAUSED
      // durumunu da denetleyip gerekirse AKTIF olarak devam ettiriyor.
      try {
        if (SoLoud.instance.getPause(handle)) {
          _voiceDebugLog(
            "unmute-check: handle PAUSED bulundu (kalan=${remainingMs}ms) "
            "- setPause(false) cagriliyor",
          );
          SoLoud.instance.setPause(handle, false);
        }
      } catch (e) {
        _voiceDebugLog("unmute-check getPause/setPause HATASI: $e");
      }

      _unmuteCheckTimer = Timer(
        Duration(milliseconds: remainingMs.clamp(50, 400)),
        check,
      );
    }

    // Aura'nin sesinin hoparlorden fiziksel olarak CIKMASI icin (donanim/
    // OS mixer gecikmesi) ilk kontrolden once kucuk bir pay birakiyoruz.
    _unmuteCheckTimer = Timer(const Duration(milliseconds: 150), check);
  }

  /// Baglanti kullanicinin KENDI istegi disinda koptuysa (Gemini
  /// konjesyonu, gecici ag sorunu vb.) kullaniciyi elle "tekrar dene"
  /// tusuna basmaya zorlamadan birkac kez otomatik yeniden baglanmayi
  /// dener. Gercekten baglanamiyor olma ihtimaline karsi (backend
  /// cokmus vb.) bir ust sinirdan sonra kullaniciya hata gosterilir.
  void _handleUnexpectedDisconnect() {
    if (state.status == VoiceCallStatus.idle ||
        _reconnecting ||
        _limitReached ||
        _intentionalClose) {
      // idle: kullanici endCall() ile kendisi kapatti - normal, bir sey
      // yapma. _reconnecting: onError+onDone ayni kopma icin iki kez
      // tetiklenmis olabilir - ikinci tetiklemeyi yoksay. _limitReached:
      // sunucu gunluk limit yuzunden kapatti - otomatik yeniden
      // baglanmak ayni reddi tekrar tetikler, anlamsiz. _intentionalClose:
      // KRITIK - endCall()/retry() KENDI _channel.sink.close() cagrisi
      // WS'nin onDone'unu tetikliyor, ama state HENUZ idle'a donmemis
      // oluyor (cleanup bitmeden degismiyor) - bu bayrak olmadan bu,
      // "beklenmedik kopma" saniIip IKINCI, cakisan bir _cleanup()
      // baslatiyordu (iki es zamanli cleanup ayni native SoLoud motoruna
      // dokununca kilitlenip TUM UYGULAMAYI donduruyordu - teshis
      // loguyla kanitlandi).
      return;
    }
    if (_autoRetryCount >= _maxAutoRetries) {
      state = state.copyWith(status: VoiceCallStatus.error);
      return;
    }
    _autoRetryCount++;
    _reconnecting = true;
    state = state.copyWith(status: VoiceCallStatus.connecting);
    unawaited(_reconnectAfterDelay());
  }

  Future<void> _reconnectAfterDelay() async {
    await _cleanup();
    await Future.delayed(const Duration(seconds: 1));
    _reconnecting = false;
    // Bekleme sirasinda kullanici endCall() ile gorusmeyi kendisi
    // bitirmis olabilir (state idle'a donmustur) - bu durumda yeniden
    // baglanmayi YENIDEN DIRILTME, sessizce vazgec.
    if (state.status == VoiceCallStatus.idle) {
      return;
    }
    await _connect();
  }

  /// Sunucunun "reconnect_needed" (GoAway/uzun gorusme tazeleme) sinyali
  /// sonrasi cagrilir. _reconnectAfterDelay'den FARKLI: bir hata/kopma
  /// degil, Gemini Live'in kendi oturum omrunun dogal bir parcasi - bu
  /// yuzden _autoRetryCount'u artirmiyor, gecikme beklemeden hemen
  /// yeniden baglaniyor (_pendingResumptionHandle zaten set edilmis
  /// olmali, _connect() bunu WS URL'ine ekleyip tuketecek).
  Future<void> _reconnectForSessionRefresh() async {
    _intentionalClose = true;
    await _cleanup();
    _intentionalClose = false;
    if (state.status == VoiceCallStatus.idle) {
      // Kullanici bu sirada endCall() ile gorusmeyi kendisi bitirmis
      // olabilir - yeniden canlandirmiyoruz. KOD INCELEMESI BULGUSU:
      // _pendingResumptionHandle burada temizlenmezse, dakikalar sonra
      // kullanici TAMAMEN YENI/ILGISIZ bir gorusme baslattiginda bu eski
      // (belki artik geçersiz) handle o yeni gorusmeye sessizce
      // tasinabiliyordu.
      _pendingResumptionHandle = null;
      return;
    }
    state = state.copyWith(status: VoiceCallStatus.connecting);
    await _connect();
  }

  /// Hata sonrasi kullaniciyi ekrandan cikmaya zorlamadan tekrar
  /// baglanmayi dener.
  Future<void> retry() async {
    _autoRetryCount = 0;
    _limitReached = false;
    _intentionalClose = true;
    await _cleanup();
    _intentionalClose = false;
    state = state.copyWith(status: VoiceCallStatus.connecting);
    await _connect();
  }

  Future<void> endCall() async {
    _voiceDebugLog("===== endCall() cagrildi =====");
    _intentionalClose = true;
    await _cleanup();
    _intentionalClose = false;
    // Kullanici gorusmeyi bilerek bitiriyor - bu ana kadar birikmis
    // (henuz tuketilmemis) bir devam-etme tokeni varsa, bir sonraki
    // TAMAMEN YENI gorusmeye sizmasin diye burada da temizliyoruz.
    _pendingResumptionHandle = null;
    _voiceDebugLog("endCall() - _cleanup() tamamlandi");
    state = const VoiceCallState();
  }

  Future<void> _cleanup() async {
    _unmuteTimer?.cancel();
    _unmuteTimer = null;
    _unmuteCheckTimer?.cancel();
    _unmuteCheckTimer = null;
    _muteMic = false;
    _bufferedDurationMs = 0;
    await _stopVideoCapture();
    // BULUNDU (kod incelemesi 2026-09-03): _desktopHiddenAt SADECE resumed'da
    // temizleniyordu. Gorusme arka plandayken biterse (limit_reached/
    // idle_timeout -> _cleanup, ama state artik "error" -> resumed guard'i
    // erken donuyor) bayat kaliyordu; sonraki gorusmede siradan bir odak
    // donusu (masaustunde resumed HER odak kazaniminda tetikleniyor) bu eski
    // zaman damgasiyla "cok uzun askidaydik" deyip gereksiz reconnect ediyordu.
    _desktopHiddenAt = null;

    _voiceDebugLog("_micSubscription.cancel() cagriliyor");
    await _micSubscription?.cancel();
    _micSubscription = null;
    _voiceDebugLog("_micSubscription.cancel() tamamlandi");
    ref.read(micLevelProvider.notifier).update(0.0);
    try {
      _voiceDebugLog("_recorder.stop() cagriliyor");
      await _recorder.stop();
      _voiceDebugLog("_recorder.stop() tamamlandi");
    } catch (e) {
      _voiceDebugLog("_recorder.stop() HATASI: $e");
    }
    try {
      _voiceDebugLog("_channel.sink.close() cagriliyor");
      await _channel?.sink.close();
      _voiceDebugLog("_channel.sink.close() tamamlandi");
    } catch (e) {
      _voiceDebugLog("_channel.sink.close() HATASI: $e");
    }
    _channel = null;
    _voiceDebugLog("WakelockPlus.disable() cagriliyor");
    await WakelockPlus.disable();
    _voiceDebugLog("WakelockPlus.disable() tamamlandi");

    // KRITIK BULUNAN 3. BUG (teshis loguyla kanitlandi, ayni desenin
    // ucuncu tekrari): setDataIsEnded()'i kaldirdiktan sonra bu sefer
    // deinit() TEK BASINA (yine hicbir re-entrancy olmadan) kilitlendi.
    // Artik net: play()/disposeSource()/setDataIsEnded()/deinit() - bu
    // motoru "durdurmaya/temizlemeye" calisan HER senkron native cagri,
    // motor o an bu source'u AKTIF calarken/mixlerken kilitlenme riski
    // tasiyor (kullanici konusma SIRASINDA kapatma tusuna basiyor).
    //
    // FIX: artik HICBIR durdurma/temizleme cagrisi yapmiyoruz. SoLoud
    // motoru bir kez baslatildiktan sonra UYGULAMA SURESI BOYUNCA acik
    // kaliyor (deinit() bir daha hic cagrilmiyor), eski source'u da
    // sadece referanstan dusuruyoruz (dispose etmeden). Bir sonraki
    // startCall() zaten `if (!isInitialized) init()` ile bunu atlayip
    // sadece taze bir setBufferStream()+play() olusturuyor - bu ikisi
    // TUM testlerde hic kilitlenmedi (sadece "durdurma" cagrilari
    // kilitleniyordu). Odun: her arama, bir onceki aramanin kucuk ses
    // arabellegini bellekte birakiyor (kucuk bir sizinti) - donmaya
    // kiyasla acik ara daha iyi, uygulama kapaninca isletim sistemi
    // zaten hepsini geri aliyor.
    _playbackSource = null;
    _playbackHandle = null;
    _resumingPlayback = false;
    _awaitingFirstChunkOfTurn = true;
  }
}

final voiceCallProvider = NotifierProvider<VoiceCallNotifier, VoiceCallState>(
  VoiceCallNotifier.new,
);
