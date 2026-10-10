"""YouTube analiz + yorum yardimcilari (resmi YouTube Data API; tarayici otomasyonu YOK).
aura_studio.py tarafindan cagrilir. Yorum GONDERME sadece operatorun tiklamasiyla olur."""
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

_svc = {"obj": None, "t": 0.0}
_cache = {"stats": None, "t": 0.0}


def _yt():
    # Servis nesnesi 30 dk'da bir yenilenir (token yenileme publish_youtube_api icinde).
    if not _svc["obj"] or time.time() - _svc["t"] > 1800:
        from publish_youtube_api import get_authenticated_service
        _svc["obj"] = get_authenticated_service()
        _svc["t"] = time.time()
    return _svc["obj"]


def channel_stats(force=False):
    """Kanal ozeti + son 50 videonun izlenme/begeni/yorum sayilari. 60 sn onbellek."""
    if not force and _cache["stats"] and time.time() - _cache["t"] < 60:
        return _cache["stats"]
    yt = _yt()
    ch = yt.channels().list(part="snippet,statistics,contentDetails", mine=True).execute()["items"][0]
    uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    ids = []
    token = None
    while len(ids) < 50:
        r = yt.playlistItems().list(part="contentDetails", playlistId=uploads, maxResults=50,
                                    pageToken=token).execute()
        ids += [i["contentDetails"]["videoId"] for i in r.get("items", [])]
        token = r.get("nextPageToken")
        if not token:
            break
    vids = []
    for i in range(0, len(ids), 50):
        r = yt.videos().list(part="snippet,statistics,status", id=",".join(ids[i:i + 50])).execute()
        for v in r.get("items", []):
            s = v.get("statistics", {})
            vids.append({
                "id": v["id"], "title": v["snippet"]["title"],
                "published": v["snippet"]["publishedAt"][:16].replace("T", " "),
                "views": int(s.get("viewCount", 0)), "likes": int(s.get("likeCount", 0)),
                "comments": int(s.get("commentCount", 0)), "description": v["snippet"].get("description", ""), "tags": v["snippet"].get("tags", []), "privacy": v["status"]["privacyStatus"],
            })
    vids.sort(key=lambda x: x["published"], reverse=True)
    cs = ch["statistics"]
    out = {"channel": ch["snippet"]["title"], "channel_id": ch["id"],
           "subscribers": int(cs.get("subscriberCount", 0)), "total_views": int(cs.get("viewCount", 0)),
           "video_count": int(cs.get("videoCount", 0)), "videos": vids,
           "fetched": time.strftime("%H:%M:%S")}
    _cache["stats"], _cache["t"] = out, time.time()
    try:
        snapshot_maybe(out)
    except Exception:
        pass
    return out


def list_comments(video_id, max_results=50):
    yt = _yt()
    mine = channel_stats()["channel_id"]
    r = yt.commentThreads().list(part="snippet,replies", videoId=video_id, order="time",
                                 maxResults=max_results, textFormat="plainText").execute()
    out = []
    for it in r.get("items", []):
        top = it["snippet"]["topLevelComment"]
        sn = top["snippet"]
        author_ch = (sn.get("authorChannelId") or {}).get("value", "")
        replied_by_me = any(
            ((rp["snippet"].get("authorChannelId") or {}).get("value", "") == mine)
            for rp in (it.get("replies") or {}).get("comments", []))
        out.append({"id": top["id"], "author": sn.get("authorDisplayName", "?"), "text": sn.get("textDisplay", ""),
                    "likes": sn.get("likeCount", 0), "mine": author_ch == mine,
                    "replied": replied_by_me, "replies": it["snippet"].get("totalReplyCount", 0)})
    return out


def post_reply(parent_id, text):
    text = (text or "").strip()
    if not text or len(text) > 1000:
        raise ValueError("Yanit bos veya cok uzun.")
    r = _yt().comments().insert(part="snippet", body={"snippet": {"parentId": parent_id, "textOriginal": text}}).execute()
    return r["id"]


def post_comment(video_id, text):
    text = (text or "").strip()
    if not text or len(text) > 1000:
        raise ValueError("Yorum bos veya cok uzun.")
    r = _yt().commentThreads().insert(part="snippet", body={"snippet": {
        "videoId": video_id, "topLevelComment": {"snippet": {"textOriginal": text}}}}).execute()
    return r["id"]


# ---- Sabit (pin) yorum takibi: YouTube API yorum SABITLEMEYI desteklemez; yorum API ile atilir,
# sabitleme operatorun tek dokunusuyla YouTube'da yapilir. Burada sadece "bekleyen sabitlemeler" tutulur.
import json

PINS_FILE = os.path.join(HERE, "pinned_comments.json")


def pins_load():
    try:
        return json.load(open(PINS_FILE, encoding="utf-8"))
    except Exception:
        return {}


def pins_add(video_id, title, comment_id, text):
    d = pins_load()
    d[comment_id] = {"video_id": video_id, "title": title, "text": text, "time": time.strftime("%Y-%m-%d %H:%M"),
                     "pinned": False,
                     "link": f"https://www.youtube.com/watch?v={video_id}&lc={comment_id}"}
    json.dump(d, open(PINS_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return d[comment_id]


def pins_done(comment_id):
    d = pins_load()
    if comment_id in d:
        d[comment_id]["pinned"] = True
        json.dump(d, open(PINS_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


# =====================================================================
# 2026-09-25: gunluk sayac kaydi (buyume egrisi), TikTok elle giris, YouTube Analytics (izlenme suresi/tutma)
# =====================================================================
SNAP_FILE = os.path.join(HERE, "snapshots.json")
TT_FILE = os.path.join(HERE, "tiktok_stats.json")
ANALYTICS_TOKEN = os.path.join(HERE, "token_analytics.json")
CLIENT_SECRET = os.path.join(HERE, "client_secret.json")
ANALYTICS_SCOPES = ["https://www.googleapis.com/auth/yt-analytics.readonly",
                    "https://www.googleapis.com/auth/youtube.readonly"]


def _jload(path, default):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return default


def snapshot_maybe(stats, min_hours=5):
    """Son kayittan >= min_hours gectiyse kanal + video sayilarini kaydeder (buyume egrisi icin)."""
    snaps = _jload(SNAP_FILE, [])
    now = time.time()
    if snaps and now - snaps[-1]["ts"] < min_hours * 3600:
        return False
    snaps.append({"ts": now, "at": time.strftime("%Y-%m-%d %H:%M"), "subs": stats["subscribers"],
                  "total_views": stats["total_views"],
                  "videos": {v["id"]: [v["views"], v["likes"], v["comments"]] for v in stats["videos"]}})
    json.dump(snaps[-400:], open(SNAP_FILE, "w", encoding="utf-8"))
    return True


def trend(stats):
    """Kayit serisi + her video icin son ~24 saatteki izlenme artisi."""
    snaps = _jload(SNAP_FILE, [])
    series = [{"at": s["at"], "subs": s["subs"], "total_views": s["total_views"]} for s in snaps]
    base = None
    now = time.time()
    for s in snaps:  # >=20 saat once olan EN YENI kayit; yoksa en eski
        if now - s["ts"] >= 20 * 3600:
            base = s
    if base is None and snaps:
        base = snaps[0]
    deltas = {}
    if base and base["ts"] < now - 600:
        for v in stats["videos"]:
            b = base["videos"].get(v["id"])
            deltas[v["id"]] = v["views"] - (b[0] if b else 0)
    return {"series": series, "deltas": deltas, "base_at": base["at"] if base else None,
            "base_age_h": round((now - base["ts"]) / 3600, 1) if base else None}


def tt_load():
    return _jload(TT_FILE, [])


def tt_add(video_id, title, views, likes, comments, shares):
    def num(x):
        x = int(x)
        if x < 0 or x > 1_000_000_000:
            raise ValueError("Gecersiz sayi.")
        return x
    rows = tt_load()
    rows.append({"date": time.strftime("%Y-%m-%d %H:%M"), "video_id": video_id, "title": title[:120],
                 "views": num(views), "likes": num(likes), "comments": num(comments), "shares": num(shares)})
    json.dump(rows[-2000:], open(TT_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return rows[-1]


def _norm_title(s):
    import re as _re
    return _re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def tiktok_sync(day_rows, tiktok_meta):
    """TikTok Display API'den (video.list) gercek video listesini ceker, bizim tiktok_meta.json'daki
    (gercekte TikTok'a yapistirilan) ACIKLAMA metniyle eslestirip tt_add ile kaydeder. day_rows:
    day_status.json listesi (day/title/youtube_id). tiktok_meta: _tiktok_meta_load() ciktisi
    {dosya_adi: {title, description}}. Eslesme day baslik -> meta description -> TikTok'un donen
    'title' (aslinda caption) alaninin normalize edilmis ilk ~50 karakteriyle yapilir - TikTok
    video.list'in kendi 'title' alani caption'in TAMAMI, YouTube basligi degil."""
    import tiktok_api
    if not tiktok_api.connected():
        return {"ok": False, "error": "TikTok baglanmamis."}
    videos = tiktok_api.video_list(20)  # TikTok video.list max_count ustu (ornegin 30) 400 veriyor
    meta_by_title = {m["title"]: m.get("description", "") for m in tiktok_meta.values() if m.get("title")}
    targets = []  # (youtube_id, normalized_description_prefix)
    for r in day_rows:
        yid = r.get("youtube_id")
        desc = meta_by_title.get(r.get("title", ""))
        if yid and desc:
            targets.append((yid, r["title"], _norm_title(desc)[:50]))
    matched, unmatched = [], []
    for v in videos:
        cap_norm = _norm_title(v.get("title", ""))[:70]
        hit = next(((yid, t) for yid, t, nd in targets if nd and nd in cap_norm), None)
        if hit:
            yid, t = hit
            tt_add(yid, t, v.get("view_count", 0), v.get("like_count", 0),
                   v.get("comment_count", 0), v.get("share_count", 0))
            matched.append(t)
        else:
            unmatched.append(v.get("title", "")[:60])
    return {"ok": True, "matched": len(matched), "matched_titles": matched, "unmatched": unmatched[:5],
            "total_tiktok_videos": len(videos)}


def tt_latest():
    """Video basina en son giris."""
    last = {}
    for r in tt_load():
        last[r["video_id"]] = r
    return last


# ---- YouTube Analytics (ayri token: token_analytics.json; ana yayin token'ina dokunmaz) ----
def analytics_creds():
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    if not os.path.exists(ANALYTICS_TOKEN):
        return None
    c = Credentials.from_authorized_user_file(ANALYTICS_TOKEN, ANALYTICS_SCOPES)
    if not c.valid:
        if c.expired and c.refresh_token:
            c.refresh(Request())
            open(ANALYTICS_TOKEN, "w", encoding="utf-8").write(c.to_json())
        else:
            return None
    return c


def analytics_status():
    try:
        return {"authorized": analytics_creds() is not None, "client_secret": os.path.exists(CLIENT_SECRET)}
    except Exception as e:
        return {"authorized": False, "client_secret": os.path.exists(CLIENT_SECRET), "error": str(e)[:200]}


def analytics_auth_flow():
    """PC'de tarayici acar; operator Google izin ekraninda KENDISI onaylar. Bu fonksiyon onay vermez."""
    from google_auth_oauthlib.flow import InstalledAppFlow
    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRET, ANALYTICS_SCOPES)
    c = flow.run_local_server(port=0, prompt="consent", authorization_prompt_message="")
    open(ANALYTICS_TOKEN, "w", encoding="utf-8").write(c.to_json())
    return True


def analytics_report(days=28):
    """Video basina: izlenme, izlenme suresi (dk), ort. izlenme suresi (sn), ort. izlenme yuzdesi, kazanilan abone."""
    from googleapiclient.discovery import build
    c = analytics_creds()
    if c is None:
        raise RuntimeError("Analytics yetkisi yok.")
    ya = build("youtubeAnalytics", "v2", credentials=c)
    end = time.strftime("%Y-%m-%d")
    start = time.strftime("%Y-%m-%d", time.localtime(time.time() - days * 86400))
    r = ya.reports().query(ids="channel==MINE", startDate=start, endDate=end,
                           metrics="views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained",
                           dimensions="video", sort="-views", maxResults=50).execute()
    rows = []
    for x in r.get("rows", []):
        rows.append({"video_id": x[0], "views": x[1], "minutes": x[2], "avg_sec": x[3], "avg_pct": round(x[4], 1), "subs": x[5]})
    return {"range": f"{start}..{end}", "rows": rows}


# ---- Retention (avg_pct) gecmisi: CTR/impressions YouTube Analytics API'de YOK (resmi API bu metrikleri
# disari vermiyor, sadece YouTube Studio arayuzunde var - bu bir platform kisitlamasi, kod hatasi degil).
# Elimizdeki en yakin gercek sinyal "ortalama izlenme yuzdesi" (retention) - onu gun gun kaydediyoruz.
ANALYTICS_SNAP_FILE = os.path.join(HERE, "analytics_snapshots.json")


def analytics_snapshot_once():
    """Bugun icin retention snapshot'i henuz alinmadiysa al ve ANALYTICS_SNAP_FILE'a ekle. Yetki yoksa/hata olursa sessizce gecer."""
    import json
    today = time.strftime("%Y-%m-%d")
    try:
        rows = json.load(open(ANALYTICS_SNAP_FILE, encoding="utf-8")) if os.path.exists(ANALYTICS_SNAP_FILE) else []
    except Exception:
        rows = []
    if rows and rows[-1].get("date") == today:
        return {"skipped": "bugun zaten alinmis"}
    try:
        rep = analytics_report()
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}
    rows.append({"date": today, "ts": time.time(), "rows": rep["rows"]})
    rows = rows[-120:]  # ~4 ay
    json.dump(rows, open(ANALYTICS_SNAP_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return {"ok": True, "date": today, "n": len(rep["rows"])}


def analytics_trend(video_id):
    """Bir video icin gun gun kaydedilmis avg_pct/views listesi (en eskiden en yeniye)."""
    import json
    try:
        rows = json.load(open(ANALYTICS_SNAP_FILE, encoding="utf-8"))
    except Exception:
        return []
    out = []
    for snap in rows:
        for r in snap.get("rows", []):
            if r["video_id"] == video_id:
                out.append({"date": snap["date"], "avg_pct": r["avg_pct"], "views": r["views"]})
    return out


if __name__ == "__main__":
    if "--auth-analytics" in sys.argv:
        analytics_auth_flow()
        print("Analytics yetkisi kaydedildi.")
