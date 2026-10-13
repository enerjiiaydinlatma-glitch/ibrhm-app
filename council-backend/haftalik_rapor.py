"""HAFTALIK RAPOR - kanalin kendi sonuclarindan Turkce, tek sayfa 'ne ise yaradi?' dosyasi. YouTube'a HICBIR sey yazmaz.

Kullanim:
  python haftalik_rapor.py                       # tracker.load() verisi -> _engine/rapor.md (yalniz --baslangic sonrasi videolar)
  python haftalik_rapor.py --tum                 # tum gecmis (eski Turkce donem dahil; yalniz bakmak icin)
  python haftalik_rapor.py --girdi videolar.json # tracker yerine dosyadan ({"videos":[...]} ya da [...])
  python haftalik_rapor.py --yorumlar y.json     # [{"video_id","text"}] -> en cok gecen kelimeler (opsiyonel)

Ilkeler (ogrenme.py ile ayni): MEDYAN, her satirda n ve guven etiketi, n<5 iken oneri YOK, hicbir sey otomatik uygulanmaz.
Rapor yalniz ONERIDIR: konu secimi ve yayin onayi insandadir; sensitivity_gate / claim_lint / source_check atlanmaz.
Varsayilan pencere: Ingilizce-tek-dil kararindan (13 Ekim 2026) sonra yayinlanan videolar; eski Turkce donemin verisi karismasin.
"""
import argparse
import collections
import datetime
import json
import os
import re
import sys

import hook_gate
import ogrenme

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, "_engine")
RAPOR_YOL = os.path.join(ENGINE, "rapor.md")
BASLANGIC = "2026-10-13"
KESIF_PAYI = 0.30          # onerilerin %30'u hic denenmemis/az denenmis alanlardan
CELISKI = re.compile(r"\b(but|not|never|wrong|lie|lies|myth|isn'?t|aren'?t|doesn'?t|actually|really|vs\.?|versus|against|instead)\b", re.I)
DURAK = set("""a an the and or but if of to in on at for with from by as is are was were be been it its this that these those
i you he she we they me my your our their him her them what who how why when where which not no yes do does did so than then
just about into over out up down more most very can will would should could have has had there here also too
""".split())


def kanca_tipi(baslik):
    """Basliktan kanca tipi (hook_gate.TETIK ile ayni mantik). Bir video tek tipe girer; oncelik: soru > rakam > celiski > diger."""
    b = baslik or ""
    if "?" in b:
        return "soru"
    if re.search(r"\d", b):
        return "rakam"
    if CELISKI.search(b):
        return "çelişki"
    return "diğer"


def acilis(baslik, k=3):
    return " ".join(re.findall(r"[a-z0-9']+", (baslik or "").lower())[:k])


def filtrele(videolar, baslangic=BASLANGIC):
    return [v for v in videolar if baslangic is None or str(v.get("published", ""))[:10] >= baslangic]


def kanca_bolumu(videolar, now=None):
    """ogrenme.karne mantigiyla (zamana gore duzeltilmis medyan) kanca tipi gruplari."""
    now = now or datetime.date.today()
    vs = [v for v in ogrenme.goreli(videolar)
          if (now - datetime.date.fromisoformat(str(v.get("published", ""))[:10])).days >= ogrenme.OLGUN_GUN]
    return ogrenme._grupla(vs, lambda v: [kanca_tipi(v.get("title", ""))])


def tekrar_acilislar(videolar, esik=2):
    c = collections.Counter(acilis(v.get("title", "")) for v in videolar if v.get("title"))
    return [(a, n) for a, n in c.most_common() if n >= esik and a]


def yorum_kelimeleri(yorumlar, k=15):
    """[{'video_id','text'}] -> en cok gecen anlamli kelimeler. Yalniz sayim: yorum metni rapora KOPYALANMAZ."""
    c = collections.Counter()
    for y in yorumlar or []:
        for w in re.findall(r"[a-z']{3,}", (y.get("text") or "").lower()):
            if w not in DURAK:
                c[w] += 1
    return c.most_common(k)


def _tablo(satirlar):
    if not satirlar:
        return "_Veri yok._\n"
    s = ["| Grup | n | Güven | Medyan izlenme | Dönemine göre | Tutma % | Yorum/1000 | Abone/1000 |", "|---|---|---|---|---|---|---|---|"]
    for r in satirlar:
        s.append(f"| {r['ad']} | {r['n']} | {r['guven']} | {r['med_izlenme']} | {r['med_goreli']}x | {r['med_tutma']} | {r['yorum_1000']} | {r['abone_1000']} |")
    return "\n".join(s) + "\n"


def rapor(videolar, yorumlar=None, now=None, baslangic=BASLANGIC):
    """Rapor metnini (Markdown, Turkce) dondurur. Saf fonksiyon: dosya/ag yok."""
    now = now or datetime.date.today()
    vs = filtrele(videolar, baslangic)
    k = ogrenme.karne(vs, now)
    n = k["genel"]["n"]
    s = [f"# Sign Council - Haftalık Rapor ({now.isoformat()})", "",
         f"Kapsam: {(baslangic + ' sonrası yayınlanan videolar') if baslangic else 'tüm geçmiş (eski Türkçe dönem dahil)'}. Olgun (≥{ogrenme.OLGUN_GUN} gün) video sayısı: **{n}** "
         f"(toplam {len(vs)}).", "",
         "> Bu rapor ÖNERİDİR, kanıt değil. Hiçbir şey otomatik uygulanmaz; konu ve yayın onayı sende. Güvenlik kapıları aynen geçerli.", ""]
    if n < ogrenme.MIN_N:
        s += [f"## Durum: veri yetersiz", "",
              f"Öneri için bir grupta en az {ogrenme.MIN_N} video gerekir; şu an toplam {n} olgun video var. "
              "Aşağıdaki tablolar yalnızca bakmak içindir. Önerilen: formatı değiştirmeden çeşitli kanca tiplerini ve karakter ikililerini DENE, "
              "sonra bu raporu tekrar çalıştır.", ""]
    g = k["genel"]
    if n:
        s += ["## Genel", "", _tablo([g]), ""]
        s += ["## Kanca tipi", "", _tablo(kanca_bolumu(vs, now)), ""]
        for ad, baslik in (("sutun", "Sütun (format)"), ("sayi", "Başlıkta sayı"), ("soru", "Soru / ifade"), ("uzunluk", "Başlık uzunluğu")):
            s += [f"## {baslik}", "", _tablo(k["bolumler"][ad]), ""]
    s += ["## Bu hafta ne yapmalı?", ""]
    if k["oneriler"]:
        s += [f"- {o['metin']}" for o in k["oneriler"]]
    else:
        s.append("- Henüz yeterli veri/belirgin fark yok. Öneri üretilmedi (uydurma yok).")
    s.append(f"- Keşif kuralı: yayınların ~%{int(KESIF_PAYI * 100)}'i en az denenmiş kanca tipi/konu/karakter ikilisinden olsun.")
    s.append("")
    tek = tekrar_acilislar(vs)
    if tek:
        s += ["## Tekrar eden açılışlar (hook_gate de buna izin vermez)", ""] + [f"- \"{a}\" ×{c}" for a, c in tek] + [""]
    if yorumlar:
        kel = yorum_kelimeleri(yorumlar)
        s += [f"## Yorumlarda en çok geçen kelimeler ({len(yorumlar)} yorum)", ""]
        s += [", ".join(f"{w} ({c})" for w, c in kel) or "_Anlamlı kelime yok._", ""]
    else:
        s += ["## Yorumlar", "", "_Yorum dosyası verilmedi (--yorumlar). Henüz yorum yoksa bu normaldir._", ""]
    s += ["## Başarı / ölüm ölçütü (14 gün, sabit)", "",
          "Medyan ≥50 izlenme, video başı ≥3 yorum, izlendi (kaydırılmadı) ≥%60. Bu üçü tutmuyorsa format veya konu değişir; "
          "ölçüt gevşetilmez.", ""]
    return "\n".join(s)


def _yukle(yol):
    with open(yol, encoding="utf-8") as f:
        d = json.load(f)
    return d.get("videos", []) if isinstance(d, dict) else d


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--girdi")
    ap.add_argument("--yorumlar")
    ap.add_argument("--tum", action="store_true")
    ap.add_argument("--cikti", default=RAPOR_YOL)
    a = ap.parse_args(argv)
    if a.girdi:
        videolar = _yukle(a.girdi)
    else:
        import tracker  # yalniz yerel makinede var
        videolar = (tracker.load() or {}).get("videos", [])
    yorumlar = _yukle(a.yorumlar) if a.yorumlar else None
    metin = rapor(videolar, yorumlar, baslangic=None if a.tum else BASLANGIC)
    os.makedirs(os.path.dirname(a.cikti), exist_ok=True)
    with open(a.cikti, "w", encoding="utf-8-sig") as f:
        f.write(metin)
    print(f"Rapor yazildi: {a.cikti}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
