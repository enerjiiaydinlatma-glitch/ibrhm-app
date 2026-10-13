"""Bir gunun uretimini okunur rapora cevirir: NE secildi, NEDEN, hangi metin, kapi sonucu.
Kullanim:  python explain_run.py [YYYY-MM-DD]     (varsayilan: bugun)
Sadece okur (_engine/<tarih>/plan.json, run.json, .uploaded_today.json). Hicbir sey yuklemez/degistirmez.
"""
import datetime
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception as e:
        return {"_okunamadi": str(e)}


def show(title, value, indent=0, limit=1200):
    pad = " " * indent
    if value in (None, "", [], {}):
        return
    print(f"{pad}{title}:")
    if isinstance(value, (dict, list)):
        txt = json.dumps(value, ensure_ascii=False, indent=2)
    else:
        txt = str(value)
    if len(txt) > limit:
        txt = txt[:limit] + " ...(kisaltildi)"
    for line in txt.splitlines():
        print(f"{pad}  {line}")


def main(day):
    d = os.path.join(HERE, "_engine", day)
    if not os.path.isdir(d):
        print(f"{day}: uretim klasoru yok ({d}) - o gun motor calismamis.")
        return 1
    plan = load(os.path.join(d, "plan.json"))
    run = load(os.path.join(d, "run.json"))
    up = load(os.path.join(d, ".uploaded_today.json"))

    print(f"=== URETIM RAPORU {day} ===")
    if up:
        vids = up.get("videos") or [{"video_id": up.get("video_id"), "ts": up.get("ts")}]
        print(f"Yuklenen video sayisi: {len(vids)}")
        for v in vids:
            print(f"  https://youtu.be/{v.get('video_id')}  ({v.get('ts')})")
    else:
        print("Yukleme kaydi yok.")

    print("\n--- 1) AURA NE SECTI, NEDEN? (plan.json) ---")
    if not plan:
        print("plan.json yok.")
    else:
        show("Secilen konu (decision)", plan.get("decision"))
        show("Acilar (angles)", plan.get("angles"))
        for k, v in plan.items():
            if k not in ("decision", "angles", "studio_verdict", "studio_note"):
                show(k, v, limit=800)
        show("Studio degerlendirmesi", plan.get("studio_verdict"))
        show("Studio notu", plan.get("studio_note"))

    print("\n--- 2) URETILEN VIDEO (run.json) ---")
    if not run:
        print("run.json yok.")
    else:
        steps = run.get("steps", {}) if isinstance(run, dict) else {}
        short = run.get("short") or steps.get("short") or {}
        if isinstance(short, dict) and short:
            show("Baslik", short.get("title"))
            show("Metin / senaryo", short.get("script"), limit=2500)
            show("Aciklama", short.get("description"), limit=600)
            show("Etiketler", short.get("tags"))
            show("Sure (sn)", short.get("seconds"))
            show("DUYARLILIK KAPISI (sensitivity)", short.get("sensitivity"))
        else:
            show("run.json adimlari (ozet)", {k: (str(v)[:200]) for k, v in steps.items()})
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else datetime.date.today().isoformat()))
