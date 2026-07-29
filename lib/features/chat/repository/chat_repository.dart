import '../models/message.dart';

abstract class ChatRepository {
  Future<Message> sendMessage(String text);
}
