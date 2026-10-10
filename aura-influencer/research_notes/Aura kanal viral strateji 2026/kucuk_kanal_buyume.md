# Küçük/Sıfırdan Başlayan Kanalların Büyüme Zaman Çizelgesi ve Cold-Start Aşımı (YouTube Shorts + TikTok)

## YouTube Shorts'ta günlük/düzenli paylaşımın algoritmik keşif üzerindeki etkisine dair resmi/yarı-resmi kaynak var mı?

### Takeaway
YouTube'un resmi Help/"How YouTube Works" sayfaları paylaşım *sıklığını* doğrudan bir sıralama sinyali olarak tanımlamıyor; bunun yerine "kritik kütle" (yeterli sayıda kaliteli video) ve izleyicinin kanalı keşfettiğinde derinlemesine gezinebileceği bir içerik kütüphanesi vurgulanıyor. Bağımsız (resmi olmayan ama büyük ölçekli) veri çalışmaları ise düzenli yükleme sıklığı ile abone/izlenme büyümesi arasında güçlü bir korelasyon (nedensellik değil) gösteriyor.

### Cited Findings
- YouTube'un resmi "Good to know about recommendations" yardım sayfası, yeni izleyicilerin bir videoyu keşfettiğinde kanalda gezinebileceği "substantial library of other high-quality content"ın algoritmaya kanalın değerli olduğu sinyalini verdiğini söylüyor; paylaşım sıklığı/tutarlılığı bu sayfada ayrı bir faktör olarak ele alınmıyor — [YouTube Help](https://support.google.com/youtube/answer/16559651?hl=en)
- vidIQ'in 10.210.278 YouTube kanalı üzerinde yaptığı çalışmada (Nisan 2025–Mart 2026, en az 1.000 aboneli kanallar), ayda 12+ video yükleyen kanalların medyan aylık izlenme büyüme oranı, ayda 1'den az yükleyen kanallara göre 4,1 kat daha yüksek; medyan abone büyümesi en düşük yükleme sıklığı grubunda ~%0,00 iken en yüksek grupta %0,91'e çıkıyor — [vidIQ Upload Frequency Study](https://vidiq.com/research/youtube-upload-frequency-study/)
- vidIQ çalışması açıkça "korelasyon, nedensellik değil" uyarısı yapıyor: büyük/sağlıklı kanalların sık yayın yapacak daha fazla kaynağa sahip olabileceğini, konu kalitesi/paketleme/kitle uyumu gibi faktörlerin de büyümeyi etkilediğini belirtiyor — [vidIQ Upload Frequency Study](https://vidiq.com/research/youtube-upload-frequency-study/)
- Backlinko/agrega kaynaklara göre (2026 Shorts istatistikleri derlemeleri), 10.000 abonenin altındaki yeni kanallarda bir Shorts videosu ilk 48 saatte tipik olarak 50–500 izlenme alıyor; 10 bin+ izlenme, Shorts algoritmasının içeriği abone olmayanlar üzerinde test edip "geçtiği" anlamına gelen güçlü bir sinyal olarak yorumlanıyor — [Teleprompter.com YouTube Shorts Statistics 2026](https://www.teleprompter.com/blog/youtube-shorts-statistics) (birincil kaynak değil, ikincil derleme — dikkatle değerlendirilmeli)
- Aynı derlemeye göre Shorts izlenimlerinin %74'ü abone olmayanlardan geliyor, bu da Shorts'u YouTube'un ana keşif formatı yapıyor; Shorts+uzun-format birlikte kullanan kanallar %41 daha hızlı büyüyor — [Teleprompter.com](https://www.teleprompter.com/blog/youtube-shorts-statistics) (ikincil kaynak, orijinal veri sahibi belirtilmemiş)

### Inferences
- Resmi YouTube kaynağı "sıklık" değil "kritik kütle + kalite" diline odaklandığı için, günlük paylaşımın kendisi değil, düzenli paylaşımın biriktirdiği içerik hacmi ve algoritmanın test edebileceği veri miktarı asıl mekanizma gibi görünüyor.
- vidIQ verisi büyüme oranındaki farkın en büyük sıçramasının "hiç/nadiren paylaşan" kanaldan "düzenli bir takvime geçen" kanaba geçişte olduğunu, ardından artışın yavaşladığını gösteriyor — yani "haftada 1-2 video" ile "günde 1 video" arasındaki fark, "hiç paylaşmama" ile "haftada 1-2" arasındaki farktan muhtemelen daha küçük.

### Gaps
- vidIQ çalışması sadece **1.000+ aboneli** kanalları kapsıyor; tek haneli aboneli, sıfırdan başlayan kanallar için resmi/büyük ölçekli bir veri seti bulunamadı — bu, araştırmanın en büyük boşluğu.
- "Creator Insider" kanalının (resmi YouTube ekip kanalı) paylaşım sıklığı/tutarlılık konusunda spesifik bir video veya alıntısı bu araştırmada doğrulanamadı; arama sonuçları genel makalelere yönlendirdi, Creator Insider'ın kendi ağzından doğrudan bir alıntı bulunamadı.

## TikTok'ta paylaşım sıklığının düşmesinin (ör. birkaç gün ara vermenin) hesabın "For You" performansını gerçekten etkilediğine dair kanıt/açıklama var mı, yoksa bu bir efsane mi?

### Takeaway
TikTok'un resmi Newsroom açıklaması, her videonun kendi başına ayrı değerlendirildiğini ve takipçi sayısı ile geçmiş video performansının doğrudan bir sıralama faktörü OLMADIĞINI net biçimde belirtiyor — yani "birkaç gün ara verince hesap cezalandırılır" iddiası TikTok'un kendi resmi açıklamasıyla çelişiyor. Bu, "ara vermek zararlıdır" iddiasının büyük ölçüde bir sektör efsanesi/varsayımı olduğuna işaret ediyor, ancak üçüncü taraf ajans/etki alanı kaynakları hâlâ "sık paylaşım = daha fazla maruziyet" tavsiyesi veriyor (bu ikisi çelişmiyor: sık paylaşım daha fazla "deneme" şansı verir, ama ara vermek cezalandırma anlamına gelmez).

### Cited Findings
- TikTok Newsroom'un resmi "How TikTok recommends videos #ForYou" açıklaması: "neither follower count nor whether the account has had previous high-performing videos are direct factors in the recommendation system" — her video kendi meritlerine göre, test kitlesinden gelen etkileşim sinyallerine dayanarak bağımsız şekilde değerlendiriliyor — [TikTok Newsroom](https://newsroom.tiktok.com/en-us/how-tiktok-recommends-videos-for-you)
- Aynı kaynağa göre yerleşik hesaplar, daha büyük bir takipçi tabanına sahip oldukları için doğal olarak daha fazla izlenme alıyor — ama bu, algoritmanın takipçi sayısını doğrudan bir sıralama sinyali olarak kullanmasından değil, o tabanın videoyu otomatik olarak görmesinden kaynaklanıyor — [TikTok Newsroom](https://newsroom.tiktok.com/en-us/how-tiktok-recommends-videos-for-you)
- TikTok'un resmi konumu "shadowban" terimini hiç kullanmıyor; ancak Community Guidelines ihlali veya "tavsiyeye uygun olmayan" içerik için dağıtımın "azaltılabileceğini" kabul ediyor — bu, "paylaşım arası boşluk" değil, içerik/davranış ihlaliyle ilgili bir mekanizma — [Later.com TikTok Shadow Ban özeti, TikTok'un resmi diline atıfla](https://later.com/blog/tiktok-shadowban/) (ikincil kaynak, TikTok'un birincil "reduced distribution" açıklamasına dolaylı atıf yapıyor — birincil TikTok metni bu araştırmada doğrudan doğrulanamadı)
- Üçüncü taraf ajans/blog kaynakları (JoinBrands, SociallyIn, Stackmatix vb., 2026 derlemeleri), 10.000 takipçi altındaki hesaplara günde 3-5 paylaşım önerirken, bunun nedeni "ceza kaçınma" değil "algoritmaya daha fazla test materyali sunmak ve maruziyet olasılığını artırmak" olarak açıklanıyor — [JoinBrands](https://joinbrands.com/blog/how-often-to-post-on-tiktok/), [SociallyIn](https://sociallyin.com/resources/how-often-should-you-post-on-tiktok/) (ikincil/pazarlama kaynakları, resmi TikTok verisi değil)

### Inferences
- Kanıtlar, "ara vermek hesabı cezalandırır" iddiasının resmi bir TikTok mekanizması olmadığını, bunun yerine "az paylaşım = az deneme şansı = daha az toplam görünürlük" şeklinde dolaylı bir istatistiksel etki olduğunu düşündürüyor. Yani etki gerçek ama mekanizma "ceza" değil "fırsat kaybı".
- "Şansı artırmak için sık paylaş" ile "ara vermek cezalandırılır" birbirinden farklı iddialar; birincisi kanıtlanabilir (her video ayrı bir çekiliş bileti gibi), ikincisi resmi kaynakla çelişiyor.

### Gaps
- TikTok'un "reduced distribution" / dağıtım azaltma mekanizmasının birincil metnini (TikTok Community Guidelines Enforcement Report veya resmi destek sayfası) bu araştırmada doğrudan fetch edilemedi; sadece ikincil kaynaklar üzerinden doğrulandı — birincil kaynak doğrulaması için ek araştırma gerekir.
- Paylaşım arasına birkaç gün/hafta ara vermenin performansa etkisini ölçen bağımsız, büyük ölçekli bir istatistiksel çalışma (TikTok için, vidIQ'in YouTube çalışmasına benzer) bulunamadı — bu konudaki kanıt tabanı YouTube'a kıyasla çok daha zayıf.

## Gerçekçi olarak: tek haneli aboneyle başlayan, günlük içerik üreten bir kanal genelde kaç videoda/kaç haftada ilk somut sıçramayı yaşıyor?

### Takeaway
Bulunan vaka çalışmaları büyük ölçüde tutarsız/parçalı veri sunuyor (çoğu blog "toplam 30 günlük sonuç" veriyor, gün-gün/video-video kırılım vermiyor), ancak eldeki örnekler ilk somut sıçramanın tipik olarak **3-5 hafta (yaklaşık 20-33 video/gün)** aralığında geldiğini gösteriyor; bazı kanallar 30 günde sadece doğrusal/yavaş büyüme (haftalık birkaç on abone) yaşarken, bazıları 4.-5. haftada ani bir viral video ile sıçrıyor. Bu tek haneli aboneli kanallara özgü, büyük ölçekli/istatistiksel bir çalışma bulunamadı — mevcut kanıtlar anekdot düzeyinde.

### Cited Findings
- Social Media Examiner'da aktarılan bir vaka çalışmasında (Pokemon kartı açma kanalı, günlük video, 60 günlük deney): gün 21'de videolar hâlâ sadece birkaç yüz izlenme alıyordu; sıçrama gün 32-33'te geldi, bir video 24 saatten kısa sürede 1 milyon izlenmeye ulaştı — [Social Media Examiner](https://www.socialmediaexaminer.com/) (spesifik makale URL'si arama sonucunda tam olarak doğrulanamadı, ikincil özet üzerinden aktarılıyor)
- Growth Models'ın 30 günlük günlük video deneyi: 219 aboneden başlayarak 30 günde ~48 abone kazanıldı (günde ortaya ~1 abone), büyüme eğrisi yavaşça yukarı kıvrılıyor; bu örnek tek haneli değil orta ölçekli bir kanaldan başlıyor — [Growth Models](https://growthmodels.co/daily-youtube-videos-30-days/)
- Dr. Luke Hobson'ın "30 Shorts in 30 Days" deneyinde: 30 günde 18.515 toplam izlenme, 140 yeni abone, 390 saat izlenme süresi (bir önceki aya göre ~%600 izlenme artışı) — ancak başlangıç abone sayısı ve gün-gün kırılım makalede yer almıyor — [Dr. Luke Hobson](https://drlukehobson.com/blog1/30shortsin30days)
- Brianabuga'nın 30 Shorts/30 gün deneyinde: 30+ Shorts sonunda 64 organik abone, ~30.000 toplam izlenme (video başına ilk 24 saatte ortalama ~1.000 izlenme); yazar "YouTube hâlâ kitlemi çözmeye çalışıyor" diyerek belirgin bir sıçrama yerine nispeten düz bir büyüme olduğunu ima ediyor — [Brianabuga](https://brianabuga.com/i-tried-posting-30-youtube-shorts-in-30-days/)

### Inferences
- Vaka çalışmaları arasındaki büyük varyans (bazı kanallar düz büyüme, bazıları 1 milyon izlenmelik ani sıçrama), "kaç video sonra büyüme başlar" sorusunun deterministik bir cevabı olmadığını, büyük ölçüde içerik/paketleme kalitesine ve şansa (algoritmanın hangi videoyu geniş kitleye test ettiğine) bağlı olduğunu gösteriyor.
- Örneklerin çoğunda 30 günlük/video pencere, "ilk somut sinyalleri görmek" için minimum eşik gibi görünüyor — 30 gün/video tamamlanmadan sonuç değerlendirmek erken olabilir.

### Gaps
- Spesifik olarak **tek haneli (1-9) aboneden başlayan** bir kanalın haftalık/video-video ilerlemesini (izlenme, abone, ilk 100+ izlenme videosu) gösteren, isim ve tarih doğrulanabilir bir vaka çalışması bulunamadı. Bulunan örneklerin çoğu ya başlangıç abone sayısını vermiyor ya da zaten üç haneli/orta ölçekli bir kanaldan başlıyor.
- "İlk 50+ abone" veya "ilk 100+ izlenme" eşiğine kaç günde/videoda ulaşıldığını doğrudan ölçen resmi/akademik bir istatistik bulunamadı.

## YouTube'un "Creator Insider" veya YouTube Help'in cold-start hesaplar için verdiği resmi tavsiyeleri neler?

### Takeaway
YouTube Help'in resmi "recommendation system" sayfası, yeni kanallar için paylaşım sıklığından çok "kritik kütle oluşturma", "niş/uzmanlık netliği" ve zamanın (güvenilirlik inşası) gerekliliğini vurguluyor; Creator Insider kanalının bu konuda doğrudan, isimlendirilebilir bir video alıntısı bu araştırmada bulunamadı — bu bir araştırma boşluğu olarak işaretleniyor.

### Cited Findings
- YouTube Help resmi sayfası: yeni kanalların algoritma tarafından tanınması için "izleyicilerin doğal olarak zaten uzmanlık veya net bir niş göstermiş kanallara çekildiğini" ve yeni kanallar için "bu güvenilirliği kazanmanın ve topluluk inşa etmenin zaman aldığını" açıkça kabul ediyor — [YouTube Help](https://support.google.com/youtube/answer/16559651?hl=en)
- Aynı sayfaya göre "kritik kütle" (critical mass) oluşturmak anahtar faktör: yeni bir izleyici bir videoyu keşfettiğinde, kanalda gezinebileceği başka yüksek kaliteli içerikler bulunması, algoritmaya kanalın değerli/ilgi çekici olduğu sinyalini veriyor — [YouTube Help](https://support.google.com/youtube/answer/16559651?hl=en)
- Genel (resmi olmayan, ikincil) kaynaklara göre yeni kanallar için ana ranking sinyalleri Click-Through Rate (CTR), Average View Duration (ortalama izlenme süresi) ve Engagement (etkileşim); yeni kanallarda algoritmanın geçmiş veri olmadığı için metadata (başlık, açıklama) sinyallerine daha çok güvendiği belirtiliyor — [TubeBuddy blog](https://www.tubebuddy.com/blog/how-youtube-recommends-videos/) (ikincil kaynak)

### Inferences
- YouTube'un resmi dilinde "sabır/zaman" ve "kritik kütle" vurgusu, cold-start'ı aşmanın resmi tavsiyesinin "hızlı viral olma taktiği" değil "sürdürülebilir, niş-odaklı içerik biriktirme" olduğunu gösteriyor.

### Gaps
- Creator Insider kanalının (youtube.com/@CreatorInsider) cold-start hesaplar için verdiği spesifik, alıntılanabilir bir tavsiye (video başlığı, tarih, doğrudan alıntı) bu araştırmada bulunamadı — arama sonuçları sadece genel referanslara ulaştı, kanalın kendi videosuna ulaşılamadı. Bu konuda ek/derinlemesine araştırma (Creator Insider kanalının video arşivinde doğrudan arama) önerilir.

## TikTok'un yeni hesaplar için "hesap ısınma" (account warm-up) kavramı gerçek mi, resmi kaynak var mı yoksa sadece sektör efsanesi mi?

### Takeaway
"Hesap ısınma" (account warm-up) terimi ve pratiği **TikTok'un resmi bir politikası/dokümantasyonu olarak doğrulanamadı** — bulunan tüm kaynaklar üçüncü taraf ajans/pazarlama blogları veya TikTok üzerindeki kullanıcı videolarıydı (resmi TikTok içeriği değil). TikTok'un resmi Newsroom açıklaması ise, yeni/sıfır takipçili bir hesabın bile güçlü etkileşim sinyaliyle geniş kitleye ulaşabileceğini söylüyor — bu, "yeni hesaplar spam gibi cezalandırılır, önce ısınmalı" iddiasıyla doğrudan çelişiyor. Sonuç: bu kavram büyük ölçüde bir **sektör efsanesi/en iyi-pratik varsayımı**, resmi TikTok kaynağıyla doğrulanmıyor.

### Cited Findings
- TikTok Newsroom resmi açıklaması: takipçi sayısı doğrudan bir sıralama faktörü değil; "a brand-new account with zero followers can still reach thousands (or even millions) of viewers if the video gets strong engagement signals" (ikincil özet üzerinden, birincil metne dayanarak) — [TikTok Newsroom](https://newsroom.tiktok.com/en-us/how-tiktok-recommends-videos-for-you)
- "Hesap ısınma" kavramını öne süren tüm kaynaklar üçüncü taraf pazarlama/ajans siteleri: superscale.ai, reel.farm, autoshorts.ai, undetectable.io, booktokguide.com — bunların hiçbiri TikTok'un resmi bir dokümanına/açıklamasına atıf yapmıyor; öneriler "TikTok'un algoritması yeni hesapları bot gibi görür" gibi doğrulanmamış varsayımlara dayanıyor — [undetectable.io TikTok Account Warm-Up](https://undetectable.io/blog/tiktok-account-warm-up/), [reel.farm](https://reel.farm/guides/how-to-warm-up-tiktok-account)
- TikTok.com/discover sayfalarında "How to Warm Up Your TikTok Account" gibi başlıklar görünüyor, ancak bunlar TikTok'un editoryal/resmi tavsiyesi değil, kullanıcıların yüklediği videoların otomatik toplandığı arama/keşif sayfaları — resmi TikTok pozisyonu olarak sayılamaz — [tiktok.com/discover](https://www.tiktok.com/discover/how-to-warm-up-your-tiktok-account)

### Inferences
- "Hesap ısınma" pratiğinin arkasındaki sezgi (yeni bir hesabın davranışının insan gibi görünmesi, bot/spam filtrelerinden kaçınması) TikTok'un genel spam/kötüye kullanım önleme sistemleriyle mantıksal olarak tutarlı olabilir, ancak bunun "yeni organik içerik üreten, gerçek bir kişi tarafından yönetilen hesaplar" için gerekli olduğuna dair resmi bir kanıt yok. Muhtemelen bu tavsiye, esas olarak **çoklu-hesap/bot-benzeri otomasyon kullanan pazarlamacılar** için ortaya çıkmış ve organik, tek-hesaplı içerik üreticilerine gereğinden fazla genelleştirilmiş bir efsane.

### Gaps
- TikTok'un spam/bot tespit sistemlerinin yeni hesapları nasıl değerlendirdiğine dair resmi, teknik bir açıklama (varsa) bu araştırmada bulunamadı — bu konuda TikTok'un Transparency Center veya Community Guidelines Enforcement dokümanlarına bakılması gerekebilir.
- "Isınma süresi" (3, 5, 7, 14 gün gibi) iddialarının hiçbiri ölçülebilir/test edilmiş bir kaynağa dayanmıyor; tüm sayılar anekdot/pazarlama tavsiyesi düzeyinde.
