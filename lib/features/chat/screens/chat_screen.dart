import "dart:async";
import "dart:typed_data";
import "dart:ui";
import "package:dio/dio.dart";
import "package:flutter/foundation.dart"
    show kIsWeb, defaultTargetPlatform, TargetPlatform;
import "package:flutter/material.dart";
import "package:flutter_riverpod/flutter_riverpod.dart";
import "package:google_fonts/google_fonts.dart";
import "package:image_picker/image_picker.dart";
import "package:file_picker/file_picker.dart";
import "package:shared_preferences/shared_preferences.dart";
import "../notifier/chat_notifier.dart";
import "../models/message.dart";
import "../widgets/aura_image_reveal.dart";
import "../../voice/screens/voice_call_screen.dart";
import "../../voice/screens/video_call_screen.dart";
import "../../voice/notifier/voice_call_notifier.dart";
import "../../settings/screens/settings_screen.dart";
import "../../../services/auth_service.dart";
import "../../../services/reminder_service.dart";
import "../../../services/tts_service.dart";
import "../widgets/sky_background.dart";
import "../widgets/aura_hale.dart";
import "../../../core/i18n.dart";

class ChatScreen extends ConsumerStatefulWidget {
  final String token;
  const ChatScreen({super.key, required this.token});

  @override
  ConsumerState<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends ConsumerState<ChatScreen> {
  final _controller = TextEditingController();
  final _scrollController = ScrollController();
  // Kod sagligi taramasinda bulundu: timeout YOKTU - /api/tts istegi
  // askida kalirsa ElevenLabs->yerel TTS fallback'i HIC TETIKLENMEZ
  // (fallback sadece istek HATA donerse calisiyor, sonsuza dek asili
  // kalirsa degil).
  final Dio _dio = Dio(
    BaseOptions(
      connectTimeout: const Duration(seconds: 15),
      receiveTimeout: const Duration(seconds: 30),
    ),
  );
  // "Hesabini Kaydet" ikonu SADECE kullanici hala anonimse gorunur -
  // ayarlar menusu degil, tek amacli kucuk bir aksiyon (bkz. plan).
  bool _isAnonymous = false;

  static const String _backendUrl =
      "https://aura-backend-production-bc9c.up.railway.app";
  static const Color _bgColor = Color(0xFF0A0A1A);
  static const Color _indigoColor = Color(0xFF6C63FF);
  static const Color _userBubbleStart = Color(0xFF6C63FF);
  static const Color _userBubbleEnd = Color(0xFF9C8FFF);

  @override
  void initState() {
    super.initState();
    _checkAnonymousStatus();
    _syncReminders();
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      final notifier = ref.read(chatProvider.notifier);
      notifier.setToken(widget.token);
      await notifier.loadHistory();
      await notifier.fetchGreeting();
    });
  }

  // Kullanici istegi (2026-08-26): sohbette gecen "haftaya persembe maca
  // gidecegim, bilet almam lazim" gibi mesajlardan cikarilan hatirlatmalari
  // (backend: aura_reminders.py) bu cihazda yerel bildirim olarak
  // zamanliyor. Basarisiz olursa (izin verilmedi, platform desteklemiyor
  // vs.) sessizce yutuluyor - sohbeti ASLA etkilememeli. Gercek network/
  // zamanlama mantigi artik ReminderService.syncFromServer'da paylasilan
  // - bkz. o metottaki kod incelemesi notu (sadece acilista degil, HER
  // sohbet turundan sonra da cagrilmasi gerektigi bulundu).
  Future<void> _syncReminders() =>
      ReminderService.instance.syncFromServer(widget.token);

  Future<void> _checkAnonymousStatus({bool isRetry = false}) async {
    try {
      final response = await _dio.get(
        "$_backendUrl/api/auth/me",
        options: Options(headers: {"Authorization": "Bearer ${widget.token}"}),
      );
      final data = response.data as Map;
      if (mounted) {
        setState(() {
          _isAnonymous = (data["is_anonymous"] as int? ?? 1) == 1;
        });
      }
    } catch (e) {
      debugPrint("Anonim durum kontrolu hatasi: $e");
      // Kod sagligi taramasinda bulundu: bu cagri sessizce basarisiz
      // olursa "Hesabini Kaydet" ikonu HIC BIR ZAMAN gorunmuyordu -
      // kullanici cihaz kaybi durumunda hesabini kurtarma firsatini
      // fark etmeden kaybediyordu. Gecici bir ag sorunu ihtimaline
      // karsi bir kez, kisa bir gecikmeyle tekrar deniyoruz.
      if (!isRetry && mounted) {
        await Future.delayed(const Duration(seconds: 3));
        if (mounted) await _checkAnonymousStatus(isRetry: true);
      }
    }
  }

  // BULUNDU (kullanici istegi): kullanici cagri tusuna basinca hicbir
  // aciklama olmadan aniden mikrofon izni istegi cikiyordu - bu ozellikle
  // ilk kullanimda guven kirici olabilir. Artik SADECE ilk seferde (bir
  // SharedPreferences bayragiyla takip edilen) kisa bir aciklama
  // gosterilip ONDAN SONRA gercek izin istegi tetikleniyor. Sonraki
  // aramalar bu adimi hic gormeden dogrudan baslar.
  static const _voiceIntroShownKey = "voice_intro_shown";

  Future<void> _startVoiceCallWithPriming() async {
    final prefs = await SharedPreferences.getInstance();
    final alreadyShown = prefs.getBool(_voiceIntroShownKey) ?? false;
    if (alreadyShown) {
      ref.read(voiceCallProvider.notifier).startCall(widget.token);
      return;
    }
    if (!mounted) return;
    final proceed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: const Color(0xFF12122A),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Row(
          children: [
            Icon(Icons.mic_none_outlined, color: _indigoColor),
            const SizedBox(width: 10),
            Text(
              I18n.t("chat.voiceIntroTitle"),
              style: GoogleFonts.poppins(
                color: Colors.white,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
        content: Text(
          I18n.t("chat.voiceIntroBody"),
          style: GoogleFonts.poppins(
            color: Colors.white70,
            fontSize: 13,
            height: 1.5,
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: Text(
              I18n.t("common.cancel"),
              style: GoogleFonts.poppins(color: Colors.white54),
            ),
          ),
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: Text(
              I18n.t("common.continue"),
              style: GoogleFonts.poppins(
                color: _indigoColor,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
    await prefs.setBool(_voiceIntroShownKey, true);
    if (proceed == true) {
      ref.read(voiceCallProvider.notifier).startCall(widget.token);
    }
  }

  /// Goruntulu gorusme girisi. _pickImageFromCamera ile AYNI masaustu
  /// kisitlamasi (camera paketinin Windows/Linux/macOS destegi yok) -
  /// orada oldugu gibi anlasilir bir mesajla reddediyoruz,
  /// sessizce kilitlenmesin.
  Future<void> _startVideoCall() async {
    if (_isDesktop) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            I18n.t("chat.videoUnavailable"),
            style: GoogleFonts.poppins(),
          ),
        ),
      );
      return;
    }
    if (ref.read(voiceCallProvider).isActive) {
      ref.read(voiceCallProvider.notifier).endCall();
      return;
    }
    // iOS Safari (+ mobil web): kamera izni SADECE kullanici hareketinin
    // (bu tik'in) KENDI cagri yiginindan istenirse dialog gorunuyor -
    // ekrana gecip orada async istersek pencere kapanmis oluyor. Bu yuzden
    // izni BURADA, navigasyondan ONCE tetikliyoruz. Basarisiz olsa bile
    // (izin yok) yine de ekrana geciyoruz - orada "Kamerayi tekrar dene"
    // + sesli devam var. `await` etmiyoruz: dialog acilirken ekran da
    // acilsin, kullanici beklemesin.
    unawaited(ref.read(voiceCallProvider.notifier).primeCamera());
    if (!mounted) return;
    await Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => VideoCallScreen(token: widget.token)),
    );
  }

  Future<void> _showClaimAccountDialog() async {
    final emailController = TextEditingController();
    final passwordController = TextEditingController();
    String? errorText;

    await showDialog<void>(
      context: context,
      builder: (dialogContext) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            return AlertDialog(
              backgroundColor: const Color(0xFF12122A),
              title: Text(
                I18n.t("chat.claimTitle"),
                style: GoogleFonts.poppins(
                  color: Colors.white,
                  fontWeight: FontWeight.w600,
                ),
              ),
              content: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    I18n.t("chat.claimBody"),
                    style: GoogleFonts.poppins(
                      color: Colors.white54,
                      fontSize: 12,
                    ),
                  ),
                  const SizedBox(height: 16),
                  TextField(
                    controller: emailController,
                    style: const TextStyle(color: Colors.white),
                    keyboardType: TextInputType.emailAddress,
                    decoration: InputDecoration(hintText: I18n.t("auth.email")),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: passwordController,
                    style: const TextStyle(color: Colors.white),
                    obscureText: true,
                    decoration: InputDecoration(
                      hintText: I18n.t("chat.pwHint"),
                    ),
                  ),
                  if (errorText != null) ...[
                    const SizedBox(height: 8),
                    Text(
                      errorText!,
                      style: const TextStyle(
                        color: Colors.redAccent,
                        fontSize: 12,
                      ),
                    ),
                  ],
                ],
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.of(dialogContext).pop(),
                  child: Text(I18n.t("common.cancel")),
                ),
                ElevatedButton(
                  onPressed: () async {
                    final email = emailController.text.trim();
                    final password = passwordController.text.trim();
                    if (email.isEmpty || password.length < 6) {
                      setDialogState(() {
                        errorText = I18n.t("chat.claimInvalid");
                      });
                      return;
                    }
                    try {
                      await AuthService().claimAccount(
                        widget.token,
                        email,
                        password,
                      );
                      if (!dialogContext.mounted) return;
                      Navigator.of(dialogContext).pop();
                      if (!mounted) return;
                      setState(() => _isAnonymous = false);
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(content: Text(I18n.t("chat.accountSaved"))),
                      );
                    } on DioException catch (e) {
                      final detail = (e.response?.data is Map)
                          ? (e.response?.data["detail"]?.toString() ??
                                "Bir hata oluştu.")
                          : "Bir hata oluştu.";
                      setDialogState(() => errorText = detail);
                    } catch (e) {
                      setDialogState(() => errorText = "Bir hata oluştu.");
                    }
                  },
                  child: Text(I18n.t("chat.save")),
                ),
              ],
            );
          },
        );
      },
    );
  }

  /// Giris cubugundaki "+" butonu - galeri / kamera / PDF secenegi sunar.
  void _showAttachSheet() {
    showModalBottomSheet(
      context: context,
      backgroundColor: const Color(0xFF12122A),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (sheetContext) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(height: 12),
            Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: Colors.white24,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const SizedBox(height: 8),
            _attachTile(
              sheetContext,
              Icons.photo_library_outlined,
              I18n.t("chat.attachGallery"),
              _pickImageFromGallery,
            ),
            _attachTile(
              sheetContext,
              Icons.photo_camera_outlined,
              I18n.t("chat.attachCamera"),
              _pickImageFromCamera,
            ),
            _attachTile(
              sheetContext,
              Icons.picture_as_pdf_outlined,
              I18n.t("chat.attachPdf"),
              _pickPdf,
            ),
            const SizedBox(height: 12),
          ],
        ),
      ),
    );
  }

  /// Bir Aura yanitina uzun basildiginda acilir - 👍/👎 (2026-09-06,
  /// "insan testleri + kendini gelistirme motoru"). "Menusuz" felsefeye
  /// uygun: her balonda gorunen ikon YOK, sadece uzun basinca cikan
  /// kucuk bir sayfa.
  void _showFeedbackSheet(Message message) {
    showModalBottomSheet(
      context: context,
      backgroundColor: const Color(0xFF12122A),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (sheetContext) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(height: 14),
            Text(
              I18n.t("chat.feedbackQ"),
              style: GoogleFonts.poppins(
                color: Colors.white70,
                fontSize: 14,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              I18n.t("chat.feedbackHelp"),
              style: GoogleFonts.poppins(color: Colors.white38, fontSize: 12),
            ),
            const SizedBox(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                _feedbackButton(
                  sheetContext,
                  message,
                  "up",
                  Icons.thumb_up_alt_rounded,
                  I18n.t("chat.feedbackGood"),
                ),
                const SizedBox(width: 20),
                _feedbackButton(
                  sheetContext,
                  message,
                  "down",
                  Icons.thumb_down_alt_rounded,
                  I18n.t("chat.feedbackBad"),
                ),
              ],
            ),
            const SizedBox(height: 16),
          ],
        ),
      ),
    );
  }

  Widget _feedbackButton(
    BuildContext sheetContext,
    Message message,
    String rating,
    IconData icon,
    String label,
  ) {
    return Semantics(
      button: true,
      label: label == I18n.t("chat.feedbackGood")
          ? I18n.t("chat.a11yMarkGood")
          : I18n.t("chat.a11yMarkBad"),
      child: ExcludeSemantics(
        child: GestureDetector(
          onTap: () {
            Navigator.pop(sheetContext);
            ref
                .read(chatProvider.notifier)
                .sendReplyFeedback(message.id, rating);
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(
                  I18n.t("chat.feedbackThanks"),
                  style: GoogleFonts.poppins(),
                ),
                duration: const Duration(seconds: 2),
              ),
            );
          },
          child: Container(
            width: 96,
            padding: const EdgeInsets.symmetric(vertical: 16),
            decoration: BoxDecoration(
              color: _indigoColor.withValues(alpha: 0.12),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: _indigoColor.withValues(alpha: 0.35)),
            ),
            child: Column(
              children: [
                Icon(icon, color: _indigoColor, size: 24),
                const SizedBox(height: 6),
                Text(
                  label,
                  style: GoogleFonts.poppins(
                    color: Colors.white70,
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _attachTile(
    BuildContext sheetContext,
    IconData icon,
    String label,
    VoidCallback onTap,
  ) {
    return ListTile(
      leading: Icon(icon, color: _indigoColor),
      title: Text(
        label,
        style: GoogleFonts.poppins(color: Colors.white70, fontSize: 15),
      ),
      onTap: () {
        Navigator.pop(sheetContext);
        onTap();
      },
    );
  }

  /// Masaustu (Windows/Linux/macOS) - orada image_picker'in galeri destegi
  /// guvenilmez ve kamera hic yok. Web + mobilde (iOS/Android) image_picker
  /// hem galeri hem kamera icin sorunsuz - iOS Safari'de bile native
  /// "Fotograf / Kamera" sayfasini acar. file_picker ise tam tersi: web'de
  /// FileType.custom galeri secimi iOS Safari'de "secilemedi" veriyordu.
  bool get _isDesktop =>
      !kIsWeb &&
      (defaultTargetPlatform == TargetPlatform.windows ||
          defaultTargetPlatform == TargetPlatform.linux ||
          defaultTargetPlatform == TargetPlatform.macOS);

  Future<void> _sendPickedImage(Uint8List bytes, String name) async {
    if (bytes.length > 11 * 1024 * 1024) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            I18n.t("chat.photoTooBig"),
            style: GoogleFonts.poppins(),
          ),
        ),
      );
      return;
    }
    final n = name.toLowerCase();
    final mime = n.endsWith(".png")
        ? "image/png"
        : n.endsWith(".webp")
        ? "image/webp"
        : "image/jpeg";
    await ref
        .read(chatProvider.notifier)
        .sendFileForAnalysis(bytes, mimeType: mime);
    _scrollToBottom();
  }

  Future<void> _pickImageFromGallery() async {
    try {
      if (_isDesktop) {
        final files = await FilePicker.pickFiles(
          type: FileType.custom,
          allowedExtensions: ["jpg", "jpeg", "png", "webp"],
        );
        if (files.isEmpty) return;
        await _sendPickedImage(
          await files.first.readAsBytes(),
          files.first.name,
        );
      } else {
        final picked = await ImagePicker().pickImage(
          source: ImageSource.gallery,
          imageQuality: 85,
        );
        if (picked == null) return;
        await _sendPickedImage(await picked.readAsBytes(), picked.name);
      }
    } catch (e) {
      debugPrint("Fotograf secme hatasi: $e");
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            I18n.t("chat.photoPickFailed"),
            style: GoogleFonts.poppins(),
          ),
        ),
      );
    }
  }

  /// Kamera: sadece image_picker'da var, mobil/web'de calisir. Masaustunde
  /// desteklenmez - kullaniciya anlasilir bir mesaj verilir.
  Future<void> _pickImageFromCamera() async {
    if (_isDesktop) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            I18n.t("chat.cameraUnavailable"),
            style: GoogleFonts.poppins(),
          ),
        ),
      );
      return;
    }
    try {
      final picked = await ImagePicker().pickImage(
        source: ImageSource.camera,
        imageQuality: 85,
      );
      if (picked == null) return;
      await _sendPickedImage(await picked.readAsBytes(), picked.name);
    } catch (e) {
      debugPrint("Kamera hatasi: $e");
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            I18n.t("chat.cameraFailed"),
            style: GoogleFonts.poppins(),
          ),
        ),
      );
    }
  }

  Future<void> _pickPdf() async {
    try {
      final files = await FilePicker.pickFiles(
        type: FileType.custom,
        allowedExtensions: ["pdf"],
      );
      if (files.isEmpty) return;
      final file = files.first;
      final bytes = await file.readAsBytes();
      // ~11MB ham (backend base64 siniri ~15MB) - buyuk PDF'i erkenden ele.
      if (bytes.length > 11 * 1024 * 1024) {
        if (!mounted) return;
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              I18n.t("chat.pdfTooBig"),
              style: GoogleFonts.poppins(),
            ),
          ),
        );
        return;
      }
      await ref
          .read(chatProvider.notifier)
          .sendFileForAnalysis(
            bytes,
            mimeType: "application/pdf",
            fileName: file.name,
          );
      _scrollToBottom();
    } catch (e) {
      debugPrint("PDF secme hatasi: $e");
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
            I18n.t("chat.pdfPickFailed"),
            style: GoogleFonts.poppins(),
          ),
        ),
      );
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  void _send() {
    final text = _controller.text.trim();
    if (text.isEmpty) return;
    _controller.clear();
    // KOD INCELEMESI BULGUSU: bu mesaj yeni bir hatirlatma cikarabilir
    // (bkz. aura_reminders.py) - yaniti bekleyip hatirlatmalari yeniden
    // senkronize ediyoruz ki yerel bildirim uygulama yeniden acilana
    // kadar beklemeden hemen zamanlansin.
    ref
        .read(chatProvider.notifier)
        .sendMessage(text)
        .then((_) => _syncReminders());
  }

  Widget _buildMessageBubble(dynamic message) {
    final isUser = message is Message
        ? message.isUser
        : message["role"] == "user";
    final text = message is Message ? message.text : message["text"] as String;
    final imageBytes = message is Message ? message.imageBytes : null;
    final fileName = message is Message ? message.fileName : null;
    final animateIn = message is Message ? message.animateIn : false;
    final hasAttachment = imageBytes != null || fileName != null;

    if (isUser) {
      return Container(
        constraints: const BoxConstraints(maxWidth: 280),
        padding: hasAttachment
            ? const EdgeInsets.all(6)
            : const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: [_userBubbleStart, _userBubbleEnd],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
          borderRadius: const BorderRadius.only(
            topLeft: Radius.circular(20),
            topRight: Radius.circular(20),
            bottomLeft: Radius.circular(20),
            bottomRight: Radius.circular(4),
          ),
          boxShadow: [
            BoxShadow(
              color: _indigoColor.withValues(alpha: 0.3),
              blurRadius: 12,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.end,
          mainAxisSize: MainAxisSize.min,
          children: [
            if (imageBytes != null)
              Semantics(
                image: true,
                label: I18n.t("chat.a11ySentPhoto"),
                child: AuraImageReveal(
                  play: animateIn,
                  borderRadius: BorderRadius.circular(16),
                  child: Image.memory(
                    imageBytes,
                    fit: BoxFit.cover,
                    height: 180,
                  ),
                ),
              ),
            if (fileName != null)
              Semantics(
                label: "${I18n.t("chat.a11ySentPdf")}: $fileName",
                child: AuraImageReveal(
                  play: animateIn,
                  borderRadius: BorderRadius.circular(14),
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 14,
                      vertical: 12,
                    ),
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(14),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(
                          Icons.picture_as_pdf_outlined,
                          color: Colors.white,
                          size: 22,
                        ),
                        const SizedBox(width: 10),
                        Flexible(
                          child: Text(
                            fileName,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: GoogleFonts.poppins(
                              color: Colors.white,
                              fontSize: 13,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            if (text.isNotEmpty)
              Padding(
                padding: EdgeInsets.only(
                  top: hasAttachment ? 8 : 0,
                  left: 10,
                  right: 10,
                ),
                child: SelectableText(
                  text,
                  style: GoogleFonts.poppins(
                    color: Colors.white,
                    fontSize: 14,
                    height: 1.5,
                  ),
                ),
              ),
          ],
        ),
      );
    }

    return ClipRRect(
      borderRadius: const BorderRadius.only(
        topLeft: Radius.circular(4),
        topRight: Radius.circular(20),
        bottomLeft: Radius.circular(20),
        bottomRight: Radius.circular(20),
      ),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
        child: Container(
          constraints: const BoxConstraints(maxWidth: 300),
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: 0.07),
            borderRadius: const BorderRadius.only(
              topLeft: Radius.circular(4),
              topRight: Radius.circular(20),
              bottomLeft: Radius.circular(20),
              bottomRight: Radius.circular(20),
            ),
            border: Border.all(
              color: Colors.white.withValues(alpha: 0.12),
              width: 1,
            ),
          ),
          child: SelectableText(
            text,
            style: GoogleFonts.poppins(
              color: Colors.white.withValues(alpha: 0.92),
              fontSize: 14,
              height: 1.5,
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildTypingIndicator() {
    return ClipRRect(
      borderRadius: BorderRadius.circular(16),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: 0.07),
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: Colors.white.withValues(alpha: 0.1)),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: List.generate(3, (i) => _dot(i)),
          ),
        ),
      ),
    );
  }

  Widget _dot(int index) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0.4, end: 1.0),
      duration: Duration(milliseconds: 600 + index * 200),
      curve: Curves.easeInOut,
      builder: (_, value, _) => Container(
        margin: const EdgeInsets.symmetric(horizontal: 3),
        width: 7,
        height: 7,
        decoration: BoxDecoration(
          color: _indigoColor.withValues(alpha: value),
          shape: BoxShape.circle,
        ),
      ),
    );
  }

  /// Giris cubugundaki yuvarlak ikon butonlari - hepsi ayni erisilebilirlik
  /// desenini paylasir: tek bir Semantics dugumu (button + label + tap),
  /// altindaki gorsel agac ekran okuyuculardan gizli. Boylece VoiceOver/
  /// TalkBack "Fotograf ekle, buton" gibi net bir sey soyler (eskiden bu
  /// GestureDetector+Icon'lar okuyucuya HIC gorunmuyordu).
  Widget _circleIconButton({
    required String label,
    required IconData icon,
    required VoidCallback onTap,
    Gradient? gradient,
  }) {
    return Semantics(
      button: true,
      label: label,
      onTap: onTap,
      child: ExcludeSemantics(
        child: GestureDetector(
          onTap: onTap,
          child: Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: gradient,
              color: gradient == null
                  ? _indigoColor.withValues(alpha: 0.15)
                  : null,
              border: gradient == null
                  ? Border.all(
                      color: _indigoColor.withValues(alpha: 0.4),
                      width: 1,
                    )
                  : null,
              boxShadow: gradient != null
                  ? [
                      BoxShadow(
                        color: _indigoColor.withValues(alpha: 0.4),
                        blurRadius: 12,
                        offset: const Offset(0, 4),
                      ),
                    ]
                  : null,
            ),
            child: Icon(
              icon,
              color: gradient != null ? Colors.white : _indigoColor,
              size: 21,
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildInputBar() {
    final callActive = ref.watch(voiceCallProvider).isActive;
    return Container(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 20),
      decoration: BoxDecoration(
        color: const Color(0xFF0A0A1A).withValues(alpha: 0.95),
        border: const Border(
          top: BorderSide(color: Color(0xFF1E1E3A), width: 0.5),
        ),
      ),
      child: Row(
        children: [
          _circleIconButton(
            label: I18n.t("chat.a11yAddPhoto"),
            icon: Icons.add,
            onTap: _showAttachSheet,
          ),
          const SizedBox(width: 6),
          _circleIconButton(
            label: callActive
                ? I18n.t("chat.a11yVoiceEnd")
                : I18n.t("chat.a11yVoiceStart"),
            icon: callActive ? Icons.call_end : Icons.call_outlined,
            onTap: () {
              final callState = ref.read(voiceCallProvider);
              if (callState.isActive) {
                ref.read(voiceCallProvider.notifier).endCall();
              } else {
                _startVoiceCallWithPriming();
              }
            },
          ),
          const SizedBox(width: 6),
          _circleIconButton(
            label: I18n.t("chat.a11yVideoStart"),
            icon: Icons.videocam_outlined,
            onTap: _startVideoCall,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: TextField(
              controller: _controller,
              style: GoogleFonts.poppins(color: Colors.white, fontSize: 14),
              decoration: InputDecoration(hintText: I18n.t("chat.inputHint")),
              onSubmitted: (_) => _send(),
            ),
          ),
          const SizedBox(width: 10),
          _circleIconButton(
            label: I18n.t("chat.send"),
            icon: Icons.send_rounded,
            onTap: _send,
            gradient: const LinearGradient(
              colors: [_userBubbleStart, _userBubbleEnd],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
          ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    // Kod sagligi taramasinda bulundu: _controller/_scrollController/_dio
    // hic dispose/close edilmiyordu - kucuk ama gercek bir memory leak.
    _controller.dispose();
    _scrollController.dispose();
    _dio.close();
    // KOD INCELEMESI BULGUSU (2026-08-27): TtsService.instance paylasilan
    // bir singleton, ekranin kendi omrune bagli degil - bu ekran kapanirken
    // (orn. cikis yapilip login ekranina donulurken) o an calan bir
    // ElevenLabs/yerel TTS sesi durdurulmadan devam edebiliyordu. Servisin
    // KENDISI dispose edilmiyor (baska ekranlar hala kullanabilir), sadece
    // o anki ses durduruluyor.
    unawaited(TtsService.instance.stop());
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final chatState = ref.watch(chatProvider);

    // KULLANICI BULGUSU (2026-09-01): bu ekran (yazili sohbet) HER
    // Aura yanitini otomatik olarak ElevenLabs ile sesli okuyordu -
    // kullanici bunu istemiyor: "sesli okuması ... sadece canlı
    // yayında olan bir özellik olarak kullanılmalı." Sesli okuma artik
    // SADECE gercekten sesle baslatilan akislarda oluyor - Canli
    // gorusme (Gemini Live, kendi sesiyle konusuyor) ve "basili tut
    // konus" yedek modu (voice_call_screen.dart, TtsService.speak
    // orada hala cagriliyor - kullanici zaten mikrofona konustugu icin
    // sesli cevap beklemek dogal). Yazarak sohbet ederken sessiz kalir.
    ref.listen(chatProvider, (previous, next) {
      _scrollToBottom();
    });

    // BULUNDU: canli altyazi metni (liveUserText/liveAssistantText)
    // partial_transcript geldikce GERCEKTEN aninda guncelleniyordu, ama
    // ekran hic asagi kaymiyordu - sadece chatProvider degisince (yani
    // turn_complete ile KALICI mesaj eklendiginde) yukaridaki listener
    // kaydirma yapiyordu. Sonuc: kullanici metnin akmadigini, hepsinin
    // tur bitince BIRDEN goründugunu saniyordu - aslinda akiyordu ama
    // ekranin disinda (kaydirilmamis alanda) akiyordu. Sesli goruşme
    // sirasinda canli metin degistikce de asagi kaydiriyoruz.
    ref.listen(voiceCallProvider, (previous, next) {
      if (next.liveUserText != previous?.liveUserText ||
          next.liveAssistantText != previous?.liveAssistantText) {
        _scrollToBottom();
      }
    });

    return Scaffold(
      backgroundColor: _bgColor,
      extendBodyBehindAppBar: true,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        flexibleSpace: ClipRect(
          child: BackdropFilter(
            filter: ImageFilter.blur(sigmaX: 20, sigmaY: 20),
            child: Container(
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [
                    const Color(0xFF12122A).withValues(alpha: 0.85),
                    const Color(0xFF0A0A1A).withValues(alpha: 0.7),
                  ],
                  begin: Alignment.topCenter,
                  end: Alignment.bottomCenter,
                ),
                border: const Border(
                  bottom: BorderSide(color: Color(0xFF2A2A4A), width: 0.5),
                ),
              ),
            ),
          ),
        ),
        title: Semantics(
          header: true,
          label: I18n.t("chat.online"),
          child: ExcludeSemantics(
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 8,
                  height: 8,
                  decoration: const BoxDecoration(
                    color: Color(0xFF00E676),
                    shape: BoxShape.circle,
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  "Aura",
                  style: GoogleFonts.poppins(
                    color: Colors.white,
                    fontSize: 20,
                    fontWeight: FontWeight.w600,
                    letterSpacing: 1.5,
                  ),
                ),
              ],
            ),
          ),
        ),
        actions: [
          if (_isAnonymous)
            IconButton(
              icon: const Icon(Icons.cloud_outlined, color: Colors.white70),
              onPressed: _showClaimAccountDialog,
              tooltip: I18n.t("chat.saveAccount"),
            ),
          // BULUNDU (kullanici istegi): profil/hafiza yonetimi, gunluk
          // kullanim gorunurlugu ve cikis yapmaya HICBIR erisim yoktu -
          // "menusuz, organik" felsefeye sadik, tek bir dislaiye tikla
          // ayarlar ekranina goturen giris noktasi.
          IconButton(
            icon: const Icon(Icons.settings_outlined, color: Colors.white70),
            tooltip: I18n.t("chat.settings"),
            onPressed: () {
              Navigator.of(context).push(
                MaterialPageRoute(
                  builder: (_) => SettingsScreen(token: widget.token),
                ),
              );
            },
          ),
        ],
      ),
      body: SkyBackground(
        child: Stack(
          children: [
            // "Aura efekti" - mesaj balonlarinin (frosted-glass) ARKASINDA,
            // sohbetin tonuna gore yavasca renk degistiren yumusak hale.
            // Tamamen dekoratif - ekran okuyuculardan gizli.
            ExcludeSemantics(child: AuraHale(mood: chatState.currentMood)),
            Column(
              children: [
                Expanded(child: _buildChatView(chatState)),
                if (chatState.errorMessage != null)
                  Padding(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 16,
                      vertical: 4,
                    ),
                    child: Semantics(
                      liveRegion: true,
                      child: Text(
                        chatState.errorMessage!,
                        style: GoogleFonts.poppins(
                          color: Colors.redAccent,
                          fontSize: 12,
                        ),
                      ),
                    ),
                  ),
                _buildInputBar(),
              ],
            ),
            Positioned(
              top: MediaQuery.of(context).padding.top + kToolbarHeight + 4,
              left: 0,
              right: 0,
              child: const VoiceCallBar(),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildChatView(dynamic chatState) {
    // Sesli goruşme sirasinda, turn_complete'i beklemeden akan canli
    // altyaziyi da (varsa) mesaj listesinin en altina, normal baloncuk
    // gibi ekliyoruz - boylece sesli konusma da yazili sohbetle AYNI
    // ekranda, ayni bicimde goruluyor. turn_complete gelince bu gecici
    // baloncuklar kaybolur, yerlerini kalici mesaj alir.
    final callState = ref.watch(voiceCallProvider);
    final showLiveUser =
        callState.isActive && callState.liveUserText.isNotEmpty;
    final showLiveAssistant =
        callState.isActive && callState.liveAssistantText.isNotEmpty;

    final extraCount =
        (chatState.isLoading && chatState.messages.isNotEmpty ? 1 : 0) +
        (showLiveUser ? 1 : 0) +
        (showLiveAssistant ? 1 : 0);

    return chatState.messages.isEmpty && chatState.isLoading
        ? Center(
            child: CircularProgressIndicator(
              color: _indigoColor.withValues(alpha: 0.7),
            ),
          )
        : ListView.builder(
            controller: _scrollController,
            padding: const EdgeInsets.fromLTRB(16, 100, 16, 16),
            itemCount: chatState.messages.length + extraCount,
            itemBuilder: (context, index) {
              if (index < chatState.messages.length) {
                final message = chatState.messages[index];
                // Aura yanitlari: uzun basinca 👍/👎 (2026-09-06). Bos/
                // ilk-yukleniyor balonlarina (text bos) verme.
                final canRate =
                    !message.isUser && message.text.trim().isNotEmpty;
                return Padding(
                  padding: const EdgeInsets.symmetric(vertical: 6),
                  child: Align(
                    alignment: message.isUser
                        ? Alignment.centerRight
                        : Alignment.centerLeft,
                    child: Column(
                      crossAxisAlignment: message.isUser
                          ? CrossAxisAlignment.end
                          : CrossAxisAlignment.start,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Semantics(
                          container: true,
                          label: message.isUser
                              ? I18n.t("chat.a11yYou")
                              : I18n.t("chat.a11yAura"),
                          child: canRate
                              ? GestureDetector(
                                  onLongPress: () =>
                                      _showFeedbackSheet(message),
                                  child: _buildMessageBubble(message),
                                )
                              : _buildMessageBubble(message),
                        ),
                        if (canRate && message.feedback != null)
                          Padding(
                            padding: const EdgeInsets.only(top: 4, left: 6),
                            child: Icon(
                              message.feedback == "up"
                                  ? Icons.thumb_up_alt_rounded
                                  : Icons.thumb_down_alt_rounded,
                              size: 13,
                              color: _indigoColor.withValues(alpha: 0.6),
                            ),
                          ),
                      ],
                    ),
                  ),
                );
              }

              var extraIndex = index - chatState.messages.length;

              if (showLiveUser) {
                if (extraIndex == 0) {
                  return Padding(
                    padding: const EdgeInsets.symmetric(vertical: 6),
                    child: Align(
                      alignment: Alignment.centerRight,
                      child: Semantics(
                        container: true,
                        liveRegion: true,
                        label: I18n.t("chat.a11ySaid"),
                        child: _buildMessageBubble({
                          "role": "user",
                          "text": callState.liveUserText,
                        }),
                      ),
                    ),
                  );
                }
                extraIndex -= 1;
              }

              if (showLiveAssistant) {
                if (extraIndex == 0) {
                  return Padding(
                    padding: const EdgeInsets.symmetric(vertical: 6),
                    child: Align(
                      alignment: Alignment.centerLeft,
                      child: Semantics(
                        container: true,
                        liveRegion: true,
                        label: I18n.t("chat.a11yAura"),
                        child: _buildMessageBubble({
                          "role": "assistant",
                          "text": callState.liveAssistantText,
                        }),
                      ),
                    ),
                  );
                }
                extraIndex -= 1;
              }

              return Align(
                alignment: Alignment.centerLeft,
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: 8),
                  child: Semantics(
                    label: I18n.t("chat.typing"),
                    liveRegion: true,
                    child: ExcludeSemantics(child: _buildTypingIndicator()),
                  ),
                ),
              );
            },
          );
  }
}
