# Yuvarlanan Konusma Ozeti — Tasarim Notu

**Durum:** TASLAK — kullanici onayi bekliyor. Kod YAZILMADI.
**Tarih:** 2026-09-10
**Sebep:** Kullanici geri bildirimi — "uzun konusmalarda sorunlar var". Aura ayni
oturumda ~10 turdan eskisini unutup sordugunu tekrar soruyor, kendiyle celisiyor.

---

## Sorun (kod incelemesinden)

- `main.py` `MAX_HISTORY_MESSAGES` (su an 30) — modele SADECE son bu kadar ham
  mesaj gidiyor. Oncesi, uzun-donem hafizaya **cikarilmadiysa** yok.
- Hafiza sistemi (`aura_brain.extract_memory_candidate`) **gercekleri** tutuyor
  ("Izmir'de yasiyor"), **konusma iplikini** degil ("15 turdur X kararini
  tartisiyoruz, kullanici Y'ye karsi cikti, ben Z onerdim").
- `aura_brain.get_context_summary()` SADECE ruh hali donduruyor. 30-mesaj
  penceresi ile konusmanin geri kalani arasinda **hicbir kopru yok**.

## Cozum

Her N turda bir, canli pencerenin DISINDA kalan mesajlari kompakt bir
"buraya kadarki konusmanin ozeti" metnine sikistir, kalici sakla, sistem
talimatina enjekte et. Standart uzun-baglam deseni.

---

## Sema (users tablosu — mevcut migration listesine ekle)

```sql
ALTER TABLE users ADD COLUMN conversation_summary TEXT DEFAULT ''
ALTER TABLE users ADD COLUMN conversation_summary_upto INTEGER DEFAULT 0
```

- `conversation_summary` — serbest metin, Aura'nin sesinden DEGIL, notr 3.
  sahis "brief" ("Kullanici ... anlatti. ... karari tartisildi. Kullanici
  ...'e karsi cikti.").
- `conversation_summary_upto` — bu ozet uretilirken kapsanan TOPLAM
  (gorunur) mesaj sayisi. Yenileme tetikleyicisi bununla karsilastirilir.

`db_compat.py` cift-mod: iki ALTER de idempotent kaliba uyar (SQLite'ta
try/except, PG'de `ADD COLUMN IF NOT EXISTS` — mevcut desen).

---

## Akis (`_process_chat_message`, `chat_stream` ayni)

Bugunku sira korunur; iki degisiklik:

### 1. Ozeti OKU + enjekte et (her tur, ucuz)

`build_system_instruction(user, message_count)` cagrisina `user` zaten
gidiyor — `user["conversation_summary"]` oradan okunur. `build_system_instruction`
icinde, `get_context_summary()` ciktisinin YANINA (yerine degil) eklenir:

```
[BURAYA KADARKI KONUSMANIN OZETI]: <conversation_summary>
Bu ozeti arka plan olarak kullan; icinden alinti yapma, "ozete gore" deme.
```

Bos ise hic eklenmez (davranis bugunkiyle ayni).

### 2. Ozeti YENILE (post-reply, latency'ye DOKUNMAZ)

Yanit kullaniciya donduRUKTEN sonra, tam olarak `extract_memory_candidate`
cagrisinin yaninda (o da post-reply, bloklamiyor):

```python
if (not hidden_now
        and AURA_SUMMARY_ENABLED
        and message_count > MAX_HISTORY_MESSAGES
        and message_count - (user.get("conversation_summary_upto") or 0) >= SUMMARY_REFRESH_EVERY):
    aura_brain.refresh_conversation_summary(user["id"], message_count)
```

`refresh_conversation_summary`:
1. `older = database.get_messages(user_id, include_hidden=False)[:-MAX_HISTORY_MESSAGES]`
   — **DIKKAT: `include_hidden=False` SABIT** (asagida "Gizli mod" bolumu).
2. Onceki `conversation_summary` + `older`'in ham metnini birlestir, tek
   LLM cagrisi ile "guncellenmis ozet" uret (ucuz model: Groq `GROQ_MODEL`
   ya da Gemini flash; `_run_background_extraction` deseni — once biri,
   coker/bos donerse digeri).
3. Ozet uzunlugu tavan: ~1200 karakter (prompt sismesin). Prompt'ta
   "eskiyen, artik gecerli olmayan detaylari at, degismeyen onemli
   baglami koru" talimati.
4. `database.update_user(user_id, conversation_summary=..., conversation_summary_upto=message_count)`.
5. Her hata sessizce yutulur + `metrics.record("conversation_summary", ok=False, ...)`
   (Sentry'ye de gider — `observability` koprusu zaten var).

Bu turda KULLANILAN ozet, bir onceki yenilemeden — en fazla
`SUMMARY_REFRESH_EVERY` tur bayat. Kabul edilebilir (ozet zaten kaba baglam).

---

## Gizli mod (KRITIK — privacy landmine)

Bugun `get_context_summary` mood-only oldugu icin gizli modla etkilesimi YOK.
Konusma ozeti bu bagisikligi KAYBEDER. Kurallar:

1. Ozet **HER ZAMAN** `include_hidden=False` mesajlardan uretilir. Gizli
   modda soylenenler ozete ASLA girmez — mod sonradan kapansa bile.
2. Dolayisiyla ozet, gizli mod AKTIFKEN de guvenle enjekte edilebilir
   (icinde gizli icerik yok). Ama tutarlilik icin: gizli mod aktifken
   ozet yenilemesi ATLANIR (`not hidden_now` kosulu yukarida) — gizli
   oturum ortasinda notr ozet guncellemek gereksiz.
3. Test: gizli modda 20 mesaj konus -> moddan cik -> ozetin o 20 mesajdan
   HICBIR iz tasimadigini `/api/... ` ya da DB ile dogrula.

---

## Sesli gorusme (`aura_voice.py`)

`build_system_instruction` orada da cagriliyor -> ozet OTOMATIK enjekte
olur (okuma tarafi bedava). Yenileme tarafi: `persist_transcripts` zaten
`extract_memory_candidate` cagiriyor, ayni kosulla `refresh_conversation_summary`
oraya da eklenir. `session_resumption` ile uzun aramada yeniden baglaninca
ozet DB'den tazece okunur — "yarim duydu" hissi azalir.

---

## Maliyet

- Ek LLM cagrisi: kullanici basina her `SUMMARY_REFRESH_EVERY` (oneri: 12)
  turda 1. Girdi ~ (onceki ozet 1200 krkt + ~12-20 mesaj). Ucuz modelde
  ihmal edilebilir (~$0.0001-0.0005/cagri).
- Post-reply oldugu icin kullanici gecikmesine **sifir** etki.
- Kapali kalabilir: `AURA_SUMMARY_ENABLED` (env, varsayilan `1` onerilir ama
  ilk hafta `0` ile cikip gozlemlenebilir).

## Ayarlar (env)

| Env | Varsayilan | Ne |
|---|---|---|
| `AURA_SUMMARY_ENABLED` | `1` | Ozelligi ac/kapa |
| `AURA_SUMMARY_REFRESH_EVERY` | `12` | Kac turda bir yenile |
| `AURA_SUMMARY_MAX_CHARS` | `1200` | Ozet uzunluk tavani |

## Geri donus

`AURA_SUMMARY_ENABLED=0` — okuma+yenileme ikisi de durur. Kolonlar zararsiz
kalir. Tam temizlik gerekmez.

---

## Ilgili sonraki adimlar (bu nottan AYRI)

- `memory_context` tavani/onceliklendirme — ilişki yaslandikca prompt
  sismesi (build_system_instruction tum hafiza satirlarini basıyor).
- Prompt token boyutunu logla (metrics/Sentry gorunurluguyle esles).
- Stil vektoru: `STYLE_EMA_ALPHA=0.15` cok yumusak, tek `haha` humor'u
  0.55'e tasir (latch DEGIL). Ayrica kod "sessizlik != notr" kararini
  ACIKCA savunuyor -> decay EKLEME. "civik" temperature+LAUBALILIK_SINIRI
  sonrasi hala varsa yeniden bak.
