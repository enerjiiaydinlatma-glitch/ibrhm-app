# Sign Council - 2 Haftalik Deney Plani (onay: 17 Ekim 2026, gunde 1 video)

Amac: kanal buyumesi. Henuz konu basina izlenme verimiz yok; bu plan bir DENEY planidir, kanit degil yon gostergesi uretir.

## Sabitler
- Gunde **1** video. Yayin saati hep **02:30 Turkiye saati** (ABD aksami). Saat degisimi karismasin diye hafta 1'de sabit.
- Video once OZEL yuklenir, `--saat` ile zamanlanir; saati veren onay vermis olur. Hicbir sey saat verilmeden yayinlanmaz.
- Her video: kapi + senin izleme/onayin. Rakam yalniz `rakam_bankasi.py` olgularindan.
- Yayindan sonra Studio'da sabit yorum: `Team Alpha or Team Beta? Vote below. And what would YOU do?`

## Takvim (yayin tarihi | konu | sutun | hazirlama gunu)
| Yayin (02:30 TR) | Konu | Sutun | Hazirlama |
|---|---|---|---|
| 18 Eki | 79 buzun 1/4'u (yuklendi) | afet | - |
| 19 Eki | 29 deniz 20 cm (yuklendi) | afet | - |
| 20 Eki | 82 insan yuzlu robota guven | robot | 18 Eki |
| 21 Eki | 25 YZ ofis islerini degistirir mi (WEF) | gelecek | 19 Eki |
| 22 Eki | 90 su alti magara baska dunyaya | gizem | 20 Eki |
| 23 Eki | 81 60 cm su sokaktan akarsa | afet | 21 Eki |
| 24 Eki | 65 bir saniyede isinlanma | kuantum | 22 Eki |

Komut: `python konsey_gun.py --konu N --saat "2026-10-DD 02:30"` (ses sunucusunu kendisi acar, onaylari sen verirsin).

## Olcum
- Yayindan ~3 saat ve 24 saat sonra: `python konsey_kontrol.py`
- Hafta sonu (24-25 Eki): `python haftalik_rapor.py` + konsey_kontrol ciktisi + Studio'dan "izlendi/kaydirildi" orani ve ulke dagilimi.
- Kayit alanlari (konsey_kayit.jsonl): konu_id, kategori, baslikta_rakam, kaynakli_rakam (18 Eki oncesi iki kayitta yok).

## Karar kurallari (onceden yazildi)
- Bir sutun, en az **3 video** olmadan elenmez. Hafta 1'de afet disindaki sutunlar n=1: yalniz yon.
- Olcut: 48 saatlik izlenme / kanalin son 14 gunluk medyani. Ortalama degil MEDYAN.
- Yorum kalitesi: kisisel cevap orani ve yorum sayisi (espri yorumlari etkilesim sayilmaz).
- Hafta 2: en iyi 2 sutunu tekrarla, en zayif 2'yi yenisiyle degistir. Saat degisecekse TEK degisken olarak.

## Kanal tabani (Studio, 19 Eyl - 16 Eki 2026, Sign Council kanali; 17 Eki 2026'da alindi)
- 28 gun: **700** goruntuleme (onceki 28 gune gore %92 az), 0,9 saat izlenme (%92 az), **+1 abone** (%95 az). Son 48 saat: **42** goruntuleme.
- En cok izlenenler eski AI-haber formatindan (223, 138, 46, 37, 19). Konsey (gunluk konular) son 48 saatte: 21, 12, 8.
- Yeni videolarin ilk 12 saatinde 0 goruntuleme gorulebiliyor (ornek: "Would You Let AI Plan Your Week?").
- Yorum: dusus yeni formattan ONCE basladi (haftalik rapor); format/konu tek basina cozmeyebilir, dagitim (kucuk kanala test kitlesi) etkili olabilir.

## Basari esikleri (taban uzerinden)
- Taban: Konsey videosu basina 48 saatte ~8-21 goruntuleme. **50+ = belirgin basari (tabanin 3-5 kati)**; **25 alti = gurultu**.
- Bu duzeyde sutunlar arasi fark rastgele olabilir. Hafta 1'in ana sorusu: yeni nisteki videolar 8-21 tabanini KIRIYOR MU (evet/hayir). Sutun sirasi kararlari n>=3 olmadan verilmez.
- Kisa video etkisi (tek gozlem): %106 ortalama izleme yuzdesi yalniz kisa (13-22 sn) videolarda goruldu; bizimkiler 33-38 sn. Hafta 2'de 20-25 sn'lik bir versiyon denenecek (karar noktasi).

## Gunde 2'ye gecis sarti (hafta sonu okumasinda uc maddenin UCU de)
1. Ust uste 3 video ilk senaryoda ya da tek duzeltmeyle cikti.
2. En az bir video kanal medyaninin ustunde.
3. Hicbir videoda gercek hata (yanlis rakam/baglam, ses) yok.
Bir sutun belirgin one cikarsa o sutundan ikinci video eklenebilir (acik karar noktasi).

## Bekleyen
- `python nis_tarama.py --nis gizem` ve `--nis bilimkurgu_kuantum` (kota ~800 birim/nis; yuklemeler kotayi yer, ertesi gun dene) -> diger nislerle karsilastirma.
- Panel anahtari yenileme. Rakam bankasi genisletme (konu/kaynak onerisi).
