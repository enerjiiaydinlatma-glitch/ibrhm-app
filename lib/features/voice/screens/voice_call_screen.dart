import "dart:async";
import "dart:convert";
import "dart:typed_data";

import "package:flutter/material.dart";
import "package:flutter_soloud/flutter_soloud.dart";
import "package:google_fonts/google_fonts.dart";
import "package:record/record.dart";
import "package:wakelock_plus/wakelock_plus.dart";
import "package:web_socket_channel/web_socket_channel.dart";

/// Aura ile gercek zamanli, tam serbest (interrupt edilebilir) sesli
/// gorusme. Mikrofon surekli acik akar (VAD/interrupt tespiti sunucu
/// tarafinda - Gemini Live), gelen ses gercek zamanli calinir.
class VoiceCallScreen extends StatefulWidget {
  final String token;
  const VoiceCallScreen({super.key, required this.token});

  @override
  State<VoiceCallScreen> createState() => _VoiceCallScreenState();
}

enum _CallState { connecting, listening, auraSpeaking, error, ended }

class _VoiceCallScreenState extends State<VoiceCallScreen> {
  static const _wsBase = "wss://aura-backend-production-bc9c.up.railway.app";
  static const _bgColor = Color(0xFF0A0A1A);
  static const _indigoColor = Color(0xFF6C63FF);

  final AudioRecorder _recorder = AudioRecorder();
  WebSocketChannel? _channel;
  StreamSubscription<Uint8List>? _micSubscription;
  AudioSource? _playbackSource;

  _CallState _state = _CallState.connecting;
  bool _soloudReady = false;

  @override
  void initState() {
    super.initState();
    WakelockPlus.enable();
    _startCall();
  }

  Future<void> _startCall() async {
    final hasMicPermission = await _recorder.hasPermission();
    if (!hasMicPermission) {
      setState(() => _state = _CallState.error);
      return;
    }

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
        bufferingTimeNeeds: 0,
      );
      await SoLoud.instance.play(_playbackSource!);
    } catch (e) {
      debugPrint("SoLoud baslatma hatasi: $e");
      setState(() => _state = _CallState.error);
      return;
    }

    final uri = Uri.parse("$_wsBase/api/voice?token=${widget.token}");

    try {
      _channel = WebSocketChannel.connect(uri);
      _channel!.stream.listen(
        _handleServerMessage,
        onError: (e) {
          debugPrint("Sesli baglanti hatasi: $e");
          if (mounted) setState(() => _state = _CallState.error);
        },
        onDone: () {
          if (mounted && _state != _CallState.ended) {
            setState(() => _state = _CallState.error);
          }
        },
      );
    } catch (e) {
      debugPrint("WebSocket baglanti hatasi: $e");
      setState(() => _state = _CallState.error);
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

      var chunkCount = 0;
      _micSubscription = micStream.listen((chunk) {
        chunkCount++;
        if (chunkCount % 20 == 0) {
          debugPrint("DEBUG mikrofon: $chunkCount chunk gonderildi, son boyut=${chunk.length}");
        }
        _channel?.sink.add(chunk);
      });
    } catch (e) {
      debugPrint("Mikrofon akis hatasi: $e");
      setState(() => _state = _CallState.error);
      return;
    }

    if (mounted) setState(() => _state = _CallState.listening);
  }

  void _handleServerMessage(dynamic message) {
    if (message is List<int>) {
      debugPrint("DEBUG sunucudan ses: ${message.length} byte, playbackSource=${_playbackSource != null}");
      if (_playbackSource != null) {
        try {
          SoLoud.instance.addAudioDataStream(
            _playbackSource!,
            Uint8List.fromList(message),
          );
        } catch (e) {
          debugPrint("DEBUG addAudioDataStream HATASI: $e");
        }
      }
      if (mounted && _state != _CallState.auraSpeaking) {
        setState(() => _state = _CallState.auraSpeaking);
      }
      return;
    }

    debugPrint("DEBUG sunucudan mesaj (tip: ${message.runtimeType}): $message");

    try {
      final data = jsonDecode(message as String) as Map<String, dynamic>;
      final type = data["type"];

      if (type == "interrupted") {
        if (_playbackSource != null) {
          SoLoud.instance.resetBufferStream(_playbackSource!);
        }
        if (mounted) setState(() => _state = _CallState.listening);
      } else if (type == "turn_complete") {
        if (mounted) setState(() => _state = _CallState.listening);
      }
    } catch (_) {
      // sesle ilgisi olmayan/parse edilemeyen kontrol mesaji - yoksay
    }
  }

  Future<void> _endCall() async {
    setState(() => _state = _CallState.ended);

    await WakelockPlus.disable();
    await _micSubscription?.cancel();
    await _recorder.stop();
    await _channel?.sink.close();

    if (_soloudReady && _playbackSource != null) {
      try {
        await SoLoud.instance.disposeSource(_playbackSource!);
      } catch (_) {}
    }

    if (mounted) Navigator.of(context).pop();
  }

  @override
  void dispose() {
    WakelockPlus.disable();
    _micSubscription?.cancel();
    _recorder.dispose();
    _channel?.sink.close();
    super.dispose();
  }

  String get _statusText {
    switch (_state) {
      case _CallState.connecting:
        return "Bağlanıyor...";
      case _CallState.listening:
        return "Dinliyorum";
      case _CallState.auraSpeaking:
        return "Aura konuşuyor";
      case _CallState.error:
        return "Bağlantı sorunu, tekrar dener misin?";
      case _CallState.ended:
        return "Görüşme sona erdi";
    }
  }

  @override
  Widget build(BuildContext context) {
    final isSpeaking = _state == _CallState.auraSpeaking;

    return Scaffold(
      backgroundColor: _bgColor,
      body: SafeArea(
        child: Column(
          children: [
            const Spacer(flex: 2),
            TweenAnimationBuilder<double>(
              tween: Tween(begin: 0.9, end: isSpeaking ? 1.15 : 1.0),
              duration: const Duration(milliseconds: 500),
              curve: Curves.easeInOut,
              builder: (_, scale, __) => Transform.scale(
                scale: scale,
                child: Container(
                  width: 160,
                  height: 160,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: RadialGradient(
                      colors: [
                        _indigoColor.withOpacity(isSpeaking ? 0.9 : 0.5),
                        _indigoColor.withOpacity(0.05),
                      ],
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 32),
            Text(
              "Aura",
              style: GoogleFonts.poppins(
                color: Colors.white,
                fontSize: 24,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              _statusText,
              style: GoogleFonts.poppins(color: Colors.white54, fontSize: 14),
            ),
            const Spacer(flex: 3),
            GestureDetector(
              onTap: _endCall,
              child: Container(
                width: 64,
                height: 64,
                decoration: const BoxDecoration(
                  color: Colors.redAccent,
                  shape: BoxShape.circle,
                ),
                child: const Icon(Icons.call_end, color: Colors.white, size: 28),
              ),
            ),
            const SizedBox(height: 48),
          ],
        ),
      ),
    );
  }
}
