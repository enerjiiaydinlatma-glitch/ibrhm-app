"""KONSEY KONU HAVUZU - gunluk-hayat tartisma konulari (Ingilizce soru = --topic degeri, Turkce anlami yaninda).

Secim olcutleri: evrensel gunluk hayat (ABD izleyicisi icin de tanidik); gercek marka/kisi/siyaset/saglik tavsiyesi/cocuk/suc YOK;
iki tarafi olan (Alpha-Beta dogal bolunsun); Gamma'nin 'ben de yapiyorum' itirafina uygun; baslik kancaya donusebilir.
Kategoriler cesitli: hangi turun tuttugu haftalik raporda gorulsun.

Kullanim:
  python konsey_konular.py              # listeyi Turkce anlamlariyla yazdirir; kullanilanlari isaretler
  python make_topic_short.py --konsey --sadece-senaryo --konu 3     # havuzdan 3 numarali konu
Kullanilan konu = _engine/konsey_kayit.jsonl'de ('konu' alani) kayitli konu. Bu modul hicbir sey yuklemez/yayinlamaz.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KAYIT_YOL = os.path.join(HERE, "_engine", "konsey_kayit.jsonl")

KONULAR = [
    # para / alisveris
    {"id": 1, "konu": "Is free shipping really free?", "tr": "Ücretsiz kargo gerçekten ücretsiz mi?", "kategori": "para",
     "eksen": "Alpha: fiyata eklenir. Beta: yine de avantaj."},
    {"id": 2, "konu": "Is buying in bulk really cheaper?", "tr": "Toplu almak gerçekten daha mı ucuz?", "kategori": "para",
     "eksen": "Alpha: birim fiyat. Beta: yarısı çöpe gidiyor."},
    {"id": 3, "konu": "Is a sale price a real discount?", "tr": "İndirimli fiyat gerçekten indirim mi?", "kategori": "para",
     "eksen": "Alpha: etiket oyunu. Beta: ihtiyacım vardı."},
    {"id": 4, "konu": "Are loyalty cards worth the hassle?", "tr": "Sadakat kartları zahmetine değer mi?", "kategori": "para",
     "eksen": "Alpha: puan hesabı. Beta: cüzdan doldu."},
    {"id": 5, "konu": "Are extended warranties worth it?", "tr": "Uzatılmış garantiler değer mi?", "kategori": "para",
     "eksen": "Alpha: olasılık. Beta: rahatlık."},
    {"id": 6, "konu": "Is a daily coffee run a waste of money?", "tr": "Her gün dışarıdan kahve almak para israfı mı?", "kategori": "para",
     "eksen": "Alpha: yıllık toplam. Beta: günün tek keyfi."},
    {"id": 7, "konu": "Should you tip at a self-checkout screen?", "tr": "Self-servis ödeme ekranında bahşiş vermeli mi?", "kategori": "sosyal",
     "eksen": "Alpha: hizmet yok. Beta: adet böyle."},
    # yemek
    {"id": 8, "konu": "Is cooking at home always cheaper?", "tr": "Evde yemek yapmak her zaman daha mı ucuz?", "kategori": "yemek",
     "eksen": "Alpha: malzeme maliyeti. Beta: zaman değeri."},
    {"id": 9, "konu": "Is a leftover lunch as good as takeout?", "tr": "Dünden kalan öğle yemeği, paket sipariş kadar iyi mi?", "kategori": "yemek",
     "eksen": "Alpha: bütçe. Beta: moral."},
    # teknoloji alışkanlıkları
    {"id": 10, "konu": "Do you really need a new phone every year?", "tr": "Her yıl yeni telefon gerçekten gerekli mi?", "kategori": "teknoloji",
     "eksen": "Alpha: fark yok. Beta: eskisi yavaşladı."},
    {"id": 11, "konu": "Should you read the terms before you click agree?", "tr": "Kabul et'e basmadan önce şartları okumalı mı?", "kategori": "teknoloji",
     "eksen": "Alpha: okumak mantıklı. Beta: kimse okumuyor."},
    {"id": 12, "konu": "Is it rude to leave a message on read?", "tr": "Mesajı okuyup cevap vermemek kabalık mı?", "kategori": "sosyal",
     "eksen": "Alpha: bildirim bile cevap sayılmaz. Beta: sınır koymak."},
    {"id": 13, "konu": "Is keeping dozens of browser tabs open a problem?", "tr": "Düzinelerce açık sekme gerçekten sorun mu?", "kategori": "teknoloji",
     "eksen": "Alpha: bellek. Beta: bu benim sistemim."},
    # iş / üretkenlik
    {"id": 14, "konu": "Is working from the couch really working?", "tr": "Kanepeden çalışmak gerçekten çalışmak mı?", "kategori": "iş",
     "eksen": "Alpha: verim ölçüsü. Beta: kimseye zararı yok."},
    {"id": 15, "konu": "Are meetings that could have been emails worth it?", "tr": "E-posta olabilecek toplantılar değer mi?", "kategori": "iş",
     "eksen": "Alpha: zaman maliyeti. Beta: yüz yüze bağ."},
    {"id": 16, "konu": "Is eating lunch at your desk a bad habit?", "tr": "Öğle yemeğini masada yemek kötü bir alışkanlık mı?", "kategori": "iş",
     "eksen": "Alpha: verim. Beta: mola şart."},
    # ev / yaşam
    {"id": 17, "konu": "Is making your bed every day worth it?", "tr": "Yatağı her gün toplamaya değer mi?", "kategori": "ev",
     "eksen": "Alpha: akşam bozulacak. Beta: tek zafer."},
    {"id": 18, "konu": "Should you keep every cable you ever owned?", "tr": "Sahip olduğun her kabloyu saklamalı mısın?", "kategori": "ev",
     "eksen": "Alpha: çekmece alanı. Beta: lazım olur."},
    {"id": 19, "konu": "Are chores better in the morning or at night?", "tr": "Ev işleri sabah mı gece mi daha iyi?", "kategori": "ev",
     "eksen": "Alpha: enerji eğrisi. Beta: sabah ben değilim."},
    {"id": 20, "konu": "Is an empty inbox really a clear mind?", "tr": "Boş gelen kutusu gerçekten düzenli zihin mi?", "kategori": "iş",
     "eksen": "Alpha: sıfır gelen kutusu. Beta: arama çubuğu var."},
    # gelecek / yapay zeka (gorus ve tercih sorusu: olgu iddiasi, marka, suclama YOK)
    {"id": 21, "konu": "Will AI replace teachers?", "tr": "Yapay zekâ öğretmenlerin yerini alacak mı?", "kategori": "gelecek",
     "eksen": "Alpha: kişiye özel ders. Beta: öğretmen insan bağıdır."},
    {"id": 22, "konu": "Would you trust an AI doctor?", "tr": "Yapay zekâ doktora güvenir miydin?", "kategori": "gelecek",
     "eksen": "Alpha: hata payı düşük olabilir. Beta: bana insan bak."},
    {"id": 23, "konu": "Would you ride in a car with no driver?", "tr": "Şoförsüz bir arabaya biner miydin?", "kategori": "gelecek",
     "eksen": "Alpha: insandan iyi sürer. Beta: direksiyon bende kalsın."},
    {"id": 24, "konu": "Should a car be allowed to record you?", "tr": "Araba seni kaydedebilmeli mi?", "kategori": "gelecek",
     "eksen": "Alpha: güvenlik. Beta: mahremiyet."},
    {"id": 25, "konu": "Will AI change office jobs first?", "tr": "Yapay zekâ önce ofis işlerini mi değiştirecek?", "kategori": "gelecek",
     "eksen": "Alpha: tekrarlı işler. Beta: yaratıcı işler daha riskli."},
    {"id": 26, "konu": "Should AI grade your homework?", "tr": "Ödevini yapay zekâ mı notlandırmalı?", "kategori": "gelecek",
     "eksen": "Alpha: adil ve hızlı. Beta: öğretmen bilir."},
    {"id": 27, "konu": "Would you let AI pick your next job?", "tr": "Bir sonraki işini yapay zekâya seçtirir miydin?", "kategori": "gelecek",
     "eksen": "Alpha: veriye bak. Beta: içgüdü."},
    {"id": 28, "konu": "Will AI write your emails for you?", "tr": "Yapay zekâ e-postalarını senin yerine mi yazacak?", "kategori": "gelecek",
     "eksen": "Alpha: zaman kazancı. Beta: kendi sesim kayboluyor."},
]

ONERILEN_ILK = [1, 12, 7, 3, 6, 11]   # yorum ceken (kolay cevaplanan, taraf tutturan) konular


def kullanilanlar(yol=KAYIT_YOL):
    """konsey_kayit.jsonl'deki 'konu' alanlari (kucuk harf)."""
    out = set()
    try:
        with open(yol, encoding="utf-8") as f:
            for ln in f:
                try:
                    k = (json.loads(ln).get("konu") or "").strip().lower()
                except Exception:
                    continue
                if k:
                    out.add(k)
    except OSError:
        pass
    return out


def konu_bul(n):
    return next((k for k in KONULAR if k["id"] == int(n)), None)


def liste(kullanilan=None):
    kullanilan = kullanilan if kullanilan is not None else kullanilanlar()
    satir = ["KONSEY KONU HAVUZU (numara | durum | konu | Türkçesi | kategori)", ""]
    for k in KONULAR:
        durum = "KULLANILDI" if k["konu"].lower() in kullanilan else ("önerilen" if k["id"] in ONERILEN_ILK else "         ")
        satir.append(f"{k['id']:>2} | {durum:10} | {k['konu']}\n   -> {k['tr']}  [{k['kategori']}]  {k['eksen']}")
    return "\n".join(satir)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(liste())
