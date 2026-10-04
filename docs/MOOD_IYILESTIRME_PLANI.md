# Mood tespiti iyileştirme planı (TASLAK, onay bekliyor)

Durum: **kod yazılmadı.** Bu plan onaylanırsa uygulanır.

## 1. Bugün ne oluyor (koddan doğrulandı)
- `auro-backend/main.py` → `detect_mood(text)`: mesajda `MOOD_KEYWORDS` kelimelerinden
  birini arar; **ilk eşleşen** etiketi döndürür (mutlu/uzgun/yorgun/stresli/enerjik), yoksa `None`.
- **Olumsuzlama yok:** "yorgun değilim" → `yorgun`. "mutlu değilim" → `mutlu`.
- **Çoklu eşleşme:** "yorgunum ama harika bir gün" → sözlükteki sıraya göre `mutlu`
  (mesajdaki sıraya göre değil).
- İstemci (`chat_notifier.dart`): mood `None` gelince **önceki rengi korur**
  (nötr mesajda hale sıçramaz). Yalnızca yeni bir etiket gelince renk değişir.
- Gizli moddayken ve `mood_tracking_enabled` kapalıyken mood hesaplanmaz (doğru, korunacak).
- `database.add_mood(...)` her etiketi `mood_logs` tablosuna **mesajın ilk 100 karakteriyle**
  birlikte yazar (gizlilik notu, bkz. §5).
- Kriz tespiti (`_CRISIS_KEYWORDS`) ayrı listedir; **bu plan ona dokunmaz.**

## 2. Hedef
Yanlış rengi azaltmak. "Neden bu renk?" özelliği ancak bundan sonra anlamlı.

## 3. Adımlar (her biri ayrı, küçük, geri alınabilir)

**Backend (`main.py`):**
1. **Olumsuzlama:** eşleşen kelimeden hemen sonra (en çok 2 kelime içinde) "değil/değilim/degil/yok/not/n't/no longer"
   varsa o eşleşme **sayılmaz** (ters duyguya ÇEVRİLMEZ; "yorgun değilim" → etiket yok, hale önceki rengini korur).
2. **Karışık duygu (kullanıcı kararı):** mesajda **birden fazla farklı** duygu varsa hepsi toplanır
   (mesajdaki sıraya göre). API yanıtı geriye dönük uyumlu kalır: `mood` = ilk duygu (eski istemciler çalışmaya devam eder),
   yeni alan `moods` = tüm duyguların listesi.
3. **Test seti:** 30-40 TR/EN cümle (olumsuzlama, karışık duygu, alakasız kelime, Türkçe karakter
   varyantları); kriz kelimelerine dokunulmadığını doğrulayan ayrı test.

**İstemci (Flutter, `aura_hale.dart` ve `chat_state/notifier`) — backend bittikten SONRA, ayrı adım:**
4. **Harman:** `moods` birden fazlaysa hale tek bir ortalama renk yerine **iki ton yan yana
   (yumuşak gradyan)** gösterir (ortalama renk çamurlaşır, iki tonun ikisi de görünsün).
5. **Coşku hâli (kullanıcı kararı):** `mutlu`, `enerjik` (ve "keyifli" gibi mutlu kelimeleri) için
   bugünkünden **daha zengin** bir görünüm. Öneri aşağıda §3b.

### 3b. Coşku hâli önerisi (karar bekliyor)
- Renk: altın → mercan → ılık pembe harman (mutlu=altın ağırlıklı, enerjik=mercan ağırlıklı,
  ikisi birden=tam harman).
- Biçim: nefes biraz daha geniş, kenarda çok yavaş akan ince ışık parçacıkları.
- **Süre kuralı:** özel görünüm duygu ilk yakalandığında birkaç saniye "açılır", sonra
  **sakin, sabit parlak** bir hâle oturur. Sürekli hareket yok (pil ve dikkat çekmeme kuralı).
- **Değişmez kurallara uyum:** titreme/yanıp sönme yok, kullanıcıyı geri çağırmak için kullanılmaz,
  sadece kullanıcının kendi mutluluğuna **cevap** olarak çıkar. "Hareket azaltma" ayarı açıksa
  yalnızca sabit parlak hâl gösterilir.
- Seçenek A: yalnızca sabit parlak hâl (en sade). Seçenek B (önerim): kısa açılış + sabit parlak.

## 3c. Uygulama durumu (backend adımları 1-3 TAMAM, dal `claude/mood-tespiti-backend`)
- Yeni modül: `auro-backend/mood_detection.py` (`detect_moods`, `detect_mood`); `main.py` buradan içe aktarır.
- `/api/chat` yanıtına `moods` listesi eklendi; `mood` eskisi gibi (ilk duygu).
- **Plana eklenen ek düzeltme (bulgu):** `"sad"` düz alt-dize eşleşiyordu, "sadece/sade/sadık"
  içeren her mesaj "üzgün" oluyordu. Kısa/İngilizce kelimeler artık tam kelime eşleşir.
- Testler: `auro-backend/tests/test_mood_detection.py` (53 test geçti). Kriz kelimeleri modülde yok, testle doğrulanır.
- İstemci (adım 4-5: harman ve coşku hâli) YAPILMADI.

## 4. Kabul ölçütü
- Test setinin tamamı geçer.
- `_CRISIS_KEYWORDS` ve kriz akışı **değişmemiş** (diff'te yok).
- Mevcut sohbet davranışı (yanıt, limit, gizli mod) değişmez; `mood` alanı eskisi gibi tek string kalır,
  yalnızca yeni `moods` listesi eklenir (eski istemci kırılmaz).
- İstemci adımları için: iki ton gerçekten ayırt edilebiliyor mu (renk körlüğü: ikinci sinyal olarak biçim/doku farkı).

## 5. Bilerek kapsam dışı
- LLM ile duygu tespiti (maliyet, gecikme, açıklanamazlık; belki sonra).
- "Neden bu renk?" arayüzü ve tetikleyici kelimeyi API'ye ekleme.
- `mood_logs.context` alanı mesajın 100 karakterini saklıyor: meta-veri ilkesiyle
  çelişir; ayrı bir gizlilik kararı olarak ele alınmalı (bu planı bloklamaz).

## 6. Onay bekleyen kararlar
1. ~~Çoklu duygu~~ → **karar verildi:** renk değişsin, iki ton harmanlansın (adım 2 ve 4).
2. Olumsuzlamada etiket **yok** (ters duygu atamıyoruz) olsun mu? (önerim: evet)
3. Coşku hâli: A (sadece sabit parlak) mı, B (kısa açılış + sabit parlak, önerim) mi?
4. Uygulama bu dalda mı, ayrı dalda mı? (önerim: ayrı dal)
5. Önce yalnızca backend (adım 1-3), istemci görünümü sonra mı? (önerim: evet; backend tek başına güvenle test edilir)
