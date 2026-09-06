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

  /// Kullanicinin bu Aura yanitina verdigi geri bildirim (2026-09-06):
  /// "up" | "down" | null (henuz verilmemis). Sadece yerel UI durumu -
  /// gonderim backend'e ates-et-unut yapilir (bkz. chat_notifier
  /// sendReplyFeedback).
  final String? feedback;

  Message({
    required this.id,
    required this.text,
    required this.isUser,
    this.imageBytes,
    this.fileName,
    this.animateIn = false,
    this.mood,
    this.feedback,
  });

  Message copyWith({String? text, String? mood, String? feedback}) {
    return Message(
      id: id,
      text: text ?? this.text,
      isUser: isUser,
      imageBytes: imageBytes,
      fileName: fileName,
      animateIn: animateIn,
      mood: mood ?? this.mood,
      feedback: feedback ?? this.feedback,
    );
  }
}
