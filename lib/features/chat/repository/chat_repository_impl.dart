import 'package:dio/dio.dart';

import '../models/message.dart';
import 'chat_repository.dart';

class ChatRepositoryImpl implements ChatRepository {
  final Dio _dio;
  final String baseUrl;
  final String token;

  ChatRepositoryImpl({
    Dio? dio,
    this.baseUrl = 'https://aura-backend-production-bc9c.up.railway.app',
    required this.token,
  }) : _dio = dio ??
            Dio(
              // Kod sagligi taramasinda bulundu: timeout YOKTU - sunucu
              // takilirsa istek sonsuza dek asili kalir, "yaziyor..."
              // gostergesi hic kapanmaz, kullaniciya hicbir hata gorunmez.
              BaseOptions(
                connectTimeout: const Duration(seconds: 15),
                // AI cevabi (Gemini + Groq fallback + fotograf analizi)
                // uzun surebiliyor, bu yuzden receiveTimeout comert tutuldu.
                receiveTimeout: const Duration(seconds: 60),
              ),
            );

  Options get _authOptions => Options(
        headers: {
          'Authorization': 'Bearer $token',
        },
      );

  @override
  Future<Message> sendMessage(String text) async {
    try {
      final response = await _dio.post(
        '$baseUrl/api/chat',
        data: {
          'message': text,
        },
        options: _authOptions,
      );

      final data = response.data as Map<String, dynamic>;
      final replyText = data['reply']?.toString() ?? '';

      return Message(
        id: DateTime.now().millisecondsSinceEpoch.toString(),
        text: replyText,
        isUser: false,
      );
    } on DioException catch (e) {
      if (e.response?.statusCode == 401) {
        throw Exception('Oturum süreniz sona ermiş.');
      }

      throw Exception('Aura\'ya şu an ulaşılamıyor.');
    }
  }

  @override
  Future<Message> analyzeImage(String base64Image, {String mimeType = "image/jpeg"}) async {
    try {
      final response = await _dio.post(
        '$baseUrl/api/analyze',
        data: {
          'image_base64': base64Image,
          'mime_type': mimeType,
        },
        options: _authOptions,
      );

      final data = response.data as Map<String, dynamic>;
      final analysis = data['analysis']?.toString() ?? '';

      return Message(
        id: DateTime.now().millisecondsSinceEpoch.toString(),
        text: analysis,
        isUser: false,
      );
    } on DioException catch (_) {
      throw Exception('Fotoğraf analiz edilemedi.');
    }
  }

  @override
  Future<String?> getGreeting() async {
    try {
      final response = await _dio.get(
        '$baseUrl/api/chat/greeting',
        options: _authOptions,
      );

      final data = response.data as Map<String, dynamic>;
      final reply = data['reply'];

      return reply?.toString();
    } on DioException catch (_) {
      return null;
    }
  }

  @override
  Future<List<Message>> getHistory() async {
    try {
      final response = await _dio.get(
        '$baseUrl/api/history',
        options: _authOptions,
      );

      final data = response.data as List;

      return data.asMap().entries.map((entry) {
        final index = entry.key;
        final item = entry.value as Map<String, dynamic>;

        return Message(
          id: 'history_$index',
          text: item['text']?.toString() ?? '',
          isUser: item['role'] == 'user',
        );
      }).toList();
    } on DioException catch (_) {
      throw Exception('Geçmiş yüklenemedi.');
    }
  }
}