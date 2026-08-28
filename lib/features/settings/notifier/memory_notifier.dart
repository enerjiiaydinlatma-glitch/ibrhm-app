import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/memory_item.dart';
import '../repository/memory_repository.dart';

class MemoryNotifier extends AsyncNotifier<List<MemoryItem>> {
  String? _token;

  @override
  FutureOr<List<MemoryItem>> build() => [];

  void setToken(String token) {
    _token = token;
  }

  MemoryRepository get _repository {
    final token = _token;

    if (token == null || token.isEmpty) {
      throw StateError('Aura oturum anahtarı bulunamadı.');
    }

    return MemoryRepositoryImpl(token: token);
  }

  Future<void> load() async {
    state = const AsyncValue.loading();
    try {
      final memories = await _repository.getMemories();
      state = AsyncValue.data(memories);
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }

  Future<void> delete(int id) async {
    final previous = state.value ?? [];

    state = AsyncValue.data(
      previous.where((m) => m.id != id).toList(),
    );

    try {
      await _repository.deleteMemory(id);
    } catch (e) {
      state = AsyncValue.data(previous);
      rethrow;
    }
  }

  /// Dogal Hafiza: kullanici bir kaydi sabitler/sabitlemeyi kaldirirsa -
  /// delete() ile ayni iyimser-guncelleme (optimistic update) deseni.
  Future<void> togglePin(int id) async {
    final previous = state.value ?? [];
    final matches = previous.where((m) => m.id == id);
    if (matches.isEmpty) return;
    final newPinned = !matches.first.pinned;

    state = AsyncValue.data(
      previous.map((m) => m.id == id ? m.copyWith(pinned: newPinned) : m).toList(),
    );

    try {
      await _repository.setMemoryPinned(id, newPinned);
    } catch (e) {
      state = AsyncValue.data(previous);
      rethrow;
    }
  }
}

final memoryNotifierProvider =
    AsyncNotifierProvider<MemoryNotifier, List<MemoryItem>>(
        MemoryNotifier.new);
