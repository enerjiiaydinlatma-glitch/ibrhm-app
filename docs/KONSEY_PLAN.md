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

## Gozlem 20 Eki 2026 (Studio mobil, 28 gun) - yon, kanit degil
- 28 gun: 668 goruntuleme, 0,8 saat. Kitle: %94 yeni izleyici, %6 sirada, duzenli <%0,1. Kesif: Shorts akisi %71,4, YouTube arama %24,3, kanal sayfalari %2,2.
- Yeni videolar: 82 (insan yuzlu robot) ilk ~18 saatte 8 goruntuleme, 1 begeni, ort. izleme %24,2, son 10 videoda 4. sira; 29 (deniz 20 cm) ~41 saatte 2; 79 (buzun 1/4'u) 48 saatte 5.
- Hipotez: kanalin son aylari AI-haberiydi; YouTube kanali AI/teknoloji izleyicisine gosteriyor. Robot ve gelecek/YZ konulari afetten iyi gidiyor (82 > 29/79; eski Konsey'de 21 ve 23 en iyiler). Tarama verisi (afet guclu) bu kanalda tutmadi.
- ONERILEN SIRA (onay bekliyor): 22 Eki konu 74 (YZ'yi kim yonlendirecek), 23 Eki konu 27 (YZ is secer mi, WEF), 24 Eki konu 84 (robotlar robot uretse), 25 Eki konu 83. Afet (81) ve gizem/kuantum (90, 65) hafta 2'ye. Afet'e n>=3 kurali: 2 video yayinda.

- YouTube arama terimleri (28 gun, ~160 arama goruntulemesi; her terim 1-4): "laws in india require us to remind you ab..." 4, "movie subscription service" 2, "tvos 27" 2, ve 1'er: "gemini argon", "gemini mental breakdown", "mac studio ai", "macbook neo macos 27", "hals eulogy", "con quay"... Son 7 gun: "movie subscription service" 2 (arama goruntulemesinin %11'i), "sill open source" 1.
- Okuma: arama trafigi uzun kuyruk ve haber-olayina bagli (eski AI-haber videolari); Konsey'den yalniz gundelik konulu "movie subscription" videosu aramadan geliyor (duz anahtar kelimeli baslik). Hacim cok kucuk (gunde ~1-2): henuz kaldirac degil. Kural: baslikta insanin aratacagi duz ifade bulunsun ("AI take jobs", "robot human face", "sea level rise"), ilk cumle/aciklama ayni ifadeyi tekrar etsin. Veri biriktikce tekrar bak.

## Gozlem 22 Eki 2026 (Studio masaustu) - yon, kanit degil
- 28 gun (24 Eyl-21 Eki): 582 goruntuleme (onceki 28 gune gore %93 az), 0,7 saat, +1 abone (%94 az). Abone: 26. Son 48 saat: 33 goruntuleme.
- Yeni videolar (toplam goruntuleme): 79 buzun 1/4'u ~5, 29 deniz 20 cm 2, 82 insan yuzlu robot 17 (2 begeni), 25 YZ ofis isleri 11, 74 YZ'yi kim yonlendirir 9 (ilk ~16 saat, ort. izleme %46,2, son 10 videoda 2. sira). Eski gundelik "Would You Ride With No Driver?" 26. Yorum: tum yeni videolarda 0.
- Siralama (yon): robot/YZ (9-17) >= gelecek (11) > afet (2-5). Tutarli: kanalin AI-izleyicisi robot/YZ'ye daha yakin. Afet duraklatildi (81 hafta 2); afet'te n=2.
- Taban 8-21/48 saat; robot/YZ videolari tabanin ust-yarisinda, belirgin basari esigi (50+) HICBIRI gecmedi. Kanal hala 20-30 gorunt./gun bandinda.
- YENI SIRA (uygulaniyor): 23 Eki konu 84 (robotlar robot uretse; robot_18000 olgusu), 24 Eki konu 83, 25 Eki konu 27 (WEF; 25 ile ayni rakamlari art arda kullanmamak icin ertelendi).
- Acik soru: dagitim (abone 26, %94 yeni izleyici). Secenek: ayni videolari TikTok/Reels'e de koymak (calisan kanal disi dagitim, organik).

## Yayin kaydi (video | yayin 02:30 TR | link | sabit yorum)
- 18 Eki | 79 buzun 1/4'u (afet) | https://youtu.be/R0NutGxhpy4 | "what would YOU do?"
- 19 Eki | 29 deniz 20 cm (afet) | https://youtu.be/JfW2Xp9oxR8 | "what would YOU do?"
- 20 Eki | 82 insan yuzlu robot (robot) | https://youtu.be/TFpREc7fybw | "what would YOU do?"
- 21 Eki | 25 YZ ve ofis isleri (gelecek) | https://youtu.be/A6Px0zAwp7E | "guilty habit?"
- 22 Eki | 74 YZ'yi kim yonlendirir (robot/YZ) | https://youtu.be/ghhL_K4Z2MQ | "what would YOU do?"
- 23 Eki | 84 robotlar robot uretse (robot) | https://youtu.be/Pp3NqM2P9II | "what would YOU do?"
- 24 Eki | 83 Could Your Friend Be A Robot? (robot) | https://youtu.be/pD_euLit6Lw | "what would YOU do?"
- 25 Eki | 44 Would You Work for a Robot Boss? (robot) | https://youtu.be/KhhZ52juSVw | "what would YOU do?"
- Siradaki: 26 Eki konu 76 veya 42 (robot sutunu; basliginda 'robot' gecsin) - 25 Eki'de hazirla. Konu 27 (WEF is) ertelendi (hakem gelecek konularinda da calisiyor).
- 26 Eki | 76 What If We Built A Robot Every Minute? (robot; 18.000 olgusu, "Comment your pick." CTA deneyi) | https://youtu.be/m7Zj83F_PsU | "what would YOU do?"
- KARAR (25 Eki, sahip): HABER/GUNDEM yonu YOK (kanal haber kanali olmayacak). Evergreen robot/insan-robot sutunu devam. Bekleyen veri: 83/84/44 icin Studio Etkilesim: izlendi/kaydirildi + ort. izleme %; onceki donemin (27 Agu-23 Eyl) en cok izlenen 10 videosu.
- Deney onerileri: 20-25 sn; ilk 2 sn hareketli gorsel (GPU modeli gerekli); kapanista ekranda net A/B; TikTok/Reels dagitimi.
- ESKI SATIR: 25 Eki konu 27 (WEF, 24 Eki'de hazirla). Kapi: editor hakemi + tamir modu devrede (konsey_gun).

## Gozlem 24 Eki 2026 (konsey_kontrol.py) - yon, kanit degil
- Yeni nis (goruntuleme | yas): 79 buz 5 | 160 sa; 29 deniz 2 | 136 sa; 82 yuzlu robot 17 | 112 sa; 25 YZ is 8 | 88 sa; 74 YZ yonlendirme 10 | 64 sa; **84 robotlar robot uretse 34 | 40 sa (0,85/sa); 83 "Could Your Friend Be A Robot?" 36 | 16 sa (2,24/sa)**. Eski gundelik: 15, 16, 15, 33, 0, 26 (yas 160-265 sa).
- 84 ve 83 tabani (8-21/48 sa) KIRDI; 50+ esigine yaklasiyor (83, 16 saatte 36). Yorum 0 (neredeyse hepsi), begeni 0-2.
- Hipotez: basliginda "robot" gecen robot-sutunu + kapi guclendirme sonrasi tutarli senaryo. 82 (basliginda 'robot' yok) 17, 74 (YZ) 10. n kucuk; erken hiz (taze videolar onde yuklu) yaniltici olabilir: 24-48 saat sonra tekrar bak.
- Karar: robot sutunu devam; sonraki konular basliginda 'robot' gecen ve kisisel-secim soran (44 robot patron, 42 robot yasalari, 76 seri uretim). 27 (WEF is) 25'in ardindan ertelendi.

## Gozlem 25 Eki 2026 (konsey_kontrol.py) - yon, kanit degil
- 83 "Could Your Friend Be A Robot?" 39 (42 sa; 16 saatte 36 idi), 84 "What if robots build all new robots?" 38 (66 sa; 40 saatte 34 idi): ILK ~1 GUNDE yuklenip DURDULAR (platoya girdi). 44 "Would You Work for a Robot Boss?" 19 (18 sa, 1,07/sa). 82: 17 (138 sa), 74: 12 (90 sa), 25: 11 (114 sa), 79: 5, 29: 2.
- Siralama: baslikta "robot" gecenler (83 39, 84 38, 44 19+) > diger (17, 12, 11) > afet (5, 2). Tavan ~40 goruntuleme/video; 50+ esigi gecilmedi; tabani (8-21/48 sa) ~2x asti. Yorum 0, begeni 0-2 (12 videoda ~0 yorum).
- Yorum: %94 yeni izleyici 'Alpha/Beta'yi bilmiyor olabilir; kapanista dogrudan yonerge ("Comment your pick.") deneyi.
- DENEY: sonraki 3 videonun kapanisina "Comment your pick." ekle; yorum sayisini karsilastir. Diger: insan-robot kimlik konulari (83>82) ve 'robot' baslikta.

## Gozlem 25 Eki 2026 - Studio icerik tablosu (27 Eyl-24 Eki, 28 gun) - yon, kanit degil
- Toplam 611 goruntuleme, 0,6 saat, +1 abone. 'Kucuk resim gosterimi' toplam 1.375 ama Shorts akisi goruntulemeleri kucuk resimden gelmez (223 goruntulemeli haber videosunun gosterimi 12): GOSTERIM METRIGI SHORTS ICIN ANLAMLI DEGIL; kullanma.
- ESKI AI-HABER (uzun: 0:36-1:47): 223 (tek aykiri deger = kanalin toplamin %36,5'i), 38, 18, 10, 8, 8, 6, 6, 4, 3, 3, 3, 3, 3, 2, 1... -> medyan ~3. Konsey (0:31-0:36): 38, 38, 33, 26, 17, 16, 15, 15, 15, 13, 11 (+ 5, 2, 2) -> medyan ~15. Yani Konsey, eski haber hattinin ~5 kati medyan; 'haber kazanir' sonucu TEK aykiri degerden cikmisti (duzeltme). HABER yonu sahibin karariyla YOK.
- Tek abone (%100) 1:17'lik aciklayici bir videodan ("Open weights is not open source"), hicbir Konsey videosundan degil.
- Gerekli: onceki donem (27 Agu-23 Eyl) icerik tablosu (tarih araligi DEGISTIRILMELI) + 83/84/44 icin izlendi/kaydirildi.

## ONEMLI BULGU 25 Eki 2026 - tutma (retention) sorunu; onceki donem (27 Agu-23 Eyl) + Studio Etkilesim
- Onceki donem: 7.454 goruntuleme, 10,2 saat (=> goruntuleme basina ORT. ~4,9 SANIYE), +18 abone; 45 video (hepsi eski AI-haber/'Council Case', cogu 1:27-1:57 uzunlukta, gunde 1-5 video). Medyan 112 goruntuleme/video. Yayin tarihine gore: 24 Agu-14 Eyl videolari 63-1.149; 15 Eyl SONRASI 2-38 (13-14 Eyl 'Council Case' 305/187/140/116, 17-20 Eyl 'Council' 20/16/11/10). Dusus 15 Eyl civarinda, format degisikliginden ONCE/bagimsiz: yeni kanal 'balayi' itmesi sonrasi taban.
- Yeni formatin (Konsey) izlenme basina suresi daha IYI: 83 ort. 8 sn, 84 17 sn, 44 20 sn (eski donem ~5 sn).
- AMA 'izlemeye devam / kaydirildi' (son 28 gun): 83 %11,6 / %88,4; 84 %7,9 / %92,1; 44 %28,6 / %71,4. Ort. izleme %: 83 24,2; 84 49,5. YANI ILK SANIYELERDE %71-92 KAYDIRIYOR. 44 (hook: 'Would you take orders from a robot?') en iyi tutma.
- Karar: ANA KPI = 'izlemeye devam %' (hedef >= %40), goruntuleme degil. Haber yonu yok (sahip karari). Retention deneyi: <=25 sn, ilk 1,5 sn'de guclu gorsel + ses vurusu, 'sen'li somut kanca, hizli kesme.

## Gunde 2'ye gecis sarti (hafta sonu okumasinda uc maddenin UCU de)
1. Ust uste 3 video ilk senaryoda ya da tek duzeltmeyle cikti.
2. En az bir video kanal medyaninin ustunde.
3. Hicbir videoda gercek hata (yanlis rakam/baglam, ses) yok.
Bir sutun belirgin one cikarsa o sutundan ikinci video eklenebilir (acik karar noktasi).

## Bekleyen
- `python nis_tarama.py --nis gizem` ve `--nis bilimkurgu_kuantum` (kota ~800 birim/nis; yuklemeler kotayi yer, ertesi gun dene) -> diger nislerle karsilastirma.
- Panel anahtari yenileme. Rakam bankasi genisletme (konu/kaynak onerisi).
