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

  /// Kombin onerisi - kiyafet fotografi gonderip (varsa hava durumuna gore)
  /// Aura'nin ne giyecegine dair onerisini alir. [mimeType] sadece resim
  /// ("image/jpeg" | "image/png" | "image/webp"), PDF desteklenmez.
  Future<Message> suggestOutfit(
    String base64Data, {
    required String mimeType,
    String question,
  });
}