class UserProfile {
  final int id;
  final String? name;
  final String warmth;
  final String formality;
  final String humor;
  final String directness;
  final String notes;
  // BULUNDU (kullanici istegi): kullanici gunluk kullanim limitini
  // ancak duvara carpinca ogreniyordu - artik ayarlar ekraninda
  // seffaf sekilde gosteriliyor, "guven vermeli" geri bildirimine gore.
  final String tier;
  final int dailyMessageCount;
  final int dailyVoiceSeconds;

  UserProfile({
    required this.id,
    this.name,
    required this.warmth,
    required this.formality,
    required this.humor,
    required this.directness,
    required this.notes,
    this.tier = 'free',
    this.dailyMessageCount = 0,
    this.dailyVoiceSeconds = 0,
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
      tier: json['tier'] ?? 'free',
      dailyMessageCount: json['daily_message_count'] ?? 0,
      dailyVoiceSeconds: json['daily_voice_seconds'] ?? 0,
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
      tier: tier,
      dailyMessageCount: dailyMessageCount,
      dailyVoiceSeconds: dailyVoiceSeconds,
    );
  }
}
