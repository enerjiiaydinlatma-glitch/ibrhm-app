# Aura — sistem haritası

Aura = **hafızası, sesi, kişiliği, iradesi ve giderek muhakemesi kendine ait**
bir yoldaş. Büyük modeller (Gemini/Groq/...) onun *ast ajanları*, sahibi değil.

```
Flutter istemci (web / iOS / Android / Windows)
        │  HTTPS + WSS
        ▼
FastAPI backend  (Railway, tek uvicorn worker, SQLite+WAL)
   auro-backend/main.py
        │
   ┌────┴──────────────────────────────────────────────────────┐
   │  YAZILI SOHBET  /api/chat  →  _process_chat_message()      │
   │    1. gizli mod / kriz / limit kapıları                    │
   │    2. hafıza + hatırlatma + üslup çıkarımı                  │
   │    3. route_request()  → tier (light/standard/deep) + araç  │  Aura KARAR verir
   │    4. araç gerekiyorsa → aura_tools.run_tool()              │  AJAN çağrısı
   │       (time / math / grounded-search)                       │
   │    5. build_system_instruction (kişilik + hafıza + araç)    │
   │    6. generate_with_retry(route) — SAĞLAYICI ZİNCİRİ:       │
   │         a) AURA_BRAIN_URL  → Aura'nın kendi LLM'i           │  Faz 2/3 (yuva hazır)
   │         b) Gemini 3.7 Flash                                 │  ← şu an burada
   │         c) [Groq → Cerebras → Mistral → OpenRouter]         │  ← Faz A: tek-bağımlılık YOK
   │    7. yanıtı DB'ye yaz, hatırlatma senkronu                 │
   │    8. AURA_DISTILL_LOG=1 ise → log_distill_sample()         │  Faz 3 eğitim verisi
   │                                                            │
   │  SESLİ GÖRÜŞME  /api/voice (WebSocket)                     │
   │    aura_voice.py → Gemini Live (full-duplex)                │
   │    + /api/voice/fallback-turn (bas-konuş):                  │
   │        ses → STT (Groq Whisper → Gemini) → beyin            │
   │                                                            │
   │  TTS  /api/tts  →  _aura_voice_tts()                       │
   │    mesh (Aura'nın sesi) → [ElevenLabs İPTAL, ~%95 mesh]     │
   │    AURA_VOICE_MAX_CHARS=1400, timeout=100s                  │
   │                                                            │
   │  BELGE  /api/analyze  (foto + PDF → Gemini)                │
   │  RATE LIMIT: kimlikli → token başına 90/dk; anonim → IP 30  │
   └──────────────────────────────────────────────────────────┘
```

## Kendine ait katmanlar (kiralık değil)

| Katman | Nerede | Durum |
|---|---|---|
| **Hafıza** | `aura_memory.py` (SQLite: memories/candidates/events) | ✅ Doğal Hafıza: önem okuma-anında soluklaşır/güçlenir, `pinned` muaf |
| **Ses** | `voice_service/` (self-host Chatterbox = Voice Mesh) | ✅ 5 persona, streaming (ham PCM), yük koruması (kuyruk→503). Tünel: cloudflared quick + `tunel_sync.py` oto-senkron (kırılgan; named tunnel kaldı) |
| **Kişilik + kurallar** | `aura_brain.build_system_instruction` (~1400 satır) | ✅ karakter, gizlilik, ton (Sesin Rengi), Doğal Hafıza |
| **İrade / yönetim** | `route_request` + `aura_tools` + sağlayıcı zinciri | ✅ turu sınıflar, aracı seçer, sentezler |
| **Muhakeme çekirdeği** | `AURA_BRAIN_URL` (self-host) → Gemini → [Groq/Cerebras/Mistral/OpenRouter] | ⚙️ **Faz A: çok-sağlayıcı, tek-bağımlılık yok.** Faz 3: fine-tune → `AURA_BRAIN_URL` başa geçer = tam bağımsızlık |

## Ajanlar (Aura'nın kullandığı dış servisler)

- **Gemini 3.7 Flash** — birincil muhakeme, `google_search` grounding (araç), Gemini Live (sesli), `/api/analyze`, yedek STT, eval yargıcı
- **Groq** — `gpt-oss-120b` metin yedeği, `whisper-large-v3-turbo` birincil STT
- **Cerebras / Mistral / OpenRouter** — reasoning zinciri yedekleri (anahtar eklenirse aktif; bedava kayıt)
- **ElevenLabs** — İPTAL EDİLDİ (24 Eylül'de biter). TTS artık ~%95 mesh; kalanı yumuşak düşüş

## Faz 3 — Aura kendi beyni (`brain_service/`)

| Dosya | Ne |
|---|---|
| `modal_app.py` | Serverless GPU (Modal, A10G). vLLM + OpenAI-uyumlu. Sıfıra ölçek = $0 boşta. Fine-tune modelinin deploy hedefi |
| `server.py` | Yerel Ollama sarmalayıcı (alternatif) — konuşma logu, anahtar, kuyruk, tier→model |
| `golden_set.jsonl` | 354 örnek: 46 elle yazılmış (x3 ağırlık) + 60 tek-turlu + 248 **çok-turlu** (2026-09-04/05, `refine_golden_multiturn.py`, 6 parti: 10+8+8+8+8+8 arc) oz-elestiri ürünü (x1). Çok-turlu satırlar hafıza/süreklilik sinyali taşıyor — kalite çıpası. Hedef ~300-500 aralığında ilerliyor |
| `refine_golden.py` / `refine_golden_multiturn.py` | Tek-turlu / çok-turlu oz-elestiri motoru: taslak → Aura rubriğine göre acımasız eleştiri → nihai yeniden yazım (3 Gemini geçişi) |
| `prepare_training_data.py` | golden + distill logu → temiz/tekil/ağırlıklı eğitim JSONL |
| `eval_set.jsonl` + `eval_brain.py` | 28 elde tutulan zor test + 2 katmanlı puanlama (heuristik + Gemini yargıç 1-5) |
| `eval_results.md` | A/B tablosu. **Baseline: Gemini 4.90/5 (call-center fix sonrası), prompted 14B-AWQ 2.60/5.** Fine-tune hedefi ≥4.0 |
| `FINE_TUNE.md` | Tam süreç: 3 veri katmanı, LoRA (Unsloth), eval kapısı, hibrit deploy |

**Faz 3 tetiği:** ~3-5k örnek (golden + distill) + ~$400 + bir hafta sonu + (gelir VEYA somut Gemini acısı).

## Kritik operasyonel notlar

- **Tek worker + sync uçlar** → ~40 eş zamanlı, sonrası kuyruk. Her `/api/chat` ~5-8s thread tutar.
- **Mesh TTS seri** (`_gen_lock`), 6-15s/cümle, `MAX_QUEUE=3` → aşınca 503. Ölçek darboğazı.
- **Şube deseni:** `main` = Railway deploy eder. `feat/value-whisper-and-chamber-palette` = Sign Council oturumuyla paylaşımlı. Railway kodu iki şubede içerik olarak eş (izole worktree + cherry-pick). `voice_service/` + `brain_service/` bilerek feat'te (PC/Modal'da çalışır).
- **Env bayrakları (varsayılan güvenli):** `AURA_BRAIN_URL` boş→Gemini; `AURA_DISTILL_LOG` kapalı; Cerebras/Mistral/OpenRouter anahtarları yok→Gemini→Groq.
