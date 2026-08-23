import "package:flutter/material.dart";
import "package:flutter_riverpod/flutter_riverpod.dart";
import "package:google_fonts/google_fonts.dart";

import "../models/voice_call_state.dart";
import "../notifier/voice_call_notifier.dart";

/// Chat ekraninin ustune gomulu, kucuk sesli-gorusme durum cubugu.
/// Cagri aktif degilken hic yer kaplamaz (SizedBox.shrink) - chat ekrani
/// hicbir zaman kaybolmaz, sadece bu ince serit AppBar'in altinda belirir.
class VoiceCallBar extends ConsumerWidget {
  const VoiceCallBar({super.key});

  static const _indigoColor = Color(0xFF6C63FF);

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

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final callState = ref.watch(voiceCallProvider);

    if (!callState.isActive) {
      return const SizedBox.shrink();
    }

    final isSpeaking = callState.status == VoiceCallStatus.auraSpeaking;
    final isError = callState.status == VoiceCallStatus.error;

    // Canli altyazi metni burada DEGIL, chat_screen.dart'taki mesaj
    // listesinde normal bir baloncuk gibi gosteriliyor - boylece sesli
    // konusma da yazili sohbetle ayni ekranda, ayni bicimde goruluyor.
    return Container(
      margin: const EdgeInsets.fromLTRB(12, 4, 12, 4),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: const Color(0xFF12122A),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: isError ? Colors.redAccent.withValues(alpha: 0.5) : _indigoColor.withValues(alpha: 0.4),
          width: 1,
        ),
      ),
      child: Row(
        children: [
          TweenAnimationBuilder<double>(
            tween: Tween(begin: 0.85, end: isSpeaking ? 1.15 : 1.0),
            duration: const Duration(milliseconds: 400),
            curve: Curves.easeInOut,
            builder: (_, scale, __) => Transform.scale(
              scale: scale,
              child: Container(
                width: 10,
                height: 10,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: isError ? Colors.redAccent : _indigoColor,
                ),
              ),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              // Limit/hata mesaji gibi spesifik bir aciklama varsa (orn.
              // "gunluk sesli goruşme hakkin doldu") onu goster - yoksa
              // genel durum metnini.
              (isError && callState.errorMessage != null)
                  ? callState.errorMessage!
                  : "Sesli görüşme • ${_statusText(callState.status)}",
              style: GoogleFonts.poppins(color: Colors.white70, fontSize: 12),
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          ),
          if (isError)
            IconButton(
              icon: const Icon(Icons.refresh, color: _indigoColor, size: 20),
              tooltip: "Tekrar Dene",
              onPressed: () => ref.read(voiceCallProvider.notifier).retry(),
            ),
          IconButton(
            icon: const Icon(Icons.call_end, color: Colors.redAccent, size: 20),
            tooltip: "Görüşmeyi Bitir",
            onPressed: () => ref.read(voiceCallProvider.notifier).endCall(),
          ),
        ],
      ),
    );
  }
}
