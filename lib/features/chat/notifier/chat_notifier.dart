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

    final assistantId = _uuid.v4();
    final placeholder = Message(
      id: assistantId,
      text: '',
      isUser: false,
    );

    state = state.copyWith(
      messages: [...state.messages, userMessage, placeholder],
      isLoading: true,
      errorMessage: null,
    );

    final buffer = StringBuffer();

    try {
      await for (final chunk in repository.sendMessageStream(text)) {
        buffer.write(chunk);
        final updatedMessages = [...state.messages];
        final index = updatedMessages.indexWhere((m) => m.id == assistantId);
        if (index != -1) {
          updatedMessages[index] = Message(
            id: assistantId,
            text: buffer.toString(),
            isUser: false,
          );
          state = state.copyWith(messages: updatedMessages, isLoading: true);
        }
      }
      state = state.copyWith(isLoading: false);
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