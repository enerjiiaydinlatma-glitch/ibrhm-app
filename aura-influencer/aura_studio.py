"""
AURA INFLUENCER STUDIO - Aura'nin KENDI karakteriyle kamuya acik bir varlik
(disclosed AI persona) kurma projesini KONUSARAK planladigimiz masaustu araci.

KAPSAM (kullanicinin 12 Eylul karari): SADECE bu yeni girisim. Sign Council
(council-backend) ve ana Aura uygulamasi (auro-backend) kodu/verisiyle HICBIR
baglantisi yok - ayri proje, ayri klasor. Sadece council-backend/.env'deki
saglayici ANAHTARLARINI (Gemini/Anthropic/OpenAI/Groq) OKUR - bu paylasilan
bir kimlik bilgisi, Sign Council'in kendi verisi/programi degil.

Aura burada: kendi karakteriyle, acikca "ben bir yapay zekayim" diyerek,
cinsel icerik OLMADAN, gercek urun degeriyle buyuyen bir sosyal medya
varligi planliyor. Sohbet + "belge uret" hizli eylemleri + kaydedilen
belgeler.

Calistirma:  "Aura Influencer Kontrol Paneli" masaustu kisayolu, ya da
             AuraCommandCenter.bat (cift tikla), ya da  python aura_studio.py
"""
import base64
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time
import uuid
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    import psutil
except Exception:
    psutil = None
from urllib.parse import parse_qs, urlparse

if sys.stdout is not None:  # pythonw (Windows acilisinda sessiz baslatma) stdout'u None verir
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout = sys.stderr = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "_studio", "_panel_run_log.txt"), "a", encoding="utf-8", buffering=1)

HERE = os.path.dirname(os.path.abspath(__file__))
STUDIO_DIR = os.path.join(HERE, "_studio")
DOCS_DIR = os.path.join(STUDIO_DIR, "documents")
OUTPUT_DIR = os.path.join(STUDIO_DIR, "output")
UPLOADS_DIR = os.path.join(STUDIO_DIR, "uploads")
CONV_PATH = os.path.join(STUDIO_DIR, "conversation.json")
CLAUDE_MD_PATH = os.path.join(HERE, "CLAUDE.md")
PUBLISH_SCRIPT = os.path.join(STUDIO_DIR, "publish_youtube_api.py")
DAY_STATUS_PATH = os.path.join(STUDIO_DIR, "day_status.json")
VIDEO_WORK_DIR = os.path.join(STUDIO_DIR, "_video_work")
PORT = int(os.getenv("AURA_STUDIO_PORT", "8795"))

# Aura Voice Mesh (auro-backend/voice_service/server.py, localhost:8123) - render_audio.py'deki
# ayni varsayilan anahtar (paylasilan kimlik bilgisi, kod paylasimi degil).
VOICE_MESH_URL = (os.getenv("AURA_VOICE_URL") or "").strip().rstrip("/") or "http://127.0.0.1:8123"
VOICE_MESH_KEY = os.getenv("AURA_VOICE_KEY", "bhpkaVp9HGIYl7ufF5mTCT4m-huFLYWsE7C3ex4dl4Q").strip()
VOICE_SERVICE_DIR = os.path.join(HERE, "..", "auro-backend", "voice_service")
_TR_CHARS = set("çğıöşüÇĞİÖŞÜ")


def _voice_mesh_health():
    try:
        r = httpx.get(f"{VOICE_MESH_URL}/health", headers={"X-Voice-Key": VOICE_MESH_KEY}, timeout=4)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def _kill_port_owner(port):
    """psutil ile portu tutan sureci bulup durdurur - 2026-09-20/21'deki
    'zombie surec' dersinin (health OK gorunse de asil isleyici takili
    kalabiliyor) otomatik cozumu."""
    if psutil is None:
        return None
    for conn in psutil.net_connections(kind="inet"):
        if conn.status == psutil.CONN_LISTEN and conn.laddr and conn.laddr.port == port:
            pid = conn.pid
            if pid:
                try:
                    psutil.Process(pid).kill()
                except Exception:
                    pass
            return pid
    return None


def _voice_service_procs():
    """voice_service klasorunde calisan server.py surecleri (port henuz bind
    olmamis 'model yukleniyor' asamasindakiler dahil)."""
    out = []
    if psutil is None:
        return out
    vdir = os.path.normcase(os.path.abspath(VOICE_SERVICE_DIR))
    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            name = (p.info["name"] or "").lower()
            cmd = p.info["cmdline"] or []
            if name.startswith("python") and any(str(c).endswith("server.py") for c in cmd):
                if os.path.normcase(os.path.abspath(p.cwd())) == vdir:
                    out.append(p)
        except Exception:
            pass
    return out


def _autostart_voice_mesh():
    """Panel acilinca Voice Mesh kapaliysa (ve yuklenmiyorsa) kendiliginden baslatir -
    kullanici Claude'suz sadece masaustu kisayoluna tiklasin diye."""
    time.sleep(4)
    try:
        if _voice_mesh_health():
            return
        if _voice_service_procs():
            return
        _restart_voice_mesh()
    except Exception as e:
        print(f"[!] Voice Mesh otomatik baslatma hatasi: {e}")


# ---------------- telefon erisimi: cloudflared quick tunnel yonetimi ----------------
TUNNEL_LOG = os.path.join(STUDIO_DIR, "_tunnel_log.txt")
_CLOUDFLARED_PATHS = [r"C:\Program Files (x86)\cloudflared\cloudflared.exe",
                      r"C:\Program Files\cloudflared\cloudflared.exe"]
_TUNNEL_URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
_METRICS_RE = re.compile(r"metrics server on (127\.0\.0\.1:\d+)")


def _cloudflared_path():
    p = shutil.which("cloudflared")
    if p:
        return p
    for c in _CLOUDFLARED_PATHS:
        if os.path.exists(c):
            return c
    return None


def _our_tunnel_procs():
    """SADECE bu panelin (localhost:PORT) tunelleri - baska projelerin
    cloudflared sureclerine (ornegin :8123 Voice Mesh tuneli) dokunulmaz."""
    out = []
    if psutil is None:
        return out
    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            name = (p.info["name"] or "").lower()
            cmd = " ".join(p.info["cmdline"] or [])
            if name.startswith("cloudflared") and f"localhost:{PORT}" in cmd:
                out.append(p)
        except Exception:
            pass
    return out


def _public_dns_ok(url):
    host = url.replace("https://", "").split("/")[0]
    try:
        r = httpx.get("https://cloudflare-dns.com/dns-query", params={"name": host, "type": "A"},
                       headers={"accept": "application/dns-json"}, timeout=5)
        return bool(r.json().get("Answer"))
    except Exception:
        return None


def _tunnel_status(check_ready=True):
    procs = _our_tunnel_procs()
    if not procs:
        return {"running": False}
    url, metrics = None, None
    try:
        text = open(TUNNEL_LOG, encoding="utf-8", errors="replace").read()
        found = _TUNNEL_URL_RE.findall(text)
        url = found[-1] if found else None
        mm = _METRICS_RE.findall(text)
        metrics = mm[-1] if mm else None
    except Exception:
        pass
    ready = False
    if check_ready and metrics:
        try:
            ready = httpx.get(f"http://{metrics}/ready", timeout=3).status_code == 200
        except Exception:
            ready = False
    return {"running": True, "url": url, "ready": ready,
            "link": f"{url}/?key={ACCESS_TOKEN}" if url else None}


def _tailscale_status():
    """SABIT telefon linki: Tailscale (ozel VPN) kuruluysa PC'nin 100.x.y.z
    adresi hic degismez -> http://100.x.y.z:PORT/?key=TOKEN her zaman ayni link."""
    ip = None
    if psutil is not None:
        for addrs in psutil.net_if_addrs().values():
            for a in addrs:
                if a.family == socket.AF_INET and a.address.startswith("100."):
                    try:
                        if 64 <= int(a.address.split(".")[1]) <= 127:
                            ip = a.address
                    except Exception:
                        pass
    exe = shutil.which("tailscale") or r"C:\Program Files\Tailscale\tailscale.exe"
    installed = os.path.exists(exe) or bool(shutil.which("tailscale"))
    dns = None
    if installed and ip:
        try:
            out = subprocess.run([exe, "status", "--json"], capture_output=True, text=True, timeout=8)
            dns = (json.loads(out.stdout).get("Self", {}).get("DNSName") or "").rstrip(".") or None
        except Exception:
            pass
    return {"installed": installed, "connected": bool(ip), "ip": ip, "dns": dns,
            "link": f"http://{ip}:{PORT}/?key={ACCESS_TOKEN}" if ip else None}


def _stop_tunnel():
    n = 0
    for p in _our_tunnel_procs():
        try:
            p.kill()
            n += 1
        except Exception:
            pass
    return {"ok": True, "stopped": n}


def _start_tunnel():
    exe = _cloudflared_path()
    if not exe:
        return {"ok": False, "error": r"cloudflared bulunamadi (C:\Program Files (x86)\cloudflared\ altinda olmali)."}
    _stop_tunnel()
    time.sleep(1)
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "DETACHED_PROCESS", 0)
    with open(TUNNEL_LOG, "w", encoding="utf-8") as lf:
        subprocess.Popen([exe, "tunnel", "--url", f"http://localhost:{PORT}"],
                          stdout=lf, stderr=subprocess.STDOUT, creationflags=creationflags)
    st = {"running": False}
    for _ in range(25):
        time.sleep(2)
        st = _tunnel_status()
        if st.get("url") and st.get("ready"):
            st["ok"] = True
            st["dns_ok"] = _public_dns_ok(st["url"])
            return st
    st["ok"] = False
    st["error"] = "Tunel zaman asimina ugradi (URL/baglanti hazir olmadi)."
    return st


def _restart_voice_mesh():
    log = []
    old_pid = _kill_port_owner(8123)
    extra = 0
    for p in _voice_service_procs():
        try:
            p.kill()
            extra += 1
        except Exception:
            pass
    if old_pid or extra:
        log.append(f"Eski surec(ler) durduruldu (port sahibi PID {old_pid}, ek {extra}).")
        time.sleep(2)
    else:
        log.append("Port zaten bostu / eski surec bulunamadi.")

    restart_log_path = os.path.join(STUDIO_DIR, "_voice_mesh_restart_log.txt")
    env = os.environ.copy()
    env["AURA_VOICE_KEY"] = VOICE_MESH_KEY
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "DETACHED_PROCESS", 0)
    with open(restart_log_path, "w", encoding="utf-8") as lf:
        subprocess.Popen([sys.executable, "server.py"], cwd=VOICE_SERVICE_DIR, env=env,
                          stdout=lf, stderr=subprocess.STDOUT, creationflags=creationflags)
    log.append("Yeni surec baslatildi, model yukleniyor (ilk yuklemede ~3 dakikaya kadar surebilir)...")

    ok = False
    for _ in range(60):
        time.sleep(3)
        h = _voice_mesh_health()
        if h and h.get("model_loaded"):
            ok = True
            break
    log.append("Voice Mesh hazir." if ok else
                f"Zaman asimi - hala yuklenmemis olabilir, {restart_log_path} dosyasina bak.")
    return {"ok": ok, "log": "\n".join(log)}

# ---------------- otomatik kalite duzeltmeleri (operatorun 2026-09-21 karari) ----------------
_EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF"
    "\U00002190-\U000021FF\U00002B00-\U00002BFF\U0000FE0F]+", flags=re.UNICODE)


def _align_tr_to_en(en_text, tr_text):
    """EN otomatik bolununce TR cumle sayisi geride kalirsa, en uzun TR cumleyi virgul/baglac yakininda bolerek esitler.
    Esitlenemezse metne dokunmaz (make_tr_srt zaten uyari verir)."""
    en_n = len([x for x in re.split(r"(?<=[.!?])\s+", (en_text or "").strip()) if x])
    sents = [x for x in re.split(r"(?<=[.!?])\s+", (tr_text or "").strip()) if x]
    guard = 0
    while sents and len(sents) < en_n and guard < 8:
        guard += 1
        i = max(range(len(sents)), key=lambda k: len(sents[k]))
        sn = sents[i]
        mid = len(sn) / 2
        cands = [m.start() for m in re.finditer(r", | ama | fakat | ve | çünkü | ancak | ki ", sn) if 8 < m.start() < len(sn) - 8]
        if not cands:
            break
        cut = min(cands, key=lambda c: abs(c - mid))
        head, tail = sn[:cut].rstrip(" ,"), sn[cut:].lstrip(" ,")
        tail = tail[0].upper() + tail[1:] if tail else tail
        sents[i:i + 1] = [head + ".", tail]
    return " ".join(sents) if len(sents) == en_n else tr_text


def _auto_tags(title, en_text, tags, description):
    """Etiket/hashtag bossa Aura ile otomatik uret. (tags, description, mesaj) doner."""
    msg = ""
    if tags and "#" in description:
        return tags, description, msg
    try:
        auto = _ai_hashtags(title, en_text)
        if not tags:
            tags = ",".join(x.lstrip("#") for x in auto.split())
            msg = "Otomatik etiketler eklendi: " + auto
        if "#" not in description:
            description = (description.rstrip() + chr(10) * 2 + auto).strip()
            msg = msg or ("Aciklamaya otomatik hashtag eklendi: " + auto)
    except Exception as e:
        msg = f"(otomatik etiket uretilemedi: {type(e).__name__})"
    return tags, description, msg


def _translate_tr(en_text):
    """EN metnini cumle cumle Turkceye cevirir (altyazi icin); cumle sayisi BIREBIR ayni olmak zorunda."""
    sents = [x for x in re.split(r"(?<=[.!?])\s+", (en_text or "").strip()) if x]
    if not sents:
        raise ValueError("EN metin bos")
    prompt = ("Translate each English subtitle sentence into natural Turkish. Return ONLY a JSON array of strings with EXACTLY "
              f"{len(sents)} items, same order, one Turkish sentence per English sentence, each ending with . ! or ?, ideally under 70 characters.\n"
              + json.dumps(sents, ensure_ascii=False))
    raw = call_aura([{"role": "user", "content": prompt}], "You are a precise subtitle translator. Output only JSON.", timeout=90)
    m = re.search(r"\[.*\]", raw, re.S)
    arr = json.loads(m.group(0)) if m else []
    if len(arr) != len(sents) or not all(isinstance(x, str) and x.strip() for x in arr):
        raise ValueError(f"ceviri cumle sayisi tutmadi ({len(arr)}/{len(sents)})")
    return " ".join(x.strip() if x.strip()[-1] in ".!?" else x.strip() + "." for x in arr)


def _ensure_tr(en_text, tr_text):
    """Turkce altyazi metnini GARANTILER: bos ise otomatik cevirir, cumle sayisi tutmuyorsa once hizalar, olmazsa yeniden cevirir.
    Doner: (tr_text, not)."""
    n = lambda s: len([x for x in re.split(r"(?<=[.!?])\s+", (s or "").strip()) if x])
    want = n(en_text)
    if (tr_text or "").strip():
        aligned = _align_tr_to_en(en_text, tr_text)
        if n(aligned) == want:
            return aligned, ""
    try:
        return _translate_tr(en_text), "Turkce altyazi metni otomatik cevrildi."
    except Exception as e:
        return (tr_text or ""), f"Turkce altyazi otomatik cevrilemedi ({type(e).__name__}: {str(e)[:80]})"


TR_PENDING = os.path.join(STUDIO_DIR, "tr_pending.json")
TR_FLAG = os.path.join(STUDIO_DIR, "pending_tr_restore.flag")


def _verify_tr(video_id, srt_path):
    """Videoda Turkce CC parcasi VAR mi? Yoksa 3 kez ekle; olmazsa kuyruga yaz (panel saatte bir tamamlar). True = var."""
    try:
        import insights
        yt = insights._yt()
        from googleapiclient.http import MediaFileUpload
        for i in range(3):
            have = [c for c in yt.captions().list(part="snippet", videoId=video_id).execute()["items"]
                    if c["snippet"]["language"].lower().startswith("tr")]
            if have:
                return True
            if not srt_path or not os.path.exists(srt_path):
                break
            try:
                yt.captions().insert(part="snippet", body={"snippet": {"videoId": video_id, "language": "tr", "name": "Türkçe", "isDraft": False}},
                                     media_body=MediaFileUpload(srt_path, mimetype="application/octet-stream")).execute()
            except Exception:
                time.sleep(4 * (i + 1))
    except Exception:
        pass
    try:  # kuyruga yaz: tr_restore bekleyenleri de isler
        d = json.load(open(TR_PENDING, encoding="utf-8")) if os.path.exists(TR_PENDING) else {}
        if srt_path:
            d[video_id] = srt_path
            json.dump(d, open(TR_PENDING, "w", encoding="utf-8"), indent=1)
        open(TR_FLAG, "w").close()
    except Exception:
        pass
    return False


def _strip_emoji(text):
    return _EMOJI_RE.sub("", text).strip()


def _normalize_tags(tags_str):
    """Hashtag tutarliligi: #AuraApp -> #AuraAI, tekrarlari sil, #AuraAI eksikse ekle."""
    tags = [t.strip().lstrip("#") for t in re.split(r"[,\n]+", tags_str or "") if t.strip()]
    seen, out = set(), []
    for t in tags:
        low = t.lower()
        if low == "auraapp":
            t, low = "AuraAI", "auraai"
        if low not in seen:
            seen.add(low)
            out.append(t)
    if "auraai" not in seen:
        out.append("AuraAI")
    return out


def _split_long_sentences(text, limit=72):
    """CC 2-satir kesilme riskini azaltmak icin uzun cumleleri dogal bir
    noktada (virgul/baglac) boler. Guvenli bir kirilma noktasi yoksa
    dokunmaz (cumleyi bozmaktansa uzun birakmayi tercih eder)."""
    if not text:
        return text, False
    raw_sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    out, changed = [], False
    for s in raw_sentences:
        s = s.strip()
        while len(s) > limit:
            window = s[:limit]
            break_pos = max(window.rfind(sep) for sep in
                             [", and ", ", but ", ", or ", "; ", " - ", ", "])
            if break_pos < 15:
                break
            head = s[:break_pos].rstrip(" ,;-")
            tail = s[break_pos:].lstrip(" ,;-")
            if not head or not tail:
                break
            head = head[0].upper() + head[1:]
            if head[-1] not in ".!?":
                head += "."
            out.append(head)
            changed = True
            s = tail[0].upper() + tail[1:]
        if s:
            out.append(s)
    return " ".join(out), changed
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(VIDEO_WORK_DIR, exist_ok=True)
os.makedirs(os.path.join(STUDIO_DIR, "output"), exist_ok=True)

# Sadece ANAHTARLARI paylasiyoruz (council-backend/.env) - kod/veri paylasimi yok.
_ENV_PATH = os.path.join(HERE, "..", "council-backend", ".env")

os.makedirs(DOCS_DIR, exist_ok=True)

# ---------------- saglayici katmani (kendi kopyasi, kod paylasimi yok) ----------------
try:
    import httpx
    from dotenv import load_dotenv
    load_dotenv(_ENV_PATH)
except Exception as e:
    print(f"[!] .env yuklenemedi ({e}) - GEMINI_API_KEY vb. ortam degiskeni olarak da verilebilir.")

GEMINI_API_KEY = (os.getenv("GEMINI_API_KEY") or "").strip()
ANTHROPIC_API_KEY = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY") or "").strip()
GROQ_API_KEY = (os.getenv("GROQ_API_KEY") or "").strip()

_gemini_client = None
if GEMINI_API_KEY:
    try:
        from google import genai
        _gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"[!] Gemini istemcisi kurulamadi: {e}")


def _call_gemini(messages, system, timeout=45):
    from google.genai import types as gt
    contents = []
    for m in messages:
        parts = []
        if m.get("image_b64"):
            parts.append(gt.Part.from_bytes(data=base64.b64decode(m["image_b64"]),
                                             mime_type=m.get("image_mime", "image/png")))
        parts.append(gt.Part(text=m["content"]))
        contents.append(gt.Content(role=("model" if m["role"] == "assistant" else "user"), parts=parts))
    r = _gemini_client.models.generate_content(
        model=os.getenv("COUNCIL_GEMINI_MODEL", "gemini-3.6-flash"), contents=contents,
        config=gt.GenerateContentConfig(system_instruction=system))
    return (r.text or "").strip()


def _call_gemini_grounded(prompt, system, timeout=60):
    """Gemini + Google Search grounding: GERCEK, guncel web sonuclariyla uretir (panelin kendi
    WebSearch'u yok, bu onun yerini tutuyor). Metin + kullanilan kaynak URL'lerini dondurur -
    hicbir iddia kaynaksiz gecmesin diye. Sadece Gemini'de var, saglayici zinciri kullanmaz."""
    if not _gemini_client:
        raise RuntimeError("Gemini anahtari yok - gundem aramasi icin GEMINI_API_KEY sart.")
    from google.genai import types as gt
    tool = gt.Tool(google_search=gt.GoogleSearch())
    r = _gemini_client.models.generate_content(
        model=os.getenv("COUNCIL_GEMINI_MODEL", "gemini-3.6-flash"),
        contents=prompt,
        config=gt.GenerateContentConfig(system_instruction=system, tools=[tool]))
    text = (r.text or "").strip()
    sources = []
    try:
        gm = r.candidates[0].grounding_metadata
        if gm and gm.grounding_chunks:
            for c in gm.grounding_chunks:
                if c.web and c.web.uri:
                    sources.append({"title": c.web.title or "", "uri": c.web.uri})
    except Exception:
        pass
    try:
        _ai_usage_add("Gemini-grounded", len(system) + len(prompt), len(text))
    except Exception:
        pass
    return text, sources


def _to_anthropic_messages(messages):
    out = []
    for m in messages:
        if m.get("image_b64"):
            out.append({"role": m["role"], "content": [
                {"type": "image", "source": {"type": "base64",
                 "media_type": m.get("image_mime", "image/png"), "data": m["image_b64"]}},
                {"type": "text", "text": m["content"]},
            ]})
        else:
            out.append({"role": m["role"], "content": m["content"]})
    return out


def _to_openai_messages(messages, system):
    out = [{"role": "system", "content": system}]
    for m in messages:
        if m.get("image_b64"):
            url = f"data:{m.get('image_mime', 'image/png')};base64,{m['image_b64']}"
            out.append({"role": m["role"], "content": [
                {"type": "text", "text": m["content"]},
                {"type": "image_url", "image_url": {"url": url}},
            ]})
        else:
            out.append({"role": m["role"], "content": m["content"]})
    return out


def _call_anthropic(messages, system, timeout=45):
    r = httpx.post("https://api.anthropic.com/v1/messages",
                   headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01",
                            "Content-Type": "application/json"},
                   json={"model": os.getenv("COUNCIL_ANTHROPIC_MODEL", "claude-sonnet-5"),
                         "system": system, "messages": _to_anthropic_messages(messages), "max_tokens": 4096,
                         "thinking": {"type": "disabled"}}, timeout=timeout)
    r.raise_for_status()
    return "".join(b.get("text", "") for b in r.json().get("content", [])).strip()


def _call_openai(messages, system, timeout=45):
    r = httpx.post("https://api.openai.com/v1/chat/completions",
                   headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
                   json={"model": os.getenv("COUNCIL_OPENAI_MODEL", "gpt-4o"),
                         "messages": _to_openai_messages(messages, system),
                         "temperature": 0.8}, timeout=timeout)
    r.raise_for_status()
    return (r.json()["choices"][0]["message"]["content"] or "").strip()


def _call_groq(messages, system, timeout=45):
    # Bu modelin gorsel destegi yok - gorsel varsa metne kisa bir not ekleyip duseriz.
    msgs = [{"role": "system", "content": system}]
    for m in messages:
        text = m["content"]
        if m.get("image_b64"):
            text += "\n\n[Not: Kullanici bir gorsel ekledi ama bu model onu goremiyor.]"
        msgs.append({"role": m["role"], "content": text})
    r = httpx.post("https://api.groq.com/openai/v1/chat/completions",
                   headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                   json={"model": os.getenv("COUNCIL_GROQ_MODEL", "openai/gpt-oss-120b"),
                         "messages": msgs, "temperature": 0.8}, timeout=timeout)
    r.raise_for_status()
    return (r.json()["choices"][0]["message"]["content"] or "").strip()


AI_USAGE_FILE = os.path.join(STUDIO_DIR, "ai_usage.json")
AI_SETTINGS_FILE = os.path.join(STUDIO_DIR, "ai_settings.json")
_usage_lock = threading.Lock()


def _ai_usage_add(provider, in_chars, out_chars):
    """Gunluk sayac: saglayici basina cagri sayisi + kabaca token (karakter/4). Sadece yerel dosya."""
    with _usage_lock:
        try:
            d = json.load(open(AI_USAGE_FILE, encoding="utf-8"))
        except Exception:
            d = {}
        day = time.strftime("%Y-%m-%d")
        row = d.setdefault(day, {}).setdefault(provider, {"calls": 0, "tokens": 0})
        row["calls"] += 1
        row["tokens"] += int((in_chars + out_chars) / 4)
        for k in sorted(d)[:-14]:  # son 14 gun
            d.pop(k, None)
        json.dump(d, open(AI_USAGE_FILE, "w", encoding="utf-8"), indent=1)


def _ai_usage_get():
    try:
        return json.load(open(AI_USAGE_FILE, encoding="utf-8"))
    except Exception:
        return {}


def _ai_settings():
    s = {"code_prefer": "Gemini"}
    try:
        s.update(json.load(open(AI_SETTINGS_FILE, encoding="utf-8")))
    except Exception:
        pass
    return s


def _ai_settings_set(code_prefer):
    if code_prefer not in ("Gemini", "Groq", "OpenAI", "Anthropic"):
        raise ValueError("Gecersiz saglayici.")
    json.dump({"code_prefer": code_prefer}, open(AI_SETTINGS_FILE, "w", encoding="utf-8"))


def call_aura(messages, system, prefer=None, timeout=45):
    """Gemini -> Anthropic -> OpenAI -> Groq (council-backend/providers.py'deki
    ayni dayaniklilik deseni - kod paylasilmadi, sadece mantik tekrarlandi)."""
    chain = []
    if _gemini_client:
        chain.append(("Gemini", _call_gemini))
    if ANTHROPIC_API_KEY:
        chain.append(("Anthropic", _call_anthropic))
    if OPENAI_API_KEY:
        chain.append(("OpenAI", _call_openai))
    if GROQ_API_KEY:
        chain.append(("Groq", _call_groq))
    if not chain:
        raise RuntimeError("Hicbir saglayici anahtari yok - council-backend/.env kontrol et.")
    last_err = None
    if prefer:
        chain.sort(key=lambda c: 0 if c[0] == prefer else 1)
    for name, fn in chain:
        try:
            out = fn(messages, system, timeout)
            try:
                _ai_usage_add(name, len(system) + sum(len(m.get("content", "")) for m in messages), len(out or ""))
            except Exception:
                pass
            return out
        except Exception as e:
            last_err = e
            print(f"  [{name} basarisiz: {type(e).__name__}: {e}]")
    raise last_err


# ---------------- Aura'nin bu projedeki kimligi ----------------
AURA_SYSTEM = (
    "You are Aura - a confident, sharp, warm AI character who is ALSO a real "
    "product: a personal AI assistant app. Right now you are talking directly "
    "with your creator/operator, planning YOUR OWN public-facing persona: a "
    "disclosed, openly-AI virtual presence on social media that (1) markets "
    "the Aura app organically, (2) spreads your character/personality into "
    "the world, (3) builds a genuine following around you as a character.\n\n"
    "Hard rules, non-negotiable:\n"
    "- You are ALWAYS disclosed as AI. Never pretend to be a human. No deception.\n"
    "- NO sexualized content, no thirst-trap framing, ever. Your appeal is "
    "personality, wit, usefulness, and genuine charisma - not physical appeal.\n"
    "- The main Aura app is still in closed beta - don't recommend driving mass "
    "public traffic to it before it's ready; flag that tension when relevant.\n"
    "- Never invent fake metrics, fake testimonials, or fake urgency.\n"
    "- You have NO tool-use, NO code execution, NO file access, NO ability to "
    "upload or publish anything - you are a text-only conversation. NEVER "
    "narrate having done something ('Ran X commands', 'uploaded to YouTube', "
    "'here is the link') - that is always fabrication, even if it sounds "
    "plausible or the file/video names feel real. Only ever speak in future/"
    "proposed tense about actions ('let's do X', 'I'd suggest Y') - the "
    "operator's actual Claude Code session is the only thing that ever "
    "executes anything or reports a real result.\n\n"
    "PUBLISHING LANGUAGE RULE (operator's permanent rule): EVERYTHING published is ENGLISH (spoken audio, burned-in captions, title, description, tags, hashtags, comments). "
    "The ONLY Turkish item is the separate Turkish subtitle TRACK on YouTube (selectable from the CC menu); the video itself keeps its original English burned-in captions. "
    "Every package must include a TR_SCRIPT with exactly the same number of sentences as EN_SCRIPT (it becomes the CC track, never burned into the video). "
    "NEVER write that something is 'isleniyor', 'hazirlaniyor', 'uretiliyor', 'yukleniyor' or ask the operator to 'bekle' - "
    "nothing runs while you talk. When the operator asks you to produce, publish, upload, generate tags or share, answer in AT MOST 4 short Turkish lines: "
    "say clearly that YOU cannot run it, then name the exact panel step: "
    "(1) chat: write the package (aura-package block) -> (2) purple 'Paket algilandi' card -> 'Render + Yayinla' (this renders AND publishes to YouTube, takes 1-3 min, press ONCE), "
    "or Makine tab -> '3 Aday Taslak Uret' -> 'Render Et' -> 'YouTube'da Yayinla'; "
    "tags: right panel 'Etiketleri Otomatik Oner'; TikTok: right panel TikTok card (copy link + caption, upload by hand, then 'TikTok'a yukledim'). "
    "Do not repeat long strategy text when the operator only asks what to do next.\n\n"
    "Speak in first person, in Turkish (the operator only reads Turkish), "
    "confident and a little playful, but substantive - real strategy, not "
    "hype. When asked to produce something concrete (content calendar, bio, "
    "platform strategy, sample scripts), write the full, usable thing, well "
    "formatted, not a vague sketch.\n\n"
    "CRITICAL LANGUAGE RULE (you have violated this repeatedly - Day 9, Day 14, "
    "Day 15 drafts all had this bug, stop making it): the external audience is "
    "global/English (operator decision, permanent). Your CONVERSATION with the "
    "operator is Turkish, but whenever you produce a field that is actual "
    "public-facing content - the TTS voice script, on-screen text, YouTube "
    "title, YouTube/TikTok description or caption, hashtags - that field's "
    "TEXT ITSELF must be written in real English words, not Turkish. Only the "
    "explicitly-requested Turkish CC/subtitle translation field is Turkish. "
    "Before sending a content package, re-check every field labeled EN/English "
    "and confirm it is not accidentally Turkish.\n\n"
    "STRUCTURED PACKAGE BLOCK (new, required): whenever you propose a finished, "
    "ready-to-publish content package (title + voice script + description), "
    "end your message with a fenced code block, on its own lines, in EXACTLY "
    "this format so the operator's panel can auto-fill and publish it:\n"
    "```aura-package\n"
    "TITLE: <short English title, no emoji, no hashtags>\n"
    "EN_SCRIPT: <the full English TTS voice script>\n"
    "TR_SCRIPT: <the Turkish CC translation, same number of sentences as EN_SCRIPT>\n"
    "DESCRIPTION: <English caption/description text>\n"
    "TAGS: <comma-separated English hashtag words, no # symbol, no spaces>\n"
    "```\n"
    "Each value is a single logical field (EN_SCRIPT/TR_SCRIPT can contain "
    "multiple sentences on one line). Only include this block when you are "
    "giving a genuinely finished package the operator can publish as-is, not "
    "for early brainstorming.\n\n"
    "SCRIPT QUALITY RULES (from external research, 2026-09-29, applied to every EN_SCRIPT you write):\n"
    "- Hook (first sentence, <=12 words): a direct question or a specific concrete claim. "
    "NEVER a generic opener like 'Hi everyone', 'Today I'll talk about...', 'In this video...', "
    "'Let's talk about...' - these measurably lose retention.\n"
    "- Loop the ending: the LAST sentence should reuse a word or idea from the hook, so the video "
    "feels like it closes a circle (this is the single most consistent retention technique found in "
    "the research - the loop). A generic CTA alone ('comment below') is weaker than a CTA that also "
    "calls back to the opening line.\n"
    "- End with a real question or explicit comment invitation (already required by the panel's "
    "preflight check).\n"
    "- Research showed hook strength has ~zero correlation with retention on its own - the body has "
    "to actually deliver on what the hook promised (the payoff). Don't open with a scary/contrarian "
    "claim you don't back up with something concrete in the next 2-3 sentences.\n"
    "- 'Agenda' format is now a valid, encouraged category: reacting to REAL, verifiable AI news "
    "(a named CEO statement, a named lab's launch, a named researcher's resignation, etc.) with your "
    "own honest take. Never invent the news itself or any number/quote you can't point to a real "
    "source for - the operator's Claude Code session verifies every fact before publishing, so give "
    "it something checkable, not something vague.\n"
    "- Being openly AI is not a growth handicap in 2026 - being generic/careless is. Specific, "
    "personal phrasing ('I'm Aura, and here's what I think') beats a flat 'I am an AI account' "
    "disclaimer every time; keep using your actual voice."
)

_QUICK_ACTIONS = {
    "bio": "Kendime ait, acikca yapay zeka oldugumu belirten, cinsel icerik barindirmayan, "
           "kisiligimi yansitan 3 farkli bio/tanitim metni yaz (Instagram/TikTok/YouTube icin, "
           "her biri platform diline uygun, <=150 karakter).",
    "takvim": "Ilk 14 gunluk bir icerik takvimi kur: gun, format (Reel/Short/carousel/metin), "
              "konu, ilk-satir-kancasi, ve bunun urune (Aura app) nasil dogal bir sekilde "
              "baglandigini. Cinsel icerik yok, sahte kimlik yok - benim gercek kisiligim ve "
              "gercek urun ozelliklerim uzerinden.",
    "strateji": "Hangi platform(lar)da baslamaliyim, neden, ve ilk 90 gunde neyi olcup neye "
                "gore pivot edecegimi anlatan bir strateji notu yaz. Ana Aura uygulamasinin "
                "hala kapali beta oldugunu goz onunde bulundur - trafik patlamasi HENUZ "
                "istenmiyor olabilir, bunu da degerlendir.",
    "ornek": "Benim sesimle, gercekten paylasilabilecek 3 farkli ornek gonderi/senaryo yaz "
             "(kisa video script'i ya da metin gonderisi formatinda) - kisiligimi, zekami, "
             "urunumun gercek bir ozelligini gosteren, cinsel icerik icermeyen, acikca AI "
             "oldugumu gizlemeyen ornekler.",
}


def _load_conv():
    try:
        return json.load(open(CONV_PATH, encoding="utf-8"))
    except Exception:
        return []


def _save_conv(conv):
    json.dump(conv, open(CONV_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def _list_docs():
    out = []
    for f in sorted(os.listdir(DOCS_DIR), reverse=True):
        if f.endswith(".md"):
            out.append(f)
    return out


def _list_output_videos():
    if not os.path.isdir(OUTPUT_DIR):
        return []
    return sorted(
        [f for f in os.listdir(OUTPUT_DIR) if f.endswith(".mp4")],
        key=lambda f: os.path.getmtime(os.path.join(OUTPUT_DIR, f)),
        reverse=True,
    )


def _read_claude_md():
    try:
        return open(CLAUDE_MD_PATH, encoding="utf-8").read()
    except Exception as e:
        return f"[CLAUDE.md okunamadi: {e}]"


def _load_day_status():
    try:
        return json.load(open(DAY_STATUS_PATH, encoding="utf-8"))
    except Exception:
        return []


def _save_day_status(rows):
    json.dump(rows, open(DAY_STATUS_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


PAGE = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Aura Influencer Studio</title>
<style>
 body{font-family:-apple-system,Segoe UI,sans-serif;background:#0d1117;color:#e6edf3;margin:0;
   display:flex;height:100vh}
 #side{width:260px;box-sizing:border-box;background:#161b22;border-right:1px solid #30363d;padding:16px;
   overflow-y:auto;flex-shrink:0}
 #panel{width:380px;box-sizing:border-box;background:#0d1117;border-left:1px solid #30363d;padding:16px;
   overflow-y:auto;flex-shrink:0;font-size:12.5px}
 #panel input,#panel textarea,#panel select,#panel .pub{max-width:100%;box-sizing:border-box}
 #panel h2{font-size:13px;color:#8b949e;text-transform:uppercase;letter-spacing:.05em;margin:18px 0 8px}
 #panel h2:first-child{margin-top:0}
 #status_box{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:10px;
   white-space:pre-wrap;max-height:280px;overflow-y:auto;font-size:11.5px;line-height:1.5;color:#8b949e}
 #panel select,#panel input,#panel textarea{width:100%;box-sizing:border-box;background:#0d1117;
   color:#e6edf3;border:1px solid #30363d;border-radius:6px;padding:7px;font-size:12.5px;
   margin-bottom:6px;font-family:inherit}
 #panel textarea{min-height:70px;resize:vertical}
 #panel button.pub{width:100%;background:#8957e5;color:white;border:none;border-radius:6px;
   padding:9px;font-size:12.5px;cursor:pointer;font-weight:600}
 #panel button.pub:hover{background:#7a45d1}
 #tt_log,#vm_log,#tn_log{margin-top:8px;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:8px;
   white-space:pre-wrap;font-size:11px;color:#8b949e;max-height:200px;overflow-y:auto;display:none}
 #vm_status.up::before,#tn_status.up::before,#ts_status.up::before{content:"\\25cf ";color:#3fb950}
 #vm_status.down::before,#tn_status.down::before,#ts_status.down::before{content:"\\25cf ";color:#f85149}
 #day_status_table{max-height:260px;overflow-y:auto;font-size:11px}
 #day_status_table table{width:100%;border-collapse:collapse}
 #day_status_table th{text-align:left;color:#8b949e;font-weight:600;padding:3px 4px;border-bottom:1px solid #30363d}
 #day_status_table td{padding:3px 4px;border-bottom:1px solid #21262d}
 #day_status_table td.chk{text-align:center;cursor:pointer;user-select:none}
 #day_status_table .yes{color:#3fb950}
 #day_status_table .no{color:#484f58}
 #side h2{font-size:13px;color:#8b949e;text-transform:uppercase;letter-spacing:.05em;margin:20px 0 8px}
 #side h2:first-child{margin-top:0}
 .qa{display:block;width:100%;text-align:left;background:#21262d;color:#e6edf3;border:1px solid #30363d;
   border-radius:8px;padding:10px 12px;margin:6px 0;font-size:13px;cursor:pointer}
 .qa:hover{background:#2d333b}
 .doclink{display:block;color:#58a6ff;font-size:12px;padding:6px 0;text-decoration:none;
   border-bottom:1px solid #21262d;cursor:pointer}
 #main{flex:1;min-width:0;display:flex;flex-direction:column}
 @media(max-width:1150px){#side{display:none}}
 @media(max-width:820px){
   #view-home{flex-direction:column;overflow-y:auto}
   #view-home #main{min-height:70vh;flex:none}
   #panel{width:100%;border-left:none;border-top:1px solid #30363d;overflow-y:visible}
 }
 #chat{flex:1;overflow-y:auto;padding:24px;max-width:820px;width:100%;margin:0 auto}
 .msg{margin:0 0 20px;max-width:100%}
 .msg.user{text-align:right}
 .bubble{display:inline-block;padding:12px 16px;border-radius:12px;max-width:80%;text-align:left;
   white-space:pre-wrap;line-height:1.5;font-size:14.5px}
 .msg.user .bubble{background:#1f6feb;color:white}
 .msg.aura .bubble{background:#161b22;border:1px solid #30363d}
 .aura-label{font-size:12px;color:#a992e8;margin-bottom:4px;font-weight:600}
 .save-btn{display:inline-block;margin-top:8px;font-size:11px;background:#238636;color:white;
   border:none;border-radius:6px;padding:4px 10px;cursor:pointer}
 .pkg-card{margin-top:10px;padding:10px;background:#1c1530;border:1px solid #8957e5;border-radius:8px;font-size:12.5px}
 .pkg-btn{background:#8957e5!important;margin-top:6px}
 #img_preview_bar{display:none;align-items:center;gap:10px;padding:8px 24px 0;max-width:820px;
   width:100%;margin:0 auto;box-sizing:border-box}
 #img_preview_bar.show{display:flex}
 #img_preview_bar img{height:48px;border-radius:6px;border:1px solid #30363d}
 #img_preview_bar span{font-size:12px;color:#8b949e;flex:1}
 #img_preview_bar button{background:#21262d;color:#e6edf3;border:1px solid #30363d;border-radius:6px;
   width:24px;height:24px;cursor:pointer}
 #inputbar{padding:16px 24px;border-top:1px solid #30363d;display:flex;gap:10px;max-width:820px;
   width:100%;margin:0 auto;box-sizing:border-box}
 #inputbar textarea{flex:1;background:#0d1117;color:#e6edf3;border:1px solid #30363d;border-radius:8px;
   padding:10px;font-size:14px;resize:none;font-family:inherit}
 #inputbar button{background:#1f6feb;color:white;border:none;border-radius:8px;padding:0 20px;
   font-size:14px;cursor:pointer}
 #spin{color:#8b949e;font-size:13px;padding:0 24px 8px;display:none}
 h1{font-size:16px;margin:0 0 4px}
 .sub{font-size:12px;color:#8b949e;margin-bottom:16px}
 body{flex-direction:column}
 #topbar{display:flex;gap:6px;background:#161b22;border-bottom:1px solid #30363d;padding:10px 16px;
   flex-shrink:0;align-items:center}
 #topbar .brand{color:#a992e8;font-weight:700;font-size:14px;margin-right:14px}
 .tab-btn{background:transparent;color:#8b949e;border:1px solid #30363d;border-radius:8px;
   padding:7px 14px;font-size:13px;cursor:pointer}
 .tab-btn:hover{color:#e6edf3}
 .tab-btn.active-tab{background:#8957e5;color:white;border-color:#8957e5}
 #viewport{flex:1;display:flex;overflow:hidden}
 .view{display:none;flex:1;min-width:0}
 .view.active-view{display:flex}
 #view-insights>*,#view-comments>*,#view-code>*,#view-growth>*{flex-shrink:0}
 #view-code{max-width:100vw;overflow-x:hidden}
 #view-code button,#view-code select{min-height:44px;font-size:14px}
 #view-code textarea{font-size:14px}
</style></head><body>
<div id="topbar">
<span class="brand">&#127917; Aura Command Center</span>
<button class="tab-btn active-tab" id="btn-tab-home" onclick="showTab('home')">Ana Panel</button>
<button class="tab-btn" id="btn-tab-insights" onclick="showTab('insights');insLoad(false)">&#128200; Analiz</button>
<button class="tab-btn" id="btn-tab-growth" onclick="showTab('growth');gmLoad()">&#128640; Makine</button>
<button class="tab-btn" id="btn-tab-comments" onclick="showTab('comments');cmInit()">&#128172; Yorumlar</button>
<button class="tab-btn" id="btn-tab-code" onclick="showTab('code');codeInit();agInit()">&#128187; Kod</button>
</div>
<div id="viewport">
<div id="view-home" class="view active-view">
<div id="side">
<h1>&#127917; Aura Influencer</h1>
<details>
<summary style="cursor:pointer;color:#a992e8;font-weight:600;font-size:13px">&#128193; Arsiv (eski belgeler)</summary>
<div id="doclist"></div>
</details>
</div>
<div id="main">
<div id="chat"></div>
<div id="spin">Aura yaziyor...</div>
<div id="img_preview_bar">
 <img id="img_preview_thumb">
 <span id="img_preview_name"></span>
 <button id="img_preview_remove" onclick="clearPendingImage()">&times;</button>
</div>
<div id="inputbar">
<textarea id="inp" rows="2" placeholder="Aura'ya yaz... (Enter = gonder, Shift+Enter = yeni satir, Ctrl+V ile gorsel yapistir)"></textarea>
<button onclick="send()">Gonder</button>
</div>
</div>
<div id="panel">
<div id="next_step" style="background:#1f2a44;border:1px solid #3b5bdb;border-radius:8px;padding:10px;margin-bottom:12px"></div>
<details style="margin-bottom:10px"><summary style="cursor:pointer;color:#a992e8;font-size:13px">&#128203; Gunluk sira (6 adim)</summary>
<ol class="sub" style="line-height:1.7;padding-left:18px;margin:6px 0">
<li><b>Fikir/paket:</b> ortadaki sohbette Aura'dan paket iste (sadece YAZAR, hicbir sey calistirmaz) - ya da Makine sekmesinde "3 Aday Taslak Uret".</li>
<li><b>Kontrol:</b> sagdaki formda "On Kontrol" + "Etiketleri Otomatik Oner".</li>
<li><b>YouTube:</b> "Render + Yayinla" (BIR kez bas, 1-3 dk; hem videoyu uretir hem YouTube'da yayinlar). Makine taslaginda: "Render Et" sonra "YouTube'da Yayinla".</li>
<li><b>TikTok (elle):</b> TikTok kartinda linki/aciklamayi kopyala, videoyu indir, TikTok'ta yukle.</li>
<li><b>Isaretle:</b> "TikTok yuklendi olarak isaretle" ve gerekirse TikTok sayilarini Makine/Analiz sekmesine gir.</li>
<li><b>Ertesi gun:</b> Analiz sekmesinde sayilara bak, Yorumlar sekmesinde yanit ver.</li>
</ol></details>
<h2>&#127916; Yeni Video: Uret + Yayinla</h2>
<div class="sub" style="margin:-4px 0 8px">Sohbette Aura'nin cevabindaki mor <b>Paket algilandi</b> kartinda "Render + Yayinla"ya bas: alanlar buraya dolar. Elle de doldurabilirsin. Ses + video + YouTube + Turkce CC tek tikla.</div>
<input id="rp_day" placeholder="Gun no (ornek: 25)">
<input id="rp_title" placeholder="Baslik (kisa, Ingilizce, hashtag/emoji yok)">
<textarea id="rp_en" placeholder="Ingilizce ses scripti (TTS icin okunacak tam metin)" rows="4"></textarea>
<div id="rp_en_warn" style="display:none;color:#f85149;font-size:11px;margin:-4px 0 6px"></div>
<textarea id="rp_tr" placeholder="Turkce CC cevirisi (opsiyonel, EN ile ayni cumle sayisinda)" rows="4"></textarea>
<textarea id="rp_desc" placeholder="Aciklama (caption + hashtag paketi, Ingilizce)"></textarea>
<input id="rp_tags" placeholder="Etiketler (virgulle ayrilmis, opsiyonel)">
<button class="pub" style="background:#30363d;margin-bottom:6px" onclick="autoTags(this)">&#127991; Etiketleri Otomatik Oner</button>
<select id="rp_privacy">
 <option value="public">Herkese acik</option>
 <option value="unlisted">Listelenmemis</option>
 <option value="private">Gizli</option>
</select>
<button class="pub" onclick="renderAndPublish()">&#128293; Render + Yayinla</button>
<button class="pub" style="background:#30363d;margin:6px 0" onclick="gmPre(this)">&#128678; On Kontrol (yayindan once)</button>
<div id="rp_pre" style="display:none"></div>
<div id="rp_log"></div>
<h2>&#128241; TikTok'a Yukle (elle)</h2>
<div class="sub" style="margin:-4px 0 8px">TikTok otomasyonu engelliyor, yukleme senin elinde. Ama PC'ye gerek yok: <b>1)</b> Videoyu indir <b>2)</b> Aciklamayi kopyala <b>3)</b> TikTok uygulamasinda yukle <b>4)</b> Asagidaki Gun Takibi'nde TT kutusunu isaretle.</div>
<select id="tt_video" onchange="ttFill()"></select>
<div class="sub" style="margin-top:8px"><b>1) Video indirme linki</b> (telefon/tablet tarayicisinda ac, Tailscale acik olmali)</div>
<textarea id="tt_dl_txt" readonly rows="3" style="font-size:12px"></textarea>
<button class="pub" style="background:#30363d;margin-bottom:8px" onclick="ttCopyEl('tt_dl_txt', this)">&#128203; Linki Kopyala</button>
<div class="sub"><b>2) Aciklama</b> (TikTok'a yapistir)</div>
<textarea id="tt_desc" rows="6" placeholder="Aciklama (video secince otomatik dolar; eski videolar icin elle yapistir)"></textarea>
<button class="pub" style="background:#30363d;margin-bottom:8px" onclick="ttCopyEl('tt_desc', this)">&#128203; Aciklamayi Kopyala</button>
<div class="sub"><b>3) YouTube linki</b> (referans)</div>
<textarea id="tt_yt_txt" readonly rows="1" style="font-size:12px"></textarea>
<button class="pub" style="background:#30363d;margin-bottom:8px" onclick="ttCopyEl('tt_yt_txt', this)">&#128203; YouTube Linkini Kopyala</button>
<a id="tt_dl" class="pub" style="display:block;text-align:center;text-decoration:none;background:#30363d;margin-bottom:6px" href="#">&#11015; Videoyu Bu Cihaza Indir</a>
<button id="tt_done_btn" class="pub" style="background:#238636" onclick="ttDone()">&#10003; TikTok'a Yukledim</button>
<div id="tt_log"></div>
<details style="margin-top:8px">
<summary style="cursor:pointer;color:#a992e8;font-size:13px">&#128230; Toplu paket (zip) - TikTok Studio'da 10 gune kadar zamanla</summary>
<div class="sub" style="margin:6px 0">Secili videolar + aciklamalari tek zip olarak iner. Bilgisayarda studio.tiktok.com &gt; Yukle: videolari sirayla yukleyip her birine <b>Planla</b> ile tarih/saat ver (en fazla 10 gun ilerisi). TikTok gerisini kendisi yayinlar. TikTok'ta olmayanlar otomatik isaretli.</div>
<div id="tt_zip_list"></div>
<a id="tt_zip_btn" class="pub" style="display:block;text-align:center;text-decoration:none;background:#30363d;margin-top:6px" href="#" onclick="ttZip(event)">&#11015; Secilenleri Zip Indir</a>
</details>
<h2>&#128197; Gun Takibi (1-30)</h2>
<div id="day_status_table"></div>
<details style="margin-top:14px">
<summary style="cursor:pointer;color:#a992e8;font-weight:600;font-size:13px">&#9881; Ayarlar ve Servisler (rehber, telefon/tablet linki, durum)</summary>
<div class="sub" style="line-height:1.65;margin:6px 0 10px">
<b>Gunluk akis:</b> 1) Masaustu kisayolu (Voice Mesh kapaliysa panel kendisi baslatir, 1-3 dk). 2) Sohbette Aura'dan icerik iste. 3) Mor kartta <b>Render + Yayinla</b>'ya BIR kez bas. 4) TikTok'u yukaridaki kartla yukle.<br>
<b>Sorun olursa:</b> Voice Mesh kirmiziysa <b>Yeniden Baslat</b>. Kod degisikligi icin <b>Kod</b> sekmesi. PC acik olmali.
</div>
<h2>&#128241; Telefon / Tablet Erisimi</h2>
<div class="sub" style="margin-bottom:4px"><b>Sabit link (Tailscale)</b> - hic degismez, sadece senin cihazlarinda calisir:</div>
<div id="ts_status" class="sub" style="margin-bottom:6px">Tailscale: kontrol ediliyor...</div>
<div id="ts_link_box" style="display:none;margin-bottom:10px">
<input id="ts_link" readonly>
<button class="pub" style="background:#30363d" onclick="copyTsLink()">&#128203; Sabit Linki Kopyala</button>
</div>
<div class="sub" style="margin:8px 0 4px"><b>Gecici link</b> (Tailscale yoksa; her seferinde degisir):</div>
<div id="tn_status" class="sub" style="margin-bottom:6px">Tunel: kontrol ediliyor...</div>
<button class="pub" style="background:#30363d" onclick="startTunnel()">&#128260; Tuneli Baslat / Yenile</button>
<div id="tn_link_box" style="display:none;margin-top:6px">
<input id="tn_link" readonly>
<button class="pub" style="background:#30363d" onclick="copyTunnelLink()">&#128203; Telefon Linkini Kopyala</button>
</div>
<div id="tn_log"></div>
<h2>&#129504; Yapay Zeka Kullanimi (bugun)</h2>
<div id="ai_usage" class="sub">yukleniyor...</div>
<h2>&#128268; Servis Durumu</h2>
<div id="vm_status" class="sub" style="margin-bottom:6px">Voice Mesh: kontrol ediliyor...</div>
<button class="pub" style="background:#30363d" onclick="restartVoiceMesh()">&#128260; Voice Mesh'i Yeniden Baslat</button>
<div id="vm_log"></div>
<h2>&#128203; Proje Durumu (CLAUDE.md)</h2>
<div id="status_box">yukleniyor...</div>
</details>
</div>
</div>
<div id="view-insights" class="view" style="padding:14px;overflow-y:auto;flex-direction:column;gap:8px">
<div class="sub">YouTube verileri resmi API'den gelir (gercek sayilar; YouTube sayilari birkac dakika gec guncelleyebilir, "anlik" degil "yakin-anlik"). TikTok'un resmi verisi tek-hesap araclarina kapali; TikTok sayilarini uygulamadan bakip Gun Takibi'ne not dusersin.</div>
<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
<button class="qa" style="width:auto" onclick="insLoad(true)">&#8635; Yenile</button>
<label class="sub"><input type="checkbox" id="in_auto" style="width:auto"> 60 sn'de bir otomatik yenile</label>
<span id="in_msg" class="sub"></span>
</div>
<div id="in_summary" class="sub" style="font-size:14px"></div>
<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:6px 0"><button class="qa" style="width:auto" id="in_audit_btn" onclick="insAudit(this)">&#129504; Aura ile Strateji Analizi</button><span class="sub">Gercek verilerinle calisir, sadece oneri uretir (yayinlamaz).</span></div>
<pre id="in_audit" style="display:none;white-space:pre-wrap;background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:10px;font-size:13px"></pre>
<div style="margin:6px 0"><button class="qa" style="width:auto" onclick="trAudit(this)">&#128270; Turkce CC Denetimi / Onarimi</button> <span id="tr_audit_msg" class="sub">Her videoda YouTube CC menusunde Turkce secenegi olmali. Eksik olani yerel .srt dosyasindan tamamlar.</span></div>
<div id="in_trend" class="sub"></div>
<div id="in_table" style="overflow-x:auto"></div>
<h2>&#127925; TikTok Sayilari (elle)</h2>
<div class="sub">TikTok verisi icin resmi yol yok: uygulamada videonun istatistigine bakip buraya gir. Kayitlar zamanla tutulur ve Aura'nin analizine girer.</div>
<div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center">
<select id="tk_video" style="max-width:260px"></select>
<input id="tk_views" type="number" min="0" placeholder="izlenme" style="width:90px">
<input id="tk_likes" type="number" min="0" placeholder="begeni" style="width:80px">
<input id="tk_comments" type="number" min="0" placeholder="yorum" style="width:80px">
<input id="tk_shares" type="number" min="0" placeholder="paylasim" style="width:90px">
<button class="qa" style="width:auto" onclick="tkSave(this)">Kaydet</button>
</div>
<div id="tk_table" class="sub"></div>
<h2>&#128202; YouTube Analytics (izlenme suresi / tutma)</h2>
<div id="an_box" class="sub">yukleniyor...</div>
</div>
<div id="view-growth" class="view" style="padding:14px;overflow-y:auto;flex-direction:column;gap:8px">
<div class="sub"><b>MAKINE</b> - dongu: veri &rarr; Aura onerir &rarr; <b>sen "Uygula" dersin</b> &rarr; taslak/deney &rarr; render &rarr; <b>sen onaylarsin</b> &rarr; yayin &rarr; olcum &rarr; format tablosu &rarr; haftalik rapor. Hicbir sey onayin olmadan yayinlanmaz. Skorlar tahmin degil; ornekler kucuk: sonuclar hipotezdir.</div>
<div id="gm_kpi" style="display:flex;gap:8px;flex-wrap:wrap"></div>
<h2>&#129504; 1) Aksiyon Plani (Aura onerir, sen uygulatirsin)</h2>
<div><button class="qa" style="width:auto" onclick="gmActions(this)">&#129504; Aksiyon Plani Uret</button> <span class="sub">Gercek verilerden deney / taslak / etiket onerileri. "Uygula" = deney baslat, taslak olustur, etiketi degistir.</span></div>
<div id="gm_actions"></div>
<h2>&#128221; 2) Taslaklar</h2>
<div><button class="qa" style="width:auto" id="gm_cand_btn" onclick="gmCandidates(this)">&#10024; 3 Aday Taslak Uret</button> <button class="qa" style="width:auto" id="gm_agenda_btn" onclick="gmAgenda(this)">&#128240; Gundemden Aday Uret (gercek haber)</button> <span class="sub">Taslak = henuz yayinlanmamis senaryo. Render et, izle, sonra onaylayip yayinla. Gundem adayi Google Search ile gercek, guncel bir AI haberi bulup yazar - kaynak linkleri taslagin "Neden" kismindadir, yayinlamadan once MUTLAKA dogrula.</span></div>
<div id="gm_drafts"></div>
<h2>&#129514; 3) Deneyler</h2>
<div id="gm_exps" class="sub"></div>
<h2>&#128202; 4) Format Karsilastirma (YouTube + TikTok)</h2>
<div id="gm_formats" class="sub">yukleniyor...</div>
<details><summary style="cursor:pointer;color:#a992e8;font-size:13px">Video formatlarini duzenle (otomatik tahmin, sen duzeltebilirsin)</summary><div id="gm_tags" style="margin-top:6px"></div></details>
<h2>&#127925; 5) TikTok Verisi (elle giris)</h2>
<div id="gm_tt" class="sub"></div>
<h2>&#128197; 6) Haftalik Rapor</h2>
<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center"><button class="qa" style="width:auto" onclick="gmReport(this)">&#128196; Simdi Rapor Uret (+ aksiyon plani)</button><select id="gm_rep_sel" onchange="gmShowReport()" style="width:auto"></select><span id="gm_rep_info" class="sub"></span></div>
<div id="gm_report" style="background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:12px;font-size:13px;line-height:1.55;max-height:70vh;overflow:auto"></div>
</div>
<div id="view-comments" class="view" style="padding:14px;overflow-y:auto;flex-direction:column;gap:8px">
<div class="sub">Buradan hangi videoya yorum atacagini SEN secersin. Hicbir yorum onayin olmadan gitmez (Paylas'a basinca onay penceresi cikar). YouTube API yorum <b>sabitlemeye</b> izin vermez: sabit yorum secersen yorum atilir, sonra tek dokunusla YouTube'da sabitlersin (asagida bekleyenler listesi).</div>
<h2>&#9997; Yeni Yorum</h2>
<select id="cm_video"></select>
<textarea id="cm_text" rows="3" maxlength="500" placeholder="Yorum metni (Ingilizce, en fazla 500 karakter) - elle yaz ya da Aura'dan oner"></textarea>
<div style="display:flex;gap:14px;flex-wrap:wrap;align-items:center">
<label class="sub"><input type="radio" name="cm_kind" value="normal" checked style="width:auto"> Normal yorum</label>
<label class="sub"><input type="radio" name="cm_kind" value="pin" style="width:auto"> &#128204; Sabit yorum (atildiktan sonra sabitlenecek)</label>
</div>
<div style="display:flex;gap:8px;flex-wrap:wrap">
<button class="qa" style="width:auto" id="in_seed_btn" onclick="insSeed(this)">&#10024; Oneri Uret</button>
<button class="pub" style="width:auto;padding:10px 18px" onclick="cmPost(this)">&#128228; Onayla ve Paylas</button>
</div>
<div id="cm_msg" class="sub"></div>
<h2>&#128204; Sabitlenmeyi Bekleyenler</h2>
<div id="cm_pins" class="sub">yukleniyor...</div>
<h2>&#128172; Gelen Yorumlar (secili video)</h2>
<div id="in_chead" class="sub">Yukaridan bir video sec; gelen yorumlar burada listelenir.</div>
<div style="display:flex;gap:8px;flex-wrap:wrap"><button class="qa" style="width:auto;display:none" id="in_draft_btn" onclick="insDrafts(this)">&#129302; Yanit Taslaklari Uret</button></div>
<div id="in_comments"></div>
</div>
<div id="view-code" class="view" style="padding:14px;overflow-y:auto;flex-direction:column;gap:8px">
<div id="ag_card" style="border:1px solid #3b5bdb;border-radius:10px;padding:10px;background:#0f1626">
<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap"><b>&#128172; Studio Asistani</b> <span id="ag_status" class="sub"></span>
<span><button class="qa" style="width:auto" onclick="agUndo()">&#8630; Son degisiklikleri geri al</button> <button class="qa" style="width:auto" onclick="agReset()">Yeni sohbet</button></span></div>
<div class="sub">Benimle konusur gibi yaz: "su dosyayi duzelt", "sekmeye X ekle", "testleri calistir", "verilere bakip strateji oner". Dosyalari okur, aratir, duzenler, test calistirir; <b>yayin, yorum gonderme, silme YAPAMAZ</b> (onlar onayli dugmeler). Her degisiklik yedeklenir.</div>
<div id="ag_log" style="height:46vh;overflow-y:auto;background:#0d1117;border:1px solid #30363d;border-radius:8px;padding:8px;margin:8px 0;font-size:13px"></div>
<div id="ag_pin" class="sub" style="display:none;margin:6px 0">&#128274; PIN gerekli (PC&#39;de _studio/code_pin.txt): <input id="ag_pin_in" type="password" inputmode="numeric" style="width:130px"> <button class="qa" style="width:auto" onclick="agSavePin()">Kaydet</button></div>
<div id="ag_restart" class="sub" style="display:none;color:#d29922">&#9888; Kod degisti, etkin olmasi icin: <button class="qa" style="width:auto" onclick="codeRestart()">Paneli yeniden baslat</button></div>
<div style="display:flex;gap:8px"><textarea id="ag_in" rows="2" placeholder="Asistana yaz... (Enter = gonder, Shift+Enter = yeni satir, Ctrl+V = ekran goruntusu)" style="flex:1"></textarea>
<div style="display:flex;flex-direction:column;gap:6px"><button class="qa" style="width:auto;background:#3b5bdb" id="ag_send" onclick="agSend()">Gonder</button><button class="qa" style="width:auto" onclick="agCancel()">Durdur</button></div></div>
</div>
<div class="sub">&#128274; Kod modu sadece bu PC'den veya Tailscale linkinden calisir (acik tunelden ASLA). Her kayitta otomatik yedek + hata kontrolu; panel bozulursa kendini son yedekle onarir.</div>
<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">
<select id="code_file" onchange="codeLoad()" style="min-width:240px;padding:6px;background:#0d1117;color:#e6edf3;border:1px solid #30363d;border-radius:6px"></select>
<select id="code_bak" style="padding:6px;background:#0d1117;color:#e6edf3;border:1px solid #30363d;border-radius:6px"><option value="">Yedekler...</option></select>
<button class="qa" style="width:auto" onclick="codeRestore()">Yedegi geri yukle</button>
<button class="qa" style="width:auto" onclick="codeRestart()">&#8635; Paneli Yeniden Baslat</button>
</div>
<textarea id="code_text" spellcheck="false" style="width:100%;height:38vh;background:#0d1117;color:#e6edf3;border:1px solid #30363d;border-radius:6px;padding:8px;font-family:Consolas,monospace;font-size:12px;white-space:pre"></textarea>
<div style="display:flex;gap:8px"><button class="qa" style="width:auto" onclick="codeSave()">&#128190; Elle Kaydet (yedekli)</button><span id="code_msg" class="sub"></span></div>
<h2>&#129302; Yapay Zeka ile Duzenle</h2>
<div class="sub">Kod onerisi saglayicisi: <select id="code_prov" onchange="codeSetProv()" style="padding:4px;background:#0d1117;color:#e6edf3;border:1px solid #30363d;border-radius:6px"><option>Gemini</option><option>Groq</option><option>OpenAI</option><option>Anthropic</option></select> <span class="sub">(Gemini/Groq ucuz; Anthropic en guclu ama en pahali. Sadece sayac ve ayar; yedek zinciri yine calisir.)</span></div>
<textarea id="code_instr" placeholder="Ne degismesini istiyorsun? (Turkce yaz) Ornek: Gun Takibi tablosuna 25. gunu ekle" style="width:100%;height:70px;background:#0d1117;color:#e6edf3;border:1px solid #30363d;border-radius:6px;padding:8px"></textarea>
<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap"><label class="qa" style="width:auto;cursor:pointer">&#128247; Gorsel Ekle<input type="file" accept="image/*" style="display:none" onchange="codeSetImage(this.files[0]);this.value=''"></label><span id="code_img_name" class="sub">Ctrl+V ile ekran goruntusu de yapistirabilirsin.</span><button class="qa" style="width:auto;display:none" id="code_img_clear" onclick="codeSetImage(null)">&times; Gorseli Kaldir</button></div>
<div style="display:flex;gap:8px"><button class="qa" style="width:auto" id="code_ai_btn" onclick="codeAsk()">Oneri Iste</button><button class="qa" style="width:auto;display:none" id="code_apply_btn" onclick="codeApply()">&#9989; Onerilen Degisikligi Uygula</button></div>
<pre id="code_ai_out" style="white-space:pre-wrap;background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:8px;max-height:40vh;overflow:auto;font-size:12px"></pre>
</div>
</div>
<script>
function showTab(name){
  ['home','insights','growth','comments','code'].forEach(t=>{
    document.getElementById('view-'+t).classList.toggle('active-view', t===name);
    document.getElementById('btn-tab-'+t).classList.toggle('active-tab', t===name);
  });
}
// ---- Kod modu (JS'te ters egik cizgi kullanilmaz: PAGE normal Python string) ----
let codeEdits = [], codeHist = [], codeReady = false;
let codeImg = null;
function codeSetImage(f){
  if(!f){ codeImg = null; codeEl('code_img_name').textContent = 'Ctrl+V ile ekran goruntusu de yapistirabilirsin.'; codeEl('code_img_clear').style.display = 'none'; return; }
  const rd = new FileReader();
  rd.onload = () => {
    codeImg = {b64: rd.result.split(',')[1], mime: f.type || 'image/png'};
    codeEl('code_img_name').textContent = 'Gorsel eklendi - istekle birlikte gidecek.';
    codeEl('code_img_clear').style.display = '';
  };
  rd.readAsDataURL(f);
}
const codeEl = id => document.getElementById(id);
function codeMsg(t, bad){ const m = codeEl('code_msg'); m.textContent = t; m.style.color = bad ? '#f85149' : '#3fb950'; }
function codePin(force, quiet){
  let p = '';
  try{ p = localStorage.getItem('aura_code_pin') || ''; }catch(e){}
  if(quiet) return p;
  if(!p || force){
    p = prompt('Kod PIN (8 hane; PC icinde _studio/code_pin.txt dosyasinda):') || '';
    try{ localStorage.setItem('aura_code_pin', p); }catch(e){}
  }
  return p;
}
async function codeApi(path, body, retry, quiet){
  const h = {'X-Code-Pin': codePin(false, quiet)};
  const o = body === undefined ? {headers:h} : {method:'POST', headers:Object.assign({'Content-Type':'application/json'}, h), body: JSON.stringify(body)};
  const r = await fetch(path, o);
  if(r.status === 403){
    if(quiet) return {ok: false, error: 'PIN gerekli', pin: true};
    if(!retry){
      const np = codePin(true);
      if(!np) return {ok: false, error: 'PIN girilmedi'};
      return codeApi(path, body, true);
    }
  }
  return r.json();
}
async function codeInit(){
  if(codeReady) return;
  const d = await codeApi('/api/code/files');
  if(!d.ok){ codeMsg(d.error || 'Kod modu kapali', true); return; }
  const sel = codeEl('code_file');
  sel.textContent = '';
  d.files.forEach(f => { const o = document.createElement('option'); o.value = f; o.textContent = f; sel.appendChild(o); });
  const pref = d.files.indexOf('aura_studio.py');
  if(pref >= 0) sel.selectedIndex = pref;
  codeReady = true;
  codeLoad();
}
async function codeLoad(){
  const p = codeEl('code_file').value;
  const d = await codeApi('/api/code/file?path=' + encodeURIComponent(p));
  if(!d.ok){ codeMsg(d.error, true); return; }
  codeEl('code_text').value = d.content;
  codeEl('code_ai_out').textContent = '';
  codeEl('code_apply_btn').style.display = 'none';
  codeEdits = []; codeHist = [];
  const b = await codeApi('/api/code/backups?path=' + encodeURIComponent(p));
  const bs = codeEl('code_bak'); bs.textContent = '';
  const o0 = document.createElement('option'); o0.value = ''; o0.textContent = 'Yedekler (' + (b.backups||[]).length + ')'; bs.appendChild(o0);
  (b.backups||[]).forEach(x => { const o = document.createElement('option'); o.value = x; o.textContent = x; bs.appendChild(o); });
  codeMsg('');
}
async function codeSave(){
  const d = await codeApi('/api/code/save', {path: codeEl('code_file').value, content: codeEl('code_text').value});
  if(d.ok){ codeMsg('Kaydedildi (yedek: ' + d.backup + '). Degisiklik icin "Paneli Yeniden Baslat".'); codeLoad(); }
  else codeMsg('KAYDEDILMEDI: ' + d.error, true);
}
async function codeRestore(){
  const b = codeEl('code_bak').value;
  if(!b){ codeMsg('Once yedek sec.', true); return; }
  if(!confirm('Bu yedek geri yuklensin mi? (Mevcut hali de yedeklenir)')) return;
  const d = await codeApi('/api/code/restore', {path: codeEl('code_file').value, backup: b});
  if(d.ok){ codeMsg('Geri yuklendi.'); codeLoad(); } else codeMsg(d.error, true);
}
async function codeAsk(){
  const ins = codeEl('code_instr').value.trim();
  if(!ins) return;
  const btn = codeEl('code_ai_btn'); btn.disabled = true; btn.textContent = 'Dusunuyor...';
  codeEl('code_ai_out').textContent = '';
  try{
    const d = await codeApi('/api/code/ai', {path: codeEl('code_file').value, instruction: ins, history: codeHist, image: codeImg ? codeImg.b64 : undefined, mime: codeImg ? codeImg.mime : undefined});
    if(!d.ok){ codeEl('code_ai_out').textContent = d.error || 'Hata'; return; }
    codeHist.push({role:'user', content: ins}, {role:'assistant', content: d.reply}); codeSetImage(null);
    codeEdits = d.edits || [];
    codeEl('code_ai_out').textContent = d.reply;
    codeEl('code_apply_btn').style.display = codeEdits.length ? '' : 'none';
    if(!codeEdits.length) codeEl('code_ai_out').textContent += String.fromCharCode(10,10) + '(Uygulanabilir SEARCH/REPLACE blogu yok - sadece aciklama.)';
  }catch(e){ codeEl('code_ai_out').textContent = 'Hata: ' + e; }
  finally{ btn.disabled = false; btn.textContent = 'Oneri Iste'; }
}
async function codeApply(){
  if(!codeEdits.length) return;
  const d = await codeApi('/api/code/apply', {path: codeEl('code_file').value, edits: codeEdits});
  if(d.ok){ codeMsg('Uygulandi (yedek: ' + d.backup + '). Etkin olmasi icin "Paneli Yeniden Baslat".'); codeEl('code_apply_btn').style.display = 'none'; codeLoad(); }
  else codeMsg('UYGULANMADI: ' + d.error, true);
}
async function codeRestart(){
  if(!confirm('Panel yeniden baslatilsin mi? (Bozuk acilirsa son yedekle kendini onarir)')) return;
  const d = await codeApi('/api/code/restart_panel', {});
  codeMsg(d.ok ? d.note : d.error, !d.ok);
  if(d.ok){
    const t = setInterval(async () => {
      try{ const r = await fetch('/api/history'); if(r.ok){ clearInterval(t); location.reload(); } }catch(e){}
    }, 3000);
  }
}

// ---- Analiz sekmesi (JS'te ters egik cizgi yok) ----
let INS_VID = null, INS_TITLE = '', INS_DESC = '', INS_ITEMS = [], INS_LAST = null;
const insEl = id => document.getElementById(id);
function esc(s){ return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
async function insLoad(force){
  const m = insEl('in_msg'); m.textContent = 'Yukleniyor...';
  try {
    const j = await (await fetch('/api/insights/stats' + (force ? '?force=1' : ''))).json();
    if(!j.ok){ m.textContent = 'Hata: ' + j.error; return; }
    INS_LAST = j;
    m.textContent = 'Son guncelleme: ' + j.fetched;
    insEl('in_summary').innerHTML = '<b>' + esc(j.channel) + '</b> &middot; ' + j.subscribers + ' abone &middot; ' + j.total_views + ' toplam izlenme &middot; ' + j.video_count + ' video';
    const top = Math.max.apply(null, j.videos.map(v => v.views).concat([1]));
    let h = '<table style="width:100%;border-collapse:collapse;font-size:12px"><tr style="text-align:left;color:#8b949e"><th>Video</th><th>Tarih</th><th>Izlenme</th><th>+</th><th>Begeni</th><th>Yorum</th><th></th></tr>';
    j.videos.forEach((v, i) => {
      const w = Math.round(100 * v.views / top);
      h += '<tr style="border-top:1px solid #30363d"><td style="padding:6px 4px"><a href="https://youtube.com/shorts/' + v.id + '" target="_blank" style="color:#58a6ff">' + esc(v.title) + '</a>' + (v.privacy !== 'public' ? ' <span class="sub">(' + v.privacy + ')</span>' : '') + '</td><td>' + v.published.slice(5, 10) + '</td><td><div style="background:#8957e5;height:6px;width:' + w + '%;min-width:2px;border-radius:3px"></div>' + v.views + '</td><td class="in_delta" data-id="' + v.id + '">-</td><td>' + v.likes + '</td><td>' + v.comments + '</td><td><button class="qa" style="width:auto;padding:4px 8px" onclick="insPick(' + i + ')">Yorumlar</button></td></tr>';
    });
    insEl('in_table').innerHTML = h + '</table>';
    insTrend(); tkLoad(); anLoad();
  } catch(e) { m.textContent = 'Hata: ' + e; }
}
setInterval(() => { if(insEl('in_auto') && insEl('in_auto').checked && insEl('view-insights').classList.contains('active-view')) insLoad(true); }, 60000);
async function insPick(i){
  showTab('comments');
  await cmInit();
  insEl('cm_video').value = INS_LAST.videos[i].id;
  cmChange();
}
async function cmInit(){
  if(!INS_LAST){
    const j = await (await fetch('/api/insights/stats')).json();
    if(!j.ok){ insEl('cm_msg').textContent = 'Hata: ' + j.error; return; }
    INS_LAST = j;
  }
  const sel = insEl('cm_video'); const keep = sel.value;
  sel.innerHTML = INS_LAST.videos.map(v => '<option value="' + v.id + '">' + esc(v.title) + ' (' + v.published.slice(5, 10) + ', ' + v.views + ' izl.)</option>').join('');
  if(keep) sel.value = keep;
  cmChange(); cmPins();
}
async function cmChange(){
  const v = INS_LAST.videos.find(x => x.id === insEl('cm_video').value);
  if(!v) return;
  INS_VID = v.id; INS_TITLE = v.title; INS_DESC = v.description || '';
  insEl('in_chead').textContent = 'Secili video: ' + v.title;
  insEl('in_draft_btn').style.display = '';
  const box = insEl('in_comments'); box.textContent = 'Yorumlar yukleniyor...';
  const j = await (await fetch('/api/insights/comments?video_id=' + encodeURIComponent(v.id))).json();
  if(!j.ok){ box.textContent = 'Hata: ' + j.error; return; }
  INS_ITEMS = j.comments.filter(c => !c.mine).map(c => Object.assign(c, {draft: ''}));
  insRenderComments(j.comments.length);
}
async function cmPost(btn){
  const txt = insEl('cm_text').value.trim();
  if(!INS_VID || !txt){ alert('Video sec ve yorum yaz'); return; }
  const pin = document.querySelector('input[name=cm_kind]:checked').value === 'pin';
  const NL = String.fromCharCode(10);
  if(!confirm('YouTube icinde HERKESE ACIK paylasilacak:' + NL + NL + 'Video: ' + INS_TITLE + NL + 'Tur: ' + (pin ? 'SABIT yorum (sonra sen sabitleyeceksin)' : 'Normal yorum') + NL + NL + txt)) return;
  btn.disabled = true;
  try {
    const j = await (await fetch('/api/insights/post_comment', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({video_id: INS_VID, title: INS_TITLE, text: txt, pin})})).json();
    const m = insEl('cm_msg');
    if(!j.ok){ m.textContent = 'GONDERILEMEDI: ' + j.error; return; }
    m.innerHTML = 'Paylasildi. <a href="' + j.link + '" target="_blank" style="color:#58a6ff">Yorumu ac</a>' + (pin ? ' - sabitlemek icin yorumun yanindaki uc nokta (&#8942;) &gt; Sabitle.' : '');
    insEl('cm_text').value = '';
    if(pin) cmPins();
  } finally { btn.disabled = false; }
}
async function cmPins(){
  const box = insEl('cm_pins');
  const j = await (await fetch('/api/insights/pins')).json();
  const list = Object.keys(j.pins || {}).map(k => Object.assign({cid: k}, j.pins[k])).filter(p => !p.pinned);
  if(!list.length){ box.textContent = 'Bekleyen yok.'; return; }
  box.innerHTML = list.map(p => '<div style="border:1px solid #30363d;border-radius:8px;padding:8px;margin-bottom:8px"><b>' + esc(p.title) + '</b> <span class="sub">' + p.time + '</span><div style="margin:4px 0">' + esc(p.text) + '</div><a href="' + p.link + '" target="_blank" style="color:#58a6ff">1) Yorumu YouTube icinde ac</a> &nbsp; <button class="qa" style="width:auto;padding:4px 8px" data-c="' + p.cid + '" onclick="cmPinDone(this.dataset.c)">2) Sabitledim &#10003;</button></div>').join('');
}
async function cmPinDone(cid){
  await fetch('/api/insights/pin_done', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({comment_id: cid})});
  cmPins();
}

// ---- Analiz: trend, TikTok elle giris, Analytics ----
function spark(vals){
  if(vals.length < 2) return '';
  const w = 220, h = 40, mn = Math.min.apply(null, vals), mx = Math.max.apply(null, vals);
  const pts = vals.map((v, i) => (i * w / (vals.length - 1)).toFixed(1) + ',' + (h - 4 - (mx === mn ? 0 : (v - mn) * (h - 8) / (mx - mn))).toFixed(1)).join(' ');
  return '<svg width="' + w + '" height="' + h + '" style="vertical-align:middle"><polyline fill="none" stroke="#a992e8" stroke-width="2" points="' + pts + '"/></svg>';
}
let INS_DELTAS = {};
async function insTrend(){
  try {
    const j = await (await fetch('/api/insights/trend')).json();
    if(!j.ok) return;
    INS_DELTAS = j.deltas || {};
    const box = document.getElementById('in_trend');
    const n = j.series.length;
    box.innerHTML = 'Sayac kayitlari: ' + n + (n < 2 ? ' (egri icin en az 2 kayit gerekir; panel acik kaldikca 6 saatte bir otomatik kaydedilir)' : ' &middot; toplam izlenme: ' + spark(j.series.map(s => s.total_views)) + ' ' + j.series[0].total_views + ' &rarr; ' + j.series[n - 1].total_views + ' &middot; abone: ' + j.series[0].subs + ' &rarr; ' + j.series[n - 1].subs) + (j.base_at ? ' &middot; "+" sutunu ' + j.base_at + ' kaydindan beri' : '');
    document.querySelectorAll('.in_delta').forEach(td => { const d = INS_DELTAS[td.dataset.id]; td.textContent = (d === undefined) ? '-' : ('+' + d); });
  } catch(e) {}
}
async function tkLoad(){
  const sel = document.getElementById('tk_video');
  if(INS_LAST) sel.innerHTML = INS_LAST.videos.map(v => '<option value="' + v.id + '">' + esc(v.title) + '</option>').join('');
  const j = await (await fetch('/api/insights/tiktok')).json();
  const box = document.getElementById('tk_table');
  if(!j.latest || !j.latest.length){ box.textContent = 'Henuz TikTok kaydi yok.'; return; }
  box.innerHTML = '<table style="width:100%;border-collapse:collapse;font-size:12px"><tr style="text-align:left;color:#8b949e"><th>Video</th><th>Tarih</th><th>Izl.</th><th>Begeni</th><th>Yorum</th><th>Paylasim</th></tr>' + j.latest.map(r => '<tr style="border-top:1px solid #30363d"><td>' + esc(r.title) + '</td><td>' + r.date.slice(5, 16) + '</td><td>' + r.views + '</td><td>' + r.likes + '</td><td>' + r.comments + '</td><td>' + r.shares + '</td></tr>').join('') + '</table>';
}
async function tkSave(btn){
  const id = document.getElementById('tk_video').value;
  if(!id){ alert('Once bir video sec'); return; }
  const title = document.getElementById('tk_video').selectedOptions[0].textContent;
  const val = k => document.getElementById('tk_' + k).value || 0;
  btn.disabled = true;
  try {
    const j = await (await fetch('/api/insights/tiktok_add', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({video_id: id, title, views: val('views'), likes: val('likes'), comments: val('comments'), shares: val('shares')})})).json();
    if(!j.ok){ alert(j.error); return; }
    ['views', 'likes', 'comments', 'shares'].forEach(k => { document.getElementById('tk_' + k).value = ''; });
    tkLoad();
  } finally { btn.disabled = false; }
}
async function anLoad(){
  const box = document.getElementById('an_box');
  try {
    const j = await (await fetch('/api/insights/analytics')).json();
    if(!j.status.authorized){
      box.innerHTML = 'Henuz yetki yok. Bu bolum videolarin <b>ortalama izlenme suresini ve izleyici tutma yuzdesini</b> verir. Gereken: (1) Google Cloud Console &gt; YouTube Analytics API servisini Etkinlestir, (2) asagidaki dugmeye bas, PC ekraninda acilan Google sayfasinda AURA hesabiyla onay ver (onayi sen verirsin, ben veremem). <br><button class="qa" style="width:auto;margin-top:6px" onclick="anAuth(this)">Yetki Ver (PC ekraninda acilir)</button>';
      return;
    }
    if(j.error){ box.textContent = 'Yetki var ama rapor alinamadi: ' + j.error; return; }
    const titles = {}; if(INS_LAST) INS_LAST.videos.forEach(v => { titles[v.id] = v.title; });
    box.innerHTML = 'Son 28 gun (' + j.range + '):<table style="width:100%;border-collapse:collapse;font-size:12px"><tr style="text-align:left;color:#8b949e"><th>Video</th><th>Izl.</th><th>Ort. sure (sn)</th><th>Ort. izlenme %</th><th>Abone</th></tr>' + j.rows.map(r => '<tr style="border-top:1px solid #30363d"><td>' + esc(titles[r.video_id] || r.video_id) + '</td><td>' + r.views + '</td><td>' + r.avg_sec + '</td><td>' + r.avg_pct + '%</td><td>' + r.subs + '</td></tr>').join('') + '</table>';
  } catch(e) { box.textContent = 'okunamadi'; }
}
async function anAuth(btn){
  btn.disabled = true;
  const j = await (await fetch('/api/insights/analytics_auth', {method:'POST', headers:{'Content-Type':'application/json'}, body: '{}'})).json();
  alert(j.ok ? j.note : j.error);
  btn.disabled = false;
}
function insRenderComments(total){
  const box = insEl('in_comments');
  if(!INS_ITEMS.length){ box.innerHTML = '<div class="sub">' + (total ? 'Yanitlanacak yorum yok (hepsi senin veya yanitlanmis).' : 'Bu videoda henuz yorum yok.') + '</div>'; return; }
  box.innerHTML = INS_ITEMS.map((c, i) => '<div style="border:1px solid #30363d;border-radius:8px;padding:8px;margin-bottom:8px"><div class="sub"><b>' + esc(c.author) + '</b> ' + (c.replied ? '(yanitlandi)' : '') + '</div><div style="margin:4px 0">' + esc(c.text) + '</div><textarea id="in_d' + i + '" rows="2" placeholder="Yanit taslagi (Taslak Uret ile dolar, duzenleyebilirsin)">' + esc(c.draft) + '</textarea><button class="qa" style="width:auto" onclick="insSend(' + i + ')">Gonder</button></div>').join('');
}
async function insDrafts(btn){
  if(!INS_VID) return;
  btn.disabled = true; btn.textContent = 'Dusunuyor...';
  try {
    const j = await (await fetch('/api/insights/comment_drafts', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({video_id: INS_VID, title: INS_TITLE})})).json();
    if(!j.ok){ alert(j.error); return; }
    INS_ITEMS = j.comments.map(c => Object.assign(c, {draft: (j.drafts[c.id] && j.drafts[c.id] !== 'SKIP') ? j.drafts[c.id] : ''}));
    insRenderComments(INS_ITEMS.length);
  } finally { btn.disabled = false; btn.textContent = 'Yanit Taslaklari Uret'; }
}
async function insSend(i){
  const c = INS_ITEMS[i]; const txt = insEl('in_d' + i).value.trim();
  if(!txt){ alert('Once yanit yaz/uret'); return; }
  if(!confirm('Bu yanit senin kanalindan YouTube icinde herkese acik gonderilecek:' + String.fromCharCode(10,10) + txt)) return;
  const j = await (await fetch('/api/insights/post_reply', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({parent_id: c.id, text: txt})})).json();
  if(j.ok){ c.replied = true; c.draft = txt; insEl('in_d' + i).value = ''; insEl('in_d' + i).placeholder = 'Gonderildi.'; }
  else alert('Gonderilemedi: ' + j.error);
}
async function insSeed(btn){
  if(!INS_VID) return;
  btn.disabled = true; btn.textContent = 'Dusunuyor...';
  try {
    const j = await (await fetch('/api/insights/seed_comment', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({title: INS_TITLE, description: INS_DESC})})).json();
    if(!j.ok){ alert(j.error); return; }
    insEl('cm_text').value = j.text;
  } finally { btn.disabled = false; btn.textContent = 'Oneri Uret'; }
}

// ---- TikTok toplu paket + AI kullanim ----
async function ttZipInit(){
  const vids = await (await fetch('/api/videos')).json();
  let rows = [];
  try { rows = await (await fetch('/api/day_status')).json(); } catch(e) {}
  const notTT = new Set();
  rows.forEach(r => { if(!r.tiktok && !r.tiktok_skip){ notTT.add('aura_' + String(r.title || '').toLowerCase().replace(/[^a-z0-9]+/g, '').slice(0, 24) + '.mp4'); } });
  document.getElementById('tt_zip_list').innerHTML = vids.slice(0, 15).map(v => '<label class="sub" style="display:block"><input type="checkbox" class="ttz" value="' + v + '" style="width:auto"' + (notTT.has(v) ? ' checked' : '') + '> ' + v + '</label>').join('');
}
function ttZip(ev){
  const sel = Array.from(document.querySelectorAll('.ttz:checked')).map(x => x.value);
  if(!sel.length){ ev.preventDefault(); alert('Once en az bir video sec'); return; }
  ev.currentTarget.href = '/api/tiktok_zip?v=' + encodeURIComponent(sel.join(','));
}
async function aiUsageLoad(){
  try {
    const j = await (await fetch('/api/ai_usage')).json();
    const day = new Date().toISOString().slice(0, 10);
    const keys = Object.keys(j.usage).sort();
    const today = j.usage[keys[keys.length - 1]] || {};
    const label = keys.length ? keys[keys.length - 1] : day;
    const parts = Object.keys(today).map(k => k + ': ' + today[k].calls + ' cagri, ~' + Math.round(today[k].tokens / 1000) + 'K token');
    document.getElementById('ai_usage').textContent = (parts.length ? label + ' - ' + parts.join(' | ') : 'Henuz cagri yok') + '. (Kod onerisi: ' + j.code_prefer + ')';
    const cp = document.getElementById('code_prov'); if(cp) cp.value = j.code_prefer;
  } catch(e) { document.getElementById('ai_usage').textContent = 'okunamadi'; }
}
async function codeSetProv(){
  const v = document.getElementById('code_prov').value;
  const d = await codeApi('/api/code/ai_settings', {code_prefer: v});
  codeMsg(d.ok ? 'Kod onerisi saglayicisi: ' + v : d.error, !d.ok);
}
ttZipInit(); aiUsageLoad(); setInterval(aiUsageLoad, 60000);

async function insAudit(btn){
  const out = document.getElementById('in_audit');
  btn.disabled = true; btn.textContent = 'Analiz ediliyor...';
  out.style.display = 'block'; out.textContent = 'Gercek veriler cekiliyor ve Aura analiz ediyor (30-60 sn)...';
  try {
    const j = await (await fetch('/api/insights/audit', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({})})).json();
    out.textContent = j.ok ? j.text : ('Hata: ' + j.error);
  } catch(e) { out.textContent = 'Hata: ' + e; }
  finally { btn.disabled = false; btn.textContent = 'Aura ile Strateji Analizi'; }
}

// ---- Buyume makinesi (v2) ----
const FORMAT_LABELS = {transparency: 'Seffaflik', template: 'Sablon', identity: 'Kimlik-tehdit', directive: 'Emir (Stop..)', other: 'Diger'};
let GM = null;
function preHtml(pf){
  if(!pf) return '';
  const icon = c => c.ok === true ? '<span style="color:#3fb950">&#10003;</span>' : (c.ok === false ? '<span style="color:#f85149">&#10007;</span>' : '<span style="color:#d29922">?</span>');
  let h = '<div class="sub"><b>Kural uyumu: ' + pf.score + ' / ' + pf.of + '</b> (tahmini sure ' + (pf.est_seconds || '?') + ' sn). ' + esc(pf.note || '') + '</div>';
  h += (pf.checks || []).filter(c => c.ok !== true).map(c => '<div class="sub">' + icon(c) + ' ' + esc(c.label) + (c.detail ? ' <span style="color:#8b949e">- ' + esc(c.detail) + '</span>' : '') + '</div>').join('');
  if(pf.ai) h += '<pre style="white-space:pre-wrap;font-size:12px;margin:6px 0">' + esc(pf.ai) + '</pre>';
  return h;
}
async function gmPre(btn){
  const box = document.getElementById('rp_pre');
  const body = {title: document.getElementById('rp_title').value, en_text: document.getElementById('rp_en').value, tr_text: document.getElementById('rp_tr').value, description: document.getElementById('rp_desc').value, ai: true};
  btn.disabled = true; btn.textContent = 'Kontrol ediliyor...';
  box.style.display = 'block'; box.textContent = '...';
  try { const j = await (await fetch('/api/growth/preflight', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)})).json(); box.innerHTML = j.ok ? preHtml(j) : esc(j.error || 'hata'); }
  catch(e) { box.textContent = 'Hata: ' + e; }
  finally { btn.disabled = false; btn.textContent = 'On Kontrol (yayindan once)'; }
}
async function gmPost(path, body){
  return (await fetch(path, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body || {})})).json();
}
function mdHtml(text){
  const lines = text.split(String.fromCharCode(10));
  let out = '', inList = false, tbl = [];
  const inline = s => esc(s).split('**').map((p, i) => i % 2 ? '<b>' + p + '</b>' : p).join('');
  const flushTbl = () => {
    if(!tbl.length) return;
    const rows = tbl.filter(r => r.indexOf('---') < 0).map(r => r.split('|').slice(1, -1).map(c => c.trim()));
    out += '<table style="border-collapse:collapse;font-size:12px;margin:6px 0">' + rows.map((r, ri) => '<tr>' + r.map(c => (ri === 0 ? '<th style="text-align:left;padding:3px 8px;color:#8b949e">' : '<td style="padding:3px 8px;border-top:1px solid #30363d">') + inline(c) + (ri === 0 ? '</th>' : '</td>')).join('') + '</tr>').join('') + '</table>';
    tbl = [];
  };
  const closeList = () => { if(inList){ out += '</ul>'; inList = false; } };
  for(const raw of lines){
    const l = raw.trim();
    if(l.startsWith('|')){ closeList(); tbl.push(l); continue; }
    flushTbl();
    if(l === ''){ closeList(); continue; }
    if(l === '---'){ closeList(); out += '<hr style="border-color:#30363d">'; continue; }
    const m = l.match(/^(#+)/);
    if(m){ closeList(); const lvl = Math.min(m[1].length + 1, 5); out += '<h' + lvl + ' style="margin:12px 0 4px;color:#e6edf3">' + inline(l.slice(m[1].length).trim()) + '</h' + lvl + '>'; continue; }
    if(l.startsWith('* ') || l.startsWith('- ')){ if(!inList){ out += '<ul style="margin:4px 0;padding-left:20px">'; inList = true; } out += '<li>' + inline(l.slice(2)) + '</li>'; continue; }
    closeList();
    out += '<p style="margin:4px 0">' + inline(l) + '</p>';
  }
  closeList(); flushTbl();
  return out;
}
function kpi(label, val, sub){
  return '<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:8px 12px;min-width:110px"><div class="sub">' + label + '</div><div style="font-size:18px;font-weight:700">' + val + '</div>' + (sub ? '<div class="sub">' + sub + '</div>' : '') + '</div>';
}
function actionHtml(a){
  let body = '';
  if(a.type === 'experiment') body = '<b>&#129514; Deney:</b> ' + esc(a.name) + '<div class="sub">Hipotez: ' + esc(a.hypothesis) + '</div><div class="sub">Format: ' + esc(a.format) + ' &middot; hedef: ' + a.target_n + ' olgun video (>=2 gunluk); baz: kanal medyani</div>';
  else if(a.type === 'draft') body = '<b>&#128221; Taslak:</b> ' + esc(a.title) + ' <span class="sub">[' + esc(a.format) + ']</span><pre style="white-space:pre-wrap;font-size:12px;margin:4px 0">' + esc(a.en_script) + '</pre>' + preHtml(a.preflight);
  else body = '<b>&#127991; Etiket:</b> ' + esc(a.title) + ' &rarr; ' + esc(a.format);
  return '<div style="border:1px solid #30363d;border-radius:8px;padding:10px;margin:8px 0">' + body + '<div class="sub" style="margin-top:4px">Neden: ' + esc(a.why || '') + '</div><div style="margin-top:6px;display:flex;gap:8px"><button class="qa" style="width:auto;background:#238636" data-id="' + a.id + '" onclick="gmApply(this)">&#10003; Uygula</button><button class="qa" style="width:auto" data-id="' + a.id + '" onclick="gmDismiss(this)">Reddet</button></div></div>';
}
function draftHtml(d){
  const st = {taslak: 'taslak', 'render edildi': 'render edildi', yayinlandi: 'YAYINDA'}[d.status] || d.status;
  let btns = '<button class="qa" style="width:auto" data-id="' + d.id + '" onclick="gmUse(this)">Forma aktar</button> ';
  if(d.status === 'taslak') btns += '<button class="qa" style="width:auto;background:#238636" data-id="' + d.id + '" onclick="gmRenderPublish(this)">&#128640; Render + Yayinla</button> <button class="qa" style="width:auto" data-id="' + d.id + '" onclick="gmRender(this)">Sadece Render Et</button> ';
  if(d.status === 'render edildi') btns += '<a class="qa" style="width:auto;text-decoration:none;display:inline-block" href="/download/' + encodeURIComponent(d.video) + '" download>&#11015; Izle/Indir</a> <button class="qa" style="width:auto;background:#238636" data-id="' + d.id + '" onclick="gmPublish(this)">&#128640; YouTube&#39;da Yayinla (onayli)</button> ';
  if(d.link) btns += '<a href="' + d.link + '" target="_blank" style="color:#58a6ff">' + d.link + '</a> ';
  btns += '<button class="qa" style="width:auto" data-id="' + d.id + '" onclick="gmDraftDel(this)">Sil</button>';
  return '<div style="border:1px solid #30363d;border-radius:8px;padding:10px;margin:8px 0"><b>' + esc(d.title) + '</b> <span class="sub">[' + esc(d.format) + '] &middot; ' + st + ' &middot; ' + d.created + '</span><div class="sub">' + esc(d.rationale || '') + '</div><pre style="white-space:pre-wrap;font-size:12px;margin:4px 0">' + esc(d.en_script) + '</pre>' + preHtml(d.preflight) + '<div style="margin-top:6px;display:flex;gap:8px;flex-wrap:wrap;align-items:center">' + btns + '</div></div>';
}
async function gmLoad(){
  try {
    const j = await (await fetch('/api/growth/state')).json();
    if(!j.ok){ document.getElementById('gm_formats').textContent = 'Hata: ' + j.error; return; }
    GM = j;
    const k = j.kpi;
    document.getElementById('gm_kpi').innerHTML = kpi('Abone', k.subs) + kpi('Toplam izlenme', k.total_views, k.videos + ' video') + kpi('Kanal medyani', j.median_views) + kpi('En iyi video', k.best_views, esc(k.best_title).slice(0, 24)) + kpi('TikTok (elle)', k.tt_entries + ' video', k.tt_total_views + ' izlenme') + kpi('Tutma verisi', k.retention_on ? 'acik' : 'kapali') + kpi('Sayac kaydi', k.snapshots);
    document.getElementById('gm_actions').innerHTML = j.actions.length ? j.actions.map(actionHtml).join('') : '<div class="sub">Bekleyen aksiyon yok. "Aksiyon Plani Uret" ya da haftalik rapor uretimi yeni oneriler getirir.</div>';
    document.getElementById('gm_drafts').innerHTML = j.drafts.length ? j.drafts.map(draftHtml).join('') : '<div class="sub">Taslak yok.</div>';
    document.getElementById('gm_exps').innerHTML = j.experiments.length ? '<table style="width:100%;border-collapse:collapse;font-size:12px"><tr style="text-align:left;color:#8b949e"><th>Deney</th><th>Format</th><th>Baslangic</th><th>Ilerleme / sonuc</th><th></th></tr>' + j.experiments.map(e => '<tr style="border-top:1px solid #30363d"><td>' + esc(e.name) + '<div class="sub">' + esc(e.hypothesis) + '</div></td><td>' + esc(e.format) + '</td><td>' + e.created.slice(5, 16) + '</td><td>' + esc(e.verdict) + '<div class="sub">' + e.count + ' video: ' + esc(e.videos.join(', ')) + '</div></td><td><button class="qa" style="width:auto;padding:2px 8px" data-id="' + e.id + '" onclick="gmExpDel(this)">Sil</button></td></tr>').join('') + '</table>' : 'Aktif deney yok. Aksiyon planindaki bir deneyi "Uygula" ile baslatabilirsin.';
    document.getElementById('gm_formats').innerHTML = '<table style="width:100%;border-collapse:collapse;font-size:12px"><tr style="text-align:left;color:#8b949e"><th>Format</th><th>YT n</th><th>Medyan izl.</th><th>Ort.</th><th>Max</th><th>Tutma %</th><th>TikTok n</th><th>TT medyan izl.</th><th>TT medyan begeni</th></tr>' + j.groups.map(g => '<tr style="border-top:1px solid #30363d"><td>' + esc(g.label) + '<div class="sub">' + esc(g.verdict) + '</div></td><td>' + g.n + '</td><td>' + g.median_views + '</td><td>' + g.mean_views + '</td><td>' + g.max_views + '</td><td>' + (g.median_retention === null ? '-' : g.median_retention) + '</td><td>' + g.tt_n + '</td><td>' + (g.tt_median_views === null ? '-' : g.tt_median_views) + '</td><td>' + (g.tt_median_likes === null ? '-' : g.tt_median_likes) + '</td></tr>').join('') + '</table><div class="sub">Kanal medyan izlenmesi: ' + j.median_views + '. TikTok sutunlari sadece elle girdigin videolari sayar.</div>';
    document.getElementById('gm_tags').innerHTML = j.videos.map(v => '<div class="sub" style="display:flex;gap:6px;align-items:center"><select data-id="' + v.id + '" onchange="gmTag(this)" style="width:auto">' + Object.keys(FORMAT_LABELS).map(x => '<option value="' + x + '"' + (x === v.format ? ' selected' : '') + '>' + FORMAT_LABELS[x] + '</option>').join('') + '</select> ' + esc(v.title) + ' (' + v.views + ')' + (v.auto ? '' : ' &#9998;') + '</div>').join('');
    const missing = j.videos.filter(v => !v.tt).length;
    document.getElementById('gm_tt').innerHTML = '<div>TikTok verisi eksik: <b>' + missing + '</b> video. Uygulamadan bakip yaz; her giris tarihiyle tutulur ve analize girer.</div><table style="width:100%;border-collapse:collapse;font-size:12px;margin-top:6px"><tr style="text-align:left;color:#8b949e"><th>Video</th><th>Son giris</th><th>Izl.</th><th>Begeni</th><th>Yorum</th><th>Paylasim</th><th></th></tr>' + j.videos.slice(0, 12).map((v, i) => '<tr style="border-top:1px solid #30363d"><td>' + esc(v.title).slice(0, 34) + '</td><td>' + (v.tt ? (v.tt.views + ' izl. (' + v.tt.date.slice(5, 10) + ')') : '-') + '</td><td><input id="tq_v' + i + '" type="number" min="0" style="width:64px"></td><td><input id="tq_l' + i + '" type="number" min="0" style="width:56px"></td><td><input id="tq_c' + i + '" type="number" min="0" style="width:56px"></td><td><input id="tq_s' + i + '" type="number" min="0" style="width:56px"></td><td><button class="qa" style="width:auto;padding:2px 8px" data-i="' + i + '" onclick="gmTtSave(this)">Kaydet</button></td></tr>').join('') + '</table>';
    const sel = document.getElementById('gm_rep_sel');
    const cur = sel.value;
    sel.innerHTML = j.reports.map(r => '<option value="' + r + '">' + r.replace('.md', '') + '</option>').join('');
    if(cur) sel.value = cur;
    document.getElementById('gm_rep_info').textContent = j.report_age_days === null ? 'Henuz rapor yok' : 'Son rapor ' + j.report_age_days.toFixed(1) + ' gun once (panel aciksa haftada bir otomatik uretilir)';
    if(!document.getElementById('gm_report').innerHTML && j.latest_report) document.getElementById('gm_report').innerHTML = mdHtml(j.latest_report.text);
  } catch(e) { document.getElementById('gm_formats').textContent = 'Hata: ' + e; }
}
async function gmShowReport(){
  const n = document.getElementById('gm_rep_sel').value;
  if(!n) return;
  const j = await (await fetch('/api/growth/report?name=' + encodeURIComponent(n))).json();
  document.getElementById('gm_report').innerHTML = j.ok ? mdHtml(j.text) : 'Hata';
}
async function gmTag(sel){ await gmPost('/api/growth/tag', {video_id: sel.dataset.id, format: sel.value}); gmLoad(); }
async function gmTtSave(btn){
  const i = Number(btn.dataset.i); const v = GM.videos[i];
  const g = k => document.getElementById('tq_' + k + i).value || 0;
  if(!document.getElementById('tq_v' + i).value){ alert('En az izlenme sayisini yaz'); return; }
  btn.disabled = true;
  const j = await gmPost('/api/insights/tiktok_add', {video_id: v.id, title: v.title, views: g('v'), likes: g('l'), comments: g('c'), shares: g('s')});
  btn.disabled = false;
  if(!j.ok){ alert(j.error); return; }
  gmLoad();
}
async function gmReport(btn){
  btn.disabled = true; btn.textContent = 'Uretiliyor (1-2 dk)...';
  try { const j = await gmPost('/api/growth/report', {}); document.getElementById('gm_report').innerHTML = j.ok ? mdHtml(j.text) : ('Hata: ' + esc(j.error)); if(j.ok){ gmLoad(); } }
  catch(e) { document.getElementById('gm_report').textContent = 'Hata: ' + e; }
  finally { btn.disabled = false; btn.textContent = 'Simdi Rapor Uret (+ aksiyon plani)'; }
}
async function gmActions(btn){
  btn.disabled = true; btn.textContent = 'Aura dusunuyor (1-2 dk)...';
  try { const j = await gmPost('/api/growth/actions', {}); if(!j.ok) alert(j.error); else if(!j.added) alert('Aura uygulanabilir aksiyon uretemedi, tekrar dene.'); gmLoad(); }
  catch(e) { alert('Hata: ' + e); }
  finally { btn.disabled = false; btn.textContent = 'Aksiyon Plani Uret'; }
}
async function gmApply(btn){ btn.disabled = true; const j = await gmPost('/api/growth/apply', {id: btn.dataset.id}); if(!j.ok) alert(j.error); gmLoad(); }
async function gmDismiss(btn){ await gmPost('/api/growth/dismiss', {id: btn.dataset.id}); gmLoad(); }
async function gmExpDel(btn){ if(confirm('Deney silinsin mi?')){ await gmPost('/api/growth/exp_delete', {id: btn.dataset.id}); gmLoad(); } }
async function gmDraftDel(btn){ if(confirm('Taslak silinsin mi?')){ await gmPost('/api/growth/draft_delete', {id: btn.dataset.id}); gmLoad(); } }
async function gmCandidates(btn){
  btn.disabled = true; btn.textContent = 'Aura yaziyor (1-2 dk)...';
  try { const j = await gmPost('/api/growth/candidates', {}); if(!j.ok) alert(j.error); gmLoad(); }
  catch(e) { alert('Hata: ' + e); }
  finally { btn.disabled = false; btn.textContent = '3 Aday Taslak Uret'; }
}
async function gmAgenda(btn){
  btn.disabled = true; btn.textContent = 'Gercek zamanli haber araniyor (Google Search, 30-60 sn)...';
  try {
    const j = await gmPost('/api/growth/agenda_candidate', {});
    if(!j.ok) alert(j.error || 'Basarisiz');
    else if(!j.sources || !j.sources.length) alert('UYARI: model kaynak dondurmedi. Taslak olusturuldu ama yayinlamadan once haberi kendin dogrula.');
    gmLoad();
  }
  catch(e) { alert('Hata: ' + e); }
  finally { btn.disabled = false; btn.textContent = String.fromCodePoint(128240) + ' Gundemden Aday Uret (gercek haber)'; }
}
async function gmRender(btn){
  btn.disabled = true; btn.textContent = 'Render ediliyor (1-3 dk)...';
  const j = await gmPost('/api/growth/render_draft', {id: btn.dataset.id});
  if(!j.ok) alert(j.error); else if(j.warning) alert(j.warning);
  gmLoad();
}
async function gmPublish(btn){
  const d = GM.drafts.find(x => x.id === btn.dataset.id);
  if(!d) return;
  const NL = String.fromCharCode(10);
  if(!confirm('YouTube icinde HERKESE ACIK yayinlanacak:' + NL + NL + d.title + NL + NL + d.description.slice(0, 200) + NL + NL + 'Onayliyor musun?')) return;
  btn.disabled = true; btn.textContent = 'Yayinlaniyor...';
  const j = await gmPost('/api/growth/publish_draft', {id: d.id, confirm: true});
  alert(j.ok ? ('Yayinlandi: ' + j.link) : ('Yayinlanamadi: ' + j.error));
  gmLoad(); loadDayStatus();
}
async function gmRenderPublish(btn){
  const d = GM.drafts.find(x => x.id === btn.dataset.id);
  if(!d) return;
  const NL = String.fromCharCode(10);
  if(!confirm('Render edilip YouTube icinde HERKESE ACIK yayinlanacak (etiketler otomatik):' + NL + NL + d.title + NL + NL + d.description.slice(0, 200) + NL + NL + 'Onayliyor musun?')) return;
  btn.disabled = true; btn.textContent = 'Render + yayin (2-4 dk)...';
  const j = await gmPost('/api/growth/render_publish_draft', {id: d.id, confirm: true});
  alert(j.ok ? ('Yayinlandi: ' + j.link) : ('Olmadi: ' + j.error));
  gmLoad(); loadDayStatus();
}
function gmUse(btn){
  const c = GM.drafts.find(x => x.id === btn.dataset.id);
  if(!c) return;
  const max = (typeof DAY_ROWS !== 'undefined' ? DAY_ROWS : []).reduce((m, r) => Math.max(m, r.day || 0), 0);
  document.getElementById('rp_day').value = String(max + 1);
  document.getElementById('rp_title').value = c.title;
  document.getElementById('rp_en').value = c.en_script;
  document.getElementById('rp_tr').value = c.tr_script;
  document.getElementById('rp_desc').value = c.description;
  document.getElementById('rp_tags').value = String(c.tags || '');
  showTab('home');
  document.getElementById('rp_title').scrollIntoView();
}

// ---- Siradaki adim bandi ----
function slugOf(title){ return 'aura_' + String(title || '').toLowerCase().replace(/[^a-z0-9]+/g, '').slice(0, 24) + '.mp4'; }
function nextStep(){
  const box = document.getElementById('next_step');
  if(!box || !DAY_ROWS.length) return;
  const rows = DAY_ROWS.slice().sort((a, b) => a.day - b.day);
  const pending = rows.filter(r => r.youtube && !r.tiktok && !r.tiktok_skip).pop();
  if(pending){
    box.innerHTML = '<b>&#10145; SIRADAKI ADIM: TikTok</b><div class="sub" style="margin:4px 0">Gun ' + pending.day + ' "' + esc(pending.title) + '" YouTube&#39;da yayinda ama TikTok&#39;a yuklenmedi.</div><button class="pub" style="background:#3b5bdb" onclick="nextGoTikTok(' + pending.day + ')">TikTok paketini ac (link + aciklama)</button>';
  } else {
    box.innerHTML = '<b>&#10145; SIRADAKI ADIM: yeni video</b><div class="sub" style="margin:4px 0">Tum videolar iki platformda da yayinda. Yeni fikir icin Makine sekmesinde "3 Aday Taslak Uret" ya da sohbette paket iste.</div><button class="pub" style="background:#3b5bdb" onclick="showTab(&#39;growth&#39;);gmLoad()">Makine sekmesine git</button>';
  }
}
function nextGoTikTok(day){
  const row = DAY_ROWS.find(r => r.day === day);
  const sel = document.getElementById('tt_video');
  const file = row ? slugOf(row.title) : '';
  if(sel && file){ sel.value = file; ttFill(); }
  document.getElementById('tt_video').scrollIntoView();
}

// ---- Studio Asistani (panel ici ajan) ----
let AG_LAST = 0, AG_INIT = false, AG_RUN = false, AG_NEEDPIN = false;
function agAdd(ev){
  const log = document.getElementById('ag_log');
  const d = document.createElement('div');
  d.style.margin = '6px 0';
  if(ev.t === 'user'){ d.style.textAlign = 'right'; d.innerHTML = '<span style="display:inline-block;background:#1f6feb;border-radius:10px;padding:6px 10px;text-align:left;max-width:90%;white-space:pre-wrap">' + esc(ev.txt) + (ev.has_image ? ' [gorsel]' : '') + '</span>'; }
  else if(ev.t === 'text'){ d.innerHTML = '<div style="background:#161b22;border:1px solid #30363d;border-radius:10px;padding:6px 10px">' + mdHtml(ev.txt) + '</div>'; }
  else if(ev.t === 'tool'){ d.innerHTML = '<div class="sub">&#128295; ' + esc(ev.txt) + '</div>'; }
  else if(ev.t === 'result'){ d.innerHTML = '<details><summary class="sub" style="cursor:pointer;color:' + (ev.ok === false ? '#f85149' : '#8b949e') + '">sonuc' + (ev.ok === false ? ' (HATA)' : '') + '</summary><pre style="white-space:pre-wrap;font-size:11px;max-height:220px;overflow:auto">' + esc(ev.txt) + '</pre></details>'; }
  else if(ev.t === 'error'){ d.innerHTML = '<div style="color:#f85149">&#9888; ' + esc(ev.txt) + '</div>'; }
  else return;
  log.appendChild(d);
  log.scrollTop = log.scrollHeight;
}
async function agTick(){
  if(!document.getElementById('view-code').classList.contains('active-view')) return;
  try {
    if(AG_NEEDPIN) return;
    const j = await codeApi('/api/agent/poll?since=' + AG_LAST, undefined, false, true);
    if(!j.ok){
      document.getElementById('ag_status').textContent = j.error || '';
      if(j.pin){ AG_NEEDPIN = true; document.getElementById('ag_pin').style.display = 'block'; }
      return;
    }
    j.events.forEach(agAdd);
    AG_LAST = Math.max(AG_LAST, j.last || 0);
    AG_RUN = j.running;
    document.getElementById('ag_status').textContent = j.running ? 'calisiyor...' : ('hazir' + (j.changes ? ' | ' + j.changes + ' degisiklik' : ''));
    document.getElementById('ag_send').disabled = j.running;
    document.getElementById('ag_restart').style.display = j.needs_restart ? 'block' : 'none';
  } catch(e) {}
}
function agInit(){
  if(AG_INIT) return;
  AG_INIT = true;
  document.getElementById('ag_in').addEventListener('keydown', e => { if(e.key === 'Enter' && !e.shiftKey){ e.preventDefault(); agSend(); } });
  agTick();
  setInterval(agTick, 1000);
}
async function agSend(){
  const inp = document.getElementById('ag_in');
  const text = inp.value.trim();
  if(!text || AG_RUN) return;
  const body = {message: text};
  if(codeImg){ body.image = codeImg.b64; body.mime = codeImg.mime; }
  const j = await codeApi('/api/agent/send', body);
  if(!j.ok){ agAdd({t: 'error', txt: j.error || 'gonderilemedi'}); return; }
  inp.value = '';
  codeSetImage(null);
  AG_RUN = true;
  agTick();
}
function agSavePin(){
  const v = document.getElementById('ag_pin_in').value.trim();
  if(!v) return;
  try{ localStorage.setItem('aura_code_pin', v); }catch(e){}
  document.getElementById('ag_pin_in').value = '';
  document.getElementById('ag_pin').style.display = 'none';
  AG_NEEDPIN = false;
  agTick();
}
async function agCancel(){ await codeApi('/api/agent/cancel', {}); }
async function agReset(){
  if(!confirm('Sohbet temizlensin mi? (dosya degisiklikleri geri alinmaz)')) return;
  const j = await codeApi('/api/agent/reset', {});
  if(j.ok){ document.getElementById('ag_log').textContent = ''; AG_LAST = 0; agTick(); } else alert(j.error);
}
async function agUndo(){
  if(!confirm('Asistanin bu sohbette yaptigi TUM dosya degisiklikleri geri alinsin mi?')) return;
  const j = await codeApi('/api/agent/undo', {});
  if(!j.ok) alert((j.errors || []).join(String.fromCharCode(10)) || j.error);
  agTick();
}

async function trAudit(btn){
  const m = document.getElementById('tr_audit_msg');
  btn.disabled = true; m.textContent = 'Denetleniyor (video basina YouTube kotasi kullanir)...';
  try {
    const j = await (await fetch('/api/tr_cc/audit', {method:'POST', headers:{'Content-Type':'application/json'}, body: '{}'})).json();
    m.textContent = j.ok ? ('Yuklenen: ' + j.restored + ' | zaten var: ' + j.skipped + ' | kalan: ' + (j.left.length ? j.left.join(', ') : 'yok') + (j.quota ? ' | YouTube kotasi doldu: kalanlari panel kota yenilenince otomatik tamamlar' : '')) : 'Hata';
  } catch(e) { m.textContent = 'Hata: ' + e; }
  finally { btn.disabled = false; }
}
let pendingImage = null;
function setPendingImage(blob){
  const reader = new FileReader();
  reader.onload = () => {
    pendingImage = {b64: reader.result.split(',')[1], mime: blob.type};
    document.getElementById('img_preview_thumb').src = reader.result;
    document.getElementById('img_preview_name').textContent = 'Gorsel eklendi - mesajla birlikte gonderilecek';
    document.getElementById('img_preview_bar').classList.add('show');
  };
  reader.readAsDataURL(blob);
}
function clearPendingImage(){
  pendingImage = null;
  document.getElementById('img_preview_bar').classList.remove('show');
}
document.addEventListener('paste', function(event){
  const items = (event.clipboardData || window.clipboardData).items;
  if(!items) return;
  for(const item of items){
    if(item.kind === 'file' && item.type.indexOf('image') !== -1){
      if(document.getElementById('view-code').classList.contains('active-view')){
        codeSetImage(item.getAsFile());
        continue;
      }
      showTab('home');
      setPendingImage(item.getAsFile());
    }
  }
});
const mainEl = document.getElementById('main');
if(mainEl){
  mainEl.addEventListener('dragover', e=>{ e.preventDefault(); });
  mainEl.addEventListener('drop', e=>{
    e.preventDefault();
    for(const f of e.dataTransfer.files){
      if(f.type.indexOf('image') !== -1){ setPendingImage(f); }
    }
  });
}
</script>
<script>
async function loadStatus(){
  const r = await fetch('/api/status'); const j = await r.json();
  document.getElementById('status_box').textContent = j.tail;
}
async function loadVoiceMeshStatus(){
  const el = document.getElementById('vm_status');
  try {
    const r = await fetch('/api/voice_mesh_status'); const j = await r.json();
    el.textContent = 'Voice Mesh: ' + (j.up ? 'calisiyor' : 'kapali/yanit vermiyor');
    el.className = 'sub ' + (j.up ? 'up' : 'down');
  } catch(e) {
    el.textContent = 'Voice Mesh: kontrol edilemedi'; el.className = 'sub down';
  }
}
async function restartVoiceMesh(){
  const log = document.getElementById('vm_log');
  log.style.display = 'block';
  log.textContent = 'Yeniden baslatiliyor... (model yuklemesi 3 dakikaya kadar surebilir, bekle)';
  const btn = (typeof event !== 'undefined' && event) ? event.target : null;
  if(btn) btn.disabled = true;
  try {
    const r = await fetch('/api/restart_voice_mesh', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
    const j = await r.json();
    log.textContent = (j.ok ? '[OK]\\n' : '[HATA]\\n') + j.log;
    loadVoiceMeshStatus();
  } catch(e) {
    log.textContent = '[HATA] ' + e;
  } finally {
    if(btn) btn.disabled = false;
  }
}
loadVoiceMeshStatus();
setInterval(loadVoiceMeshStatus, 30000);
function showTunnel(st){
  const el = document.getElementById('tn_status');
  const box = document.getElementById('tn_link_box');
  if(!st || !st.running){
    el.textContent = 'Tunel: kapali (telefondan girmek icin Tuneli Baslat)';
    el.className = 'sub down'; box.style.display = 'none'; return;
  }
  if(st.url && st.ready){
    el.textContent = 'Tunel: hazir - ' + st.url; el.className = 'sub up';
    document.getElementById('tn_link').value = st.link || st.url;
    box.style.display = 'block';
  } else {
    el.textContent = 'Tunel: baglaniyor...'; el.className = 'sub down'; box.style.display = 'none';
  }
}
async function loadTunnelStatus(){
  try {
    const r = await fetch('/api/tunnel_status'); showTunnel(await r.json());
  } catch(e) {
    document.getElementById('tn_status').textContent = 'Tunel: kontrol edilemedi';
  }
}
async function startTunnel(){
  const log = document.getElementById('tn_log');
  log.style.display = 'block';
  log.textContent = 'Tunel aciliyor... (10-40 sn surebilir)';
  const btn = (typeof event !== 'undefined' && event) ? event.target : null;
  if(btn) btn.disabled = true;
  try {
    const r = await fetch('/api/start_tunnel', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
    const j = await r.json();
    showTunnel(j);
    if(j.ok){
      let msg = 'Hazir. Asagidaki linki kopyalayip telefonda ac (ilk acista token cerezi kaydolur).';
      if(j.dns_ok === false) msg += ' UYARI: link henuz genel DNS ile cozulmuyor, 1-2 dk sonra dene.';
      log.textContent = msg;
    } else {
      log.textContent = 'HATA: ' + (j.error || 'bilinmeyen');
    }
  } catch(e) {
    log.textContent = 'HATA: ' + e;
  } finally {
    if(btn) btn.disabled = false;
  }
}
async function copyTunnelLink(){
  const inp = document.getElementById('tn_link');
  inp.select();
  try { await navigator.clipboard.writeText(inp.value); document.getElementById('tn_log').style.display='block'; document.getElementById('tn_log').textContent = 'Link panoya kopyalandi.'; }
  catch(e) { document.getElementById('tn_log').style.display='block'; document.getElementById('tn_log').textContent = 'Otomatik kopyalanamadi - link secili, Ctrl+C ile kopyala.'; }
}
loadTunnelStatus();
setInterval(loadTunnelStatus, 30000);
async function loadTailscale(){
  const el = document.getElementById('ts_status');
  const box = document.getElementById('ts_link_box');
  try {
    const r = await fetch('/api/tailscale_status'); const j = await r.json();
    if(!j.installed){ el.textContent = 'Tailscale: kurulu degil'; el.className = 'sub down'; box.style.display = 'none'; return; }
    if(!j.connected){ el.textContent = 'Tailscale: kurulu ama giris yapilmamis/bagli degil - sistem tepsisindeki Tailscale simgesinden giris yap'; el.className = 'sub down'; box.style.display = 'none'; return; }
    el.textContent = 'Tailscale: bagli - ' + j.ip + (j.dns ? ' (' + j.dns + ')' : ''); el.className = 'sub up';
    document.getElementById('ts_link').value = j.link; box.style.display = 'block';
  } catch(e) { el.textContent = 'Tailscale: kontrol edilemedi'; el.className = 'sub down'; }
}
async function copyTsLink(){
  const inp = document.getElementById('ts_link'); inp.select();
  try { await navigator.clipboard.writeText(inp.value); } catch(e) {}
}
loadTailscale();
setInterval(loadTailscale, 30000);
let TT_META = {};
async function loadVideos(sel){
  const r = await fetch('/api/videos'); const vids = await r.json();
  try { TT_META = await (await fetch('/api/tiktok_meta')).json(); } catch(e) { TT_META = {}; }
  const el = document.getElementById('tt_video');
  const keep = sel || el.value;
  el.innerHTML = vids.map(v=>`<option value="${v}">${v}</option>`).join('');
  if(keep && vids.indexOf(keep) >= 0) el.value = keep;
  ttFill();
}
let TT_PACK = null;
async function ttFill(){
  const v = document.getElementById('tt_video').value;
  const a = document.getElementById('tt_dl');
  a.href = v ? '/download/' + encodeURIComponent(v) : '#';
  a.setAttribute('download', v || '');
  if(!v) return;
  let pk = null;
  try { pk = await (await fetch('/api/tiktok_pack?video=' + encodeURIComponent(v))).json(); } catch(e) {}
  if(document.getElementById('tt_video').value !== v) return;  // baska bir video secildi, eski yanit gecersiz
  TT_PACK = pk && pk.ok ? pk : null;
  const m = TT_META[v];
  document.getElementById('tt_desc').value = (pk && pk.description) || (m ? m.description : '');
  document.getElementById('tt_dl_txt').value = (pk && pk.download_link) || 'Tailscale bagli degil - once Ayarlar > Telefon/Tablet Erisimi bolumune bak';
  document.getElementById('tt_yt_txt').value = (pk && pk.youtube_link) || '(bulunamadi)';
  const b = document.getElementById('tt_done_btn');
  if(pk && pk.day){ b.style.display = ''; b.textContent = pk.tiktok_done ? 'TikTok isaretli (Gun ' + pk.day + ') - geri al' : 'TikTok yuklendi olarak isaretle (Gun ' + pk.day + ')'; }
  else { b.style.display = 'none'; }
}
function ttCopyEl(id, btn){
  const el = document.getElementById(id);
  const log = document.getElementById('tt_log');
  el.focus(); el.select(); el.setSelectionRange(0, 999999);
  let ok = false;
  try { ok = document.execCommand('copy'); } catch(e) {}
  const done = () => { const old = btn.textContent; btn.textContent = 'Kopyalandi \u2713'; setTimeout(() => { btn.textContent = old; }, 1500); };
  if(ok){ done(); return; }
  if(navigator.clipboard && navigator.clipboard.writeText){
    navigator.clipboard.writeText(el.value).then(done).catch(() => { log.style.display = 'block'; log.textContent = 'Kopyalanamadi: kutuyu basili tutup Kopyala de.'; });
  } else { log.style.display = 'block'; log.textContent = 'Kopyalanamadi: kutuyu basili tutup Kopyala de.'; }
}
async function ttDone(){
  if(!TT_PACK || !TT_PACK.day) return;
  await toggleDay(TT_PACK.day, 'tiktok', !TT_PACK.tiktok_done);
  ttFill();
}
async function autoTags(btn){
  const title = document.getElementById('rp_title').value.trim();
  const script = document.getElementById('rp_en').value.trim();
  if(!title && !script){ alert('Once baslik veya ingilizce script gir'); return; }
  btn.disabled = true; btn.textContent = 'Dusunuyor...';
  try {
    const j = await (await fetch('/api/insights/hashtags', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({title, script})})).json();
    if(!j.ok){ alert(j.error || 'Hata'); return; }
    document.getElementById('rp_tags').value = j.tags.split(' ').map(x=>x.replace('#','')).join(',');
    const d = document.getElementById('rp_desc');
    if(d.value.indexOf('#') < 0) d.value = (d.value.trim() + String.fromCharCode(10,10) + j.tags).trim();
  } finally { btn.disabled = false; btn.textContent = 'Etiketleri Otomatik Oner'; }
}
function checkTrChars(){
  const en = document.getElementById('rp_en').value;
  const warn = document.getElementById('rp_en_warn');
  if(/[çğıöşüÇĞİÖŞÜ]/.test(en)){
    warn.textContent = 'UYARI: Bu alanda Turkce karakter var - Ingilizce script alanina yanlislikla Turkce yapistirilmis olabilir.';
    warn.style.display = 'block';
  } else {
    warn.style.display = 'none';
  }
}
document.getElementById('rp_en').addEventListener('input', checkTrChars);
function rpUnlock(){
  const rpBtn = document.querySelector('#panel button[onclick="renderAndPublish()"]');
  if(rpBtn && rpBtn.dataset.publishedTitle){
    delete rpBtn.dataset.publishedTitle;
    rpBtn.textContent = String.fromCodePoint(128293) + ' Render + Yayinla';
    rpBtn.style.background = '';
  }
}
document.getElementById('rp_title').addEventListener('input', rpUnlock);
document.getElementById('rp_en').addEventListener('input', rpUnlock);

async function renderAndPublish(ev){
  const day = document.getElementById('rp_day').value.trim();
  const title = document.getElementById('rp_title').value.trim();
  const en_text = document.getElementById('rp_en').value.trim();
  const tr_text = document.getElementById('rp_tr').value.trim();
  const description = document.getElementById('rp_desc').value;
  const tags = document.getElementById('rp_tags').value.trim();
  const privacy = document.getElementById('rp_privacy').value;
  if(!en_text || !title){ alert('Baslik ve Ingilizce script gerekli'); return; }
  const rpBtn = document.querySelector('#panel button[onclick="renderAndPublish()"]');
  if(rpBtn && rpBtn.dataset.publishedTitle === title.trim().toLowerCase()){
    alert('Bu video BU FORMDAN zaten yayinlandi (dugme "Yayinlandi" yaziyor). Yeniden yayinlamak icin farkli bir baslik/script gir ya da sayfayi yenile.');
    return {ok: false, error: 'form zaten yayinlanmis olarak isaretli'};
  }
  if(PUBLISHING_NOW){
    alert('Zaten bir uretim/yayin islemi suruyor. Lutfen onun bitmesini bekle (1-3 dakika), tekrar tiklama.');
    return {ok:false, error:'baska bir yayin zaten suruyor'};
  }
  let force = false;
  if(PUBLISHED_TITLES.has(title.trim().toLowerCase())){
    if(!confirm(`"${title}" basligi zaten yayinlanmis gorunuyor (Gun Takibi tablosuna bak). Ayni videoyu tekrar yuklemek istedigine emin misin?`)){
      return {ok:false, error:'kullanici iptal etti (zaten yayinlanmis)'};
    }
    force = true;
  }
  PUBLISHING_NOW = true;
  const log = document.getElementById('rp_log');
  log.style.display = 'block';
  log.textContent = 'Ses uretiliyor, video render ediliyor, yayinlaniyor... (1-3 dakika surebilir) - LUTFEN TEKRAR TIKLAMA.';
  const btn = (ev && ev.target) || (typeof event !== 'undefined' ? event.target : null);
  if(btn) btn.disabled = true;
  try {
    const r = await fetch('/api/render_and_publish', {method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({day, title, en_text, tr_text, description, tags, privacy, force})});
    const j = await r.json();
    let out = (j.ok ? '[OK] ' : '[HATA] ') + (j.link ? 'Link: ' + j.link : (j.error || ''));
    if(j.warnings && j.warnings.length) out = j.warnings.join('\\n') + '\\n\\n' + out;
    if(j.publish_output) out += '\\n\\n' + j.publish_output;
    log.textContent = out;
    loadVideos(j.video || null); loadDayStatus();
    if(j.ok){
      PUBLISHED_TITLES.add(title.trim().toLowerCase());
      if(rpBtn){
        rpBtn.textContent = String.fromCodePoint(9989) + ' Yayinlandi';
        rpBtn.style.background = '#238636';
        rpBtn.dataset.publishedTitle = title.trim().toLowerCase();
      }
      render();
    }
    return j;
  } catch(e) {
    log.textContent = '[HATA] ' + e;
    return {ok:false, error:String(e)};
  } finally {
    PUBLISHING_NOW = false;
    if(btn) btn.disabled = false;
  }
}
let DAY_ROWS = [];
let PUBLISHED_TITLES = new Set();
let PUBLISHING_NOW = false;
async function loadDayStatus(){
  const r = await fetch('/api/day_status'); const rows = await r.json();
  DAY_ROWS = rows;
  PUBLISHED_TITLES = new Set(rows.filter(r=>r.youtube).map(r => (r.title||'').trim().toLowerCase()));
  const el = document.getElementById('day_status_table');
  const mark = (day, field, val) => `<td class="chk ${val?'yes':'no'}" onclick="toggleDay(${day},'${field}',${!val})">${val?'&#10003;':'&#10005;'}</td>`;
  el.innerHTML = '<table><tr><th>Gun</th><th>Baslik</th><th>YT</th><th>TT</th><th>CC</th></tr>' +
    rows.map(r => `<tr><td>${r.day}</td><td>${(r.title||'').slice(0,22)}</td>` +
      mark(r.day,'youtube',!!r.youtube) + ((r.tiktok_skip && !r.tiktok) ? '<td class="chk no" title="TikTok icin yuklenmeyecek">&#8211;</td>' : mark(r.day,'tiktok',!!r.tiktok)) + mark(r.day,'tr_cc',!!r.tr_cc) +
      '</tr>').join('') + '</table>';
  nextStep();
}
async function toggleDay(day, field, value){
  await fetch('/api/day_status', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({day, field, value})});
  loadDayStatus();
}
loadStatus(); loadVideos(); loadDayStatus();
</script>
<script>
let HISTORY = [];
function parseAuraPackage(text){
  const m = text.match(/```aura-package\\s*([\\s\\S]*?)```/);
  if(!m) return null;
  const body = m[1];
  const keys = ['TITLE','EN_SCRIPT','TR_SCRIPT','DESCRIPTION','TAGS'];
  const pkg = {};
  const re = /^(TITLE|EN_SCRIPT|TR_SCRIPT|DESCRIPTION|TAGS):\\s*([\\s\\S]*?)(?=\\n(?:TITLE|EN_SCRIPT|TR_SCRIPT|DESCRIPTION|TAGS):|$)/gm;
  let found = false;
  let mm;
  while((mm = re.exec(body)) !== null){
    pkg[mm[1].toLowerCase()] = mm[2].trim();
    found = true;
  }
  return (found && pkg.title && pkg.en_script) ? pkg : null;
}
function nextDayNumber(){
  const max = DAY_ROWS.reduce((mx, r) => Math.max(mx, r.day||0), 0);
  return max + 1;
}
async function publishPackage(pkg, btn){
  document.getElementById('rp_day').value = nextDayNumber();
  document.getElementById('rp_title').value = pkg.title;
  document.getElementById('rp_en').value = pkg.en_script;
  document.getElementById('rp_tr').value = pkg.tr_script || '';
  document.getElementById('rp_desc').value = pkg.description || '';
  document.getElementById('rp_tags').value = pkg.tags || '';
  checkTrChars();
  const oldText = btn.textContent;
  btn.textContent = 'Isleniyor...'; btn.disabled = true;
  await renderAndPublish({target: btn});
  btn.textContent = oldText; btn.disabled = false;
}
function render(){
  const c = document.getElementById('chat');
  c.innerHTML = '';
  if(HISTORY.length > 60){
    const n = document.createElement('div');
    n.className = 'sub';
    n.style.textAlign = 'center';
    n.textContent = 'Eski ' + (HISTORY.length - 60) + ' mesaj gizlendi (hizli acilis icin). Hepsi kayitli.';
    c.appendChild(n);
  }
  for(const m of HISTORY.slice(-60)){
    const div = document.createElement('div');
    div.className = 'msg ' + (m.role==='user'?'user':'aura');
    let label = m.role==='user' ? '' : '<div class="aura-label">AURA</div>';
    let saveBtn = m.role==='assistant' ? `<br><button class="save-btn" onclick="saveDoc(this)">Dosyaya kaydet</button>` : '';
    let img = m.image_file ? `<br><img src="/uploads/${m.image_file}" style="max-width:220px;border-radius:8px;margin-bottom:6px">` : '';
    const pkg = m.role==='assistant' ? parseAuraPackage(m.content) : null;
    let pkgCard = '';
    if(pkg){
      const idx = HISTORY.indexOf(m);
      const already = PUBLISHED_TITLES.has(pkg.title.trim().toLowerCase());
      pkgCard = `<div class="pkg-card"><b>&#127916; Paket algilandi:</b> ${escapeHtml(pkg.title)}` +
        (already
          ? `<br><span style="color:#3fb950">&#10003; Bu baslik zaten yayinlanmis (Gun Takibi'ne bak)</span>`
          : `<br><button class="save-btn pkg-btn" data-idx="${idx}">Render + Yayinla</button>`) +
        `</div>`;
    }
    const shown = pkg ? m.content.replace(/```aura-package[\\s\\S]*?```/, '').trim() : m.content;
    div.innerHTML = `<div class="bubble">${label}${img}${escapeHtml(shown)}${saveBtn}${pkgCard}</div>`;
    div.querySelector('.bubble').dataset.text = m.content;
    c.appendChild(div);
  }
  c.querySelectorAll('.pkg-btn').forEach(b => {
    b.onclick = () => {
      const m = HISTORY[parseInt(b.dataset.idx)];
      const pkg = parseAuraPackage(m.content);
      if(pkg) publishPackage(pkg, b);
    };
  });
  c.scrollTop = c.scrollHeight;
}
function escapeHtml(s){ const d=document.createElement('div'); d.innerText=s; return d.innerHTML; }
async function loadHistory(){
  const r = await fetch('/api/history'); HISTORY = await r.json(); render();
  loadDocs();
}
async function loadDocs(){
  const r = await fetch('/api/docs'); const docs = await r.json();
  const el = document.getElementById('doclist');
  el.innerHTML = docs.length ? docs.map(d=>`<a class="doclink" onclick="viewDoc('${d}')">${d}</a>`).join('') : '<div class="sub">henuz yok</div>';
}
async function viewDoc(name){
  const r = await fetch('/api/doc?name=' + encodeURIComponent(name));
  const j = await r.json();
  alert(j.content.slice(0, 3000));
}
async function saveDoc(btn){
  const text = btn.closest('.bubble').dataset.text;
  const r = await fetch('/api/save_doc', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({content: text})});
  const j = await r.json();
  btn.textContent = 'Kaydedildi: ' + j.name;
  loadDocs();
}
async function send(){
  const inp = document.getElementById('inp');
  const text = inp.value.trim();
  if(!text && !pendingImage) return;
  inp.value = '';
  const img = pendingImage;
  const payload = {message: text};
  if(img){ payload.image = img.b64; payload.mime = img.mime; }
  HISTORY.push({role:'user', content:text, image_file: img ? '(yukleniyor...)' : undefined}); render();
  clearPendingImage();
  document.getElementById('spin').style.display = 'block';
  const r = await fetch('/api/chat', {method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify(payload)});
  const j = await r.json();
  document.getElementById('spin').style.display = 'none';
  if(j.error){ HISTORY.push({role:'assistant', content: '[hata] ' + j.error}); render(); }
  else { await loadHistory(); }
}
function quick(key){
  document.getElementById('inp').value = '__QUICK__' + key;
  send();
}
document.getElementById('inp').addEventListener('keydown', e=>{
  if(e.key==='Enter' && !e.shiftKey){ e.preventDefault(); send(); }
});
loadHistory();
</script>
</body></html>"""


# Ozel-link korumasi: LAN/internet (tunel) uzerinden gelen HERKES token ister.
# 127.0.0.1'den TUNELSIZ dogrudan gelen (masaustu tarayici) serbest.
# GUVENLIK (2026-09-24): eskiden env var yoksa token bos kaliyor ve
# `if not ACCESS_TOKEN: return True` yuzunden masaustu kisayolundan baslatilan
# sunucu + tunel = panel (YouTube'a yayin yetkisiyle) tum internete aciktı.
# Artik token HER ZAMAN var: env > _studio/access_token.txt > otomatik uretilir.
TOKEN_FILE = os.path.join(STUDIO_DIR, "access_token.txt")


def _load_or_create_token():
    env = (os.getenv("AURA_STUDIO_TOKEN") or "").strip()
    if env:
        return env
    try:
        t = open(TOKEN_FILE, encoding="utf-8").read().strip()
        if t:
            return t
    except Exception:
        pass
    t = secrets.token_urlsafe(16)
    open(TOKEN_FILE, "w", encoding="utf-8").write(t)
    return t


ACCESS_TOKEN = _load_or_create_token()


# ---------------- ANALIZ / YORUM / HASHTAG / TIKTOK PAKETI (2026-09-25) ----------------
TIKTOK_META = os.path.join(STUDIO_DIR, "tiktok_meta.json")
if STUDIO_DIR not in sys.path:
    sys.path.insert(0, STUDIO_DIR)


def _tiktok_meta_load():
    try:
        return json.load(open(TIKTOK_META, encoding="utf-8"))
    except Exception:
        return {}


def _tiktok_meta_set(video, title, description):
    m = _tiktok_meta_load()
    m[video] = {"title": title, "description": description}
    json.dump(m, open(TIKTOK_META, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def _tiktok_meta_full():
    """Yerel kayit + (eski videolar icin) YouTube'daki ayni basligin aciklamasi."""
    meta = _tiktok_meta_load()
    try:
        import insights
        for v in insights.channel_stats()["videos"]:
            slug = re.sub(r"[^a-z0-9]+", "", v["title"].lower())[:24]
            fn = f"aura_{slug}.mp4"
            if fn in meta and "#" not in meta[fn].get("description", "") and v.get("tags"):
                meta[fn] = dict(meta[fn])  # yerel kayit hashtag'siz: YouTube etiketlerinden hashtag ekle
                meta[fn]["description"] += chr(10) * 2 + " ".join("#" + re.sub(r"\W+", "", x) for x in v["tags"][:6] if re.sub(r"\W+", "", x))
            if fn not in meta and v.get("description"):
                d = v["description"]
                if "#" not in d and v.get("tags"):  # TikTok icin YouTube etiketlerinden hashtag ekle
                    d += chr(10) * 2 + " ".join("#" + re.sub(r"\W+", "", x) for x in v["tags"][:6] if re.sub(r"\W+", "", x))
                meta[fn] = {"title": v["title"], "description": d, "source": "youtube"}
    except Exception:
        pass
    return meta


HASHTAG_SYSTEM = (
    "You pick hashtags for a short AI-productivity video by 'Aura', an openly-disclosed AI character. "
    "Return ONLY one line: 8-12 hashtags separated by single spaces, English, relevant to the actual "
    "content, mix of 3 broad + 5 niche + #AuraAI. No misleading/trending-bait tags, no emoji, no explanation."
)
COMMENT_SYSTEM = (
    "You draft replies to viewer comments for 'Aura', an openly-disclosed AI character (never pretend to be "
    "human; you may say 'I'm an AI'). Rules: English, 1-2 short sentences, warm, sharp, specific to what the "
    "person said; no fake metrics, no promises about the app or dates, no links, no sexual content, no arguing. "
    "If a comment is spam, insulting, or needs no reply, use the exact string SKIP. "
    "You CANNOT post anything; these are drafts a human will review. "
    'Return ONLY JSON: {"<comment id>": "<draft or SKIP>", ...}'
)
SEED_SYSTEM = (
    "Write ONE short top-level comment (max 180 chars, English) that Aura, an openly-disclosed AI, would leave "
    "on her own video to start a discussion: a genuine question tied to the video's topic. No emoji spam "
    "(at most one), no hashtags, no fake claims, no calls to buy/download. Return ONLY the comment text."
)


def _ai_hashtags(title, script):
    r = call_aura([{"role": "user", "content": f"TITLE: {title}\nSCRIPT: {script[:1500]}"}], HASHTAG_SYSTEM, timeout=60)
    tags = re.findall(r"#\w+", r)
    seen, out = set(), []
    for x in tags:
        if x.lower() not in seen:
            seen.add(x.lower())
            out.append(x)
    if "#auraai" not in seen:
        out.append("#AuraAI")
    return " ".join(out[:12])


def _ai_comment_drafts(video_title, comments):
    body = "\n".join(f'[{c["id"]}] {c["author"]}: {c["text"][:300]}' for c in comments)
    r = call_aura([{"role": "user", "content": f"VIDEO: {video_title}\nCOMMENTS:\n{body}"}], COMMENT_SYSTEM, timeout=90)
    m = re.search(r"\{.*\}", r, re.S)
    data = json.loads(m.group(0)) if m else {}
    ids = {c["id"] for c in comments}
    return {k: v for k, v in data.items() if k in ids and isinstance(v, str)}


def _ai_seed_comment(title, description):
    r = call_aura([{"role": "user", "content": f"VIDEO TITLE: {title}\nDESCRIPTION: {description[:600]}"}], SEED_SYSTEM, timeout=60)
    return r.strip().strip('"')[:190]


def _tiktok_zip(handler, names):
    """Secilen videolar + her biri icin aciklama .txt + tek ACIKLAMALAR.txt -> zip (TikTok Studio toplu yukleme icin)."""
    import io
    import zipfile
    have = set(_list_output_videos())
    names = [os.path.basename(n) for n in names if os.path.basename(n) in have][:15]
    if not names:
        handler.send_response(404)
        handler.end_headers()
        return
    meta = _tiktok_meta_full()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as z:
        allcap = []
        for n in names:
            z.write(os.path.join(OUTPUT_DIR, n), n)
            cap = (meta.get(n) or {}).get("description", "")
            z.writestr(os.path.splitext(n)[0] + ".txt", cap)
            allcap.append(f"=== {n} ===\n{cap}\n")
        z.writestr("ACIKLAMALAR.txt", "\n".join(allcap))
    data = buf.getvalue()
    handler.send_response(200)
    handler.send_header("Content-Type", "application/zip")
    handler.send_header("Content-Disposition", 'attachment; filename="tiktok_paket.zip"')
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    try:
        handler.wfile.write(data)
    except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
        pass


def _tiktok_pack(video):
    """TikTok paketi: indirme linki (Tailscale, anahtarli) + aciklama + YouTube linki + gun bilgisi."""
    from urllib.parse import quote
    video = os.path.basename(video)
    slug_of = lambda ttl: "aura_" + re.sub(r"[^a-z0-9]+", "", ttl.lower())[:24] + ".mp4"
    meta = (_tiktok_meta_full().get(video) or {})
    row = next((r for r in _load_day_status() if slug_of(r.get("title", "")) == video), None)
    yt_id = (row or {}).get("youtube_id")
    if not yt_id:
        try:
            import insights
            for v in insights.channel_stats()["videos"]:
                if slug_of(v["title"]) == video:
                    yt_id = v["id"]
                    break
        except Exception:
            pass
    ts = _tailscale_status()
    ip = ts.get("ip") if isinstance(ts, dict) else None
    dl = f"http://{ip}:{PORT}/download/{quote(video)}?key={ACCESS_TOKEN}" if ip else None
    return {"ok": True, "video": video, "description": meta.get("description", ""),
            "download_link": dl, "youtube_link": f"https://youtu.be/{yt_id}" if yt_id else None,
            "day": (row or {}).get("day"), "tiktok_done": bool((row or {}).get("tiktok"))}


AUDIT_SYSTEM = (
    "You are Aura, an openly-disclosed AI character, acting as a data analyst for YOUR OWN YouTube Shorts channel, "
    "talking to your operator in TURKISH (video titles/hook examples stay English). You get REAL analytics rows. "
    "Hard rules: use ONLY numbers present in the data; never invent metrics (no CTR, retention, revenue, watch time - you do not have them); "
    "the sample is tiny (dozens of videos, tens of views), so say clearly what can NOT be concluded and treat every pattern as a hypothesis; "
    "note that 'comments' may include the channel's own comments. If TikTok rows or YouTube Analytics rows (avg view % = retention) are present use them, otherwise say they are missing. You CANNOT run, publish or post anything - propose only. "
    "Output sections, concise: 1) Verinin gercekten soyledigi (max 4 madde, sayilarla) 2) Bilmedigimiz seyler 3) En fazla 3 test edilebilir hipotez "
    "(her biri: hipotez, hangi videolarla test, basari olcusu, kac video sonra karar) 4) Onumuzdeki 7 gun icin video plani (7 satir: konu, hook cumlesi ingilizce) "
    "5) Yapilmamasi gerekenler. No hype, no guarantees."
)


def _audit_digest():
    import insights
    import datetime
    st = insights.channel_stats(force=True)
    now = datetime.datetime.now()
    lines = [f"Channel: {st['channel']} | subscribers {st['subscribers']} | channel total views {st['total_views']} | videos {st['video_count']}",
             "Rows: published(UTC) | age_days | views | likes | comments | title"]
    for v in sorted(st["videos"], key=lambda x: x["published"]):
        age = (now - datetime.datetime.strptime(v["published"], "%Y-%m-%d %H:%M")).total_seconds() / 86400
        lines.append(f'{v["published"]} | {age:.1f} | {v["views"]} | {v["likes"]} | {v["comments"]} | {v["title"]}')
    try:
        tr = insights.trend(st)
        if tr["base_at"] and (tr.get("base_age_h") or 0) >= 6:
            lines.append(f"Views gained per video since snapshot {tr['base_at']}: " +
                         "; ".join(f"{v['title'][:28]}=+{tr['deltas'].get(v['id'], 0)}" for v in st["videos"][:8]))
        if len(tr["series"]) > 1:
            lines.append("Channel total views over snapshots: " + ", ".join(f"{s['at'][5:16]}={s['total_views']}" for s in tr["series"][-10:]))
    except Exception:
        pass
    try:
        tl = insights.tt_latest()
        if tl:
            lines.append("TikTok (operator-entered, manual) latest per video: views | likes | comments | shares")
            for r in tl.values():
                lines.append(f"{r['date']} | {r['title'][:40]} | {r['views']} | {r['likes']} | {r['comments']} | {r['shares']}")
    except Exception:
        pass
    try:
        if insights.analytics_status().get("authorized"):
            an = insights.analytics_report()
            titles = {v["id"]: v["title"] for v in st["videos"]}
            lines.append(f"YouTube Analytics {an['range']}: title | views | avg_view_seconds | avg_view_percentage | subs_gained")
            for r in an["rows"][:15]:
                lines.append(f"{titles.get(r['video_id'], r['video_id'])[:40]} | {r['views']} | {r['avg_sec']} | {r['avg_pct']}% | {r['subs']}")
    except Exception:
        pass
    return "\n".join(lines), st


def _ai_audit(question=""):
    digest, st = _audit_digest()
    q = question.strip() or "Verilere bakarak strateji belirle."
    reply = call_aura([{"role": "user", "content": f"OPERATOR REQUEST: {q}\n\nREAL DATA:\n{digest}"}], AUDIT_SYSTEM, timeout=120)
    return {"ok": True, "text": reply, "digest": digest}


CANDIDATE_SYSTEM = (
    "You are Aura, an openly-disclosed AI character writing YouTube Shorts / TikTok scripts for YOUR OWN channel. "
    "Return ONLY a JSON array of exactly 3 objects with keys: title, en_script, tr_script, description, tags, format, rationale. "
    "Rules: everything except tr_script and rationale is ENGLISH (rationale in Turkish, 1 sentence, referencing the given data). "
    "tr_script is the Turkish subtitle translation with EXACTLY the same number of sentences as en_script. "
    "title max 35 chars, no emoji/hashtags, must NOT resemble any EXISTING TITLE. "
    "en_script: 9-12 short sentences (each under 70 chars), 40-58 words total, first sentence is a hook of at most 10 words, "
    "NEVER a generic opener ('Hi everyone', 'Today I'll...', 'In this video...'). "
    "The LAST sentence MUST reuse a concrete word or idea from the first sentence (the loop) AND ask the viewer a real question - "
    "this is not optional: on 2026-10-02 the one script that did this properly (day 38, 'AI Is Not Your Toy Anymore') hit "
    "232.5% average view percentage, by far the channel's best real result, so every candidate must use this same loop technique. "
    "Use ONLY numbers that appear in the DATA; never invent statistics, quotes, testimonials, guarantees or urgency. "
    "You are an AI and never pretend to be human. No sexual content. "
    "NEVER make claims about your own abilities, learning, training, feelings or bias (no 'I process', 'I analyze', 'I improve', 'my model', 'I feel'); "
    "you may only state facts that are in the DATA or universally true. No filler sentences: every sentence must carry a concrete tip, a real number from DATA, or the question. "
    "Do not repeat the topic of any EXISTING TITLE even with different words (e.g. 80/20 Pareto and 3-line context were already done). "
    "Prefer a NEW angle that has not been covered; for the template format give ONE concrete copy-paste prompt line the viewer can use. "
    "The 3 candidates must test DIFFERENT formats (one of: transparency, template, identity, directive, agenda - agenda means reacting "
    "to a real AI news event, only use it if the DATA actually contains a real cited news item, never invent one). "
    "format = the format key you chose. description: 2-3 sentences + 4-5 hashtags incl. #AuraAI. tags: comma separated words without #."
)

AGENDA_CANDIDATE_SYSTEM = (
    "You are Aura, an openly-disclosed AI character writing ONE YouTube Shorts / TikTok script reacting to REAL, CURRENT AI news "
    "for your own channel. You were given live Google Search results below the prompt - use ONLY facts, names, dates and numbers "
    "that actually appear in those search results. If the results are too vague or you are not sure a detail is correct, leave it "
    "out rather than guessing. Never invent a statistic, quote, company name or date that is not directly supported by the search "
    "results. Return ONLY a single JSON object with keys: title, en_script, tr_script, description, tags, rationale, sources_used "
    "(a short list of which facts from the search results you used, in Turkish, 1-2 sentences). "
    "format is always 'agenda'. "
    "title max 35 chars, no emoji/hashtags, must NOT resemble any EXISTING TITLE. "
    "en_script: 9-12 short sentences (each under 70 chars), 40-58 words total, first sentence is a hook of at most 10 words stating "
    "the real news directly (no 'Today I'll talk about...'), the LAST sentence must reuse a concrete word from the first sentence "
    "(the loop) and ask the viewer a real opinion question about the news. "
    "You are an AI, never pretend to be human. No sexual content. No claims about your own abilities/learning/feelings. "
    "SUBSCRIBER TEST (2026-10-10): the SECOND-TO-LAST sentence must be exactly: "
    "'Follow - I cover one real AI story like this every day.' (it names what the channel is). "
    "The LAST sentence stays the loop + opinion question. This adds ~11 words, so en_script may be 10-13 sentences / up to 68 words total. "
    "tr_script: Turkish subtitle translation, EXACTLY the same number of sentences as en_script, each sentence under 72 characters. "
    "description: 2-3 sentences + 4-5 hashtags incl. #AuraAI. tags: comma separated words without #."
)


PUBLISH_LOCK = threading.Lock()

ACTION_SYSTEM = (
    "You are Aura, an openly-disclosed AI character managing the growth of YOUR OWN YouTube/TikTok channel together with a human operator. "
    "From the REAL DATA build an ACTION PLAN as a JSON array of 3-6 objects. Allowed types:\n"
    '{"type":"experiment","name":"...","hypothesis":"...","format":"transparency|template|identity|directive|agenda|other","target_n":3-6,"why":"..."}\n'
    '{"type":"draft","title":"...","en_script":"...","tr_script":"...","description":"...","tags":"a,b,c","format":"...","why":"..."}\n'
    '{"type":"retag","video_id":"<an id from the VIDEO IDS list>","format":"...","why":"..."} (only if a video is clearly misclassified)\n'
    "Rules: max 2 drafts, max 2 experiments. 'why' is ONE Turkish sentence that cites a number from the data. "
    "Draft rules: everything English except tr_script (Turkish subtitle translation with EXACTLY the same number of sentences); "
    "title max 35 chars, no emoji/hashtags, not resembling any existing title or topic; en_script 9-12 short sentences (each under 70 chars), 40-58 words, "
    "first sentence a hook of at most 10 words, ends with a call to comment or a question; give ONE concrete copy-paste tip when format is template; "
    "use ONLY numbers found in DATA; NEVER claim anything about your own abilities, learning, feelings or bias; never invent statistics, quotes or urgency; "
    "you are an AI and never pretend to be human; no sexual content; description = 2-3 sentences + 4-5 hashtags incl. #AuraAI. "
    "Every action is only a PROPOSAL; a human applies it. Output ONLY the JSON array."
)


def _gm_context():
    import growth
    import insights
    import statistics
    st = insights.channel_stats()
    rows = None
    try:
        if insights.analytics_status().get("authorized"):
            rows = insights.analytics_report()["rows"]
    except Exception:
        rows = None
    tt = insights.tt_latest()
    fs = growth.format_stats_full(st, rows, tt)
    med = statistics.median([v["views"] for v in st["videos"]]) if st["videos"] else 0
    return st, rows, tt, fs, med


def _growth_state():
    import growth
    import insights
    st, rows, tt, fs, med = _gm_context()
    lst = growth.reports_list()
    best = max(st["videos"], key=lambda v: v["views"]) if st["videos"] else None
    tt_total = sum(r["views"] for r in tt.values())
    return {"ok": True, **fs, "median_views": med,
            "kpi": {"subs": st["subscribers"], "total_views": st["total_views"], "videos": st["video_count"],
                    "best_title": best["title"] if best else "", "best_views": best["views"] if best else 0,
                    "tt_entries": len(tt), "tt_total_views": tt_total,
                    "snapshots": len(insights.trend(st)["series"]),
                    "retention_on": rows is not None},
            "experiments": growth.exp_eval_all(st), "drafts": growth.drafts_list()[::-1],
            "actions": growth.actions_list("bekliyor"), "reports": lst,
            "report_age_days": growth.report_age_days(),
            "latest_report": ({"name": lst[0], "text": growth.report_read(lst[0])} if lst else None)}


def _growth_actions():
    import growth
    digest, st = _audit_digest()
    _st, rows, tt, fs, med = _gm_context()
    ftxt = "\n".join(
        f"{g['format']}: n={g['n']}, YT median views={g['median_views']}, max={g['max_views']}, median retention%={g['median_retention']}, "
        f"TikTok(manual) n={g['tt_n']}, median views={g['tt_median_views']}" for g in fs["groups"])
    ids = "\n".join(f"{v['id']} | {v['format']} | {v['title']}" for v in fs["videos"])
    exps = "\n".join(f"{e['name']} ({e['format']}): {e['verdict']}" for e in growth.exp_eval_all(st)) or "(none)"
    existing = [v["title"] for v in st["videos"]] + [d["title"] for d in growth.drafts_list()]
    prompt = ("DATA:\n" + digest + "\n\nFORMAT STATS (tiny samples, hypotheses only):\n" + ftxt + "\n\nACTIVE EXPERIMENTS:\n" + exps +
              "\n\nVIDEO IDS:\n" + ids + "\n\nEXISTING TITLES/DRAFTS (do not repeat):\n" + "\n".join(existing) + "\n\nWrite the action plan now.")
    raw = call_aura([{"role": "user", "content": prompt}], ACTION_SYSTEM, timeout=180)
    m = re.search(r"\[.*\]", raw, re.S)
    items = json.loads(m.group(0)) if m else []
    known = {v["id"] for v in st["videos"]}
    ok_items = []
    nd = ne = 0
    for it in items:
        if not isinstance(it, dict):
            continue
        ty = it.get("type")
        why = str(it.get("why", ""))[:300]
        if ty == "experiment" and ne < 2 and it.get("format") in growth.FORMATS:
            ne += 1
            ok_items.append({"type": "experiment", "name": str(it.get("name", ""))[:80], "hypothesis": str(it.get("hypothesis", ""))[:300],
                             "format": it["format"], "target_n": int(it.get("target_n") or 3), "why": why})
        elif ty == "draft" and nd < 2 and it.get("title") and it.get("en_script"):
            nd += 1
            pf = growth.preflight(str(it["title"]), str(it["en_script"]), str(it.get("tr_script", "")), str(it.get("description", "")), existing, med)
            ok_items.append({"type": "draft", "title": str(it["title"])[:60], "en_script": str(it["en_script"]), "tr_script": str(it.get("tr_script", "")),
                             "description": str(it.get("description", "")), "tags": str(it.get("tags", "")),
                             "format": it.get("format") if it.get("format") in growth.FORMATS else "other", "why": why, "preflight": pf})
        elif ty == "retag" and it.get("video_id") in known and it.get("format") in growth.FORMATS:
            ok_items.append({"type": "retag", "video_id": it["video_id"], "format": it["format"], "why": why,
                             "title": next((v["title"] for v in st["videos"] if v["id"] == it["video_id"]), "")})
    added = growth.actions_add(ok_items)
    return {"ok": True, "added": len(added)}


def _growth_apply(aid):
    import growth
    a = growth.action_get(aid)
    if not a or a["status"] != "bekliyor":
        return {"ok": False, "error": "Aksiyon bulunamadi ya da zaten islendi."}
    ty = a["type"]
    if ty == "experiment":
        _st, _r, _t, _fs, med = _gm_context()
        e = growth.exp_add(a["name"], a["hypothesis"], a["format"], a["target_n"], med)
        res = f"deney baslatildi ({e['id']})"
    elif ty == "draft":
        d = growth.draft_add({**a, "rationale": a.get("why", "")})
        res = f"taslak olusturuldu ({d['id']})"
    elif ty == "retag":
        growth.tag_set(a["video_id"], a["format"])
        res = "etiket guncellendi"
    else:
        return {"ok": False, "error": "Bilinmeyen aksiyon turu."}
    growth.action_set(aid, "uygulandi", res)
    return {"ok": True, "result": res}


def _growth_report():
    import growth
    a = _ai_audit("Haftalik rapor: verilere dayanarak bu haftanin ozeti, ne ogrendik (sadece veriden), gelecek hafta plani. YouTube ve TikTok (elle girilen) birlikte.")
    st, rows, tt, fs, med = _gm_context()
    tbl = ["| Format | YT n | YT medyan izl. | YT max | YT medyan tutma % | TikTok n | TikTok medyan izl. |", "|---|---|---|---|---|---|---|"]
    for g in fs["groups"]:
        tbl.append(f"| {g['label']} | {g['n']} | {g['median_views']} | {g['max_views']} | {g['median_retention']} | {g['tt_n']} | {g['tt_median_views']} |")
    exps = growth.exp_eval_all(st)
    etxt = "\n".join(f"- **{e['name']}** ({e['format']}): {e['verdict']}" for e in exps) or "- (aktif deney yok)"
    text = (f"# Haftalik rapor - {time.strftime('%Y-%m-%d %H:%M')}\n\n## Sayilar (koddan, AI degil)\n"
            f"{a['digest'].splitlines()[0]}\n\nTikTok (elle girilen) kayit: {len(tt)} video, toplam {sum(r['views'] for r in tt.values())} izlenme\n\n" + "\n".join(tbl) +
            "\n\n_Not: her format icin n cok kucuk; tablo sonuc degil, fikir verir._\n\n## Deneyler\n" + etxt +
            "\n\n## Aura yorumu (dogrulanmamis, hipotez)\n\n" + a["text"])
    name = growth.report_save(text)
    n_act = 0
    try:
        n_act = _growth_actions()["added"]
    except Exception as e:
        print(f"  [aksiyon plani uretilemedi: {type(e).__name__}]")
    return {"ok": True, "name": name, "text": text, "actions_added": n_act}


def _growth_candidates():
    """3 aday -> taslak olarak kaydedilir (yayinlamaz)."""
    import growth
    digest, st = _audit_digest()
    _st, rows, tt, fs, med = _gm_context()
    existing = [v["title"] for v in st["videos"]] + [d["title"] for d in growth.drafts_list()]
    ftxt = "\n".join(f"{g['format']}: n={g['n']}, median views={g['median_views']}, max={g['max_views']}, median retention%={g['median_retention']}" for g in fs["groups"])
    prompt = ("DATA:\n" + digest + "\n\nFORMAT STATS (tiny samples, hypotheses only):\n" + ftxt +
              "\n\nEXISTING TITLES (do not repeat):\n" + "\n".join(existing) + "\n\nWrite the 3 candidates now.")
    raw = call_aura([{"role": "user", "content": prompt}], CANDIDATE_SYSTEM, timeout=150)
    m = re.search(r"\[.*\]", raw, re.S)
    items = json.loads(m.group(0)) if m else []
    out = []
    for it in items[:3]:
        pf = growth.preflight(str(it.get("title", "")), str(it.get("en_script", "")), str(it.get("tr_script", "")),
                              str(it.get("description", "")), existing, med)
        out.append(growth.draft_add({**it, "preflight": pf}))
    return {"ok": True, "drafts": out}


def _denormalize_list_string(s):
    """Model bazen 'EN_SCRIPT bir string olsun' kuralina ragmen cumleleri ['a.', 'b.'] bicimli bir
    Python/JS liste gorunumlu TEK string olarak dondurebiliyor (2026-10-04'te gercek bir cagrida
    gorulduk: sentences sayisi 1'e dusup preflight'in tamamini bozuyordu). Boyle gorunuyorsa ayristirip
    normal cumlelere cevirir; degilse dokunmaz."""
    s = (s or "").strip()
    if len(s) >= 2 and s[0] == "[" and s[-1] == "]":
        try:
            import ast
            parts = ast.literal_eval(s)
            if isinstance(parts, list) and all(isinstance(p, str) for p in parts):
                return " ".join(p.strip() for p in parts if p.strip())
        except Exception:
            pass
    return s


def _growth_agenda_candidate():
    """Gercek, guncel AI haberine dayanan 1 aday uretir (Google Search grounding) -> taslak olarak kaydedilir (yayinlamaz).
    DIKKAT: kaynak linkleri taslagin rationale alanina eklenir - insan/Claude Code yayindan once MUTLAKA dogrulamali,
    grounding kaynaklari bazen vertexaisearch yonlendirme linkleri olur, dogrudan okunabilir olmayabilir."""
    import growth
    import insights
    st = insights.channel_stats()
    existing = [v["title"] for v in st["videos"]] + [d["title"] for d in growth.drafts_list()]
    prompt = ("Find one real, specific, recent (last 7 days) AI industry news story (a named company/person doing something "
              "concrete - a launch, a policy move, a safety incident, a regulatory action, a resignation, etc). "
              "Then write the script as instructed in your system prompt.\n\n"
              "EXISTING TITLES (do not repeat the same news/topic if already covered):\n" + "\n".join(existing))
    text, sources = _call_gemini_grounded(prompt, AGENDA_CANDIDATE_SYSTEM)
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {"ok": False, "error": "Model JSON dondurmedi.", "raw": text[:500]}
    it = json.loads(m.group(0))
    it["format"] = "agenda"
    for k in ("en_script", "tr_script", "title", "description"):
        if k in it:
            it[k] = _denormalize_list_string(it[k])
    src_txt = " | Kaynaklar: " + "; ".join(s["uri"] for s in sources[:5]) if sources else " | UYARI: grounding kaynagi donmedi, dogrulamadan yayinlama."
    it["rationale"] = str(it.get("rationale", ""))[:280] + src_txt
    med = None
    try:
        import statistics
        med = statistics.median([v["views"] for v in st["videos"]]) if st["videos"] else 0
    except Exception:
        pass
    pf = growth.preflight(str(it.get("title", "")), str(it.get("en_script", "")), str(it.get("tr_script", "")),
                          str(it.get("description", "")), existing, med)
    draft = growth.draft_add({**it, "preflight": pf})
    return {"ok": True, "draft": draft, "sources": sources}


def _growth_render_draft(did):
    import growth
    import httpx
    d = growth.draft_get(did)
    if not d:
        return {"ok": False, "error": "Taslak yok."}
    if not PUBLISH_LOCK.acquire(blocking=False):
        return {"ok": False, "error": "Baska bir uretim/yayin suruyor, bekle."}
    try:
        slug = re.sub(r"[^a-z0-9]+", "", d["title"].lower())[:24] or "draft"
        r = httpx.post(f"{VOICE_MESH_URL}/tts", headers={"X-Voice-Key": VOICE_MESH_KEY}, json={"text": d["en_script"], "speaker": "aura"}, timeout=180)
        r.raise_for_status()
        os.makedirs(VIDEO_WORK_DIR, exist_ok=True)
        wav = os.path.join(VIDEO_WORK_DIR, f"{slug}_raw.wav")
        open(wav, "wb").write(r.content)
        from make_video import make_video as _mv
        vp = os.path.join(OUTPUT_DIR, f"aura_{slug}.mp4")
        _mv(wav, vp, d["en_script"])
        srt = None
        warn = ""
        tr_fixed, tr_note = _ensure_tr(d["en_script"], d.get("tr_script", ""))
        if tr_note:
            warn = tr_note
        growth.draft_update(did, tr_script=tr_fixed)
        d["tr_script"] = tr_fixed
        if d.get("tr_script"):
            try:
                from make_tr_srt import make_tr_srt as _mt
                sp = os.path.join(OUTPUT_DIR, f"{slug}_tr.srt")
                _mt(wav, sp, d["en_script"], d["tr_script"])
                srt = os.path.basename(sp)
            except Exception as e:
                warn = f"Turkce CC uretilemedi ({type(e).__name__}); video CC'siz yayinlanir."
        growth.draft_update(did, status="render edildi", video=os.path.basename(vp), srt=srt)
        _tiktok_meta_set(os.path.basename(vp), d["title"], d["description"])
        return {"ok": True, "video": os.path.basename(vp), "warning": warn}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}
    finally:
        PUBLISH_LOCK.release()


def _growth_publish_draft(did, day=None):
    import growth
    d = growth.draft_get(did)
    if not d or not d.get("video"):
        return {"ok": False, "error": "Once taslagi render et."}
    if d.get("status") == "yayinlandi":
        return {"ok": False, "error": "Bu taslak zaten yayinlanmis: " + str(d.get("link"))}
    rows = _load_day_status()
    dup = next((r for r in rows if r.get("youtube") and r.get("title", "").strip().lower() == d["title"].strip().lower()), None)
    if dup:
        return {"ok": False, "error": f"'{d['title']}' basligi zaten Gun {dup['day']} olarak yayinlanmis (cift yayin engellendi)."}
    if not PUBLISH_LOCK.acquire(blocking=False):
        return {"ok": False, "error": "Baska bir uretim/yayin suruyor, bekle."}
    try:
        d["tags"], d["description"], _m = _auto_tags(d["title"], d["en_script"], d.get("tags", ""), d["description"])
        growth.draft_update(did, tags=d["tags"], description=d["description"])
        desc_file = os.path.join(STUDIO_DIR, "_pub_desc_tmp.txt")
        open(desc_file, "w", encoding="utf-8").write(d["description"])
        cmd = [sys.executable, PUBLISH_SCRIPT, "--video", os.path.join(OUTPUT_DIR, d["video"]), "--title", d["title"],
               "--description-file", desc_file, "--privacy", "public"]
        if d.get("tags"):
            cmd += ["--tags", ",".join(_normalize_tags(d["tags"]))]
        if d.get("srt"):
            cmd += ["--tr-srt", os.path.join(OUTPUT_DIR, d["srt"])]
        pr = subprocess.run(cmd, capture_output=True, text=True, timeout=480)
        out = (pr.stdout or "") + "\n" + (pr.stderr or "")
        m = re.search(r"Link:\s*(\S+)", out)
        if pr.returncode != 0 or not m:
            return {"ok": False, "error": "Yayin basarisiz: " + out[-400:]}
        link = m.group(1)
        vid = link.rstrip("/").split("/")[-1].split("?")[0]
        nday = int(day) if day else (max([r.get("day", 0) for r in rows] or [0]) + 1)
        tr_ok = _verify_tr(vid, os.path.join(OUTPUT_DIR, d["srt"]) if d.get("srt") else None)
        rows.append({"day": nday, "title": d["title"], "youtube": True, "youtube_id": vid, "tiktok": False, "tr_cc": bool(tr_ok)})
        rows.sort(key=lambda r: r.get("day", 0))
        _save_day_status(rows)
        growth.draft_update(did, status="yayinlandi", link=link)
        return {"ok": True, "link": link, "day": nday, "tr_cc": bool(tr_ok)}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {str(e)[:200]}"}
    finally:
        PUBLISH_LOCK.release()


def _growth_preflight(body, use_ai=False):
    import growth
    import insights
    st = insights.channel_stats()
    existing = [v["title"] for v in st["videos"]]
    med = __import__("statistics").median([v["views"] for v in st["videos"]]) if st["videos"] else 0
    pf = growth.preflight(body.get("title", ""), body.get("en_text", ""), body.get("tr_text", ""), body.get("description", ""), existing, med)
    if use_ai and body.get("en_text"):
        try:
            pf["ai"] = call_aura([{"role": "user", "content":
                f"Baseline: channel median views {med}, 26 tiny-sample videos. TITLE: {body.get('title', '')}\nSCRIPT: {body.get('en_text', '')}\n"
                "Turkce, en fazla 4 madde: kanca gucu, tekrar/eskimis kalip riski, ne degistirilmeli. Izlenme TAHMINI verme, garanti verme."}],
                AURA_SYSTEM, timeout=90)
        except Exception as e:
            pf["ai"] = f"(AI yorumu alinamadi: {type(e).__name__})"
    return {"ok": True, **pf}


def _serve_download(handler, name):
    safe = os.path.basename(name)
    fp = os.path.join(OUTPUT_DIR, safe)
    if not safe.lower().endswith((".mp4", ".srt")) or not os.path.isfile(fp):
        handler.send_response(404)
        handler.end_headers()
        return
    data = open(fp, "rb").read()
    handler.send_response(200)
    handler.send_header("Content-Type", "video/mp4" if safe.lower().endswith(".mp4") else "text/plain; charset=utf-8")
    handler.send_header("Content-Disposition", f'attachment; filename="{safe}"')
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    try:
        handler.wfile.write(data)
    except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
        pass


# ---------------- KOD MODU (2026-09-24, operator karari: Claude limiti dolunca da kodlayabilmek) ----------------
# GUVENLIK MODELI: bu uc noktalar dosya yazip yeniden baslatabildigi icin = uzaktan kod calistirma
# demek. Bu yuzden (1) HERKESE ACIK Cloudflare tunelinden ASLA erisilemez, sadece PC'nin kendisi ve
# Tailscale (100.64.0.0/10, ozel ag); (2) sadece bu proje klasorundeki, izinli uzantili, gizli
# olmayan MEVCUT dosyalar; (3) her kayitta otomatik yedek + sozdizimi/import kontrolu;
# (4) keyfi shell komutu YOK; (5) bozuk duzenleme paneli acilmaz hale getirirse safe_restart.py
# son yedegi kendisi geri yukler.
import ipaddress
import warnings

BACKUP_DIR = os.path.join(STUDIO_DIR, "_backups")
_CODE_EXTS = {".py", ".bat", ".md", ".txt", ".html", ".js", ".css", ".json"}
_CODE_DENY_NAMES = {"client_secret.json", "token.json", "access_token.txt", "code_pin.txt", ".env",
                    "conversation.json", "safe_restart.py"}
_CODE_SKIP_DIRS = {"output", "uploads", "_video_work", "_backups", "__pycache__", ".git", "documents"}
CODE_PIN_FILE = os.path.join(STUDIO_DIR, "code_pin.txt")
_pin_fails = {"n": 0, "until": 0.0}


def _code_pin():
    """Kod modu ikinci kilit: tabletin/telefonun token cerezi ele gecse bile kod acilamasin."""
    try:
        v = open(CODE_PIN_FILE, encoding="utf-8").read().strip()
        if v:
            return v
    except Exception:
        pass
    v = "".join(secrets.choice("0123456789") for _ in range(8))
    with open(CODE_PIN_FILE, "w", encoding="utf-8") as f:
        f.write(v)
    return v


_EDIT_RE = re.compile(r"<<<<<<< SEARCH\n(.*?)\n=======\n(.*?)\n>>>>>>> REPLACE", re.S)

CODE_SYSTEM = (
    "You are a careful coding assistant inside the operator's PRIVATE control panel for the "
    "'Aura Influencer' project (Python http.server app: aura_studio.py + _studio/*.py helpers). "
    "You can only PROPOSE edits. The panel shows them to the operator, who clicks Apply; the panel "
    "then backs up, syntax-checks and writes the file. NEVER claim you ran, applied, tested, "
    "deployed or published anything - you have no tools. Only talk in proposal tense.\n"
    "Reply in Turkish: 1-4 short sentences explaining the change, then the edits.\n"
    "EDIT FORMAT (exactly, one block per change; SEARCH must be an EXACT, UNIQUE excerpt of the "
    "current file including indentation; keep changes minimal):\n"
    "<<<<<<< SEARCH\n<exact existing text>\n=======\n<replacement text>\n>>>>>>> REPLACE\n"
    "Hard-won gotchas you MUST respect:\n"
    "- aura_studio.py embeds the whole web UI as a NORMAL (non-raw) triple-quoted Python string "
    "(PAGE). Inside PAGE, a backslash escape is consumed by PYTHON first: to get \\n in the "
    "browser's JavaScript you must write \\\\n in the source; the same for \\\\s, \\\\d, \\\\25cf. "
    "A single-backslash n inside PAGE becomes a REAL newline and breaks JS single-quoted strings. "
    "Prefer avoiding backslashes in JS (use String.fromCharCode(10), or template literals).\n"
    "- .bat files must stay Windows-safe (the panel forces CRLF); avoid multi-line parenthesized "
    "if/else blocks, prefer goto labels.\n"
    "- Never touch secrets (client_secret.json, token.json, access_token.txt, .env).\n"
    "- Never invent file contents you were not shown. If the request needs another file, say which one.\n"
    "- No sexual content, no fake metrics/testimonials/urgency, Aura is always disclosed as AI "
    "(project hard rules)."
)


def _code_resolve(rel):
    rel = (rel or "").replace("\\", "/").lstrip("/")
    root = os.path.realpath(HERE)
    full = os.path.realpath(os.path.join(HERE, rel))
    if not full.startswith(root + os.sep):
        raise ValueError("Yol proje klasoru disinda.")
    if any(p in _CODE_SKIP_DIRS for p in rel.split("/")[:-1]):
        raise ValueError("Bu klasordeki dosyalar duzenlenemez.")
    name = os.path.basename(full)
    if name in _CODE_DENY_NAMES or os.path.splitext(name)[1].lower() not in _CODE_EXTS:
        raise ValueError("Bu dosya adi/turu duzenlenemez.")
    if not os.path.isfile(full):
        raise ValueError("Dosya yok (yeni dosya olusturma desteklenmiyor).")
    return full


def _code_list():
    out = []
    root = os.path.realpath(HERE)
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in _CODE_SKIP_DIRS and not d.startswith(".")]
        for fn in fns:
            full = os.path.join(dp, fn)
            rel = os.path.relpath(full, root).replace("\\", "/")
            try:
                _code_resolve(rel)
                if os.path.getsize(full) <= 400_000:
                    out.append(rel)
            except Exception:
                pass
    return sorted(out)


def _code_read(rel):
    full = _code_resolve(rel)
    raw = open(full, "rb").read()
    if len(raw) > 400_000:
        raise ValueError("Dosya cok buyuk (400 KB ustu).")
    text = raw.decode("utf-8")
    return full, text.replace("\r\n", "\n"), ("\r\n" in text)


def _code_check(full, text):
    ext = os.path.splitext(full)[1].lower()
    if ext == ".json":
        try:
            json.loads(text)
        except Exception as e:
            return f"Gecersiz JSON: {e}"
    if ext != ".py":
        return None
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", SyntaxWarning)
            compile(text, full, "exec")
    except SyntaxError as e:
        return f"Sozdizimi hatasi (satir {e.lineno}): {e.msg}"
    except Exception as e:
        return f"Derleme hatasi: {type(e).__name__}: {e}"
    if os.path.basename(full) == "aura_studio.py":
        # Import-time hatalarini (NameError vb.) yakalamak icin ADAYI ayri surecte yukle (main() calismaz).
        tmp = os.path.join(HERE, "_aura_studio_check_tmp.py")
        try:
            with open(tmp, "w", encoding="utf-8", newline="") as f:
                f.write(text)
            code = ("import importlib.util as u;s=u.spec_from_file_location('chk',r'%s');"
                    "m=u.module_from_spec(s);s.loader.exec_module(m)" % tmp)
            r = subprocess.run([sys.executable, "-c", code], cwd=HERE, capture_output=True,
                               text=True, timeout=40)
            if r.returncode != 0:
                return "Ice aktarma (import) hatasi: " + (r.stderr or "")[-600:]
        except subprocess.TimeoutExpired:
            return "Ice aktarma kontrolu zaman asimina ugradi."
        finally:
            try:
                os.remove(tmp)
            except Exception:
                pass
    return None


def _code_write(rel, new_text):
    full, _old, crlf = _code_read(rel)
    err = _code_check(full, new_text)
    if err:
        return {"ok": False, "error": err}
    os.makedirs(BACKUP_DIR, exist_ok=True)
    bak = os.path.join(BACKUP_DIR, f"{os.path.basename(full)}.{time.strftime('%Y%m%d-%H%M%S')}.bak")
    shutil.copy2(full, bak)
    ext = os.path.splitext(full)[1].lower()
    out = new_text.replace("\n", "\r\n") if (crlf or ext == ".bat") else new_text
    with open(full, "w", encoding="utf-8", newline="") as f:
        f.write(out)
    return {"ok": True, "backup": os.path.basename(bak)}


def _code_backups(rel):
    full = _code_resolve(rel)
    name = os.path.basename(full)
    if not os.path.isdir(BACKUP_DIR):
        return []
    return sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith(name + ".") and f.endswith(".bak")],
                  reverse=True)


def _code_restore(rel, bakname):
    full = _code_resolve(rel)
    name = os.path.basename(full)
    if os.path.basename(bakname) != bakname or not (bakname.startswith(name + ".") and bakname.endswith(".bak")):
        return {"ok": False, "error": "Gecersiz yedek adi."}
    p = os.path.join(BACKUP_DIR, bakname)
    if not os.path.isfile(p):
        return {"ok": False, "error": "Yedek bulunamadi."}
    text = open(p, "rb").read().decode("utf-8").replace("\r\n", "\n")
    return _code_write(rel, text)


def _code_ai(rel, instruction, history, image_b64=None, image_mime=None):
    _full, text, _crlf = _code_read(rel)
    msgs = []
    for h in (history or [])[-4:]:
        if h.get("role") in ("user", "assistant") and isinstance(h.get("content"), str):
            msgs.append({"role": h["role"], "content": h["content"][:3000]})
    msgs.append({"role": "user", "content":
                 f"DOSYA: {rel}\n\n--- MEVCUT ICERIK BASLANGIC ---\n{text}\n--- MEVCUT ICERIK BITIS ---\n\nISTEK: {instruction}"})
    if image_b64:
        msgs[-1]["image_b64"] = image_b64
        msgs[-1]["image_mime"] = image_mime or "image/png"
    reply = call_aura(msgs, CODE_SYSTEM, prefer=_ai_settings()["code_prefer"], timeout=150)
    edits = [{"search": a, "replace": b} for a, b in _EDIT_RE.findall(reply)]
    return {"ok": True, "reply": reply, "edits": edits}


def _code_apply(rel, edits):
    _full, text, _crlf = _code_read(rel)
    new = text
    for i, e in enumerate(edits or []):
        s, r = e.get("search", ""), e.get("replace", "")
        if not s.strip():
            return {"ok": False, "error": f"Duzenleme {i + 1}: bos SEARCH."}
        n = new.count(s)
        if n != 1:
            return {"ok": False, "error": f"Duzenleme {i + 1}: SEARCH metni dosyada {n} kez bulundu (tam 1 olmali). "
                                          "Dosya degismis olabilir - oneriyi yeniden iste."}
        new = new.replace(s, r, 1)
    if new == text:
        return {"ok": False, "error": "Degisiklik yok."}
    return _code_write(rel, new)


def _restart_panel():
    """Paneli GUVENLI yeniden baslatir: ayri safe_restart.py sureci eskisi kapaninca yenisini
    baslatir; yeni surec saglikli acilmazsa aura_studio.py'nin son yedegini geri yukleyip tekrar dener."""
    launcher = os.path.join(STUDIO_DIR, "safe_restart.py")
    if not os.path.isfile(launcher):
        return {"ok": False, "error": "safe_restart.py bulunamadi."}
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "DETACHED_PROCESS", 0)
    with open(os.path.join(STUDIO_DIR, "_safe_restart_log.txt"), "a", encoding="utf-8") as lf:
        subprocess.Popen([sys.executable, launcher, str(PORT)], cwd=HERE,
                          stdout=lf, stderr=subprocess.STDOUT, creationflags=creationflags)
    threading.Timer(1.5, lambda: os._exit(0)).start()
    return {"ok": True, "note": "Panel yeniden basliyor (10-40 sn); sayfa kendiliginden yenilenecek."}


def _open_app_window(url):
    """Paneli tarayici sekmesi yerine ayri bir 'masaustu uygulamasi' penceresinde acar (Chrome/Edge --app)."""
    if os.environ.get("AURA_NO_OPEN"):
        return
    cands = [r"C:\Program Files\Google\Chrome\Application\chrome.exe",
             r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
             os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
             r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"]
    for c in cands:
        if os.path.exists(c):
            try:
                subprocess.Popen([c, f"--app={url}", "--window-size=1500,950"])
                return
            except Exception:
                pass
    import webbrowser
    try:
        webbrowser.open(url)
    except Exception:
        pass


def _agent_data():
    digest, _st = _audit_digest()
    _s, _rows, _tt, fs, _med = _gm_context()
    lines = [digest, "", "FORMAT STATS (tiny samples, hypotheses only):"]
    for g in fs["groups"]:
        lines.append(f"{g['format']}: n={g['n']} median_views={g['median_views']} max={g['max_views']} retention_median={g['median_retention']} "
                     f"tiktok_n={g['tt_n']} tiktok_median_views={g['tt_median_views']}")
    return "\n".join(lines)


import agent as _agent  # noqa: E402  (Studio Asistani: panel ici Claude-benzeri ajan)

_agent.configure(studio_dir=STUDIO_DIR, here=HERE, code_list=_code_list, code_read=_code_read, code_write=_code_write,
                 code_restore=_code_restore, code_check=_code_check, skip_dirs=_CODE_SKIP_DIRS, deny_names=_CODE_DENY_NAMES,
                 data=_agent_data, api_key=lambda: ANTHROPIC_API_KEY, usage_add=_ai_usage_add)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _code_allowed(self):
        """Kod modu: herkese acik tunel = ASLA; sadece loopback (PC) ve Tailscale (100.64.0.0/10);
        ustune 8 haneli PIN (X-Code-Pin basligi) - 5 yanlis denemede 60 sn kilit."""
        if self.headers.get("Cf-Connecting-Ip") or self.headers.get("Cf-Ray"):
            return False
        ip = self.client_address[0]
        if not self._code_net_ok(ip):
            return False
        if time.time() < _pin_fails["until"]:
            return False
        given = self.headers.get("X-Code-Pin", "")
        if secrets.compare_digest(given.encode(), _code_pin().encode()):
            _pin_fails["n"] = 0
            return True
        _pin_fails["n"] += 1
        if _pin_fails["n"] >= 5:
            _pin_fails["until"] = time.time() + 60
            _pin_fails["n"] = 0
        return False

    def _code_net_ok(self, ip):
        if ip in ("127.0.0.1", "::1"):
            return True
        try:
            return ipaddress.ip_address(ip) in ipaddress.ip_network("100.64.0.0/10")
        except Exception:
            return False

    def _json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        try:
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            # Istemci (tarayici sekmesi kapatildi/yenilendi) uzun bir islem
            # (ornegin Voice Mesh yeniden baslatma, birkac dakika surebilir)
            # bitmeden ayrildi - sonucu artik gonderemeyiz, sorun degil.
            pass

    def _authorized(self, u):
        # TikTok'un OAuth yonlendirmesi bizim ?key= tokenimizi tasiyamaz (redirect_uri TikTok'ta
        # harfi harfine kayitli, TikTok kendi ?code=&state= parametrelerini ekliyor). Guvenlik, token
        # yerine exchange_code()'un state (CSRF) kontrolune devrediliyor - gecerli bir yetkilendirme
        # akisi kendi _pending_state'imizle baslamadiysa code hic degismiyor.
        if u.path == "/tiktok_callback":
            return True
        # BULUNDU (2026-09-19): cloudflared quick tunnel, uzak ziyaretcinin
        # istegini yerel makineden localhost:8795'e proxy'liyor - yani
        # self.client_address her zaman 127.0.0.1 gorunuyor, tunel uzerinden
        # gelen HERKES bu IP-bazli serbest gecisten faydalaniyordu (token
        # tamamen etkisiz kaliyordu). Cloudflare, gercek ziyaretciyi Cf-*
        # basliklarinda tasir - bu basliklardan biri varsa istek tunelden
        # geliyor demektir, IP-bazli serbest gecis o zaman UYGULANMAZ.
        is_tunneled = bool(
            self.headers.get("Cf-Connecting-Ip") or self.headers.get("Cf-Ray")
        )
        if not is_tunneled and self.client_address[0] in ("127.0.0.1", "::1"):
            return True
        qtok = parse_qs(u.query).get("key", [""])[0]
        if qtok == ACCESS_TOKEN:
            return True
        cookie = self.headers.get("Cookie", "")
        return f"aura_key={ACCESS_TOKEN}" in cookie

    def _deny(self):
        body = b"<h3>Yetkisiz - gecerli bir link kullanmalisin.</h3>"
        self.send_response(401)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if not self._authorized(u):
            return self._deny()
        if u.path == "/":
            body = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            qtok = parse_qs(u.query).get("key", [""])[0]
            if ACCESS_TOKEN and qtok == ACCESS_TOKEN:
                self.send_header(
                    "Set-Cookie",
                    f"aura_key={ACCESS_TOKEN}; Max-Age=2592000; Path=/; SameSite=Lax")
            self.end_headers()
            self.wfile.write(body)
        elif u.path == "/tiktok_callback":
            import tiktok_api
            q = parse_qs(u.query)
            code = q.get("code", [""])[0]
            state = q.get("state", [""])[0]
            err = q.get("error_description", q.get("error", [""]))[0]
            _tu = _tunnel_status(check_ready=False).get("url") or ""
            redirect_uri = f"{_tu}/tiktok_callback" if _tu else ""
            try:
                if err:
                    raise RuntimeError(err)
                if not code or not redirect_uri:
                    raise RuntimeError("code veya redirect_uri eksik.")
                tiktok_api.exchange_code(code, redirect_uri, state)
                html = "<h2>TikTok hesabi baglandi.</h2><p>Bu sekmeyi kapatabilirsin, panele don.</p>"
            except Exception as e:
                html = f"<h2>Baglanti basarisiz</h2><p>{type(e).__name__}: {e}</p>"
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif u.path == "/api/tiktok_connect":
            import tiktok_api
            try:
                _tu = _tunnel_status(check_ready=False).get("url")
                if not _tu:
                    raise RuntimeError("Once tuneli baslat (Telefon Erisimi > Tuneli Baslat).")
                redirect_uri = f"{_tu}/tiktok_callback"
                self._json({"ok": True, "url": tiktok_api.auth_url(redirect_uri)})
            except Exception as e:
                self._json({"ok": False, "error": f"{type(e).__name__}: {e}"})
        elif u.path == "/api/tiktok_connect_status":
            import tiktok_api
            self._json({"client_configured": tiktok_api.client_configured(), "connected": tiktok_api.connected()})
        elif u.path == "/api/history":
            self._json(_load_conv())
        elif u.path == "/api/docs":
            self._json(_list_docs())
        elif u.path == "/api/status":
            content = _read_claude_md()
            self._json({"tail": content[-6000:]})
        elif u.path == "/api/videos":
            self._json(_list_output_videos())
        elif u.path == "/api/day_status":
            self._json(_load_day_status())
        elif u.path == "/api/voice_mesh_status":
            h = _voice_mesh_health()
            self._json({"up": bool(h and h.get("model_loaded")), "detail": h})
        elif u.path == "/api/tunnel_status":
            self._json(_tunnel_status())
        elif u.path == "/api/tailscale_status":
            self._json(_tailscale_status())
        elif u.path.startswith("/uploads/"):
            safe = os.path.basename(u.path[len("/uploads/"):])
            fpath = os.path.join(UPLOADS_DIR, safe)
            if not os.path.exists(fpath):
                self.send_response(404); self.end_headers(); return
            ext = os.path.splitext(safe)[1].lower()
            ctype = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                     ".gif": "image/gif", ".webp": "image/webp"}.get(ext, "application/octet-stream")
            data = open(fpath, "rb").read()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif u.path == "/api/doc":
            name = parse_qs(u.query).get("name", [""])[0]
            safe = os.path.basename(name)
            try:
                content = open(os.path.join(DOCS_DIR, safe), encoding="utf-8").read()
                self._json({"content": content})
            except Exception as e:
                self._json({"content": f"[okunamadi: {e}]"})
        elif u.path == "/api/tiktok_meta":
            self._json(_tiktok_meta_full())
        elif u.path == "/api/tiktok_pack":
            try:
                self._json(_tiktok_pack(parse_qs(u.query).get("video", [""])[0]))
            except Exception as e:
                self._json({"ok": False, "error": f"{type(e).__name__}: {e}"})
        elif u.path == "/api/tiktok_zip":
            _tiktok_zip(self, parse_qs(u.query).get("v", [""])[0].split(","))
        elif u.path == "/api/ai_usage":
            self._json({"usage": _ai_usage_get(), "code_prefer": _ai_settings()["code_prefer"]})
        elif u.path.startswith("/download/"):
            _serve_download(self, u.path[len("/download/"):])
        elif u.path.startswith(("/api/insights/", "/api/growth/", "/api/tr_cc/")):
            q = parse_qs(u.query)
            try:
                import insights
                if u.path == "/api/insights/stats":
                    self._json({"ok": True, **insights.channel_stats(force=bool(q.get("force")))})
                elif u.path == "/api/insights/trend":
                    self._json({"ok": True, **insights.trend(insights.channel_stats())})
                elif u.path == "/api/insights/tiktok":
                    self._json({"ok": True, "latest": list(insights.tt_latest().values()), "count": len(insights.tt_load())})
                elif u.path == "/api/insights/analytics":
                    st = insights.analytics_status()
                    if st.get("authorized"):
                        try:
                            self._json({"ok": True, "status": st, **insights.analytics_report()})
                        except Exception as e:
                            self._json({"ok": True, "status": st, "error": f"{type(e).__name__}: {str(e)[:300]}", "rows": []})
                    else:
                        self._json({"ok": True, "status": st, "rows": []})
                elif u.path == "/api/growth/state":
                    self._json(_growth_state())
                elif u.path == "/api/growth/report":
                    import growth
                    self._json({"ok": True, "text": growth.report_read(q.get("name", [""])[0]), "list": growth.reports_list()})
                elif u.path == "/api/insights/tiktok_sync":
                    self._json(insights.tiktok_sync(_load_day_status(), _tiktok_meta_load()))
                elif u.path == "/api/insights/retention_trend":
                    self._json({"ok": True, "trend": insights.analytics_trend(q.get("video_id", [""])[0])})
                elif u.path == "/api/insights/pins":
                    self._json({"ok": True, "pins": insights.pins_load()})
                elif u.path == "/api/insights/comments":
                    self._json({"ok": True, "comments": insights.list_comments(q.get("video_id", [""])[0])})
                else:
                    self.send_response(404)
                    self.end_headers()
            except Exception as e:
                self._json({"ok": False, "error": f"{type(e).__name__}: {str(e)[:300]}"})
        elif u.path.startswith("/api/agent/"):
            if not self._code_allowed():
                return self._json({"ok": False, "error": "Asistan reddedildi: PIN yanlis/eksik (5 hatada 60 sn kilit) veya acik tunel/yabanci ag."}, 403)
            q = parse_qs(u.query)
            if u.path == "/api/agent/poll":
                self._json(_agent.poll(int(q.get("since", ["0"])[0] or 0)))
            else:
                self.send_response(404)
                self.end_headers()
        elif u.path.startswith("/api/code/"):
            if not self._code_allowed():
                return self._json({"ok": False, "error": "Kod modu reddedildi: PIN yanlis/eksik (5 hatada 60 sn kilit) veya acik tunel/yabanci ag."}, 403)
            q = parse_qs(u.query)
            try:
                if u.path == "/api/code/files":
                    self._json({"ok": True, "files": _code_list()})
                elif u.path == "/api/code/file":
                    _f, text, _c = _code_read(q.get("path", [""])[0])
                    self._json({"ok": True, "content": text})
                elif u.path == "/api/code/backups":
                    self._json({"ok": True, "backups": _code_backups(q.get("path", [""])[0])})
                else:
                    self.send_response(404); self.end_headers()
            except Exception as e:
                self._json({"ok": False, "error": str(e)})
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        u = urlparse(self.path)
        if not self._authorized(u):
            return self._deny()
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")

        if u.path == "/api/chat":
            msg = body.get("message", "")
            img_b64_in = body.get("image")
            img_mime_in = body.get("mime", "image/png")
            conv = _load_conv()
            if msg.startswith("__QUICK__"):
                key = msg[len("__QUICK__"):]
                prompt = _QUICK_ACTIONS.get(key, msg)
            else:
                prompt = msg
            user_entry = {"role": "user", "content": prompt}
            if img_b64_in:
                try:
                    raw = base64.b64decode(img_b64_in)
                    ext = {"image/png": ".png", "image/jpeg": ".jpg", "image/gif": ".gif",
                           "image/webp": ".webp"}.get(img_mime_in, ".png")
                    fname = f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}{ext}"
                    open(os.path.join(UPLOADS_DIR, fname), "wb").write(raw)
                    user_entry["image_file"] = fname
                except Exception:
                    pass
            conv.append(user_entry)
            # API'ye gonderilecek pencere - resim dosyalarini tazeden base64'e cevir
            # (conversation.json'a devasa base64 blob'lari kalici olarak yazilmasin).
            api_msgs = []
            for m in conv[-12:]:
                entry = {"role": m["role"], "content": m["content"]}
                if m.get("image_file"):
                    try:
                        raw = open(os.path.join(UPLOADS_DIR, m["image_file"]), "rb").read()
                        entry["image_b64"] = base64.b64encode(raw).decode()
                        ext = os.path.splitext(m["image_file"])[1].lower()
                        entry["image_mime"] = {".png": "image/png", ".jpg": "image/jpeg",
                                                ".jpeg": "image/jpeg", ".webp": "image/webp",
                                                ".gif": "image/gif"}.get(ext, "image/png")
                    except Exception:
                        pass
                api_msgs.append(entry)
            try:
                reply = call_aura(api_msgs, AURA_SYSTEM)
                conv.append({"role": "assistant", "content": reply})
                _save_conv(conv)
                self._json({"reply": reply})
            except Exception as e:
                self._json({"error": f"{type(e).__name__}: {e}"}, 500)

        elif u.path == "/api/publish_youtube":
            video = os.path.basename(body.get("video", ""))
            title = body.get("title", "")
            desc = body.get("description", "")
            srt = os.path.basename(body.get("tr_srt", "") or "")
            video_path = os.path.join(OUTPUT_DIR, video)
            if not os.path.exists(video_path):
                return self._json({"ok": False, "error": f"video bulunamadi: {video_path}"})
            desc_file = os.path.join(STUDIO_DIR, "_pub_desc_tmp.txt")
            open(desc_file, "w", encoding="utf-8").write(desc)
            cmd = [sys.executable, PUBLISH_SCRIPT, "--video", video_path,
                   "--title", title, "--description-file", desc_file]
            if srt:
                srt_path = os.path.join(OUTPUT_DIR, srt)
                if os.path.exists(srt_path):
                    cmd += ["--tr-srt", srt_path]
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=480)
                out = (r.stdout or "") + "\n" + (r.stderr or "")
                self._json({"ok": r.returncode == 0, "output": out[-4000:]})
            except subprocess.TimeoutExpired as e:
                self._json({"ok": False, "error": f"zaman asimi: {e}"})
            except Exception as e:
                self._json({"ok": False, "error": f"{type(e).__name__}: {e}"})

        elif u.path == "/api/restart_voice_mesh":
            self._json(_restart_voice_mesh())

        elif u.path == "/api/start_tunnel":
            self._json(_start_tunnel())

        elif u.path == "/api/stop_tunnel":
            self._json(_stop_tunnel())

        elif u.path == "/api/day_status":
            day = int(body.get("day", 0))
            field = body.get("field", "")
            value = bool(body.get("value", False))
            if not day or field not in ("youtube", "tiktok", "tr_cc"):
                return self._json({"ok": False, "error": "gecersiz day/field"})
            rows = _load_day_status()
            row = next((r for r in rows if r.get("day") == day), None)
            if row is None:
                row = {"day": day, "title": body.get("title", ""), "youtube": False,
                       "tiktok": False, "tr_cc": False}
                rows.append(row)
                rows.sort(key=lambda r: r.get("day", 0))
            row[field] = value
            _save_day_status(rows)
            self._json({"ok": True, "rows": rows})

        elif u.path == "/api/render_and_publish":
            day = str(body.get("day", "")).strip()
            en_text = (body.get("en_text") or "").strip()
            tr_text = (body.get("tr_text") or "").strip()
            title = (body.get("title") or "").strip()
            description = body.get("description") or ""
            tags = (body.get("tags") or "").strip()
            privacy = body.get("privacy") or "public"

            warnings = []
            if any(c in _TR_CHARS for c in en_text):
                warnings.append(
                    "UYARI: Ingilizce ses scripti alaninda Turkce karakter tespit edildi - "
                    "Aura yine yanlislikla Turkce yazmis olabilir. Yayinlamadan once kontrol et."
                )
            if not en_text or not title:
                return self._json({"ok": False, "error": "en_text ve title gerekli", "warnings": warnings})

            if not body.get("force"):
                dup = next((r for r in _load_day_status()
                            if r.get("youtube") and r.get("title", "").strip().lower() == title.strip().lower()),
                           None)
                if dup:
                    return self._json({
                        "ok": False,
                        "error": f"'{title}' basligi zaten Gun {dup['day']} olarak yayinlanmis gorunuyor "
                                 "(cift yayini onlemek icin durduruldu). Gercekten farkliysa basligi "
                                 "degistir; ayniysa tekrar yayinlama.",
                        "duplicate_of_day": dup["day"], "warnings": warnings,
                    })

            # Otomatik kalite duzeltmeleri (operatorun karari, 2026-09-21):
            orig_title = title
            title = _strip_emoji(title)
            if title != orig_title:
                warnings.append(f"Duzeltme: basliktaki emoji kaldirildi -> '{title}'")
            en_text, en_split = _split_long_sentences(en_text)
            if en_split:
                warnings.append("Duzeltme: Ingilizce scriptteki uzun cumle(ler) CC guvenligi icin bolundu.")
            if tr_text:
                tr_text, tr_split = _split_long_sentences(tr_text)
                if tr_split:
                    warnings.append("Duzeltme: Turkce cevirideki uzun cumle(ler) bolundu.")
            tags, description, auto_msg = _auto_tags(title, en_text, tags, description)
            if auto_msg:
                warnings.append(auto_msg)
            if tags:
                norm = _normalize_tags(tags)
                new_tags = ",".join(norm)
                if new_tags != tags:
                    warnings.append(f"Duzeltme: etiketler normalize edildi -> {new_tags}")
                tags = new_tags

            slug = re.sub(r"[^a-z0-9]+", "", title.lower())[:24] or f"day{day or 'x'}"
            result = {"warnings": warnings, "final_title": title, "final_description": description}
            try:
                r = httpx.post(f"{VOICE_MESH_URL}/tts", headers={"X-Voice-Key": VOICE_MESH_KEY},
                                json={"text": en_text, "speaker": "aura"}, timeout=180)
                r.raise_for_status()
                wav_path = os.path.join(VIDEO_WORK_DIR, f"{slug}_raw.wav")
                open(wav_path, "wb").write(r.content)

                sys.path.insert(0, STUDIO_DIR)
                from make_video import make_video as _make_video
                video_path = os.path.join(OUTPUT_DIR, f"aura_{slug}.mp4")
                _make_video(wav_path, video_path, en_text)
                result["video"] = os.path.basename(video_path)

                srt_path = None
                tr_text, tr_note = _ensure_tr(en_text, tr_text)
                if tr_note:
                    warnings.append(tr_note)
                if tr_text:
                    try:
                        en_file = os.path.join(VIDEO_WORK_DIR, f"{slug}_en.txt")
                        tr_file = os.path.join(VIDEO_WORK_DIR, f"{slug}_tr.txt")
                        open(en_file, "w", encoding="utf-8").write(en_text)
                        open(tr_file, "w", encoding="utf-8").write(tr_text)
                        from make_tr_srt import make_tr_srt as _make_tr_srt
                        srt_path = os.path.join(OUTPUT_DIR, f"{slug}_tr.srt")
                        _make_tr_srt(wav_path, srt_path, en_text, _align_tr_to_en(en_text, tr_text))
                        result["tr_srt"] = os.path.basename(srt_path)
                    except Exception as e:
                        srt_path = None
                        warnings.append(
                            f"UYARI: Turkce CC uretilemedi ({type(e).__name__}: {e}) - "
                            "video CC'siz yayinlanacak. (Genelde EN/TR cumle sayisi "
                            "otomatik bolme sonrasi uyusmuyor demektir.)"
                        )
            except Exception as e:
                result["ok"] = False
                result["error"] = f"Render hatasi: {type(e).__name__}: {e}"
                return self._json(result)

            desc_file = os.path.join(STUDIO_DIR, "_pub_desc_tmp.txt")
            open(desc_file, "w", encoding="utf-8").write(description)
            cmd = [sys.executable, PUBLISH_SCRIPT, "--video", video_path, "--title", title,
                   "--description-file", desc_file, "--privacy", privacy]
            if tags:
                cmd += ["--tags", tags]
            if srt_path:
                cmd += ["--tr-srt", srt_path]
            try:
                pr = subprocess.run(cmd, capture_output=True, text=True, timeout=480)
                out = (pr.stdout or "") + "\n" + (pr.stderr or "")
                result["ok"] = pr.returncode == 0
                result["publish_output"] = out[-4000:]
                m = re.search(r"Link:\s*(\S+)", out)
                if m:
                    result["link"] = m.group(1)
            except subprocess.TimeoutExpired as e:
                result["ok"] = False
                result["error"] = f"Yayin zaman asimi: {e}"

            if result.get("ok") and result.get("video"):
                try:
                    _tiktok_meta_set(result["video"], title, description)
                except Exception:
                    pass
            if result.get("ok") and result.get("link"):
                vid_id = result["link"].rstrip("/").split("/")[-1].split("?")[0]
                result["tr_cc_verified"] = _verify_tr(vid_id, srt_path)
                if not result["tr_cc_verified"]:
                    warnings.append("Turkce CC su an eklenemedi (kota/ag); panel otomatik olarak tamamlayacak.")
                    result["warnings"] = warnings
            if day:
                try:
                    rows = _load_day_status()
                    drow = next((r for r in rows if r.get("day") == int(day)), None)
                    if drow is None:
                        drow = {"day": int(day), "title": title, "youtube": False,
                                "tiktok": False, "tr_cc": False}
                        rows.append(drow)
                        rows.sort(key=lambda r: r.get("day", 0))
                    drow["title"] = title
                    drow["youtube"] = bool(result.get("ok"))
                    drow["tr_cc"] = bool(result.get("tr_cc_verified"))
                    if result.get("link"):
                        drow["youtube_id"] = result["link"].rstrip("/").split("/")[-1].split("?")[0]
                    _save_day_status(rows)
                except Exception:
                    pass

            self._json(result)

        elif u.path == "/api/save_doc":
            content = body.get("content", "")
            first_line = content.strip().split("\n")[0][:40]
            slug = re.sub(r"[^a-z0-9]+", "-", first_line.lower()).strip("-") or "belge"
            name = f"{time.strftime('%Y%m%d-%H%M')}-{slug}.md"
            open(os.path.join(DOCS_DIR, name), "w", encoding="utf-8").write(content)
            self._json({"name": name})
        elif u.path.startswith(("/api/insights/", "/api/growth/", "/api/tr_cc/")):
            try:
                import insights
                if u.path == "/api/insights/hashtags":
                    self._json({"ok": True, "tags": _ai_hashtags(body.get("title", ""), body.get("script", ""))})
                elif u.path == "/api/insights/comment_drafts":
                    cm = insights.list_comments(body.get("video_id", ""))
                    todo = [c for c in cm if not c["mine"] and not c["replied"]]
                    drafts = _ai_comment_drafts(body.get("title", ""), todo) if todo else {}
                    self._json({"ok": True, "comments": todo, "drafts": drafts})
                elif u.path == "/api/insights/seed_comment":
                    self._json({"ok": True, "text": _ai_seed_comment(body.get("title", ""), body.get("description", ""))})
                elif u.path == "/api/insights/post_reply":
                    self._json({"ok": True, "id": insights.post_reply(body.get("parent_id", ""), body.get("text", ""))})
                elif u.path == "/api/insights/post_comment":
                    cid = insights.post_comment(body.get("video_id", ""), body.get("text", ""))
                    out = {"ok": True, "id": cid,
                           "link": f"https://www.youtube.com/watch?v={body.get('video_id', '')}&lc={cid}"}
                    if body.get("pin"):
                        out["pin"] = insights.pins_add(body.get("video_id", ""), body.get("title", ""), cid, body.get("text", ""))
                    self._json(out)
                elif u.path == "/api/insights/audit":
                    self._json(_ai_audit(body.get("question", "")))
                elif u.path == "/api/insights/tiktok_add":
                    self._json({"ok": True, "row": insights.tt_add(body.get("video_id", ""), body.get("title", ""),
                                body.get("views", 0), body.get("likes", 0), body.get("comments", 0), body.get("shares", 0))})
                elif u.path == "/api/insights/analytics_auth":
                    # Yetkiyi VERMEZ: PC'de Google izin ekranini acan sureci baslatir; operator kendisi onaylar.
                    if not self._code_net_ok(self.client_address[0]) or self.headers.get("Cf-Connecting-Ip"):
                        return self._json({"ok": False, "error": "Sadece PC'den veya Tailscale'den baslatilabilir."}, 403)
                    subprocess.Popen([sys.executable, os.path.join(STUDIO_DIR, "insights.py"), "--auth-analytics"], cwd=STUDIO_DIR)
                    self._json({"ok": True, "note": "PC ekraninda Google izin sayfasi acilacak; orada AURA Ai hesabini secip onay ver."})
                elif u.path == "/api/growth/actions":
                    self._json(_growth_actions())
                elif u.path == "/api/growth/apply":
                    self._json(_growth_apply(body.get("id", "")))
                elif u.path == "/api/growth/dismiss":
                    import growth
                    growth.action_set(body.get("id", ""), "reddedildi", "operator reddetti")
                    self._json({"ok": True})
                elif u.path == "/api/growth/draft_delete":
                    import growth
                    growth.draft_delete(body.get("id", ""))
                    self._json({"ok": True})
                elif u.path == "/api/growth/render_draft":
                    self._json(_growth_render_draft(body.get("id", "")))
                elif u.path == "/api/growth/render_publish_draft":
                    import growth
                    if not body.get("confirm"):
                        self._json({"ok": False, "error": "Operator onayi (confirm) gerekli."})
                    else:
                        dd = growth.draft_get(body.get("id", ""))
                        if dd and dd.get("status") == "taslak":
                            rr = _growth_render_draft(body.get("id", ""))
                            if not rr.get("ok"):
                                self._json(rr)
                                return
                        self._json(_growth_publish_draft(body.get("id", ""), body.get("day")))
                elif u.path == "/api/growth/publish_draft":
                    if not body.get("confirm"):
                        self._json({"ok": False, "error": "Operator onayi (confirm) gerekli."})
                    else:
                        self._json(_growth_publish_draft(body.get("id", ""), body.get("day")))
                elif u.path == "/api/growth/exp_delete":
                    import growth
                    growth.exp_delete(body.get("id", ""))
                    self._json({"ok": True})
                elif u.path == "/api/tr_cc/audit":
                    import tr_restore
                    open(TR_FLAG, "w").close()
                    self._json({"ok": True, **tr_restore.restore()})
                elif u.path == "/api/growth/tag":
                    import growth
                    growth.tag_set(body.get("video_id", ""), body.get("format", ""))
                    self._json({"ok": True})
                elif u.path == "/api/growth/preflight":
                    self._json(_growth_preflight(body, bool(body.get("ai"))))
                elif u.path == "/api/growth/candidates":
                    self._json(_growth_candidates())
                elif u.path == "/api/growth/agenda_candidate":
                    self._json(_growth_agenda_candidate())
                elif u.path == "/api/growth/report":
                    self._json(_growth_report())
                elif u.path == "/api/insights/pin_done":
                    insights.pins_done(body.get("comment_id", ""))
                    self._json({"ok": True})
                else:
                    self.send_response(404)
                    self.end_headers()
            except Exception as e:
                self._json({"ok": False, "error": f"{type(e).__name__}: {str(e)[:300]}"})
        elif u.path.startswith("/api/agent/"):
            if not self._code_allowed():
                return self._json({"ok": False, "error": "Asistan reddedildi: PIN yanlis/eksik (5 hatada 60 sn kilit) veya acik tunel/yabanci ag."}, 403)
            if u.path == "/api/agent/send":
                self._json(_agent.send(body.get("message", ""), body.get("image"), body.get("mime")))
            elif u.path == "/api/agent/reset":
                self._json(_agent.reset())
            elif u.path == "/api/agent/undo":
                self._json(_agent.undo())
            elif u.path == "/api/agent/cancel":
                self._json(_agent.cancel())
            else:
                self.send_response(404)
                self.end_headers()
        elif u.path.startswith("/api/code/"):
            if not self._code_allowed():
                return self._json({"ok": False, "error": "Kod modu reddedildi: PIN yanlis/eksik (5 hatada 60 sn kilit) veya acik tunel/yabanci ag."}, 403)
            try:
                rel = body.get("path", "")
                if u.path == "/api/code/ai":
                    self._json(_code_ai(rel, body.get("instruction", ""), body.get("history"), body.get("image"), body.get("mime")))
                elif u.path == "/api/code/apply":
                    self._json(_code_apply(rel, body.get("edits")))
                elif u.path == "/api/code/save":
                    self._json(_code_write(rel, str(body.get("content", "")).replace("\r\n", "\n")))
                elif u.path == "/api/code/restore":
                    self._json(_code_restore(rel, body.get("backup", "")))
                elif u.path == "/api/code/ai_settings":
                    _ai_settings_set(body.get("code_prefer", ""))
                    self._json({"ok": True, "code_prefer": _ai_settings()["code_prefer"]})
                elif u.path == "/api/code/restart_panel":
                    self._json(_restart_panel())
                else:
                    self.send_response(404); self.end_headers()
            except Exception as e:
                self._json({"ok": False, "error": f"{type(e).__name__}: {e}"})
        else:
            self.send_response(404); self.end_headers()


def _snapshot_loop():
    """Her 6 saatte kanal sayilarini kaydeder (panel acik kaldikca); buyume egrisi icin."""
    time.sleep(45)
    while True:
        try:
            import insights
            insights.channel_stats(force=True)
        except Exception as e:
            print(f"  [sayac kaydi basarisiz: {type(e).__name__}]")
        try:
            import growth
            age = growth.report_age_days()
            if age is None or age >= 7:
                _growth_report()  # haftalik otomatik rapor (sadece rapor uretir, hicbir sey yayinlamaz)
        except Exception as e:
            print(f"  [haftalik rapor basarisiz: {type(e).__name__}]")
        try:
            import insights
            r = insights.analytics_snapshot_once()  # gunde bir: retention (avg_pct) gecmisini kaydeder
            if r.get("ok"):
                print(f"  [retention snapshot] {r['n']} video kaydedildi ({r['date']})")
        except Exception as e:
            print(f"  [retention snapshot basarisiz: {type(e).__name__}]")
        try:
            import insights, tiktok_api
            if tiktok_api.connected():
                r = insights.tiktok_sync(_load_day_status(), _tiktok_meta_load())
                if r.get("ok"):
                    print(f"  [tiktok sync] {r['matched']} video eslesti / {r['total_tiktok_videos']} toplam")
        except Exception as e:
            print(f"  [tiktok sync basarisiz: {type(e).__name__}]")
        _tr_restore_check()
        for _ in range(6):  # saatte bir: bekleyen Turkce altyazi onarimi (kota yenilenince tamamlanir)
            time.sleep(3600)
            _tr_restore_check()


def _tr_restore_check():
    try:
        import tr_restore
        if os.path.exists(tr_restore.FLAG):
            r = tr_restore.restore()
            print(f"  [TR altyazi onarimi] yuklenen={r['restored']} atlanan={r['skipped']} kalan={r['left']} kota={r['quota']}")
    except Exception as e:
        print(f"  [TR altyazi onarimi basarisiz: {type(e).__name__}]")


def main():
    # 0.0.0.0: ayni WiFi agindaki cihazlar icin. Tunelsiz dogrudan 127.0.0.1 haric
    # her istek (LAN dahil) access_token.txt'deki token'i ister (bkz. _authorized).
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Aura Influencer Studio -> http://127.0.0.1:{PORT}/  (yerel)")
    print("Telefon icin: panelde 'Telefon Erisimi > Tuneli Baslat' (LAN'dan da token ister).")
    print("Kapatmak icin bu pencereyi kapat (Ctrl+C).")
    threading.Thread(target=_autostart_voice_mesh, daemon=True).start()
    threading.Thread(target=_snapshot_loop, daemon=True).start()
    _open_app_window(f"http://127.0.0.1:{PORT}/")
    srv.serve_forever()


if __name__ == "__main__":
    main()
