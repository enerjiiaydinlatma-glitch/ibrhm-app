import "package:flutter/material.dart";
import "package:flutter_tts/flutter_tts.dart";

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final tts = FlutterTts();

  List<dynamic> voices = [];
  for (int i = 0; i < 10; i++) {
    voices = await tts.getVoices as List<dynamic>;
    if (voices.isNotEmpty) break;
    await Future.delayed(const Duration(milliseconds: 500));
  }

  print("=== MEVCUT SESLER (deneme sayisi ile) ===");
  print("Toplam ses sayisi: ${voices.length}");
  for (var v in voices) {
    print(v);
  }

  runApp(const MaterialApp(home: Scaffold(body: Center(child: Text("Konsolu kontrol et")))));
}
