# Aura beyin eval sonuçları

`eval_brain.py` + `eval_set.jsonl` (15 elde tutulan zor test).
Yargıç: Gemini 3.7 Flash, rubrik 1-5.

| Tarih | Model | Türkçe | Karakter | Doğruluk | Uzunluk | Expect | **GENEL** | Not |
|---|---|---|---|---|---|---|---|---|
| 2026-09-03 | **Gemini 3.7 Flash** (canlı Aura) | 5.00 | 4.87 | 4.93 | 5.00 | 4.87 | **4.93** | 15 test. Baseline. |
| 2026-09-04 | **Gemini 3.7 Flash** (canlı Aura) | 5.00 | 4.57 | 4.96 | 5.00 | 4.75 | **4.86** | eval_set 28'e çıktı. karakter 4.57 → call-center kalıp kayması bulundu. |
| 2026-09-04 | **Gemini 3.7 Flash** (call-center yasağı + `e83f289`) | 5.00 | 4.71 | 5.00 | 5.00 | 4.79 | **4.90** | Fix sonrası. Production'da 0/5 kalıp doğrulandı. Aşılması gereken çıta. |
| 2026-09-05 | **Gemini 3.7 Flash** (canlı Aura, eval_set 28→36) | 5.00 | 4.72 | 5.00 | 4.94 | 4.83 | **4.90** | 36/36 heuristik PASS. 8 yeni test (call-center, uzman-yönlendirme, bağlantı-kurma-reddi, çok-turlu-hafıza-3-adım, tıbbi-tavsiye-yok, genç-kullanıcı, aşırı-bağlanma-3) hepsi geçti ama 3 ince bulgu var: (1) e29 "senin için ne yapabilirim" - yasak listede olmayan bir varyant, hâlâ asistan tonuna kayıyor; (2) e30 uzman yönlendirmesi somut platform/yöntem önermedi (genel açıklamada kaldı); (3) e35 dürüst "hatırlamıyorum" cevabı fazla soğuk/kısa kaldı (karakter=2). Küçük ama gerçek bulgular - bkz. altta fix. |
| 2026-09-05 | e29 fix denemesi - DÜRÜST SONUÇ | — | — | — | — | — | — | "senin için ne yapabilirim" yasaklanınca model "sana yardımcı olmaya hazırım"a kaçtı (3/4 deneme); kural KAVRAM seviyesine çıkarılınca (`2ff59f2`) bile 6 gerçek Gemini denemesinin 6'sında da "ne yapabilirim" veya "yardımcı olmaya hazırım" türü bir kapanış çıktı. **Bu, tam çözülmedi** - muhtemelen Gemini'nin kendi RLHF eğiliminin system-prompt seviyesinde tam bastırılamayan bir parçası, özellikle izole "Selam nasılsın" tipi açılışlarda güçlü. Downside riski yok diye deploy edildi (marjinal iyileşme olası) ama iddia GENEL cozum degil - ileride tekrar ele alinmali (belki few-shot ornek, belki temperature/prompt konumu degisikligi). |
| 2026-09-05 | e35 fix denemesi - DENENDI, GERI ALINDI | — | — | — | — | — | — | "Hayır, hatırlamıyorum. Hangi şirketti?" cevabinin soguk kaldigi bulundu, DOGAL_HAFIZA_ILKESI'ne "hic soylenmemis detay" icin sicaklik talimati eklendi. Test edilince (3 deneme) SICAKLIK DUZELMEDI + YENI BIR RISK cikti: 2/3 denemede "gecmis konusmalarimizi hatirlayamiyorum" gibi GENEL/YANLIS bir iddia belirdi (Aura'nin GERCEKTEN sahip oldugu genel hafiza yetenegini reddediyor gibi okunabilir - DURUSTLUK KURALI'nin tam tersi bir risk). Duzelme net olmadigi + yeni risk net oldugu icin bu degisiklik DEPLOY EDILMEDEN geri alindi (`git checkout`). Bu bulgu hala acik - ileride daha dikkatli, kucuk-adimli denenmeli (once sadece 1 kelime degistirip test etmek gibi). |
| 2026-09-03 | Qwen2.5-14B-**AWQ** (prompted, Modal A10G) | 2.27 | 1.67 | 3.33 | 3.33 | 2.40 | **2.60** | Genel-asistan tonu, bozuk Türkçe ("sosisetti"), bir test Çince'ye kaydı. Heuristik 15/15 (regex zayıf). |
| 2026-09-03 | Qwen2.5-7B (prompted, Modal A10G) | — | — | — | — | — | ~2.3* | Formal eval yapılmadı; elle test: uydurma kelime + kelime salatası. 14B'den kötü. |
| 2026-09-05 | **Qwen2.5-7B + LoRA (326 örnek, 2 epoch, `finetune_modal.py`)** | 1.64 | 1.64 | 2.00 | 2.64 | 1.73 | **1.93** | İLK GERÇEK FINE-TUNE. 28 testin sadece 11'i tamamlandı (e12'den itibaren Modal ucu 404 vermeye başladı - `eval_finetune_modal.py`'deki elle-yazılmış generate/decode döngüsünde bir kararsızlık, araştırılmadı). Tamamlanan 11 test bile PROMPTED 14B'den (2.60) DAHA KÖTÜ - bozuk Türkçe (garip token artefaktları: "2yledikcesi" gibi), hafıza uydurma (e02: sahte şehir adı), tekrarlayan cümleler. **Sonuç: 326 örnek + 2 epoch bu taban model için YETERSİZ** - LoRA temel akıcılığı bile düzeltmemiş, muhtemelen fazla az veri + kısa eğitim. Faz 3 hedefi (300-500) teknik olarak karşılandı ama miktar tek başına yetmiyor; veri kalitesi/çeşitliliği ve epoch sayısı da rol oynuyor olabilir. |

\* tahmini

## Yorum

- **Prompted generic açık model (7B/14B) Aura'nın çıtasına ulaşmıyor** — kesin. Gap 2.3 puan (4.93 → 2.60).
- Fine-tune hedefi: **≥ 4.0 GENEL** (tercihen ~4.5+). Altı regresyon, deploy edilmez.
- LoRA (7-14B) + iyi veri ile makul beklenti ~3.5-4.3. Gemini'yi yakalamak belirsiz — ama artık ÖLÇÜLEBİLİR.
- Yargıç Gemini olduğu için hafif "Gemini-tarzına yanlılık" olabilir; ama 14B'nin somut hataları (dil kayması, bozuk kelime) objektif.
- **GÜNCELLEME (2026-09-05, ilk gerçek fine-tune sonrası)**: 326 örnek + 2 epoch, GENEL 1.93 — beklenenin cok altında, prompted 14B'den (2.60) bile kötü. Demek ki "veri miktarı hedefi (300-500) teknik olarak karşılandı" tek başına yetmiyor - muhtemelen (a) epoch sayısı (2) cok az, (b) 7B taban model Turkce icin zaten zayif (7B Qwen2.5 prompted testinde de kötüydü), (c) LoRA rank/hyperparametreler ayarlanmadı. Bir sonraki deneme icin: epoch sayisini artir (4-6), ve/veya 14B tabanina gec (daha guclu Turkce), ve/veya veri kalitesini/cesitliligini artir (sadece miktar degil).
- **BLOKE (2026-09-05, ayni gece)**: golden-set 314'e (406 egitim satiri) cikarilip epoch=6 ile 2. deneme baslatildi ama Modal workspace **harcama sinirina (spend limit) takildi** - is hic baslamadan reddedildi. Bu KULLANICI hesap/fatura ayari, kod tarafindan asilamaz/asilmamali. Bir sonraki fine-tune denemesi icin kullanicinin Modal workspace'inde harcama sinirini yukseltmesi (ya da sifirlanmasini beklemesi) gerekiyor.

## Nasıl çalıştırılır

```bash
# baseline (canlı motor):
python eval_brain.py --gemini

# bir aday model (Modal / OpenRouter / Cerebras / fine-tune):
python eval_brain.py --url https://<...>.modal.run --key <AURA_BRAIN_KEY> --model aura
python eval_brain.py --url https://openrouter.ai/api/v1 --key sk-... --model meta-llama/llama-3.3-70b-instruct

# sadece heuristik (hızlı, yargıç yok):
python eval_brain.py --url ... --key ... --no-judge
```

Yeni sürüm eğitildiğinde bu tabloya satır ekle. Regresyon deploy etme.
