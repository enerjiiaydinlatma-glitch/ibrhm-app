import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Bu cihazda daha once gecerli bir oturum vardi ama artik gecersiz -
/// buyuk ihtimalle kullanici baska bir cihazdan giris yaptigi icin
/// (free tier: ayni anda tek cihaz kurali) bu cihazin oturumu dustu.
/// Bu durumda SESSIZCE yeni bir anonim hesap ACILMAMALI (kullanici
/// gercek/claim edilmis hesabini fark etmeden kaybeder) - bunun yerine
/// giris formu, aciklayici bir mesajla gosterilmeli.
class SessionKickedOutException implements Exception {
  const SessionKickedOutException();
}

class AuthService {
  static const String _baseUrl =
      'https://aura-backend-production-bc9c.up.railway.app';

  static const String _tokenKey = 'auth_token';
  static const String _userKey = 'auth_user';

  final Dio _dio = Dio(
    BaseOptions(
      baseUrl: _baseUrl,
      connectTimeout: const Duration(seconds: 15),
      receiveTimeout: const Duration(seconds: 30),
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
    ),
  );

  Future<String?> getToken() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_tokenKey);
  }

  Future<String> getOrCreateAnonymousToken() async {
    final existingToken = await getToken();

    if (existingToken != null && existingToken.isNotEmpty) {
      final valid = await isLoggedIn();

      if (valid) {
        return existingToken;
      }

      // ONEMLI: burada token VARDI ama artik gecersiz - bu, ilk kurulum
      // durumundan (hic token yok) FARKLI. Sessizce yeni bir anonim
      // hesap acmak, kullanicinin claim ettigi gercek hesabini fark
      // etmeden kaybetmesine yol acar (bkz. SessionKickedOutException).
      await clearToken();
      throw const SessionKickedOutException();
    }

    final stamp = DateTime.now().microsecondsSinceEpoch;
    final email = 'anonymous_$stamp@aura.local';
    final password = 'Aura_$stamp!';

    final result = await register(
      email,
      password,
      'Aura Kullanıcısı',
    );

    final token = result['token']?.toString();

    if (token == null || token.isEmpty) {
      throw Exception('Anonim Aura oturumu oluşturulamadı.');
    }

    await saveToken(token);

    return token;
  }

  Future<void> saveToken(String token) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_tokenKey, token);
  }

  Future<void> clearToken() async {
    final prefs = await SharedPreferences.getInstance();

    await prefs.remove(_tokenKey);
    await prefs.remove(_userKey);
  }

  Future<bool> isLoggedIn() async {
    final token = await getToken();

    if (token == null || token.isEmpty) {
      return false;
    }

    try {
      final response = await _dio.get(
        '/api/auth/me',
        options: Options(
          headers: {
            'Authorization': 'Bearer $token',
          },
        ),
      );

      return response.statusCode == 200;
    } on DioException {
      return false;
    } catch (_) {
      return false;
    }
  }

  Future<Map<String, dynamic>> register(
    String email,
    String password,
    String name,
  ) async {
    final response = await _dio.post(
      '/api/auth/register',
      data: {
        'email': email,
        'password': password,
        'name': name,
      },
    );

    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<Map<String, dynamic>> login(
    String email,
    String password,
  ) async {
    final response = await _dio.post(
      '/api/auth/login',
      data: {
        'email': email,
        'password': password,
      },
    );

    return Map<String, dynamic>.from(response.data as Map);
  }

  /// Anonim (kullanicinin hic gormedigi) hesabi, kullanicinin kendi
  /// belirledigi gercek email/sifreyle hatirlanabilir bir hesaba cevirir.
  /// Ayni kullanici satiri guncellenir - tum gecmis/hafiza korunur.
  Future<Map<String, dynamic>> claimAccount(
    String token,
    String email,
    String password,
  ) async {
    final response = await _dio.post(
      '/api/auth/claim',
      data: {
        'email': email,
        'password': password,
      },
      options: Options(
        headers: {
          'Authorization': 'Bearer $token',
        },
      ),
    );

    return Map<String, dynamic>.from(response.data as Map);
  }

  Future<void> logout(String token) async {
    try {
      await _dio.post(
        '/api/auth/logout',
        options: Options(
          headers: {
            'Authorization': 'Bearer $token',
          },
        ),
      );
    } catch (_) {
      // Backend logout baÅŸarÄ±sÄ±z olsa bile
      // yerel token temizlenir.
    }

    await clearToken();
  }
}
