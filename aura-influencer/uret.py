"""Terminalden uretim: tek komutla paket -> Turkce anlam onayi -> render -> izle -> yayin -> TikTok paketi.

Kullanim (PowerShell):
    python C:\\AuraProject\\ibrhm_app\\aura-influencer\\uret.py            # bekleyen isleri listeler
    python C:\\AuraProject\\ibrhm_app\\aura-influencer\\uret.py petra      # basliginda "petra" gecen taslagi uretir

Panelin (aura_studio.py) calisiyor olmasi gerekir; bu betik panelin KENDI API'sini cagirir, yani panel ekraniyla ayni
guvenceler gecerlidir (sunucuda onay sarti, ayni baslik korumasi, tek islem kilidi). Onay terminalde YAZARAK verilir:
hicbir sey kendiliginden yayinlanmaz.
"""
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("AURA_URL", "http://127.0.0.1:" + os.environ.get("AURA_STUDIO_PORT", "8795"))
PROMISES = ["i will", "i'll", "every day", "every week", "every month", "always", "i promise", "guarantee"]


def api(method, path, body=None, timeout=60):
    req = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode("utf-8") if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8") or "null")


def split_sentences(text):
    out, cur, s = [], "", str(text or "")
    for i, ch in enumerate(s):
        cur += ch
        if ch in ".?!" and (i + 1 >= len(s) or s[i + 1] == " "):
            out.append(cur.strip())
            cur = ""
    if cur.strip():
        out.append(cur.strip())
    return out


def checks(d):
    """Panelin 'Onay ve kontrol listesi'ndeki otomatik kontrollerin aynisi."""
    txt = str(d.get("en_script", "")) + " " + str(d.get("description", ""))
    warns = []
    if not re.search(r"not real footage|3D rebuild", txt, re.I):
        warns.append("Videoda ya da aciklamada 'not real footage' ibaresi YOK.")
    low = str(d.get("en_script", "")).lower()
    hit = [p for p in PROMISES if p in low]
    if hit:
        warns.append("Gelecek davranis vaadi olabilir: " + ", ".join(hit) + ". Her seferinde tutabilecek misin?")
    return warns


def show(d):
    en, tr = split_sentences(d.get("en_script")), split_sentences(d.get("tr_script"))
    print("\n" + "=" * 72)
    print(d["title"] + "   [" + d.get("status", "") + "]")
    pf = d.get("preflight") or {}
    if pf:
        print("Kural uyumu: %s/%s  (~%s sn)" % (pf.get("score"), pf.get("of"), pf.get("est_seconds")))
    print("=" * 72)
    for i, a in enumerate(en):
        print("%2d  EN: %s" % (i + 1, a))
        print("    TR: %s" % (tr[i] if i < len(tr) else "(yok)"))
    if len(en) != len(tr):
        print("\n!! DIKKAT: EN %d / TR %d cumle" % (len(en), len(tr)))
    print("\nNeden bu konu / kaynaklar:\n  " + str(d.get("rationale", ""))[:700])


def copy_clip(text):
    try:
        subprocess.run(["clip"], input=text.encode("utf-16"), check=True)
        return True
    except Exception:
        return False


def pinned(d):
    ss = split_sentences(d.get("en_script"))
    q = [x for x in ss if x.endswith("?")]
    last = ss[-1] if ss else ""
    return (q[-1] if q else "") + (" " + last if "one word" in last.lower() or last.lower().startswith("comment") else "")


def main(argv, inp=input, opener=None, out=print):
    opener = opener or (os.startfile if hasattr(os, "startfile") else (lambda p: None))
    try:
        api("POST", "/api/growth/load_packages", {})
        state = api("GET", "/api/growth/state")
    except (urllib.error.URLError, ConnectionError, OSError) as e:
        out("Panele ulasilamadi (%s). Once guncelle.bat ile paneli baslat." % e)
        return 2
    drafts = state.get("drafts", [])
    pend = [d for d in drafts if d.get("status") != "yayinlandi"]
    key = " ".join(argv).strip().lower()
    if not key:
        out("Bekleyen isler:")
        for d in pend:
            out("  - %s  [%s]" % (d["title"], d.get("status")))
        out("\nUretmek icin: python uret.py <baslikta gecen kelime>")
        return 0
    cand = [d for d in pend if key in d["title"].lower()]
    if not cand:
        out("Bekleyen taslaklar arasinda '%s' yok." % key)
        return 1
    if len(cand) > 1:
        out("Birden fazla eslesme; daha belirgin yaz:")
        for d in cand:
            out("  - " + d["title"])
        return 1
    d = cand[0]
    show(d)
    warns = checks(d)
    for w in warns:
        out("\n!! UYARI: " + w)
    if inp("\nTurkce anlamini okudun ve her sayi/iddianin kaynagi notta var mi? Onay icin EVET yaz: ").strip() != "EVET":
        out("Onay verilmedi, durdum.")
        return 0
    if warns and inp("Uyarilar var. Yine de devam icin DEVAM yaz: ").strip() != "DEVAM":
        out("Durdum.")
        return 0
    if d.get("status") == "taslak":
        out("\nRender ediliyor (gercek Aura sesiyle 1-4 dk)...")
        r = api("POST", "/api/growth/render_draft", {"id": d["id"]}, timeout=900)
        if not r.get("ok"):
            out("RENDER OLMADI: " + str(r.get("error")))
            return 1
        if r.get("warning"):
            out("Uyari: " + str(r["warning"]))
    daily = api("GET", "/api/daily")
    info = next((x for x in daily.get("items", []) if x["id"] == d["id"]), {})
    path = info.get("path")
    if path and os.path.exists(path):
        out("\nVideo: " + path)
        try:
            opener(path)
        except Exception:
            pass
    out("Izle: ust bant sonuna kadar duruyor mu, ilk karede yuz var mi, oy karti sonda cikiyor mu, ses temiz mi?")
    if inp("Yayinlansin mi? (HERKESE ACIK yayin icin YAYINLA yaz, bos birak = cik): ").strip() != "YAYINLA":
        out("Yayinlanmadi. Render hazir; panelden ya da yeniden calistirarak yayinlayabilirsin.")
        return 0
    r = api("POST", "/api/growth/publish_draft", {"id": d["id"], "confirm": True}, timeout=900)
    if not r.get("ok"):
        out("YAYIN OLMADI: " + str(r.get("error")))
        return 1
    out("\nYAYINDA: " + str(r.get("link")))
    cap = d.get("tiktok_description") or d.get("description", "")
    out("\n--- TikTok / Reels ---\nDosya:\n  " + str(path) + "\nAciklama (panoya kopyalandi):\n  " + cap)
    copy_clip(cap)
    out("\nSabit yorum:\n  " + pinned(d))
    out("\n'AI ile uretildi' etiketini ac. Ilk saatte her yoruma cevap ver. 24 saat olcumu: panel > Olcum.")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.exit(main(sys.argv[1:]))
