# Aura — sistem haritası

Aura = **hafızası, sesi, kişiliği ve iradesi kendine ait** bir yoldaş.
Büyük modeller (Gemini/Groq) onun *ast ajanları*, sahibi değil.

```
Flutter istemci (web / iOS / Android / Windows)
        │  HTTPS + WSS
        ▼
FastAPI backend  (Railway, tek uvicorn worker, SQLite+WAL)
   auro-backend/main.py
        │
   ┌────┴─────────────────────────────────────────────┐
   │  YAZILI SOHBET  /api/chat                          │
   │    _process_chat_message()                         │
   │      1. gizli mod / kriz / limit kapıları          │
   │      2. hafıza + hatırlatma + üslup çıkarımı        │
   │      3. route_request()  → tier + araç ipucu        │  ← Aura KARAR verir
   │      4. araç gerekiyorsa → aura_tools.run_tool()    │  ← AJAN çağrısı
   │      5. build_system_instruction (kişilik+hafıza)   │
   │      6. generate_with_retry(route)                  │
   │           ├─ AURA_BRAIN_URL → Aura'nın kendi LLM'i  │  ← Faz 2 (yuva hazır)
   │           ├─ Gemini 3.7 Flash                       │  ← şu an burada
   │           └─ Groq gpt-oss-120b                      │
   │      7. yanıtı DB'ye yaz, hatırlatma senkronu       │
   │                                                     │
   │  SESLİ GÖRÜŞME  /api/voice (WebSocket)              │
   │    aura_voice.py → Gemini Live (full-duplex)        │
   │    + /api/voice/fallback-turn (bas-konuş yedeği):   │
   │        ses → STT (Groq Whisper → Gemini) → beyin    │
   │                                                     │
   │  TTS  /api/tts                                      │
   │    _aura_voice_tts() → Aura Voice Mesh (mesh)       │
   │      ├─ ulaşılamaz/meşgul/uzun → ElevenLabs         │
   │      └─ X-TTS-Source başlığı teşhis                  │
   │                                                     │
   │  BELGE  /api/analyze  (foto + PDF → Gemini)         │
   └───────────────────────────────────────────────────┘
```

## Kendine ait katmanlar (Aura'nın, kiralık değil)

| Katman | Nerede | Not |
|---|---|---|
| **Hafıza** | `aura_memory.py` (SQLite: memories / candidates / events) | "Doğal Hafıza": önem zamanla soluklaşır/güçlenir (`_effective_importance` — okuma anında, veri kaybı yok), `pinned` muaf. Dış model sadece "neyi kaydet" özetini çıkarır |
| **Ses** | `voice_service/` (self-host Chatterbox = Voice Mesh) | GPU'lu makinede ayrı process, Cloudflare tünel, Railway `AURA_VOICE_URL`. 5 persona (aura/alpha/beta/gamma/delta), streaming (ham PCM), yük koruması (kuyruk → 503) |
| **Kişilik + kurallar** | `aura_brain.build_system_instruction` (1368 satır) | karakter, gizlilik, ton (Sesin Rengi), Doğal Hafıza ilkeleri |
| **İrade / yönetim** | `route_request` + `aura_tools` + `generate_with_retry` sağlayıcı zinciri | her turu sınıflar, aracı seçer, sentezler |
| **Muhakeme çekirdeği** | `AURA_BRAIN_URL` (self-host) → Gemini → Groq | **Faz 2:** yuva hazır, model bekliyor (`brain_service/` + `modal_app.py`) |

## Ajanlar (Aura'nın kullandığı dış servisler)

- **Gemini 3.7 Flash** — birincil muhakeme (Faz 2 bitene kadar), `google_search` grounding (araç), Gemini Live (sesli), `/api/analyze` (belge), yedek STT
- **Groq** — `gpt-oss-120b` metin yedeği, `whisper-large-v3-turbo` birincil STT
- **ElevenLabs** — TTS yedeği (mesh çökerse). *Şu an key 401 — yenilenecek*

## Araçlar (`aura_tools.py`, Seviye 1d)

`route_request` ipucu verir → `run_tool(name, query)` çalışır → sonuç sistem
talimatına `[ARAÇ BİLGİSİ]` notu → Aura kendi sesiyle sentezler. Fail-safe
(araç patlarsa sessizce atlanır).

| Araç | Ne yapar |
|---|---|
| `time` | Türkiye saati/tarihi + "X tarihine kaç gün" (ay adı / sayı / yıl-başlı yazım) |
| `math` | AST-tabanlı güvenli hesaplayıcı (`eval` YOK), Türkçe çarpı/bölü/yüzde |
| `search` | `aura_brain.grounded_answer` → Google-arama bağlamlı Gemini alt-çağrısı |

## Kritik operasyonel notlar

- **Rate limit:** kimlikli istek → token parmak izi başına (`RATE_LIMIT_USER_PER_MIN=90`), anonim → IP başına (30). Hesap-başına günlük tavanlar ayrı katman.
- **Tek worker + sync uçlar** → ~40 eş zamanlı istek (thread pool), sonrası kuyruk. Her `/api/chat` bir thread'i Gemini süresi boyunca (~5-8s) tutar.
- **Mesh TTS seri:** GPU'da tek üretim (`_gen_lock`), 6-15s/cümle. `MAX_QUEUE=3` → aşınca 503. Ölçek darboğazı — Faz 2 GPU / ikinci instance gerekebilir.
- **Şube deseni:** `main` = Railway'in deploy ettiği. `feat/value-whisper-and-chamber-palette` = Sign Council oturumuyla paylaşımlı. Railway kodu iki şubede içerik olarak eş tutulur (izole worktree + cherry-pick). `voice_service/` bilerek yalnız `feat`'te ileride (PC'de çalışır).

## Detaylı bağlam

`aura_brain.py` (sağlayıcı zinciri + routing + araç köprüsü), `aura_memory.py`
(Doğal Hafıza), `aura_voice.py` (Gemini Live relay), `voice_service/SETUP.md`,
`brain_service/SETUP.md` (Faz 2 kurulum). Yol haritası: memory `aura-own-brain-roadmap`.
