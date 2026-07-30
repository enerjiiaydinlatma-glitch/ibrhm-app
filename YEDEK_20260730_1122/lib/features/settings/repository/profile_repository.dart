import 'package:dio/dio.dart';
import '../models/profile.dart';

abstract class ProfileRepository {
  Future<UserProfile> getProfile();
  Future<UserProfile> updateProfile({
    String? name,
    String? warmth,
    String? formality,
    String? humor,
    String? directness,
    String? notes,
  });
}

class ProfileRepositoryImpl implements ProfileRepository {
  final Dio _dio;
  final String baseUrl;

  ProfileRepositoryImpl({
    Dio? dio,
    this.baseUrl = 'http://127.0.0.1:8000',
  }) : _dio = dio ?? Dio();

  @override
  Future<UserProfile> getProfile() async {
    final response = await _dio.get('$baseUrl/api/profile');
    return UserProfile.fromJson(response.data);
  }

  @override
  Future<UserProfile> updateProfile({
    String? name,
    String? warmth,
    String? formality,
    String? humor,
    String? directness,
    String? notes,
  }) async {
    final data = <String, dynamic>{};
    if (name != null) data['name'] = name;
    if (warmth != null) data['warmth'] = warmth;
    if (formality != null) data['formality'] = formality;
    if (humor != null) data['humor'] = humor;
    if (directness != null) data['directness'] = directness;
    if (notes != null) data['notes'] = notes;

    final response = await _dio.post(
      '$baseUrl/api/profile',
      data: data,
    );
    return UserProfile.fromJson(response.data);
  }
}
