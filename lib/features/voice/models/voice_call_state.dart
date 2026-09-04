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

  // Goruntulu gorusme (2026-09-04, "canli kamera acilsin sesli ve goruntulu
  // konussun"): bu iki alan SADECE UI'nin ne gostermesi gerektigini bilmesi
  // icin - kameranin kendisi (CameraController) BILEREK bu immutable state'in
  // DISINDA, notifier'in kendi ozel alani olarak yasiyor (bkz.
  // VoiceCallNotifier.cameraController getter'i) - controller'i her
  // copyWith'te tasimak/karsilastirmak gereksiz karmasiklik/hata riski
  // eklerdi.
  final bool videoEnabled;
  final bool cameraReady;
  // BULUNDU (2026-09-04, kullanici + kendi testimde ayni sekilde
  // uretildi): kamera izni reddedilince/donanim basarisiz olunca ekran
  // SESSIZCE "Kamera aciliyor..." yazisinda sonsuza dek takili kaliyordu -
  // mikrofon tarafinin AKSINE (o net "izin verilmedi" mesaji veriyor) hic
  // geri bildirim yoktu. Bu bayrak video_call_screen.dart'a "beklemeyi
  // birak, kullaniciya soyle" sinyali verir - CAGRIYI SONLANDIRMAZ (ses
  // hala calisir), sadece kamera onizlemesi yerine anlasilir bir mesaj
  // gosterilir.
  final bool cameraFailed;

  const VoiceCallState({
    this.status = VoiceCallStatus.idle,
    this.liveUserText = "",
    this.liveAssistantText = "",
    this.errorMessage,
    this.videoEnabled = false,
    this.cameraReady = false,
    this.cameraFailed = false,
  });

  bool get isActive => status != VoiceCallStatus.idle;

  VoiceCallState copyWith({
    VoiceCallStatus? status,
    String? liveUserText,
    String? liveAssistantText,
    String? errorMessage,
    bool? videoEnabled,
    bool? cameraReady,
    bool? cameraFailed,
  }) {
    return VoiceCallState(
      status: status ?? this.status,
      liveUserText: liveUserText ?? this.liveUserText,
      liveAssistantText: liveAssistantText ?? this.liveAssistantText,
      errorMessage: errorMessage,
      videoEnabled: videoEnabled ?? this.videoEnabled,
      cameraReady: cameraReady ?? this.cameraReady,
      cameraFailed: cameraFailed ?? this.cameraFailed,
    );
  }
}
