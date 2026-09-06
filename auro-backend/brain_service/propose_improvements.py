"""INSAN-ONAYLI kendini gelistirme motoru (2026-09-06, kullanici istegi:
"insan testleri yaptiralim... kendini icine gelistirme motor sistemi").

Bu betik OTONOM DEGIL: production /api/admin/feedback ucundan gercek
kullanici 👍/👎 geri bildirimlerini ceker, 👎'lari desen bazinda analiz
eder ve aura_brain.py'ye eklenebilecek SOMUT kural/golden onerileri
uretip `improvement_proposals.md`'ye yazar. Uygulamayi bir INSAN yapar
(bu oturumda elle yurutulen test -> bulgu -> kural -> dogrulama
dongusunun urunlestirilmis hali).

Kullanim:
    set ADMIN_KEY=...   (ya da --admin-key)
    python propose_improvements.py [--since 2026-09-01] [--limit 500]

Cikti: improvement_proposals.md (append, tarih damgali). Hicbir sey
otomatik canliya gitmez.
"""
import argparse
import datetime as _dt
import json
import os
import re
import sys
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = "https://aura-backend-production-bc9c.up.railway.app"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "Chrome/126 Safari/537.36")


def _gkey():
    for p in (os.path.join(HERE, "..", ".env"),
              "C:/AuraProject/ibrhm_app/auro-backend/.env"):
        if os.path.exists(p):
            for line in open(p, encoding="utf-8"):
                if line.strip().startswith("GEMINI_API_KEY="):
                    return line.strip().split("=", 1)[1].strip()
    return os.getenv("GEMINI_API_KEY")


def fetch_feedback(admin_key, since=None, limit=500):
    url = f"{BACKEND}/api/admin/feedback?limit={limit}"
    if since:
        url += f"&since={since}"
    req = urllib.request.Request(url, headers={"X-Admin-Key": admin_key,
                                               "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            sys.exit("HATA: 404 - ADMIN_KEY yanlis ya da Railway'de tanimli "
                     "degil. Railway > Variables > ADMIN_KEY ekleyip redeploy "
                     "sonrasi tekrar dene.")
        sys.exit(f"HATA: HTTP {e.code} - {e.read()[:200]}")


ANALYSIS_PROMPT = """Sen Aura adli Turkce yapay zeka yoldas-asistanin kalite
muhendisisin. Asagida gercek kullanicilarin BEGENMEDIGI ({down_n} adet) ve
BEGENDIGI ({up_n} adet) Aura yanitlari var (kullanici mesaji + Aura yaniti
ciftleri).

BEGENILMEYENLER:
{down_block}

BEGENILENLER (kiyas icin):
{up_block}

Gorevin: begenilmeyenlerde TEKRAR EDEN somut desenleri bul (klise ton,
asiri uzunluk, soruyla kacma, sahte kesinlik, sinir ihlali, kendini
tekrar, kimlik kaymasi vb.). Her desen icin:
1. Deseni tek cumleyle tarif et + kac ornekte gorundugunu yaz.
2. En net 1-2 kanit alintisi.
3. aura_brain.py'ye eklenebilecek SOMUT bir kural metni ONER (mevcut
   kurallarin uslubunda: BUYUK HARF baslik + net yasak/yonlendirme), YA DA
   bunun bir kural degil golden-ornek isi oldugunu soyle.
4. Guven: yuksek/orta/dusuk (kac ornege dayaniyor).

En fazla 5 desen. Yeterli veri yoksa "yeterli sinyal yok" de. Turkce yaz.
SADECE analizi ver, baska bir sey ekleme."""


def _pairs_block(items, rating, cap=40):
    out = []
    for it in items:
        if it.get("rating") != rating:
            continue
        um = (it.get("user_message") or "").strip()
        ar = (it.get("aura_reply") or "").strip()
        note = (it.get("note") or "").strip()
        seg = f"- KULLANICI: {um[:400]}\n  AURA: {ar[:700]}"
        if note:
            seg += f"\n  KULLANICI NOTU: {note[:200]}"
        out.append(seg)
        if len(out) >= cap:
            break
    return "\n\n".join(out) if out else "(yok)"


def analyze(gkey, items):
    from google import genai
    from google.genai import types
    cl = genai.Client(api_key=gkey,
                      http_options=types.HttpOptions(timeout=60000))
    down_n = sum(1 for i in items if i.get("rating") == "down")
    up_n = sum(1 for i in items if i.get("rating") == "up")
    prompt = ANALYSIS_PROMPT.format(
        down_n=down_n, up_n=up_n,
        down_block=_pairs_block(items, "down"),
        up_block=_pairs_block(items, "up", cap=15),
    )
    r = cl.models.generate_content(
        model="gemini-3.7-flash",
        contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
        config=types.GenerateContentConfig(temperature=0.2))
    return (r.text or "").strip(), down_n, up_n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--admin-key", default=os.getenv("ADMIN_KEY", ""))
    ap.add_argument("--since", default=None)
    ap.add_argument("--limit", type=int, default=500)
    ap.add_argument("--min-down", type=int, default=5,
                    help="bu sayidan az 👎 varsa analiz calistirma")
    args = ap.parse_args()
    if not args.admin_key:
        sys.exit("HATA: ADMIN_KEY gerekli (env ya da --admin-key).")
    gkey = _gkey()
    if not gkey:
        sys.exit("HATA: GEMINI_API_KEY bulunamadi.")

    data = fetch_feedback(args.admin_key, since=args.since, limit=args.limit)
    counts = data.get("counts", {})
    items = data.get("items", [])
    down_total = counts.get("down", 0)
    print(f"Geri bildirim: toplam {counts.get('total', 0)} "
          f"(👍 {counts.get('up', 0)} / 👎 {counts.get('down', 0)}) | "
          f"cekilen {len(items)}")

    if down_total < args.min_down:
        print(f"👎 sayisi ({down_total}) esigin ({args.min_down}) altinda - "
              f"anlamli desen cikmaz, analiz atlaniyor.")
        return

    analysis, dn, un = analyze(gkey, items)
    stamp = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    out_path = os.path.join(HERE, "improvement_proposals.md")
    header = (f"\n\n---\n\n## {stamp} - {dn} begenilmeyen / {un} begenilen "
              f"yanit analizi\n\n")
    with open(out_path, "a", encoding="utf-8") as f:
        f.write(header + analysis + "\n")
    print(f"\nYAZILDI: {out_path}")
    print("Bu bir ONERI - iyi olanlari elle aura_brain.py'ye ekleyip A/B "
          "dogrula (bkz. bu oturumun test->kural->dogrula dongusu).")


if __name__ == "__main__":
    main()
