# "2–3 iş günü" → "2 iş günü" geçişi — ilerleme

- Yazılan: 82 üründen ilk 25'i (sıra 0–24, fix4.json sırasına göre; son yazılan ürün id 14892810010991).
- Kalan: 57 ürün. Her üründe `2[–-]3 iş günü` → `2 iş günü` yapılacak; rakip tablosundaki "3–7 gün", "2–5 gün" ve "2–3 saatte", "2–3 m²" gibi ifadelere dokunulmayacak.
- Yöntem: canlı açıklamayı çek, regex uygula, `productUpdate(product:{id,descriptionHtml})` ile yaz (eski `input:` argümanı artık reddediliyor).
- Bilinen hata: ürün 14892361187695 açıklamasında "Kiracilar" yazım hatası var (doğrusu "Kiracılar"). Tüm bitince canlıdan çekip karşılaştırarak kontrol et.
- Tema metinleri (500 TL, 2–3 iş günü) ve Shopify politikaları elle yapıştırılacak: politika-metinleri.md
