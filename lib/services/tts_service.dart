import 'package:audioplayers/audioplayers.dart';
import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_tts/flutter_tts.dart';

/// BULUNDU (kod incelemesi, 2026-08-26 - sesli gorusme yedek modu
/// eklenirken): ElevenLabs+yerel-TTS-yedegi mantigi SADECE chat_screen.dart
/// icinde ozel bir metottu (_speakWithElevenLabs). Sesli gorusme yedek
/// modunun (VoiceCallBar) da AYNI sese ihtiyaci vardi - ya kopyala-
/// yapistir yapip iki yerde ayri ayri bakim gerektirecekti ya da (burada
/// yapilan) tek, paylasilan bir servise cikarilacakti. chat_screen.dart
/// artik bu servise DELEGE ediyor, davranis degismedi.
class TtsService {
  TtsService._();
  static final TtsService instance = TtsService._();

  static const String backendUrl = "https://aura-backend-production-bc9c.up.railway.app";

  final Dio _dio = Dio(
    BaseOptions(
      connectTimeout: const Duration(seconds: 15),
      receiveTimeout: const Duration(seconds: 30),
    ),
  );
  final AudioPlayer _audioPlayer = AudioPlayer();
  final FlutterTts _localTts = FlutterTts();
  bool _localTtsReady = false;

  Future<void> _ensureLocalTtsReady() async {
    if (_localTtsReady) return;
    try {
      await _localTts.setLanguage("tr-TR");
      await _localTts.setSpeechRate(0.48);
      await _localTts.setPitch(1.0);
      _localTtsReady = true;
    } catch (e) {
      debugPrint("Yerel TTS baslatma hatasi: $e");
    }
  }

  String _cleanForSpeech(String text) {
    final emojiPattern = RegExp(
      r"[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{2190}-\u{21FF}\u{2B00}-\u{2BFF}\u{FE0F}]",
      unicode: true,
    );
    return text
        .replaceAll(emojiPattern, "")
        .replaceAll(RegExp(r"\*\*"), "")
        .replaceAll(RegExp(r"#+\s*"), "")
        .trim();
  }

  /// Once ElevenLabs'i (daha dogal/karakterli ses) dener - kota bitmisse
  /// ya da baska bir sebeple basarisiz olursa, platformun kendi
  /// (ucretsiz, sinirsiz) sesine SESSIZCE duser.
  Future<void> speak(String text, {required String token, String voice = "female"}) async {
    final cleanText = _cleanForSpeech(text);
    if (cleanText.isEmpty) return;
    await _ensureLocalTtsReady();
    try {
      final response = await _dio.post<List<int>>(
        "$backendUrl/api/tts",
        data: {"text": cleanText, "voice": voice},
        options: Options(
          responseType: ResponseType.bytes,
          headers: {"Authorization": "Bearer $token"},
        ),
      );
      if (response.data != null) {
        await _audioPlayer.stop();
        await _audioPlayer.play(
          BytesSource(Uint8List.fromList(response.data!)),
        );
      }
    } catch (e) {
      debugPrint("ElevenLabs TTS hatasi (yerel sese dusuluyor): $e");
      if (_localTtsReady) {
        try {
          await _localTts.stop();
          await _localTts.speak(cleanText);
        } catch (e2) {
          debugPrint("Yerel TTS hatasi: $e2");
        }
      }
    }
  }
}
