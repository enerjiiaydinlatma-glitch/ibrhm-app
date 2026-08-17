import 'package:flutter_riverpod/flutter_riverpod.dart';

final chatNotifierProvider =
    StateNotifierProvider<ChatNotifier, List<String>>((ref) {
  return ChatNotifier();
});

class ChatNotifier extends StateNotifier<List<String>> {
  ChatNotifier() : super([]);

  void sendMessage(String message) {
    state = [...state, message];
  }

  void addResponse(String response) {
    state = [...state, response];
  }

  void clear() {
    state = [];
  }
}