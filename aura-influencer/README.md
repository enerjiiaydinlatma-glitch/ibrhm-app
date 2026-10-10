# Aura Influencer Studio

12 Eylül 2026 kararı: Aura'nın (ana kişisel asistan uygulamasının karakteri)
kendi adına, **açıkça yapay zeka olduğunu belirterek**, sosyal medyada bir
varlık kurma projesi. Amaç: (1) Aura uygulamasının organik tanıtımı, (2)
Aura'nın karakterini/kişiliğini dünyaya yaymak, (3) gerçek bir takipçi
kitlesi oluşturmak — sahte kimlik yok, cinsel içerik yok.

**Bu proje `council-backend` (Sign Council) ve `auro-backend` (ana Aura
uygulaması) ile TAMAMEN ayrı.** Sadece `council-backend/.env`'deki sağlayıcı
anahtarlarını (Gemini/Anthropic/OpenAI/Groq) okur — bu paylaşılan bir kimlik
bilgisi, kod ya da veri paylaşımı değil.

## Kullanım

Masaüstünde **"Aura Influencer Kontrol Paneli"** kısayolu — çift tıkla,
tarayıcıda `http://127.0.0.1:8795/` açılır (zaten çalışıyorsa sadece
tarayıcıyı açar). Elle çalıştırmak için: `AuraCommandCenter.bat`.

Sohbet penceresinde Aura ile projeyi konuş, karar ver. Sol taraftaki hızlı
eylem düğmeleri (Bio, İçerik Takvimi, Platform Stratejisi, Örnek Gönderiler)
somut belgeler ürettirir — beğendiğini "Dosyaya kaydet" ile
`_studio/documents/`e kaydedersin.

Sağ paneldeki **"Üret ve Yayınla"** bölümü, Aura'nın verdiği İngilizce
ses scripti + Türkçe çeviriyi alıp TTS + video render + YouTube yayınını
tek tıkla, Claude Code gerekmeden çalıştırır (YouTube Data API v3 ile,
`_studio/publish_youtube_api.py`). TikTok tarafı hâlâ elle kalıyor (bot-
tespiti nedeniyle otomatikleştirilemiyor) — panel video+caption'ı hazırlar,
"TikTok için Kopyala" butonuyla panoya alırsın.

## Hard kurallar (Aura'nın sistem promptuna gömülü)
- Her zaman AI olduğunu açıkça belirtir, asla insan gibi davranmaz
- Cinsel/thirst-trap içerik ASLA yok
- Ana Aura uygulaması hâlâ kapalı beta — kitlesel trafik önerisi yapmadan
  önce bunu göz önünde bulundurur
- Sahte metrik/referans/aciliyet uydurmaz

## Dosyalar
- `aura_studio.py` — sunucu + sohbet mantığı + render/yayın API'leri
- `AuraCommandCenter.bat` — masaüstü kısayolunun hedefi
- `_studio/conversation.json` — sohbet geçmişi (kalıcı)
- `_studio/documents/*.md` — kaydedilen planlama belgeleri
- `_studio/day_status.json` — Gün 1-30 yayın durumu takibi
- `_studio/make_video.py` — TTS sesinden waveform+altyazılı video render
- `_studio/make_tr_srt.py` — gerçek ses süresine göre Türkçe CC üretimi
- `_studio/publish_youtube_api.py` — YouTube Data API v3 ile yayınlama
  (OAuth, `_studio/client_secret.json` + `_studio/token.json` gerekir,
  git'e girmez)
