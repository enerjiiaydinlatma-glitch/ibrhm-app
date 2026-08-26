import 'package:flutter/material.dart';

/// Kullanici istegi (2026-08-26): "en samimi en guzel etkili cekici"
/// bir arayuz - "herkeste olan zaten bizde var, onemli olan kimsede
/// olmayani bulmak." Rakiplerin (Replika/Character.AI/ChatGPT) hepsi
/// SABIT bir koyu tema kullaniyor. Aura'nin sohbet arka plani artik
/// kullanicinin GERCEK saatine gore surekli degisen, canli bir gokyuzu -
/// gun boyunca safaktan geceye akan bir gradyan. Mesaj balonlari zaten
/// buzlu-cam (BackdropFilter) oldugu icin gokyuzu altlarindan hafifce
/// gorunuyor.
///
/// 5 renk-duragi olan 4 "anahtar kare" (gece/safak/gunduz/aksam) arasinda
/// dogrusal interpolasyon yapiyoruz - saatin ondalik kismi (12:30 -> 12.5)
/// iki en yakin anahtar kare arasindaki gecis oranini belirliyor. Sonuc:
/// uygulamayi her actiginda GUNUN O ANKI saatine ozel, essiz bir gokyuzu.
class SkyGradient {
  SkyGradient._();

  // Saat -> 5 renk-duragi. Sirasiyla: gece yarisi, safak, gunduz zirvesi,
  // aksam, tekrar gece yarisi (24 = 0, dongu kapaniyor).
  static const List<double> _hours = [0, 6, 13, 19, 24];

  static const List<List<Color>> _stops = [
    // Gece (00:00)
    [Color(0xFF05050F), Color(0xFF0C0E24), Color(0xFF141A35), Color(0xFF1C2440), Color(0xFF232C48)],
    // Safak (06:00)
    [Color(0xFF2B2140), Color(0xFF6B4A6B), Color(0xFFD97A6B), Color(0xFFF0B86E), Color(0xFFF6D9A0)],
    // Gunduz zirvesi (13:00)
    [Color(0xFF3F7DC0), Color(0xFF4F8FD1), Color(0xFF7FB8E8), Color(0xFFBFE0F2), Color(0xFFEAF5E6)],
    // Aksam (19:00)
    [Color(0xFF1B1140), Color(0xFF4A2360), Color(0xFF9C3F5E), Color(0xFFE0703F), Color(0xFFF4A25A)],
    // Gece yarisi (24:00 == 00:00 ile ayni, dongu kapaniyor)
    [Color(0xFF05050F), Color(0xFF0C0E24), Color(0xFF141A35), Color(0xFF1C2440), Color(0xFF232C48)],
  ];

  /// [dimFactor] 0.0-1.0 arasi - yagmurlu/kapali havada gokyuzunu
  /// soluklastirmak icin (0 = degisiklik yok, 1 = tam gri/soluk).
  /// Su an her zaman 0 gonderiliyor - hava durumu verisi client'a henuz
  /// tasinmadi, bu bilerek kapsam disi birakildi bir sonraki adim.
  static LinearGradient forTime(DateTime time, {double dimFactor = 0.0}) {
    final hourFraction = time.hour + time.minute / 60.0;

    var i = 0;
    while (i < _hours.length - 2 && hourFraction >= _hours[i + 1]) {
      i++;
    }

    final rangeStart = _hours[i];
    final rangeEnd = _hours[i + 1];
    final t = ((hourFraction - rangeStart) / (rangeEnd - rangeStart)).clamp(0.0, 1.0);

    final colors = List<Color>.generate(5, (stopIndex) {
      final blended = Color.lerp(_stops[i][stopIndex], _stops[i + 1][stopIndex], t)!;
      if (dimFactor <= 0) return blended;
      // Yagmurlu hava: doygunlugu dusur, griye yaklastir.
      final gray = (blended.r * 0.299 + blended.g * 0.587 + blended.b * 0.114);
      return Color.lerp(blended, Color.from(alpha: 1, red: gray, green: gray, blue: gray), dimFactor)!;
    });

    return LinearGradient(
      colors: colors,
      begin: Alignment.topCenter,
      end: Alignment.bottomCenter,
    );
  }
}

/// Gokyuzunu belirli araliklarla (5 dakikada bir) yeniden hesaplayip
/// yumusak bir gecisle gosteren wrapper widget.
class SkyBackground extends StatefulWidget {
  final Widget child;
  const SkyBackground({super.key, required this.child});

  @override
  State<SkyBackground> createState() => _SkyBackgroundState();
}

class _SkyBackgroundState extends State<SkyBackground> {
  @override
  void initState() {
    super.initState();
    _scheduleNextTick();
  }

  void _scheduleNextTick() {
    Future.delayed(const Duration(minutes: 5), () {
      if (!mounted) return;
      setState(() {});
      _scheduleNextTick();
    });
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedContainer(
      duration: const Duration(seconds: 2),
      curve: Curves.easeInOut,
      decoration: BoxDecoration(gradient: SkyGradient.forTime(DateTime.now())),
      child: widget.child,
    );
  }
}
