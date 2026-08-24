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
  bool _soloudReady = false;
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
      _soloudReady = true;

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
      await SoLoud.instance.play(_playbackSource!);
      _voiceDebugLog("play() tamamlandi");
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
    if (state.status == VoiceCallStatus.idle || _reconnecting || _limitReached) {
      // idle: kullanici endCall() ile kendisi kapatti - normal, bir sey
      // yapma. _reconnecting: onError+onDone ayni kopma icin iki kez
      // tetiklenmis olabilir - ikinci tetiklemeyi yoksay. _limitReached:
      // sunucu gunluk limit yuzunden kapatti - otomatik yeniden
      // baglanmak ayni reddi tekrar tetikler, anlamsiz.
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
    await _cleanup();
    state = state.copyWith(status: VoiceCallStatus.connecting);
    await _connect();
  }

  Future<void> endCall() async {
    await _cleanup();
    state = const VoiceCallState();
  }

  Future<void> _cleanup() async {
    _unmuteTimer?.cancel();
    _unmuteTimer = null;
    _muteMic = false;

    await _micSubscription?.cancel();
    _micSubscription = null;
    try {
      await _recorder.stop();
    } catch (_) {}
    try {
      await _channel?.sink.close();
    } catch (_) {}
    _channel = null;
    await WakelockPlus.disable();

    // Sadece kaynagi (source) degil, TUM SoLoud motorunu kapatiyoruz.
    // Motoru acik birakip sadece source'u dispose etmek, ayni uygulama
    // oturumunda IKINCI aramada native ses motorunun bozuk bir durumda
    // kalip donmasina (tum pencerenin kilitlenmesine) yol aciyordu. Bir
    // sonraki startCall() zaten `if (!isInitialized) init()` ile motoru
    // sifirdan baslatiyor - kucuk bir gecikme pahasina saglamlik kazaniyoruz.
    //
    // Resmi ornekteki gibi: kapanistan once akisin bittigini isaretle
    // (setDataIsEnded, tamamen senkron/hafif bir cagri - disposeSource
    // gibi kaynak yok etmiyor). AYRICA disposeSource() cagirmiyoruz -
    // deinit() zaten TUM kaynaklari (disposeAllSound() ile, motoru
    // kapatirken) tek seferde serbest birakiyor.
    if (_playbackSource != null) {
      try {
        SoLoud.instance.setDataIsEnded(_playbackSource!);
      } catch (_) {}
    }
    _playbackSource = null;
    if (_soloudReady) {
      try {
        SoLoud.instance.deinit();
      } catch (e) {
        debugPrint("SoLoud deinit hatasi: $e");
      }
      _soloudReady = false;
    }
  }
}

final voiceCallProvider =
    NotifierProvider<VoiceCallNotifier, VoiceCallState>(VoiceCallNotifier.new);
