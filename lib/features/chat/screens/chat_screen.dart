import "dart:typed_data";
import "dart:ui";
import "package:dio/dio.dart";
import "package:flutter/material.dart";
import "package:flutter_riverpod/flutter_riverpod.dart";
import "package:google_fonts/google_fonts.dart";
import "package:speech_to_text/speech_to_text.dart" as stt;
import "package:audioplayers/audioplayers.dart";
import "package:image_picker/image_picker.dart";
import "../notifier/chat_notifier.dart";
import "../models/message.dart";
import "../../voice/screens/voice_call_screen.dart";
import "../../voice/notifier/voice_call_notifier.dart";

class ChatScreen extends ConsumerStatefulWidget {
  final String token;
  const ChatScreen({super.key, required this.token});

  @override
  ConsumerState<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends ConsumerState<ChatScreen> {
  final _controller = TextEditingController();
  final _scrollController = ScrollController();
  final stt.SpeechToText _speech = stt.SpeechToText();
  final AudioPlayer _audioPlayer = AudioPlayer();
  final Dio _dio = Dio();

  bool _isListening = false;
  bool _speechAvailable = false;
  String _selectedVoice = "female";

  // Hikaye modu
  bool _storyMode = false;
  List<Map<String, String>> _storyHistory = [];
  bool _storyLoading = false;

  static const String _backendUrl = "https://aura-backend-production-bc9c.up.railway.app";
  static const Color _bgColor = Color(0xFF0A0A1A);
  static const Color _indigoColor = Color(0xFF6C63FF);
  static const Color _userBubbleStart = Color(0xFF6C63FF);
  static const Color _userBubbleEnd = Color(0xFF9C8FFF);

  @override
  void initState() {
    super.initState();
    _initSpeech();
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      final notifier = ref.read(chatProvider.notifier);
      notifier.setToken(widget.token);
      await notifier.loadHistory();
      await notifier.fetchGreeting();
    });
  }

  Future<void> _initSpeech() async {
    _speechAvailable = await _speech.initialize(
      onStatus: (status) {
        if (status == "done" || status == "notListening") {
          setState(() => _isListening = false);
        }
      },
      onError: (error) => setState(() => _isListening = false),
    );
    setState(() {});
  }

  String _cleanForSpeech(String text) {
    final emojiPattern = RegExp(
      r"[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{2190}-\u{21FF}\u{2B00}-\u{2BFF}\u{FE0F}]",
      unicode: true,
    );
    return text
        .replaceAll(emojiPattern, "")
        .replaceAll(RegExp(r"\*\*"), "")
        .replaceAll(RegExp(r"#+\s*"), "")
        .trim();
  }

  Future<void> _speakWithElevenLabs(String text) async {
    final cleanText = _cleanForSpeech(text);
    if (cleanText.isEmpty) return;
    try {
      final response = await _dio.post<List<int>>(
        "$_backendUrl/api/tts",
        data: {"text": cleanText, "voice": _selectedVoice},
        options: Options(responseType: ResponseType.bytes),
      );
      if (response.data != null) {
        await _audioPlayer.stop();
        await _audioPlayer.play(
          BytesSource(Uint8List.fromList(response.data!)),
        );
      }
    } catch (e) {
      debugPrint("ElevenLabs TTS hatasi: $e");
    }
  }

  Future<void> _pickAndAnalyzeImage() async {
    try {
      final picked = await ImagePicker().pickImage(
        source: ImageSource.gallery,
        imageQuality: 85,
      );
      if (picked == null) return;

      final bytes = await picked.readAsBytes();

      await ref.read(chatProvider.notifier).sendImageForAnalysis(bytes);
      _scrollToBottom();
    } catch (e) {
      debugPrint("Fotograf secme hatasi: $e");
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text("Fotoğraf seçilemedi.", style: GoogleFonts.poppins())),
      );
    }
  }

  Future<void> _startStory() async {
    setState(() {
      _storyMode = true;
      _storyHistory = [];
      _storyLoading = true;
    });

    try {
      final response = await _dio.post(
        "$_backendUrl/api/story",
        data: {"action": "", "history": []},
      );
      final text = response.data["continuation"] ?? "";
      setState(() {
        _storyHistory = [{"role": "assistant", "text": text}];
        _storyLoading = false;
      });
      _speakWithElevenLabs(text);
      _scrollToBottom();
    } catch (e) {
      setState(() => _storyLoading = false);
    }
  }

  Future<void> _continueStory(String action) async {
    if (action.trim().isEmpty) return;
    setState(() {
      _storyHistory.add({"role": "user", "text": action});
      _storyLoading = true;
    });

    try {
      final response = await _dio.post(
        "$_backendUrl/api/story",
        data: {
          "action": action,
          "history": _storyHistory.sublist(0, _storyHistory.length - 1),
        },
      );
      final text = response.data["continuation"] ?? "";
      setState(() {
        _storyHistory.add({"role": "assistant", "text": text});
        _storyLoading = false;
      });
      _speakWithElevenLabs(text);
      _scrollToBottom();
    } catch (e) {
      setState(() => _storyLoading = false);
    }
  }

  void _exitStory() {
    setState(() {
      _storyMode = false;
      _storyHistory = [];
    });
  }

  void _toggleListening() async {
    if (!_speechAvailable) {
      await _initSpeech();
      if (!_speechAvailable) return;
    }
    if (_isListening) {
      await _speech.stop();
      setState(() => _isListening = false);
      return;
    }
    setState(() => _isListening = true);
    await _speech.listen(
      localeId: "tr_TR",
      onResult: (result) {
        setState(() {
          _controller.text = result.recognizedWords;
          _controller.selection = TextSelection.fromPosition(
            TextPosition(offset: _controller.text.length),
          );
        });
      },
    );
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
    if (_storyMode) {
      _continueStory(text);
    } else {
      ref.read(chatProvider.notifier).sendMessage(text);
    }
  }

  void _showVoiceSelector() {
    showModalBottomSheet(
      context: context,
      backgroundColor: const Color(0xFF12122A),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (_) => SafeArea(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(height: 12),
            Container(
              width: 40, height: 4,
              decoration: BoxDecoration(
                color: Colors.white24,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(20),
              child: Text("Aura Sesi",
                style: GoogleFonts.poppins(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w600)),
            ),
            _voiceTile("female", "KadÄ±n Ses", Icons.face),
            _voiceTile("male", "Erkek Ses", Icons.face_3),
            const SizedBox(height: 16),
          ],
        ),
      ),
    );
  }

  Widget _voiceTile(String voice, String label, IconData icon) {
    final selected = _selectedVoice == voice;
    return ListTile(
      leading: Icon(icon, color: selected ? _indigoColor : Colors.white54),
      title: Text(label, style: GoogleFonts.poppins(
        color: selected ? _indigoColor : Colors.white70,
        fontWeight: selected ? FontWeight.w600 : FontWeight.normal,
      )),
      trailing: selected ? const Icon(Icons.check_circle, color: _indigoColor) : null,
      onTap: () {
        setState(() => _selectedVoice = voice);
        Navigator.pop(context);
      },
    );
  }

  Widget _buildMessageBubble(dynamic message) {
    final isUser = message is Message ? message.isUser : message["role"] == "user";
    final text = message is Message ? message.text : message["text"] as String;
    final imageBytes = message is Message ? message.imageBytes : null;

    if (isUser) {
      return Container(
        constraints: const BoxConstraints(maxWidth: 280),
        padding: imageBytes != null
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
            BoxShadow(color: _indigoColor.withValues(alpha: 0.3), blurRadius: 12, offset: const Offset(0, 4)),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.end,
          mainAxisSize: MainAxisSize.min,
          children: [
            if (imageBytes != null)
              ClipRRect(
                borderRadius: BorderRadius.circular(16),
                child: Image.memory(
                  imageBytes,
                  fit: BoxFit.cover,
                  height: 180,
                ),
              ),
            if (text.isNotEmpty)
              Padding(
                padding: EdgeInsets.only(top: imageBytes != null ? 8 : 0, left: 10, right: 10),
                child: Text(text, style: GoogleFonts.poppins(color: Colors.white, fontSize: 14, height: 1.5)),
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
            border: Border.all(color: Colors.white.withValues(alpha: 0.12), width: 1),
          ),
          child: Text(text, style: GoogleFonts.poppins(
            color: Colors.white.withValues(alpha: 0.92), fontSize: 14, height: 1.5)),
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
      builder: (_, value, __) => Container(
        margin: const EdgeInsets.symmetric(horizontal: 3),
        width: 7, height: 7,
        decoration: BoxDecoration(
          color: _indigoColor.withValues(alpha: value),
          shape: BoxShape.circle,
        ),
      ),
    );
  }

  Widget _buildInputBar() {
    return Container(
      padding: const EdgeInsets.fromLTRB(12, 8, 12, 20),
      decoration: BoxDecoration(
        color: const Color(0xFF0A0A1A).withValues(alpha: 0.95),
        border: const Border(top: BorderSide(color: Color(0xFF1E1E3A), width: 0.5)),
      ),
      child: Row(
        children: [
          GestureDetector(
            onTap: _toggleListening,
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              width: 44, height: 44,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: _isListening ? Colors.red.withValues(alpha: 0.2) : _indigoColor.withValues(alpha: 0.15),
                border: Border.all(
                  color: _isListening ? Colors.red : _indigoColor.withValues(alpha: 0.4),
                  width: 1,
                ),
              ),
              child: Icon(
                _isListening ? Icons.mic : Icons.mic_none,
                color: _isListening ? Colors.red : _indigoColor,
                size: 20,
              ),
            ),
          ),
          if (!_storyMode) ...[
            const SizedBox(width: 6),
            GestureDetector(
              onTap: _pickAndAnalyzeImage,
              child: Container(
                width: 44, height: 44,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: _indigoColor.withValues(alpha: 0.15),
                  border: Border.all(color: _indigoColor.withValues(alpha: 0.4), width: 1),
                ),
                child: Icon(Icons.image_outlined, color: _indigoColor, size: 20),
              ),
            ),
            const SizedBox(width: 6),
            GestureDetector(
              onTap: () {
                final callState = ref.read(voiceCallProvider);
                if (callState.isActive) {
                  ref.read(voiceCallProvider.notifier).endCall();
                } else {
                  ref.read(voiceCallProvider.notifier).startCall(widget.token);
                }
              },
              child: Container(
                width: 44, height: 44,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: _indigoColor.withValues(alpha: 0.15),
                  border: Border.all(color: _indigoColor.withValues(alpha: 0.4), width: 1),
                ),
                child: Icon(Icons.call_outlined, color: _indigoColor, size: 20),
              ),
            ),
          ],
          const SizedBox(width: 10),
          Expanded(
            child: TextField(
              controller: _controller,
              style: GoogleFonts.poppins(color: Colors.white, fontSize: 14),
              decoration: InputDecoration(
                hintText: _storyMode ? "Hikayeyi yÃ¶nlendir..." : "Mesaj yaz...",
              ),
              onSubmitted: (_) => _send(),
            ),
          ),
          const SizedBox(width: 10),
          GestureDetector(
            onTap: _send,
            child: Container(
              width: 44, height: 44,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: const LinearGradient(
                  colors: [_userBubbleStart, _userBubbleEnd],
                  begin: Alignment.topLeft,
                  end: Alignment.bottomRight,
                ),
                boxShadow: [
                  BoxShadow(color: _indigoColor.withValues(alpha: 0.4), blurRadius: 12, offset: const Offset(0, 4)),
                ],
              ),
              child: const Icon(Icons.send_rounded, color: Colors.white, size: 20),
            ),
          ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    _speech.stop();
    _audioPlayer.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final chatState = ref.watch(chatProvider);

    ref.listen(chatProvider, (previous, next) {
      _scrollToBottom();
      final justFinished = (previous?.isLoading ?? false) && !next.isLoading;
      if (justFinished && next.messages.isNotEmpty) {
        final lastMessage = next.messages.last;
        if (!lastMessage.isUser && lastMessage.text.isNotEmpty) {
          _speakWithElevenLabs(lastMessage.text);
        }
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
        title: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (_storyMode)
              const Icon(Icons.auto_stories, color: Color(0xFFFFD700), size: 16)
            else
              Container(
                width: 8, height: 8,
                decoration: const BoxDecoration(color: Color(0xFF00E676), shape: BoxShape.circle),
              ),
            const SizedBox(width: 8),
            Text(
              _storyMode ? "Hikaye Modu" : "Aura",
              style: GoogleFonts.poppins(
                color: Colors.white, fontSize: 20,
                fontWeight: FontWeight.w600, letterSpacing: 1.5,
              ),
            ),
          ],
        ),
        actions: [
          if (_storyMode)
            IconButton(
              icon: const Icon(Icons.close, color: Colors.white70),
              onPressed: _exitStory,
              tooltip: "Hikayeden Ã‡Ä±k",
            )
          else ...[
            IconButton(
              icon: const Icon(Icons.auto_stories_outlined, color: Colors.white70),
              onPressed: _startStory,
              tooltip: "Hikaye BaÅŸlat",
            ),
            IconButton(
              icon: const Icon(Icons.record_voice_over_outlined, color: Colors.white70),
              onPressed: _showVoiceSelector,
              tooltip: "Ses SeÃ§",
            ),
          ],
        ],
      ),
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            colors: [Color(0xFF0A0A1A), Color(0xFF0D0B2A), Color(0xFF0A0A1A)],
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
          ),
        ),
        child: Stack(
          children: [
            Column(
              children: [
                Expanded(
                  child: _storyMode
                      ? _buildStoryView()
                      : _buildChatView(chatState),
                ),
                if (!_storyMode && chatState.errorMessage != null)
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                    child: Text(
                      chatState.errorMessage!,
                      style: GoogleFonts.poppins(color: Colors.redAccent, fontSize: 12),
                    ),
                  ),
                _buildInputBar(),
              ],
            ),
            if (!_storyMode)
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
    return chatState.messages.isEmpty && chatState.isLoading
        ? Center(child: CircularProgressIndicator(color: _indigoColor.withValues(alpha: 0.7)))
        : ListView.builder(
            controller: _scrollController,
            padding: const EdgeInsets.fromLTRB(16, 100, 16, 16),
            itemCount: chatState.messages.length +
                (chatState.isLoading && chatState.messages.isNotEmpty ? 1 : 0),
            itemBuilder: (context, index) {
              if (index == chatState.messages.length) {
                return Align(
                  alignment: Alignment.centerLeft,
                  child: Padding(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    child: _buildTypingIndicator(),
                  ),
                );
              }
              final message = chatState.messages[index];
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 6),
                child: Align(
                  alignment: message.isUser ? Alignment.centerRight : Alignment.centerLeft,
                  child: _buildMessageBubble(message),
                ),
              );
            },
          );
  }

  Widget _buildStoryView() {
    if (_storyLoading && _storyHistory.isEmpty) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            CircularProgressIndicator(color: _indigoColor.withValues(alpha: 0.7)),
            const SizedBox(height: 16),
            Text("Hikaye baÅŸlÄ±yor...",
              style: GoogleFonts.poppins(color: Colors.white54, fontSize: 14)),
          ],
        ),
      );
    }

    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.fromLTRB(16, 100, 16, 16),
      itemCount: _storyHistory.length + (_storyLoading ? 1 : 0),
      itemBuilder: (context, index) {
        if (index == _storyHistory.length) {
          return Align(
            alignment: Alignment.centerLeft,
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: _buildTypingIndicator(),
            ),
          );
        }
        final msg = _storyHistory[index];
        return Padding(
          padding: const EdgeInsets.symmetric(vertical: 6),
          child: Align(
            alignment: msg["role"] == "user" ? Alignment.centerRight : Alignment.centerLeft,
            child: _buildMessageBubble(msg),
          ),
        );
      },
    );
  }
}

