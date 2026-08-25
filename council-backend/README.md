# council-backend

Sign Council yayininin (Aura + Alpha + Beta + Gamma + Delta) orkestrasyon
katmani. `auro-backend/` (kisisel asistan Aura) ile hicbir kod veya veri
paylasmiyor - ayri `.env`, ayri kimlikler, ayri state. Ortak olan tek sey
ayni Python ortaminda calisabilmesi: `google-genai`, `httpx`,
`python-dotenv` zaten `auro-backend/venv` icinde kurulu, yeni bagimlilik
gerekmiyor.

## Kurulum

1. `.env.example` dosyasini `.env` olarak kopyalayin, API anahtarlarini
   girin.
   - `GEMINI_API_KEY`: `auro-backend/.env` icindekiyle ayni deger
     kullanilabilir - bu sadece bir kimlik bilgisi, kullanici verisi
     degil.
   - `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `XAI_API_KEY`: sirasiyla
     Alpha / Gamma / Beta icin gerekli, henuz konfigure edilmedi.
2. `auro-backend/venv`'i aktive edip buradan calistirabilirsiniz, ayri
   bir venv kurmaniza gerek yok.

## Calistirma

Tek komutla bastan sona (metin -> ses -> video):

```
python run_full_pipeline.py bolum_0
python run_full_pipeline.py bolum_1
```

Veya adim adim:

```
python run_episode.py bolum_0        # sadece metin
python render_audio.py output/...json # sadece ses
python render_video.py output/...json # sadece video
```

Cikti hem konsola basilir hem `output/` klasorune JSON transkript olarak
kaydedilir. Bir ajanin API anahtari eksikse o ajanin repligi durdurmadan
`[ATLANDI - ...]` olarak isaretlenir - devre kesici mantigi
`auro-backend/aura_brain.py`'deki fallback ilkesiyle ayni (bkz. Sign
Council Rundown, Segment 05). Ayni sekilde ses kimligi atanmamis
(`voices.py`) ya da ElevenLabs kotasi dolmus ajanlarin video karesi de
atlanir, bolum durmaz.

## Bolumler

- `episodes/bolum_0.py` — "Ego ve bencillik", Aura + Alpha + Gamma (pilot)
- `episodes/bolum_1.py` — "2030'da AI'nin gelecegi", tam kadro (5 ajan)

## Dosyalar

- `personas.py` — ajan kimlikleri (Aura, Alpha, Beta, Gamma, Delta)
- `providers.py` — saglayici API cagrilari (Gemini, OpenAI, Anthropic, xAI)
- `orchestrator.py` — tur-bazli soru-cevap motoru
- `voices.py` — ajan basina ElevenLabs ses kimligi
- `generate_avatars.py` — 5 ajan icin sabit avatar karti uretir (API'siz)
- `render_audio.py` — transkript -> ses klipleri (ElevenLabs)
- `render_video.py` — avatar + altyazi + ses -> bolum videosu (ffmpeg)
- `episodes/` — her bolumun konusu + soz sirasi tanimi
- `run_episode.py` / `run_full_pipeline.py` — CLI calistiricilar
- `youtube_auth.py` / `upload_youtube.py` / `publish_youtube.py` — YouTube
  yukleme (kurulum: `YOUTUBE_SETUP.md`). Yukleme HER ZAMAN `private`
  yapar; herkese acik yapmak ayri, bilincli bir adim.

## Onemli not

`XAI_API_KEY` (Grok / xAI, Beta ajani) ile `auro-backend/.env` icindeki
`GROQ_API_KEY` (Groq - hizli acik model altyapisi, uygulamada fallback
olarak kullaniliyor) **farkli seylerdir**. Isimleri neredeyse ayni,
karistirmayin.
