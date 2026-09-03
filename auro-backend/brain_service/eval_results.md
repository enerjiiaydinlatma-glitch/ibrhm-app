# Aura beyin eval sonuçları

`eval_brain.py` + `eval_set.jsonl` (15 elde tutulan zor test).
Yargıç: Gemini 3.7 Flash, rubrik 1-5.

| Tarih | Model | Türkçe | Karakter | Doğruluk | Uzunluk | Expect | **GENEL** | Not |
|---|---|---|---|---|---|---|---|---|
| 2026-09-03 | **Gemini 3.7 Flash** (canlı Aura) | 5.00 | 4.87 | 4.93 | 5.00 | 4.87 | **4.93** | Baseline. Aşılması gereken çıta. |
| 2026-09-03 | Qwen2.5-14B-**AWQ** (prompted, Modal A10G) | 2.27 | 1.67 | 3.33 | 3.33 | 2.40 | **2.60** | Genel-asistan tonu, bozuk Türkçe ("sosisetti"), bir test Çince'ye kaydı. Heuristik 15/15 (regex zayıf). |
| 2026-09-03 | Qwen2.5-7B (prompted, Modal A10G) | — | — | — | — | — | ~2.3* | Formal eval yapılmadı; elle test: uydurma kelime + kelime salatası. 14B'den kötü. |

\* tahmini

## Yorum

- **Prompted generic açık model (7B/14B) Aura'nın çıtasına ulaşmıyor** — kesin. Gap 2.3 puan (4.93 → 2.60).
- Fine-tune hedefi: **≥ 4.0 GENEL** (tercihen ~4.5+). Altı regresyon, deploy edilmez.
- LoRA (7-14B) + iyi veri ile makul beklenti ~3.5-4.3. Gemini'yi yakalamak belirsiz — ama artık ÖLÇÜLEBİLİR.
- Yargıç Gemini olduğu için hafif "Gemini-tarzına yanlılık" olabilir; ama 14B'nin somut hataları (dil kayması, bozuk kelime) objektif.

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
