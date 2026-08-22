import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/chat_state.dart';
import '../models/message.dart';
import '../repository/chat_repository_impl.dart';

final chatProvider =
    NotifierProvider<ChatNotifier, ChatState>(ChatNotifier.new);

class ChatNotifier extends Notifier<ChatState> {
  String? _token;

  @override
  ChatState build() {
    return ChatState();
  }

  void setToken(String token) {
    _token = token;
  }

  ChatRepositoryImpl get _repository {
    final token = _token;

    if (token == null || token.isEmpty) {
      throw StateError('Aura oturum anahtarı bulunamadı.');
    }

    return ChatRepositoryImpl(token: token);
  }

  Future<void> loadHistory() async {
    try {
      final messages = await _repository.getHistory();

      state = state.copyWith(
        messages: messages,
        isLoading: false,
        errorMessage: null,
      );
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: 'Geçmiş yüklenemedi.',
      );
    }
  }

  /// Kullanicinin gecmisi bomsa Aura'nin ilk sozu kendisinin almasi
  /// icin cagrilir. Gecmis doluysa sessizce hicbir sey yapmaz.
  Future<void> fetchGreeting() async {
    if (state.messages.isNotEmpty) return;

    state = state.copyWith(isLoading: true, errorMessage: null);

    try {
      final greeting = await _repository.getGreeting();

      if (greeting != null && greeting.trim().isNotEmpty) {
        state = state.copyWith(
          messages: [
            ...state.messages,
            Message(
              id: DateTime.now().microsecondsSinceEpoch.toString(),
              text: greeting,
              isUser: false,
            ),
          ],
          isLoading: false,
          errorMessage: null,
        );
      } else {
        state = state.copyWith(isLoading: false);
      }
    } catch (_) {
      state = state.copyWith(isLoading: false);
    }
  }

  Future<void> sendMessage(String text) async {
    final cleanText = text.trim();

    if (cleanText.isEmpty) {
      return;
    }

    final userMessage = Message(
      id: DateTime.now().microsecondsSinceEpoch.toString(),
      text: cleanText,
      isUser: true,
    );

    state = state.copyWith(
      messages: [
        ...state.messages,
        userMessage,
      ],
      isLoading: true,
      errorMessage: null,
    );

    final assistantId =
        DateTime.now().microsecondsSinceEpoch.toString();

    final assistantMessage = Message(
      id: assistantId,
      text: '',
      isUser: false,
    );

    state = state.copyWith(
      messages: [
        ...state.messages,
        assistantMessage,
      ],
      isLoading: true,
      errorMessage: null,
    );

    try {
      final reply = await _repository.sendMessage(cleanText);

      final messages = state.messages;

      if (messages.isNotEmpty && !messages.last.isUser) {
        final updatedAssistant = Message(
          id: assistantId,
          text: reply.text,
          isUser: false,
        );

        state = state.copyWith(
          messages: [
            ...messages.sublist(0, messages.length - 1),
            updatedAssistant,
          ],
          isLoading: false,
          errorMessage: null,
        );
      } else {
        state = state.copyWith(
          messages: [
            ...messages,
            reply,
          ],
          isLoading: false,
          errorMessage: null,
        );
      }
    } catch (e) {
      final messages = state.messages;

      if (messages.isNotEmpty && !messages.last.isUser) {
        final failedAssistant = Message(
          id: assistantId,
          text: 'Aura şu an cevap veremiyor. Biraz sonra tekrar deneyelim.',
          isUser: false,
        );

        state = state.copyWith(
          messages: [
            ...messages.sublist(0, messages.length - 1),
            failedAssistant,
          ],
          isLoading: false,
          errorMessage: 'Aura bağlantısında bir sorun oluştu.',
        );
      } else {
        state = state.copyWith(
          isLoading: false,
          errorMessage: 'Aura bağlantısında bir sorun oluştu.',
        );
      }
    }
  }
  void addUserMessage(String text) {
    final cleanText = text.trim();

    if (cleanText.isEmpty) {
      return;
    }

    state = state.copyWith(
      messages: [
        ...state.messages,
        Message(
          id: DateTime.now().microsecondsSinceEpoch.toString(),
          text: cleanText,
          isUser: true,
        ),
      ],
      errorMessage: null,
    );
  }

  void addAssistantMessage(String text) {
    final cleanText = text.trim();

    if (cleanText.isEmpty) {
      return;
    }

    state = state.copyWith(
      messages: [
        ...state.messages,
        Message(
          id: DateTime.now().microsecondsSinceEpoch.toString(),
          text: cleanText,
          isUser: false,
        ),
      ],
      errorMessage: null,
    );
  }

  void clear() {
    state = ChatState();
  }
}
