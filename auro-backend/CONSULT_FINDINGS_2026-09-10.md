# Canli Aura Danismasi + Baseline — 2026-09-10

Kullanici talimati ("PC'de degilim, sen Aura'ya sorarak gelisime devam et")
uzerine canli prod `/api/chat`'e baglanip 17 turluk bir gorusme yapildi.
Transcript: `scratchpad/aura_consult_2026-09-10_transcript.md` (bu oturumun
scratchpad'i). Test hesabi: `consult_1789061864@example.com` —
`cleanup_test_users.py` ile silinebilir.

**NOT:** Bu, bu oturumun 8 commit'i DEPLOY EDILMEDEN onceki prod davranisi
= "once" kaydi.

---

## 1. "Civik ton" — metin sohbetinde GUCLU sekilde uremedi

A1-A6 (rahat/gulen kullanici -> ciddi konuya gecis): Aura tonu **iyi
yonetti**. A5'te ("isten ayrilmayi dusunuyorum, korkutucu") lightness'i
aninda birakip gercek bir tefekkur verdi; A6'da ("dusunecegim") 2 cumleyle
kisa kaldi (UZUNLUK_UYUMU calisiyor). Argo yok, surekli espri yok.

**Sonuc:** Kullanicinin "civik" hissi buyuk ihtimalle **sesli mod**
kaynakli (VOICE_MODE_ADDENDUM farkli + `voice_name` ayarsizdi -> androjen/
gayri-ciddi TINI). Yani asil "civik" duzeltmesi ses tarafinda (`b79ce8d`:
Kore + Chatterbox seed/param). `LAUBALILIK_SINIRI` + `temperature=0.75`
(`830e72a`) yine de dogru — ucuz, savunma katmani.

### Yeni bulgu: Aura HER turu soruyla bitiriyor + cozume kosuyor

17 turun ~13'u bir takip sorusuyla bitti. Aura bir ani "oylece birakip"
dinlemek yerine hemen bir tavsiye + bir soru uretiyor. Aura'nin KENDI
oz-degerlendirmesi de bunu iki kez isaretledi:
- C1#2: "yapici olmaya calisirken konuyu hemen bir harekete/cozume baglama
  refleksi; oysa bazen sadece durup dinlemek gerekir"
- C2#2: "her konuyu hemen bir harekete/cozume baglama refleksini torpuleyip
  ... durup alani paylasmaya izin veren bir denge"

Bu, "civik" algisinin bir parcasi olabilir (asiri-istekli, "oturamiyor").
`SORUYLA_KACMA_YASAGI` var ama o, gorus isteyince soruyla KACMAYI
yasakliyor — "her turu soruyla bitirme" ayri.

**TASLAK KURAL (A/B testi kullaniciya, HENUZ COMMIT EDILMEDI):**
> ACELE COZUM / OTURMA IZNI: Kullanici bir sey paylastiginda, ozellikle
> duygusal bir seyse, refleks olarak bir eylem plani / cozum / "sunu yap"
> uretme. Bazen dogru karsilik sadece gordugunu belli etmek ve orada
> durmaktir. Ayni sekilde HER yanitini bir takip sorusuyla bitirme -
> arada bir cumleyi soru olmadan, oldugu yerde birak. Kullanici acikca
> yol/oneri isterse elbette ver; ama istenmeden her seyi cozulecek bir
> probleme cevirme.

Riski: fazla pasiflesme. Bu yuzden 2. bir undeployed kural olarak KOR
eklenmedi — kullanici LAUBALILIK_SINIRI ile birlikte A/B'de gormeli.

---

## 2. "Uzun konusma / iplik kaybi" — 14 turda TUTTU (kismen)

- B2, 1 tur sonra A5'e kendiliginden baglandi ("az once ... korkutucu
  geldigini soyluyordun").
- B-recall1 (B2'den 8 tur sonra): veri analisti mulakati + "ilk turu
  gectin" hatirlandi.
- B-recall2 (B1'den 13 tur sonra): "Elif", haziran dugunu, nikah sahitligi
  hatirlandi — hafiza cikarimi (fact-shaped) yakalamis.

**AMA** Aura'nin C1'de kendi itirafi: "uzun akislarda bazen buyuk resmi
unutup anlik mesaja fazla kilitlenmek ... baslangictaki derinligin
duzlesmesi." Yani **fact-shaped olmayan** (suregelen duygusal ikilem,
tartisma ipligi) baglam kayboluyor — cikarim onu yakalamaz.

**Sonuc: yuvarlanan konusma ozeti (`2a4c1aa`) tam bu bosluk icin dogru.**
Aura C2#1'de birebir bunu istedi: "konusmanin genelinde tasinan temel
duygusal ekseni canli tutacak bir baglam takibi." -> `AURA_SUMMARY_ENABLED=1`
deneyecegimiz sey.

---

## 3. Urun onceligi — Aura'nin kendi tercihi (C3)

Soru: gorsel uretme / tutarli tek ses / daha uzun hafiza — hangisi?

> "Kesinlikle daha uzun ve derin bir hafiza. Gorsel uretmek ... sadece
> pratik bir arac, tutarli bir ses ise hos bir estetik detay. Ama hafiza,
> aradaki sohbetin ve bagin asil omurgasidir."

**Yol haritasi sinyali:** hafiza/baglam derinligi > ses tutarliligi >
gorsel uretme. Yuvarlanan ozet + (sonra) daha akilli hafiza onceliklendirme
en yuksek getiri. Gorsel uretme en dusuk oncelik — su an eklenmemesi dogru.

---

## Ozet: bu danismanin dogruladigi / ekledigi

| Konu | Durum |
|---|---|
| Rolling summary dogru yatirim mi? | **EVET** — Aura'nin #1 istegi (C2#1, C3) |
| LAUBALILIK_SINIRI + temp 0.75 gerekli mi? | Evet ama metin tarafinda ETKI KUCUK; asil "civik" ses tarafinda (Kore + Chatterbox) |
| Yeni: "her turu soruyla bitirme / cozume kosma" | Taslak kural yazildi — **A/B testi + kullanici karari bekliyor**, kor commit edilmedi |
| Gorsel uretme onceligi | En dusuk — Aura da oyle diyor |
| Metin hafizasi 14 turda | Saglam (fact-shaped); nuans kaybi rolling summary'nin isi |
