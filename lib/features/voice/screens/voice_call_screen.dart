import "dart:async";
import "dart:convert";
import "dart:typed_data";

import "package:dio/dio.dart";
import "package:flutter/material.dart";
import "package:flutter_riverpod/flutter_riverpod.dart";
import "package:google_fonts/google_fonts.dart";
import "package:record/record.dart";

import "../../chat/notifier/chat_notifier.dart";
import "../../../services/auth_service.dart";
import "../../../services/reminder_service.dart";
import "../../../services/tts_service.dart";
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
          color: isError
              ? Colors.redAccent.withValues(alpha: 0.5)
              : _indigoColor.withValues(alpha: 0.4),
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
            const ExcludeSemantics(child: _MicLevelBars())
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
            child: Semantics(
              liveRegion: true,
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
          ),
          if (isError)
            IconButton(
              icon: const Icon(Icons.refresh, color: _indigoColor, size: 20),
              tooltip: "Tekrar Dene",
              onPressed: () => ref.read(voiceCallProvider.notifier).retry(),
            ),
          // Kullanici istegi (2026-08-26): "Aura beyin, digerleri ajan"
          // ilkesindeki bilinen bosluk (Gemini Live'in gercek zamanli
          // esdegeri olan bir Groq yedegi yok) icin somut cozum. Canli
          // baglanti kurulamiyorsa "basili tut konus" ile Groq Whisper +
          // mevcut dayanikli metin hattina (Gemini/Groq yedekli) duser.
          if (isError) const _VoiceFallbackButton(),
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

/// "Basili tut konus" yedek sesli mod (2026-08-26, kullanici istegi).
/// Gemini Live baglanamadiginda/coktugunde gorunur (bkz. yukaridaki
/// isError kontrolu). Canli/kesintisiz DEGIL - basip konus, birak,
/// birkaç saniye bekle: ses Groq Whisper'a gidip metne cevrilir, metin
/// /api/chat ile AYNI govdeden (guvenlik/gizlilik dahil) gecip Aura'nin
/// cevabini uretir, cevap TtsService ile okunur. Kendi basina TAMAMEN
/// bagimsiz - VoiceCallNotifier'in karmasik yeniden-baglanma durum
/// makinesine HIC dokunmuyor (o sistemde bugune kadar birkaç kritik
/// donma hatasi bulunup duzeltildi - riski buyutmemek icin bilerek ayri
/// tutuldu).
class _VoiceFallbackButton extends ConsumerStatefulWidget {
  const _VoiceFallbackButton();

  @override
  ConsumerState<_VoiceFallbackButton> createState() =>
      _VoiceFallbackButtonState();
}

class _VoiceFallbackButtonState extends ConsumerState<_VoiceFallbackButton> {
  static const _indigoColor = Color(0xFF6C63FF);
  static const _minRecordingBytes = 3200; // ~0.1sn, 16kHz mono 16-bit

  final AudioRecorder _recorder = AudioRecorder();
  // KOD INCELEMESI BULGUSU (2026-08-27): her kayitta SIFIRDAN yeni bir
  // Dio() olusturuluyordu - tam da bu oturumda backend tarafinda
  // (_groq_http/elevenlabs_http/_weather_http) duzeltilen "her cagrida
  // yeniden TCP+TLS el sikismesi" israfinin ayni Flutter tarafindaki
  // hali. Tek, kalici bir Dio ile baglanti yeniden kullaniliyor.
  final Dio _dio = Dio(
    BaseOptions(
      connectTimeout: const Duration(seconds: 15),
      receiveTimeout: const Duration(seconds: 40),
    ),
  );
  StreamSubscription<Uint8List>? _sub;
  BytesBuilder _buffer = BytesBuilder();
  bool _recording = false;
  bool _sending = false;
  // KOD INCELEMESI BULGUSU: _startRecording icindeki `await`'ler (izin
  // dialogu + startStream) tamamlanmadan _recording HALA false - kullanici
  // parmagini erken kaldirirsa (orn. ilk kullanimda izin dialogunu
  // onaylamak icin) onLongPressEnd -> _stopAndSend erken calisip
  // `if (!_recording) return;` ile hicbir sey yapmadan cikiyordu; kayit
  // birkac an sonra GERCEKTEN baslayip hic durdurulamadan sonsuza kadar
  // acik kaliyordu. Bu bayrak, "kullanici parmagini cektiginde kaydi
  // beklemeden durdur" niyetini await'ler boyunca da hatirliyor.
  bool _releasedBeforeStart = false;

  Future<void> _startRecording() async {
    if (_sending || _recording) return;
    _releasedBeforeStart = false;
    try {
      final hasPermission = await _recorder.hasPermission();
      if (!hasPermission) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text(
                "Mikrofon izni verilmedi - cihaz ayarlarindan acabilirsin.",
              ),
            ),
          );
        }
        return;
      }
      _buffer = BytesBuilder();
      final stream = await _recorder.startStream(
        const RecordConfig(
          encoder: AudioEncoder.pcm16bits,
          sampleRate: 16000,
          numChannels: 1,
          // voice_call_notifier.dart'taki ayni fix - bu ucun ONCEDEN
          // hic acilmadigi, kod incelemesinde bulundu: birincil sesli
          // gorusme yolu bunu zaten kullaniyordu, yedek buton kendi
          // AYRI RecordConfig'ini kopyalarken bu ucu miras almamisti.
          echoCancel: true,
          autoGain: true,
          noiseSuppress: true,
        ),
      );
      _sub = stream.listen((chunk) => _buffer.add(chunk));
      if (_releasedBeforeStart) {
        // Kullanici, biz hala izin/baslatma await'lerindeyken parmagini
        // cekmis - kaydi hic "basladi" saymadan hemen durdurup gonder.
        unawaited(_stopAndSend());
        return;
      }
      if (mounted) setState(() => _recording = true);
    } catch (e) {
      debugPrint("Yedek ses kaydi baslatilamadi: $e");
    }
  }

  Future<void> _stopAndSend() async {
    if (!_recording) {
      // _startRecording hala await'lerdeyse (izin dialogu vb.) bunu
      // isaretleyip, o taraf devraldiginda durdurmasini sagliyoruz.
      _releasedBeforeStart = true;
      return;
    }
    if (mounted) setState(() => _recording = false);
    await _sub?.cancel();
    try {
      await _recorder.stop();
    } catch (_) {
      // Zaten durmus olabilir - onemli degil.
    }
    final pcmBytes = _buffer.toBytes();
    if (pcmBytes.length < _minRecordingBytes) return;

    if (mounted) setState(() => _sending = true);
    try {
      final token = await AuthService().getToken();
      if (token == null) return;
      final wavBytes = _pcm16ToWav(pcmBytes);
      final response = await _dio.post(
        "${TtsService.backendUrl}/api/voice/fallback-turn",
        data: {"audio_base64": base64Encode(wavBytes)},
        options: Options(headers: {"Authorization": "Bearer $token"}),
      );
      final data = response.data as Map;
      final transcript = (data["transcript"] as String?)?.trim() ?? "";
      final reply = (data["reply"] as String?)?.trim() ?? "";
      if (transcript.isNotEmpty) {
        ref.read(chatProvider.notifier).addUserMessage(transcript);
      }
      if (reply.isNotEmpty) {
        ref.read(chatProvider.notifier).addAssistantMessage(reply);
        unawaited(TtsService.instance.speak(reply, token: token));
        // KOD INCELEMESI BULGUSU: bu tur de (yazili sohbetle ayni ortak
        // govdeden gectigi icin) yeni bir hatirlatma cikarabilir - bkz.
        // ReminderService.syncFromServer'daki not.
        unawaited(ReminderService.instance.syncFromServer(token));
      }
    } catch (e) {
      // KOD INCELEMESI BULGUSU: bu hata daha once SADECE debugPrint'e
      // gidiyordu - kullanici konusup birakinca hicbir sey olmuyormus
      // gibi goruyordu (backend zaten bir Groq/Gemini cagrisi harcamis
      // olabilecegi halde). Artik kisa bir geri bildirim gosteriliyor.
      debugPrint("Yedek sesli mod hatasi: $e");
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text("Ses gönderilemedi, tekrar dener misin?"),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  /// Groq Whisper'ın (ve genel olarak cogu STT servisinin) beklendigi
  /// gibi calismasi icin ham PCM16'nin basina standart 44 baytlik bir
  /// WAV basligi ekler - record paketinin startStream() ciktisi HAM
  /// (baslksiz) PCM oldugu icin bu adim sart.
  Uint8List _pcm16ToWav(
    List<int> pcmBytes, {
    int sampleRate = 16000,
    int numChannels = 1,
  }) {
    const bitsPerSample = 16;
    final byteRate = sampleRate * numChannels * bitsPerSample ~/ 8;
    final blockAlign = numChannels * bitsPerSample ~/ 8;
    final dataLength = pcmBytes.length;

    final header = BytesBuilder();
    void writeString(String s) => header.add(s.codeUnits);
    void writeUint32(int v) => header.add([
      v & 0xff,
      (v >> 8) & 0xff,
      (v >> 16) & 0xff,
      (v >> 24) & 0xff,
    ]);
    void writeUint16(int v) => header.add([v & 0xff, (v >> 8) & 0xff]);

    writeString("RIFF");
    writeUint32(36 + dataLength);
    writeString("WAVE");
    writeString("fmt ");
    writeUint32(16);
    writeUint16(1);
    writeUint16(numChannels);
    writeUint32(sampleRate);
    writeUint32(byteRate);
    writeUint16(blockAlign);
    writeUint16(bitsPerSample);
    writeString("data");
    writeUint32(dataLength);

    final result = BytesBuilder();
    result.add(header.toBytes());
    result.add(pcmBytes);
    return result.toBytes();
  }

  @override
  void dispose() {
    _sub?.cancel();
    _recorder.dispose();
    _dio.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: _recording
          ? "Kaydediyor, bırakınca gönderilir"
          : "Basılı tut ve konuş",
      hint: "Basılı tutarken konuş, bırak",
      child: GestureDetector(
        onLongPressStart: (_) => _startRecording(),
        onLongPressEnd: (_) => _stopAndSend(),
        child: Tooltip(
          message: "Basılı tut, konuş",
          child: Container(
            width: 32,
            height: 32,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: _recording
                  ? Colors.redAccent
                  : _indigoColor.withValues(alpha: 0.25),
            ),
            child: _sending
                ? const Padding(
                    padding: EdgeInsets.all(8),
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.white,
                    ),
                  )
                : Icon(
                    _recording ? Icons.mic : Icons.mic_none,
                    color: Colors.white,
                    size: 18,
                  ),
          ),
        ),
      ),
    );
  }
}
