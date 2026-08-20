import 'dart:ui';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../../../services/auth_service.dart';
import 'chat_screen.dart';

class AuthScreen extends StatefulWidget {
  const AuthScreen({super.key});

  @override
  State<AuthScreen> createState() => _AuthScreenState();
}

class _AuthScreenState extends State<AuthScreen> {
  @override
  void initState() {
    super.initState();
    _startAnonymousSession();
  }

  Future<void> _startAnonymousSession() async {
    setState(() {
      _loading = true;
    });

    try {
      final token = await _authService.getOrCreateAnonymousToken();

      if (!mounted) return;

      Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) => ChatScreen(token: token),
        ),
      );
    } catch (e) {
      if (!mounted) return;

      setState(() {
        _loading = false;
        _error = 'Aura başlatılamadı.';
      });
    }
  }

  final TextEditingController _emailController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();
  final TextEditingController _nameController = TextEditingController();

  final AuthService _authService = AuthService();

  bool _isLogin = true;
  bool _loading = false;
  String? _error;

  static const Color _bgColor = Color(0xFF0A0A1A);
  static const Color _indigoColor = Color(0xFF6C63FF);

  Future<void> _submit() async {
    final email = _emailController.text.trim();
    final password = _passwordController.text.trim();
    final name = _nameController.text.trim();

    if (email.isEmpty || password.isEmpty) {
      setState(() {
        _error = 'Email ve şifre gerekli.';
      });
      return;
    }

    if (!_isLogin && name.isEmpty) {
      setState(() {
        _error = 'İsim gerekli.';
      });
      return;
    }

    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final Map<String, dynamic> result;

      if (_isLogin) {
        result = await _authService.login(email, password);
      } else {
        result = await _authService.register(
          email,
          password,
          name,
        );
      }

      final tokenValue = result['token'];

      if (tokenValue is! String || tokenValue.isEmpty) {
        throw Exception('Backend token döndürmedi.');
      }

      await _authService.saveToken(tokenValue);

      if (!mounted) return;

      Navigator.of(context).pushReplacement(
        MaterialPageRoute(
          builder: (_) => ChatScreen(token: tokenValue),
        ),
      );
    } on DioException catch (e) {
      String detail = 'Bir hata oluştu.';

      final responseData = e.response?.data;

      if (responseData is Map<String, dynamic>) {
        final serverDetail = responseData['detail'];

        if (serverDetail != null) {
          detail = serverDetail.toString();
        }
      }

      if (mounted) {
        setState(() {
          _error = detail;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _error = 'Bağlantı hatası. Backend çalışıyor mu?';
        });
      }
    } finally {
      if (mounted) {
        setState(() {
          _loading = false;
        });
      }
    }
  }

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    _nameController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bgColor,
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            colors: [
              Color(0xFF0A0A1A),
              Color(0xFF0D0B2A),
              Color(0xFF0A0A1A),
            ],
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
          ),
        ),
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(32),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  'AURA',
                  style: GoogleFonts.poppins(
                    color: Colors.white,
                    fontSize: 42,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 8,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  'Kişisel yapay zeka asistanın',
                  style: GoogleFonts.poppins(
                    color: Colors.white38,
                    fontSize: 14,
                  ),
                ),
                const SizedBox(height: 48),
                ClipRRect(
                  borderRadius: BorderRadius.circular(24),
                  child: BackdropFilter(
                    filter: ImageFilter.blur(
                      sigmaX: 10,
                      sigmaY: 10,
                    ),
                    child: Container(
                      padding: const EdgeInsets.all(28),
                      decoration: BoxDecoration(
                        color: Colors.white.withValues(alpha: 0.05),
                        borderRadius: BorderRadius.circular(24),
                        border: Border.all(
                          color: Colors.white.withValues(alpha: 0.1),
                        ),
                      ),
                      child: Column(
                        children: [
                          Row(
                            children: [
                              Expanded(
                                child: _tabButton(
                                  'Giriş Yap',
                                  _isLogin,
                                  () {
                                    setState(() {
                                      _isLogin = true;
                                      _error = null;
                                    });
                                  },
                                ),
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: _tabButton(
                                  'Kayıt Ol',
                                  !_isLogin,
                                  () {
                                    setState(() {
                                      _isLogin = false;
                                      _error = null;
                                    });
                                  },
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 24),
                          if (!_isLogin) ...[
                            _field(
                              _nameController,
                              'İsmin',
                              Icons.person_outline,
                            ),
                            const SizedBox(height: 16),
                          ],
                          _field(
                            _emailController,
                            'Email',
                            Icons.email_outlined,
                            type: TextInputType.emailAddress,
                          ),
                          const SizedBox(height: 16),
                          _field(
                            _passwordController,
                            'Şifre',
                            Icons.lock_outline,
                            obscure: true,
                          ),
                          if (_error != null) ...[
                            const SizedBox(height: 16),
                            Text(
                              _error!,
                              style: GoogleFonts.poppins(
                                color: Colors.redAccent,
                                fontSize: 13,
                              ),
                              textAlign: TextAlign.center,
                            ),
                          ],
                          const SizedBox(height: 24),
                          SizedBox(
                            width: double.infinity,
                            height: 52,
                            child: _loading
                                ? const Center(
                                    child: CircularProgressIndicator(
                                      color: _indigoColor,
                                    ),
                                  )
                                : GestureDetector(
                                    onTap: _submit,
                                    child: Container(
                                      decoration: BoxDecoration(
                                        gradient: const LinearGradient(
                                          colors: [
                                            Color(0xFF6C63FF),
                                            Color(0xFF9C8FFF),
                                          ],
                                          begin: Alignment.centerLeft,
                                          end: Alignment.centerRight,
                                        ),
                                        borderRadius:
                                            BorderRadius.circular(16),
                                        boxShadow: [
                                          BoxShadow(
                                            color: _indigoColor.withValues(
                                              alpha: 0.4,
                                            ),
                                            blurRadius: 20,
                                            offset: const Offset(0, 8),
                                          ),
                                        ],
                                      ),
                                      child: Center(
                                        child: Text(
                                          _isLogin
                                              ? 'Giriş Yap'
                                              : 'Hesap Oluştur',
                                          style: GoogleFonts.poppins(
                                            color: Colors.white,
                                            fontSize: 16,
                                            fontWeight: FontWeight.w600,
                                          ),
                                        ),
                                      ),
                                    ),
                                  ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _tabButton(
    String label,
    bool active,
    VoidCallback onTap,
  ) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(
          horizontal: 20,
          vertical: 10,
        ),
        decoration: BoxDecoration(
          color: active
              ? _indigoColor.withValues(alpha: 0.2)
              : Colors.transparent,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: active ? _indigoColor : Colors.white12,
          ),
        ),
        child: Center(
          child: Text(
            label,
            style: GoogleFonts.poppins(
              color: active ? Colors.white : Colors.white38,
              fontWeight:
                  active ? FontWeight.w600 : FontWeight.normal,
              fontSize: 14,
            ),
          ),
        ),
      ),
    );
  }

  Widget _field(
    TextEditingController controller,
    String hint,
    IconData icon, {
    bool obscure = false,
    TextInputType type = TextInputType.text,
  }) {
    return TextField(
      controller: controller,
      obscureText: obscure,
      keyboardType: type,
      style: GoogleFonts.poppins(
        color: Colors.white,
        fontSize: 14,
      ),
      onSubmitted: (_) => _submit(),
      decoration: InputDecoration(
        hintText: hint,
        hintStyle: GoogleFonts.poppins(
          color: Colors.white38,
          fontSize: 14,
        ),
        prefixIcon: Icon(
          icon,
          color: Colors.white38,
          size: 20,
        ),
        filled: true,
        fillColor: const Color(0xFF1A1A3A),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide.none,
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: const BorderSide(
            color: Color(0xFF2A2A4A),
          ),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: const BorderSide(
            color: _indigoColor,
            width: 1.5,
          ),
        ),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 16,
          vertical: 14,
        ),
      ),
    );
  }
}