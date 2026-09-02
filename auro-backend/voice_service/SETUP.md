# Aura Voice Mesh — kurulum

Aura'nın **kendi sesi** (Chatterbox TTS). GPU'lu bir makinede kaşar, `auro-backend`
buna HTTP ile bağlanır; ulaşılamazsa `auro-backend` otomatik ElevenLabs'e düşer.

---

## A. TEK SEFERLİK (bir kez)

### 1. Bağımlılıklar
Global Python 3.12'de `chatterbox-tts` + `torch (cu118)` zaten kurulu. Yeni makinede:
```
pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu118
pip install -r requirements.txt
```

### 2. cloudflared (kurulu değilse)
```
winget install --id Cloudflare.cloudflared
```

### 3. Kalıcı tünel
```
kurulum_tek_seferlik.bat
```
- Tarayıcı açılır → Cloudflare hesabınla giriş yap, domaini seç (**Authorize**)
- Script `aura-ses` tünelini oluşturur ve sana bir alt alan adı sorar (örn. `ses.enerjiiaydinlatma.com`)
- `cloudflared tunnel list` ile tünel ID'sini gör

### 4. `config.yml` düzenle
- `credentials-file`: `C:\Users\<KULLANICI>\.cloudflared\<TUNNEL-ID>.json` (veya `aura-ses.json`)
- `hostname`: adım 3'te seçtiğin alt alan adı

### 5. Railway → `auro-backend` → Variables
| Değişken | Değer |
|---|---|
| `AURA_VOICE_URL` | `https://ses.senindomainin.com` (sonda `/` yok) |
| `AURA_VOICE_KEY` | `baslat.bat` içindeki `AURA_VOICE_KEY` ile **birebir aynı** |

Bu ikisi tanımlanınca `/api/tts` önce Aura Voice Mesh'e sorar. **Tanımsızken mesh
hiç denenmez** — davranış eskisiyle aynı (ElevenLabs).

---

## B. GÜNLÜK

```
baslat_hepsi.bat
```
TTS servisi + tünel iki ayrı pencerede açılır, çökerse kendini yeniden başlatır.
Bilgisayar açık olduğu sürece Aura kendi sesiyle konuşur; kapalıyken otomatik
ElevenLabs devreye girer (aynı ses — `iLcCq17...`).

### Açılışta otomatik başlat (isteğe bağlı)
`Win+R` → `shell:startup` → `baslat_hepsi.bat` kısayolunu bu klasöre koy.

---

## Test

```
curl https://ses.senindomainin.com/health
curl -X POST https://ses.senindomainin.com/tts -H "X-Voice-Key: ANAHTAR" ^
  -H "Content-Type: application/json" -d "{\"text\":\"Selam, kendi sesimle konusuyorum.\"}" -o test.wav
```

## Notlar

- Chatterbox ~1x gerçek-zaman (RTX 4060). `auro-backend` 800 karakterden uzun metni
  doğrudan ElevenLabs'e yollar (`AURA_VOICE_MAX_CHARS`).
- `stream=true` cümle cümle döner (ilk cümle ~3 sn) — istemci progresif oynatma = faz-2.
- Ton ayarı: `AURA_TTS_EXAGGERATION` / `AURA_TTS_CFG_WEIGHT` env (varsayılan 0.4 / 0.5).
- VRAM ~3.2 GB, model yükleme ~22 sn.
