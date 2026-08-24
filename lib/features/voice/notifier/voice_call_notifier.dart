import "dart:async";
import "dart:convert";
import "dart:io";

import "package:flutter/foundation.dart";
import "package:flutter_riverpod/flutter_riverpod.dart";
import "package:flutter_soloud/flutter_soloud.dart";
import "package:record/record.dart";
import "package:wakelock_plus/wakelock_plus.dart";
import "package:web_socket_channel/web_socket_channel.dart";

import "../../chat/notifier/chat_notifier.dart";
import "../models/voice_call_state.dart";

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

/// Aura ile gercek zamanli, tam serbest (interrupt edilebilir) sesli
/// gorusme. Chat ekranindan hicbir zaman ayrilmaz - bir Notifier olarak
/// yasar, ChatScreen sadece kucuk bir durum cubugu (VoiceCallBar) render
/// eder. Konusulan sozler turn_complete ile birlikte donen transkript
/// uzerinden chatProvider'a (ayni mesaj listesine) ekleniyor - yazili ve
/// sesli mesajlar tek bir akista birlesiyor.
class VoiceCallNotifier extends Notifier<VoiceCallState> {
  static const _wsBase = "wss://aura-backend-production-bc9c.up.railway.app";

  final AudioRecorder _recorder = AudioRecorder();
  WebSocketChannel? _channel;
  StreamSubscription<Uint8List>? _micSubscription;
  AudioSource? _playbackSource;
  // play()'in dondurdugu "calma ornegi" - SoLoud dokumantasyonuna gore
  // bu handle, akis DURMUS ya da "bitmis" sayilirsa dogal olarak
  // GECERSIZ hale gelebiliyor (getIsValidVoiceHandle: "Returns false if
  // it's been stopped or if it finished playing") - biz BufferingType.
  // preserved kullandigimiz icin akisin asla "bitmemesini" bekliyorduk,
  // ama pratikte turlar arasindaki bosluklarda handle gecersiz hale
  // gelip yeni beslenen veri hic calinmiyor olabilir (kullanici raporu:
  // ilk tur sesli, sonrakiler sessiz - veri basariyla akiyor ama ses
  // duyulmuyor). Bu yuzden her ses parcasindan once handle'in hala
  // gecerli olup olmadigini kontrol edip, degilse play()'i TEKRAR
  // cagirip playback'i canlandiriyoruz.
  SoundHandle? _playbackHandle;
  bool _resumingPlayback = false;
  // PAUSED durumu icin en fazla 300ms'de bir kontrol/unpause denemesi
  // yapmak icin (throttle) - bkz. _handleServerMessage'daki aciklama.
  DateTime? _lastResumeCheckTime;
  String? _token;

  // Yanki koruma: donanim AEC'i olmadan (kulaksiz/hoparlorle kullanimda)
  // Aura'nin sesi mikrofona sizip Gemini'nin "kullanici konusuyor" sanip
  // kendi kendini kesmesine (ve bu hizli kesinti dongusunun SoLoud'u
  // kilitleyip tum uygulamayi dondurmesine) yol aciyordu. Aura konusurken
  // mikrofonu sunucuya GONDERMEYEREK bu dongude kesilir - konusma hala
  // dogal sirayla akar, sadece Aura'nin sozu bu sirada kesilemez.
  bool _muteMic = false;
  Timer? _unmuteTimer;
  int _audioChunkCounter = 0;

  // Beklenmedik baglanti kopmasi (Gemini konjesyonu, gecici ag sorunu vb.)
  // durumunda kullaniciyi elle "tekrar dene" tusuna basmaya zorlamadan
  // OTOMATIK olarak yeniden baglanmayi dener. Gercekten baglanamiyor
  // olma ihtimaline karsi (backend cokmus vb.) sonsuz donguye girmesin
  // diye bir ust sinir var - o noktada kullaniciya hata gosterilir.
  int _autoRetryCount = 0;
  static const int _maxAutoRetries = 3;
  bool _reconnecting = false;

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
    ref.onDispose(() {
      _unmuteTimer?.cancel();
      _micSubscription?.cancel();
      _channel?.sink.close();
      WakelockPlus.disable();
    });
    return const VoiceCallState();
  }

  Future<void> startCall(String token) async {
    _voiceDebugLog("===== startCall() =====");
    _audioChunkCounter = 0;
    _token = token;
    _autoRetryCount = 0;
    _limitReached = false;
    state = state.copyWith(status: VoiceCallStatus.connecting);
    await _connect();
  }

  Future<void> _connect() async {
    final hasMicPermission = await _recorder.hasPermission();
    if (!hasMicPermission) {
      state = state.copyWith(status: VoiceCallStatus.error);
      return;
    }

    await WakelockPlus.enable();

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
        // (0.3s) hem dusuk gecikme saglar hem bu erken-bitis sorununu onler.
        bufferingTimeNeeds: 0.3,
      );
      _voiceDebugLog("play() cagriliyor");
      _playbackHandle = await SoLoud.instance.play(_playbackSource!);
      _voiceDebugLog("play() tamamlandi (handle=$_playbackHandle)");
    } catch (e) {
      debugPrint("SoLoud baslatma hatasi: $e");
      _voiceDebugLog("baslatma HATASI: $e");
      state = state.copyWith(status: VoiceCallStatus.error);
      return;
    }

    final uri = Uri.parse("$_wsBase/api/voice?token=$_token");

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
      state = state.copyWith(status: VoiceCallStatus.error);
      return;
    }

    try {
      final micStream = await _recorder.startStream(
        const RecordConfig(
          encoder: AudioEncoder.pcm16bits,
          sampleRate: 16000,
          numChannels: 1,
        ),
      );

      _micSubscription = micStream.listen((chunk) {
        if (_muteMic) return;
        _channel?.sink.add(chunk);
      });
    } catch (e) {
      debugPrint("Mikrofon akis hatasi: $e");
      state = state.copyWith(status: VoiceCallStatus.error);
      return;
    }

    state = state.copyWith(status: VoiceCallStatus.listening);
  }

  void _handleServerMessage(dynamic message) {
    // Sunucudan gelen HERHANGI bir mesaj, baglantinin saglikli oldugunun
    // kaniti - otomatik yeniden baglanma sayacini sifirla ki uzun bir
    // gorusmede araya sikisan birkac ayri, gecici kopma toplam hakkı
    // tuketmesin.
    _autoRetryCount = 0;

    if (message is List<int>) {
      // Aura'nin sesi hoparlorden cikmaya baslayacak - yanki dongusune
      // girmemek icin mikrofonu hemen sustur (bkz. _muteMic aciklamasi).
      _unmuteTimer?.cancel();
      _muteMic = true;

      try {
        if (_playbackSource != null) {
          final handle = _playbackHandle;
          if (handle != null) {
            // TESHIS SONUCU 1: getIsValidVoiceHandle HER ZAMAN true
            // donuyordu (handle "gecersiz" hic olmuyor) - SoLoud
            // dokumantasyonu "valid"i "playing VEYA PAUSED" olarak
            // taniyor. Asil sorun handle'in GECERSIZ olmasi degil,
            // BufferingType.preserved'in "arabellek tukenince
            // duraklat, yeterli veri gelince otomatik devam et"
            // davranisinin (SADECE ilk play() cagrisinda dogal olarak
            // isliyor - turn 1 hep sorunsuzdu) turlar arasi boslukta
            // olusan PAUSED durumdan OTOMATIK cikmamasi.
            //
            // TESHIS SONUCU 2: setPause(false)'u HER parcada kosulsuz
            // cagirmak "kesik kesik ses"e yol acti - log kanitladi: 2.
            // turda HER TEK addAudioDataStream'den hemen sonra handle
            // yeniden PAUSED buluyorduk, yani zorla erken uyandirmak
            // arabellegin (bufferingTimeNeeds: 0.3s) hic birikmeden
            // surekli tukenip yeniden duraklamasina yol aciyordu -
            // dongusel bir kesinti.
            //
            // TESHIS SONUCU 3: "turn basina sadece BIR KEZ" denemesi de
            // yetersiz kaldi - bir sonraki testte 3. turda hic PAUSED
            // tespiti olmadi ama yine ses gelmedi, yani duraklama TUR
            // ICINDE de (sadece basinda degil) tekrar olusabiliyor.
            // Cozum: ne her parcada, ne sadece turn basinda - en fazla
            // 300ms'de BIR kontrol edilen (throttled) surekli bir kontrol.
            // Bu, dongusel kesintiyi onlerken (300ms'den sik cagrilamaz)
            // tur icinde herhangi bir noktada olusabilecek yeniden
            // duraklamayi da yakalar.
            final now = DateTime.now();
            final dueForCheck = _lastResumeCheckTime == null ||
                now.difference(_lastResumeCheckTime!) >
                    const Duration(milliseconds: 300);
            if (dueForCheck) {
              _lastResumeCheckTime = now;
              try {
                if (SoLoud.instance.getPause(handle)) {
                  _voiceDebugLog("handle PAUSED - setPause(false) cagriliyor");
                  SoLoud.instance.setPause(handle, false);
                }
              } catch (e) {
                _voiceDebugLog("getPause/setPause HATASI: $e");
              }
            }
          } else if (!_resumingPlayback) {
            // Handle hic yoksa (beklenmedik durum) play()'i tekrar
            // cagirip bir tane olusturuyoruz.
            _resumingPlayback = true;
            _voiceDebugLog("handle yok - play() cagriliyor");
            unawaited(
              SoLoud.instance.play(_playbackSource!).then((newHandle) {
                _playbackHandle = newHandle;
                _resumingPlayback = false;
                _voiceDebugLog("play() (resume) tamamlandi (handle=$newHandle)");
              }).catchError((e) {
                _resumingPlayback = false;
                _voiceDebugLog("play() (resume) HATASI: $e");
              }),
            );
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
      } else if (type == "interrupted") {
        _voiceDebugLog("interrupted alindi (chunk #$_audioChunkCounter)");
        // Aura'nin sozu kesildi - hala tamponda bekleyen (henuz calinmamis)
        // sesi temizlemek icin resetBufferStream() kullaniyoruz (resmi
        // ornekteki desen). Bu, disposeSource()'in aksine TAMAMEN SENKRON
        // ve kaynagi yok etmiyor, sadece pozisyonunu sifirliyor - ayni
        // source gorusme boyunca yasamaya devam ediyor.
        if (_playbackSource != null) {
          try {
            _voiceDebugLog("resetBufferStream() cagriliyor");
            SoLoud.instance.resetBufferStream(_playbackSource!);
            _voiceDebugLog("resetBufferStream() tamamlandi");
          } catch (e) {
            debugPrint("resetBufferStream hatasi: $e");
            _voiceDebugLog("resetBufferStream HATASI: $e");
          }
        }
        _scheduleUnmute();
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
        final userText = (data["user_text"] as String?)?.trim();
        final assistantText = (data["assistant_text"] as String?)?.trim();

        final chatNotifier = ref.read(chatProvider.notifier);
        if (userText != null && userText.isNotEmpty) {
          chatNotifier.addUserMessage(userText);
        }
        if (assistantText != null && assistantText.isNotEmpty) {
          chatNotifier.addAssistantMessage(assistantText);
        }

        // Ayni source gorusme boyunca yasamaya devam ediyor - bir sonraki
        // turun sesi de dogrudan addAudioDataStream ile ayni akisa eklenir.
        _scheduleUnmute();
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

  /// Aura'nin turu bittikten sonra mikrofonu HEMEN degil, kisa bir
  /// gecikmeyle acar - SoLoud tamponunda (bufferingTimeNeeds: 0.3s) hala
  /// calinmakta olan son ses kuyrugunun hoparlorden tamamen bitmesini
  /// bekleriz, yoksa o kuyruk da mikrofona sizip yeni bir yanki dongusu
  /// baslatabilir.
  void _scheduleUnmute() {
    _unmuteTimer?.cancel();
    _unmuteTimer = Timer(const Duration(milliseconds: 500), () {
      _muteMic = false;
    });
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
    _voiceDebugLog("endCall() - _cleanup() tamamlandi");
    state = const VoiceCallState();
  }

  Future<void> _cleanup() async {
    _unmuteTimer?.cancel();
    _unmuteTimer = null;
    _muteMic = false;

    _voiceDebugLog("_micSubscription.cancel() cagriliyor");
    await _micSubscription?.cancel();
    _micSubscription = null;
    _voiceDebugLog("_micSubscription.cancel() tamamlandi");
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
    _lastResumeCheckTime = null;
  }
}

final voiceCallProvider =
    NotifierProvider<VoiceCallNotifier, VoiceCallState>(VoiceCallNotifier.new);
