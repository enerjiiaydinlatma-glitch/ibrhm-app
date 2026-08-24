import "dart:ui";
import "package:dio/dio.dart";
import "package:flutter/material.dart";
import "package:flutter_riverpod/flutter_riverpod.dart";
import "package:google_fonts/google_fonts.dart";
import "../../../services/auth_service.dart";
import "../../chat/screens/auth_screen.dart";

class ProfileScreen extends ConsumerStatefulWidget {
  final String token;
  const ProfileScreen({super.key, required this.token});

  @override
  ConsumerState<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends ConsumerState<ProfileScreen> {
  final _nameController = TextEditingController();
  final _dio = Dio();
  // bkz. friends_screen.dart'taki ayni not - localhost'tan production'a cekildi.
  static const _baseUrl = "https://aura-backend-production-bc9c.up.railway.app";
  static const _indigo = Color(0xFF6C63FF);
  static const _bg = Color(0xFF0A0A1A);

  Map<String, dynamic> _profile = {};
  String _biography = "";
  bool _loading = true;
  bool _bioLoading = false;
  int _selectedAvatar = 0;

  final List<String> _avatarEmojis = ["ğŸŒŸ", "ğŸ”®", "âš¡", "ğŸŒ™", "ğŸ¯", "ğŸ¦‹", "ğŸŒŠ", "ğŸ”¥", "ğŸ’", "ğŸŒ¸"];

  @override
  void initState() {
    super.initState();
    _loadProfile();
  }

  Future<void> _loadProfile() async {
    try {
      final r = await _dio.get("$_baseUrl/api/profile",
          options: Options(headers: {"Authorization": "Bearer ${widget.token}"}));
      setState(() {
        _profile = r.data as Map<String, dynamic>;
        _nameController.text = _profile["name"] ?? "";
        _loading = false;
      });
    } catch (_) {
      setState(() => _loading = false);
    }
  }

  Future<void> _saveProfile() async {
    try {
      await _dio.post(
        "$_baseUrl/api/profile",
        data: {"name": _nameController.text.trim()},
        options: Options(headers: {"Authorization": "Bearer ${widget.token}"}),
      );
      // BULUNDU (kod sagligi taramasi): await sonrasi widget agactan
      // kaldirilmis olabilir - mounted kontrolu olmadan context kullanmak
      // framework assertion hatasina yol acabilir.
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text("Profil kaydedildi", style: GoogleFonts.poppins()),
          backgroundColor: _indigo,
        ),
      );
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text("Profil kaydedilemedi", style: GoogleFonts.poppins()),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  Future<void> _generateBiography() async {
    setState(() => _bioLoading = true);
    try {
      final r = await _dio.post(
        "$_baseUrl/api/chat",
        data: {
          "message":
              "Benim hakkÄ±mda ÅŸimdiye kadar Ã¶ÄŸrendiklerinden yola Ã§Ä±karak, beni tanÄ±mlayan felsefi ve Ã¶zgÃ¼n bir biyografi yaz. 2-3 cÃ¼mle, birinci ÅŸahÄ±s deÄŸil Ã¼Ã§Ã¼ncÃ¼ ÅŸahÄ±s. Åiirsel ama gerÃ§ekÃ§i olsun."
        },
        options: Options(headers: {"Authorization": "Bearer ${widget.token}"}),
      );
      if (!mounted) return;
      setState(() {
        _biography = r.data["reply"] ?? "";
        _bioLoading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _bioLoading = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text("Biyografi oluşturulamadı", style: GoogleFonts.poppins()),
          backgroundColor: Colors.red,
        ),
      );
    }
  }

  Future<void> _logout() async {
    final auth = AuthService();
    await auth.logout(widget.token);
    if (!mounted) return;
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(builder: (_) => const AuthScreen()),
      (_) => false,
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bg,
      extendBodyBehindAppBar: true,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, color: Colors.white70),
          onPressed: () => Navigator.pop(context),
        ),
        title: Text("Profil", style: GoogleFonts.poppins(color: Colors.white, fontWeight: FontWeight.w600)),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout, color: Colors.white70),
            onPressed: _logout,
          ),
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
        child: _loading
            ? const Center(child: CircularProgressIndicator(color: _indigo))
            : SingleChildScrollView(
                padding: const EdgeInsets.fromLTRB(20, 100, 20, 40),
                child: Column(
                  children: [
                    // Avatar
                    GestureDetector(
                      onTap: _showAvatarPicker,
                      child: Container(
                        width: 100,
                        height: 100,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          gradient: const LinearGradient(
                            colors: [Color(0xFF6C63FF), Color(0xFF9C8FFF)],
                          ),
                          boxShadow: [
                            BoxShadow(color: _indigo.withValues(alpha: 0.4), blurRadius: 20, offset: const Offset(0, 8)),
                          ],
                        ),
                        child: Center(
                          child: Text(_avatarEmojis[_selectedAvatar], style: const TextStyle(fontSize: 48)),
                        ),
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text("AvatarÄ±nÄ± seÃ§", style: GoogleFonts.poppins(color: Colors.white38, fontSize: 12)),
                    const SizedBox(height: 24),

                    // Ä°sim
                    _glassCard(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text("Ä°sim", style: GoogleFonts.poppins(color: Colors.white54, fontSize: 12)),
                          const SizedBox(height: 8),
                          TextField(
                            controller: _nameController,
                            style: GoogleFonts.poppins(color: Colors.white, fontSize: 16),
                            decoration: InputDecoration(
                              hintText: "AdÄ±n ne?",
                              hintStyle: GoogleFonts.poppins(color: Colors.white24),
                              border: InputBorder.none,
                            ),
                          ),
                          const SizedBox(height: 8),
                          Text(_profile["email"] ?? "", style: GoogleFonts.poppins(color: Colors.white38, fontSize: 12)),
                        ],
                      ),
                    ),
                    const SizedBox(height: 16),

                    // Aura Biyografisi
                    _glassCard(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Text("Aura Biyografim", style: GoogleFonts.poppins(color: Colors.white54, fontSize: 12)),
                              const Spacer(),
                              GestureDetector(
                                onTap: _generateBiography,
                                child: Container(
                                  padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                                  decoration: BoxDecoration(
                                    color: _indigo.withValues(alpha: 0.2),
                                    borderRadius: BorderRadius.circular(12),
                                    border: Border.all(color: _indigo.withValues(alpha: 0.4)),
                                  ),
                                  child: _bioLoading
                                      ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: _indigo))
                                      : Text("âœ¨ Ãœret", style: GoogleFonts.poppins(color: _indigo, fontSize: 12)),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 12),
                          _biography.isEmpty
                              ? Text(
                                  "Aura seni tanÄ±dÄ±kÃ§a burada seni anlatan Ã¶zgÃ¼n bir biyografi Ã¼retecek.",
                                  style: GoogleFonts.poppins(color: Colors.white24, fontSize: 13, fontStyle: FontStyle.italic),
                                )
                              : Text(_biography, style: GoogleFonts.poppins(color: Colors.white.withValues(alpha: 0.85), fontSize: 14, height: 1.6)),
                        ],
                      ),
                    ),
                    const SizedBox(height: 24),

                    // Kaydet
                    SizedBox(
                      width: double.infinity,
                      height: 52,
                      child: GestureDetector(
                        onTap: _saveProfile,
                        child: Container(
                          decoration: BoxDecoration(
                            gradient: const LinearGradient(
                              colors: [Color(0xFF6C63FF), Color(0xFF9C8FFF)],
                            ),
                            borderRadius: BorderRadius.circular(16),
                            boxShadow: [
                              BoxShadow(color: _indigo.withValues(alpha: 0.4), blurRadius: 12, offset: const Offset(0, 4)),
                            ],
                          ),
                          child: Center(
                            child: Text("Kaydet", style: GoogleFonts.poppins(color: Colors.white, fontWeight: FontWeight.w600, fontSize: 16)),
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
              ),
      ),
    );
  }

  Widget _glassCard({required Widget child}) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(20),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 10, sigmaY: 10),
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: 0.06),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: Colors.white.withValues(alpha: 0.1)),
          ),
          child: child,
        ),
      ),
    );
  }

  void _showAvatarPicker() {
    showModalBottomSheet(
      context: context,
      backgroundColor: const Color(0xFF12122A),
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(24))),
      builder: (_) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text("Avatar SeÃ§", style: GoogleFonts.poppins(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w600)),
              const SizedBox(height: 20),
              Wrap(
                spacing: 16,
                runSpacing: 16,
                children: List.generate(_avatarEmojis.length, (i) {
                  return GestureDetector(
                    onTap: () {
                      setState(() => _selectedAvatar = i);
                      Navigator.pop(context);
                    },
                    child: Container(
                      width: 56,
                      height: 56,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: _selectedAvatar == i ? _indigo.withValues(alpha: 0.3) : Colors.white.withValues(alpha: 0.05),
                        border: Border.all(color: _selectedAvatar == i ? _indigo : Colors.white12),
                      ),
                      child: Center(child: Text(_avatarEmojis[i], style: const TextStyle(fontSize: 28))),
                    ),
                  );
                }),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
