import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';

import '../notifier/profile_notifier.dart';

const _kBgColor = Color(0xFF0A0A1A);
const _kCardColor = Color(0xFF12122A);
const _kIndigoColor = Color(0xFF6C63FF);
const _kBorderColor = Color(0xFF2A2A4A);

/// Kod-kelime ile gizlenen mesajlari gosteren ekran. Bu ekrana gelmeden
/// once zaten LockScreen ile PIN/biyometrik dogrulamasi yapilmis olmali
/// (bkz. settings_screen.dart'taki giris noktasi) - burasi kendi basina
/// ekstra bir dogrulama istemiyor.
class HiddenChatsScreen extends ConsumerStatefulWidget {
  const HiddenChatsScreen({super.key});

  @override
  ConsumerState<HiddenChatsScreen> createState() => _HiddenChatsScreenState();
}

class _HiddenChatsScreenState extends ConsumerState<HiddenChatsScreen> {
  List<Map<String, dynamic>>? _messages;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final messages =
          await ref.read(profileNotifierProvider.notifier).getHiddenHistory();
      if (!mounted) return;
      setState(() => _messages = messages);
    } catch (_) {
      if (!mounted) return;
      setState(() => _error = 'Gizli sohbetler yüklenemedi.');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _kBgColor,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        title: Text('Gizli Sohbetler', style: GoogleFonts.poppins()),
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_error != null) {
      return Center(
        child: Text(_error!, style: GoogleFonts.poppins(color: Colors.white54)),
      );
    }
    if (_messages == null) {
      return const Center(
        child: CircularProgressIndicator(color: _kIndigoColor),
      );
    }
    if (_messages!.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Text(
            'Henüz gizli bir sohbet yok. Kod cümleni tek başına bir mesaj '
            'olarak gönderirsen, o andan sonraki konuşma burada saklanır.',
            textAlign: TextAlign.center,
            style: GoogleFonts.poppins(color: Colors.white38, fontSize: 13),
          ),
        ),
      );
    }
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _messages!.length,
      itemBuilder: (context, i) {
        final msg = _messages![i];
        final isUser = msg['role'] == 'user';
        return Align(
          alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
          child: Container(
            margin: const EdgeInsets.symmetric(vertical: 6),
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            constraints: BoxConstraints(
              maxWidth: MediaQuery.of(context).size.width * 0.75,
            ),
            decoration: BoxDecoration(
              color: isUser ? _kIndigoColor.withValues(alpha: 0.25) : _kCardColor,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: _kBorderColor),
            ),
            child: Text(
              (msg['text'] ?? '').toString(),
              style: GoogleFonts.poppins(color: Colors.white, fontSize: 14),
            ),
          ),
        );
      },
    );
  }
}
