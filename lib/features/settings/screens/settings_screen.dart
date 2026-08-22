import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../models/memory_item.dart';
import '../notifier/memory_notifier.dart';
import '../notifier/profile_notifier.dart';

class SettingsScreen extends ConsumerStatefulWidget {
  final String token;
  const SettingsScreen({super.key, required this.token});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  final _nameController = TextEditingController();
  final _notesController = TextEditingController();
  String _warmth = 'sicak';
  String _formality = 'samimi';
  String _humor = 'orta';
  String _directness = 'dengeli';
  bool _initialized = false;

  static const warmthOptions = ['mesafeli', 'dengeli', 'sicak'];
  static const formalityOptions = ['resmi', 'dengeli', 'samimi'];
  static const humorOptions = ['dusuk', 'orta', 'yuksek'];
  static const directnessOptions = ['yumusak', 'dengeli', 'dogrudan'];

  static const _categoryLabels = {
    'identity': 'Kimlik',
    'preference': 'Tercihler',
    'hobiler': 'Hobiler',
    'hobby': 'Hobiler',
    'goals': 'Hedefler',
    'work': 'Meslek',
  };

  @override
  void initState() {
    super.initState();
    ref.read(profileNotifierProvider.notifier)
      ..setToken(widget.token)
      ..load();
    ref.read(memoryNotifierProvider.notifier)
      ..setToken(widget.token)
      ..load();
  }

  void _fillFromProfile(profile) {
    if (_initialized) return;
    _nameController.text = profile.name ?? '';
    _notesController.text = profile.notes;
    _warmth = profile.warmth;
    _formality = profile.formality;
    _humor = profile.humor;
    _directness = profile.directness;
    _initialized = true;
  }

  void _save() {
    ref.read(profileNotifierProvider.notifier).save(
          name: _nameController.text.trim().isEmpty
              ? null
              : _nameController.text.trim(),
          warmth: _warmth,
          formality: _formality,
          humor: _humor,
          directness: _directness,
          notes: _notesController.text.trim(),
        );
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Ayarlar kaydedildi')),
    );
  }

  Future<void> _deleteMemory(MemoryItem memory) async {
    try {
      await ref.read(memoryNotifierProvider.notifier).delete(memory.id);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('"${memory.memoryValue}" unutuldu')),
      );
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Silinemedi, tekrar dene')),
      );
    }
  }

  Widget _buildDropdown(
    String label,
    String value,
    List<String> options,
    void Function(String) onChanged,
  ) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          Expanded(child: Text(label)),
          DropdownButton<String>(
            value: value,
            items: options
                .map((o) => DropdownMenuItem(value: o, child: Text(o)))
                .toList(),
            onChanged: (v) {
              if (v != null) setState(() => onChanged(v));
            },
          ),
        ],
      ),
    );
  }

  Widget _buildMemorySection() {
    final memoriesAsync = ref.watch(memoryNotifierProvider);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Hafızam',
          style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
        ),
        const SizedBox(height: 4),
        const Text(
          'Aura senin hakkında bunları hatırlıyor. İstemediğini silebilirsin.',
          style: TextStyle(fontSize: 12, color: Colors.white54),
        ),
        const SizedBox(height: 12),
        memoriesAsync.when(
          loading: () => const Padding(
            padding: EdgeInsets.symmetric(vertical: 16),
            child: Center(child: CircularProgressIndicator()),
          ),
          error: (err, st) => Text('Hafıza yüklenemedi: $err'),
          data: (memories) {
            if (memories.isEmpty) {
              return const Padding(
                padding: EdgeInsets.symmetric(vertical: 8),
                child: Text(
                  'Henüz hiçbir şey hatırlamıyor.',
                  style: TextStyle(color: Colors.white54),
                ),
              );
            }
            return Column(
              children: memories.map((memory) {
                final label = _categoryLabels[memory.category] ??
                    memory.category;
                return Card(
                  margin: const EdgeInsets.only(bottom: 8),
                  child: ListTile(
                    dense: true,
                    title: Text(memory.memoryValue),
                    subtitle: Text(label),
                    trailing: IconButton(
                      icon: const Icon(Icons.delete_outline),
                      tooltip: 'Unut',
                      onPressed: () => _deleteMemory(memory),
                    ),
                  ),
                );
              }).toList(),
            );
          },
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final profileAsync = ref.watch(profileNotifierProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Aura Ayarlari')),
      body: profileAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (err, st) => Center(child: Text('Hata: $err')),
        data: (profile) {
          if (profile == null) {
            return const Center(child: CircularProgressIndicator());
          }
          _fillFromProfile(profile);
          return SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Kisisel Bilgiler',
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: _nameController,
                  decoration: const InputDecoration(
                    labelText: 'Adin',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 24),
                const Text(
                  'Aura Nasil Davransin',
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                ),
                _buildDropdown(
                  'Sicaklik',
                  _warmth,
                  warmthOptions,
                  (v) => _warmth = v,
                ),
                _buildDropdown(
                  'Resmiyet',
                  _formality,
                  formalityOptions,
                  (v) => _formality = v,
                ),
                _buildDropdown(
                  'Mizah',
                  _humor,
                  humorOptions,
                  (v) => _humor = v,
                ),
                _buildDropdown(
                  'Dogrudanlik',
                  _directness,
                  directnessOptions,
                  (v) => _directness = v,
                ),
                const SizedBox(height: 24),
                const Text(
                  'Serbest Talimat',
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                ),
                const SizedBox(height: 8),
                TextField(
                  controller: _notesController,
                  maxLines: 4,
                  decoration: const InputDecoration(
                    hintText:
                        'Ornek: Beni sakaci bul ama is konularinda ciddi ol.',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 24),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: _save,
                    child: const Padding(
                      padding: EdgeInsets.symmetric(vertical: 12),
                      child: Text('Kaydet'),
                    ),
                  ),
                ),
                const SizedBox(height: 32),
                const Divider(),
                const SizedBox(height: 16),
                _buildMemorySection(),
              ],
            ),
          );
        },
      ),
    );
  }
}
