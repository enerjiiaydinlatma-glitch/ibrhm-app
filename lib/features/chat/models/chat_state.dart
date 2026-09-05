import 'message.dart';

class ChatState {
  final List<Message> messages;
  final bool isLoading;
  final String? errorMessage;

  /// "Aura efekti" - sohbetin en son tespit edilen ruh hali ("mutlu"/
  /// "uzgun"/"yorgun"/"stresli"/"enerjik" ya da hic tespit yoksa null).
  /// BILEREK diger alanlar gibi her copyWith'te SIFIRLANMIYOR - backend
  /// notr bir mesajda (yeni bir mood tespit etmeden) da yanit doner,
  /// o durumda hale aniden sonmek yerine bir onceki tonunu KORUR (daha
  /// organik/"nefes gibi" hissettirir). Sadece GERCEKTEN yeni bir mood
  /// tespit edildiginde degisir - bkz. chat_notifier.sendMessage.
  final String? currentMood;

  ChatState({
    this.messages = const [],
    this.isLoading = false,
    this.errorMessage,
    this.currentMood,
  });

  ChatState copyWith({
    List<Message>? messages,
    bool? isLoading,
    String? errorMessage,
    String? currentMood,
  }) {
    return ChatState(
      messages: messages ?? this.messages,
      isLoading: isLoading ?? this.isLoading,
      errorMessage: errorMessage,
      currentMood: currentMood ?? this.currentMood,
    );
  }
}
