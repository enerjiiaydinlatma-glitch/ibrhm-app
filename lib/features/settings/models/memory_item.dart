class MemoryItem {
  final int id;
  final String category;
  final String memoryKey;
  final String memoryValue;
  final double confidence;
  final double importance;

  MemoryItem({
    required this.id,
    required this.category,
    required this.memoryKey,
    required this.memoryValue,
    required this.confidence,
    required this.importance,
  });

  factory MemoryItem.fromJson(Map<String, dynamic> json) {
    return MemoryItem(
      id: json['id'] as int,
      category: json['category']?.toString() ?? '',
      memoryKey: json['memory_key']?.toString() ?? '',
      memoryValue: json['memory_value']?.toString() ?? '',
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0.0,
      importance: (json['importance'] as num?)?.toDouble() ?? 0.0,
    );
  }
}
