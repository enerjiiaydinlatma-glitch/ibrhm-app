"""TikTok Display API (video.list / user.info) - sadece OKUMA, kendi hesabimiz icin.
Resmi Content Posting/paylasim API'si DEGIL - o tek-hesap kullanimi icin kapali (bkz. CLAUDE.md 2026-09-15).
Bu modul SADECE kendi onayladigimiz TikTok hesabinin video istatistiklerini (izlenme/begeni/yorum/paylasim)
okur - hicbir yayinlama/yorum/takip yetkisi yok, scope'lar user.info.basic/profile/stats + video.list.
"""
import json
import os
import time

import httpx

HERE = os.path.dirname(os.path.abspath(__file__))
CLIENT_FILE = os.path.join(HERE, "tiktok_client.json")
TOKEN_FILE = os.path.join(HERE, "tiktok_token.json")

AUTH_BASE = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
VIDEO_LIST_URL = "https://open.tiktokapis.com/v2/video/list/"
USER_INFO_URL = "https://open.tiktokapis.com/v2/user/info/"

SCOPES = "user.info.basic,user.info.profile,user.info.stats,video.list"

_pending_state = {"value": None}


def client_creds():
    try:
        d = json.load(open(CLIENT_FILE, encoding="utf-8"))
        return d.get("client_key", "").strip(), d.get("client_secret", "").strip()
    except Exception:
        return "", ""


def client_configured():
    k, s = client_creds()
    return bool(k and s)


def set_client_creds(client_key, client_secret):
    json.dump({"client_key": client_key.strip(), "client_secret": client_secret.strip()},
               open(CLIENT_FILE, "w", encoding="utf-8"))


def auth_url(redirect_uri):
    import secrets
    from urllib.parse import urlencode
    key, _ = client_creds()
    if not key:
        raise RuntimeError("TikTok client_key/secret henuz ayarlanmadi.")
    state = secrets.token_urlsafe(16)
    _pending_state["value"] = state
    q = urlencode({
        "client_key": key, "scope": SCOPES, "response_type": "code",
        "redirect_uri": redirect_uri, "state": state,
    })
    return f"{AUTH_BASE}?{q}"


def exchange_code(code, redirect_uri, state):
    if not _pending_state["value"] or state != _pending_state["value"]:
        raise RuntimeError("Gecersiz state (CSRF kontrolu basarisiz) - yetkilendirmeyi yeniden baslat.")
    _pending_state["value"] = None
    key, secret = client_creds()
    r = httpx.post(TOKEN_URL, data={
        "client_key": key, "client_secret": secret, "code": code,
        "grant_type": "authorization_code", "redirect_uri": redirect_uri,
    }, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=30)
    r.raise_for_status()
    d = r.json()
    if "access_token" not in d:
        raise RuntimeError(f"Token alinamadi: {d}")
    d["obtained_at"] = time.time()
    json.dump(d, open(TOKEN_FILE, "w", encoding="utf-8"), indent=1)
    return d


def _load_token():
    try:
        return json.load(open(TOKEN_FILE, encoding="utf-8"))
    except Exception:
        return None


def _refresh(tok):
    key, secret = client_creds()
    r = httpx.post(TOKEN_URL, data={
        "client_key": key, "client_secret": secret,
        "grant_type": "refresh_token", "refresh_token": tok["refresh_token"],
    }, headers={"Content-Type": "application/x-www-form-urlencoded"}, timeout=30)
    r.raise_for_status()
    d = r.json()
    if "access_token" not in d:
        raise RuntimeError(f"Token yenilenemedi: {d}")
    d["obtained_at"] = time.time()
    json.dump(d, open(TOKEN_FILE, "w", encoding="utf-8"), indent=1)
    return d


def access_token():
    tok = _load_token()
    if not tok:
        return None
    age = time.time() - tok.get("obtained_at", 0)
    if age > tok.get("expires_in", 0) - 120:  # 2 dk pay birak
        tok = _refresh(tok)
    return tok["access_token"]


def connected():
    return _load_token() is not None


def video_list(max_count=20):
    """Hesabin kendi videolarini (herkese acik) id/baslik/izlenme/begeni/yorum/paylasim ile doner."""
    at = access_token()
    if not at:
        raise RuntimeError("TikTok hesabi henuz baglanmadi.")
    r = httpx.post(
        f"{VIDEO_LIST_URL}?fields=id,title,view_count,like_count,comment_count,share_count,create_time",
        headers={"Authorization": f"Bearer {at}", "Content-Type": "application/json"},
        json={"max_count": max_count}, timeout=30)
    r.raise_for_status()
    d = r.json()
    if d.get("error", {}).get("code") not in (None, "ok"):
        raise RuntimeError(f"video.list hatasi: {d['error']}")
    return d.get("data", {}).get("videos", [])


def user_info():
    at = access_token()
    if not at:
        raise RuntimeError("TikTok hesabi henuz baglanmadi.")
    r = httpx.get(
        f"{USER_INFO_URL}?fields=display_name,follower_count,following_count,likes_count,video_count",
        headers={"Authorization": f"Bearer {at}"}, timeout=30)
    r.raise_for_status()
    d = r.json()
    if d.get("error", {}).get("code") not in (None, "ok"):
        raise RuntimeError(f"user.info hatasi: {d['error']}")
    return d.get("data", {}).get("user", {})
