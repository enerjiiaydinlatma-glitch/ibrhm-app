import "package:flutter/material.dart";
import "package:flutter_riverpod/flutter_riverpod.dart";
import "package:speech_to_text/speech_to_text.dart" as stt;
import "package:flutter_tts/flutter_tts.dart";
import "../notifier/chat_notifier.dart";
import "../../settings/screens/settings_screen.dart";

class ChatScreen extends ConsumerStatefulWidget {
  const ChatScreen({super.key});

  @override
  ConsumerState<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends ConsumerState<ChatScreen> {
  final _controller = TextEditingController();
  final _scrollController = ScrollController();
  final stt.SpeechToText _speech = stt.SpeechToText();
  final FlutterTts _tts = FlutterTts();
  bool _isListening = false;
  bool _speechAvailable = false;
  bool _ttsReady = false;
  bool _ttsUnlocked = false;
  int _lastSpokenCount = 0;

  @override
  void initState() {
    super.initState();
    _initSpeech();
    _initTts();
  }

  Future<void> _initSpeech() async {
    _speechAvailable = await _speech.initialize(
      onStatus: (status) {
        if (status == "done" || status == "notListening") {
          setState(() => _isListening = false);
        }
      },
      onError: (error) {
        setState(() => _isListening = false);
      },
    );
    setState(() {});
  }

  Future<void> _initTts() async {
    try {
      await _tts.setLanguage("tr-TR");
      await _tts.setSpeechRate(0.62);
      await _tts.setVolume(1.0);
      await _tts.setPitch(1.0);

      try {
        final voices = await _tts.getVoices as List<dynamic>;
        final trVoices = voices.where((v) {
          final map = Map<String, dynamic>.from(v as Map);
          final locale = (map["locale"] ?? "").toString().toLowerCase();
          return locale.contains("tr");
        }).toList();

        if (trVoices.isNotEmpty) {
          final preferred = trVoices.firstWhere(
            (v) {
              final name = Map<String, dynamic>.from(v as Map)["name"]
                  .toString()
                  .toLowerCase();
              return name.contains("online") ||
                  name.contains("natural") ||
                  name.contains("emel");
            },
            orElse: () => trVoices.first,
          );
          await _tts.setVoice(
            Map<String, String>.from(preferred as Map),
          );
        }
      } catch (e) {
        debugPrint("Ses listesi alinamadi: $e");
      }

      _tts.setErrorHandler((msg) {
        debugPrint("TTS HATASI: $msg");
      });
      _ttsReady = true;
    } catch (e) {
      debugPrint("TTS baslatma hatasi: $e");
      _ttsReady = false;
    }
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

  void _unlockTtsIfNeeded() {
    if (!_ttsUnlocked && _ttsReady) {
      _ttsUnlocked = true;
      _tts.speak(" ");
    }
  }

  void _send() {
    final text = _controller.text;
    if (text.trim().isEmpty) return;
    _unlockTtsIfNeeded();
    ref.read(chatNotifierProvider.notifier).sendMessage(text);
    _controller.clear();
  }

  @override
  void dispose() {
    _speech.stop();
    _tts.stop();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final chatState = ref.watch(chatNotifierProvider);

    ref.listen(chatNotifierProvider, (previous, next) {
      if (previous?.messages.length != next.messages.length) {
        _scrollToBottom();

        if (next.messages.isNotEmpty && next.messages.length > _lastSpokenCount) {
          final lastMessage = next.messages.last;
          if (!lastMessage.isUser && _ttsReady) {
            final cleanText = _cleanForSpeech(lastMessage.text);
            _tts.stop().then((_) => _tts.speak(cleanText));
          }
          _lastSpokenCount = next.messages.length;
        }
      }
    });

    return Scaffold(
      appBar: AppBar(
        title: const Text("Aura"),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings),
            onPressed: () {
              Navigator.of(context).push(
                MaterialPageRoute(builder: (_) => const SettingsScreen()),
              );
            },
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: chatState.messages.isEmpty && chatState.isLoading
                ? const Center(child: CircularProgressIndicator())
                : ListView.builder(
                    controller: _scrollController,
                    padding: const EdgeInsets.all(12),
                    itemCount: chatState.messages.length,
                    itemBuilder: (context, index) {
                      final message = chatState.messages[index];
                      return Align(
                        alignment: message.isUser
                            ? Alignment.centerRight
                            : Alignment.centerLeft,
                        child: Container(
                          margin: const EdgeInsets.symmetric(vertical: 4),
                          padding: const EdgeInsets.all(10),
                          decoration: BoxDecoration(
                            color: message.isUser
                                ? Colors.blue.shade100
                                : Colors.grey.shade200,
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: Text(message.text),
                        ),
                      );
                    },
                  ),
          ),
          if (chatState.isLoading && chatState.messages.isNotEmpty)
            const Padding(
              padding: EdgeInsets.all(8),
              child: CircularProgressIndicator(),
            ),
          if (chatState.errorMessage != null)
            Padding(
              padding: const EdgeInsets.all(8),
              child: Text(
                chatState.errorMessage!,
                style: const TextStyle(color: Colors.red),
              ),
            ),
          Padding(
            padding: const EdgeInsets.all(8),
            child: Row(
              children: [
                IconButton(
                  icon: Icon(
                    _isListening ? Icons.mic : Icons.mic_none,
                    color: _isListening ? Colors.red : null,
                  ),
                  onPressed: () {
                    _unlockTtsIfNeeded();
                    _toggleListening();
                  },
                ),
                Expanded(
                  child: TextField(
                    controller: _controller,
                    decoration: const InputDecoration(
                      hintText: "Mesaj yaz...",
                      border: OutlineInputBorder(),
                    ),
                    onSubmitted: (_) => _send(),
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.send),
                  onPressed: _send,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
