"""Turkce altyazi (CC) onarimi: videolarda eksik Turkce parcalari yerel .srt dosyalarindan geri yukler.
Idempotenttir (var olani atlar), kota bitince durur ve sonraki calismada devam eder.
Bayrak dosyasi: _studio/pending_tr_restore.flag  (panelin arka plan dongusu saatte bir kontrol eder; tamamlaninca siler)
"""
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
FLAG = os.path.join(HERE, "pending_tr_restore.flag")
DONE = os.path.join(HERE, "tr_restore_done.json")


def _slug(t):
    return re.sub(r"[^a-z0-9]+", "", t.lower())[:24]


def plan():
    """[(gun, youtube_id, srt_yolu)] ve eslesemeyenler."""
    import insights
    st = insights.channel_stats()
    rows = json.load(open(os.path.join(HERE, "day_status.json"), encoding="utf-8"))
    items, missing = [], []
    for r in rows:
        if r["day"] < 12:
            continue
        norm = lambda s: re.sub(r"[^a-z0-9]+", "", s.lower())
        v = next((x for x in st["videos"] if norm(r["title"]) in norm(x["title"])), None)
        if not v:
            missing.append((r["day"], "video bulunamadi"))
            continue
        cands = [f"day{r['day']}_tr.srt", f"{_slug(r['title'])}_tr.srt", f"{_slug(v['title'])}_tr.srt"]
        srt = next((os.path.join(HERE, "output", c) for c in cands if os.path.exists(os.path.join(HERE, "output", c))), None)
        if not srt:
            missing.append((r["day"], "srt dosyasi yok"))
            continue
        items.append((r["day"], v["id"], srt))
    pend = os.path.join(HERE, "tr_pending.json")  # yayin aninda eklenemeyenler (kota/ag)
    if os.path.exists(pend):
        for vid, srt in json.load(open(pend, encoding="utf-8")).items():
            if os.path.exists(srt) and all(vid != i[1] for i in items):
                items.append((0, vid, srt))
    return items, missing


def restore():
    """Eksik Turkce parcalari yukler. Doner: {'restored':n,'skipped':n,'left':[gunler],'quota':bool,'missing':[...]}"""
    import publish_youtube_api as p
    from googleapiclient.errors import HttpError
    yt = p.get_authenticated_service()
    items, missing = plan()
    done = set(json.load(open(DONE)) if os.path.exists(DONE) else [])
    restored = skipped = 0
    left = []
    quota = False
    for day, vid, srt in items:
        if vid in done:
            skipped += 1
            continue
        if quota:
            left.append(day)
            continue
        try:
            have = [c for c in yt.captions().list(part="snippet", videoId=vid).execute()["items"] if c["snippet"]["language"].lower().startswith("tr")]
            if have:
                done.add(vid)
                skipped += 1
                continue
            media = __import__("googleapiclient.http", fromlist=["MediaFileUpload"]).MediaFileUpload(srt, mimetype="application/octet-stream")
            yt.captions().insert(part="snippet", body={"snippet": {"videoId": vid, "language": "tr", "name": "Türkçe", "isDraft": False}}, media_body=media).execute()
            done.add(vid)
            restored += 1
        except HttpError as e:
            txt = str(e)
            if "quotaExceeded" in txt or "quota" in txt.lower():
                quota = True
                left.append(day)
            elif "captionExists" in txt or e.resp.status == 409:
                done.add(vid)
                skipped += 1
            else:
                left.append(day)
        except Exception:
            left.append(day)
        json.dump(sorted(done), open(DONE, "w"))
        time.sleep(0.5)
    pend = os.path.join(HERE, "tr_pending.json")
    if os.path.exists(pend):  # tamamlananlari kuyruktan cikar
        try:
            pd_ = json.load(open(pend, encoding="utf-8"))
            pd_ = {k: v for k, v in pd_.items() if k not in done}
            json.dump(pd_, open(pend, "w", encoding="utf-8"), indent=1)
        except Exception:
            pass
    if not left and os.path.exists(FLAG):
        os.remove(FLAG)
    return {"restored": restored, "skipped": skipped, "left": left, "quota": quota, "missing": missing}


if __name__ == "__main__":
    print(json.dumps(restore(), ensure_ascii=False))
