import 'package:dio/dio.dart';
import '../models/profile.dart';

abstract class ProfileRepository {
  Future<UserProfile> getProfile();
  Future<UserProfile> updateProfile({
    String? name,
    String? notes,
  });
}

class ProfileRepositoryImpl implements ProfileRepository {
  final Dio _dio;
  final String baseUrl;
  final String token;

  ProfileRepositoryImpl({
    Dio? dio,
    this.baseUrl = 'https://aura-backend-production-bc9c.up.railway.app',
    required this.token,
  }) : _dio = dio ??
            Dio(BaseOptions(
              connectTimeout: const Duration(seconds: 15),
              receiveTimeout: const Duration(seconds: 20),
            ));

  Options get _authOptions => Options(
        headers: {
          'Authorization': 'Bearer $token',
        },
      );

  @override
  Future<UserProfile> getProfile() async {
    final response = await _dio.get(
      '$baseUrl/api/profile',
      options: _authOptions,
    );
    return UserProfile.fromJson(response.data);
  }

  @override
  Future<UserProfile> updateProfile({
    String? name,
    String? notes,
  }) async {
    final data = <String, dynamic>{};
    if (name != null) data['name'] = name;
    if (notes != null) data['notes'] = notes;

    final response = await _dio.post(
      '$baseUrl/api/profile',
      data: data,
      options: _authOptions,
    );
    return UserProfile.fromJson(response.data);
  }
}
