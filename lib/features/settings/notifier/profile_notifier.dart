import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/profile.dart';
import '../repository/profile_repository.dart';

final profileRepositoryProvider = Provider<ProfileRepository>((ref) {
  return ProfileRepositoryImpl();
});

class ProfileNotifier extends AsyncNotifier<UserProfile> {
  @override
  Future<UserProfile> build() async {
    final repository = ref.read(profileRepositoryProvider);
    return repository.getProfile();
  }

  Future<void> save({
    String? name,
    String? warmth,
    String? formality,
    String? humor,
    String? directness,
    String? notes,
  }) async {
    final repository = ref.read(profileRepositoryProvider);
    state = const AsyncValue.loading();
    try {
      final updated = await repository.updateProfile(
        name: name,
        warmth: warmth,
        formality: formality,
        humor: humor,
        directness: directness,
        notes: notes,
      );
      state = AsyncValue.data(updated);
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }
}

final profileNotifierProvider =
    AsyncNotifierProvider<ProfileNotifier, UserProfile>(() {
  return ProfileNotifier();
});
