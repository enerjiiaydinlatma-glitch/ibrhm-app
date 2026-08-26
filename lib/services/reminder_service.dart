import 'package:flutter/foundation.dart' show kIsWeb, debugPrint;
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:timezone/data/latest_all.dart' as tz_data;
import 'package:timezone/timezone.dart' as tz;

/// Kullanici istegi (2026-08-26): "haftaya persembe maca gidecegim,
/// bilet almam lazim, hatirlatma alarmi olabilir mi?" - backend tarafi
/// (aura_reminders.py) mesajlardan tarih+hazirlik cikarip /api/reminders
/// altinda saklıyor; bu servis o listeyi cekip HER birini cihazda yerel
/// bir bildirim olarak zamanliyor.
///
/// DURUST NOT: bu GERCEK bir OS bildirimi (push degil, TAMAMEN yerel -
/// sunucu/Firebase gerektirmiyor). Android'de guvenilir calisir. Windows'ta
/// (flutter_local_notifications_windows, WinRT toast) calisiyor OLMASI
/// gerekir ama bu uygulama bir MSIX yukleyici ile kurulmadigi (dogrudan
/// .exe olarak calistigi) icin bazi Windows ozellikleri (iptal etme,
/// aktif bildirimleri listeleme) sinirli olabilir - GOSTERME kismi
/// etkilenmemeli ama canli test edilmeden %100 garanti verilmiyor. Web'de
/// hic denenmiyor (kIsWeb ile atlaniyor).
class ReminderService {
  ReminderService._();
  static final ReminderService instance = ReminderService._();

  final FlutterLocalNotificationsPlugin _plugin = FlutterLocalNotificationsPlugin();
  bool _initialized = false;
  bool _available = false;

  // Hatirlatmalar sadece bir TARIH tasiyor (saat degil) - gunun bu
  // saatinde gosteriliyor. Sabah erken degil, ama gunun cogu bolumunu
  // kacirmayacak makul bir varsayilan.
  static const int _defaultHour = 10;

  Future<void> init() async {
    if (_initialized || kIsWeb) return;
    _initialized = true;
    try {
      tz_data.initializeTimeZones();
      const androidSettings = AndroidInitializationSettings('@mipmap/ic_launcher');
      const windowsSettings = WindowsInitializationSettings(
        appName: 'Aura',
        appUserModelId: 'AuraApp.Aura.Assistant',
        guid: '113f88ff-2d1d-46bd-94f6-4bbce8f3d40f',
      );
      const settings = InitializationSettings(
        android: androidSettings,
        windows: windowsSettings,
      );
      final ok = await _plugin.initialize(settings: settings);
      _available = ok ?? true;
    } catch (e) {
      // Bildirim altyapisi kurulamadi (ornegin desteklenmeyen bir
      // platform/surum) - sessizce devre disi birak, uygulamanin geri
      // kalanini ETKILEME. Hatirlatmalar yine backend'de duruyor, sadece
      // yerel alarm olarak gosterilemiyor.
      debugPrint('ReminderService init basarisiz: $e');
      _available = false;
    }
  }

  Future<void> requestPermissions() async {
    if (!_available || kIsWeb) return;
    try {
      await _plugin
          .resolvePlatformSpecificImplementation<
              AndroidFlutterLocalNotificationsPlugin>()
          ?.requestNotificationsPermission();
    } catch (_) {
      // Android disi platformlarda bu implementasyon zaten yok - normal.
    }
  }

  /// [reminders] her biri en az {id, description, remind_at} icermeli
  /// (backend'in /api/reminders yaniti tam olarak bu sekli veriyor).
  Future<void> scheduleAll(List<Map<String, dynamic>> reminders) async {
    if (!_available || kIsWeb) return;
    for (final r in reminders) {
      final id = r['id'];
      final description = r['description'];
      final remindAtStr = r['remind_at'];
      if (id is! int || description is! String || remindAtStr is! String) {
        continue;
      }
      await _scheduleOne(id, description, remindAtStr);
    }
  }

  Future<void> _scheduleOne(int id, String description, String remindAtIso) async {
    final date = DateTime.tryParse(remindAtIso);
    if (date == null) return;

    final scheduled = tz.TZDateTime.local(date.year, date.month, date.day, _defaultHour);
    // Zaten gecmis bir saate denk geliyorsa (ornek: bugun ama saat 10'u
    // gectiyse) hemen simdi goster - sessizce atlamak yerine.
    final effective = scheduled.isBefore(tz.TZDateTime.now(tz.local))
        ? tz.TZDateTime.now(tz.local).add(const Duration(seconds: 5))
        : scheduled;

    const details = NotificationDetails(
      android: AndroidNotificationDetails(
        'aura_reminders',
        'Aura Hatırlatmaları',
        channelDescription: 'Aura ile konuşurken belirlediğin hatırlatmalar',
        importance: Importance.high,
        priority: Priority.high,
      ),
      windows: WindowsNotificationDetails(),
    );

    try {
      await _plugin.zonedSchedule(
        id: id,
        title: 'Aura hatırlatıyor',
        body: description,
        scheduledDate: effective,
        notificationDetails: details,
        androidScheduleMode: AndroidScheduleMode.inexactAllowWhileIdle,
      );
    } catch (e) {
      debugPrint('Hatirlatma zamanlanamadi (id=$id): $e');
    }
  }
}
