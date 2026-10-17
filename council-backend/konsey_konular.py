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
    # gelecek / yapay zeka (gorus ve tercih sorusu: olgu iddiasi, marka, suclama YOK). TIBBI konu (doktor/hap/teshis) EKLEME: kapiyi zorluyor,
# uydurma saglik iddiasi riski ve kalitesiz senaryo veriyor (15 Ekim 2026).
    {"id": 21, "konu": "Will AI replace teachers?", "tr": "Yapay zekâ öğretmenlerin yerini alacak mı?", "kategori": "gelecek",
     "eksen": "Alpha: kişiye özel ders. Beta: öğretmen insan bağıdır."},
    {"id": 22, "konu": "Would you let AI plan your week?", "tr": "Yapay zekâ haftanı planlasın ister miydin?", "kategori": "gelecek",
     "eksen": "Alpha: verimli takvim. Beta: plansızlık da keyif."},
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
    # ------------------------------------------------------------------------------------------------------------------
    # EVREN (17 Ekim 2026): afet/iklim, sehir/ulasim, robot, uzay, insan+teknoloji, dunyanin sonu, what-if fizik.
    # 'risk': yesil | sari (korku/abartiya kayabilir: ton sakin+merakli, tarih tahmini yok) | insan (beden/beyin/cip: yalniz FELSEFI-KISISEL soru ve
    # gelecek-kipi; bugun etkili oldugu iddiasi yok, bkz. konsey_format.ETKI_KELIME). Tarama verisi: afet/deniz-buz/ucan araba/what-if fizik guclu, uzay zayif.
    # Kural: gercek marka/kisi/kurum adi YOK; 'alien' yazma (claim_lint 'lie' parcasi), 'believe/right/origin' gibi parca eslesmeleri de yasak.
    {"id": 29, "konu": "What if the sea rose 20 centimeters?", "tr": "Deniz 20 santim yükselse ne olur?", "kategori": "afet", "risk": "yesil",
     "eksen": "Alpha: kıyı şeridi. Beta: en rahatsız edici soru: fırtınada ne olur?"},
    {"id": 30, "konu": "What if all the ice on Earth melted?", "tr": "Dünyadaki bütün buzlar erise ne olur?", "kategori": "afet", "risk": "sari",
     "eksen": "Alpha: haritalar değişir. Beta: kim önce taşınır?"},
    {"id": 31, "konu": "What are melting glaciers trying to tell us?", "tr": "Eriyen buzullar bize ne söylemeye çalışıyor?", "kategori": "afet", "risk": "yesil",
     "eksen": "Alpha: işaret. Beta: ne yapmalı, bedeli ne?"},
    {"id": 32, "konu": "What if a giant wave hit a coastal city tonight?", "tr": "Bu gece kıyı şehrine dev bir dalga çarpsa?", "kategori": "afet", "risk": "sari",
     "eksen": "Alpha: tahliye süresi. Beta: kim geride kalır?"},
    {"id": 33, "konu": "What would you grab if the water kept rising?", "tr": "Su yükselmeye devam etse neyi kapıp çıkardın?", "kategori": "afet", "risk": "yesil",
     "eksen": "Alpha: pratik liste. Beta: hatıralar."},
    {"id": 34, "konu": "What if a volcano woke up tomorrow?", "tr": "Yarın bir yanardağ uyansa ne olur?", "kategori": "afet", "risk": "yesil",
     "eksen": "Alpha: kül ve hava. Beta: sakin kalmak mümkün mü?"},
    {"id": 35, "konu": "What if every car could fly tomorrow?", "tr": "Yarın bütün arabalar uçsa ne olurdu?", "kategori": "sehir", "risk": "yesil",
     "eksen": "Alpha: trafik biter. Beta: gökyüzü kazaları."},
    {"id": 36, "konu": "Would you fly your car to work?", "tr": "İşe uçan arabayla gider miydin?", "kategori": "sehir", "risk": "yesil",
     "eksen": "Alpha: zaman kazancı. Beta: ben yere basayım."},
    {"id": 37, "konu": "Would you live in a city under the ocean?", "tr": "Okyanusun altındaki bir şehirde yaşar mıydın?", "kategori": "sehir", "risk": "yesil",
     "eksen": "Alpha: yeni sınır. Beta: gün ışığı."},
    {"id": 38, "konu": "Could we live in cities deep underground?", "tr": "Yerin derinlerindeki şehirlerde yaşayabilir miyiz?", "kategori": "sehir", "risk": "yesil",
     "eksen": "Alpha: korunaklı. Beta: gökyüzü yok."},
    {"id": 39, "konu": "Would you live in a floating city?", "tr": "Yüzen bir şehirde yaşar mıydın?", "kategori": "sehir", "risk": "yesil",
     "eksen": "Alpha: yükselen denize cevap. Beta: ya fırtına?"},
    {"id": 40, "konu": "What are robots really built for?", "tr": "Robotlar gerçekte ne için yapılıyor?", "kategori": "robot", "risk": "yesil",
     "eksen": "Alpha: işi devralmak. Beta: kimin işi, kimin adına?"},
    {"id": 41, "konu": "Where is the robot age taking us?", "tr": "Robot çağı bizi nereye götürüyor?", "kategori": "robot", "risk": "sari",
     "eksen": "Alpha: verimlilik. Beta: biz neye yarayacağız?"},
    {"id": 42, "konu": "What if robots wrote their own laws?", "tr": "Robotlar kendi yasalarını yazsa?", "kategori": "robot", "risk": "sari",
     "eksen": "Alpha: mantıklı kurallar. Beta: kim itiraz eder?"},
    {"id": 43, "konu": "Could machines build a country of their own?", "tr": "Makineler kendi ülkesini kurabilir mi?", "kategori": "robot", "risk": "sari",
     "eksen": "Alpha: sınırsız çalışma. Beta: vatandaş kim?"},
    {"id": 44, "konu": "Would you work for a robot boss?", "tr": "Robot bir patronun yanında çalışır mıydın?", "kategori": "robot", "risk": "yesil",
     "eksen": "Alpha: adil mesai. Beta: kime şikâyet edeceksin?"},
    {"id": 45, "konu": "What if robots ran every construction site?", "tr": "Bütün şantiyeleri robotlar yönetse?", "kategori": "robot", "risk": "yesil",
     "eksen": "Alpha: hızlı inşaat. Beta: işçiler ne olacak?"},
    {"id": 46, "konu": "Who plants the first flag on Mars: humans or robots?", "tr": "Mars'a ilk bayrağı kim dikecek: insan mı robot mu?", "kategori": "uzay", "risk": "yesil",
     "eksen": "Alpha: robotlar önce. Beta: bayrak insan eli ister."},
    {"id": 47, "konu": "Would you move to Mars?", "tr": "Mars'a taşınır mıydın?", "kategori": "uzay", "risk": "yesil",
     "eksen": "Alpha: yeni başlangıç. Beta: geri dönüş yok."},
    {"id": 48, "konu": "What would you do on a trip to the Moon?", "tr": "Ay'a bir yolculukta ilk ne yapardın?", "kategori": "uzay", "risk": "yesil",
     "eksen": "Alpha: bilim. Beta: manzara ve fotoğraf."},
    {"id": 49, "konu": "Could we build a city on the Moon?", "tr": "Ay'da bir şehir kurabilir miyiz?", "kategori": "uzay", "risk": "yesil",
     "eksen": "Alpha: mühendislik. Beta: ev gibi hissettirir mi?"},
    {"id": 50, "konu": "If a chip could read your thoughts, whose thoughts are they?", "tr": "Bir çip düşüncelerini okusa, o düşünceler kimin olur?", "kategori": "insan", "risk": "insan",
     "eksen": "Alpha: veri. Beta: ya sahipliği?"},
    {"id": 51, "konu": "Would you put a chip in your brain?", "tr": "Beynine çip taktırır mıydın?", "kategori": "insan", "risk": "insan",
     "eksen": "Alpha: yeni yetenek. Beta: geri alamazsan?"},
    {"id": 52, "konu": "Who decides in your head: you or the chip?", "tr": "Kafanda kim karar verir: sen mi çip mi?", "kategori": "insan", "risk": "insan",
     "eksen": "Alpha: birlikte karar. Beta: son söz kimde?"},
    {"id": 53, "konu": "Half human, half machine: would you still be you?", "tr": "Yarı insan yarı makine: yine de sen olur muydun?", "kategori": "insan", "risk": "insan",
     "eksen": "Alpha: parça parça yenilenir. Beta: ruh nerede kalır?"},
    {"id": 54, "konu": "What would a body with machine parts feel like?", "tr": "Makine parçalı bir beden nasıl hissettirirdi?", "kategori": "insan", "risk": "insan",
     "eksen": "Alpha: güç. Beta: dokunmayı kaybedersen?"},
    {"id": 55, "konu": "What if the world ended tomorrow?", "tr": "Dünya yarın bitse ne olur?", "kategori": "son", "risk": "sari",
     "eksen": "Alpha: plan yok. Beta: son bir gün."},
    {"id": 56, "konu": "Could humanity really come to an end?", "tr": "İnsanlık gerçekten sona erebilir mi?", "kategori": "son", "risk": "sari",
     "eksen": "Alpha: olasılık. Beta: ya hazırsak?"},
    {"id": 57, "konu": "What would you do with your last 24 hours?", "tr": "Son 24 saatini nasıl geçirirdin?", "kategori": "son", "risk": "yesil",
     "eksen": "Alpha: liste. Beta: sevdiklerim."},
    {"id": 58, "konu": "What if humans were no longer the smartest on Earth?", "tr": "İnsanlar artık Dünya'nın en zeki varlığı olmasa?", "kategori": "son", "risk": "sari",
     "eksen": "Alpha: yeni düzen. Beta: kim yönetir?"},
    {"id": 59, "konu": "What if the Earth stopped spinning for one second?", "tr": "Dünya bir saniye dönmeyi bıraksa ne olur?", "kategori": "fizik", "risk": "yesil",
     "eksen": "Alpha: hız. Beta: biz ne hissederdik?"},
    {"id": 60, "konu": "What if the Moon disappeared tonight?", "tr": "Ay bu gece kaybolsa ne olur?", "kategori": "fizik", "risk": "yesil",
     "eksen": "Alpha: gelgitler. Beta: gece gökyüzü."},
    {"id": 61, "konu": "What if gravity doubled for one day?", "tr": "Yerçekimi bir günlüğüne ikiye katlansa?", "kategori": "fizik", "risk": "yesil",
     "eksen": "Alpha: ağırlık. Beta: yürüyebilir miyiz?"},
    {"id": 62, "konu": "What if humans lived forever?", "tr": "İnsanlar sonsuza kadar yaşasa?", "kategori": "fizik", "risk": "yesil",
     "eksen": "Alpha: bitmeyen plan. Beta: sıkılmak."},
    {"id": 63, "konu": "What if we could travel back in time?", "tr": "Zamanda geriye gidebilsek?", "kategori": "fizik", "risk": "yesil",
     "eksen": "Alpha: neyi düzeltirdin. Beta: ya her şey bozulursa?"},
    {"id": 64, "konu": "What if an asteroid landed in the ocean?", "tr": "Okyanusa bir asteroit düşse ne olur?", "kategori": "fizik", "risk": "sari",
     "eksen": "Alpha: dalga. Beta: kıyıdakiler."},
    # 17 Ekim 2026 (ikinci dalga, Ibrahim'in listesi): isinlanma, klonlama, boyut kapisi, kara delik, gen, YZ yonetimi, robot seri uretimi.
    # Arastirma notu: isinlanma yalniz kuantum DURUMU icin kanitlandi (143 km, 2012); insan isinlamasi yok. Kara delik goruntusu 2019 (M87).
    # Gen: ilk CRISPR tedavisi 2023 (orak hucre); boy/dev-cuce icin tek bir gen yok, bu yuzden yalniz 'ya olsa' kipi.
    # Biyolojik silah / yapay veba KASITLI YOK: YouTube zararli/tehlikeli icerik politikasi + Konsey kapi kurallari (suc/korku) ile uyumsuz.
    {"id": 65, "konu": "What if you could teleport anywhere in one second?", "tr": "Bir saniyede istediğin yere ışınlanabilsen?", "kategori": "fizik", "risk": "yesil",
     "eksen": "Alpha: mesafe biter. Beta: en rahatsız edici soru: gelen kim?"},
    {"id": 66, "konu": "Would you step into a teleporter?", "tr": "Bir ışınlanma makinesine girer miydin?", "kategori": "fizik", "risk": "yesil",
     "eksen": "Alpha: aynı atomlar, aynı sen. Beta: kopya mı geliyor?"},
    {"id": 67, "konu": "What would you say if you met your clone?", "tr": "Klonunla karşılaşsan ona ne derdin?", "kategori": "insan", "risk": "insan",
     "eksen": "Alpha: aynı biziz. Beta: hangimiz gerçek?"},
    {"id": 68, "konu": "What if a door to another dimension opened in your room?", "tr": "Odanda başka bir boyuta açılan bir kapı olsa?", "kategori": "fizik", "risk": "yesil",
     "eksen": "Alpha: önce incele. Beta: içeri girer miyim?"},
    {"id": 69, "konu": "What would you see at the edge of a black hole?", "tr": "Bir kara deliğin kenarında ne görürdün?", "kategori": "fizik", "risk": "yesil",
     "eksen": "Alpha: zaman yavaşlar. Beta: geri dönüş yok."},
    {"id": 70, "konu": "What if another universe was one step away?", "tr": "Başka bir evren bir adım ötede olsa?", "kategori": "fizik", "risk": "yesil",
     "eksen": "Alpha: kanıt ara. Beta: orada başka bir ben var mı?"},
    {"id": 71, "konu": "What if humans grew twice as tall?", "tr": "İnsanlar iki kat uzun olsa ne olurdu?", "kategori": "insan", "risk": "insan",
     "eksen": "Alpha: kapılar, yataklar, kalp. Beta: gökyüzüne bakmak başka olur."},
    {"id": 72, "konu": "What if people could edit their own genes?", "tr": "İnsanlar kendi genlerini düzenleyebilse?", "kategori": "insan", "risk": "insan",
     "eksen": "Alpha: ne istersen. Beta: kim sınır koyar?"},
    {"id": 73, "konu": "Would you change your genes if you could?", "tr": "Yapabilsen genlerini değiştirir miydin?", "kategori": "insan", "risk": "insan",
     "eksen": "Alpha: kusursuz ben. Beta: o artık ben miyim?"},
    {"id": 74, "konu": "Who will steer AI: humans or the machines?", "tr": "Yapay zekâyı kim yönlendirecek: insanlar mı makineler mi?", "kategori": "robot", "risk": "sari",
     "eksen": "Alpha: direksiyon bizde. Beta: son söz kimde?"},
    {"id": 75, "konu": "What if AI ran the power and traffic of a whole country?", "tr": "Yapay zekâ bir ülkenin elektriğini ve trafiğini yönetse?", "kategori": "robot", "risk": "sari",
     "eksen": "Alpha: kesintisiz düzen. Beta: bir hata olursa?"},
    {"id": 76, "konu": "What if robots were built like cars, one a minute?", "tr": "Robotlar araba gibi, dakikada bir seri üretilse?", "kategori": "robot", "risk": "yesil",
     "eksen": "Alpha: herkese bir tane. Beta: o kadar robotla ne yapacağız?"},
    {"id": 77, "konu": "What if the world order changed overnight?", "tr": "Dünya düzeni bir gecede değişse?", "kategori": "son", "risk": "sari",
     "eksen": "Alpha: yeni kurallar. Beta: sabah kim uyanır?"},
    {"id": 78, "konu": "What if your city was cut off from the world for a month?", "tr": "Şehrin bir ay dünyadan kopsa ne olur?", "kategori": "afet", "risk": "yesil",
     "eksen": "Alpha: su, gıda, enerji hesabı. Beta: en rahatsız edici soru: komşun kapıyı çalarsa?"},
    {"id": 79, "konu": "What if a quarter of Earth's ice melted?", "tr": "Dünyadaki buzun dörtte biri erise ne olur?", "kategori": "afet", "risk": "sari",
     "eksen": "Alpha: kıyılar yeniden çizilir. Beta: en rahatsız edici soru: kim önce taşınır?"},
    {"id": 80, "konu": "What if the Arctic had no summer ice?", "tr": "Kuzey Kutbu'nda yazın hiç buz kalmasa ne olur?", "kategori": "afet", "risk": "sari",
     "eksen": "Alpha: yeni deniz yolları. Beta: hava düzeni nasıl bozulur?"},
    {"id": 81, "konu": "What if 60 centimeters of water ran down your street?", "tr": "Sokağından 60 santim yüksekliğinde su aksa ne olur?", "kategori": "afet", "risk": "yesil",
     "eksen": "Alpha: araçlar sürüklenir. Beta: en rahatsız edici soru: kimler içeride kalır?"},
    {"id": 82, "konu": "Would you trust a robot with a human face?", "tr": "İnsan yüzlü bir robota güvenir miydin?", "kategori": "robot", "risk": "yesil",
     "eksen": "Alpha: yüz güven verir. Beta: en rahatsız edici soru: kimin yüzü?"},
    {"id": 83, "konu": "What if you could not tell a robot from a human?", "tr": "Bir robotu insandan ayıramasan ne olur?", "kategori": "robot", "risk": "sari",
     "eksen": "Alpha: fark etmez. Beta: nasıl anlayacağız?"},
    {"id": 84, "konu": "What if robots built every new robot?", "tr": "Her yeni robotu robotlar üretse ne olur?", "kategori": "robot", "risk": "sari",
     "eksen": "Alpha: durmayan üretim. Beta: durdurma düğmesi kimde?"},
    # 17 Ekim 2026 (gol/selale/gecit/boyut kapisi). Arastirma: gercek 'gizli gecit' ornekleri var (su alti magara sistemleri, buzul alti goller);
    # boyut kapisi icin GOZLEMSEL KANIT YOK (ekstra boyutlar kuramsal). 'hidden/secret' kelimeleri claim_lint'te engelli: 'undiscovered/unseen' kullan.
    {"id": 85, "konu": "What if an undiscovered tunnel ran under a lake?", "tr": "Bir gölün altından keşfedilmemiş bir tünel geçse?", "kategori": "fizik", "risk": "yesil",
     "eksen": "Alpha: haritayı çıkar. Beta: en rahatsız edici soru: girişi kim bulur, içeriden ne çıkar?"},
    {"id": 86, "konu": "What lives in lakes buried under four kilometers of ice?", "tr": "Dört kilometre buzun altına gömülü göllerde ne yaşar?", "kategori": "fizik", "risk": "yesil",
     "eksen": "Alpha: mikroplar. Beta: ya daha fazlası?"},
    {"id": 87, "konu": "What is behind a waterfall?", "tr": "Bir şelalenin arkasında ne var?", "kategori": "fizik", "risk": "yesil",
     "eksen": "Alpha: kaya ve mağara. Beta: içeri girer miydin?"},
    {"id": 88, "konu": "Where would a door to another dimension be?", "tr": "Başka bir boyuta açılan kapı nerede olurdu?", "kategori": "fizik", "risk": "yesil",
     "eksen": "Alpha: kanıt aranırdı: nerede ölçüm var? Beta: kapıyı açan kim, kapatan kim?"},
    {"id": 89, "konu": "How would you know you found a door to another world?", "tr": "Başka bir dünyaya açılan bir kapı bulduğunu nasıl anlardın?", "kategori": "fizik", "risk": "yesil",
     "eksen": "Alpha: ölçüm ve kanıt. Beta: içeri girmeden anlaşılır mı?"},
    {"id": 90, "konu": "What if a flooded cave led to another world?", "tr": "Su altı bir mağara başka bir dünyaya çıksa?", "kategori": "fizik", "risk": "yesil",
     "eksen": "Alpha: haritalar bağlanıyor: gerçek mağaralar da birleşti. Beta: geri dönüş yolu var mı?"},
]

# Yeni strateji (17 Ekim 2026, tarama verisi): once afet/deniz-buz, ucan araba, Mars 'insan mi robot mu', robot yasalari, 'dunya durdu' fizigi.
# Eski gunluk-hayat konulari (1-28) listede kalir ama oncelik disindadir (konsey_gun sonraki_konu: once bu liste, sonra id sirasi).
ONERILEN_ILK = [29, 35, 46, 42, 59, 33, 50, 36, 30, 40, 60, 51, 65, 69, 74, 72, 78, 79, 81, 82, 84, 90, 86]


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
