enum VoiceCallStatus { idle, connecting, listening, auraSpeaking, error }

class VoiceCallState {
  final VoiceCallStatus status;
  // Canli altyazi: tur bitmeden (turn_complete'ten once), o ana kadar
  // konusulani gosteren gecici metin. turn_complete gelince ikisi de
  // temizlenir - kalici metin zaten sohbet baloncugu olarak eklenir.
  final String liveUserText;
  final String liveAssistantText;
  // status==error iken gosterilecek spesifik mesaj (orn. "gunluk
  // sesli goruşme hakkin doldu"). Bilerek HER copyWith cagrisinda
  // sifirlaniyor (asagida ?? YOK) - cunku status error'dan degisince
  // eski mesajin kalmasi istenmiyor, error'a girerken de zaten cagiran
  // taraf spesifik bir mesaj VEYA null (genel "Baglanti sorunu" icin)
  // acikca gecirir.
  final String? errorMessage;

  const VoiceCallState({
    this.status = VoiceCallStatus.idle,
    this.liveUserText = "",
    this.liveAssistantText = "",
    this.errorMessage,
  });

  bool get isActive => status != VoiceCallStatus.idle;

  VoiceCallState copyWith({
    VoiceCallStatus? status,
    String? liveUserText,
    String? liveAssistantText,
    String? errorMessage,
  }) {
    return VoiceCallState(
      status: status ?? this.status,
      liveUserText: liveUserText ?? this.liveUserText,
      liveAssistantText: liveAssistantText ?? this.liveAssistantText,
      errorMessage: errorMessage,
    );
  }
}
