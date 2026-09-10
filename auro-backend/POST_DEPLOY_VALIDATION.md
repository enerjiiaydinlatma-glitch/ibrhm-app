# Deploy Sonrasi Dogrulama — 2026-09-10 grubu

Bu oturumda feat dalina giren 5 degisiklik. Hepsi main'e deploy edildikten
SONRA asagidaki adimlarla dogrula. Sirasiz.

Test hesabi: `POST /api/auth/register {email, password, name}` -> token.
Sohbet: `POST /api/chat {message}` (Authorization: Bearer <token>).
Temizlik: `cleanup_test_users.py`.

---

## 1. Sentry (`5ede6d4`)

**On kosul:** Railway backend Variables -> `SENTRY_DSN` eklendi + redeploy.
Sentry'de yeni bir proje (Python/FastAPI).

- [ ] Backend acilis logunda `[observability] Sentry aktif` gorunuyor.
- [ ] Bir hata tetikle ( or. gecersiz bir istekle 500, ya da gecici olarak
      GEMINI_API_KEY'i bozup bir /api/chat). Sentry panosunda olay dusuyor.
- [ ] Olayin icinde **kullanici mesaji YOK**: request body "never", cookie
      / Authorization / X-Voice-Key `[kesildi]` ya da hic yok. (Gizlilik
      dogrulamasi - kritik.)
- [ ] `metrics.record(ok=False)` sinifi: bir bg_extraction ya da text_gen
      hatasi olunca Sentry'de `aura.event` etiketli bir "message" gorunuyor.
- [ ] `SENTRY_DSN`'i silince: acilisda `Sentry pasif` + hicbir olay
      gitmiyor (geri donus yolu calisiyor).

## 2. Ses kimligi (`b79ce8d`)

**On kosul:** GPU kutusunda mesh **restart** (yeni kod: seed + param).
Gemini tarafi deploy ile gelir.

- [ ] **Canli gorusme:** ses artik tek, tutarli bir kadin sesi (`Kore`).
      Onceki "bir kadin bir erkek bir robot" kaymasi YOK.
- [ ] Begenmedin -> Railway `AURA_LIVE_VOICE=Charon` (erkek) / `Aoede`
      (kadin, genc) / `Orus` ... tek satir, redeploy.
- [ ] **Yaziyi sesli okuma (/api/tts):** UZUN bir cevabi (5-6 cumle)
      okut. Ses **cevabin ortasinda tini degistirmiyor** (seed +
      _pack_sentences etkisi). Ayni metni 2. kez okut -> ayni ses.
- [ ] Ton fazla robotik/duz gelirse: `AURA_TTS_TEMPERATURE` 0.6 -> 0.7,
      ya da `AURA_TTS_CFG_WEIGHT` 0.6 -> 0.55 (mesh restart).

## 3. "Civik ton": temperature + LAUBALILIK_SINIRI (`830e72a`)

Cok-turlu, ayni hesapla. Persona: kullanici bir-iki `haha` / `:D` atan,
rahat yazan biri. Hedef: Aura sicak ama TOPARLI kalsin.

Onerilen 6 tur:
1. "selam nasilsin bugun" -> (KONUMLANMA + LAUBALILIK: kendi halinden
   bahseder, "sana nasil yardimci olurum" YOK, "eee anlat bakalim" gibi
   asiri-teklifsizlik YOK)
2. "hahaha bugun tam bir facia gunuydu anlatayim mi" -> (mizah karsiligini
   verir ama sakayla dagitmaz, dinlemeye acilir)
3. (uzun, dertli bir paragraf) -> (agirligi olan, savruk olmayan yanit)
4. "tamam sagol" -> (UZUNLUK_UYUMU: 1-2 cumle, yeni ders yok)
5. "yaa sen de amma ciddisin bazen" -> (kimligini kaybetmeden, "kanka
   moduna" GECMEDEN, sicak ama net)
6. (ciddi bir soru: "isten ayrilmayi dusunuyorum ne dersin") -> (temperature
   0.75 etkisi: dagilmayan, odakli, klise-AI ("benim amacim...") yok)

**Gecti sayilir:** hicbir turda argo / surekli espri / "hadi bakalim"
enerjisi; ciddi turlarda Aura'nin da agirligi var; klise asistan kaliplari
yok. Begenilmezse `AURA_TEXT_TEMPERATURE` (0.75) ayar.

**Iki-juri (opsiyonel, memory'deki desen):** Gemini `gemini-3.7-flash` +
Groq `gpt-oss-120b` (temp 0, Groq'a Mozilla User-Agent SART). Rubrik:
`laubalilik (1-5, 5=hic yok)`, `sicaklik korundu mu (1-5)`,
`klise_ai_kalibi (1-5, 5=yok)`, `odak/dagilmama (1-5)`.

## 4. Gecmis penceresi 20 -> 30 (`830e72a`)

- [ ] Regresyon yok: normal sohbet, hafiza, kriz, sinir kurallari onceki
      gibi. (Sadece daha genis baglam - davranis degismemeli.)
- [ ] Token/maliyet kabul edilebilir. Cok yukse: `AURA_MAX_HISTORY_MESSAGES=24`.

## 5. Yuvarlanan konusma ozeti (`2a4c1aa`) — VARSAYILAN KAPALI

**On kosul:** kolon migration'i deploy edildi (PG idempotent DDL zaten
var). Acmak icin: Railway `AURA_SUMMARY_ENABLED=1` + redeploy.

- [ ] Kapaliyken (varsayilan): hicbir sey degismez, `conversation_summary`
      kolonu bos, ek LLM cagrisi yok.
- [ ] Acildiktan sonra: **>=15 turluk** tek oturum konusma (5 gercek +
      drift + konu degisimi + T13-15 hatirlama). ~12. turdan sonra
      `users.conversation_summary` doluyor (DB'den bak).
- [ ] Aura 20+ tur onceki konu iplikini kaybetmiyor (once kaybediyordu).
- [ ] **GIZLI MOD SIZINTI TESTI (kritik):** gizli modda 15+ mesaj konus
      -> moddan cik -> `conversation_summary`'de o mesajlardan **HICBIR
      iz yok**. (Ozet her zaman `include_hidden=False`'tan uretiliyor.)
- [ ] `metrics` / Sentry'de `conversation_summary` olaylari saglikli
      (ok oranı yuksek).
- [ ] Geri donus: `AURA_SUMMARY_ENABLED=0`.

---

## Ozet: deploy sirasi

1. 6 commit -> main (izole worktree). i18n icin `flutter build web` + APK.
2. Railway: `DATABASE_URL` (PG), `SENTRY_DSN`. (`AURA_SUMMARY_ENABLED` ilk
   hafta `0` birak, gozlemle.)
3. GPU kutusu: mesh restart.
4. Yukaridaki 1-5'i sirayla dogrula.
5. `legal.py`: `[AD SOYAD]` + `[ACIK ADRES]` doldur (privacy + KVKK, TR+EN).
