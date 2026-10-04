# Danışma Odası

Sign Council'in YouTube karakterlerinden bağımsız, bizimle konuşan çalışma masası.
Sağlayıcı katmanı `../providers.py` ile ortak; anahtarlar `../.env` içinde kalır.

## Çalıştırma (Windows)
`danisma\Danisma_Baslat.bat` çift tıkla → tarayıcıda http://127.0.0.1:8765 açılır.

Elle: `council-backend` klasöründen
`..\auro-backend\venv\Scripts\activate` sonra
`python -m uvicorn danisma.server:app --host 127.0.0.1 --port 8765`

## Akış
1. **Anahtarları sına:** her anahtar küçük bir istekle denenir; yalnızca çalışanlar üye olur.
2. **Kör tur:** üyeler birbirini görmeden, zorunlu JSON şemasıyla (iddia/kanıt/güven/bilmiyorum) cevaplar.
   Kaynaksız rakam otomatik ⚠ işaretlenir.
3. **Claude cevabı (isteğe bağlı):** Claude'a aynı soruyu üyelerin cevabını görmeden sor, yapıştır.
4. **Çapraz eleştiri:** herkes diğerlerinin en zayıf noktasını bulur.
5. **Takip:** istediğin kadar yönerge/soru.
6. Her adım `docs/danisma/<zaman>.md` + `.json` olarak kaydolur; commit/push edersen Claude okuyabilir.

## Güvenlik
- Yalnızca 127.0.0.1'e bağlanır.
- Anahtar değerleri çıktıdan maskelenir; veri paketi repo dışına çıkamaz.
- Yalnızca metin (ekran görüntüsü yok).
