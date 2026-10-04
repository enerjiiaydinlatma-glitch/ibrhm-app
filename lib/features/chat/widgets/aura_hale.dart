import "dart:math" as math;

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
///
/// 2026-10-04 (bkz. docs/MOOD_IYILESTIRME_PLANI.md):
/// - KARISIK DUYGU: backend artik `moods` listesi de donuyor; birden fazla
///   duygu varsa hale TEK ortalama renk yerine IKI TONU YAN YANA gosterir
///   (ortalama renk camurlasir, iki duygu da okunmaz).
/// - COSKU HALI: yalnizca mutlu/enerjik (ya da ikisi) varken hale daha
///   zengin (sicak altin-mercan-pembe, daha parlak). Duygu YENI yakalandiginda
///   birkac saniyelik bir acilis (nefes + ince isik parcaciklari) oynar, sonra
///   SAKIN, SABIT parlak bir hale oturur. Surekli hareket yok; kullaniciyi
///   geri cagirmak icin degil, yalnizca kendi mutluluguna CEVAP olarak
///   cikar. "Hareket azaltma" aciksa acilis hic oynamaz.
class AuraHale extends StatefulWidget {
  final String? mood;

  /// Tespit edilen tum duygular (mesajdaki sirayla). Bos/null ise [mood]
  /// kullanilir (eski backend uyumu).
  final List<String>? moods;

  const AuraHale({super.key, this.mood, this.moods});

  @override
  State<AuraHale> createState() => _AuraHaleState();
}

/// Bir ruh hali listesinin gorsel karsiligi. Saf veri - test edilebilir.
@visibleForTesting
class AuraHaleLook {
  const AuraHaleLook({
    required this.a,
    required this.b,
    required this.spread,
    required this.joy,
  });

  /// Birinci / ikinci hale rengi.
  final Color a;
  final Color b;

  /// 0 = tek merkezli hale; 1 = iki ton yan yana tam ayrik (harman).
  final double spread;

  /// 0..1 - coskulu (mutlu/enerjik) zenginlestirme miktari.
  final double joy;

  static const Color neutral = Color(0xFF6C63FF);

  static const Map<String, Color> moodColors = {
    "mutlu": Color(0xFFFFC978), // sicak altin
    "enerjik": Color(0xFFFF8C69), // canli mercan
    "uzgun": Color(0xFF5A6FA8), // yumusak, soluk mavi
    "yorgun": Color(0xFF8478A0), // sakin lavanta-gri
    "stresli": Color(0xFFC97B63), // ilik terracotta (alarm degil)
  };

  static const Set<String> joyMoods = {"mutlu", "enerjik"};

  /// Tum duygular coskulu aileden mi (mutlu/enerjik)? Bos liste -> false.
  static bool isJoy(List<String> moods) {
    final known = _known(moods);
    return known.isNotEmpty && known.every(joyMoods.contains);
  }

  static List<String> _known(List<String> moods) {
    final out = <String>[];
    for (final m in moods) {
      if (moodColors.containsKey(m) && !out.contains(m)) out.add(m);
    }
    return out;
  }

  /// [moods] -> gorunum. Bilinmeyen etiketler yok sayilir; en fazla ilk
  /// IKI farkli duygu harmanlanir.
  static AuraHaleLook forMoods(List<String> moods) {
    final known = _known(moods);
    if (known.isEmpty) {
      return const AuraHaleLook(a: neutral, b: neutral, spread: 0, joy: 0);
    }
    if (known.length == 1) {
      final only = known.first;
      final color = moodColors[only]!;
      if (joyMoods.contains(only)) {
        // Tek coskulu duygu: kendi tonu agirlikli, digeri hafif eslik eder.
        final other = only == "mutlu"
            ? moodColors["enerjik"]!
            : moodColors["mutlu"]!;
        return AuraHaleLook(a: color, b: other, spread: 0.35, joy: 1);
      }
      return AuraHaleLook(a: color, b: color, spread: 0, joy: 0);
    }
    final first = known[0];
    final second = known[1];
    return AuraHaleLook(
      a: moodColors[first]!,
      b: moodColors[second]!,
      spread: 1,
      joy: isJoy(known) ? 1 : 0,
    );
  }

  static AuraHaleLook lerp(AuraHaleLook x, AuraHaleLook y, double t) {
    return AuraHaleLook(
      a: Color.lerp(x.a, y.a, t)!,
      b: Color.lerp(x.b, y.b, t)!,
      spread: x.spread + (y.spread - x.spread) * t,
      joy: x.joy + (y.joy - x.joy) * t,
    );
  }
}

class _AuraHaleState extends State<AuraHale> with TickerProviderStateMixin {
  // Cosku acilisi arasinda en az bu kadar sure gecmeli - her mutlu
  // mesajda parilti oynamasin (dikkat cekme/aliskanlik araci olmasin).
  static const Duration _burstCooldown = Duration(minutes: 2);

  static const Color _pink = Color(0xFFFF9EC4); // cosku hali ilik pembe

  // "Nefes alma" nabzi - surekli, cok yavas ve hafif bir opaklik/olcek
  // salinimi. Kasitli olarak UZUN (6sn) ve DAR bir aralikta (0.85-1.0) -
  // goz ucuyla farkedilecek kadar canli ama asla "yanip sonme" gibi
  // dikkat dagitici degil.
  late final AnimationController _breath = AnimationController(
    vsync: this,
    duration: const Duration(seconds: 6),
  )..repeat(reverse: true);

  // Renk/harman/cosku gecisi: mood degistiginde ~3.5sn'de yumusakca yeni
  // gorunume kayar, ani bir sicrama olmadan. value=1: baslangicta gecis yok.
  late final AnimationController _morph = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 3500),
    value: 1.0,
  );

  // Cosku acilisi: tek seferlik, 5sn.
  late final AnimationController _burst = AnimationController(
    vsync: this,
    duration: const Duration(seconds: 5),
  );

  late AuraHaleLook _from;
  late AuraHaleLook _to;
  DateTime? _lastBurst;

  static List<String> _effective(String? mood, List<String>? moods) {
    if (moods != null && moods.isNotEmpty) return moods;
    return mood != null ? [mood] : const [];
  }

  @override
  void initState() {
    super.initState();
    // Ilk olusumda dogrudan hedef gorunumle baslar (animasyon ve acilis YOK).
    _to = _from = AuraHaleLook.forMoods(_effective(widget.mood, widget.moods));
  }

  @override
  void didUpdateWidget(AuraHale oldWidget) {
    super.didUpdateWidget(oldWidget);
    final oldMoods = _effective(oldWidget.mood, oldWidget.moods);
    final newMoods = _effective(widget.mood, widget.moods);
    if (_sameMoods(oldMoods, newMoods)) return;

    // Gecis o anki GOSTERILEN gorunumden baslar (yarim kalan gecis dahil).
    final t = Curves.easeInOut.transform(_morph.value);
    _from = AuraHaleLook.lerp(_from, _to, t);
    _to = AuraHaleLook.forMoods(newMoods);
    _morph.forward(from: 0);

    if (AuraHaleLook.isJoy(newMoods) && !AuraHaleLook.isJoy(oldMoods)) {
      _maybeBurst();
    }
  }

  static bool _sameMoods(List<String> a, List<String> b) {
    if (a.length != b.length) return false;
    for (var i = 0; i < a.length; i++) {
      if (a[i] != b[i]) return false;
    }
    return true;
  }

  void _maybeBurst() {
    if (MediaQuery.maybeOf(context)?.disableAnimations ?? false) return;
    final now = DateTime.now();
    final last = _lastBurst;
    if (last != null && now.difference(last) < _burstCooldown) return;
    _lastBurst = now;
    _burst.forward(from: 0);
  }

  @override
  void dispose() {
    _breath.dispose();
    _morph.dispose();
    _burst.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: AnimatedBuilder(
        animation: Listenable.merge([_breath, _morph, _burst]),
        builder: (context, _) {
          final breathT = Curves.easeInOut.transform(_breath.value);
          final look = AuraHaleLook.lerp(
            _from,
            _to,
            Curves.easeInOut.transform(_morph.value),
          );
          // 0 -> 1 -> 0 egrisi: acilis sirasinda en yuksek, bitince 0.
          final burstT = _burst.isAnimating
              ? math.sin(math.pi * _burst.value)
              : 0.0;

          final scale = 1.0 + breathT * 0.06 + burstT * 0.08;
          // Harman iki ayri tona bolundugu icin biraz daha parlak: yoksa iki
          // soluk ton gri-camura yakin gorunur.
          final baseOpacity =
              ((0.16 + breathT * 0.06) *
                          (1 + 0.45 * look.joy + 0.30 * look.spread) +
                      burstT * 0.08)
                  .clamp(0.0, 0.45)
                  .toDouble();
          // Harmanda iki isik birbirinden UZAKLASIR ve KUCULUR: yakin/buyuk
          // olunca iki ton ortada karisip gri-camura doner, ikisi de okunmaz.
          final aAlpha = baseOpacity;
          final bAlpha = baseOpacity * look.spread;
          final pinkAlpha = baseOpacity * 0.55 * look.joy;
          final radius = 0.75 - 0.20 * look.spread;

          return Align(
            alignment: Alignment.bottomCenter,
            child: Transform.scale(
              scale: scale,
              alignment: Alignment.bottomCenter,
              child: SizedBox(
                width: 520,
                height: 420,
                child: Stack(
                  fit: StackFit.expand,
                  children: [
                    _glow(
                      look.a,
                      aAlpha,
                      Alignment(-0.55 * look.spread, 0.05 * look.spread),
                      radius,
                    ),
                    _glow(
                      look.b,
                      bAlpha,
                      Alignment(0.55 * look.spread, -0.10 * look.spread),
                      radius,
                    ),
                    _glow(_pink, pinkAlpha, const Alignment(0.0, -0.25), 0.75),
                    if (_burst.isAnimating)
                      CustomPaint(
                        painter: _SparklePainter(
                          progress: _burst.value,
                          colors: [look.a, look.b, _pink],
                        ),
                      ),
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _glow(Color color, double alpha, Alignment center, double radius) {
    return DecoratedBox(
      decoration: BoxDecoration(
        gradient: RadialGradient(
          center: center,
          radius: radius,
          colors: [
            color.withValues(alpha: alpha),
            color.withValues(alpha: 0.0),
          ],
        ),
      ),
    );
  }
}

/// Cosku acilisinda, hale alaninda yukari dogru YAVASCA suzulen birkac ince
/// isik parcacigi. Yalnizca acilis (5sn) boyunca cizilir; basta ve sonda
/// saydam, ortada en gorunur (sin egrisi).
class _SparklePainter extends CustomPainter {
  _SparklePainter({required this.progress, required this.colors});

  final double progress;
  final List<Color> colors;

  static final List<_Spark> _sparks = List.generate(14, (i) {
    final r = math.Random(i * 7919 + 13);
    return _Spark(
      x: r.nextDouble(),
      phase: r.nextDouble(),
      speed: 0.6 + r.nextDouble() * 0.6,
      radius: 1.4 + r.nextDouble() * 2.2,
      drift: r.nextDouble() * 2 * math.pi,
      colorIndex: i % 3,
    );
  });

  @override
  void paint(Canvas canvas, Size size) {
    final envelope = math.sin(math.pi * progress);
    if (envelope <= 0) return;
    final paint = Paint()
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 2);
    for (final s in _sparks) {
      final p = (progress * s.speed + s.phase) % 1.0;
      final dx =
          size.width * (0.1 + 0.8 * s.x) +
          math.sin(p * 2 * math.pi + s.drift) * 12;
      final dy = size.height * (0.95 - 0.7 * p);
      final alpha = (math.sin(math.pi * p) * envelope * 0.55).clamp(0.0, 0.55);
      paint.color = colors[s.colorIndex % colors.length].withValues(
        alpha: alpha,
      );
      canvas.drawCircle(Offset(dx, dy), s.radius, paint);
    }
  }

  @override
  bool shouldRepaint(_SparklePainter old) => old.progress != progress;
}

class _Spark {
  const _Spark({
    required this.x,
    required this.phase,
    required this.speed,
    required this.radius,
    required this.drift,
    required this.colorIndex,
  });

  final double x;
  final double phase;
  final double speed;
  final double radius;
  final double drift;
  final int colorIndex;
}
