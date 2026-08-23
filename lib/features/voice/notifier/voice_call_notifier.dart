import "dart:async";
import "dart:convert";

import "package:flutter/foundation.dart";
import "package:flutter_riverpod/flutter_riverpod.dart";
import "package:flutter_soloud/flutter_soloud.dart";
import "package:record/record.dart";
import "package:wakelock_plus/wakelock_plus.dart";
import "package:web_socket_channel/web_socket_channel.dart";

import "../../chat/notifier/chat_notifier.dart";
import "../models/voice_call_state.dart";

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

  @override
  VoiceCallState build() {
    ref.onDispose(() {
      _micSubscription?.cancel();
      _channel?.sink.close();
      WakelockPlus.disable();
    });
    return const VoiceCallState();
  }

  Future<void> startCall(String token) async {
    _token = token;
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
        await SoLoud.instance.init();
      }
      _soloudReady = true;

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
      await SoLoud.instance.play(_playbackSource!);
    } catch (e) {
      debugPrint("SoLoud baslatma hatasi: $e");
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
          state = state.copyWith(status: VoiceCallStatus.error);
        },
        onDone: () {
          if (state.status != VoiceCallStatus.idle) {
            state = state.copyWith(status: VoiceCallStatus.error);
          }
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
    if (message is List<int>) {
      if (_playbackSource != null) {
        try {
          SoLoud.instance.addAudioDataStream(
            _playbackSource!,
            Uint8List.fromList(message),
          );
        } catch (e) {
          debugPrint("addAudioDataStream hatasi: $e");
        }
      }
      if (state.status != VoiceCallStatus.auraSpeaking) {
        state = state.copyWith(status: VoiceCallStatus.auraSpeaking);
      }
      return;
    }

    try {
      final data = jsonDecode(message as String) as Map<String, dynamic>;
      final type = data["type"];

      if (type == "interrupted") {
        if (_playbackSource != null) {
          try {
            SoLoud.instance.resetBufferStream(_playbackSource!);
          } catch (e) {
            debugPrint("resetBufferStream hatasi: $e");
          }
        }
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
        final userText = (data["user_text"] as String?)?.trim();
        final assistantText = (data["assistant_text"] as String?)?.trim();

        final chatNotifier = ref.read(chatProvider.notifier);
        if (userText != null && userText.isNotEmpty) {
          chatNotifier.addUserMessage(userText);
        }
        if (assistantText != null && assistantText.isNotEmpty) {
          chatNotifier.addAssistantMessage(assistantText);
        }

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

  /// Hata sonrasi kullaniciyi ekrandan cikmaya zorlamadan tekrar
  /// baglanmayi dener.
  Future<void> retry() async {
    await _cleanup();
    state = state.copyWith(status: VoiceCallStatus.connecting);
    await _connect();
  }

  Future<void> endCall() async {
    await _cleanup();
    state = const VoiceCallState();
  }

  Future<void> _cleanup() async {
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

    if (_playbackSource != null && _soloudReady) {
      try {
        await SoLoud.instance.disposeSource(_playbackSource!);
      } catch (_) {}
      _playbackSource = null;
    }
  }
}

final voiceCallProvider =
    NotifierProvider<VoiceCallNotifier, VoiceCallState>(VoiceCallNotifier.new);
