class MemoryItem {
  final int id;
  final String category;
  final String memoryKey;
  final String memoryValue;
  final double confidence;
  final double importance;
  // Dogal Hafiza (2026-08-27): kullanici "hep hatirla" diye sabitlerse
  // bu kayit backend'deki soluklasma hesabindan muaf tutulur - bkz.
  // aura_memory.py _effective_importance.
  final bool pinned;

  MemoryItem({
    required this.id,
    required this.category,
    required this.memoryKey,
    required this.memoryValue,
    required this.confidence,
    required this.importance,
    this.pinned = false,
  });

  factory MemoryItem.fromJson(Map<String, dynamic> json) {
    return MemoryItem(
      id: json['id'] as int,
      category: json['category']?.toString() ?? '',
      memoryKey: json['memory_key']?.toString() ?? '',
      memoryValue: json['memory_value']?.toString() ?? '',
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0.0,
      importance: (json['importance'] as num?)?.toDouble() ?? 0.0,
      pinned: json['pinned'] == true || json['pinned'] == 1,
    );
  }

  MemoryItem copyWith({bool? pinned}) {
    return MemoryItem(
      id: id,
      category: category,
      memoryKey: memoryKey,
      memoryValue: memoryValue,
      confidence: confidence,
      importance: importance,
      pinned: pinned ?? this.pinned,
    );
  }
}
