import "dart:math" as math;

import "package:flutter/material.dart";

/// "Aura efekti" - bir fotograf ya da PDF cipi mesaj akisinda ILK
/// belirdiginde bir kez oynayan imza acilis animasyonu (varyant C:
/// parilti akisi + indigo nabiz). ~900ms, sonra child normal haliyle kalir.
///
/// Yalnizca [play] true iken oynar (Message.animateIn) - gecmis yeniden
/// yuklendiginde tekrar tetiklenmesin diye.
class AuraImageReveal extends StatefulWidget {
  final Widget child;
  final bool play;
  final BorderRadius borderRadius;

  const AuraImageReveal({
    super.key,
    required this.child,
    this.play = true,
    this.borderRadius = const BorderRadius.all(Radius.circular(14)),
  });

  @override
  State<AuraImageReveal> createState() => _AuraImageRevealState();
}

class _AuraImageRevealState extends State<AuraImageReveal>
    with SingleTickerProviderStateMixin {
  static const _indigo = Color(0xFF6C63FF);
  static const _indigoLight = Color(0xFF9C8FFF);

  late final AnimationController _c = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 900),
  );

  @override
  void initState() {
    super.initState();
    if (widget.play) {
      _c.forward();
    } else {
      _c.value = 1.0;
    }
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _c,
      builder: (context, child) {
        final t = _c.value;
        if (t >= 1.0) return child!;

        // 1) child belirme: opaklik + hafif olcek
        final appear = Curves.easeOut.transform(t);
        // 2) parilti supurmesi (0.05 - 0.72 araligi)
        final shineT = ((t - 0.05) / 0.67).clamp(0.0, 1.0);
        final shineX = -1.4 + shineT * 2.8; // -1.4 -> 1.4
        final shineOpacity = math.sin(shineT * math.pi); // 0 -> 1 -> 0
        // 3) indigo nabiz: hizli parla, yavas son
        final glow = math.sin(math.min(t * 1.15, 1.0) * math.pi);

        return Stack(
          children: [
            Opacity(
              opacity: appear,
              child: Transform.scale(
                scale: 0.96 + 0.04 * appear,
                child: child,
              ),
            ),
            // parilti akisi
            if (shineOpacity > 0.01)
              Positioned.fill(
                child: IgnorePointer(
                  child: ClipRRect(
                    borderRadius: widget.borderRadius,
                    child: Opacity(
                      opacity: shineOpacity * 0.9,
                      child: DecoratedBox(
                        decoration: BoxDecoration(
                          gradient: LinearGradient(
                            begin: Alignment(shineX - 0.6, -1),
                            end: Alignment(shineX + 0.6, 1),
                            colors: const [
                              Color(0x00FFFFFF),
                              _indigoLight,
                              Color(0xCCFFFFFF),
                              Color(0x00FFFFFF),
                            ],
                            stops: const [0.35, 0.48, 0.52, 0.65],
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            // indigo nabiz (dis parilti)
            if (glow > 0.01)
              Positioned.fill(
                child: IgnorePointer(
                  child: Container(
                    decoration: BoxDecoration(
                      borderRadius: widget.borderRadius,
                      border: Border.all(
                        color: _indigo.withValues(alpha: glow * 0.65),
                        width: 1.5,
                      ),
                      boxShadow: [
                        BoxShadow(
                          color: _indigo.withValues(alpha: glow * 0.55),
                          blurRadius: 22 * glow,
                          spreadRadius: 1.5 * glow,
                        ),
                      ],
                    ),
                  ),
                ),
              ),
          ],
        );
      },
      child: ClipRRect(borderRadius: widget.borderRadius, child: widget.child),
    );
  }
}
