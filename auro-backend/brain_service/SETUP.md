# Aura Brain Mesh — kurulum

Aura'nın **kendi muhakeme çekirdeği** (Faz 1b + Faz 2). Voice Mesh ile aynı
mantık: `auro-backend` HTTP ile bağlanır, ulaşılamazsa Gemini'ye düşer.

```
auro-backend (Railway)                        model nerede?
  generate_with_retry
    ├─ AURA_BRAIN_URL varsa ──HTTP──►  A) yerel: brain_service :8130 ──► Ollama :11434
    │                                  B) bulut: Modal serverless (modal_app.py)
    ├─ olmadı ─► Gemini 3.7 Flash
    └─ olmadı ─► Groq
```

`AURA_BRAIN_URL` Railway'den **silinince davranış birebir eskiye döner**
(Gemini → Groq). Risksiz aç/kapa.

---

## A) Yerel GPU + Ollama (geliştirme / kendi donanımın)

### 1. Ollama (bir kez)
https://ollama.com/download
```
ollama serve                        (ayrı pencere, açık kalsın)
ollama pull qwen2.5:7b-instruct
```
- 8GB GPU + Chatterbox aynı anda → `qwen2.5:3b-instruct` (~2GB, güvenli)
- Sadece beyin (Chatterbox başka makinede) → `7b` veya `14b-instruct-q4`

### 2. brain_service
```
cd auro-backend/brain_service
python -m pip install -r requirements.txt
```
`sync_secrets.example.txt` → `sync_secrets.txt` (GITIGNORE) doldur:
- `RAILWAY_TOKEN / PROJECT_ID / ENVIRONMENT_ID / SERVICE_ID` — voice_service ile **aynı** (auro-backend servisi); `voice_service/sync_secrets.txt`'ten kopyala
- `AURA_BRAIN_KEY` — uzun rastgele; Railway'deki `AURA_BRAIN_KEY` ile **aynı**
- `BRAIN_BACKEND_MODEL` — ollama model adı

### 3. Başlat
```
baslat_hepsi.bat        (LLM sarmalayıcı + cloudflared tünel + Railway oto-senkron)
```
Masaüstü kısayolu yapılabilir (voice_service'teki gibi). `tunel_sync.py`
tünel adresini yakalayıp Railway `AURA_BRAIN_URL`'ini otomatik günceller —
adres değişse bile elle iş yok.

`GET http://localhost:8130/health` → `backend_ok: true` olmalı.

---

## B) Serverless GPU (Modal) — ÖNERİLEN başlangıç (Faz 2 seçenek C)

Kendi GPU'na bağımlı değil, saniye başı ödeme, kullanılmayınca **sıfıra
ölçeklenir** (soğuk başlama ~20-40s, sonra sıcak). Küçük trafikte en ucuz.

```
pip install modal
modal token new
modal secret create aura-brain-secret AURA_BRAIN_KEY=<Railway'deki ile aynı>
modal deploy auro-backend/brain_service/modal_app.py
```
Çıkan URL (`https://<org>--aura-brain-serve.modal.run`) → Railway Variables:
| değişken | değer |
|---|---|
| `AURA_BRAIN_URL` | Modal URL (sonda `/` yok) |
| `AURA_BRAIN_KEY` | secret ile aynı |
| `AURA_BRAIN_MODEL` | `aura` |

`modal_app.py` içinde: `MODEL_ID` (varsayılan `Qwen/Qwen2.5-7B-Instruct`),
`GPU` (`A10G` ucuz / `A100-40GB` / `H100`), `scaledown_window` (boşta kapanma).
Değiştir → `modal deploy` tekrar. Konuşma logu bir Modal Volume'a yazılır.

Ölçek büyüyünce: `scaledown_window`'u uzat veya kiralık 7/24 GPU'ya (seçenek B) geç.

---

## Zorluk-bazlı model (Seviye 1c ile birlikte)

`route_request` her turu `light / standard / deep` sınıflar; `auro-backend`
brain'e `model: "aura-light"` / `"aura-deep"` gönderir.

- **A (yerel):** `brain_service` env — `BRAIN_MODEL_LIGHT=qwen2.5:3b-instruct`,
  `BRAIN_MODEL_DEEP=qwen2.5:14b-instruct`. Verilmezse hepsi ana modele düşer.
- **B (Modal):** şimdilik tek model; ileride `modal_app.py`'de tier→model haritası.

Tek model yeterliyse hiçbir ek ayar gerekmez.

---

## Faz 3 hazırlığı — eğitim verisi

Her tur `conversations.jsonl`'e (`{ts, messages, reply, model, elapsed_s, ok}`)
yazılır — yerelde `brain_service/`, Modal'da `/logs` Volume. Bu dosya Aura'nın
kendi modelini fine-tune etmenin yakıtı. **Kişisel veri → gitignore, paylaşma.**
`AURA_BRAIN_LOG=` (boş) ile kapatılır.
