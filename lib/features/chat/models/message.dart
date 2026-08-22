import "dart:typed_data";

class Message {
  final String id;
  final String text;
  final bool isUser;
  final Uint8List? imageBytes;

  Message({
    required this.id,
    required this.text,
    required this.isUser,
    this.imageBytes,
  });
}
