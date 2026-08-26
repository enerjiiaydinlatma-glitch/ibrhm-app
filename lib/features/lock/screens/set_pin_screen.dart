import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';

import '../../../services/app_lock_service.dart';

const _kPinLength = 4;
const _kBgColor = Color(0xFF0A0A1A);
const _kIndigoColor = Color(0xFF6C63FF);

/// Yeni PIN belirleme akisi: once gir, sonra tekrar gir (yazim hatasina
/// karsi). Basarili olunca AppLockService.setPin() cagirip true doner.
class SetPinScreen extends StatefulWidget {
  const SetPinScreen({super.key});

  @override
  State<SetPinScreen> createState() => _SetPinScreenState();
}

class _SetPinScreenState extends State<SetPinScreen> {
  String _first = '';
  String _entered = '';
  bool _confirming = false;
  String? _error;
  bool _shaking = false;

  void _onDigit(String digit) {
    if (_entered.length >= _kPinLength) return;
    setState(() {
      _entered += digit;
      _error = null;
    });
    if (_entered.length == _kPinLength) {
      _handleComplete();
    }
  }

  void _onBackspace() {
    if (_entered.isEmpty) return;
    setState(() => _entered = _entered.substring(0, _entered.length - 1));
  }

  Future<void> _handleComplete() async {
    if (!_confirming) {
      setState(() {
        _first = _entered;
        _entered = '';
        _confirming = true;
      });
      return;
    }
    if (_entered == _first) {
      await AppLockService.instance.setPin(_first);
      if (mounted) Navigator.of(context).pop(true);
      return;
    }
    HapticFeedback.mediumImpact();
    setState(() {
      _shaking = true;
      _entered = '';
      _first = '';
      _confirming = false;
      _error = 'PIN\'ler eşleşmedi, baştan dene';
    });
    Future.delayed(const Duration(milliseconds: 400), () {
      if (mounted) setState(() => _shaking = false);
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _kBgColor,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        title: Text('PIN Belirle', style: GoogleFonts.poppins()),
      ),
      body: SafeArea(
        child: Column(
          children: [
            const Spacer(flex: 2),
            const Icon(Icons.lock_outline, color: _kIndigoColor, size: 40),
            const SizedBox(height: 16),
            Text(
              _confirming ? 'PIN\'i tekrar gir' : '4 haneli bir PIN belirle',
              style: GoogleFonts.poppins(
                color: Colors.white,
                fontSize: 16,
                fontWeight: FontWeight.w500,
              ),
            ),
            const SizedBox(height: 24),
            AnimatedContainer(
              duration: const Duration(milliseconds: 80),
              transform: Matrix4.translationValues(_shaking ? 8 : 0, 0, 0),
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
                _error ?? '',
                style: GoogleFonts.poppins(color: Colors.redAccent, fontSize: 13),
              ),
            ),
            const Spacer(flex: 2),
            _buildKeypad(),
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
                    onTap: () {
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
