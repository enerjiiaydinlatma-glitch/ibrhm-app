"""Gunluk video siniri (kilit) - aura_engine.py kullanir.

Eskiden: .uploaded_today.json varsa ikinci calistirma atlanirdi (gunde 1).
Simdi: gunluk ust sinir MAX_DAILY (varsayilan 2). Sinira ulasinca yeni yukleme
YAPILMAZ - --force dahil (force sadece "bugun zaten 1 var" kontrolunu asar,
sert siniri asamaz). Sinir ortam degiskeniyle YUKSELTILEMEZ, sadece 1'e inebilir.

Dosya bicimi: {"video_id": son, "ts": son, "count": N, "videos": [{"video_id","ts"}...]}
Eski bicim ({"video_id","ts"}) 1 yukleme sayilir.
"""
import datetime
import json
import os

MAX_DAILY = 2  # SERT UST SINIR - degistirmeden once sensitivity_gate/PRIORITY ile birlikte gozden gecir


def _limit():
    try:
        v = int(os.environ.get("AURA_MAX_DAILY", MAX_DAILY))
    except ValueError:
        v = MAX_DAILY
    return max(1, min(v, MAX_DAILY))


def read_info(path):
    """Bugunun yukleme kaydi; yoksa/bozuksa count=0 (bozuk dosya 1 sayilir - guvenli taraf)."""
    if not os.path.exists(path):
        return {"count": 0, "videos": []}
    try:
        with open(path, encoding="utf-8") as f:
            info = json.load(f)
    except Exception:
        return {"count": 1, "videos": [], "video_id": "?", "ts": "?"}
    videos = info.get("videos")
    if not isinstance(videos, list) or not videos:
        videos = [{"video_id": info.get("video_id", "?"), "ts": info.get("ts", "?")}]
    info["videos"] = videos
    info["count"] = max(int(info.get("count", 0) or 0), len(videos))
    return info


def can_upload(path, force=False):
    """(izin, bilgi). Sert sinira ulasildiysa force olsa bile izin yok."""
    info = read_info(path)
    n = info["count"]
    if n >= MAX_DAILY:
        return False, info
    if n >= _limit() and not force:
        return False, info
    return True, info


def record_upload(path, video_id):
    info = read_info(path)
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    if any(v.get("video_id") == video_id for v in info["videos"]):
        return info  # ayni video iki kez sayilmaz
    videos = [v for v in info["videos"] if v.get("video_id") != "?"] + [{"video_id": video_id, "ts": ts}]
    out = {"video_id": video_id, "ts": ts, "count": len(videos), "videos": videos}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f)
    return out
