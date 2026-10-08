"""RECEIPT URETECI - kaynak paketinden (kaynak_cek) KURAL TABANLI Receipt JSON'u kurar. MODEL YAZMAZ.

Girdi: paket (iddia cumlesi + secilen kanit cumleleri, hepsi sayfadan birebir), sirket/urun adi, sayfa tarihi,
       operatorun HUKMU (4 izinli damgadan biri). Cikti: receipt.py'nin bekledigi JSON (4-6 beat).
Her alinti sayfadan birebir ALT-DIZEDIR; olusan Receipt receipt.verify_receipt ile (alinti, sayi, niyet atfi/suc dili)
dogrulanir; sorun varsa YAZILMAZ ve nedenleri dondurulur.
Hukum insandir: kod 'destekliyor mu?' sorusuna kendisi karar vermez.
"""
import json
import os
import re
import unicodedata

import receipt as receipt_mod

HERE = os.path.dirname(os.path.abspath(__file__))
RECEIPTS = os.path.join(HERE, "receipts")

HUKUM_SABLON = {
    "SUPPORTED": "Our reading: supported. The page shows what its headline claims. Does the headline match the page for you?",
    "PARTLY SUPPORTED": "Our reading: partly supported, because the page qualifies its own claim. The headline or the details: which do you trust?",
    "NOT SUPPORTED BY THE PAGE": "Our reading: the page does not support its own claim. Would you accept this as proof?",
    "NOT SHOWN ON THE PAGE": "Our reading: the page states the claim but does not show the test behind it. Is a claim without a test enough for you?",
}
KANIT_GIRIS = ["The page also says: {q1}.", "It also states: {q1}.", "And: {q1}."]
KONUSMACI = ["alpha", "gamma", "beta"]


_BAGLAC = {"and", "or", "but", "to", "of", "the", "a", "an", "for", "with", "in", "on", "at", "by", "that", "which", "as", "is", "are",
           "not", "than", "from", "into", "its", "their", "this", "these", "while", "so"}


def _uc_temizle(q):
    """Basta/sonda yarim kalan baglac-edat sozcuklerini at (alinti hala birebir alt-dize kalir)."""
    kel = q.split()
    while kel and kel[0].lower().strip(",;:") in _BAGLAC:
        kel = kel[1:]
    while kel and kel[-1].lower().strip(",;:.") in _BAGLAC:
        kel = kel[:-1]
    return " ".join(kel)


def parca(cumle, anahtar="", maks=20):
    """Cumleden BIREBIR alt-dize (kelime sinirlarinda). Anahtar varsa onun etrafi; yoksa cumle basi, mumkunse
    virgul/noktalama (yan cumle) sinirinda biter. Yarim kalan baglac/edatlar atilir. Cift tirnak icermez."""
    kel = list(re.finditer(r"\S+", cumle))
    if not kel:
        return ""
    bas, son = 0, min(len(kel), maks)
    if anahtar:
        i = cumle.lower().find(anahtar.lower())
        if i >= 0:
            wi = next((k for k, m in enumerate(kel) if m.end() > i), 0)
            wj = next((k for k, m in enumerate(kel) if m.end() >= i + len(anahtar)), len(kel) - 1)
            bas = max(0, wi - 8)
            son = min(len(kel), max(wj + 4, bas + 1))
            while son - bas > maks and bas < wi:
                bas += 1
            while son - bas > maks and son > wj + 1:
                son -= 1
    elif len(kel) > maks:
        sinirlar = [k + 1 for k, m in enumerate(kel[: maks + 6]) if m.group(0)[-1] in ",;:" and k + 1 >= 6]
        if sinirlar:
            son = sinirlar[-1]
    q = cumle[kel[bas].start():kel[son - 1].end()].strip().rstrip(".,;:")
    if '"' in q:                                           # satir sablonu cift tirnaklidir: tirnaksiz en uzun parcayi al
        q = max(q.split('"'), key=len).strip()
    q2 = _uc_temizle(q)
    return q2 if len(q2) >= 12 and q2 in cumle else q


def _slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "receipt"


def kur(paket, sirket, urun, kaynak_tarih, hukum, kanit_idx=None, anahtar=""):
    """-> (receipt_dict | None, sorunlar[])"""
    if hukum not in HUKUM_SABLON:
        return None, [f"Hukum {sorted(HUKUM_SABLON)} listesinden biri olmali."]
    sirket, urun = (sirket or "").strip(), (urun or "").strip()
    if not sirket:
        return None, ["Sirket adi gerekli."]
    iddia = (paket.get("claim") or "").strip()
    if not iddia:
        return None, ["Pakette iddia cumlesi yok; Receipt kurulamaz."]
    kanitlar = paket.get("evidence", [])
    idx = list(range(len(kanitlar))) if kanit_idx is None else [i for i in kanit_idx if 0 <= i < len(kanitlar)]
    idx = idx[:3]
    if len(idx) < 2:
        return None, ["En az 2 kanit cumlesi sec (en fazla 3); Receipt 4-6 beat'ten olusur."]
    iq = parca(iddia, anahtar)
    if len(iq) < 12:
        return None, ["Iddia cumlesinden anlamli bir alinti cikarilamadi."]
    url = paket.get("url", "")
    beats = [{"who": "aura", "screen": "CLAIM VS PAGE", "label": "THE CLAIM",
              "line": f"The claim, from {sirket}'s own page: {{q1}}.", "quotes": [iq]}]
    for n, i in enumerate(idx):
        beats.append({"who": KONUSMACI[n % 3], "screen": "THE PAGE SAYS", "label": f"EVIDENCE {n + 1}",
                      "line": KANIT_GIRIS[n % 3], "quotes": [parca(kanitlar[i])]})
    beats.append({"who": "aura", "screen": "OUR READING", "label": "VERDICT", "stamp": hukum,
                  "line": HUKUM_SABLON[hukum], "quotes": []})
    kisa = anahtar.strip() if anahtar and anahtar.lower() in iddia.lower() and len(anahtar) <= 40 else ""
    baslik = f"{sirket}'s '{kisa}' Claim vs Its Own Page" if kisa else f"{sirket}'s Claim vs Its Own Page"
    ad = re.sub(r"^https?://(www\.)?", "", url).strip("/")
    r = {"company": sirket, "product": urun or sirket, "source_name": ad[:80] or paket.get("title", "")[:80],
         "source_date": kaynak_tarih or (paket.get("fetched_at", "")[:10]), "url": url, "title": baslik,
         "hookthumb": "CLAIM VS PAGE", "beats": beats}
    sorun = receipt_mod.verify_receipt(r, paket)
    return (None, sorun) if sorun else (r, [])


def yaz(r, klasor=RECEIPTS):
    os.makedirs(klasor, exist_ok=True)
    ad = f"{_slug(r['company'] + '-' + r['product'])}_{r['source_date']}.json"
    yol = os.path.join(klasor, ad)
    with open(yol, "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=1)
    return ad
