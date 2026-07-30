import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../notifier/profile_notifier.dart';

class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

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

  @override
  Widget build(BuildContext context) {
    final profileAsync = ref.watch(profileNotifierProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Aura Ayarlari')),
      body: profileAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (err, st) => Center(child: Text('Hata: $err')),
        data: (profile) {
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
              ],
            ),
          );
        },
      ),
    );
  }
}
