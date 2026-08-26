class UserProfile {
  final int id;
  final String? name;
  final String notes;
  // BULUNDU (kullanici istegi): kullanici gunluk kullanim limitini
  // ancak duvara carpinca ogreniyordu - artik ayarlar ekraninda
  // seffaf sekilde gosteriliyor, "guven vermeli" geri bildirimine gore.
  final String tier;
  final int dailyMessageCount;
  final int dailyVoiceSeconds;
  // Gizli mod kod cumlesi belirlenmis mi (2026-08-26) - kod cumlesinin
  // kendisi/hash'i istemciye ASLA gonderilmiyor, sadece bu bool.
  final bool hasSecretPhrase;

  UserProfile({
    required this.id,
    this.name,
    required this.notes,
    this.tier = 'free',
    this.dailyMessageCount = 0,
    this.dailyVoiceSeconds = 0,
    this.hasSecretPhrase = false,
  });

  factory UserProfile.fromJson(Map<String, dynamic> json) {
    return UserProfile(
      id: json['id'] ?? 1,
      name: json['name'],
      notes: json['notes'] ?? '',
      tier: json['tier'] ?? 'free',
      dailyMessageCount: json['daily_message_count'] ?? 0,
      dailyVoiceSeconds: json['daily_voice_seconds'] ?? 0,
      hasSecretPhrase: json['has_secret_phrase'] ?? false,
    );
  }

  UserProfile copyWith({
    String? name,
    String? notes,
    bool? hasSecretPhrase,
  }) {
    return UserProfile(
      id: id,
      name: name ?? this.name,
      notes: notes ?? this.notes,
      tier: tier,
      dailyMessageCount: dailyMessageCount,
      dailyVoiceSeconds: dailyVoiceSeconds,
      hasSecretPhrase: hasSecretPhrase ?? this.hasSecretPhrase,
    );
  }
}
