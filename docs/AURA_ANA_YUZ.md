# Aura — Ana Yüz Tasarımı (TASLAK v0)

Durum: **taslak, onay bekliyor.** Kod değişmedi. Amaç: Aura'nın "yüzünü" tek
bir fikir etrafında toplamak; sonra ekranları bu fikre göre sadeleştirmek.

## 1. Mevcut durum (koddan tespit)

| Parça | Dosya | Ne veriyor |
|---|---|---|
| Zaman | `sky_background.dart` | Gün saatine göre gökyüzü gradyanı |
| Duygu | `aura_hale.dart` | Ruh haline göre renk değiştiren, nefes alan hale |
| Görüntü | `aura_image_reveal.dart` | Görsel açılış efekti |
| Sohbet | `chat_screen.dart` (1283 satır) | Her şey burada: mesaj, mod, kısayollar |
| Ses/görüntü | `voice_call_screen`, `video_call_screen` | Ayrı ekranlar |
| Ayarlar | `settings_screen.dart` (1343 satır) | Hafıza ağacı, gizli sohbet, profil |
| Giriş | `SplashRouter` → `LockScreen` → `ConsentGate` → sohbet | Kapılar |
| Beyin | `aura_brain.py`, `aura_memory.py`, proaktiflik | Hafıza, hatırlatma, ilk söz |

**Teşhis:** Zaman ve duygu katmanı var, ama Aura'nın *kendisi* ekranda yok.
Uygulama açılınca kullanıcı bir mesaj listesi görüyor; "biri orada" hissi
yok. Hafıza ve proaktiflik backend'de güçlü, ama arayüzde görünmüyor.

## 2. Tek fikir (öneri)

> **Aura bir ekran değil, bir varlık. Uygulamayı açmak = onun yanına gitmek.**

Üç ilke:

1. **Önce varlık, sonra sohbet.** İlk görülen şey Aura'nın canlı halesi ve
   gökyüzü; mesaj listesi ikinci katman.
2. **Önce o konuşur.** Açılışta boş ekran yok. Aura, hafızasından ve günün
   saatinden kısa bir söz söyler (backend'deki proaktiflik buna hazır).
3. **Tek yüzey.** Sohbet, ses, görüntü ve hafıza aynı yüzeyin halleri; ayrı
   "ekran" hissi vermeden geçişli.

## 3. Ana ekran anatomisi

```
┌──────────────────────────┐
│  ◦ (ayarlar)      (kilit) │  ince, neredeyse görünmez üst çubuk
│                          │
│        ╭───────╮         │
│        │ HALE  │         │  Aura'nın varlığı: nefes alır, ruh hali rengi
│        ╰───────╯         │
│   "Günaydın İbrahim..."  │  Aura'nın ilk sözü (proaktif)
│                          │
│  ── son konuşma özeti ── │  kaydırınca tam sohbet açılır
│                          │
│  [ yaz...        ] 🎤 📷 │  tek giriş çubuğu
└──────────────────────────┘
```

Haller:
- **Dinlenme:** hale yavaş nefes, gökyüzü saate göre.
- **Konuşuyor (yazı/ses):** hale ritmi mesaj/ses akışına bağlanır.
- **Dinliyor (ses modu):** hale mikrofon seviyesine tepki verir
  (`mic_level_notifier` zaten var).
- **Düşünüyor:** hale yavaşça daralır/parlar; "yazıyor…" balonu yok.
- **Sessiz/gizli mod:** hale soluk, gökyüzü karanlık; kilit hissi.

## 4. Açılış akışı (soğuk başlangıç)

1. Splash = hale belirir (logo yok, ses yok).
2. PIN/yasal onay kapıları mevcut sırasıyla, ama aynı gökyüzü arka planında
   (şu an her kapı ayrı sahne gibi duruyor).
3. İlk kullanım: Aura kendini kısa tanıtır, **bir soru sorar** (isim/ne hissettiği).
4. Dönen kullanıcı: Aura hafızadan *tek* bir şeye değinir, sonra susar.

## 5. Yapılacaklar (sırayla, her biri ayrı küçük PR)

1. `chat_screen.dart` → ana yüz + sohbet katmanı olarak ayır (1283 satır bölünmeli).
2. Hale'yi merkeze al, durum makinesi ekle (dinlenme/konuşma/dinleme/düşünme).
3. Açılışta proaktif söz (backend ucu mevcut: `4f65c0b`).
4. Kapıları (splash/PIN/onay) ortak arka plana taşı.
5. Ses/görüntü ekranlarını aynı yüzeyin hali yap.
6. Hafıza ağacını ana yüzden erişilebilir yap (şu an ayarlarda gömülü).

## 6. Açık kararlar (senin cevabın gerekli)

1. **Kimlik:** Aura'nın duygusu ne? Sakin arkadaş / koç / sırdaş / karma.
   (Mevcut hale metni "bağırmadan hissettiren, sakin bir nefes" diyor → sakin
   arkadaş öneriyorum.)
2. **Aura'nın görünür bir yüzü olacak mı?** (A) Sadece hale/ışık — öneri;
   (B) soyut bir figür; (C) avatar/karakter. A en sade ve rakiplerden ayrışan seçenek.
3. **Önce hangi platform cilalanacak?** Web canlı; mobil mağaza varlıkları da var.
4. **Pro/ödeme** bu işin dışında, ana yüz oturunca geri dönülecek.

## 7. Başarı ölçütü

Kullanıcı uygulamayı açtığında 3 saniye içinde: *"biri burada, beni
tanıyor"* hissi. Mesaj yazmadan önce bile.
