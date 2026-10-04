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
1. **Olumsuzlama:** eşleşen kelimeden hemen sonra (en çok 2 kelime içinde) "değil/değilim/degil/yok/not/n't/no longer"
   gibi bir olumsuzlama varsa o eşleşme **sayılmaz** (ters duyguya ÇEVRİLMEZ; "yorgun değilim" → etiket yok).
2. **Çoklu eşleşme:** mesajda **birden fazla farklı** duygu varsa `None` döndür (belirsiz).
   İstemci önceki rengi korur. (Bugünkü "sözlükte ilk gelen kazanır" davranışı kalkar.)
3. **Test seti:** 30-40 TR/EN örnek cümle (olumsuzlama, çoklu duygu, alakasız kelime,
   Türkçe karakter varyantları) ve beklenen etiket; otomatik çalışan test dosyası.
   Kriz kelimelerine dokunulmadığını doğrulayan ayrı bir test.
4. *(Sonraki iş, bu plana dahil değil)* API yanıtına tetikleyici kelimeyi ekleme
   ("Neden bu renk?" için).

## 4. Kabul ölçütü
- Test setinin tamamı geçer.
- `_CRISIS_KEYWORDS` ve kriz akışı **değişmemiş** (diff'te yok).
- Mevcut sohbet davranışı (yanıt, limit, gizli mod) değişmez; yalnızca `mood` alanı farklı dönebilir.

## 5. Bilerek kapsam dışı
- LLM ile duygu tespiti (maliyet, gecikme, açıklanamazlık; belki sonra).
- "Neden bu renk?" arayüzü, hale tasarımı.
- `mood_logs.context` alanı mesajın 100 karakterini saklıyor: meta-veri ilkesiyle
  çelişir; ayrı bir gizlilik kararı olarak ele alınmalı (bu planı bloklamaz).

## 6. Onay bekleyen kararlar
1. Çoklu duygu → `None` (belirsiz) olsun mu?
2. Olumsuzlama yakalanınca etiket **yok** (ters duygu atamıyoruz) olsun mu?
3. Plan onaylanırsa uygulama bu dalda mı yapılsın, ayrı dalda mı?
