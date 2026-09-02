import "dart:typed_data";

class Message {
  final String id;
  final String text;
  final bool isUser;
  final Uint8List? imageBytes;

  /// PDF/belge eklendiginde dosya adi (balonda belge cipi olarak gosterilir).
  /// imageBytes null + fileName dolu => belge mesaji.
  final String? fileName;

  /// Sadece YENI eklenen ekler icin true - "Aura efekti" (AuraImageReveal)
  /// acilis animasyonu yalnizca bunda oynar, gecmis yeniden yuklenince degil.
  final bool animateIn;

  Message({
    required this.id,
    required this.text,
    required this.isUser,
    this.imageBytes,
    this.fileName,
    this.animateIn = false,
  });
}
