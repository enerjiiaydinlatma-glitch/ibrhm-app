import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/profile.dart';
import '../repository/profile_repository.dart';

class ProfileNotifier extends AsyncNotifier<UserProfile?> {
  String? _token;

  @override
  FutureOr<UserProfile?> build() => null;

  void setToken(String token) {
    _token = token;
  }

  ProfileRepository get _repository {
    final token = _token;

    if (token == null || token.isEmpty) {
      throw StateError('Aura oturum anahtarı bulunamadı.');
    }

    return ProfileRepositoryImpl(token: token);
  }

  Future<void> load() async {
    state = const AsyncValue.loading();
    try {
      final profile = await _repository.getProfile();
      state = AsyncValue.data(profile);
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }

  Future<void> save({
    String? name,
    String? notes,
  }) async {
    final repository = _repository;
    state = const AsyncValue.loading();
    try {
      final updated = await repository.updateProfile(
        name: name,
        notes: notes,
      );
      state = AsyncValue.data(updated);
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }
}

final profileNotifierProvider =
    AsyncNotifierProvider<ProfileNotifier, UserProfile?>(ProfileNotifier.new);
