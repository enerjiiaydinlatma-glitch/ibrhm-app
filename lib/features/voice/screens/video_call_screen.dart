import "package:camera/camera.dart";
import "package:flutter/material.dart";
import "package:flutter_riverpod/flutter_riverpod.dart";
import "package:google_fonts/google_fonts.dart";

import "../models/voice_call_state.dart";
import "../notifier/voice_call_notifier.dart";

/// Tam ekran goruntulu gorusme (2026-09-04, kullanici istegi: "canli
/// kamera acilsin sesli ve goruntulu konussun fotoğraf çekebilsin aura
/// efekt yapabilsin"). Ses/baglanti tarafinin TAMAMI zaten VoiceCallNotifier
/// icinde yasiyor (bu ekran sadece kamerayi gosterip startCall'i video:true
/// ile cagiriyor) - VoiceCallBar ile ayni durum makinesini paylasir, bu
/// yuzden chat ekranindaki tum dayaniklilik (otomatik yeniden baglanma,
/// gunluk limit, oturum tazeleme) burada da GECERLI.
class VideoCallScreen extends ConsumerStatefulWidget {
  const VideoCallScreen({super.key, required this.token});

  final String token;

  @override
  ConsumerState<VideoCallScreen> createState() => _VideoCallScreenState();
}

class _VideoCallScreenState extends ConsumerState<VideoCallScreen> {
  static const _indigoColor = Color(0xFF6C63FF);
  bool _capturing = false;
  String? _flashMessage;

  @override
  void initState() {
    super.initState();
    // Ekran acilir acilmaz baglan - kullanici "canli kamera acilsin"
    // dedigi icin ekstra bir "baslat" tusuna gerek yok, ekranin kendisi
    // zaten o niyeti tasiyor.
    Future.microtask(
      () => ref.read(voiceCallProvider.notifier).startCall(
            widget.token,
            video: true,
          ),
    );
  }

  @override
  void dispose() {
    // Ekrandan HERHANGI bir sekilde cikiliyorsa (geri tusu, sistem geri
    // hareketi) gorusmeyi de bitir - arka planda mikrofon/kamera acik
    // kalan "hayalet" bir gorusme birakmayalim.
    ref.read(voiceCallProvider.notifier).endCall();
    super.dispose();
  }

  String _statusText(VoiceCallStatus status) {
    switch (status) {
      case VoiceCallStatus.idle:
        return "";
      case VoiceCallStatus.connecting:
        return "Bağlanıyor...";
      case VoiceCallStatus.listening:
        return "Dinliyorum";
      case VoiceCallStatus.auraSpeaking:
        return "Aura konuşuyor";
      case VoiceCallStatus.error:
        return "Bağlantı sorunu";
    }
  }

  Future<void> _takePhoto() async {
    if (_capturing) return;
    setState(() => _capturing = true);
    final ok = await ref.read(voiceCallProvider.notifier).captureAndAnalyzePhoto();
    if (!mounted) return;
    setState(() {
      _capturing = false;
      _flashMessage = ok
          ? "Fotoğraf sohbete eklendi ✨"
          : "Fotoğraf çekilemedi, tekrar dener misin?";
    });
    Future.delayed(const Duration(seconds: 2), () {
      if (mounted) setState(() => _flashMessage = null);
    });
  }

  @override
  Widget build(BuildContext context) {
    final callState = ref.watch(voiceCallProvider);
    final controller = ref.watch(voiceCallProvider.notifier).cameraController;
    final isError = callState.status == VoiceCallStatus.error;

    return PopScope(
      onPopInvokedWithResult: (didPop, _) {
        // dispose() zaten endCall() cagiriyor - burada ekstra bir sey
        // yapmaya gerek yok, sadece normal geri gitmeye izin veriyoruz.
      },
      child: Scaffold(
        backgroundColor: Colors.black,
        body: SafeArea(
          child: Stack(
            children: [
              // Kamera onizlemesi - hazir olana kadar sade bir bekleme
              // ekrani (bagimsiz oldugu icin ses baglantisi kamera
              // hazir olmadan da baslayabilir, konusma bekletilmez).
              Positioned.fill(
                child: (callState.cameraReady &&
                        controller != null &&
                        controller.value.isInitialized)
                    ? Center(
                        child: AspectRatio(
                          aspectRatio: controller.value.aspectRatio,
                          child: CameraPreview(controller),
                        ),
                      )
                    : Container(
                        color: const Color(0xFF0A0A18),
                        alignment: Alignment.center,
                        child: Column(
                          mainAxisSize: MainAxisSize.min,
                          // BULUNDU (2026-09-04, gercek testte kanitlandi):
                          // mikrofon izni reddedilince _connect() ERKEN
                          // donuyor ve _startVideoCapture() HIC CAGRILMIYOR
                          // - yani cameraFailed asla true olmuyor, ama
                          // cameraReady da hep false kaliyor. Eskiden bu
                          // durumda ekran (ust banner'daki mikrofon hatasina
                          // ragmen) sonsuza dek "Kamera aciliyor..."
                          // gosteriyordu - kamera hic denenmemisken bile.
                          // isError kontrolu bu yaniltici durumu da kapatiyor.
                          children: isError
                              ? [
                                  const Icon(Icons.error_outline,
                                      color: Colors.white38, size: 40),
                                  const SizedBox(height: 16),
                                  Padding(
                                    padding: const EdgeInsets.symmetric(horizontal: 32),
                                    child: Text(
                                      callState.errorMessage ??
                                          "Görüşme başlatılamadı.",
                                      textAlign: TextAlign.center,
                                      style: GoogleFonts.poppins(color: Colors.white54, fontSize: 13),
                                    ),
                                  ),
                                ]
                              : callState.cameraFailed
                                  ? [
                                      const Icon(Icons.videocam_off_outlined,
                                          color: Colors.white38, size: 40),
                                      const SizedBox(height: 16),
                                      Padding(
                                        padding: const EdgeInsets.symmetric(horizontal: 32),
                                        child: Text(
                                          "Kamera açılamadı. Tarayıcı/telefon ayarlarından "
                                          "kamera iznini kontrol et — sesli konuşmaya devam "
                                          "edebilirsin.",
                                          textAlign: TextAlign.center,
                                          style: GoogleFonts.poppins(color: Colors.white54, fontSize: 13),
                                        ),
                                      ),
                                    ]
                                  : [
                                      const CircularProgressIndicator(color: _indigoColor),
                                      const SizedBox(height: 16),
                                      Text(
                                        "Kamera açılıyor...",
                                        style: GoogleFonts.poppins(color: Colors.white54, fontSize: 13),
                                      ),
                                    ],
                        ),
                      ),
              ),

              // Ust bar: geri + durum.
              Positioned(
                top: 8,
                left: 8,
                right: 8,
                child: Row(
                  children: [
                    IconButton(
                      icon: const Icon(Icons.arrow_back, color: Colors.white),
                      onPressed: () => Navigator.of(context).maybePop(),
                    ),
                    Expanded(
                      child: Container(
                        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                        decoration: BoxDecoration(
                          color: Colors.black.withValues(alpha: 0.45),
                          borderRadius: BorderRadius.circular(20),
                        ),
                        child: Text(
                          (isError && callState.errorMessage != null)
                              ? callState.errorMessage!
                              : "Görüntülü görüşme • ${_statusText(callState.status)}",
                          textAlign: TextAlign.center,
                          style: GoogleFonts.poppins(color: Colors.white, fontSize: 12),
                          maxLines: 3,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ),
                    const SizedBox(width: 40), // geri tusuyla gorsel denge
                  ],
                ),
              ),

              // Canli altyazi (varsa) - alt kontrollerin hemen ustunde.
              if (callState.liveUserText.isNotEmpty ||
                  callState.liveAssistantText.isNotEmpty)
                Positioned(
                  left: 16,
                  right: 16,
                  bottom: 120,
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                    decoration: BoxDecoration(
                      color: Colors.black.withValues(alpha: 0.5),
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: Text(
                      callState.liveAssistantText.isNotEmpty
                          ? callState.liveAssistantText
                          : callState.liveUserText,
                      style: GoogleFonts.poppins(color: Colors.white, fontSize: 13),
                      maxLines: 4,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ),

              if (_flashMessage != null)
                Positioned(
                  left: 16,
                  right: 16,
                  bottom: 190,
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                    decoration: BoxDecoration(
                      color: _indigoColor.withValues(alpha: 0.85),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(
                      _flashMessage!,
                      textAlign: TextAlign.center,
                      style: GoogleFonts.poppins(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w600),
                    ),
                  ),
                ),

              // Alt kontroller: deklansor + bitir.
              Positioned(
                left: 0,
                right: 0,
                bottom: 24,
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    _CircleButton(
                      onTap: (callState.cameraReady && !_capturing) ? _takePhoto : null,
                      color: Colors.white.withValues(alpha: 0.15),
                      icon: _capturing ? null : Icons.camera_alt_rounded,
                      child: _capturing
                          ? const SizedBox(
                              width: 20,
                              height: 20,
                              child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                            )
                          : null,
                    ),
                    const SizedBox(width: 28),
                    _CircleButton(
                      onTap: () => Navigator.of(context).maybePop(),
                      color: Colors.redAccent,
                      icon: Icons.call_end,
                      size: 64,
                    ),
                    const SizedBox(width: 28),
                    if (isError)
                      _CircleButton(
                        onTap: () => ref.read(voiceCallProvider.notifier).retry(),
                        color: _indigoColor,
                        icon: Icons.refresh,
                      )
                    else
                      const SizedBox(width: 52),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _CircleButton extends StatelessWidget {
  const _CircleButton({
    required this.onTap,
    required this.color,
    this.icon,
    this.child,
    this.size = 52,
  });

  final VoidCallback? onTap;
  final Color color;
  final IconData? icon;
  final Widget? child;
  final double size;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: size,
        height: size,
        decoration: BoxDecoration(
          shape: BoxShape.circle,
          color: onTap == null ? color.withValues(alpha: 0.4) : color,
        ),
        child: child ?? (icon != null ? Icon(icon, color: Colors.white) : null),
      ),
    );
  }
}
