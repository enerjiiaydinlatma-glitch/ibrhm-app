import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';

import '../../../services/app_lock_service.dart';

const _kPinLength = 4;
const _kBgColor = Color(0xFF0A0A1A);
const _kIndigoColor = Color(0xFF6C63FF);

/// Uygulama acilisinda (ve arka plandan donuste) gosterilen kilit ekrani.
/// [onUnlocked] dogru PIN/biyometrik sonrasi cagrilir - navigasyonu
/// cagiran taraf yonetir (bkz. main.dart).
class LockScreen extends StatefulWidget {
  final VoidCallback onUnlocked;
  const LockScreen({super.key, required this.onUnlocked});

  @override
  State<LockScreen> createState() => _LockScreenState();
}

class _LockScreenState extends State<LockScreen> {
  String _entered = '';
  String? _error;
  bool _shaking = false;
  bool _biometricAvailable = false;
  bool _biometricEnabled = false;

  // BASIT KABA-KUVVET FRENI: bir cihaza fiziksel erisimi olan birinin
  // 4 haneli PIN'i (10.000 ihtimal) art arda hizlica denemesini
  // yavaslatir - kalici kilitleme YOK (kullanici kendi cihazinda kendi
  // PIN'ini deniyor, disaridan bir saldirgan varsayimiyla karistirilmamali,
  // amac sadece otomatik/hizli deneme donguisunu kirmak).
  int _wrongAttempts = 0;
  DateTime? _lockedUntil;
  Timer? _tickTimer;

  @override
  void initState() {
    super.initState();
    _checkBiometric();
  }

  @override
  void dispose() {
    _tickTimer?.cancel();
    super.dispose();
  }

  Future<void> _checkBiometric() async {
    final available = await AppLockService.instance.isBiometricAvailable();
    final enabled = await AppLockService.instance.isBiometricEnabled();
    if (!mounted) return;
    setState(() {
      _biometricAvailable = available;
      _biometricEnabled = enabled;
    });
    if (available && enabled) {
      _tryBiometric();
    }
  }

  Future<void> _tryBiometric() async {
    final ok = await AppLockService.instance.authenticateWithBiometrics();
    if (ok && mounted) {
      widget.onUnlocked();
    }
  }

  bool get _isLockedOut =>
      _lockedUntil != null && DateTime.now().isBefore(_lockedUntil!);

  void _onDigit(String digit) {
    if (_isLockedOut) return;
    if (_entered.length >= _kPinLength) return;
    setState(() {
      _entered += digit;
      _error = null;
    });
    if (_entered.length == _kPinLength) {
      _verify();
    }
  }

  void _onBackspace() {
    if (_entered.isEmpty) return;
    setState(() => _entered = _entered.substring(0, _entered.length - 1));
  }

  Future<void> _verify() async {
    final ok = await AppLockService.instance.verifyPin(_entered);
    if (!mounted) return;
    if (ok) {
      widget.onUnlocked();
      return;
    }
    _wrongAttempts++;
    HapticFeedback.mediumImpact();
    setState(() {
      _shaking = true;
      _entered = '';
      _error = 'Yanlış PIN';
      if (_wrongAttempts >= 5) {
        _lockedUntil = DateTime.now().add(const Duration(seconds: 30));
        _error = '5 kez yanlış girdin, 30 saniye bekle';
        _tickTimer?.cancel();
        _tickTimer = Timer.periodic(const Duration(seconds: 1), (t) {
          if (!mounted) return;
          if (!_isLockedOut) {
            t.cancel();
            setState(() {
              _error = null;
              _wrongAttempts = 0;
            });
          } else {
            setState(() {});
          }
        });
      }
    });
    Future.delayed(const Duration(milliseconds: 400), () {
      if (mounted) setState(() => _shaking = false);
    });
  }

  @override
  Widget build(BuildContext context) {
    final remaining = _isLockedOut
        ? _lockedUntil!.difference(DateTime.now()).inSeconds + 1
        : 0;
    return Scaffold(
      backgroundColor: _kBgColor,
      body: SafeArea(
        child: Column(
          children: [
            const Spacer(flex: 2),
            const Icon(Icons.lock_outline, color: _kIndigoColor, size: 40),
            const SizedBox(height: 16),
            Text(
              'Aura kilitli',
              style: GoogleFonts.poppins(
                color: Colors.white,
                fontSize: 20,
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 24),
            AnimatedContainer(
              duration: const Duration(milliseconds: 80),
              transform: Matrix4.translationValues(
                _shaking ? 8 : 0,
                0,
                0,
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: List.generate(_kPinLength, (i) {
                  final filled = i < _entered.length;
                  return Container(
                    margin: const EdgeInsets.symmetric(horizontal: 8),
                    width: 16,
                    height: 16,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: filled ? _kIndigoColor : Colors.transparent,
                      border: Border.all(color: _kIndigoColor, width: 1.5),
                    ),
                  );
                }),
              ),
            ),
            const SizedBox(height: 16),
            SizedBox(
              height: 20,
              child: Text(
                _isLockedOut
                    ? '${_error ?? ""} ($remaining sn)'
                    : (_error ?? ''),
                style: GoogleFonts.poppins(
                  color: Colors.redAccent,
                  fontSize: 13,
                ),
              ),
            ),
            const Spacer(flex: 2),
            _buildKeypad(),
            const SizedBox(height: 12),
            if (_biometricAvailable && _biometricEnabled)
              TextButton.icon(
                onPressed: _isLockedOut ? null : _tryBiometric,
                icon: const Icon(Icons.fingerprint, color: Colors.white54),
                label: Text(
                  'Biyometrik ile aç',
                  style: GoogleFonts.poppins(color: Colors.white54, fontSize: 13),
                ),
              ),
            const Spacer(),
          ],
        ),
      ),
    );
  }

  Widget _buildKeypad() {
    const rows = [
      ['1', '2', '3'],
      ['4', '5', '6'],
      ['7', '8', '9'],
      ['', '0', '⌫'],
    ];
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: rows.map((row) {
        return Padding(
          padding: const EdgeInsets.symmetric(vertical: 6),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: row.map((key) {
              if (key.isEmpty) {
                return const SizedBox(width: 72, height: 60);
              }
              return SizedBox(
                width: 72,
                height: 60,
                child: Material(
                  color: Colors.transparent,
                  child: InkWell(
                    borderRadius: BorderRadius.circular(36),
                    onTap: _isLockedOut
                        ? null
                        : () {
                            if (key == '⌫') {
                              _onBackspace();
                            } else {
                              _onDigit(key);
                            }
                          },
                    child: Center(
                      child: key == '⌫'
                          ? const Icon(Icons.backspace_outlined,
                              color: Colors.white70, size: 20)
                          : Text(
                              key,
                              style: GoogleFonts.poppins(
                                color: Colors.white,
                                fontSize: 24,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                    ),
                  ),
                ),
              );
            }).toList(),
          ),
        );
      }).toList(),
    );
  }
}
