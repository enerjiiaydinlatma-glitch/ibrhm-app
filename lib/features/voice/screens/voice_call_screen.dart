import "package:flutter/material.dart";
import "package:flutter_riverpod/flutter_riverpod.dart";
import "package:google_fonts/google_fonts.dart";

import "../models/voice_call_state.dart";
import "../notifier/mic_level_notifier.dart";
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
          // Kullanici istegi (2026-08-26): sesli gorusme ekrani "sade"ydi -
          // sabit tek bir nokta yerine, kullanici konusurken GERCEKTEN
          // mikrofon seviyesine tepki veren kucuk bir dalga gostergesi.
          // Aura konusurken (mikrofon susturulmus/pasif) eski nabiz
          // animasyonuna donuluyor - o durumda gosterecek gercek bir
          // girdi sinyali yok.
          if (callState.status == VoiceCallStatus.listening)
            const _MicLevelBars()
          else
            TweenAnimationBuilder<double>(
              tween: Tween(begin: 0.85, end: isSpeaking ? 1.15 : 1.0),
              duration: const Duration(milliseconds: 400),
              curve: Curves.easeInOut,
              builder: (_, scale, _) => Transform.scale(
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
              // Teknik hata mesajlari (orn. web/Safari istisna metinleri)
              // uzun olabiliyor - teshis icin okunabilir kalsin diye 2'den
              // 4'e cikarildi.
              maxLines: 4,
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

/// 4 cubuktan olusan minik bir ses-seviye gostergesi. micLevelProvider
/// SADECE bu widget'i besliyor (bkz. mic_level_notifier.dart) - VoiceCallBar
/// zaten voiceCallProvider'i izliyor, bu ikinci watch onunla CAKISMIYOR,
/// sadece bu kucuk alt agac saniyede ~10 kez yeniden ciziliyor - tum
/// sohbet listesi degil.
class _MicLevelBars extends ConsumerWidget {
  const _MicLevelBars();

  static const _indigoColor = Color(0xFF6C63FF);
  // Her cubugun gecmis genlige tepki agirligi - ortadaki cubuklar daha
  // duyarli, kenardakiler daha yumusak tepki verir (gercek bir
  // ekolayzir gorunumu icin).
  static const List<double> _sensitivity = [0.6, 1.0, 1.0, 0.6];

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final level = ref.watch(micLevelProvider);
    return SizedBox(
      width: 22,
      height: 16,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        crossAxisAlignment: CrossAxisAlignment.center,
        children: List.generate(4, (i) {
          final barLevel = (level * _sensitivity[i]).clamp(0.0, 1.0);
          return AnimatedContainer(
            duration: const Duration(milliseconds: 90),
            width: 3,
            height: 4.0 + barLevel * 12,
            decoration: BoxDecoration(
              color: _indigoColor,
              borderRadius: BorderRadius.circular(2),
            ),
          );
        }),
      ),
    );
  }
}
