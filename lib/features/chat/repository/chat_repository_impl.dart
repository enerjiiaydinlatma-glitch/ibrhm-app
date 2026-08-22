import 'dart:convert';

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
  }) : _dio = dio ?? Dio();

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
  Stream<String> sendMessageStream(String text) async* {
    try {
      final response = await _dio.post<ResponseBody>(
        '$baseUrl/api/chat/stream',
        data: {
          'message': text,
        },
        options: Options(
          responseType: ResponseType.stream,
          headers: {
            'Authorization': 'Bearer $token',
          },
        ),
      );

      final stream = response.data!.stream;

      await for (final chunk in stream) {
        yield utf8.decode(
          chunk,
          allowMalformed: true,
        );
      }
    } on DioException catch (_) {
      throw Exception('Aura\'ya şu an ulaşılamıyor.');
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