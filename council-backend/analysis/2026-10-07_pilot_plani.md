# Gunde 2 video — 7 gunluk pilot plani (2026-10-07)

Durum: TASLAK. Danisma Odasi turu veri paketi okunmadan yapildi (uyduruk rakamlar cikti); tur yeniden calistirilmali. Kilit guncellemesi (aura_engine.py) repoda olmadigi icin uygulanmadi.

## Degismez korumalar (pilot boyunca ayni)
1. sensitivity_gate.py "critical": suc + kasitli-ortbas iddiasi -> otomatik red.
2. operator_rules.md PRIORITY: cikar catismasi birincil kriter.
3. Gunluk video kilidi: siniri 1 -> 2 yap, KALDIRMA. 3. deneme sert red. (.uploaded_today.json)
Kaynak kartinda yalnizca gercek belge adi + tarih. "Verified", sahte link, uydurma logo YOK.

## Yapi
- Dil: TUM anlatim Ingilizce. Turkce yalnizca altyazi secenegi (mevcut Turkce altyazi hatti). Turkce anlatim/Short serisi YOK.
- Video 1 (16:00 TR): mevcut ana format. Degismez.
- Video 2 (aksam slotu; saat onerisi: 21:00 TR = ABD ogleden sonra/aksam, onay bekliyor): Ingilizce, niche + efektli yeni format, 20-30 sn, kaynak karti gercek belge adi + tarih.
- Ikilem formati kullanilmaz.
- Kanal ulkesi ABD 3-4 gun once yapildi: "izleyicilerin %100'u TR" verisi gecikmeli olabilir. Pilotun ilk gunlerinde Studio > Kitle > Cografya'dan ABD payi izlenir; pay artiyorsa dil karari gereksiz.

## Geri cekilme (taban degerine gore; mutlak esik degil)
Taban (28 gun): izlemeye devam %15,5 | medyan izlenme ~6 | yorum 0/1000 | abone 2,65/1000
- Tek sensitivity_gate "critical" uyarisi -> Video 2 hemen kapanir.
- Ana formatin "izlemeye devam" orani pilotta %15,5'in altina duserse -> Video 2 durur.
- 7 gun sonunda Video 2'nin izlemeye devam veya medyan izlenmesi Video 1'den iyi degilse VE toplam erisim artmadiysa -> pilot biter, tek videoya don.
- Gunluk kilit 2'yi asarsa -> sistem durur, elle incele.
Not: ~7 video istatistiksel kanit degil, sadece yon.

## Gunluk olcum
`python daily_check.py` (bugun kac video, izlenme/saat, gecmis kaydi). Studio'dan elle: izlemeye devam %, Video 1 vs Video 2 karsilastirma, ABD/TR kitle payi.

## Acik is listesi
- [ ] Veri paketini Danisma Odasi'na yuklu oldugunu dogrula, turu yeniden calistir
- [ ] aura_engine.py kilidi 1 -> 2 (dosya repoya eklenince)
- [ ] 2. slot zamanlamasi (SignCouncilDaily'nin 16:00 hatasi 0xC000013A: pencere/oturum kapanmasi)
- [ ] Kitle cografyasi (ABD payi) 7 gun boyunca izlenir
- [ ] Yeni Ingilizce niche format tasarimi (Video 2)
