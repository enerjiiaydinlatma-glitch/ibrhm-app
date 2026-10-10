# YouTube Shorts ve TikTok Dağıtım/Keşif Algoritmaları (2025-2026)

## YouTube Shorts'ta bir video ilk kaç saat/gün içinde kaç kişiye "test" gösterimi yapılır, hangi sinyaller videoyu daha geniş kitleye taşır?

### Takeaway
YouTube resmi olarak (support.google.com) Shorts dağıtımının "izleyicinin izlemeyi seçip seçmediği, izleme süresi ve izlenen yüzde" gibi sinyallere dayandığını doğruluyor; somut bir "ilk X kişiye gösterilir" rakamı resmi kaynakta yok. Ancak YouTube'un kendi Shorts Ürün Direktörü Todd Sherman, şirketin resmi "Creator Insider" kanalında Shorts'un "explore/exploit" (keşif/sömürme) mantığıyla küçük bir "seed audience" (tohum kitle) ile test edilip sinyaller iyiyse daha geniş kitleye yayıldığını açıkladı — bu resmi ama ikinci elden (creator-insider özetleri üzerinden) aktarılan bir bilgi.

### Cited Findings
- YouTube'un resmi Yardım Merkezi'ne göre: "Shorts recommendations aim to help each viewer find videos they want to watch and support the discoverability and growth of Shorts creators" ve sistem "percentage of viewers who chose to view, average view duration and average percentage viewed" sinyallerini kullanarak sıralama yapıyor; ayrıca "likes and post-watch survey results" izleyici memnuniyetini tahmin etmek için kullanılıyor — [YouTube Help: Search & discovery tips - Shorts](https://support.google.com/youtube/answer/11914225?hl=en&co=YOUTUBE._YTVideoType%3Dshorts)
- Aynı resmi sayfa: Shorts feed'in "recency" (video ne kadar yeni) üzerine ağırlık verdiğini, bunun yeni içeriklerin keşfi için iyi olduğunu belirtiyor; ayrıca "Shorts performansının uzun-format video önerilerini olumsuz etkilemediğini" ve resmi minimum yükleme sıklığı olmadığını söylüyor: "Focus on what your audience likes. If you do that and people watch, recommendations will follow." — [YouTube Help: Search & discovery tips - Shorts](https://support.google.com/youtube/answer/11914225?hl=en&co=YOUTUBE._YTVideoType%3Dshorts)
- YouTube'un genel öneri sistemi sayfası (destek merkezi), sistemin "80 milyardan fazla sinyal parçası" kullandığını, bunların izleme/arama geçmişi, abonelikler, beğeni/beğenmeme, "ilgilenmiyorum" geri bildirimleri ve memnuniyet anketlerini içerdiğini belirtiyor; ancak bu sayfa Shorts'a özgü test-kitlesi büyüklüğü veya zaman çizelgesi vermiyor — [YouTube Help: How YouTube recommendations work](https://support.google.com/youtube/answer/16089387?hl=en)
- YouTube Shorts Kıdemli Ürün Direktörü Todd Sherman'ın resmi "Creator Insider" video-sohbetinde aktardığı (üçüncü taraf özetiyle): "We approach these formats differently because they serve different purposes. With long-form content, people actively choose what they want to watch by clicking on specific videos. Shorts, on the other hand, is all about swiping through a feed and discovering content on the go. That's why we measure them in different ways." — [Creator Handbook: YouTube explains how the YouTube Shorts algorithm works](https://www.creatorhandbook.net/youtube-explains-how-the-youtube-shorts-algoritm-works/) (not: bu bir üçüncü-taraf özeti, orijinal video YouTube'un kendi kanalında yayınlandı)
- Aynı kaynağa göre Sherman, tıklama olmadığı için (kaydırma bazlı akış) sistemin bir Short'u kalitesini ölçmek için "agresif biçimde çok sayıda gösterimle" test ettiğini, sinyaller iyiyse gösterimlerin kartopu gibi büyüdüğünü, zayıfsa hızla kesildiğini açıklıyor — [MediaPost: YouTube Shorts Product Lead Offers Insights For Creators And Brands](https://www.mediapost.com/publications/article/388588/youtube-shorts-product-lead-offers-insights-for-cr.html)

### Inferences
- Resmi kaynaklar "kaç kişiye ilk test gösterimi yapılır" sorusuna somut bir sayı (ör. "500 kişi" gibi) vermiyor; bu tür rakamlar (50-500 görüntülenme/48 saat gibi) yalnızca üçüncü-taraf/SEO blog tahminlerinde geçiyor ve resmi olarak doğrulanmamış — dikkatle "tahmini/doğrulanmamış" olarak ele alınmalı.
- "Explore/exploit" (keşfet/sömür) çerçevesi — küçük tohum kitle → sinyal iyi ise geniş kitle — YouTube'un kendi sözcüsü tarafından kavramsal olarak doğrulanmış durumda, ancak kesin sayılar (kaç izleyici, kaç saat) resmi olarak paylaşılmamış.

### Gaps
- YouTube'un "ilk kaç saat/gün içinde kaç kişiye test gösterimi yapıldığına" dair resmi, sayısal bir açıklaması bulunamadı. Üçüncü taraf blog/agregatör kaynaklarda (ör. Shortimize, Gyre, Metricool) geçen "birkaç yüz gösterim", "50-500 görüntülenme/48 saat" gibi rakamlar spekülatif olup resmi kaynaklarla doğrulanamadı — bu rakamlar notlarda spekülasyon olarak işaretlenmelidir, gerçek olarak sunulmamalıdır.
- "Swipe-away rate" (kaydırıp-geçme oranı) teriminin YouTube'un kendi resmi yardım sayfalarında birebir bu isimle geçtiğine dair doğrudan bir alıntı bulunamadı; bu terim YouTube Analytics arayüzünde "Viewed vs Swiped Away" grafiği olarak var (üçüncü taraf kaynaklarca doğrulanıyor) ancak resmi destek sayfası bu grafiği ayrıntılı açıklamıyor.

---

## TikTok'un "For You" (Sizin İçin) akışı yeni/küçük hesapları nasıl değerlendiriyor? "Sibyl" tipi sinyal sistemi ve içerik kalitesi puanlaması hakkında güncel (2025-2026) kamuya açık bilgi var mı?

### Takeaway
TikTok'un tek resmi, birincil kaynağı olan 2020 tarihli Newsroom makalesi hâlâ TikTok'un kendi web sitesinde yayında ve güncel referans olarak gösteriliyor; bu makale "takipçi sayısı veya geçmiş video performansının doğrudan bir sıralama faktörü olmadığını" açıkça belirtiyor. "Sibyl" TikTok'a değil Google/YouTube'a ait 2014 tarihli bir makine öğrenmesi sistemi olup TikTok ile hiçbir doğrulanmış bağlantısı yok — bu, araştırma sorusundaki bir kavram karışıklığı olabilir.

### Cited Findings
- TikTok Newsroom'un resmi makalesi (18 Haziran 2020 tarihli, halen TikTok'un kendi sitesinde canlı): sistem "user interactions" (beğeni, paylaşım, takip edilen hesaplar, yorumlar, oluşturulan içerik), "video information" (altyazılar, sesler, hashtag'ler) ve "device/account settings" (dil, ülke, cihaz tipi — bu sonuncusu daha düşük ağırlıklı) sinyallerini kullanıyor — [TikTok Newsroom: How TikTok recommends videos #ForYou](https://newsroom.tiktok.com/en-us/how-tiktok-recommends-videos-for-you)
- Aynı resmi makale açıkça belirtiyor: "Follower count and prior video performance are explicitly not direct ranking factors, though larger accounts benefit from their existing audience" (yani takipçi sayısı/geçmiş performans doğrudan sıralama faktörü değil, ama büyük hesaplar mevcut kitlelerinden faydalanıyor) — [TikTok Newsroom: How TikTok recommends videos #ForYou](https://newsroom.tiktok.com/en-us/how-tiktok-recommends-videos-for-you)
- Aynı kaynak: yeni kullanıcılar ilgi kategorileri (evcil hayvan, seyahat vb.) seçebiliyor; seçmeyenlere sistem önce "a generalized feed of popular videos" (popüler videolardan oluşan genel bir akış) sunuyor, sonra beğeni/tekrar-izleme gibi erken etkileşimlerden öğreniyor — [TikTok Newsroom: How TikTok recommends videos #ForYou](https://newsroom.tiktok.com/en-us/how-tiktok-recommends-videos-for-you)
- "Sibyl", Google'ın 2014'te halka açıklanan, YouTube dahil çeşitli Google ürünlerinde (Android, Gmail, Google+) kullanılan büyük ölçekli bir denetimli makine öğrenmesi platformu; TikTok ile hiçbir bağlantısı doğrulanamadı — [HPCwire: Inside Sibyl, Google's Massively Parallel Machine Learning Platform](https://www.hpcwire.com/bigdatawire/2014/07/17/inside-sibyl-googles-massively-parallel-machine-learning-platform/)
- 2025 sonu için, doğrulanamamış/üçüncü-taraf iddialara göre TikTok'un yeni bir "trafik havuzu" (traffic pool) modeli kullandığı, yeni videonun önce ~500 kullanıcılık temel bir havuza girdiği ve güçlü izlenme süresi/beğeni/yorum/tamamlama oranıyla daha büyük havuzlara (nihayetinde For You Page'e) geçtiği iddia ediliyor — [TikTok Seller University: How TikTok Recommends Content to New Users](https://seller-us.tiktok.com/university/essay?knowledge_id=2410858052077355) (not: bu sayfa satıcı/reklamveren odaklı yarı-resmi bir TikTok kaynağı olsa da "500 kullanıcı" rakamı resmi Newsroom makalesinde doğrulanmıyor, dikkatle ele alınmalı)
- Üçüncü-taraf sektör kaynaklarına göre (doğrulanmamış/spekülatif): TikTok 2025 sonunda dağıtımın ilk aşamasını değiştirip yeni videoları rastgele ilgi-eşleşen kullanıcı havuzuna değil, önce oluşturucunun kendi takipçilerinin bir alt kümesine gösterdiği, ardından tepkiye göre bağlantısız kitlelere yaydığı iddia ediliyor; ayrıca "micro-niche push" (mikro-niş itme) stratejisi getirdiği söyleniyor — kaynak gösterilmediği için bu iddia doğrulanamamış/söylenti olarak işaretlenmelidir — [Sueio blog, Kasım 2025](https://sueio.com/2025/11/08/tiktok-algorithm-change-crashing-views-2025/) (birincil TikTok kaynağıyla teyit edilemedi)

### Inferences
- Araştırma sorusundaki "Sibyl tipi sinyal sistemi" muhtemelen bir kavram karışıklığı: Sibyl, TikTok değil Google/YouTube'un eski (2014) bir sistemi. TikTok'un kendi iç puanlama sisteminin adı (varsa) kamuya açık, doğrulanmış bir kaynakta bulunamadı.
- TikTok'un 2020 Newsroom makalesi hâlâ TikTok'un ana resmi referansı olarak kullanılıyor; 2025-2026 için TikTok'tan bunu güncelleyen yeni bir Newsroom makalesi/blog yazısı bulunamadı — bu, TikTok'un algoritma açıklama politikasında resmi güncelleme yapmadığı, sadece politika (AI içerik etiketleme, ticari içerik ifşası vb.) konularında yeni duyurular yaptığı anlamına gelebilir.

### Gaps
- TikTok'un 2025-2026'ya özgü, resmi (Newsroom/Creator Portal) bir algoritma güncellemesi bulunamadı; bulunan "2025 sonu dağıtım değişikliği" ve "trafik havuzu" rakamları (500 kullanıcı vb.) yalnızca üçüncü-taraf/SEO blog kaynaklarında geçiyor, TikTok'un kendi kanallarında doğrulanamadı — bunlar raporda açıkça "doğrulanmamış" olarak işaretlenmeli.
- TikTok'un yeni/küçük hesaplara özel resmi bir "cold start" açıklaması (somut süre, video sayısı vb.) hiçbir resmi kaynakta bulunamadı.

---

## İzleyici tutma oranının (average view duration / average view percentage) somut olarak dağıtıma etkisi nedir - resmi kaynaklarda buna dair ne söyleniyor?

### Takeaway
YouTube'un resmi Yardım Merkezi, "average view duration" ve "average percentage viewed"i açıkça birer sıralama sinyali olarak adlandırıyor, ancak "%70 üstü viral" gibi somut eşik değerleri resmi kaynaklarda yok — bu tür yüzdeler tamamen üçüncü-taraf tahminleri. TikTok tarafında ise resmi kaynak "tamamlama"nın önemli olduğunu dolaylı olarak ima ediyor (uzun bir videoyu bitirmenin coğrafi benzerlikten daha ağırlıklı olduğu belirtiliyor) ama somut bir eşik yayınlamıyor.

### Cited Findings
- YouTube resmi Yardım sayfası: sistem "percentage of viewers who chose to view, average view duration and average percentage viewed" kullanarak sıralama yapıyor; "likes and post-watch survey results" ile izleyici memnuniyetini ölçüyor — [YouTube Help: Search & discovery tips - Shorts](https://support.google.com/youtube/answer/11914225?hl=en&co=YOUTUBE._YTVideoType%3Dshorts)
- TikTok'un resmi Newsroom makalesi: sinyaller eşit ağırlıklı değil; "finishing a lengthy video receives more weight than sharing geography with a creator" (uzun bir videoyu bitirmek, bir oluşturucuyla coğrafi yakınlık paylaşmaktan daha ağırlıklı) — [TikTok Newsroom: How TikTok recommends videos #ForYou](https://newsroom.tiktok.com/en-us/how-tiktok-recommends-videos-for-you)
- Üçüncü-taraf kaynaklara göre (doğrulanmamış somut eşikler): "%70 ve üzeri ortalama izlenen yüzde 2026'da Shorts için sağlıklı kabul ediliyor", "%50-70 arası daha geniş dağıtım alıyor", "%30 altı dağıtımın durmasına yol açıyor" — bu eşik değerler resmi YouTube kaynağında doğrulanamadı, yalnızca SEO/analiz blog'larında geçiyor (ör. Shortimize, Gyre) — [Shortimize: YouTube Shorts Retention Rate (2026)](https://www.shortimize.com/blog/youtube-shorts-retention-rate)
- YouTube Shorts Kıdemli Ürün Direktörü Todd Sherman'ın (üçüncü-taraf özetiyle aktarılan) açıklamasına göre, izlenme oranı/tamamlama ve kaydırıp-geçme (swipe-away) oranının "ham izlenme sayısının önüne geçtiği" ve dağıtımı öngören asıl sinyaller haline geldiği belirtiliyor — [MediaPost: YouTube Shorts Product Lead Offers Insights For Creators And Brands](https://www.mediapost.com/publications/article/388588/youtube-shorts-product-lead-offers-insights-for-cr.html)

### Inferences
- Resmi kaynaklar tutma oranının bir sinyal OLDUĞUNU doğruluyor ama hiçbir platform "şu yüzdenin üstü viral olur" gibi somut bir sayısal eşik yayınlamıyor. Bu nedenle "%70 kuralı" gibi rakamlar sektör tahminidir, platform garantisi değildir.

### Gaps
- Ne YouTube ne de TikTok, "tutma oranı X puan artarsa dağıtım Y kat artar" türünden nicel/somut bir ilişki yayınlamış değil. Bu tamamen üçüncü-taraf çıkarım ve A/B test paylaşımlarına dayanıyor, resmi doğrulama yok.

---

## "İlk 3 saniye" / "hook" kuralının kaynağı nedir, güncel veriyle hâlâ geçerli mi?

### Takeaway
"İlk 3 saniye" kuralının kesin, tek bir birincil kaynağı (resmi platform yayını) net biçimde tespit edilemedi; en sık atıfta bulunulan köken Meta/Facebook'un eski (2016 civarı) iç verisi ve TikTok for Business'ın pazarlama materyalleridir. 2025-2026 itibarıyla hem YouTube (Sherman açıklamaları) hem TikTok resmi kaynakları "erken izleyici tepkisinin/kaydırıp-geçmenin" önemli bir sinyal olduğunu dolaylı olarak destekliyor, ancak "tam olarak 3 saniye" gibi kesin bir eşik resmi kaynaklarda doğrulanmadı.

### Cited Findings
- Meta/Facebook'un (üçüncü-taraf kaynakla aktarılan) eski iç verisine göre: "videonun ilk 3 saniyesini izleyen kişilerin %65'i en az 10 saniye izlemeye devam ediyor, %45'i 30 saniyeye kadar kalıyor" — bu veri doğrudan Meta kaynağından teyit edilemedi, yalnızca ikincil pazarlama makalelerinde (tarihsiz/eski) atıfta bulunuluyor; birincil kaynak linki bulunamadı, dolayısıyla doğrulanmamış olarak işaretlenmeli.
- TikTok for Business'a atfedilen (ikincil kaynak üzerinden) bir istatistik: "en yüksek tıklama oranına sahip videoların %63'ü izleyicileri ilk üç saniyede yakalıyor" — birincil TikTok for Business kaynağına doğrudan ulaşılamadı, ikincil pazarlama blog'larında aktarılıyor.
- "Güçlü kancaya sahip videoların For You sayfasına düşme olasılığının 2,4 kat arttığı" iddiası "Brandefy ve TikTok Creator Insights (2024)" kaynağına atfediliyor ancak birincil kaynağa ulaşılamadı ve doğrulanamadı — spekülatif/doğrulanmamış olarak işaretlenmeli.
- YouTube Shorts Ürün Direktörü Todd Sherman'ın (ikincil kaynakla aktarılan) açıklaması, Shorts'ta izleyicinin aktif tıklama yapmadan kaydırarak keşfettiğini, bu yüzden erken sinyallerin (izlemeye devam etme/kaydırıp geçme) sistem tarafından yoğun biçimde test edildiğini doğruluyor — bu, "ilk saniyelerin önemi" fikrini dolaylı olarak destekliyor ama "3 saniye" gibi kesin bir sayı belirtmiyor — [MediaPost: YouTube Shorts Product Lead Offers Insights](https://www.mediapost.com/publications/article/388588/youtube-shorts-product-lead-offers-insights-for-cr.html)

### Inferences
- "İlk 3 saniye kuralı" büyük olasılıkla pazarlama/ajans dünyasında (Meta'nın 2016 civarı reklam verisi + TikTok for Business pazarlama materyalleri) doğmuş, zamanla bir "platform gerçeği" gibi tekrarlanan bir sektör klişesine dönüşmüş bir kural. Platformların kendi resmi ürün sözcüleri (Sherman gibi) "erken izleyici tepkisinin önemli olduğunu" doğruluyor ama kesin "3 saniye" eşiğini teyit eden birincil, tarihli bir platform yayını bulunamadı.

### Gaps
- "İlk 3 saniye" ifadesinin geçtiği tek, birincil ve tarihli bir YouTube veya TikTok yayını (resmi blog/destek sayfası) bulunamadı — bu kural sektörde yaygın biçimde tekrarlanıyor ama doğrudan platform kaynağıyla doğrulanamadı. Rapor yazarının bunu "yaygın kabul görmüş ama birincil kaynağı belirsiz bir sektör kuralı" olarak sunması önerilir.

---

## Sıfırdan başlayan bir hesap için "cold start" aşaması tipik olarak ne kadar sürer? Platformların resmi blog/yardım sayfalarında somut bir zaman çizelgesi var mı?

### Takeaway
Ne YouTube ne de TikTok, resmi kaynaklarında "cold start X gün/hafta sürer" biçiminde somut, sayısal bir zaman çizelgesi yayınlamıyor. Bulunan tüm süre/video-sayısı rakamları (20-30 video, 30 gün, 10-14 günlük "warm-up" vb.) üçüncü-taraf ajans/SEO kaynaklarına ait tahminlerdir ve resmi olarak doğrulanmamıştır.

### Cited Findings
- YouTube'un resmi Shorts destek sayfası herhangi bir minimum yükleme sıklığı veya "öğrenme süresi" belirtmiyor; yalnızca "No minimum posting schedule is required" (zorunlu bir minimum yükleme takvimi yok) diyor — [YouTube Help: Search & discovery tips - Shorts](https://support.google.com/youtube/answer/11914225?hl=en&co=YOUTUBE._YTVideoType%3Dshorts)
- TikTok'un resmi Newsroom makalesi herhangi bir "cold start süresi" belirtmiyor; yalnızca yeni kullanıcıların ilgi kategorisi seçtiğini veya seçmezse "genelleştirilmiş popüler video akışı" aldığını, sistemin sonra erken etkileşimlerden (beğeni, tekrar izleme) öğrendiğini söylüyor — süre/video sayısı belirtilmiyor — [TikTok Newsroom: How TikTok recommends videos #ForYou](https://newsroom.tiktok.com/en-us/how-tiktok-recommends-videos-for-you)
- Üçüncü-taraf/doğrulanmamış tahminler: "çoğu hesabın neyin işe yaradığını bulması için 20-30 video gerekiyor", "değerlendirme için en az 30 gün ve 30 video" öneriliyor — kaynak birincil platform verisi değil, ajans/danışmanlık blog tahmini — [Reel.farm: How to Warm Up a TikTok Account](https://reel.farm/guides/how-to-warm-up-tiktok-account) (doğrulanmamış)
- Üçüncü-taraf tahmin: yeni/sıfır etkileşimli hesapların "en küçük olası test kitlesiyle" başladığı, ilk videoların toplamda yalnızca ~50 kişiye ulaşabileceği iddia ediliyor — birincil kaynakla teyit edilemedi, spekülatif — [Reel.farm: How to Warm Up a TikTok Account](https://reel.farm/guides/how-to-warm-up-tiktok-account) (doğrulanmamış)
- Üçüncü-taraf tahmin: yeni bir YouTube kanalında ilk 48 saatte bir Short için "50-500 görüntülenme"nin normal aralık olduğu, "günler içinde gerçek sıfır görüntülenme"nin ise genelde teknik bir soruna (işleme hatası, topluluk ihlali, otomatik moderasyon bayrağı) işaret ettiği belirtiliyor — birincil YouTube kaynağıyla doğrulanamadı, spekülatif — [Subscribr: Why Your YouTube Shorts Aren't Getting Views](https://subscribr.ai/youtube-strategy/youtube-shorts-no-views-fix) (doğrulanmamış)

### Inferences
- Her iki platform da bilinçli olarak somut bir "cold start süresi" taahhüt etmiyor gibi görünüyor — bu muhtemelen algoritmanın hesap-bazlı değil video-bazlı/sinyal-bazlı çalıştığının, yani "yaşı" değil her videonun kendi erken performansının belirleyici olduğunun bir yansıması (resmi kaynaklarda dolaylı olarak destekleniyor: TikTok "takipçi sayısı/geçmiş performans doğrudan faktör değil" diyor).
- Sektörde dolaşan "20-30 video / 30 gün" gibi rakamlar muhtemelen ajansların kendi müşteri verilerinden türettiği ampirik tahminler; genellenebilir platform kuralları olarak sunulmamalı.

### Gaps
- Hiçbir resmi kaynakta "cold start" terimi bile geçmiyor; bu tamamen sektörün türettiği bir kavram. Platformların bunu nasıl tanımladığına dair resmi bir açıklama yok — bu önemli bir boşluk, rapor yazarı bunun sektör jargonundan geldiğini ve platformlarca resmen tanımlanmadığını açıkça belirtmeli.

---

## Genel Metodoloji Notu (Kaynak Kalitesi Hakkında)

Bu araştırma sırasında arama sonuçlarının büyük çoğunluğu (Shortimize, Gyre, Metricool, Quso, Riverside, Socialpilot, Reelforgeai, Miraflow, Influenceflow, Likes.io, Dataslayer, Enrich Labs, Beatstorapon, Darkroom, Fanpage Karma, Sueio, Reel.farm, Subscribr, EzUGC vb.) SEO/pazarlama ajansı blog'ları olup **birincil kaynak değildir**. Bunlar genellikle:
1. Somut sayısal eşikler (%70 viral, 500 kullanıcılık havuz, 50 kişilik test kitlesi vb.) veriyor ama bu sayıların kaynağını göstermiyor veya döngüsel olarak birbirlerinden alıntı yapıyorlar.
2. "2026" tarihini başlıklarına koyuyor olsalar da içerik çoğunlukla daha eski, doğrulanmamış sektör bilgisinin yeniden paketlenmesi.

Bulunan **gerçek birincil/resmi kaynaklar** şunlardır:
- [YouTube Help: How YouTube recommendations work](https://support.google.com/youtube/answer/16089387?hl=en)
- [YouTube Help: Search & discovery tips - Shorts](https://support.google.com/youtube/answer/11914225?hl=en&co=YOUTUBE._YTVideoType%3Dshorts)
- [TikTok Newsroom: How TikTok recommends videos #ForYou](https://newsroom.tiktok.com/en-us/how-tiktok-recommends-videos-for-you) (18 Haziran 2020 — TikTok'un hâlâ canlı tuttuğu, güncellemediği tek büyük resmi algoritma açıklaması)
- YouTube'un kendi "Creator Insider" kanalındaki Todd Sherman açıklamaları (yalnızca ikincil özetler üzerinden erişilebildi, doğrudan video transkripti incelenmedi)

**Sonuç olarak:** Rapor yazarı, bu notlardaki somut yüzde/sayı eşiklerini (ör. "%70 kuralı", "500 kullanıcılık havuz", "ilk 3 saniyede %65'i kalır") **platform garantisi değil, sektör tahmini/doğrulanmamış bilgi** olarak sunmalı; yalnızca "Cited Findings" bölümlerinde resmi kaynak (support.google.com, newsroom.tiktok.com) olarak işaretlenen ifadeler platformun kendi sözü olarak güvenle aktarılabilir.
