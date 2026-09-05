import "package:flutter/material.dart";

/// "Aura efekti" (2026-09-05, kullanicinin kendi Aura'ya sordugu soru
/// sonucu netlesen yon): Snapchat/Instagram tarzi yuz-filtresi YERINE,
/// sohbetin duygusal tonuna gore yavasca renk degistiren yumusak bir
/// hale - Aura'nin kendi ifadesiyle "varligini bagirmadan hissettiren,
/// sakin bir nefes gibi" bir imza. SkyBackground'in (gunun saatine gore
/// degisen gokyuzu) YERINE degil, onun USTUNE, dusuk opasiteli ek bir
/// katman - ikisi birlikte "zaman + duygu" iki boyutunu tasiyor.
///
/// Veri kaynagi: backend'de ZATEN var olan, ama once hic disariya
/// donmeyen detect_mood() (main.py) - her /api/chat yanitinda "mutlu"/
/// "uzgun"/"yorgun"/"stresli"/"enerjik" ya da tespit yoksa null olarak
/// geliyor (bkz. ChatState.currentMood, chat_notifier.sendMessage).
class AuraHale extends StatefulWidget {
  final String? mood;

  const AuraHale({super.key, this.mood});

  @override
  State<AuraHale> createState() => _AuraHaleState();
}

class _AuraHaleState extends State<AuraHale>
    with SingleTickerProviderStateMixin {
  // Notr/hic tespit yokken Aura'nin kendi imza rengi (indigo) - marka
  // kimligiyle tutarli, uygulamanin her yerinde kullanilan ayni ton.
  static const Color _neutral = Color(0xFF6C63FF);

  static const Map<String, Color> _moodColors = {
    "mutlu": Color(0xFFFFC978), // sicak altin
    "enerjik": Color(0xFFFF8C69), // canli mercan
    "uzgun": Color(0xFF5A6FA8), // yumusak, soluk mavi
    "yorgun": Color(0xFF8478A0), // sakin lavanta-gri
    "stresli": Color(0xFFC97B63), // ilik terracotta (alarm degil)
  };

  Color get _targetColor => _moodColors[widget.mood] ?? _neutral;

  // "Nefes alma" nabzi - surekli, cok yavas ve hafif bir opaklik/olcek
  // salinimi. Kasitli olarak UZUN (6sn) ve DAR bir aralikta (0.85-1.0) -
  // goz ucuyla farkedilecek kadar canli ama asla "yanip sonme" gibi
  // dikkat dagitici degil.
  late final AnimationController _breath = AnimationController(
    vsync: this,
    duration: const Duration(seconds: 6),
  )..repeat(reverse: true);

  @override
  void dispose() {
    _breath.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: AnimatedBuilder(
        animation: _breath,
        builder: (context, _) {
          final breathT = Curves.easeInOut.transform(_breath.value);
          final scale = 1.0 + breathT * 0.06;
          final baseOpacity = 0.16 + breathT * 0.06;
          return Align(
            alignment: Alignment.bottomCenter,
            child: Transform.scale(
              scale: scale,
              alignment: Alignment.bottomCenter,
              // Renk gecisi: AnimatedContainer'in kendi (implicit) BoxDecoration
              // interpolasyonu - mood degistiginde ~3.5sn'de yumusakca
              // yeni tona kayar, ani bir sicrama olmadan.
              child: TweenAnimationBuilder<Color?>(
                // BILEREK sadece 'end' verildi, 'begin' YOK: TweenAnimationBuilder
                // ilk olusumda dogrudan bu renkle baslar, ama widget.mood
                // degisip _targetColor degistiginde (didUpdateWidget) ONCEKI
                // GOSTERILEN renkten YENI end'e otomatik gecis yapar - iki
                // ayri "hedef" degeri elle vermeye gerek yok/YANLIS olurdu
                // (baslangicta 'begin: _targetColor' ile ayni veriliyorsa
                // asla gercek bir interpolasyon olmazdi).
                tween: ColorTween(end: _targetColor),
                duration: const Duration(milliseconds: 3500),
                curve: Curves.easeInOut,
                builder: (context, color, _) {
                  final c = color ?? _targetColor;
                  return Container(
                    width: 520,
                    height: 420,
                    decoration: BoxDecoration(
                      gradient: RadialGradient(
                        center: Alignment.center,
                        radius: 0.75,
                        colors: [
                          c.withValues(alpha: baseOpacity),
                          c.withValues(alpha: 0.0),
                        ],
                      ),
                    ),
                  );
                },
              ),
            ),
          );
        },
      ),
    );
  }
}
