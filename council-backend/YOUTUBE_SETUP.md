# YouTube yükleme kurulumu — sizin yapmanız gereken adımlar

Kod tarafı hazır (`youtube_auth.py`, `upload_youtube.py`,
`publish_youtube.py`). Aşağıdaki adımlar sadece sizin yapabileceğiniz,
hesap/kimlik doğrulama gerektiren kısımlar.

## 1. Google Cloud projesi + API'yi etkinleştirme

1. [console.cloud.google.com](https://console.cloud.google.com) → yeni proje oluşturun (örn. "sign-council").
2. Sol menü → **APIs & Services → Library** → "YouTube Data API v3" arayın → **Enable**.
3. Ücretli değil, kart bilgisi istemiyor — sadece günlük kullanım kotası var (video başına ~1600 birim, günlük 10.000 birim = birkaç video/gün için fazlasıyla yeterli).

## 2. OAuth Client ID oluşturma

1. **APIs & Services → Credentials → Create Credentials → OAuth client ID**.
2. İlk seferde "OAuth consent screen" kurmanız istenebilir — **User Type: External**, uygulama adı "Sign Council" yazıp kaydedin (yayın durumu "Testing" kalabilir, sorun değil).
3. Client ID türü: **Desktop app**.
4. Oluşturunca bir JSON dosyası indirin.
5. Bu dosyayı **`council-backend/client_secret.json`** olarak kaydedin (isim birebir bu olmalı).

## 3. Tek seferlik yetkilendirme

```
python youtube_auth.py
```

Bu bir tarayıcı penceresi açacak — **Sign Council kanalının bağlı
olduğu Google hesabıyla siz giriş yapıp "izin ver" demelisiniz** (bu
adımı Claude yapamaz). Onayladıktan sonra `youtube_token.json` oluşur,
bundan sonra tekrar giriş istemez.

## 4. Kullanım

```
python upload_youtube.py output/teaser/sign_council_teaser.mp4 \
  --title "Yapay Zekalar Kendi Aralarında Tartışıyor — Sign Council Geliyor" \
  --description "$(cat output/teaser/metadata.md)" \
  --tags "yapay zeka,AI ethics,Sign Council" \
  --privacy private
```

Video **her zaman `private` olarak yüklenir** — herkese açık yapmak
ayrı bir adım:

```
python publish_youtube.py VIDEO_ID
```

Bunu Claude sizden ayrı, açık bir onay almadan çalıştırmaz.

## Güvenlik notu

`client_secret.json` ve `youtube_token.json` gerçek kimlik bilgileridir
— `.gitignore`'a eklendi, asla paylaşmayın/commit etmeyin.
