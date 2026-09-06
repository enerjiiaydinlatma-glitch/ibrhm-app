import "package:dio/dio.dart";
import "package:flutter/material.dart";
import "package:google_fonts/google_fonts.dart";
import "package:shared_preferences/shared_preferences.dart";
import "package:url_launcher/url_launcher.dart";

import "../../core/i18n.dart";

import "../chat/screens/chat_screen.dart";

const _kBg = Color(0xFF0A0A1A);
const _kCard = Color(0xFF12122A);
const _kIndigo = Color(0xFF6C63FF);
const _kBackend = "https://aura-backend-production-bc9c.up.railway.app";
const _kConsentPrefKey = "consent_accepted_v1";

/// Yayin hazirligi (2026-09-06): sohbete gecmeden once 18+ / Gizlilik +
/// Kullanim Sartlari onami. Bir kez onaylaninca (yerel bayrak + sunucu
/// kaydi) bir daha gosterilmez. ChatScreen'e giden TUM yollar bunun
/// icinden gecirilir (main.dart + auth_screen.dart).
class ConsentGate extends StatefulWidget {
  final String token;
  const ConsentGate({super.key, required this.token});

  @override
  State<ConsentGate> createState() => _ConsentGateState();
}

class _ConsentGateState extends State<ConsentGate> {
  final Dio _dio = Dio(
    BaseOptions(
      connectTimeout: const Duration(seconds: 12),
      receiveTimeout: const Duration(seconds: 15),
    ),
  );
  bool _checking = true;
  bool _needsConsent = false;

  @override
  void initState() {
    super.initState();
    _resolve();
  }

  Future<void> _resolve() async {
    // 1) Yerel bayrak - bu cihazda daha once onaylandiysa hic ag cagrisi yok.
    try {
      final prefs = await SharedPreferences.getInstance();
      if (prefs.getBool(_kConsentPrefKey) ?? false) {
        setState(() => _checking = false);
        return;
      }
    } catch (_) {}
    // 2) Sunucudan sor (baska cihazda onaylanmis olabilir).
    try {
      final r = await _dio.get(
        "$_kBackend/api/auth/me",
        options: Options(headers: {"Authorization": "Bearer ${widget.token}"}),
      );
      final accepted = (r.data is Map) && (r.data["consent_accepted"] == true);
      if (accepted) {
        try {
          (await SharedPreferences.getInstance()).setBool(
            _kConsentPrefKey,
            true,
          );
        } catch (_) {}
        if (mounted) setState(() => _checking = false);
        return;
      }
    } catch (_) {
      // Ag hatasi: onami GOSTER (guvenli taraf) - kullanici kabul edince
      // zaten sunucuya yazilacak.
    }
    if (mounted) {
      setState(() {
        _checking = false;
        _needsConsent = true;
      });
    }
  }

  Future<void> _onAccepted() async {
    try {
      (await SharedPreferences.getInstance()).setBool(_kConsentPrefKey, true);
    } catch (_) {}
    // Ates-et-unut: sunucuya yaz (basarisiz olsa da yerel bayrak yeter,
    // bir sonraki /api/auth/me denemesi tekrar yazdirir - degil, yerel
    // bayrak varken hic sormuyoruz; o yuzden burada bir kez daha deneriz).
    try {
      await _dio.post(
        "$_kBackend/api/auth/consent",
        options: Options(headers: {"Authorization": "Bearer ${widget.token}"}),
      );
    } catch (_) {}
    if (mounted) setState(() => _needsConsent = false);
  }

  @override
  Widget build(BuildContext context) {
    if (_checking) {
      return Scaffold(
        backgroundColor: _kBg,
        body: Center(
          child: Semantics(
            label: I18n.t("common.loading"),
            child: const CircularProgressIndicator(color: _kIndigo),
          ),
        ),
      );
    }
    if (_needsConsent) {
      return ConsentScreen(onAccepted: _onAccepted);
    }
    return ChatScreen(token: widget.token);
  }
}

class ConsentScreen extends StatefulWidget {
  final Future<void> Function() onAccepted;
  const ConsentScreen({super.key, required this.onAccepted});

  @override
  State<ConsentScreen> createState() => _ConsentScreenState();
}

class _ConsentScreenState extends State<ConsentScreen> {
  bool _age = false;
  bool _terms = false;
  bool _submitting = false;

  bool get _canProceed => _age && _terms && !_submitting;

  Future<void> _open(String path) async {
    final uri = Uri.parse("$_kBackend/legal/$path");
    try {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              "${I18n.t("consent.linkFailed")}: $uri",
              style: GoogleFonts.poppins(),
            ),
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _kBg,
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(28),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Semantics(
                  header: true,
                  child: Text(
                    I18n.t("consent.title"),
                    style: GoogleFonts.poppins(
                      color: Colors.white,
                      fontSize: 24,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
                const SizedBox(height: 12),
                Text(
                  I18n.t("consent.blurb"),
                  style: GoogleFonts.poppins(
                    color: Colors.white70,
                    fontSize: 13.5,
                    height: 1.6,
                  ),
                ),
                const SizedBox(height: 22),
                Container(
                  decoration: BoxDecoration(
                    color: _kCard,
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: const Color(0xFF2A2A4A)),
                  ),
                  child: Column(
                    children: [
                      _check(
                        value: _age,
                        onChanged: (v) => setState(() => _age = v ?? false),
                        label: I18n.t("consent.age"),
                      ),
                      const Divider(height: 1, color: Color(0xFF2A2A4A)),
                      _check(
                        value: _terms,
                        onChanged: (v) => setState(() => _terms = v ?? false),
                        labelWidget: Wrap(
                          crossAxisAlignment: WrapCrossAlignment.center,
                          children: [
                            Text(
                              I18n.t("consent.acceptPrefix"),
                              style: GoogleFonts.poppins(
                                color: Colors.white70,
                                fontSize: 13,
                              ),
                            ),
                            _link(I18n.t("consent.privacy"), "privacy"),
                            Text(
                              I18n.t("consent.and"),
                              style: GoogleFonts.poppins(
                                color: Colors.white70,
                                fontSize: 13,
                              ),
                            ),
                            _link(I18n.t("consent.terms"), "terms"),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 10),
                TextButton(
                  onPressed: () => _open("kvkk"),
                  style: TextButton.styleFrom(padding: EdgeInsets.zero),
                  child: Text(
                    I18n.t("consent.kvkk"),
                    style: GoogleFonts.poppins(
                      color: Colors.white38,
                      fontSize: 12,
                    ),
                  ),
                ),
                const SizedBox(height: 18),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: _canProceed
                        ? () async {
                            setState(() => _submitting = true);
                            await widget.onAccepted();
                          }
                        : null,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: _kIndigo,
                      disabledBackgroundColor: _kIndigo.withValues(alpha: 0.3),
                      padding: const EdgeInsets.symmetric(vertical: 15),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(14),
                      ),
                    ),
                    child: _submitting
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : Text(
                            I18n.t("consent.button"),
                            style: GoogleFonts.poppins(
                              color: Colors.white,
                              fontWeight: FontWeight.w600,
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

  Widget _check({
    required bool value,
    required ValueChanged<bool?> onChanged,
    String? label,
    Widget? labelWidget,
  }) {
    return InkWell(
      onTap: () => onChanged(!value),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Checkbox(
              value: value,
              onChanged: onChanged,
              activeColor: _kIndigo,
              side: const BorderSide(color: Colors.white38),
            ),
            Expanded(
              child:
                  labelWidget ??
                  Text(
                    label ?? "",
                    style: GoogleFonts.poppins(
                      color: Colors.white70,
                      fontSize: 13,
                    ),
                  ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _link(String text, String path) {
    return GestureDetector(
      onTap: () => _open(path),
      child: Text(
        text,
        style: GoogleFonts.poppins(
          color: _kIndigo,
          fontSize: 13,
          decoration: TextDecoration.underline,
          decorationColor: _kIndigo,
        ),
      ),
    );
  }
}
