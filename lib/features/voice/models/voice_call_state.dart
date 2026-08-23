enum VoiceCallStatus { idle, connecting, listening, auraSpeaking, error }

class VoiceCallState {
  final VoiceCallStatus status;
  // Canli altyazi: tur bitmeden (turn_complete'ten once), o ana kadar
  // konusulani gosteren gecici metin. turn_complete gelince ikisi de
  // temizlenir - kalici metin zaten sohbet baloncugu olarak eklenir.
  final String liveUserText;
  final String liveAssistantText;

  const VoiceCallState({
    this.status = VoiceCallStatus.idle,
    this.liveUserText = "",
    this.liveAssistantText = "",
  });

  bool get isActive => status != VoiceCallStatus.idle;

  VoiceCallState copyWith({
    VoiceCallStatus? status,
    String? liveUserText,
    String? liveAssistantText,
  }) {
    return VoiceCallState(
      status: status ?? this.status,
      liveUserText: liveUserText ?? this.liveUserText,
      liveAssistantText: liveAssistantText ?? this.liveAssistantText,
    );
  }
}
