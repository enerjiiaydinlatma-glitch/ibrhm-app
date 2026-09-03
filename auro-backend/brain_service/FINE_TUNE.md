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

## Araç zinciri (hepsi `brain_service/` içinde)

```
scenarios.jsonl ──► refine_golden.py ──► refined_candidates ──(elle inceleme)──┐
golden_set.jsonl (elle "golden" x3 + "refined" x1) ───────────────────────────┤
brain_distill.jsonl (AURA_DISTILL_LOG=1 → Railway diski) ─────────────────────┤
                                                                              ▼
                                          prepare_training_data.py  ──► train.jsonl
                                                                              ▼
                                          finetune_modal.py (Unsloth QLoRA)  ──► aura-lora/
                                                                              ▼
                                          modal_app.py (LoRA yükle / merge)  ──► serve
                                                                              ▼
                                          eval_brain.py (--gemini baseline + aday)  ──► eval_results.md
```

## Eğitim (tetik hizalanınca)

Önkoşul: ~3-5k toplam örnek (golden + refined + distill) + ~$300-600 + bir hafta sonu.

1. `brain_distill.jsonl`'i Railway diskinden indir (`railway ssh` → `cat > brain_distill.jsonl`).
2. `python prepare_training_data.py --golden golden_set.jsonl --distill brain_distill.jsonl --out train.jsonl`
3. `modal volume put aura-ft-data train.jsonl /train.jsonl`
4. `modal run finetune_modal.py` — A10G'de Qwen2.5-7B QLoRA ~30-90 dk. 14B için
   `FT_GPU=A100-40GB` + Modal'a ödeme yöntemi. Türkçe temel denemek için
   `FT_BASE=unsloth/<...>` (Trendyol/YTÜ Cosmos 4-bit varsa).
5. Çıkan adapter: `aura-ft-out/aura-lora/`. `modal_app.py`'de vLLM `enable_lora`
   ile yükle **veya** `merge_and_unload` → HF'e push → `MODEL_ID` yap.
6. `python eval_brain.py --url <modal-url> --key <AURA_BRAIN_KEY>` → `eval_results.md`'ye
   satır ekle. **GENEL < 4.0 ise deploy ETME**, veriyi/rank'ı ayarla, tekrar.
7. Geçerse: `AURA_BRAIN_URL` Railway'e → Aura kendi beyni. Hibrit: fine-tune Aura
   = varsayılan; Gemini `route_request` `deep` tier'ı için çağrılan ajan.

## İlke

Karakter kaymasını önlemek: her fine-tune sürümü aynı eval setinden geçer,
golden set sürüm kontrollü, Gemini her zaman geri dönülebilir yedek
(`AURA_BRAIN_URL` sil).
