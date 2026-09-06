import '../models/message.dart';

abstract class ChatRepository {
  Future<Message> sendMessage(String text);
  Future<List<Message>> getHistory();
  Future<String?> getGreeting();

  /// Fotograf VEYA PDF gonderip Aura'nin incelemesini alir.
  /// [mimeType] "image/jpeg" | "image/png" | "image/webp" | "application/pdf".
  /// [question] opsiyonel - PDF ile birlikte sorulan soru.
  Future<Message> analyzeFile(
    String base64Data, {
    required String mimeType,
    String question,
    String fileName,
  });

  /// Bir Aura yanitina kullanici geri bildirimi (👍/👎). Ates-et-unut:
  /// hata olsa bile sohbeti etkilemez. [rating] "up" | "down".
  Future<void> sendFeedback({
    required String rating,
    required String auraReply,
    String userMessage,
    String note,
  });
}
