enum VoiceCallStatus { idle, connecting, listening, auraSpeaking, error }

class VoiceCallState {
  final VoiceCallStatus status;

  const VoiceCallState({this.status = VoiceCallStatus.idle});

  bool get isActive => status != VoiceCallStatus.idle;

  VoiceCallState copyWith({VoiceCallStatus? status}) {
    return VoiceCallState(status: status ?? this.status);
  }
}
