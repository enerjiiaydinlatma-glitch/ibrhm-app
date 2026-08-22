import '../models/message.dart';

abstract class ChatRepository {
  Future<Message> sendMessage(String text);
  Stream<String> sendMessageStream(String text);
  Future<List<Message>> getHistory();
  Future<String?> getGreeting();
  Future<Message> analyzeImage(String base64Image, {String mimeType});
}