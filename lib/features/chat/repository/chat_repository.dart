import '../models/message.dart';

abstract class ChatRepository {
  Future<Message> sendMessage(List<Message> history);
}
