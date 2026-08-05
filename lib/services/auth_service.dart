import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';

class AuthService {
  static const String _baseUrl = 'https://aura-backend-production-bc9c.up.railway.app';
  static const String _tokenKey = 'auth_token';
  static const String _userKey = 'auth_user';

  final Dio _dio = Dio();

  Future<String?> getToken() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString(_tokenKey);
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
    if (token == null) return false;
    try {
      final response = await _dio.get(
        '$_baseUrl/api/auth/me',
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }

  Future<Map<String, dynamic>> register(String email, String password, String name) async {
    final response = await _dio.post(
      '$_baseUrl/api/auth/register',
      data: {'email': email, 'password': password, 'name': name},
    );
    return response.data as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> login(String email, String password) async {
    final response = await _dio.post(
      '$_baseUrl/api/auth/login',
      data: {'email': email, 'password': password},
    );
    return response.data as Map<String, dynamic>;
  }

  Future<void> logout(String token) async {
    try {
      await _dio.post(
        '$_baseUrl/api/auth/logout',
        options: Options(headers: {'Authorization': 'Bearer $token'}),
      );
    } catch (_) {}
    await clearToken();
  }
}