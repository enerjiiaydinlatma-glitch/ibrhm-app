class UserProfile {
  final int id;
  final String? name;
  final String warmth;
  final String formality;
  final String humor;
  final String directness;
  final String notes;

  UserProfile({
    required this.id,
    this.name,
    required this.warmth,
    required this.formality,
    required this.humor,
    required this.directness,
    required this.notes,
  });

  factory UserProfile.fromJson(Map<String, dynamic> json) {
    return UserProfile(
      id: json['id'] ?? 1,
      name: json['name'],
      warmth: json['warmth'] ?? 'sicak',
      formality: json['formality'] ?? 'samimi',
      humor: json['humor'] ?? 'orta',
      directness: json['directness'] ?? 'dengeli',
      notes: json['notes'] ?? '',
    );
  }

  UserProfile copyWith({
    String? name,
    String? warmth,
    String? formality,
    String? humor,
    String? directness,
    String? notes,
  }) {
    return UserProfile(
      id: id,
      name: name ?? this.name,
      warmth: warmth ?? this.warmth,
      formality: formality ?? this.formality,
      humor: humor ?? this.humor,
      directness: directness ?? this.directness,
      notes: notes ?? this.notes,
    );
  }
}
