"""KANCA KAPISI - uretimden ONCE acilis ve baslik denetimi. Saf fonksiyonlar (test edilebilir).

13 Ekim 2026 bulgusu: 'ilk 3 saniye kurali' yalnizca modelin yazdigi formatlarin ISTEMINDE vardi (make_topic_short.py);
Receipt videolari sablondan uretildigi icin ilk cumle hep 'The claim, from X's own page: "..."' idi ve kanca denetimi YOKTU.
Bu modul kurali KODLA zorlar: ihlal varsa uretim yapilmamali (cagiran taraf karar verir).

Bu kapi dogruluk korumalarinin (claim_lint, source_check, sensitivity_gate) YERINE GECMEZ; onlara EK bir kalite kapisidir.
Yeni sablon/format uretimine baglanmadan once yalnizca kontrol fonksiyonu olarak vardir (henuz hicbir uretim yoluna kablolanmadi).
"""
import re

ILK_MAX_KELIME = 8
ILK_MAX_KARAKTER = 50
BASLIK_MAX = 45
EKRAN_MIN, EKRAN_MAX = 3, 5

YASAK_ACILIS = re.compile(r"^\s*(the claim|from |according to|today[, ]|in this (video|short)|hello|hi[, ]|hey[, ]|welcome|"
                          r"let'?s (talk|look|dive)|did you know)", re.I)
TETIK = re.compile(r"\?|\d|\b(but|not|never|why|how|wrong|missing|only|just|nobody|everyone|still|vs\.?|versus|against|"
                   r"worst|best|first|last|stop|before|after|instead)\b", re.I)
VARSAYILAN_KANCA_ETIKETLERI = {"CLAIM VS PAGE", "THE REAL STORY", ""}


def _kelime(s):
    return re.findall(r"[A-Za-z0-9'%$.-]+", s or "")


def kontrol(baslik, ilk_cumle, son_cumle="", ekran_metni=""):
    """-> [(kod, mesaj)]. Bos liste = gecti."""
    sorun = []
    ilk = (ilk_cumle or "").strip()
    n = len(_kelime(ilk))
    if n > ILK_MAX_KELIME:
        sorun.append(("ILK_UZUN", f"Ilk cumle {n} kelime (en fazla {ILK_MAX_KELIME})."))
    if len(ilk) > ILK_MAX_KARAKTER:
        sorun.append(("ILK_KARAKTER", f"Ilk cumle {len(ilk)} karakter (en fazla {ILK_MAX_KARAKTER})."))
    if YASAK_ACILIS.search(ilk):
        sorun.append(("YASAK_ACILIS", "Ilk cumle kanca degil, anons/alinti kalibiyla basliyor ('The claim...', 'Today...', 'Hello...')."))
    if not TETIK.search(ilk):
        sorun.append(("TETIK_YOK", "Ilk cumlede rakam, soru ya da celiski/tetik sozcugu yok."))
    if re.search(r"[\"\u201c\u201d]", ilk):
        sorun.append(("ILK_ALINTI", "Ilk cumlede tirnakli alinti var; alinti 2. bolumden once baslamamali."))
    b = (baslik or "").strip()
    if len(b) > BASLIK_MAX:
        sorun.append(("BASLIK_UZUN", f"Baslik {len(b)} karakter (en fazla {BASLIK_MAX}); viral tarama: kisa baslik 2x medyan."))
    if ":" in b:
        sorun.append(("BASLIK_IKI_NOKTA", "Baslikta iki nokta var; viral tarama: iki noktali basliklar 0,16x."))
    if re.search(r"[\"'\u2018\u2019\u201c\u201d]\s*\w", b) and b.count("'") + b.count('"') >= 2:
        sorun.append(("BASLIK_TIRNAK", "Baslikta tirnakli ifade var."))
    if ekran_metni is not None and ekran_metni != "":
        w = len(_kelime(ekran_metni))
        if ekran_metni.strip().upper() in VARSAYILAN_KANCA_ETIKETLERI:
            sorun.append(("EKRAN_VARSAYILAN", "Ilk kart etiketi varsayilan sablon metni."))
        elif not (EKRAN_MIN <= w <= EKRAN_MAX):
            sorun.append(("EKRAN_UZUNLUK", f"Ilk kart metni {w} kelime ({EKRAN_MIN}-{EKRAN_MAX} olmali)."))
    elif ekran_metni == "":
        sorun.append(("EKRAN_YOK", "Ilk kart metni tanimli degil."))
    s = (son_cumle or "").strip()
    if s and not ("?" in s or re.search(r"\b(a or b|team \w+|vote|comment|you)\b", s, re.I)):
        sorun.append(("SON_KAPANIS", "Son cumle izleyiciyi yorumla bir tarafa cagirmiyor (soru / iki secenek)."))
    return sorun


def tekrar_kontrol(ilk_cumleler, yeni, son_n=5):
    """Ayni acilis kalibinin (ilk 2 kelime: 'Why did', 'How to'...) son N videoda tekrarlanmasini yakalar."""
    def kalip(x):
        return " ".join(w.lower() for w in _kelime(x)[:2])
    k = kalip(yeni)
    if k and sum(1 for x in ilk_cumleler[-son_n:] if kalip(x) == k) >= 2:
        return [("ACILIS_TEKRAR", f"Acilis kalibi son {son_n} videoda zaten >=2 kez kullanildi: '{k}'.")]
    return []
