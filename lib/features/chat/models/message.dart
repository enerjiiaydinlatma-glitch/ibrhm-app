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

  /// Sadece Aura'nin (asistan) yanitlarinda dolu - backend'in bu turde
  /// tespit ettigi ruh hali ("mutlu"/"uzgun"/"yorgun"/"stresli"/"enerjik"
  /// ya da tespit yoksa null). chat_notifier bunu ChatState.currentMood'a
  /// tasiyip AuraHale (sohbet arka planindaki ton-reaktif hale) bunu okur.
  final String? mood;

  Message({
    required this.id,
    required this.text,
    required this.isUser,
    this.imageBytes,
    this.fileName,
    this.animateIn = false,
    this.mood,
  });
}
