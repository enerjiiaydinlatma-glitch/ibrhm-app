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
  // Otomatik ogrenen uslup vektoru (0.0-1.0) - backend zaten donduruyordu,
  // sadece istemci tarafinda hic gosterilmiyordu. "Aura kendi kendine
  // ogreniyor" yazisinin GORUNMEZ kalmasi yerine, ne ogrendigini kucuk
  // bir ozetle gostermek icin (2026-08-26, kullanici istegi devami).
  final double styleWarmth;
  final double styleFormality;
  final double styleHumor;
  final int styleSampleCount;

  UserProfile({
    required this.id,
    this.name,
    required this.notes,
    this.tier = 'free',
    this.dailyMessageCount = 0,
    this.dailyVoiceSeconds = 0,
    this.hasSecretPhrase = false,
    this.styleWarmth = 0.5,
    this.styleFormality = 0.5,
    this.styleHumor = 0.5,
    this.styleSampleCount = 0,
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
      styleWarmth: (json['style_warmth'] as num?)?.toDouble() ?? 0.5,
      styleFormality: (json['style_formality'] as num?)?.toDouble() ?? 0.5,
      styleHumor: (json['style_humor'] as num?)?.toDouble() ?? 0.5,
      styleSampleCount: json['style_sample_count'] ?? 0,
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
      styleWarmth: styleWarmth,
      styleFormality: styleFormality,
      styleHumor: styleHumor,
      styleSampleCount: styleSampleCount,
    );
  }
}
