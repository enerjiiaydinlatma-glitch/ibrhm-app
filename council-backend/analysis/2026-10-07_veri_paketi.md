# Sign Council — Veri Paketi (2026-10-07)

Kaynak: YouTube Studio ve Mission Control ekranlari (5-7 Ekim 2026). Sadece ekranda gorunen sayilar; yorumlar ayri etiketli.

## Kanal (son 28 gun, 9 Eyl - 6 Eki)
- Goruntuleme 2.129 (onceki 28 gun: ~6.021; Mission Control: 1.887 vs 6.021)
- Izlenme suresi 3,6 saat (onceki doneme gore -%56)
- Abone +4 (onceki doneme gore -%78); toplam 26
- Son 48 saat: 6-18 goruntuleme
- Kanal ulkesi ABD yapildi; izleyicilerin %100'u TR (800/800 izlenme)
- Turkce altyazi: 48 videoda zaten vardi, 8'ine eklendi, 1 kaynak hazir degil

## Shorts (son 28 gun)
- Goruntuleme ~2,1 B (kanalin neredeyse tamami Shorts)
- Begeni 97 (-%43), abone +4 (-%43)
- Kesif: Shorts akisi %77,3 | YouTube arama %14,0 | Kanal sayfalari %5,7 | Diger %3
- Izlemeye devam edenler %15,5 / izlemeden gecenler %84,5
- En populer 5 Short: Council Case #3 "Should I tell my boss..." 305 | Anthropic jumps to top rank as OpenAI... 224 | The Council Decides: "Should I take a st..." 187 | What is a 'control point' in AI infrastructure 178 | Did Cognition score 92.8 on a benchmark... 165
- Son Shorts "Three AI Safety Claims Fail Inspection While Two Pass": ilk 1 gunde 1 goruntuleme, 1 yorum, 0 begeni
- Son 5 video: 223 / 14 / 5 / 3 / 1 goruntuleme
- Son uzun/topluluk yayini: 14 Eylul (anket, 0 oy)
- Grafik: 13 Eyl civari ~700 tek tepe; sonra duz; 5 Eki civari ~250 kucuk tepe

## Buyume makinesi (1000 izlenme basina)
- Abone 2,65 (onceki 3,65, hedef 8, %33)
- Yorum 0 (onceki 1, hedef 2)
- Paylasim 0,53 (onceki 0,66, hedef 1)
- Begeni 48,22 (onceki 34,88)
- 26 Eylul sonrasi yeni kurallarla uretilenler: 9 video, 284 izlenme -> abone 3,52, yorum 0, paylasim 0 (/1000)
- Derin test: 84/87 gecti, 0 hata. Uyari: medyan izlenme >=50 hedefi icin 6; toplam yorum >=5 icin 0

## Uygulanmis kararlar (25-26 Eylul)
- Sesli takip cagrisi her videonun sonunda
- 27 videoda hic yorum yok -> aciklamaya tek cumlelik soru, kapanis sorusu
- 9 videoda izlenme tutma <%18 (14,8 / 16,9 / 14,5) -> ilk cumle (kanca) kisalt, ilk 3 sn'de sonucu soyle
- Hashtag: #Nvidia ort. 420 izlenme (3 video), #Ekonomi 60 (6 video) — ornek az

## Operasyon
- Zamanlanmis gorev SignCouncilDaily 2026-10-07 16:00'da hata verdi (kod 3221225786 = 0xC000013A, islem sonlandirildi)
- Bugunku video: yayinlanmadi (Mission Control "HENUZ YOK"), otomatik zamanlayici kapali
- Gunluk limit simdi 1 video; 2'ye cikma karari bekliyor

## Degismez korumalar (gevsetilemez)
1. sensitivity_gate.py "critical": suc + kasitli-ortbas iddialari otomatik reddedilir
2. operator_rules.md PRIORITY: cikar catismasi (kendi odevini kendi notlayan sirket) birincil kriter
3. aura_engine.py gunluk video kilidi (.uploaded_today.json) — 2'ye guncellenecek, kaldirilmayacak
Gecmiste 2-3 video/gun denendi; kalite dustu, 2 video hukuki riskle silindi ("OpenAI suc isledi + kasitli ortbas" kaynaksiz iddiasi).

## Bugunku aday konu (Nvidia)
- "Nvidia Sells the Chips. Then Funds the Buyers." (cikar catismasi acisi)
- "Who Really Controls AI? Not the Model Makers." (altyapi kontrol noktasi)
- "Nvidia Made $[X] in One Quarter. Here's Who Paid." (musteri yogunlasmasi)
- "Nvidia + Hugging Face: Open Source, Closed Door?"
