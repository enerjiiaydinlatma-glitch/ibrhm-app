import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Mikrofon ses seviyesi (0.0-1.0), sesli gorusme sirasinda her PCM
/// parcasinda guncelleniyor (bkz. voice_call_notifier.dart).
///
/// KASITLI OLARAK voiceCallProvider'dan AYRI bir provider - o state
/// saniyede ~10 kez guncellenirse, chat_screen.dart'taki
/// ref.watch(voiceCallProvider) TUM mesaj listesini saniyede 10 kez
/// yeniden cizerdi (performans sorunu). Bu provider'i SADECE gorsel
/// dalga widget'i izliyor, geri kalan hicbir sey etkilenmiyor.
class MicLevelNotifier extends Notifier<double> {
  @override
  double build() => 0.0;

  void update(double value) => state = value;
}

final micLevelProvider = NotifierProvider<MicLevelNotifier, double>(MicLevelNotifier.new);
