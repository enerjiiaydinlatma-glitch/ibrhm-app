# Aura Brain Mesh — kurulum

Aura'nın **kendi muhakeme çekirdeği** (Seviye 1b). Voice Mesh ile aynı mantık:
GPU'lu makinede ayrı bir process, `auro-backend` HTTP ile bağlanır, ulaşılamazsa
Gemini'ye düşer.

```
auro-backend (Railway)                bu makine (GPU)
  generate_with_retry
    ├─ AURA_BRAIN_URL varsa ──HTTP──►  brain_service/server.py  :8130
    │                                      │  (log + anahtar + kuyruk)
    │                                      ▼
    │                                  Ollama / vLLM  :11434   ← gerçek model
    ├─ olmadı ─► Gemini 3.7 Flash
    └─ olmadı ─► Groq
```

## Adımlar

### 1. Arka plan LLM'i (bir kez)

**Ollama** (en kolay): https://ollama.com/download
```
ollama serve
```
Model çek (ayrı pencere):
```
ollama pull qwen2.5:7b-instruct
```
- 8GB GPU + Chatterbox aynı anda çalışıyorsa → `qwen2.5:3b-instruct` (daha güvenli, ~2GB)
- Sadece beyin (Chatterbox başka makinede) → `qwen2.5:7b-instruct` veya `qwen2.5:14b-instruct-q4`

### 2. brain_service

```
cd auro-backend/brain_service
python -m pip install -r requirements.txt
```

`sync_secrets.txt` (voice_service'teki gibi, GITIGNORE) veya ortam değişkeni:
```
set AURA_BRAIN_KEY=uzun-gizli-bir-anahtar
set BRAIN_BACKEND_MODEL=qwen2.5:7b-instruct
python server.py
```
`GET http://localhost:8130/health` → `backend_ok: true` olmalı.

### 3. Tünel + Railway

Voice Mesh ile **aynı** akış:
- `cloudflared tunnel --url http://localhost:8130` → `https://<rastgele>.trycloudflare.com`
- Railway Variables:
  - `AURA_BRAIN_URL` = tünel adresi (sonda `/` yok)
  - `AURA_BRAIN_KEY` = yukarıdaki anahtar
  - `AURA_BRAIN_MODEL` = `aura` (brain_service backend adına çevirir)
- Deploy → `generate_with_retry` artık önce Aura'nın kendi modelini dener.

`tunel_sync.py` (voice_service'teki) `LOCAL_URL` ve Railway değişken adları
değiştirilerek buraya da uyarlanabilir — otomatik adres senkronu için.

## Geri alma

`AURA_BRAIN_URL` Railway'den silinince davranış **birebir eskiye** döner
(Gemini → Groq). Risksiz aç/kapa.

## Faz 3 hazırlığı

Her tur `brain_service/conversations.jsonl`'e yazılır
(`{ts, messages, reply, model, elapsed_s, ok}`). Bu dosya, Aura'nın kendi
modelini fine-tune etmenin eğitim verisi. `AURA_BRAIN_LOG=` (boş) ile kapatılır.
Kişisel veri içerir → **gitignore**, paylaşma.
