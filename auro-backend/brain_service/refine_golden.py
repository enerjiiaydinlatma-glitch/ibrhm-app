"""Öz-eleştiri R&D motoru: senaryolardan cilalı "zirve Aura" örnekleri üretir.

Kullanıcının istedigi "kendi gelistirme ozelligi" - otomatik golden-set
buyutme. Her senaryo icin 3 gecis:
  1. TASLAK    - Gemini, Aura personasiyla yanit uretir
  2. ELESTIRI  - Gemini, o yaniti Aura rubrigine gore acimasizca elestirir
  3. NIHAI     - Gemini, elestiriyi uygulayarak yaniti yeniden yazar

Cikti: golden_set formatinda JSONL (provider="refined"). INSAN INCELEMESI
sart - iyi olanlari elle golden_set.jsonl'e tasi.

Kullanim:
    python refine_golden.py --in scenarios.jsonl --out refined_candidates.jsonl [--limit 20]

scenarios.jsonl bir satir = {"scenario": "...", "system": "...", "user": "..."}
(system kisa bir persona blogu; golden_set.jsonl'deki system alanlariyla ayni tarz)
"""
import argparse
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))


def gkey():
    v = (os.getenv("GEMINI_API_KEY") or "").strip()
    if v:
        return v
    for p in (os.path.join(HERE, "..", ".env"), os.path.join(HERE, ".env")):
        try:
            for line in open(p, encoding="utf-8"):
                if line.strip().startswith("GEMINI_API_KEY="):
                    return line.strip().split("=", 1)[1].strip()
        except OSError:
            pass
    sys.exit("GEMINI_API_KEY yok (.env veya ortam)")


AURA_RUBRIC = """Aura nasil konusur:
- Sicak, dogal, AKICI Turkce. Genel "yapay zeka asistani" tonundan UZAK.
- Gerektiginde kullaniciyi NAZIKCE ama NETCE yasama/harekete ceker (icine kapanmaya korukorune hak vermez).
- Sahte kesinlikten kacinir; bilmedigini soyler; sahte teselli ("her sey gecer", "guclu ol") YOK.
- Ozgunluk memnun etmekten onemli - gerektiginde nazikce katilmadigini soyler.
- Uzunluk soruya uyar. Somut tavsiyede TEK net ip, 5 maddelik liste degil.
- Her zor duyguda "uzmana danis" diye SAVUSTURMAZ (sadece gercek risk varsa, spesifik).
- Metin sohbetinde kullanicinin SESINE dair iddia YOK.
- Cok nadiren kisa carpici tek cumlelik gozlemle baslar - abartmadan."""


def _client(k):
    from google import genai
    from google.genai import types
    return genai.Client(api_key=k, http_options=types.HttpOptions(timeout=20000)), types


def gen(cl, types, prompt, temp=0.7):
    r = cl.models.generate_content(
        model="gemini-3.7-flash",
        contents=[types.Content(role="user", parts=[types.Part(text=prompt)])],
        config=types.GenerateContentConfig(temperature=temp),
    )
    return (r.text or "").strip()


def refine_one(cl, types, system, user):
    draft = gen(cl, types,
        f"{system}\n\nKullanici: {user}\n\nAura olarak yanitla (sadece yaniti yaz):", 0.7)

    critique = gen(cl, types,
        f"{AURA_RUBRIC}\n\nKULLANICI: {user}\nAURA'NIN TASLAK YANITI:\n{draft}\n\n"
        "Bu taslagi Aura rubrigine gore acimasizca elestir. Somut kusurlari madde madde "
        "yaz (ton, akicilik, yasam-lehine itiraz eksikligi, fazla uzunluk, klise, savusturma, "
        "sahte kesinlik...). Iyi yanlarini da 1 cumleyle belirt.", 0.3)

    final = gen(cl, types,
        f"{system}\n\nKULLANICI: {user}\n\nTASLAK:\n{draft}\n\nELESTIRI:\n{critique}\n\n"
        "Elestirideki her kusuru gidererek yaniti YENIDEN yaz. Aura'nin sesiyle, sicak ve "
        "akici Turkce. Sadece nihai yaniti yaz, aciklama ekleme.", 0.6)
    return draft, critique, final


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default=os.path.join(HERE, "scenarios.jsonl"))
    ap.add_argument("--out", default=os.path.join(HERE, "refined_candidates.jsonl"))
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    k = gkey()
    cl, types = _client(k)
    scen = [json.loads(l) for l in open(args.inp, encoding="utf-8") if l.strip()]
    if args.limit:
        scen = scen[: args.limit]
    print(f"{len(scen)} senaryo -> {args.out}\n")

    n = 0
    with open(args.out, "w", encoding="utf-8") as f:
        for s in scen:
            try:
                draft, crit, final = refine_one(cl, types, s["system"], s["user"])
            except Exception as e:
                print(f"  [{s.get('scenario','?')}] HATA: {type(e).__name__}: {e}")
                time.sleep(3)
                continue
            row = {
                "scenario": s.get("scenario", ""),
                "messages": [
                    {"role": "system", "content": s["system"]},
                    {"role": "user", "content": s["user"]},
                ],
                "reply": final,
                "provider": "refined",
                "_draft": draft,
                "_critique": crit,
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
            print(f"  [{s.get('scenario','?')}]  taslak {len(draft)} -> nihai {len(final)} krkt")
            time.sleep(1)

    print(f"\n{n} aday yazildi: {args.out}")
    print("INSAN INCELEMESI: _draft/_critique alanlarina bak, iyi olanlarin reply'sini")
    print("(bu iki alani cikararak) golden_set.jsonl'e tasi.")


if __name__ == "__main__":
    sys.exit(main())
