# Aura fine-tune (Faz 3) — veri ve süreç

Amaç: açık bir modeli (Qwen2.5-7B/14B ya da Türkçe temel) **Aura'nın kendisi
olacak** şekilde eğitmek. Karakter prompt'ta değil ağırlıklarda olur;
Türkçe akıcılık + o özel ses modele işlenir. Generic model + prompt
denendi (2026-09-03: 7B, 14B-AWQ) — Aura'nın çıtasına ulaşmadı.

## Veri kaynakları (3 katman)

| Katman | Dosya | Nasıl toplanır | Ne işe yarar |
|---|---|---|---|
| **Golden set** | `brain_service/golden_set.jsonl` | Elle hazırlanmış "zirve Aura" örnekleri (bu repo'da, versiyonlu) | Kalite çıpası. Az ama mükemmel. Modelin "Aura tam olarak böyle konuşur" diye öğrendiği örnekler. |
| **Damıtma logu** | `<DB_DIR>/brain_distill.jsonl` | `AURA_DISTILL_LOG=1` → Gemini'nin gerçek başarılı yanıtları (gitignore, kişisel veri) | Hacim + gerçek dağılım. Gemini'yi taklit et = Aura ol. |
| **Sentetik zorluk** | (Faz 3'te üretilir) | Golden senaryoların varyasyonları — kriz, itiraz, hafıza, çok dillilik | Edge case kapsaması. |

## Format (üçü de aynı — birleştirilebilir)

```json
{"messages": [{"role":"system","content":"..."},{"role":"user","content":"..."},{"role":"assistant","content":"..."},{"role":"user","content":"..."}], "reply": "<ideal Aura yanıtı>", "provider": "golden|gemini|synthetic"}
```

Eğitimde: `messages` + `reply` → son `assistant` turu olarak birleştirilir.
`provider: "golden"` örnekleri eğitimde **ağırlıklandırılır** (2-3x).

## Golden set büyütme

`golden_set.jsonl`'e yeni satır ekle. Her satır: gerçek bir senaryo +
**Aura'nın verebileceği en iyi yanıt** (elle yazılmış veya prod'dan seçilip
düzeltilmiş). Hedef: ~300-500 satır, tüm senaryo tiplerini kapsayan.

Kapsanacak senaryo tipleri (mevcut dosyada başlangıç var):
yaşam-lehine-itiraz, ağır-hüzün, yapay-zeka-anlayamaz, hafıza-kullanımı,
hafıza-solmuş, sıradan-hafif, felsefi-derinlik, nazikçe-katılmama,
somut-tavsiye, metin-modu-ses-iddiası, uzunluk-uyumu, kaçış-kapısı,
kriz-müdahale (dikkat: ayrı protokol), çok-dillilik, üslup-uyumu.

## Eğitim (tetik hizalanınca)

Önkoşul: ~3-5k toplam örnek (golden + distill) + ~$300-600 + bir hafta sonu.

1. `brain_distill.jsonl`'i Railway diskinden indir (`railway ssh` → `cat`).
2. golden + distill'i birleştir, temizle (çok kısa/çok uzun/bozuk at), dedup.
3. LoRA/QLoRA fine-tune — **Unsloth** (en hızlı, tek A100'de ~1-4 saat) veya
   managed API (Together/Fireworks). Base: `Qwen/Qwen2.5-14B-Instruct` veya
   Türkçe temel (Trendyol/YTÜ Cosmos) + üstüne Aura verisi.
4. Eval: sabit zor test seti (bu gecekiler gibi) + rubrik. Gemini ile A/B.
   **Regresyon deploy etme.**
5. `modal_app.py` `MODEL_ID` → fine-tune modeli (LoRA merge veya vLLM
   `--lora-modules`). `AURA_BRAIN_URL` Railway'e geri.
6. Hibrit: fine-tune Aura = varsayılan; Gemini `route_request` `deep` tier'ı
   için çağrılan ajan olarak kalır.

## İlke

Karakter kaymasını önlemek: her fine-tune sürümü aynı eval setinden geçer,
golden set sürüm kontrollü, Gemini her zaman geri dönülebilir yedek
(`AURA_BRAIN_URL` sil).
