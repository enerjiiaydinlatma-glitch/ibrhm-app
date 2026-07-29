import 'package:dio/dio.dart';
import '../models/message.dart';
import 'chat_repository.dart';

class ChatRepositoryImpl implements ChatRepository {
  final Dio _dio;
  final String baseUrl;

  ChatRepositoryImpl({
    Dio? dio,
    this.baseUrl = 'http://127.0.0.1:8000',
  }) : _dio = dio ?? Dio();

  @override
  Future<Message> sendMessage(List<Message> history) async {
    try {
      final response = await _dio.post(
        '$baseUrl/api/chat',
        data: {
          'history': history
              .map((m) => {
                    'role': m.isUser ? 'user' : 'assistant',
                    'text': m.text,
                  })
              .toList(),
        },
      );

      final replyText = response.data['reply'] ?? '';

      return Message(
        id: DateTime.now().millisecondsSinceEpoch.toString(),
        text: replyText.toString(),
        isUser: false,
      );
    } on DioException catch (e) {
      throw Exception('Aura API hatasi: ${e.message}');
    }
  }
}
