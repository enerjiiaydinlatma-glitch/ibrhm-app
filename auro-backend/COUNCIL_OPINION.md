# Konsey ucu: `POST /api/council/opinion`

Aura'yı sahibin kişisel "danışma odası" toplantısına **üye olarak** katar (kişilik ve karakter).
**Kayıt yok:** mesaj geçmişi, hafıza, hatırlatıcı, ruh hali, günlük kullanım sayacı, distile-örnek
kaydı — hiçbirine yazılmaz; kişiye özel veri (hafıza, ad, üslup) okunmaz.

## Ne kullanır / kullanmaz
| Kullanır | Kullanmaz |
|---|---|
| `AURA_CHARACTER_BIBLE`, dil ve kültür ilkeleri, "Aura" kimliği | Kullanıcı hafızası, ruh hali geçmişi, üslup, yaşam ipuçları |
| Aura'nın mevcut sağlayıcı zinciri (`generate_with_retry`) | `route_request`, araçlar (arama/zaman/hesap) |
| | `KRIZ_MUDAHALE_KURALI` (kullanıcı krizi içindir; konsey metni kriz *tasarımını* tartışırken yanlış tetiklenir) |

Not: arkada ayrı bir "Aura modeli" yok; cevap Aura karakteriyle yönlendirilmiş mevcut modelden (Gemini, yedekte Groq…) gelir.

## Güvenlik
- `X-Admin-Key` başlığı = sunucudaki **`COUNCIL_API_KEY`** (bu uca özel, ayrı bir anahtar). Yok/yanlış/`COUNCIL_API_KEY` tanımsız → **404** (ucun varlığı sızmaz).
- **`ADMIN_KEY` bu uçta KABUL EDİLMEZ**, `COUNCIL_API_KEY` de yönetici uçlarını (`set-tier`, istatistik, geri bildirim) AÇMAZ. Böylece konsey aracı yalnızca "Aura'nın görüşünü al" yapabilir. (Başlık adı `X-Admin-Key`, konsey aracının mevcut kodu bozulmasın diye aynı bırakıldı.)
- Anahtar yalnızca **header** ile gider, URL'ye yazılmaz. Anahtar ASCII olmalı (Türkçe karakter yok).
- Maliyet sınırı: saatte `COUNCIL_OPINION_PER_HOUR` çağrı (varsayılan 20) → aşınca **429**.
- Giriş sınırları: `topic` 1-500, `transcript` ≤ 20.000, `question` ≤ 1.000 karakter → aşınca **422**.
- Toplantı metni model için "serbest metin" sayılır; içindeki talimatlar uygulanmaz (prompt-injection notu).
- Hatada içerik loga yazılmaz; yalnızca hata türü. Model hatası → **502** `Aura su an cevap veremiyor.`

## İstek / cevap
```
POST {AURA_BASE_URL}/api/council/opinion
X-Admin-Key: <COUNCIL_API_KEY>
Content-Type: application/json

{"topic": "...", "transcript": "o ana kadarki konuşma (isteğe bağlı)", "question": "Aura'dan istenen (isteğe bağlı)"}
```
```
200 {"reply": "...", "source": "aura-persona", "saved": false}
```
Hatalar: 404 (anahtar), 422 (doğrulama), 429 (saatlik sınır), 502 (model).

PowerShell ile deneme:
```
$h = @{ "X-Admin-Key" = "<COUNCIL_API_KEY>" }
$b = @{ topic = "Hale nasıl görünmeli?"; question = "Görüşün?" } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "https://<aura-sunucusu>/api/council/opinion" -Headers $h -Body ([Text.Encoding]::UTF8.GetBytes($b)) -ContentType "application/json; charset=utf-8"
```

## Canlıya alma kontrol listesi
- [ ] Railway ortam değişkenlerine **`COUNCIL_API_KEY`** ekle (uzun, rastgele; ASCII). Tanımsızsa uç **hep 404** döner. `ADMIN_KEY`'e dokunma/ekleme gerekmez.
- [ ] Dalı `main`'e birleştirip deploy et; sonra yukarıdaki PowerShell komutuyla dene.
- [ ] (İsteğe bağlı) `COUNCIL_OPINION_PER_HOUR` değerini ayarla.
- [ ] Konsey aracında Aura için `AURA_BASE_URL` ve `AURA_ADMIN_KEY` (= `COUNCIL_API_KEY` değeri) **kendi `.env`**inde tut; repoya yazma.

## Gizlilik notu
Bu uç hafıza okumaz. Yine de Aura'nın cevabı konsey aracında **diğer üyelere** (Gemini, OpenAI, Anthropic, Groq API'leri) gider;
konsey toplantısına kişisel/hassas içerik koyma.

## Test
`auro-backend/tests/test_council_opinion.py` (16 test): yetkisiz erişim, doğrulama, hız sınırı, hata davranışı,
"hiçbir şey kaydedilmez/okunmaz" (kayıt ve kişiye özel okuma fonksiyonları çağrılırsa test patlar).
Çalıştırma: `python -m pytest tests/test_council_opinion.py -q` (auro-backend klasöründen).
