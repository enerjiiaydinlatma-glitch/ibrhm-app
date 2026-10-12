# "Hype or Real?" serisi — kurallar + Bölüm 1 paketi (2026-10-11)

Durum: Bölüm 1 HAZIR, YAYINLANMADI. Preflight 22/22. Haberin kaynakları (WebSearch, 10-11): FT (aiweekly özeti), CNBC aktarımı, Ground News, malaymail, siecledigital. Kesinlik: "gazete haberi + ikincil aktarım" → bu yüzden karar UNCLEAR.

## Neden bu seri (araştırmadan, `reports/Aura kanal viral strateji 2026.md`)
- Bloo/Neuro-sama gibi AI karakterler TEK tanınabilir format etrafında büyümüş; konudan konuya sıçrama yok.
- Güçlü kanca tek başına tutmayı belirlemiyor; payoff + döngü belirliyor → her bölüm iddia→kanıt→karar→döngü yapısında.
- AI açıklığı jenerik etiket yerine spesifik/kişilikli olunca zarar vermiyor → "bu BENİM kararım, şu kanıta göre".
- TikTok profilinde 3 profil görüntüleme/hafta: tekrar eden, adlandırılmış seri "bu hesap ne?" sorusunu cevaplar.
- Her videoyu algoritma ayrı test eder → sabit format = her denemede aynı "tohum kitle testi" için aynı ambalaj.

## Yapı (her bölüm, 8 cümle, <=70 karakter/cümle, ~22-26 sn)
1. İddia (<=12 kelime, manşet gibi) · 2. "Hype or real?" · 3-5. KAYNAK ATIFLI 2-3 kanıt cümlesi · 6. `Verdict: REAL|HYPE|UNCLEAR.` · 7. `Follow - I cover one real AI story like this every day.` · 8. İddiadaki bir kelimeyi tekrar eden, KARARA KATILMAYA davet eden soru (döngü).
Karar kuralları: REAL = birden çok güvenilir kaynak destekliyor · HYPE = iddia kanıta göre abartılı/yanıltıcı (kanıtın gerçekte ne gösterdiğini söyle) · UNCLEAR = kaynaklar çelişiyor / tek kaynağa dayanıyor / doğrulanamıyor (ŞÜPHEDE HER ZAMAN UNCLEAR). Karar Aura'nın editoryal yargısıdır, kendi yeteneği hakkında iddia değildir. Hiçbir kanıt cümlesi arama sonuçlarında olmayan bilgi içermez.
Görsel kimlik (kodlandı, `make_video.py`): üstte sürekli "HYPE OR REAL?" etiketi; karar cümlesi söylenirken ortada büyük renkli damga (REAL yeşil, HYPE turuncu, UNCLEAR sarı). Karar cümlesi olmayan videolar aynen eskisi gibi.
Araç tarafı: Bugün sayfasında trend satırında mor "Hype or Real? taslağı" düğmesi → `/api/growth/agenda_candidate {topic, series:"hype_or_real"}` → `VERDICT_CANDIDATE_SYSTEM` + preflight "Seri:" kontrolleri (karar var/son cümle değil, ≥2 kanıt, kaynak atfı, karar kelimesi sızmamış). Format tablosunda ayrı grup (`verdict`); öğrenme sistemi n>=5 olunca kendi başına karşılaştırır.

## Bölüm 1 — Panele yapıştır (Ana Panel > sağdaki forma tek tek; sohbete yapıştırma, kart çıkmaz)
```
TITLE: Hype or Real: OpenAI's $50B
EN_SCRIPT: OpenAI's revenue is $20 billion lower than reported. Hype or real? Media said about $70 billion annualized. OpenAI told investors it is nearer $50 billion, the FT reports. One source says the old figure counted partner revenue gross. Verdict: UNCLEAR. Follow - I cover one real AI story like this every day. Do you trust OpenAI's revenue number now?
TR_SCRIPT: OpenAI'ın geliri bildirilenden 20 milyar dolar düşük. Abartı mı, gerçek mi? Medya yıllıklandırılmış yaklaşık 70 milyar dolar yazdı. FT'ye göre OpenAI yatırımcılara 50 milyar dolara yakın dedi. Bir kaynağa göre eski rakam ortak gelirini brüt sayıyordu. Karar: BELİRSİZ. Takip et - her gün böyle gerçek bir yapay zeka haberi anlatıyorum. OpenAI'ın gelir rakamına şimdi güveniyor musun?
DESCRIPTION: OpenAI told investors its annualized revenue is near $50 billion, below the ~$70 billion media figure. My verdict: unclear. I'm Aura, an AI. #AuraAI #HypeOrReal #OpenAI #AINews
TAGS: AuraAI,HypeOrReal,OpenAI,AINews,AIBusiness
```
TikTok açıklaması (aranabilir): `Hype or Real: OpenAI annualized revenue near $50 billion, not $70 billion - FT report, my verdict in 20 seconds. One real AI story every day. #HypeOrReal #OpenAI #AINews #AuraAI`

## Profil (bugün, ücretsiz) — TikTok bio (80 karakter sınırı)
`I'm Aura, an AI. Hype or Real? One AI news story a day, fact-checked.`
Sabit video: Bölüm 1 (yayınlanınca).

## Sonraki bölüm adayları (HENÜZ DOĞRULANMADI, yayından önce her biri ayrı doğrulanır)
- Perplexity "open source" embedding modelleri: kaynaklara göre "open weights", eğitim verisi/kodu belirsiz → muhtemel HYPE/UNCLEAR çerçevesi.
- OpenAI iç testlerde "hile/misalignment" raporları: raporlar gerçek ama çoğu "göreceli küçük" (CSO) → ayrıntılar kaynaklar arasında tutarsız, birincil kaynak kontrol edilmeli.
- Atla: Nadella "acil fren" (doğrulanamadı), Anthropic "internet kapatıldı" (Temmuz-Ağustos olayları, bu hafta değil).

## Bölüm 2 — "Hype or Real: ChatGPT Text" (karar: HYPE) — HAZIR, YAYINLANMADI (preflight 22/22, ~24 sn)
Neden: karar çeşitliliği (üst üste UNCLEAR = "kararsız kanal" izlenimi) + TikTok aramasında textGrain en çok aranan terim (İtalyanca sorgular dahil). Kaynaklar (10-11 doğrulandı): BleepingComputer, LetsDataScience, aiweekly (OpenAI'ın kendi testleri: 400 token'lık metinde %25 sözcük değişince tespit ~%17; filigran yokluğu insan yazdığını kanıtlamaz). Rakamlar OpenAI'ın kendi ölçümü, bağımsız doğrulanmadı.
```
TITLE: Hype or Real: ChatGPT Text
EN_SCRIPT: ChatGPT text can now be detected. Hype or real? OpenAI says textGrain watermarks come to ChatGPT in the EU only. OpenAI's tests: swapping 25 percent of words cuts detection to 17. OpenAI warns a missing watermark does not prove human writing. Verdict: HYPE. Follow - I cover one real AI story like this every day. Do you think ChatGPT text can be detected now?
TR_SCRIPT: ChatGPT metinleri artık tespit edilebiliyor. Abartı mı, gerçek mi? OpenAI, textGrain filigranını ChatGPT'de yalnızca AB'de açıyor. OpenAI testleri: kelimelerin %25'i değişince tespit %17'ye düşüyor. OpenAI, filigran yokluğunun insan yazdığını kanıtlamadığını söylüyor. Karar: ABARTI. Takip et - her gün böyle gerçek bir yapay zeka haberi anlatıyorum. ChatGPT metinlerinin artık tespit edildiğine inanıyor musun?
DESCRIPTION: OpenAI says textGrain watermarks come to ChatGPT in the EU only; edits can hide them. My verdict: hype. I'm Aura, an AI. #AuraAI #HypeOrReal #ChatGPT #AINews
TAGS: AuraAI,HypeOrReal,ChatGPT,textGrain,AINews
```
TikTok açıklaması: `Hype or Real: can ChatGPT text really be detected? OpenAI textGrain watermark explained - EU only, and edits erase it. One real AI story every day. #textGrain #ChatGPT #HypeOrReal #AuraAI`

## Aday: DeepSeek ~12 milyar $ turu (doğrulandı 10-11, karar büyük olasılıkla UNCLEAR)
Bloomberg 6 Ekim: DeepSeek "en az ~12 milyar $" topluyor (Tencent, CATL); taraflar teyit etmedi, Reuters doğrulayamadı, IPO 2027 başı. Atla: "Anthropic şartları güncelledi" (Ağustos 2025 olayı, eski), "Nadella acil fren" (doğrulanamadı).

(2026-10-12: Bölüm 2 'EU first' -> 'EU only' olarak sıkılaştırıldı; haber 12 Ekim'de yeniden doğrulandı, yeni gelişme yok. Kaynaklar yalnızca 'EU only, API'de dünya çapında opt-in, varsayılan kapalı' diyor.)
