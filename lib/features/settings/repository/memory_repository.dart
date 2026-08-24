import 'package:dio/dio.dart';
import '../models/memory_item.dart';

abstract class MemoryRepository {
  Future<List<MemoryItem>> getMemories();
  Future<void> deleteMemory(int id);
}

class MemoryRepositoryImpl implements MemoryRepository {
  final Dio _dio;
  final String baseUrl;
  final String token;

  MemoryRepositoryImpl({
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
  Future<List<MemoryItem>> getMemories() async {
    final response = await _dio.get(
      '$baseUrl/api/memories',
      options: _authOptions,
    );
    final list = response.data as List;
    return list
        .map((e) => MemoryItem.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<void> deleteMemory(int id) async {
    await _dio.delete(
      '$baseUrl/api/memories/$id',
      options: _authOptions,
    );
  }
}
