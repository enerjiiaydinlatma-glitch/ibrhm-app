# Aura Pro: satın alma (ödeme) akışı planı (TASLAK, onay bekliyor)

Durum: **kod yazılmadı.** Bu belge bugünkü durumu, dış kuralları, verilmesi gereken kararları ve önerilen
mimariyi içerir. Karar verilmeden uygulamaya geçilmez. Hukuki/mali konular için avukat ve mali müşavir
görüşü şart; bu belge hukuki tavsiye değildir.

## 1. Bugün (koddan doğrulanan)

| Konu | Durum |
|---|---|
| Seviye | `users.tier` metin alanı: `'free'` / `'pro'`. Yalnızca admin ucu `POST /api/admin/set-tier` (`ADMIN_KEY`) değiştiriyor. |
| Ödeme kodu | **Yok.** Ne sunucuda ne istemcide ödeme/abonelik kodu var; `pubspec.yaml`'da ödeme paketi yok. |
| Pro neleri açıyor | Günlük **30 mesaj** sınırı yok; TTS günlük sınırı yok; tek-cihaz oturum kuralı yok. |
| Sesli görüşme | Free: **10 dk/gün**. Pro: **90 dk/gün** tavan (`VOICE_PRO_DAILY_LIMIT_SECONDS = 5400`). |
| Veri modeli | **Bitiş tarihi yok** (tier kalıcı), ödeme kaydı tablosu yok, sağlayıcı müşteri/abonelik kimliği yok, iptal/yenileme durumu yok. |
| Yükseltme arayüzü | **Yok.** Limit dolunca "yarın sıfırlanacak" mesajı çıkıyor, satın alma yönlendirmesi bilerek yok (`LIMIT_REACHED_REPLY` yorumu). |
| Hesaplar | Uygulama ilk açılışta **anonim hesap** açıyor (e-postasız). Ödeme yapan anonim kullanıcı hesabını kaybederse Pro'yu da kaybeder; `/api/auth/claim` ucu var. |
| Yasal metinler | `legal.py` Kullanım Şartları'nda ücretli hizmet, fiyat, iade, cayma, abonelik iptali bölümü **yok**; yalnızca sorumluluk üst sınırı cümlesi ("fiilen ödediğin tutarla, ücretsiz kullanımda sıfır"). |
| Platformlar | Repoda Android (`com.auraapp.assistant`), iOS, web (`/app`), Windows/macOS/Linux klasörleri var. **Hangilerinin gerçekten yayında olduğunu bilmiyorum.** |

### Tutarsız / yanıltıcı metinler (ödemeden bağımsız, satıştan ÖNCE düzeltilmeli)
- `lib/core/i18n.dart` → `settings.proNoLimit`: *"Pro hesap - günlük kullanım sınırın yok."* **Yanlış:** Pro'da sesli görüşme 90 dk/gün ile sınırlı.
- `store_assets/STORE_LISTING.md`: *"sınırsız kullanım için Pro sürümüne geçebilirsin."* Aynı sorun ("sınırsız" doğru değil) ve henüz satın alma yolu da yok.

### Maliyet riski (ölçülmedi)
`aura_voice.py` içindeki 2 Eylül notuna göre Gemini Live sesli görüşme ≈ **dakikada 0,10-0,30 USD**
(güncel olduğu doğrulanmadı). Pro'nun 90 dk/gün tavanı tam kullanılırsa teorik günlük 9-27 USD, aylık
270-810 USD eder: **tek bir yoğun kullanıcı aboneliğin gelirini aşabilir.** Fiyat belirlenmeden önce gerçek
maliyet ölçülmeli ve sesli tavan yeniden düşünülmeli.

## 2. Dış kurallar (resmî kaynaklardan, sınırlarıyla)

- **iyzico abonelik:** ürün → ödeme planı → abonelik. "Initialize Subscription" ile Checkout Form başlatılıyor
  (plan referans kodu, müşteri bilgisi, durum `ACTIVE`/`PENDING`, callback URL). Yönlendirme ödemeden hemen sonra
  olur; ödemenin alındığı **ayrıca sorgulanmalı**. Kart doğrulaması 1 TL çekim + iade ile yapılabiliyor.
  *Doğrulanmadı:* abonelik ürününün ücreti/ek onay gerekip gerekmediği (bir sayfada "ilk 3 ay ücretsiz, sonra 199 TL" yazıyor, güncel olmayabilir).
- **iyzico webhook:** HTTP POST, imza başlığı `X-Iyz-Signature-V3` (V1/V2 desteklenmeyecek), 15 dk arayla en fazla 3 deneme.
  *Doğrulanmadı:* abonelik yaşam döngüsü olayları ve yük yapısı (dokümantasyon sayfasını okuyamadım).
- **Google Play:** Play'de dağıtılan uygulamalarda dijital mal/abonelik satışı için **Play Faturalandırma zorunlu**
  (resmî Play Console yardım sayfası). Güncel değişiklikleri ayrıca kontrol etmedim.
- **Apple App Store (Guideline 3.1.1):** uygulama içinde erişilen dijital abonelik **uygulama içi satın alma (IAP)** ile satılmalı.
  Haberlere göre ABD mağazasında dış satın alma bağlantıları 2025'ten beri serbest, diğer ülkelerde eski kural geçerli. Resmî sayfayı okuyamadım.

**Sonuç:** iyzico ile tahsilat, **web** için doğal çözüm. Mobil mağaza sürümlerinde uygulama içinden iyzico ile Pro satmak
mağaza kuralını ihlal edebilir (hesap/uygulama riski). Mobilde ne yapılacağı ayrı bir karar ve mağaza politikası kontrolü ister.

## 3. Karar listesi (benim önerimle)

| # | Karar | Öneri |
|---|---|---|
| K1 | Nerede satılsın? | **Yalnızca web'de** (iyzico). Mobil uygulamaya satın alma düğmesi/bağlantısı **koyma**; mobil için mağaza kuralları ayrıca incelenip karar verilsin. |
| K2 | Model | **Küçük başla:** tek seferlik **30 günlük Pro paketi** (otomatik yenileme yok). Yenileme/iptal/başarısız ödeme/cayma yükü yok. Abonelik sonraki aşama. |
| K3 | Fiyat | **Önce maliyeti ölç**, sonra TL fiyat belirle. Sesli tavan (şu an 90 dk) fiyatın altında kalacak şekilde düşürülsün ya da sesli ayrı kota olsun. |
| K4 | Pro vaadi | "Sınırsız" kelimesi kullanılmasın; metin ve sesli için net sayılar yazılsın; ilgili iki yanıltıcı metin düzeltilsin. |
| K5 | Yasal/vergi | Mesafeli satış sözleşmesi + ön bilgilendirme, cayma/iade, fatura/e-arşiv, KDV, KVKK/gizlilik güncellemesi, iyzico üye iş yeri başvurusu (şahıs/şirket). **Avukat/mali müşavir.** |
| K6 | Anonim hesap | Ödemeden **önce** hesabı e-postaya bağlamayı zorunlu kıl (`/api/auth/claim`), yoksa ödeme yapan kullanıcı hesabıyla birlikte Pro'yu kaybedebilir. |

## 4. Önerilen mimari (uygulanmadı)

- **Veri:** `users.pro_until` (zaman damgası); `payments` tablosu (kullanıcı, sağlayıcı, sağlayıcı referansı/token, tutar, para birimi, durum, zaman, olay özeti); tekrar eden olaylar için **idempotency**.
- **Pro denetimi:** dağınık `user.get("tier") != "pro"` kontrolleri tek bir `user_is_pro(user)` yardımcısına taşınır; Pro = `tier == 'pro'` (manuel admin) **veya** `pro_until > şimdi`. `set-tier` manuel yol olarak kalır.
- **Uçlar:** `POST /api/billing/checkout` (kimlikli): iyzico Checkout Form başlatır. **Callback'e değil, iyzico'ya sunucudan sorarak** ödemeyi doğrular, başarılıysa `pro_until` uzatır. `POST /api/billing/webhook`: imza (`X-Iyz-Signature-V3`) doğrulanır, idempotent işlenir.
- **Güvenlik:** kart verisi bizim sunucudan **geçmez** (Checkout Form), `IYZICO_API_KEY/SECRET` yalnızca Railway ortam değişkeninde, önce sandbox.
- **İstemci (web):** Ayarlar → "Pro'ya geç" → checkout sayfası → dönünce durum sorgulanır.

## 5. Aşamalar
0. Kararlar (K1-K6) + yasal/vergi hazırlığı + iyzico üye iş yeri/sandbox hesabı.
1. Ödemeden bağımsız düzeltmeler: iki yanıltıcı metin, gerçek sesli maliyetin ölçülmesi, sesli tavan kararı.
2. Altyapı: `pro_until`, `user_is_pro`, `payments` tablosu, testler (mevcut davranış bozulmadan).
3. iyzico sandbox ile ödeme akışı (checkout + sunucu doğrulaması).
4. Webhook ve süre bitişi/yenileme.
5. Yasal metinler, kontrollü açılış (küçük kullanıcı grubu), izleme.

## 6. Açık sorular (cevap bekleniyor)
1. Android ve iOS uygulamaları mağazalarda **yayında mı**? Yalnızca web mi?
2. iyzico **üye iş yeri hesabın** var mı (şahıs mı, şirket mi)? Sandbox hesabı?
3. Kaç kullanıcı var, kaçı sesli görüşme kullanıyor? (Maliyet ve fiyat için.)
4. Pro için aklındaki fiyat/vaat nedir?
