import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_fonts/google_fonts.dart';
import '../models/memory_item.dart';
import '../notifier/memory_notifier.dart';
import '../widgets/memory_tree_painter.dart';
import '../models/profile.dart';
import '../notifier/profile_notifier.dart';
import '../../../services/auth_service.dart';
import '../../../services/app_lock_service.dart';
import '../../chat/screens/auth_screen.dart';
import '../../lock/screens/lock_screen.dart';
import '../../lock/screens/set_pin_screen.dart';
import 'hidden_chats_screen.dart';

/// Ayarlar ekrani - kullanicinin "ayarlara hicbir erisimi yok" bulgusuna
/// karsi eklendi (2026-08-24). Onceden vardi ama hicbir yerden
/// ulasilamiyordu (nav baglantisi yoktu) ve uygulamanin geri kalaniyla
/// hic uyumsuz varsayilan (acik/beyaz) Material temasindaydi - artik
/// chat_screen.dart ile ayni koyu/indigo kimlige getirildi ve AppBar'a
/// bir giris noktasi eklendi.
class SettingsScreen extends ConsumerStatefulWidget {
  final String token;
  const SettingsScreen({super.key, required this.token});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen> {
  static const _bgColor = Color(0xFF0A0A1A);
  static const _cardColor = Color(0xFF12122A);
  static const _indigoColor = Color(0xFF6C63FF);
  static const _borderColor = Color(0xFF2A2A4A);

  final _nameController = TextEditingController();
  final _notesController = TextEditingController();
  final _secretPhraseController = TextEditingController();
  bool _initialized = false;
  bool _loggingOut = false;
  bool _savingSecretPhrase = false;

  bool _lockEnabled = false;
  bool _biometricAvailable = false;
  bool _biometricEnabled = false;
  bool _hideNotificationPreviews = false;

  // Backend'deki LIMIT_DAILY_MESSAGES/VOICE_DAILY_LIMIT_SECONDS ile
  // ayni deger - sunucu bu sayilari ayrica bir API ile yayinlamiyor,
  // bu yuzden burada eslenik olarak tutuluyor (degisirse ikisi de
  // guncellenmeli).
  static const int _freeMessageLimit = 30;
  static const int _freeVoiceSecondsLimit = 600;

  // NOT: bu kategoriler bir LLM'in serbest metinden urettigi degerler -
  // sabit bir enum degil, o yuzden bu liste HICBIR ZAMAN tam olamaz.
  // Bilinen tum varyantlari (Turkce+Ingilizce, hem cikarim promptunun
  // kendi ornekleri hem gercek testlerde gorulenler) burada topluyoruz;
  // eslesmeyenler icin asagidaki _prettifyCategory() devreye giriyor.
  static const _categoryLabels = {
    'isim': 'İsim',
    'identity': 'Kimlik',
    'yer': 'Yaşadığı Yer',
    'location': 'Yaşadığı Yer',
    'meslek': 'Meslek',
    'work': 'Meslek',
    'job': 'Meslek',
    'hobiler': 'Hobiler',
    'hobby': 'Hobiler',
    'hobbies': 'Hobiler',
    'ilgi_alanlari': 'İlgi Alanları',
    'interests': 'İlgi Alanları',
    'hedefler': 'Hedefler',
    'goals': 'Hedefler',
    'goal': 'Hedefler',
    'tercihler': 'Tercihler',
    'preference': 'Tercihler',
    'preferences': 'Tercihler',
    'projeler': 'Projeler',
    'important_projects': 'Projeler',
    'projects': 'Projeler',
    'planlar': 'Planlar',
    'plans': 'Planlar',
    'upcoming_event': 'Yaklaşan Gündem',
    'gundem': 'Yaklaşan Gündem',
    'korkular': 'Korkular',
    'iletisim_tercihleri': 'İletişim Tercihleri',
    'communication_preferences': 'İletişim Tercihleri',
    'routine': 'Rutin',
    'rutin': 'Rutin',
    'evcil_hayvan': 'Evcil Hayvan',
    'pet': 'Evcil Hayvan',
    'pet_info': 'Evcil Hayvan',
    'en_buyuk_korku': 'Korkular',
    'fear': 'Korkular',
    'pattern_insight': 'Fark Edilen Örüntü',
  };

  /// Yukaridaki sabit listede olmayan (LLM'in uretebilecegi herhangi bir)
  /// kategori icin ham "important_projects" yerine en azindan okunabilir
  /// bir gorunum: alt cizgileri bosluga cevirip her kelimeyi buyuk harfle
  /// baslatiyoruz. Mukemmel Turkce ceviri degil ama ham anahtardan iyi.
  static String _prettifyCategory(String raw) {
    if (raw.isEmpty) return raw;
    return raw
        .split(RegExp(r'[_\s]+'))
        .where((w) => w.isNotEmpty)
        .map((w) => w[0].toUpperCase() + w.substring(1))
        .join(' ');
  }

  @override
  void initState() {
    super.initState();
    ref.read(profileNotifierProvider.notifier)
      ..setToken(widget.token)
      ..load();
    ref.read(memoryNotifierProvider.notifier)
      ..setToken(widget.token)
      ..load();
    _loadLockState();
  }

  @override
  void dispose() {
    _nameController.dispose();
    _notesController.dispose();
    _secretPhraseController.dispose();
    super.dispose();
  }

  Future<void> _loadLockState() async {
    final lockEnabled = await AppLockService.instance.isLockEnabled();
    final biometricAvailable = await AppLockService.instance.isBiometricAvailable();
    final biometricEnabled = await AppLockService.instance.isBiometricEnabled();
    final hidePreviews = await AppLockService.instance.hideNotificationPreviews();
    if (!mounted) return;
    setState(() {
      _lockEnabled = lockEnabled;
      _biometricAvailable = biometricAvailable;
      _biometricEnabled = biometricEnabled;
      _hideNotificationPreviews = hidePreviews;
    });
  }

  Future<void> _toggleHideNotificationPreviews(bool hide) async {
    await AppLockService.instance.setHideNotificationPreviews(hide);
    if (mounted) setState(() => _hideNotificationPreviews = hide);
  }

  Future<void> _toggleLock(bool enable) async {
    if (enable) {
      final created = await Navigator.of(context).push<bool>(
        MaterialPageRoute(builder: (_) => const SetPinScreen()),
      );
      if (created == true && mounted) {
        setState(() => _lockEnabled = true);
      }
      return;
    }
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: _cardColor,
        title: Text('Kilidi kaldır', style: GoogleFonts.poppins(color: Colors.white)),
        content: Text(
          'Uygulama kilidini kapatmak istediğine emin misin?',
          style: GoogleFonts.poppins(color: Colors.white70),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Vazgeç')),
          TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Kaldır')),
        ],
      ),
    );
    if (confirmed == true) {
      await AppLockService.instance.disableLock();
      if (mounted) {
        setState(() {
          _lockEnabled = false;
          _biometricEnabled = false;
        });
      }
    }
  }

  Future<void> _changePin() async {
    await Navigator.of(context).push<bool>(
      MaterialPageRoute(builder: (_) => const SetPinScreen()),
    );
  }

  Future<void> _toggleBiometric(bool enable) async {
    if (enable) {
      final ok = await AppLockService.instance.authenticateWithBiometrics();
      if (!ok) return;
    }
    await AppLockService.instance.setBiometricEnabled(enable);
    if (mounted) setState(() => _biometricEnabled = enable);
  }

  Future<void> _saveSecretPhrase() async {
    final phrase = _secretPhraseController.text.trim();
    if (phrase.length < 2) return;
    setState(() => _savingSecretPhrase = true);
    try {
      await ref.read(profileNotifierProvider.notifier).setSecretPhrase(phrase);
      _secretPhraseController.clear();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Gizli mod kodu ayarlandı', style: GoogleFonts.poppins())),
        );
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Kod ayarlanamadı, tekrar dene', style: GoogleFonts.poppins())),
        );
      }
    } finally {
      if (mounted) setState(() => _savingSecretPhrase = false);
    }
  }

  Future<void> _clearSecretPhrase() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: _cardColor,
        title: Text('Gizli mod kodunu kaldır', style: GoogleFonts.poppins(color: Colors.white)),
        content: Text(
          'Kod kaldırılınca gizli mod bir daha tetiklenemez. Zaten kaydedilmiş gizli sohbetler etkilenmez.',
          style: GoogleFonts.poppins(color: Colors.white70),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Vazgeç')),
          TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Kaldır')),
        ],
      ),
    );
    if (confirmed == true) {
      await ref.read(profileNotifierProvider.notifier).clearSecretPhrase();
    }
  }

  void _openHiddenChats() {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (_) => LockScreen(
          onUnlocked: () {
            Navigator.of(context).pushReplacement(
              MaterialPageRoute(builder: (_) => const HiddenChatsScreen()),
            );
          },
        ),
      ),
    );
  }

  void _fillFromProfile(UserProfile profile) {
    if (_initialized) return;
    _nameController.text = profile.name ?? '';
    _notesController.text = profile.notes;
    _initialized = true;
  }

  void _save() {
    ref.read(profileNotifierProvider.notifier).save(
          name: _nameController.text.trim().isEmpty
              ? null
              : _nameController.text.trim(),
          notes: _notesController.text.trim(),
        );
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('Ayarlar kaydedildi', style: GoogleFonts.poppins())),
    );
  }

  Future<void> _deleteMemory(MemoryItem memory) async {
    try {
      await ref.read(memoryNotifierProvider.notifier).delete(memory.id);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('"${memory.memoryValue}" unutuldu', style: GoogleFonts.poppins())),
      );
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Silinemedi, tekrar dene', style: GoogleFonts.poppins())),
      );
    }
  }

  Future<void> _logout() async {
    setState(() => _loggingOut = true);
    try {
      await AuthService().logout(widget.token);
    } finally {
      if (mounted) {
        Navigator.of(context).pushAndRemoveUntil(
          MaterialPageRoute(builder: (_) => const AuthScreen()),
          (route) => false,
        );
      }
    }
  }

  Future<void> _confirmLogout() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        backgroundColor: _cardColor,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Text('Çıkış yap', style: GoogleFonts.poppins(color: Colors.white, fontWeight: FontWeight.w600)),
        content: Text(
          'Hesabın kaydedilmediyse (anonimse) bu cihazdan çıktığında geçmişine bir daha erişemeyebilirsin.',
          style: GoogleFonts.poppins(color: Colors.white70, fontSize: 13),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: Text('Vazgeç', style: GoogleFonts.poppins(color: Colors.white54)),
          ),
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: Text('Çıkış yap', style: GoogleFonts.poppins(color: Colors.redAccent)),
          ),
        ],
      ),
    );
    if (confirmed == true) await _logout();
  }

  InputDecoration _fieldDecoration(String label, {String? hint}) {
    return InputDecoration(
      labelText: label,
      hintText: hint,
      labelStyle: GoogleFonts.poppins(color: Colors.white54, fontSize: 13),
      hintStyle: GoogleFonts.poppins(color: Colors.white30, fontSize: 13),
      filled: true,
      fillColor: _bgColor,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: _borderColor),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: _borderColor),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(12),
        borderSide: const BorderSide(color: _indigoColor),
      ),
    );
  }

  Widget _sectionTitle(String text) => Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: Text(
          text,
          style: GoogleFonts.poppins(fontWeight: FontWeight.w600, fontSize: 15, color: Colors.white),
        ),
      );

  Widget _card({required Widget child}) => Container(
        padding: const EdgeInsets.all(18),
        decoration: BoxDecoration(
          color: _cardColor,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: _borderColor),
        ),
        child: child,
      );

  Widget _buildUsageSection(UserProfile profile) {
    final isPro = profile.tier == 'pro';
    if (isPro) {
      return _card(
        child: Row(
          children: [
            const Icon(Icons.workspace_premium_outlined, color: Color(0xFFFFC857)),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                'Pro hesap - günlük kullanım sınırın yok.',
                style: GoogleFonts.poppins(color: Colors.white, fontSize: 13),
              ),
            ),
          ],
        ),
      );
    }
    final msgLeft = (_freeMessageLimit - profile.dailyMessageCount).clamp(0, _freeMessageLimit);
    final voiceLeftSec = (_freeVoiceSecondsLimit - profile.dailyVoiceSeconds).clamp(0, _freeVoiceSecondsLimit);
    final msgRatio = profile.dailyMessageCount / _freeMessageLimit;
    final voiceRatio = profile.dailyVoiceSeconds / _freeVoiceSecondsLimit;
    return _card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  'Bugünkü ücretsiz kullanım',
                  style: GoogleFonts.poppins(fontWeight: FontWeight.w600, fontSize: 13, color: Colors.white),
                ),
              ),
              Text('yarın sıfırlanır', style: GoogleFonts.poppins(fontSize: 11, color: Colors.white38)),
            ],
          ),
          const SizedBox(height: 14),
          _usageRow('Mesaj', profile.dailyMessageCount, _freeMessageLimit, msgRatio, '$msgLeft mesaj kaldı'),
          const SizedBox(height: 12),
          _usageRow(
            'Sesli görüşme',
            profile.dailyVoiceSeconds ~/ 60,
            _freeVoiceSecondsLimit ~/ 60,
            voiceRatio,
            '${(voiceLeftSec / 60).ceil()} dk kaldı',
            unit: 'dk',
          ),
        ],
      ),
    );
  }

  Widget _usageRow(String label, int used, int max, double ratio, String remainingText, {String unit = ''}) {
    final clampedRatio = ratio.clamp(0.0, 1.0);
    final barColor = clampedRatio > 0.85 ? Colors.redAccent : _indigoColor;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Expanded(
              child: Text(label, style: GoogleFonts.poppins(fontSize: 12, color: Colors.white70)),
            ),
            Text(
              '$used$unit / $max$unit',
              style: GoogleFonts.poppins(fontSize: 12, color: Colors.white70, fontFeatures: const [FontFeature.tabularFigures()]),
            ),
          ],
        ),
        const SizedBox(height: 6),
        ClipRRect(
          borderRadius: BorderRadius.circular(6),
          child: LinearProgressIndicator(
            value: clampedRatio,
            minHeight: 6,
            backgroundColor: _bgColor,
            valueColor: AlwaysStoppedAnimation(barColor),
          ),
        ),
        const SizedBox(height: 4),
        Text(remainingText, style: GoogleFonts.poppins(fontSize: 11, color: Colors.white38)),
      ],
    );
  }

  Widget _buildPrivacySection(UserProfile profile) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionTitle('Gizlilik'),
        _card(
          child: Column(
            children: [
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                activeThumbColor: _indigoColor,
                title: Text('Uygulama kilidi (PIN)',
                    style: GoogleFonts.poppins(color: Colors.white, fontSize: 14)),
                subtitle: Text('Aura\'yı her açışında PIN sorulsun',
                    style: GoogleFonts.poppins(color: Colors.white38, fontSize: 12)),
                value: _lockEnabled,
                onChanged: _toggleLock,
              ),
              const Divider(color: _borderColor, height: 1),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                activeThumbColor: _indigoColor,
                title: Text('Bildirim önizlemesini gizle',
                    style: GoogleFonts.poppins(color: Colors.white, fontSize: 14)),
                subtitle: Text('Kilit ekranında hatırlatma içeriği yerine "Aura" yazsın',
                    style: GoogleFonts.poppins(color: Colors.white38, fontSize: 12)),
                value: _hideNotificationPreviews,
                onChanged: _toggleHideNotificationPreviews,
              ),
              if (_lockEnabled) ...[
                const Divider(color: _borderColor, height: 1),
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text('PIN\'i değiştir',
                      style: GoogleFonts.poppins(color: Colors.white, fontSize: 14)),
                  trailing: const Icon(Icons.chevron_right, color: Colors.white38),
                  onTap: _changePin,
                ),
                if (_biometricAvailable) ...[
                  const Divider(color: _borderColor, height: 1),
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    activeThumbColor: _indigoColor,
                    title: Text('Biyometrik ile aç',
                        style: GoogleFonts.poppins(color: Colors.white, fontSize: 14)),
                    subtitle: Text('Parmak izi / yüz tanıma ile hızlı giriş',
                        style: GoogleFonts.poppins(color: Colors.white38, fontSize: 12)),
                    value: _biometricEnabled,
                    onChanged: _toggleBiometric,
                  ),
                ],
                const Divider(color: _borderColor, height: 1),
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Gizli mod kod cümlesi',
                          style: GoogleFonts.poppins(color: Colors.white, fontSize: 14)),
                      const SizedBox(height: 4),
                      Text(
                        profile.hasSecretPhrase
                            ? 'Bir kod belirlendi. Sohbette bu cümleyi tek başına gönderirsen gizli mod açılır/kapanır.'
                            : 'Kendi cümleni belirle. Sohbette bunu tek başına bir mesaj olarak gönderirsen, o andan sonraki konuşma normal geçmişte görünmez.',
                        style: GoogleFonts.poppins(color: Colors.white38, fontSize: 12),
                      ),
                      const SizedBox(height: 10),
                      Row(
                        children: [
                          Expanded(
                            child: TextField(
                              controller: _secretPhraseController,
                              style: GoogleFonts.poppins(color: Colors.white, fontSize: 13),
                              decoration: _fieldDecoration('', hint: 'örn: bugün ay çok parlak'),
                            ),
                          ),
                          const SizedBox(width: 8),
                          _savingSecretPhrase
                              ? const SizedBox(
                                  width: 20, height: 20,
                                  child: CircularProgressIndicator(strokeWidth: 2, color: _indigoColor),
                                )
                              : IconButton(
                                  onPressed: _saveSecretPhrase,
                                  icon: const Icon(Icons.check_circle_outline, color: _indigoColor),
                                ),
                        ],
                      ),
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          TextButton.icon(
                            onPressed: _openHiddenChats,
                            icon: const Icon(Icons.visibility_off_outlined, size: 16, color: Colors.white54),
                            label: Text('Gizli sohbetleri gör',
                                style: GoogleFonts.poppins(color: Colors.white54, fontSize: 12)),
                          ),
                          if (profile.hasSecretPhrase)
                            TextButton(
                              onPressed: _clearSecretPhrase,
                              child: Text('Kodu kaldır',
                                  style: GoogleFonts.poppins(color: Colors.redAccent.withValues(alpha: 0.8), fontSize: 12)),
                            ),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildMemorySection() {
    final memoriesAsync = ref.watch(memoryNotifierProvider);

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionTitle('Hafızam'),
        Text(
          'Aura senin hakkında bunları hatırlıyor. İstemediğini silebilirsin.',
          style: GoogleFonts.poppins(fontSize: 12, color: Colors.white54),
        ),
        const SizedBox(height: 12),
        memoriesAsync.when(
          loading: () => const Padding(
            padding: EdgeInsets.symmetric(vertical: 16),
            child: Center(child: CircularProgressIndicator(color: _indigoColor)),
          ),
          error: (err, st) => Text('Hafıza yüklenemedi: $err', style: GoogleFonts.poppins(color: Colors.white54, fontSize: 12)),
          data: (memories) {
            if (memories.isEmpty) {
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: Text(
                  'Henüz hiçbir şey hatırlamıyor.',
                  style: GoogleFonts.poppins(color: Colors.white38, fontSize: 12),
                ),
              );
            }
            return Column(
              children: [
                // "Kök ve Dal" - kullanici istegi uzerine eklendi
                // (2026-08-26): duz liste yerine, hafizanin kategorilere
                // gore nasil dagildigini ve ne kadar buyudugunu gosteren
                // buyuyen bir agac. Liste ASLA kaldirilmadi (silme islevi
                // hala gerekli) - agac SADECE bir gorsel ozet, ustune.
                _card(child: MemoryTreeWidget(memories: memories)),
                const SizedBox(height: 16),
                ...memories.map((memory) {
                final label = _categoryLabels[memory.category.toLowerCase()] ??
                    _prettifyCategory(memory.category);
                return Container(
                  margin: const EdgeInsets.only(bottom: 8),
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 4),
                  decoration: BoxDecoration(
                    color: _bgColor,
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: _borderColor),
                  ),
                  child: ListTile(
                    dense: true,
                    contentPadding: EdgeInsets.zero,
                    title: Text(memory.memoryValue, style: GoogleFonts.poppins(color: Colors.white, fontSize: 13)),
                    subtitle: Text(label, style: GoogleFonts.poppins(color: Colors.white38, fontSize: 11)),
                    trailing: IconButton(
                      icon: const Icon(Icons.delete_outline, color: Colors.white38, size: 20),
                      tooltip: 'Unut',
                      onPressed: () => _deleteMemory(memory),
                    ),
                  ),
                );
              }),
              ],
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
      backgroundColor: _bgColor,
      appBar: AppBar(
        backgroundColor: _bgColor,
        elevation: 0,
        title: Text('Ayarlar', style: GoogleFonts.poppins(color: Colors.white, fontWeight: FontWeight.w600)),
        iconTheme: const IconThemeData(color: Colors.white),
      ),
      body: profileAsync.when(
        loading: () => const Center(child: CircularProgressIndicator(color: _indigoColor)),
        error: (err, st) => Center(
          child: Text('Hata: $err', style: GoogleFonts.poppins(color: Colors.white54)),
        ),
        data: (profile) {
          if (profile == null) {
            return const Center(child: CircularProgressIndicator(color: _indigoColor));
          }
          _fillFromProfile(profile);
          return SingleChildScrollView(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _buildUsageSection(profile),
                const SizedBox(height: 24),
                _sectionTitle('Kişisel Bilgiler'),
                _card(
                  child: TextField(
                    controller: _nameController,
                    style: GoogleFonts.poppins(color: Colors.white, fontSize: 14),
                    decoration: _fieldDecoration('Adın'),
                  ),
                ),
                const SizedBox(height: 24),
                _sectionTitle('Aura Nasıl Davransın'),
                _card(
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Icon(Icons.auto_awesome, color: _indigoColor, size: 20),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          'Artık burada elle ayar yok — Aura, konuşma tarzından '
                          'sıcaklığını, resmiyetini ve mizahını kendi kendine '
                          'öğreniyor ve zamanla sana uyum sağlıyor.',
                          style: GoogleFonts.poppins(color: Colors.white70, fontSize: 13, height: 1.4),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 24),
                _buildPrivacySection(profile),
                const SizedBox(height: 24),
                _sectionTitle('Serbest Talimat'),
                _card(
                  child: TextField(
                    controller: _notesController,
                    maxLines: 4,
                    style: GoogleFonts.poppins(color: Colors.white, fontSize: 13),
                    decoration: _fieldDecoration(
                      '',
                      hint: 'Örnek: Beni şakacı bul ama iş konularında ciddi ol.',
                    ),
                  ),
                ),
                const SizedBox(height: 20),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: _save,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: _indigoColor,
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      child: Text('Kaydet', style: GoogleFonts.poppins(fontWeight: FontWeight.w600, color: Colors.white)),
                    ),
                  ),
                ),
                const SizedBox(height: 32),
                _buildMemorySection(),
                const SizedBox(height: 32),
                Center(
                  child: TextButton.icon(
                    onPressed: _loggingOut ? null : _confirmLogout,
                    icon: _loggingOut
                        ? const SizedBox(
                            width: 14, height: 14,
                            child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white38),
                          )
                        : const Icon(Icons.logout, size: 18, color: Colors.white38),
                    label: Text('Çıkış yap', style: GoogleFonts.poppins(color: Colors.white38, fontSize: 13)),
                  ),
                ),
                const SizedBox(height: 24),
              ],
            ),
          );
        },
      ),
    );
  }
}
