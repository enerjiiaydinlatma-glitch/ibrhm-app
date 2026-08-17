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
  static const _baseUrl = "https://aura-backend-production-bc9c.up.railway.app";
  static const _indigo = Color(0xFF6C63FF);
  static const _bg = Color(0xFF0A0A1A);

  Map<String, dynamic> _profile = {};
  String _biography = "";
  bool _loading = true;
  bool _bioLoading = false;
  int _selectedAvatar = 0;

  final List<String> _avatarEmojis = ["🌟", "🔮", "⚡", "🌙", "🎯", "🦋", "🌊", "🔥", "💎", "🌸"];

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
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text("Profil kaydedildi", style: GoogleFonts.poppins()),
          backgroundColor: _indigo,
        ),
      );
    } catch (_) {}
  }

  Future<void> _generateBiography() async {
    setState(() => _bioLoading = true);
    try {
      final r = await _dio.post(
        "$_baseUrl/api/chat",
        data: {
          "message":
              "Benim hakkımda şimdiye kadar öğrendiklerinden yola çıkarak, beni tanımlayan felsefi ve özgün bir biyografi yaz. 2-3 cümle, birinci şahıs değil üçüncü şahıs. Şiirsel ama gerçekçi olsun."
        },
        options: Options(headers: {"Authorization": "Bearer ${widget.token}"}),
      );
      setState(() {
        _biography = r.data["reply"] ?? "";
        _bioLoading = false;
      });
    } catch (_) {
      setState(() => _bioLoading = false);
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
                            BoxShadow(color: _indigo.withOpacity(0.4), blurRadius: 20, offset: const Offset(0, 8)),
                          ],
                        ),
                        child: Center(
                          child: Text(_avatarEmojis[_selectedAvatar], style: const TextStyle(fontSize: 48)),
                        ),
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text("Avatarını seç", style: GoogleFonts.poppins(color: Colors.white38, fontSize: 12)),
                    const SizedBox(height: 24),

                    // İsim
                    _glassCard(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text("İsim", style: GoogleFonts.poppins(color: Colors.white54, fontSize: 12)),
                          const SizedBox(height: 8),
                          TextField(
                            controller: _nameController,
                            style: GoogleFonts.poppins(color: Colors.white, fontSize: 16),
                            decoration: InputDecoration(
                              hintText: "Adın ne?",
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
                                    color: _indigo.withOpacity(0.2),
                                    borderRadius: BorderRadius.circular(12),
                                    border: Border.all(color: _indigo.withOpacity(0.4)),
                                  ),
                                  child: _bioLoading
                                      ? const SizedBox(width: 16, height: 16, child: CircularProgressIndicator(strokeWidth: 2, color: _indigo))
                                      : Text("✨ Üret", style: GoogleFonts.poppins(color: _indigo, fontSize: 12)),
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 12),
                          _biography.isEmpty
                              ? Text(
                                  "Aura seni tanıdıkça burada seni anlatan özgün bir biyografi üretecek.",
                                  style: GoogleFonts.poppins(color: Colors.white24, fontSize: 13, fontStyle: FontStyle.italic),
                                )
                              : Text(_biography, style: GoogleFonts.poppins(color: Colors.white.withOpacity(0.85), fontSize: 14, height: 1.6)),
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
                              BoxShadow(color: _indigo.withOpacity(0.4), blurRadius: 12, offset: const Offset(0, 4)),
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
            color: Colors.white.withOpacity(0.06),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: Colors.white.withOpacity(0.1)),
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
              Text("Avatar Seç", style: GoogleFonts.poppins(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w600)),
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
                        color: _selectedAvatar == i ? _indigo.withOpacity(0.3) : Colors.white.withOpacity(0.05),
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