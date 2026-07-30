import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';
import '../models/chat_state.dart';
import '../models/message.dart';
import '../repository/chat_repository.dart';
import '../repository/chat_repository_impl.dart';

final chatRepositoryProvider = Provider<ChatRepository>((ref) {
  return ChatRepositoryImpl();
});

class ChatNotifier extends Notifier<ChatState> {
  final _uuid = const Uuid();

  @override
  ChatState build() {
    Future.microtask(_loadHistory);
    return ChatState(isLoading: true);
  }

  Future<void> _loadHistory() async {
    final repository = ref.read(chatRepositoryProvider);
    try {
      final messages = await repository.getHistory();
      state = state.copyWith(
        messages: messages,
        isLoading: false,
      );
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: e.toString(),
      );
    }
  }

  Future<void> sendMessage(String text) async {
    if (text.trim().isEmpty) return;

    final repository = ref.read(chatRepositoryProvider);

    final userMessage = Message(
      id: _uuid.v4(),
      text: text,
      isUser: true,
    );

    state = state.copyWith(
      messages: [...state.messages, userMessage],
      isLoading: true,
      errorMessage: null,
    );

    try {
      final aiMessage = await repository.sendMessage(text);
      state = state.copyWith(
        messages: [...state.messages, aiMessage],
        isLoading: false,
      );
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: e.toString(),
      );
    }
  }
}

final chatNotifierProvider = NotifierProvider<ChatNotifier, ChatState>(() {
  return ChatNotifier();
});
