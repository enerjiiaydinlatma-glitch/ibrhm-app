# Aura Voice Mesh — kurulum

Aura'nın **kendi sesi** (Chatterbox TTS). GPU'lu bir makinede kaşar, `auro-backend`
buna HTTP ile bağlanır; ulaşılamazsa `auro-backend` ElevenLabs'e düşer.

## 1. Bağımlılıklar (bir kez)

Global Python 3.12'de `chatterbox-tts` + `torch (cu118)` zaten kurulu (test edildi).
Yeni bir makinede:

```
pip install torch==2.6.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu118
pip install -r requirements.txt
```

## 2. Servisi başlat

`baslat.bat` içindeki `AURA_VOICE_KEY`'i uzun/gizli bir değerle değiştir, sonra:

```
baslat.bat
```

İlk açılışta model ~20 sn yüklenir. `http://localhost:8123/health` → `{"status":"ok",...}`.

## 3. İnternete aç — Cloudflare Tunnel

### Hızlı (test — hesap/domain gerekmez)

```
winget install --id Cloudflare.cloudflared
tunel_baslat.bat
```

Çıkan `https://<rastgele>.trycloudflare.com` adresini kopyala. **Bilgisayar/tunel
kapanınca adres değişir** — sadece test için.

### Kalıcı (production — Cloudflare hesabı + domain gerekir)

```
cloudflared tunnel login
cloudflared tunnel create aura-voice
cloudflared tunnel route dns aura-voice voice.SENIN-DOMAININ.com
cloudflared tunnel run --url http://localhost:8123 aura-voice
```

`voice.SENIN-DOMAININ.com` sabit kalır.

## 4. Railway ortam değişkenleri (`auro-backend` servisi)

| Değişken | Değer |
|---|---|
| `AURA_VOICE_URL` | tünel adresi (örn. `https://xxx.trycloudflare.com`) — **sonda `/` yok** |
| `AURA_VOICE_KEY` | `baslat.bat`'teki `AURA_VOICE_KEY` ile **birebir aynı** |

Bu ikisi tanımlanınca `auro-backend` `/api/tts`'i önce Aura Voice Mesh'e sorar.
Tanımsızken mesh hiç denenmez — davranış eskisiyle aynı (ElevenLabs).

## 5. Uçtan uca test

```
curl -X POST https://<tunel>/tts -H "X-Voice-Key: ANAHTAR" ^
  -H "Content-Type: application/json" -d "{\"text\":\"Selam, kendi sesimle konusuyorum.\"}" -o test.wav
```

## Notlar

- Chatterbox ~1x gerçek-zaman üretir (RTX 4060'ta). `auro-backend` 800 karakterden
  uzun metni doğrudan ElevenLabs'e yollar (`AURA_VOICE_MAX_CHARS`).
- `stream=true` cümle cümle döner (ilk cümle ~3 sn) — istemci progresif oynatınca
  gecikme gizlenir; bu ikinci aşama.
- Ton ayarı: `AURA_TTS_EXAGGERATION` / `AURA_TTS_CFG_WEIGHT` env'leri (varsayılan
  0.4 / 0.5). Sonra ayarlanacak.
