# Gunde 2 video — 7 gunluk pilot plani (2026-10-07)

Durum: TASLAK. Danisma Odasi turu veri paketi okunmadan yapildi (uyduruk rakamlar cikti); tur yeniden calistirilmali. Kilit guncellemesi (aura_engine.py) repoda olmadigi icin uygulanmadi.

## Degismez korumalar (pilot boyunca ayni)
1. sensitivity_gate.py "critical": suc + kasitli-ortbas iddiasi -> otomatik red.
2. operator_rules.md PRIORITY: cikar catismasi birincil kriter.
3. Gunluk video kilidi: siniri 1 -> 2 yap, KALDIRMA. 3. deneme sert red. (.uploaded_today.json)
Kaynak kartinda yalnizca gercek belge adi + tarih. "Verified", sahte link, uydurma logo YOK.

## Yapi
- Video 1 (16:00 TR): mevcut ana format, Ingilizce. Degismez.
- Video 2 (aksam slotu; saat: 21:00 TR onerisi — ABD gunduz/ogleden sonra): TURKCE anlatim, ayni konu, 20-30 sn, Ingilizce kaynak altyazisi.
- Ilk gun(ler)de Video 2 = Video 1'in Turkce versiyonu (adil karsilastirma).
- Ikilem formati kullanilmaz.

## Geri cekilme (taban degerine gore; mutlak esik degil)
Taban (28 gun): izlemeye devam %15,5 | medyan izlenme ~6 | yorum 0/1000 | abone 2,65/1000
- Tek sensitivity_gate "critical" uyarisi -> Video 2 hemen kapanir.
- Ana formatin "izlemeye devam" orani pilotta %15,5'in altina duserse -> Video 2 durur.
- 7 gun sonunda Turkce video, Ingilizce esine gore izlemeye devam veya medyan izlenmede ustun degilse -> pilot biter, tek videoya don.
- Gunluk kilit 2'yi asarsa -> sistem durur, elle incele.
Not: ~7 video istatistiksel kanit degil, sadece yon.

## Gunluk olcum
`python daily_check.py` (bugun kac video, izlenme/saat, gecmis kaydi). Studio'dan elle: izlemeye devam %, Turkce vs Ingilizce karsilastirma.

## Acik is listesi
- [ ] Veri paketini Danisma Odasi'na yuklu oldugunu dogrula, turu yeniden calistir
- [ ] aura_engine.py kilidi 1 -> 2 (dosya repoya eklenince)
- [ ] 2. slot zamanlamasi (SignCouncilDaily'nin 16:00 hatasi 0xC000013A: pencere/oturum kapanmasi)
- [ ] Turkce anlatim hattini (ses + metin) Mission Control'de dogrula
