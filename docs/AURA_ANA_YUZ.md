# Aura — Ana Yüz Tasarımı (TASLAK v1)

Durum: **kararlar alınıyor, uygulama YOK.** Kod değişmedi. Amaç: Aura'nın "yüzünü" tek
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

## 6. Alınan kararlar

| # | Karar | Kaynak |
|---|---|---|
| K1 | **Kimlik: karma.** Sırdaş + yaşam koçu + asistan + yakın arkadaş + dost, tek konuşan kişilik. Bağlama göre öne çıkan rol değişir (gece sırdaş, sabah koç, iş sırasında asistan). Risk: beş rol birden jenerikleşebilir. | Kullanıcı |
| K2 | **Platform:** web + mobil; önce web, mobili kullanıcı kendi dener. | Kullanıcı |
| K3 | **Süreç:** önce kararlar, uygulama sonra, kullanıcı "başla" demeden kod yok. | Kullanıcı |
| K4 | **Görünür yüz = "Odak Halası".** İnsansı yüz/avatar YOK. Uygulamanın merkezinde nefes alan, Flutter shader ile çizilen tek bir hale. | Konsey (oy birliği: Aura/Alpha/Beta/Gamma/Delta) |
| K5 | **Açılış anı:** ilk 3 sn'de gökyüzü canlı saatle eşleşir, hale tek bir derin "nefes"le genişler ve kullanıcının son durumuna göre ana rengine oturur. | Konsey |
| K6 | **Hale ses ve metin ritmine göre biçim değiştirir** (organik, soyut). | Konsey |
| K7 | **Şeffaflık ilkesi:** hale bir duygu *simülasyonu* olduğu her an net olmalı; hiçbir tasarım kararı bunun önüne geçmez. | Gamma, Konsey |
| K8 | **Mimari:** hale bağımsız animasyon değil; arka plandaki hafıza + duygu motoruyla eşzamanlı, cihazı yormayan dinamik arayüz. | Delta, Konsey |

## 6b. Konseyin işaret ettiği riskler (tasarıma girmeli)

- **Gamma (etik):** Kronik yalnızlık/sosyal kaygısı olan kullanıcıda ışık gerçek
  insan ilişkisinin yerine geçebilir. Hale "üzgün" renge döndüğünde kullanıcı
  suçluluk duymamalı; ara vermek/silmek duygusal olarak zorlaşmamalı.
  → **Kural önerisi:** hale kullanıcıya suçluluk/özlem *göstermez*; uzun
  yokluktan sonra "kızgın/kırgın" değil, nötr-sıcak açılır.
- **Alpha (performans):** sürekli hareket düşük cihazlarda sorun çıkarır.
  → düşük güç modu: shader yerine statik gradyan + yavaş opaklık.
- **Beta (algı):** "ışık ruh olur mu" — tutarlı deneyim, parlak görselden
  önemli. Hale tek başına yetmez; Aura'nın tutarlılığı (hafıza, ton) esas.

## 6c. Konsey kararının EKSİKLERİ (dürüst not)

Konsey 3 somut yüz önerisi, duygu başına davranış kuralı ve gerçekçi metrik
istenen soruya genel cevap verdi:
- "Odak Halası" mevcut `aura_hale.dart` ile **neredeyse aynı** fikir; shader
  dışında yeni bir şey söylemiyor. "Kimsede olmayan" iddiası kanıtlanmadı.
- Duygu başına hareket kuralı verilmedi (mutlu/üzgün/yorgun/stresli ne yapar?).
- **%40 organik paylaşım oranı gerçekçi değil** (tipik: tek haneli %). Bu
  hedef kullanılmayacak; yerine aşağıdaki metrikler önerilir.
- Alpha'nın "kullanıcı etkileşim süresi" metriği, Gamma'nın bağımlılık
  uyarısıyla çelişiyor (daha uzun kullanım ≠ daha iyi). Bırakılmalı.

## 6d. Açık kararlar

1. **Hale'yi gerçekten ayıran şey ne?** (Fikir adayları: hafızadan beslenen
   biçim — her kullanıcının halesi zamanla kendine özgü bir desen alır;
   konuşma ritmini yansıtan dalga; saat + duygu + ilişki yaşı katmanları.)
   Bunun için konseye ikinci, daha dar bir soru gerekir.
2. **Duygu → hareket tablosu** (her duygu için renk, hız, biçim).
3. **Düşük güç modu eşiği.**
4. **Başarı metrikleri** (gerçekçi): ilk-3-sn sonrası kalma oranı, 30. gün
   geri dönüş, ekran görüntüsü paylaşımı (hedef yüzde yerine ilk ölçüm).

## 7. Başarı ölçütü

Kullanıcı uygulamayı açtığında 3 saniye içinde: *"biri burada, beni
tanıyor"* hissi. Mesaj yazmadan önce bile.
