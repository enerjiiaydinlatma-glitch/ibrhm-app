# Trader Lab

Çok piyasalı (BIST, ABD, Londra, Frankfurt, Tokyo, Hong Kong) **paper-trading** ve analiz laboratuvarı.
**Gerçek para / gerçek emir YOK.** Aura uygulamasından bağımsızdır (`trader-lab/`).

## Kurulum (kendi bilgisayarında)

Gerekenler: Python 3.11+, internet (Yahoo Finance verisi için). Başka hesap/anahtar gerekmez.

```bash
cd trader-lab
./run.sh            # venv kurar, bağımlılıkları yükler, http://127.0.0.1:8000 açar
```

Testler: `python -m pytest -q tests`

Opsiyonel: `hybrid` ve `agent` modları için `export ANTHROPIC_API_KEY=...` (model: `TRADER_LLM_MODEL`, varsayılan `claude-sonnet-5-5`).
Anahtar yoksa sistem otomatik **kural moduna düşer** ve panelde bunu yazar.

Veri kaynağı `auto`: önce Yahoo, erişilemezse **SENTETİK** veri (panelde kırmızı uyarı). Sentetik veri yalnızca test/demo içindir,
oradan çıkan hiçbir sonuç gerçek performans kanıtı değildir.

## Üç karar modu
| Mod | Nasıl çalışır |
|---|---|
| `rule` (A) | Tamamen deterministik. Backtest ve walk-forward yalnız bununla yapılır. |
| `hybrid` (B) | Kural sinyali üretir; LLM sadece onay / azalt / **veto** diyebilir, boyutu artıramaz. |
| `agent` (C) | LLM adayları seçer; sistemde olmayan sembol reddedilir; yine risk motoru + stop kurallarından geçer. |

LLM kararları tekrarlanamaz olduğu için backtest edilemez; yalnızca canlı paper hesapta ölçülür (karar defteri + veto değeri).

## Farklılaştıran parçalar
- **Aynı motor** backtest ve canlı paperda çalışır; sapma olmaz.
- **Dürüst maliyet:** komisyon, vergi/harç, hacme katılımla artan kayma, bir sonraki açılışta dolum, gap'te stop, FX spread.
- **Karar defteri:** her kararın girdisi, gerekçesi, "ne zaman haksız çıkarım" koşulu; SHA-256 zincirli (kurcalanırsa bozulur).
- **Veto değeri:** reddedilen sinyalin 10 gün sonraki "gölge" getirisi → beyin vetosu değer kattı mı?
- **Rejim bilinci:** TREND_UP / TREND_DOWN / RANGE / HIGH_VOL; strateji yalnız uygun rejimde girer.
- **Walk-forward kapısı:** eğitimde parametre seç, görülmemiş dönemde test et; geçmeyen strateji "güvenilir" sayılmaz.
- **Risk motoru** (aşılamaz): işlem başı %1 risk, pozisyon/borsa/likidite limiti, günlük %3 kayıp ve %15 drawdown freni (20 gün soğuma).

## Para birimi
Her borsa kendi para biriminde işlem görür. Panelde tek baz para ile **gösterim bedavadır** (sadece değerleme).
Maliyet yalnızca gerçek dönüşümde doğar. İki mod karşılaştırılabilir (Araştırma → "Cüzdan vs tek para"):
- `per_market`: her borsaya yerel cüzdan (çeviri yok).
- `single_base`: tek baz para, her alımda çevirme (spread 30 bps + 5 bps ücret) ve satışta geri çevirme.

Nakit faizi (`config.CASH_RATE`) bir **varsayımdır**; kendi mevduat oranına göre güncelle.

## Sınırlar (bilmen gerekenler)
- Veri günlük ve ücretsiz (Yahoo, BIST ~15 dk gecikmeli): gün içi/scalping yok, swing/günlük stratejiler.
- Komisyon/vergi oranları yaklaşık; kendi aracı kurum tarifene göre `trader/config.py` içinde güncelle.
- Hiçbir strateji kâr garantisi vermez; kapıyı geçmek de kâr garantisi değildir.
- Gerçek emir göndermek için ayrı bir broker adaptörü gerekir; bilinçli olarak eklenmedi.
