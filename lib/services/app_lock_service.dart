import 'dart:convert';
import 'dart:math';

import 'package:crypto/crypto.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:local_auth/local_auth.dart';

/// Uygulama kilidi: PIN + (varsa) biyometrik. Kullanici istegi uzerine
/// eklendi (2026-08-26) - "kilitli sozler/kelimeler" gizlilik istegindeki
/// taban katman. Tamamen YEREL (sunucuya hic PIN gitmiyor, hic gitmemeli) -
/// flutter_secure_storage Android'de Keystore, Windows'ta DPAPI, web'de
/// (daha zayif ama kabul edilebilir) sarmalanmis tarayici depolamasi
/// kullaniyor.
///
/// PIN hic acik metin saklanmiyor - rastgele bir salt + SHA-256 hash.
/// Bu bir sunucu sifresi degil (kaba kuvvete karsi bcrypt gibi yavas bir
/// algoritma gerektirmiyor) - cihaza fiziksel erisimi olan biri zaten
/// secure storage'in kendisini hedef alir, o yuzden SHA-256 + salt bu
/// katman icin yeterli ve hizli.
class AppLockService {
  AppLockService._();
  static final AppLockService instance = AppLockService._();

  static const _storage = FlutterSecureStorage();
  static const _kPinHashKey = 'aura_lock_pin_hash';
  static const _kPinSaltKey = 'aura_lock_pin_salt';
  static const _kLockEnabledKey = 'aura_lock_enabled';
  static const _kBiometricEnabledKey = 'aura_lock_biometric_enabled';

  final LocalAuthentication _localAuth = LocalAuthentication();

  String _hash(String value, String salt) {
    return sha256.convert(utf8.encode(salt + value)).toString();
  }

  String _newSalt() {
    final rand = Random.secure();
    return base64UrlEncode(List<int>.generate(16, (_) => rand.nextInt(256)));
  }

  Future<bool> isLockEnabled() async {
    final v = await _storage.read(key: _kLockEnabledKey);
    return v == 'true';
  }

  Future<void> setPin(String pin) async {
    final salt = _newSalt();
    final hash = _hash(pin, salt);
    await _storage.write(key: _kPinSaltKey, value: salt);
    await _storage.write(key: _kPinHashKey, value: hash);
    await _storage.write(key: _kLockEnabledKey, value: 'true');
  }

  Future<bool> verifyPin(String pin) async {
    final salt = await _storage.read(key: _kPinSaltKey);
    final storedHash = await _storage.read(key: _kPinHashKey);
    if (salt == null || storedHash == null) return false;
    return _hash(pin, salt) == storedHash;
  }

  Future<void> disableLock() async {
    await _storage.delete(key: _kPinHashKey);
    await _storage.delete(key: _kPinSaltKey);
    await _storage.write(key: _kLockEnabledKey, value: 'false');
    await _storage.write(key: _kBiometricEnabledKey, value: 'false');
  }

  /// Sadece GERCEK biyometrik donanim (parmak izi/yuz) var mi diye bakar -
  /// cihazin genel PIN/desen kilidini SAYMAZ, cunku o zaten bizim kendi
  /// PIN ekranimizla ayni islevi tekrar ediyor olurdu.
  Future<bool> isBiometricAvailable() async {
    if (kIsWeb) return false;
    try {
      final canCheck = await _localAuth.canCheckBiometrics;
      if (!canCheck) return false;
      final available = await _localAuth.getAvailableBiometrics();
      return available.isNotEmpty;
    } catch (_) {
      return false;
    }
  }

  Future<bool> isBiometricEnabled() async {
    final v = await _storage.read(key: _kBiometricEnabledKey);
    return v == 'true';
  }

  Future<void> setBiometricEnabled(bool enabled) async {
    await _storage.write(
      key: _kBiometricEnabledKey,
      value: enabled ? 'true' : 'false',
    );
  }

  Future<bool> authenticateWithBiometrics() async {
    if (kIsWeb) return false;
    try {
      return await _localAuth.authenticate(
        localizedReason: 'Aura\'ya girmek için kimliğini doğrula',
        biometricOnly: true,
        persistAcrossBackgrounding: true,
      );
    } catch (_) {
      return false;
    }
  }
}
