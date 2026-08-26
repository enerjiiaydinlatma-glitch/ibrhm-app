import 'dart:math' as math;
import 'package:flutter/material.dart';

import '../models/memory_item.dart';

/// Kullanici istegi (2026-08-26): hafiza ekrani duz bir liste yerine
/// BUYUYEN BIR AGAC - her dal bir hafiza kategorisi, her yaprak tek bir
/// ani. Once "Gökyüzü ve Kök" konsept mockup'inda gosterildi, burada
/// Flutter CustomPainter'a tasindi (3D motor yok, tamamen 2D vektor).
///
/// Buyume metrigi: TOPLAM HAFIZA SAYISI (backend'deki mesaj-sayisi
/// tabanli FAMILIARITY_THRESHOLD degil, BILEREK) - bu ekran hafiza
/// hakkinda, sohbet tonu hakkinda degil, o yuzden "Aura ne kadar sey
/// biliyor" burada daha dogru bir buyume olcusu.
class MemoryBranch {
  final String label;
  final Color color;
  final double angleDeg;
  final double length;
  const MemoryBranch(this.label, this.color, this.angleDeg, this.length);
}

const List<MemoryBranch> memoryBranches = [
  MemoryBranch('Kimlik', Color(0xFFC96A3E), -100, 95),
  MemoryBranch('Hobiler & İlgi', Color(0xFF7FB894), -55, 110),
  MemoryBranch('Hedefler & Planlar', Color(0xFFD4A437), -20, 100),
  MemoryBranch('Rutin & Tercihler', Color(0xFF6A8FC9), -140, 100),
  MemoryBranch('Anılar & Diğer', Color(0xFFA179C9), -165, 85),
];

/// Herhangi bir serbest-metin kategoriyi 5 daldan birine esler. Bilinen
/// hicbir dalla eslesmezse "Anılar & Diğer"e duser - yeni bir kategori
/// turu Aura'nin cikarim promptuna eklendiginde bu haritanin
/// GUNCELLENMESI GEREKMEZ, hep bir dalda yer bulur.
int branchIndexForCategory(String category) {
  final c = category.toLowerCase();
  const kimlik = ['isim', 'identity', 'yer', 'location', 'meslek', 'work', 'job'];
  const hobi = ['hobiler', 'hobby', 'hobbies', 'ilgi_alanlari', 'interests'];
  const hedef = ['hedefler', 'goals', 'goal', 'projeler', 'projects', 'planlar', 'plans', 'upcoming_event', 'gundem'];
  const rutin = ['routine', 'rutin', 'tercihler', 'preference', 'preferences', 'iletisim_tercihleri', 'communication_preferences'];
  if (kimlik.contains(c)) return 0;
  if (hobi.contains(c)) return 1;
  if (hedef.contains(c)) return 2;
  if (rutin.contains(c)) return 3;
  return 4;
}

double _seededRand(int seed) {
  final x = math.sin(seed * 999) * 10000;
  return x - x.floorToDouble();
}

class MemoryTreePainter extends CustomPainter {
  final List<MemoryItem> memories;
  final double growth; // 0.0 - 1.0

  MemoryTreePainter({required this.memories, required this.growth});

  @override
  void paint(Canvas canvas, Size size) {
    final baseX = size.width / 2;
    final baseY = size.height - 12;
    final trunkTop = baseY - 90 * math.min(1.0, 0.4 + growth * 0.6);

    final trunkPaint = Paint()
      ..color = const Color(0xFF6B4A34)
      ..strokeWidth = 10 * math.min(1.0, 0.5 + growth * 0.5)
      ..strokeCap = StrokeCap.round;
    canvas.drawLine(Offset(baseX, baseY), Offset(baseX, trunkTop), trunkPaint);

    // Kategoriye gore grupla
    final Map<int, List<MemoryItem>> byBranch = {};
    for (final m in memories) {
      final idx = branchIndexForCategory(m.category);
      byBranch.putIfAbsent(idx, () => []).add(m);
    }

    for (var bi = 0; bi < memoryBranches.length; bi++) {
      final branchActive = growth > bi * 0.12;
      if (!branchActive) continue;
      final branch = memoryBranches[bi];
      final rad = branch.angleDeg * math.pi / 180;
      final growFactor = math.min(1.0, (growth - bi * 0.12) / 0.35);
      final len = branch.length * growFactor;
      final forkY = trunkTop + (baseY - trunkTop) * (0.15 + bi * 0.12);
      final endX = baseX + math.cos(rad) * len;
      final endY = forkY + math.sin(rad) * len;

      final branchPaint = Paint()
        ..color = const Color(0xFF6B4A34)
        ..strokeWidth = 4
        ..style = PaintingStyle.stroke;
      final path = Path()
        ..moveTo(baseX, forkY)
        ..quadraticBezierTo(
          baseX + math.cos(rad) * len * 0.5,
          forkY + math.sin(rad) * len * 0.5 - 10,
          endX, endY,
        );
      canvas.drawPath(path, branchPaint);

      final items = byBranch[bi] ?? const [];
      // En az bir sembolik yaprak goster (dal "bos degil" hissi versin),
      // gercek hafiza sayisi kadar da yaprak ekle (max 14, gorsel karisikligi
      // onlemek icin).
      final leafCount = items.isEmpty ? 0 : math.min(14, items.length);
      final leafPaint = Paint();
      for (var i = 0; i < leafCount; i++) {
        final t = (i + 1) / (leafCount + 1) * growFactor;
        final jitterX = (_seededRand(bi * 50 + i) - 0.5) * 14;
        final jitterY = (_seededRand(bi * 50 + i + 1) - 0.5) * 14;
        final lx = baseX + math.cos(rad) * len * t + jitterX;
        final ly = forkY + math.sin(rad) * len * t + jitterY;
        leafPaint.color = branch.color.withValues(
          alpha: 0.55 + _seededRand(bi * 90 + i) * 0.45,
        );
        canvas.drawCircle(Offset(lx, ly), 4.5, leafPaint);
      }
    }
  }

  @override
  bool shouldRepaint(covariant MemoryTreePainter oldDelegate) {
    return oldDelegate.growth != growth || oldDelegate.memories.length != memories.length;
  }
}

/// Ustte agac, altinda asama etiketi ("Fide" / "Genc agac" / "Olgun agac").
class MemoryTreeWidget extends StatelessWidget {
  final List<MemoryItem> memories;
  const MemoryTreeWidget({super.key, required this.memories});

  @override
  Widget build(BuildContext context) {
    final growth = math.min(1.0, memories.length / 20.0);
    final stage = growth < 0.25
        ? 'Fide'
        : growth < 0.65
            ? 'Genç ağaç'
            : 'Olgun ağaç';
    return Column(
      children: [
        SizedBox(
          height: 220,
          width: double.infinity,
          child: CustomPaint(
            painter: MemoryTreePainter(memories: memories, growth: growth),
          ),
        ),
        const SizedBox(height: 8),
        Text(
          stage,
          style: const TextStyle(
            color: Colors.white,
            fontWeight: FontWeight.w600,
            fontSize: 15,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          '${memories.length} anı biriktirdi',
          style: const TextStyle(color: Colors.white38, fontSize: 12),
        ),
      ],
    );
  }
}
