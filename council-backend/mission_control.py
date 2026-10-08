"""
MISSION CONTROL - Sign Council'in TEK EKRAN masaustu kontrol paneli.

Bugune kadar canli yayina almak icin 3 ayri terminal penceresi (ses sunucusu
-> health-check -> go_live.bat), telefon paneli icin ayri bir script
(command_center.py) ve tahmin defteri/onay kuyrugu icin elle JSON duzenlemek
gerekiyordu. Bu dosya hepsini TEK bir yerel HTTP sunucuda birlestirir;
mission_control_launch.py bunu pywebview ile native bir pencerede acar.

Guvenlik modeli command_center.py'den FARKLI: bu panel SADECE 127.0.0.1'de
dinler, disariya (telefon/internet) hic acilmaz - o yuzden token/tunnel
gerekmiyor. Telefondan erisim gerekiyorsa mevcut command_center.py ayrica
calismaya devam ediyor, bu dosya ona dokunmuyor.

Canli yayin kontrolu: live_aura.py'yi (go_live.bat'in yaptigi gibi) subprocess
olarak baslatir, kendi operatpr panelini (:8790, --operator-tunnel ile acilan
cloudflared satirindan token'i yakalayarak) proxy'ler - kontrol mantigi
YENIDEN YAZILMADI, var olan operator_panel.py API'sine konusuluyor.

Calistirma:
    python mission_control.py          # sadece sunucu (test)
    mission_control.bat                # cift tikla -> native pencere (normal kullanim)
"""
import datetime
import glob
import io
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
ENGINE = os.path.join(HERE, "_engine")
PORT = int(os.getenv("MISSION_CONTROL_PORT", "8800"))

import assistant  # noqa: E402
import codeassist  # noqa: E402
import health  # noqa: E402
import analysis_config  # noqa: E402
import analytics_report  # noqa: E402
import tracker  # noqa: E402
import tracker_actions  # noqa: E402
import autotest  # noqa: E402
import maintenance  # noqa: E402
import security  # noqa: E402
import bugun  # noqa: E402
import analiz  # noqa: E402
import sutun  # noqa: E402
import ogrenme  # noqa: E402
import daily_limit  # noqa: E402

# ---- kimlik dogrulama: TUM istekler gizli anahtar ister ---------------------
# 24 Eylul 2026: telefon baglantisi (Cloudflare tuneli) eklenince panel
# internetten erisilebilir oldu. Tunel trafigi sunucuya HER ZAMAN 127.0.0.1
# gibi gorunur (bkz. memory: localhost-tunnel-ip-auth-bypass) - IP'ye
# guvenilemez, o yuzden yerel pencere dahil herkes ayni gizli anahtari kullanir.
_TOKEN_PATH = os.path.join(ENGINE, "mission_token.txt")


def _get_token():
    try:
        t = open(_TOKEN_PATH, encoding="utf-8").read().strip()
        if len(t) >= 20:
            return t
    except OSError:
        pass
    t = secrets.token_urlsafe(24)
    os.makedirs(ENGINE, exist_ok=True)
    open(_TOKEN_PATH, "w", encoding="utf-8").write(t)
    return t


TOKEN = _get_token()


def _py():
    p = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Python", "Python312", "python.exe")
    return p if os.path.exists(p) else (sys.executable or "python")


PY = _py()


# =====================================================================
# genel yardimcilar
# =====================================================================
def _get_json(url, timeout=3):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def _read_json(path, default=None):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return [] if default is None else default


# =====================================================================
# kisa isler (Dagitim/Buyume sekmesi) - command_center.py ile AYNI desen
# =====================================================================
_JOBS = {}


def _run_job(args, env=None, timeout=900):
    jid = uuid.uuid4().hex[:10]
    _JOBS[jid] = {"status": "running", "out": "", "started": time.time()}

    def _go():
        try:
            p = subprocess.run([PY, "-u", *args], cwd=HERE, capture_output=True, env=env,
                               text=True, encoding="utf-8", errors="replace", timeout=timeout)
            _JOBS[jid]["out"] = (p.stdout or "") + (("\n[stderr]\n" + p.stderr) if p.stderr else "")
        except Exception as e:
            _JOBS[jid]["out"] = "[HATA] " + health.friendly_error(e)
        _JOBS[jid]["status"] = "done"

    threading.Thread(target=_go, daemon=True).start()
    return jid


def _autotest_loop():
    """Derin testi gunde bir kez (ilk acilistan ~3 dk sonra, sonra 20 saatten eskiyse) kendisi calistirir."""
    time.sleep(180)
    while True:
        try:
            a = autotest.last()
            old = (not a) or (time.time() - os.path.getmtime(autotest.OUT)) > 20 * 3600
            if old:
                autotest.run(f"http://127.0.0.1:{PORT}")
        except Exception:
            pass
        time.sleep(3600)


def _run_sync(fn, *a):
    try:
        return fn(*a)
    except Exception as e:
        return {"text": "[HATA] " + health.friendly_error(e)}


def _run_py_job(fn, *a, **kw):
    jid = uuid.uuid4().hex[:10]
    _JOBS[jid] = {"status": "running", "out": "", "started": time.time()}

    def _go():
        try:
            res = fn(*a, **kw)
            _JOBS[jid]["out"] = res if isinstance(res, str) and res else "tamam"
        except Exception as e:
            _JOBS[jid]["out"] = "[HATA] " + health.friendly_error(e)
        _JOBS[jid]["status"] = "done"

    threading.Thread(target=_go, daemon=True).start()
    return jid


_SAFE = {
    "drafts":          ["distribution_agent.py", "--pack"],
    "receipt":         ["distribution_agent.py", "--receipt"],
    "mark_reddit":     ["distribution_agent.py", "--mark-reddit"],
    "optimize":        ["optimize_loop.py", "--md"],
    "reference":       ["reference_mine.py"],
    "engagement":      ["engagement_signal.py", "--md"],
    "arc_show":        ["editorial_arc.py", "--show"],
    "retitle_preview": ["retitle_agent.py"],
    "backfill_dry":    ["backfill_playlists.py", "--dry"],
    "plan_only":       ["aura_engine.py", "--plan-only"],
}
_RISKY = {
    "retitle_apply":      ["retitle_agent.py", "--apply"],
    "retitle_apply_desc": ["retitle_agent.py", "--apply", "--desc"],
    "backfill_apply":     ["backfill_playlists.py"],
}


# =====================================================================
# BUGUN sekmesi: tek ekranda gundem -> kaynak -> uretim (private) -> inceleme -> yayin
# Korumalar motorda (aura_engine.py) aynen calisir; burasi sadece adimlari baglar.
# =====================================================================
def _bugun_env():
    env = dict(os.environ)
    env["AURA_VOICE_URL"] = "http://127.0.0.1:8124"
    env["AURA_VOICE_KEY"] = _voice_key()
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _bugun_receipt_arg(name):
    """Receipt dosya adi SADECE receipts/ klasorundeki listeden secilebilir (yol enjeksiyonu yok)."""
    if not name:
        return [], ""
    if name not in bugun.receipt_listesi():
        return None, "Bilinmeyen receipt dosyasi."
    return ["--receipt", os.path.join("receipts", name)], ""


def bugun_durum_full():
    d = bugun.bugun_durum()
    d["ses_hazir"] = bool((voice_health() or {}).get("model_loaded"))
    d["receipts"] = bugun.receipt_listesi()
    d["kontrol"] = bugun.YAYIN_KONTROL
    g = bugun.gundem_oku()
    d["gundem_zaman"] = g.get("zaman")
    d["dolu"] = d["adet"] >= d["limit"]
    return d


def _council_debate(briefing, plan):
    """Gunun analizi icin Konsey turu: ask_council ile AYNI motor/kilit; yalniz sistem talimati gecici Turkce."""
    with _ASK_LOCK:
        originals = {k: p["system_instruction"] for k, p in PERSONAS.items()}
        try:
            for p in PERSONAS.values():
                p["system_instruction"] += _TR_OVERRIDE
            transcript = run_episode(briefing, plan)
        finally:
            for k, orig in originals.items():
                PERSONAS[k]["system_instruction"] = orig
    return [{"speaker": t["speaker"], "name": PERSONAS[t["speaker"]]["display_name"], "text": t["text"]} for t in transcript]


def _watch_ihlal(jid, sutun_ad="", onceki=None):
    """Uretim bitince: (1) yeni video(lar)i sutuna bagla (olcum icin), (2) motor engel mesajiysa 'ihlal' kaydet (guven olcutu)."""
    def _go():
        while _JOBS.get(jid, {}).get("status") == "running":
            time.sleep(2)
        try:
            yeni = {v.get("video_id") for v in bugun.bugun_durum()["videolar"]} - set(onceki or [])
            for vid_ in yeni:
                if vid_ and sutun_ad:
                    sutun.kaydet(vid_, sutun_ad)
        except Exception:
            pass
        out = _JOBS.get(jid, {}).get("out", "")
        if "ENGELLEYICI ISARET" in out or "KAYNAKTA OLMAYAN ICERIK" in out:
            analiz.log({"olay": "ihlal", "job": jid})
    threading.Thread(target=_go, daemon=True).start()


def _tracker_kanal():
    """Sutun/veri analizi icin kanal verisi: tracker (tutma, abone, hashtag dahil) varsa onu kullan; yoksa YouTube API."""
    try:
        k = ogrenme.kanal_tracker(tracker.load())
        return k if k.get("ok") else None
    except Exception:
        return None


def bugun_analiz_baslat(sutun_ad=None):
    def _is():
        def _rapor():
            try:
                return analytics_report.load_report()
            except Exception:
                return None
        return analiz.calistir(bugun.gundem_yenile, bugun.gundem_oku, _council_debate, rapor=_rapor(), kanal=_tracker_kanal(),
                               hazirlik=bugun.sayfa_hazirlik, sutun=sutun_ad or None)
    return {"job": _run_py_job(_is)}


def bugun_job(kind, receipt_name="", sutun_ad="receipt"):
    sutun_ad = sutun_ad if sutun_ad in sutun.SUTUNLAR else "receipt"
    sd = sutun.SUTUNLAR[sutun_ad]
    paket = bugun._son_paket() if sd["kaynak"] else ""
    if kind == "plan" and not sd["kaynak"]:
        return {"error": "Bu sutunda plan onizlemesi yok: konuyu motor kendi secer (ikilem havuzu / Aura toplantisi). Uretim OZEL yuklenir, yayin kararini sen verirsin."}
    if kind in ("plan", "uret") and sd["kaynak"] and not paket:
        return {"error": "Once kaynak paketini hazirla (Adim 3)."}
    rec, err = _bugun_receipt_arg(receipt_name if sd["kaynak"] else "")
    if rec is None:
        return {"error": err}
    if kind == "plan":
        return {"job": _run_job(["aura_engine.py", "--plan-only", "--source", paket, *rec], env=_bugun_env(), timeout=300)}
    if kind == "uret":
        izin, info = daily_limit.can_upload(os.path.join(ENGINE, datetime.date.today().isoformat(), ".uploaded_today.json"))
        if not izin:
            return {"error": f"Bugun {info['count']}/{daily_limit.MAX_DAILY} video var - gunluk sinir doldu."}
        if not (voice_health() or {}).get("model_loaded"):
            return {"error": "Ses sunucusu hazir degil. Bakim sekmesinden baslat, YESIL 'CALISIYOR' gorunce tekrar dene."}
        bugun.gecmis_yaz({"olay": "uretim", "sutun": sutun_ad, "paket": paket, "receipt": receipt_name})
        onceki = [v.get("video_id") for v in bugun.bugun_durum()["videolar"]]
        args = ["aura_engine.py", "--short-upload", "--source", paket, *rec] if sd["kaynak"] else ["aura_engine.py", "--short-upload", *sd["bayrak"]]
        jid = _run_job(args, env=_bugun_env(), timeout=1500)
        _watch_ihlal(jid, sutun_ad, onceki)
        if sd["kaynak"]:
            bugun.paket_kullanildi()  # bir paket = bir uretim (ayni konudan ikinci video cikmasin)
        return {"job": jid}
    if kind == "rapor":
        return {"job": _run_job(["explain_run.py"], env=_bugun_env(), timeout=120)}
    return {"error": "bilinmeyen adim"}


def bugun_yayinla(video_id, onay, isaretli):
    hata = bugun.yayin_dogrula(onay, isaretli)
    if hata:
        return {"error": hata}
    ids = {v.get("video_id") for v in bugun.bugun_durum()["videolar"]}
    if video_id not in ids:
        return {"error": "Bu video bugunun yukleme kaydinda yok."}
    from publish_youtube import publish_video
    analiz.log({"olay": "yayin", "video_id": video_id})
    return {"job": _run_py_job(publish_video, video_id)}


# =====================================================================
# ses sunucusu (:8124) - sign_council_voice.bat'i supervise eder
# =====================================================================
_VOICE = {"proc": None, "log": deque(maxlen=300)}


def _pump(proc, buf):
    try:
        for line in proc.stdout:
            buf.append(line.rstrip("\n"))
    except Exception:
        pass


def voice_alive():
    return _VOICE["proc"] is not None and _VOICE["proc"].poll() is None


def voice_health():
    return _get_json("http://127.0.0.1:8124/health", timeout=2)


def _voice_key():
    """Ses sunucusu anahtari: .voice_key dosyasindan; dosya yoksa YENI uretilir (bos anahtar = kimlik kontrolu yok, olmaz)."""
    path = os.path.join(HERE, ".voice_key")
    try:
        k = open(path, encoding="utf-8").read().strip()
        if k:
            return k
    except Exception:
        pass
    k = "sc-local-" + secrets.token_urlsafe(24)
    with open(path, "w", encoding="utf-8") as f:
        f.write(k)
    return k


_VOICE_SRV = os.path.normpath(os.path.join(HERE, "..", "auro-backend", "voice_service", "server.py"))
_VOICE_ENV = {
    "AURA_VOICE_PORT": "8124",
    "AURA_VOICE_VOICES_DIR": os.path.join(HERE, "reference_voices"),
    "AURA_VOICE_DEFAULT_SPEAKER": "aura",
    "AURA_VOICE_KEY": _voice_key(),
    "AURA_TTS_EXAGGERATION": "0.4",
    "AURA_TTS_CFG_WEIGHT": "0.5",
}


def _kill_old_voice_servers():
    # sign_council_voice.bat'in kendi on-kosulu ile ayni: 8GB GPU tek Chatterbox
    # alir, baska bir server.py (or. ana app :8123) calisirsa synth yavaslayip
    # yayin donuyor - bat wrapper'i (cmd /c) birakip dogrudan yonetime gectigimizde
    # bu guvenlik adimini KAYBETMEMEK icin ayni PowerShell komutunu tekrarliyoruz.
    subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Get-CimInstance Win32_Process -Filter \"name='python.exe'\" | "
                    "Where-Object { $_.CommandLine -like '*server.py*' } | "
                    "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"],
                   capture_output=True, timeout=15)


def start_voice():
    if voice_alive():
        return {"ok": False, "error": "zaten calisiyor"}
    _kill_old_voice_servers()
    time.sleep(1)
    env = dict(os.environ)
    env.update(_VOICE_ENV)
    # Onceki denemede cmd /c sign_council_voice.bat sarmalayicisi kullanildi:
    # cmd.exe erkenden cikip icindeki python.exe'yi oksuz birakiyordu, panel
    # "calisiyor mu" takibini bozuyordu. server.py'yi DOGRUDAN yonetiyoruz.
    proc = subprocess.Popen([PY, "-u", _VOICE_SRV], cwd=HERE, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
                            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    _VOICE["proc"] = proc
    _VOICE["log"].clear()
    threading.Thread(target=_pump, args=(proc, _VOICE["log"]), daemon=True).start()
    return {"ok": True}


def stop_voice():
    if not voice_alive():
        return {"ok": False, "error": "calismiyor"}
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(_VOICE["proc"].pid)], capture_output=True)
    _VOICE["proc"] = None
    return {"ok": True}


# =====================================================================
# canli yayin (go_live.bat'in yaptigini birebir tekrarlar, ama parametrik)
# =====================================================================
_LIVE = {"proc": None, "log": deque(maxlen=500), "op_token": None, "op_port": 8790, "watch_url": None}
_OP_TOKEN_RE = re.compile(r"OPERATOR PANELI:.*?\?k=([A-Za-z0-9_-]+)")
_WATCH_RE = re.compile(r"İzleme linki:\s*(\S+)")


def _pump_live(proc):
    try:
        for line in proc.stdout:
            line = line.rstrip("\n")
            _LIVE["log"].append(line)
            m = _OP_TOKEN_RE.search(line)
            if m:
                _LIVE["op_token"] = m.group(1)
            m2 = _WATCH_RE.search(line)
            if m2:
                _LIVE["watch_url"] = m2.group(1)
    except Exception:
        pass


def live_alive():
    return _LIVE["proc"] is not None and _LIVE["proc"].poll() is None


def start_show(agenda="", auto_agenda=False, public=True, test=False, duration=2400, title=""):
    if live_alive():
        return {"ok": False, "error": "yayin zaten acik"}
    h = voice_health()
    if not h or not h.get("model_loaded"):
        return {"ok": False, "error": "ses sunucusu (:8124) hazir degil - once baslat"}
    env = dict(os.environ)
    env.update({
        "AURA_TTS_MESH": "1", "AURA_TTS_MESH_STREAM": "", "AURA_TTS_NO_CHATTERBOX": "1",
        "AURA_STUDIO_RES": "960x540", "AURA_VOICE_URL": "http://127.0.0.1:8124",
        "AURA_VOICE_KEY": _voice_key(), "AURA_STUDIO_GPU": "off",
        # 22 Eylul 2026 konsey karari (known_issues.json/live-tts-delay): mesh
        # takilirsa 110sn'lik varsayilan yerine HIZLI Groq'a dussun, tartisma
        # turleri kilitlenmesin. Isolate test 4.6s'de cevap veriyordu - 15s
        # saglikli bir istege bol pay birakiyor, gercek bir hangi ise hizli pes eder.
        "AURA_MESH_TIMEOUT": "15",
    })
    args = [PY, "-u", "live_aura.py"]
    if test:
        args += ["--test"]
    else:
        args += ["--debate", "--duration", str(int(duration))]
        if public:
            args += ["--public"]
        if auto_agenda or not agenda.strip():
            args += ["--auto-agenda"]
        else:
            args += ["--agenda", agenda.strip()]
        if title.strip():
            args += ["--title", title.strip()]
        args += ["--fps", "15", "--operator-tunnel"]
    proc = subprocess.Popen(args, cwd=HERE, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, bufsize=1, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    _LIVE.update({"proc": proc, "op_token": None, "watch_url": None})
    _LIVE["log"].clear()
    threading.Thread(target=_pump_live, args=(proc,), daemon=True).start()
    return {"ok": True}


def stop_show():
    # stop_live.bat ile birebir ayni, kanitlanmis yontem: _stop_live_aura
    # dosyasini yaratmak live_aura.py'nin ana dongusunu temiz durduruyor.
    open(os.path.join(HERE, "_stop_live_aura"), "w", encoding="utf-8").write("stop")
    return {"ok": True}


def live_state():
    if not _LIVE.get("op_token"):
        return None
    return _get_json(f"http://127.0.0.1:{_LIVE['op_port']}/state?k={_LIVE['op_token']}", timeout=2)


def live_cmd(action, who="", text=""):
    if not _LIVE.get("op_token"):
        return {"ok": False, "error": "operator token yok (yayin henuz hazirlaniyor olabilir)"}
    body = json.dumps({"action": action, "who": who, "text": text}).encode("utf-8")
    req = urllib.request.Request(
        f"http://127.0.0.1:{_LIVE['op_port']}/cmd?k={_LIVE['op_token']}",
        data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=3) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return {"ok": False, "error": str(e)}


# =====================================================================
# durum ozeti
# =====================================================================
def status_summary():
    vh = voice_health()
    today = datetime.date.today().isoformat()
    plan = _read_json(os.path.join(ENGINE, today, "plan.json"), {})
    tok = _read_json(os.path.join(HERE, "youtube_token.json"), {})
    if tok.get("refresh_token"):
        exp = (tok.get("expiry") or "")[:16]
        yt_state = f"bagli (erisim tokeni: {exp})" if exp else "bagli"
    else:
        yt_state = "baglanti yok"
    quota_flag = os.path.exists(os.path.join(ENGINE, "GEMINI_QUOTA_EXHAUSTED.flag"))
    # _read_json'un varsayilani None olsa bile [] donmesi ozelligi yuzunden
    # (asagida bkz. _read_json tanimi) dosya yoksa acikca None'a ceviriyoruz -
    # yoksa arayuzde "video var" saniliyordu (bos liste JS'te de truthy).
    _uf = os.path.join(ENGINE, today, ".uploaded_today.json")
    today_video = _read_json(_uf, {}) if os.path.exists(_uf) else {}
    today_video = today_video if today_video.get("video_id") else None
    pend = _read_json(os.path.join(ENGINE, "pending_approval.json"), [])
    today_pending = next((p for p in pend if p.get("video_id") == (today_video or {}).get("video_id")), None)
    return {
        "voice_up": bool(vh and vh.get("model_loaded")),
        "voice_proc_running": voice_alive(),
        "live_running": live_alive(),
        "live_watch_url": _LIVE.get("watch_url"),
        "today_topic": (plan or {}).get("decision", ""),
        "today_video": today_video,
        "today_video_pending": bool(today_pending),
        "youtube": yt_state,
        "gemini_quota_exhausted": quota_flag,
    }


def _age_days(path):
    try:
        return (time.time() - os.path.getmtime(path)) / 86400
    except Exception:
        return None


def freshness_summary():
    """21 Eylul 2026 kullanici geri bildirimi: 'kirmizi butonlara ne zaman
    basmam gerektigini bilmiyorum' - butonlarin yaninda son calisma zamanini
    ve bayatlamis mi diye gosteriyoruz, kullanici tahmin etmek zorunda
    kalmasin. Esikler bu islerin dogal ritmine gore (haftalik otomatik
    calisanlar icin ~8 gun, elle yapilan retitle icin ~30 gun)."""
    items = []

    def _add(key, label, path, stale_after_days, auto_weekly=False):
        age = _age_days(path)
        items.append({
            "key": key, "label": label,
            "age_days": round(age, 1) if age is not None else None,
            "stale": age is None or age > stale_after_days,
            "auto_weekly": auto_weekly,
        })

    _add("optimize", "Performans raporu (erişim×tutma)", os.path.join(ENGINE, "optimize.md"), analysis_config.get("stale_days_weekly"), True)
    _add("reference", "Referans kanal analizi", os.path.join(ENGINE, "reference_patterns.md"), analysis_config.get("stale_days_weekly"), True)
    _add("engagement", "Etkileşim sinyali (yorum+paylaşım)", os.path.join(ENGINE, "engagement_digest.md"), analysis_config.get("stale_days_weekly"), True)
    backups = sorted(glob.glob(os.path.join(ENGINE, "title_backup_*.json")))
    _add("retitle", "Son başlık güncellemesi", backups[-1] if backups else "___yok___", analysis_config.get("stale_days_retitle"), False)
    return items


_KNOWN_ISSUES_PATH = os.path.join(ENGINE, "known_issues.json")


def known_issues():
    return _read_json(_KNOWN_ISSUES_PATH, [])


def diagnose(issue_id):
    """'Sorun çözme' butonu: statik metin degil, TAM SIMDI canli kontroller
    yapip gercek nedeni gostermeye calisir (22 Eylul 2026 istegi)."""
    checked_at = datetime.datetime.now().strftime("%H:%M:%S")
    if issue_id == "live-tts-delay":
        findings = []
        vh = voice_health()
        findings.append(f"Ses sunucusu (:8124): {'HAZIR (model yuklu)' if vh and vh.get('model_loaded') else 'YANIT VERMİYOR'}")
        if vh:
            findings.append(f"Anlık işlemdeki istek sayısı: {vh.get('inflight')} / kuyruk sınırı {vh.get('max_queue')}")
        rival = _get_json("http://127.0.0.1:8123/health", timeout=2)
        if rival:
            findings.append("⚠ Ana Aura uygulamasının KENDİ ses sunucusu (:8123) HÂLÂ ÇALIŞIYOR - aynı GPU'yu paylaşıyor, çakışma riski sürüyor.")
        else:
            findings.append("Ana Aura uygulamasının ses sunucusu (:8123) kapalı - o kaynaktan çakışma yok.")
        findings.append("Uygulanan geçici önlem: canlı yayın artık 110sn yerine 15sn zaman aşımıyla başlıyor (AURA_MESH_TIMEOUT) - mesh yanıt vermezse hızla Groq'a düşüp yayını kilitlemeyecek.")
        findings.append("Kalıcı kök neden HÂLÂ bulunamadı - izole istekte 4.6sn'de cevap veren aynı sunucu, canlı yayın süreci içinden çağrılınca neden yavaşlıyor bilinmiyor.")
        return {"issue_id": issue_id, "checked_at": checked_at, "findings": findings}
    return {"issue_id": issue_id, "checked_at": checked_at, "findings": ["Bu sorun için otomatik tanı henüz tanımlanmadı."]}


def list_days():
    if not os.path.isdir(ENGINE):
        return []
    days = [d for d in os.listdir(ENGINE) if re.match(r"^\d{4}-\d{2}-\d{2}$", d)]
    return sorted(days, reverse=True)


def day_detail(day):
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", day or ""):
        return None
    base = os.path.join(ENGINE, day)
    uploaded = _read_json(os.path.join(base, ".uploaded_today.json"), None)
    # 27 Eyl 2026: plan.json TEK toplantiyi tutar (uzerine yazilir) - o gun
    # birden fazla kez "Bugunun plani" calistirilmissa (elle ya da sabah+aksam)
    # onceki toplantilar plan_history.json'da da saklanir, hicbiri kaybolmaz.
    hist = _read_json(os.path.join(base, "plan_history.json"), [])
    for h in hist:
        h["led_to_video"] = False
    if uploaded:
        before = [h for h in hist if h.get("ts", "") <= uploaded.get("ts", "")]
        if before:
            max(before, key=lambda h: h.get("ts", ""))["led_to_video"] = True
    return {"plan": _read_json(os.path.join(base, "plan.json"), {}),
            "run": _read_json(os.path.join(base, "run.json"), {}),
            "history": hist, "uploaded": uploaded}


from orchestrator import run_episode
from personas import PERSONAS

_CHAT_HISTORY_PATH = os.path.join(ENGINE, "council_chat_history.json")
_CHAT_TURN_PLAN = [
    {"speaker": "aura", "directive": (
        "Frame this question/decision sharply - name the real tension "
        "underneath it, not just the surface question. 2-4 sentences.")},
    {"speaker": "alpha", "directive": (
        "Give the concrete practical/economic read - real costs, numbers, "
        "or mechanisms involved. 3-5 sentences.")},
    {"speaker": "beta", "directive": (
        "Attack the framing so far if it deserves it, then give a blunt "
        "Risk Score out of 10 and justify it. 3-5 sentences.")},
    {"speaker": "gamma", "directive": (
        "Name who is actually affected by this decision (beyond the person "
        "asking) and the real stake for them. 3-5 sentences.")},
    {"speaker": "delta", "directive": (
        "Find the one point where Alpha, Beta and Gamma actually agree "
        "underneath their disagreement, with one concrete analogy. "
        "3-5 sentences.")},
    {"speaker": "aura", "directive": (
        "Close as the COUNCIL VERDICT: the actual recommendation, direct "
        "and specific, not a recap. 2-4 sentences.")},
]


_TR_OVERRIDE = ("\n\nOVERRIDE FOR THIS CONVERSATION ONLY: ignore any earlier "
                "instruction about responding in English. This is a private "
                "strategy discussion with the channel operator (not public "
                "video content) - respond ONLY in Turkish (Türkçe).")


def ask_council(jid, question, image_b64=None, image_mime=None):
    # council_chat.py ile AYNI motor (orchestrator.run_episode) ve AYNI
    # _engine/council_chat_history.json dosyasi - iki arac ayni gecmisi
    # paylasir, hangisinden sorulursa sorulsun tek bir kayit olur.
    # personas.py TUM personalara "always respond in English" zorluyor
    # (gercek YouTube icerigi icin dogru) - ama bu sohbet kullanicinin
    # KENDISI icin, video degil; kullanici sadece Turkce anladigi icin
    # sistem talimatini GECICI olarak Turkce'ye zorluyoruz, sonra geri aliyoruz.
    full_question = question
    if image_b64:
        import base64
        from providers import describe_image
        img_desc = describe_image(base64.b64decode(image_b64), image_mime or "image/png", question)
        full_question = (f"{question}\n\n[Kullanicinin ekte paylastigi ekran "
                         f"goruntusunun detayli tarifi:]\n{img_desc}")
    # Ust uste iki soru PERSONAS sozlugunu ayni anda degistirip yanlis geri
    # yukleyebilirdi (kalici Turkce zorlama) - tek seferde tek soru.
    with _ASK_LOCK:
        originals = {k: p["system_instruction"] for k, p in PERSONAS.items()}
        try:
            for p in PERSONAS.values():
                p["system_instruction"] += _TR_OVERRIDE
            transcript = run_episode(full_question, _CHAT_TURN_PLAN)
        finally:
            for k, orig in originals.items():
                PERSONAS[k]["system_instruction"] = orig
    out = [{"speaker": t["speaker"], "name": PERSONAS[t["speaker"]]["display_name"], "text": t["text"]}
           for t in transcript]
    hist = _read_json(_CHAT_HISTORY_PATH, [])
    hist.append({"id": uuid.uuid4().hex, "ts": time.time(), "question": question, "transcript": out})
    json.dump(hist[-200:], open(_CHAT_HISTORY_PATH, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    _JOBS[jid]["transcript"] = out


_ASK_LOCK = threading.Lock()


# =====================================================================
# telefon baglantisi (Cloudflare gecici tunel) - uygulamanin KENDISI yonetir
# =====================================================================
_TUNNEL = {"proc": None, "url": None, "log": deque(maxlen=40), "started": None}
_TUNNEL_URL_RE = re.compile(r"https://(?!api\.)[a-z0-9-]+\.trycloudflare\.com")


def tunnel_alive():
    return _TUNNEL["proc"] is not None and _TUNNEL["proc"].poll() is None


def _cloudflared_exe():
    return shutil.which("cloudflared") or next(
        (p for p in [r"C:\Program Files (x86)\cloudflared\cloudflared.exe",
                     r"C:\Program Files\cloudflared\cloudflared.exe"] if os.path.exists(p)), None)


def _pump_tunnel(proc):
    try:
        for line in proc.stdout:
            line = line.rstrip("\n")
            _TUNNEL["log"].append(line)
            m = _TUNNEL_URL_RE.search(line)
            if m and not _TUNNEL["url"]:
                _TUNNEL["url"] = m.group(0)
    except Exception:
        pass


def tunnel_start():
    if tunnel_alive():
        return {"ok": True, "already": True}
    exe = _cloudflared_exe()
    if not exe:
        return {"ok": False, "error": "cloudflared bulunamadi (Bakim > Sistem Kontrolu'ne bak)"}
    # onceki calismadan kalan, bu porta bakan tunelleri kapat (oksuz birikmesin)
    maintenance._ps("Get-CimInstance Win32_Process -Filter \"name='cloudflared.exe'\" | Where-Object { "
                    f"$_.CommandLine -like '*:{PORT}*' }} | ForEach-Object {{ Stop-Process -Id $_.ProcessId -Force "
                    "-ErrorAction SilentlyContinue }")
    proc = subprocess.Popen([exe, "tunnel", "--url", f"http://127.0.0.1:{PORT}", "--no-autoupdate"],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1,
                            encoding="utf-8", errors="replace", creationflags=subprocess.CREATE_NO_WINDOW)
    _TUNNEL.update(proc=proc, url=None, started=time.time())
    _TUNNEL["log"].clear()
    threading.Thread(target=_pump_tunnel, args=(proc,), daemon=True).start()
    return {"ok": True}


def tunnel_stop():
    if tunnel_alive():
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(_TUNNEL["proc"].pid)], capture_output=True)
    _TUNNEL.update(proc=None, url=None, started=None)
    return {"ok": True}


def _qr_svg(text):
    try:
        import qrcode
        import qrcode.image.svg
        img = qrcode.make(text, image_factory=qrcode.image.svg.SvgPathImage, box_size=8, border=2)
        buf = io.BytesIO()
        img.save(buf)
        svg = buf.getvalue().decode("utf-8", "replace")
        i = svg.find("<svg")
        return svg[i:] if i >= 0 else None
    except Exception:
        return None


_BOUND_HOST = {"host": "127.0.0.1"}


def phone_status():
    alive = tunnel_alive()
    url = _TUNNEL["url"] if alive else None
    link = f"{url}/?key={TOKEN}" if url else None
    return {"running": alive, "starting": alive and not url, "link": link,
            "qr_svg": _qr_svg(link) if link else None,
            "log": list(_TUNNEL["log"])[-6:] if alive and not url else [],
            "cloudflared": bool(_cloudflared_exe()),
            "lan_active": _BOUND_HOST["host"] == "0.0.0.0",
            "lan_setting": bool(settings().get("lan")),
            "lan_urls": [{"url": f"http://{ip}:{PORT}/?key={TOKEN}",
                          "label": "Tailscale (SABIT adres - Tailscale'li her cihazdan, internete acik degil)" if ip.startswith("100.") else "Ayni Wi-Fi"}
                         for ip in lan_ips()] if _BOUND_HOST["host"] == "0.0.0.0" else []}


def shutdown_children():
    """Pencere kapaninca: telefon tuneli + ses sunucusu kapatilir (oksuz kalmasin).
    Acik canli yayina DOKUNULMAZ (--duration ile kendiliginden biter)."""
    try:
        tunnel_stop()
    except Exception:
        pass
    try:
        if voice_alive():
            stop_voice()
    except Exception:
        pass


# =====================================================================
# Sorun Cozucu (Yardim sekmesi) - Claude Code'dan BAGIMSIZ, projenin kendi
# Gemini anahtariyla (kota biterse otomatik diger saglayicilara duser)
# =====================================================================
_HELP_PATH = os.path.join(HERE, "HELP_TR.md")


def manual_text():
    try:
        return open(_HELP_PATH, encoding="utf-8").read()
    except OSError:
        return "El kitabi bulunamadi (HELP_TR.md)."


def help_ask(jid, question, image_b64=None, image_mime=None):
    from providers import call_gemini, describe_image
    if image_b64:
        import base64
        desc = describe_image(base64.b64decode(image_b64), image_mime or "image/png", question)
        question = f"{question}\n\n[Kullanicinin ekte paylastigi ekran goruntusunun tarifi:]\n{desc}"
    try:
        issues = [f"{r.get('title')} ({r.get('status')})" for r in known_issues()]
    except Exception:
        issues = []
    recent = _read_json(os.path.join(ENGINE, "interventions.json"), [])[-5:]
    state = json.dumps({"durum": status_summary(), "bilinen_sorunlar": issues,
                        "son_otomatik_mudahaleler": recent}, ensure_ascii=False)
    system = (
        "You are the built-in troubleshooting assistant of 'Sign Council Mission Control', a Windows desktop app. "
        "Reply ONLY in TURKISH, short and concrete (numbered steps). The user is non-technical. "
        "Use the MANUAL and CURRENT STATE below. RULES: (1) You can NOT run or change anything - never say you "
        "did, will do, or are doing an action; tell the user exactly WHICH TAB/BUTTON to press or which manual step "
        "to take. (2) Never invent buttons, files, or features that are not in the manual. (3) If the manual does "
        "not cover it, say you are not sure and give the safest general Windows/Python step, and say that a "
        "developer may be needed. (4) Never ask for or repeat passwords/API keys.\n\n"
        f"CURRENT STATE (json): {state}\n\nMANUAL:\n{manual_text()}")
    answer = call_gemini([{"role": "user", "content": question}], system)
    _JOBS[jid]["answer"] = answer


def pending_reject(video_id):
    path = os.path.join(ENGINE, "pending_approval.json")
    rows = [r for r in _read_json(path, []) if r.get("video_id") != video_id]
    json.dump(rows, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # 28 Eyl 2026: reddedilen video hicbir zaman yayinlanmadi - "gunde 1 video"
    # kilidinin o gunku bayragini da kaldir, yoksa ayni gun ELLE yeni bir
    # video uretmek istersen (--force olmadan) kilit yanlislikla engelliyordu.
    today = datetime.date.today().isoformat()
    uf = os.path.join(ENGINE, today, ".uploaded_today.json")
    up = _read_json(uf, {})
    if up.get("video_id") == video_id:
        try:
            os.remove(uf)
        except OSError:
            pass


_AUTH_URL_RE = re.compile(r"https://accounts\.google\.com/\S+")


def account_status():
    tok = _read_json(os.path.join(HERE, "youtube_token.json"), None)
    if not tok:
        return {"connected": False}
    return {"connected": True, "has_refresh_token": bool(tok.get("refresh_token")),
            "expiry": tok.get("expiry", ""), "scopes": tok.get("scopes", [])}


def reconnect_youtube(jid):
    """youtube_auth.py'yi subprocess olarak calistirir, konsolda basilan
    yetkilendirme URL'ini yakalayip is durumuna yazar (kullanici linki KENDI
    tarayicisinda acmali - bu adim otomatiklestirilemez)."""
    proc = subprocess.Popen([PY, "-u", "youtube_auth.py"], cwd=HERE,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
    for line in proc.stdout:
        _JOBS[jid]["out"] += line
        m = _AUTH_URL_RE.search(line)
        if m and "auth_url" not in _JOBS[jid]:
            _JOBS[jid]["auth_url"] = m.group(0)
    proc.wait(timeout=180)


# =====================================================================
# HTML/JS (tek sayfa, sekmeli)
# =====================================================================
PAGE = r"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sign Council - Mission Control</title>
<style>
 :root{color-scheme:dark}
 body{font-family:-apple-system,Segoe UI,sans-serif;background:#0d1117;color:#e6edf3;margin:0;padding:0}
 header{padding:14px 20px;border-bottom:1px solid #30363d;display:flex;align-items:center;gap:12px}
 header h1{font-size:17px;margin:0}
 nav{display:flex;gap:4px;padding:8px 16px;border-bottom:1px solid #30363d;flex-wrap:wrap}
 nav button{background:none;border:1px solid #30363d;color:#8b949e;border-radius:6px;padding:7px 12px;font-size:13px;cursor:pointer}
 nav button.active{background:#1f6feb22;color:#58a6ff;border-color:#1f6feb}
 main{padding:18px 20px;max-width:900px}
 .tab{display:none} .tab.active{display:block} .tab.guest{display:block}
 details.fold{margin:14px 0;border:1px solid #30363d;border-radius:8px;padding:6px 12px;background:#0d1117}
 details.fold>summary{cursor:pointer;font-weight:600;padding:6px 0;color:#c9d1d9}
 .card{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:14px 16px;margin-bottom:14px}
 .row{display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid #21262d}
 .row:last-child{border-bottom:none}
 .pill{display:inline-block;border-radius:99px;padding:2px 10px;font-size:11px}
 .ok{background:#23863622;color:#3fb950} .bad{background:#f8514922;color:#f85149} .warn{background:#d2992222;color:#d29922}
 button.act{background:#21262d;color:#e6edf3;border:1px solid #30363d;border-radius:7px;padding:9px 14px;font-size:13px;cursor:pointer;margin:4px 6px 4px 0}
 button.act:hover{background:#30363d}
 button.risky{border-color:#f85149;color:#f85149}
 button.primary{background:#1f6feb;border-color:#1f6feb;color:#fff}
 input[type=text],textarea,select{background:#0d1117;border:1px solid #30363d;color:#e6edf3;border-radius:6px;padding:8px;width:100%;box-sizing:border-box;font-family:inherit}
 textarea{min-height:60px}
 label{font-size:12px;color:#8b949e;display:block;margin:8px 0 4px}
 pre.log{white-space:pre-wrap;background:#010409;border:1px solid #30363d;border-radius:8px;padding:10px;font-size:12px;max-height:320px;overflow:auto}
 h2{font-size:14px;color:#8b949e;text-transform:uppercase;letter-spacing:.04em;margin:0 0 10px}
 .persona{font-weight:600} .persona.alpha{color:#58a6ff} .persona.beta{color:#f85149} .persona.gamma{color:#3fb950} .persona.delta{color:#d29922} .persona.aura{color:#c9a3ff}
 select.dayp{width:auto}
 #phoneQr svg{width:200px;height:200px;display:block}
 .alert{padding:8px 12px;margin:8px 16px 0;border-radius:8px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;font-size:13px}
 .alert.bad{background:#f8514922;border:1px solid #f85149;color:#ffb3ae}
 .alert.warn{background:#d2992222;border:1px solid #d29922;color:#f0d28a}
 .alert.info{background:#1f6feb22;border:1px solid #1f6feb;color:#a5c8ff}
 .alert button{background:none;border:1px solid currentColor;color:inherit;border-radius:6px;padding:3px 9px;font-size:12px;cursor:pointer}
 .alert button:first-of-type{margin-left:auto}
 .step-res{white-space:pre-wrap;font-size:13px;margin-top:6px}
 .chip{display:inline-block;background:#21262d;color:#e6edf3;border:1px solid #30363d;border-radius:99px;padding:4px 11px;margin:3px 4px 3px 0;font-size:12px;cursor:pointer}
 .chip:hover{background:#30363d}
 .kpi{background:#0d1117;border:1px solid #30363d;border-radius:10px;padding:10px 12px}
 .kpi b{font-size:22px;display:block} .kpi small{color:#8b949e}
 .up{color:#3fb950} .down{color:#f85149}
 .bar{height:10px;background:#1f6feb;border-radius:5px}
 table.tbl{width:100%;border-collapse:collapse;font-size:13px} table.tbl td,table.tbl th{padding:5px 6px;border-bottom:1px solid #21262d;text-align:left} table.tbl th{color:#8b949e;font-weight:normal}
 .diff{white-space:pre;font-family:Consolas,monospace;font-size:12px;background:#010409;border:1px solid #30363d;border-radius:8px;padding:8px;max-height:360px;overflow:auto}
 .diff .add{color:#3fb950} .diff .del{color:#f85149} .diff .hunk{color:#58a6ff}
 main{max-width:1100px}
 @media (pointer:coarse){ button.act,nav button{min-height:44px;font-size:15px} input,textarea,select{font-size:16px} }
 @media (min-width:900px){
  #tab-durum.active,#tab-bakim.active,#tab-telefon.active,#tab-dagitim.active,#tab-yardim.active,#tab-hesap.active,#tab-onay.active{display:grid;grid-template-columns:1fr 1fr;gap:14px;align-items:start}
  #tab-durum.active .card,#tab-bakim.active .card,#tab-telefon.active .card,#tab-dagitim.active .card,#tab-yardim.active .card,#tab-hesap.active .card,#tab-onay.active .card{margin-bottom:0}
  .card.wide{grid-column:1/-1}
 }
 @media (max-width:640px){ main{padding:12px} nav button{flex:1 1 auto} .row{flex-wrap:wrap;gap:4px} }
</style></head><body>
<header><h1>🎛 Sign Council — Mission Control <span style="font-size:11px;font-weight:normal;color:#8b949e">v2.1 · 25 Eylül 2026</span></h1></header>
<div id="alertBar"></div>
<nav>
 <button data-tab="bugun" class="active">🚀 Bugün</button>
 <button data-tab="analiz">📊 Performans</button>
 <button data-tab="sistem">⚙ Sistem</button>
 <button data-tab="asistan">🛠 Asistan</button>
 <button data-tab="kod">Kod</button>
</nav>
<main>

<div class="tab active" id="tab-bugun">
 <div class="card wide">
  <h2>🚀 Bugün <span id="bgSayac" class="pill" style="margin-left:6px"></span></h2>
  <div style="color:#8b949e;font-size:13px">Tek ekran: gündem → kaynak → üretim (özel/private) → inceleme → yayın. Korumalar (iddia/niyet taraması, kaynak doğrulama, günlük 2 sınırı) arka planda aynen çalışır. Yayın yalnızca senin onayınla.</div>
  <div id="bgDurum" style="margin-top:8px;font-size:13px"></div>
 </div>
 <div class="card wide">
  <h2>0 · Günün analizi <span style="font-weight:normal;color:#8b949e;font-size:12px">(konular → kanal verisi → çıktılar → Konsey tartışması → karar; paylaşımdan hemen önce çalıştır)</span></h2>
  <button class="act primary" style="font-size:15px;padding:12px 20px" onclick="bgAnaliz()">🔎 Analizi başlat (1-3 dk)</button> <span id="bgAnalizSt" style="font-size:13px;color:#8b949e"></span>
  <div id="bgAnalizBox" style="margin-top:10px"></div>
  <div id="bgGuven" style="margin-top:12px;font-size:13px"></div>
 </div>
 <div class="card wide">
  <h2>1 · Gündem (elle bakmak istersen) <span style="font-weight:normal;color:#8b949e;font-size:12px">(son 24 saat haberleri; puan = kanal kuralına uyum + tazelik, "viral olur" tahmini değil)</span></h2>
  <button class="act primary" onclick="bgGundem()">Gündemi yenile (10-30 sn)</button> <span id="bgGundemSt" style="font-size:12px;color:#8b949e"></span>
  <div id="bgAdaylar" style="margin-top:8px"></div>
 </div>
 <div class="card wide">
  <h2>2 · Kaynak sayfa</h2>
  <input id="bgUrl" placeholder="https://… (listeden «Seç» ile dolar ya da kendin yapıştır)" style="width:100%;max-width:640px">
  <div style="margin-top:6px"><button class="act primary" onclick="bgKaynak()">Sayfayı çek ve kanıtları çıkar</button> <span id="bgKaynakSt" style="font-size:12px;color:#8b949e"></span></div>
  <div id="bgKanit" style="margin-top:8px"></div>
 </div>
 <div class="card wide">
  <h2>3 · Paket <span style="font-weight:normal;color:#8b949e;font-size:12px">(seçtiğin kanıt cümleleri; video yalnızca bunlara dayanır)</span></h2>
  <input id="bgFacts" placeholder="Grafikte gördüğün sayılar (isteğe bağlı, ; ile ayır)" style="width:100%;max-width:640px">
  <div style="margin-top:6px"><button class="act primary" onclick="bgPaket()">Paketi hazırla</button> <span id="bgPaketSt" style="font-size:12px;color:#8b949e"></span></div>
 </div>
 <div class="card wide">
  <h2>4 · Önizleme ve üretim <span style="font-weight:normal;color:#8b949e;font-size:12px">(üretim 2-4 dk; video ÖZEL yüklenir)</span></h2>
  <div id="bgSutunEtiket" style="color:#58a6ff;font-size:13px;margin-bottom:4px">Seçili sütun: receipt</div>
  <div>Receipt (varsa): <select id="bgReceipt"><option value="">(yok — sayfadan otomatik)</option></select></div>
  <div style="margin-top:6px">
   <button class="act" onclick="bgAdim('plan')">Planı göster (yüklemez)</button>
   <button class="act primary" onclick="bgAdim('uret')">🎬 Üret (özel yükle)</button>
   <button class="act" onclick="bgAdim('rapor')">İnceleme raporu</button>
  </div>
  <pre id="bgOut" style="white-space:pre-wrap;max-height:380px;overflow:auto;background:#0d1117;border:1px solid #30363d;border-radius:6px;padding:8px;margin-top:8px;font-size:12px"></pre>
 </div>
 <div class="card wide">
  <h2>5 · Yayın kararı <span style="font-weight:normal;color:#8b949e;font-size:12px">(sadece sen)</span></h2>
  <div id="bgVideolar" style="font-size:13px"></div>
  <div id="bgKontrol" style="margin:8px 0"></div>
  <input id="bgOnay" placeholder="YAYINLA yaz" style="width:160px">
  <button class="act risky" onclick="bgYayinla()">Yayınla</button> <span id="bgYayinSt" style="font-size:12px;color:#8b949e"></span>
  <div style="font-size:12px;color:#8b949e;margin-top:6px">Yayınlamazsan video özel kalır; Studio'dan silebilir veya sonra yayınlayabilirsin.</div>
 </div>
 <div class="card wide">
  <h2>6 · Paylaş <span style="font-weight:normal;color:#8b949e;font-size:12px">(hazır metin; otomatik gönderilmez, sen kopyalayıp paylaşırsın; etkisi ölçülür)</span></h2>
  <button class="act" onclick="bgPaylas('reddit')">Reddit taslağı</button>
  <button class="act" onclick="bgPaylas('x')">X taslağı</button>
  <div id="bgPaylasBox" style="margin-top:8px"></div>
 </div>
</div>

<div class="tab" id="tab-sistem"></div>

<div class="tab" id="tab-durum">
 <div class="card"><h2>Sistem Durumu</h2><div id="statusBox">yukleniyor...</div></div>
 <div class="card wide" id="issuesCard" style="display:none"><h2>⚠ Bilinen Sorunlar</h2><div id="issuesBox"></div></div>
 <div class="card"><h2>Otomatik Müdahale Kayıtları (şeffaflık)</h2><div id="intervBox">yükleniyor...</div></div>
</div>

<div class="tab" id="tab-live">
 <div class="card">
  <h2>Ses Sunucusu (:8124)</h2>
  <div id="voiceStatus" class="row"><span>durum</span><span class="pill">...</span></div>
  <button class="act primary" onclick="voiceStart()">Ses Sunucusunu Başlat</button>
  <button class="act risky" onclick="voiceStop()">Durdur</button>
 </div>
 <div class="card">
  <h2>Yayın</h2>
  <label>Gündem (boş bırak = Aura kendi seçsin)</label>
  <textarea id="agendaText" placeholder="Örn: Google AI Studio'nun..."></textarea>
  <label>Yayın başlığı (opsiyonel)</label>
  <input type="text" id="titleText">
  <label><input type="checkbox" id="publicChk" checked style="width:auto"> Herkese açık (kapalıysa unlisted test yayını)</label>
  <div style="margin-top:10px">
   <button class="act primary" onclick="liveStart(false)">Yayını Başlat</button>
   <button class="act" onclick="liveStart(true)">Sadece Bağlantı Testi (--test)</button>
   <button class="act risky" onclick="liveStop()">Yayını Durdur</button>
  </div>
  <div id="liveState" style="margin-top:12px"></div>
  <div id="liveControls" style="display:none;margin-top:10px">
   <button class="act" onclick="liveCmd('pause')">Duraklat</button>
   <button class="act" onclick="liveCmd('resume')">Devam</button>
   <button class="act" onclick="liveCmd('skip')">Sıradaki Tura Geç</button>
  </div>
 </div>
 <div class="card"><h2>Canlı Günlük</h2><pre class="log" id="liveLog"></pre></div>
</div>

<div class="tab" id="tab-kararlar">
 <div class="card">
  <h2>Karar Merkezi — Konseye Sor</h2>
  <div style="color:#8b949e;font-size:13px;margin-bottom:8px">Burası <b>danışma ve arşiv</b> içindir — video ÜRETMEZ. Stratejik bir soru sor, ya da aşağıdan geçmiş günlerin hangi konuyu seçtiğine bak.</div>
  <textarea id="askText" placeholder="Örn: Hafta sonları da yayın yapmalı mıyız? Bir ekran görüntüsünü buraya yapıştırabilirsin (Ctrl+V)."></textarea>
  <div id="imgPreviewBox" style="display:none;margin-top:8px">
   <img id="imgPreview" style="max-width:180px;max-height:120px;border-radius:6px;border:1px solid #30363d;display:block">
   <button class="act risky" style="display:inline-block;width:auto;padding:4px 10px;margin-top:4px" onclick="clearImage()">Resmi kaldır</button>
  </div>
  <div style="margin-top:8px">
   <button class="act primary" onclick="askCouncil()">Konseye Sor</button>
   <span id="askStatus" style="color:#8b949e;font-size:12px;margin-left:8px"></span>
  </div>
  <div id="askTurns" style="margin-top:12px"></div>
 </div>
 <div class="card">
  <h2>Geçmiş Konuşmalar</h2>
  <div id="chatHistory"></div>
 </div>
 <div class="card">
  <h2>Günlük Kararlar (otomatik üretim)</h2>
  <select class="dayp" id="daySelect" onchange="loadDay()"></select>
  <div id="dayDetail" style="margin-top:12px"></div>
 </div>
</div>

<div class="tab" id="tab-tahmin">
 <div class="card"><h2>Skor Kartı</h2><div id="predScore" class="row"></div></div>
 <div class="card"><h2>Tahminler</h2><div id="predList"></div></div>
</div>

<div class="tab" id="tab-onay">
 <div class="card wide">
  <h2>🎬 Video üret ve yayınla</h2>
  <div style="color:#8b949e;font-size:13px;margin-bottom:10px">Otomatik zamanlayıcı KAPALI. Video sadece burada, sen istediğinde üretilir — kimse sormaz, kimseye bağlı değil. Üretim 2-4 dakika sürer, sonucu aşağıda görürsün.</div>
  <button class="act primary" style="font-size:16px;padding:14px 22px" onclick="uretBaslat()">🎬 Şimdi yeni video üret</button>
  <span id="uretStatus" style="margin-left:10px;font-size:13px;color:#8b949e"></span>
 </div>
 <div class="card">
  <h2>Bugün ne oldu?</h2>
  <div id="uretBugun">yükleniyor...</div>
 </div>
 <div class="card wide">
  <h2>Onay bekleyen videolar <span style="font-weight:normal;color:#8b949e;font-size:12px">(hassas iddia içerenler burada senin onayını bekler; diğerleri direkt herkese açık olur)</span></h2>
  <div id="pendingList">yükleniyor...</div>
 </div>
</div>

<div class="tab" id="tab-dagitim">
 <div class="card">
  <h2>Durum / Rapor</h2>
  <button class="act" onclick="run('arc_show')">Aylık tema</button>
  <button class="act" onclick="run('plan_only')">Bugünkü planı göster (2-4 dk)</button>
 </div>
 <div class="card">
  <h2>Trafik / Dağıtım</h2>
  <button class="act" onclick="run('drafts')">Paylaşım taslakları üret</button>
  <button class="act" onclick="run('receipt')">Receipt taslağı</button>
  <button class="act" onclick="run('mark_reddit')">"Reddit'i attım" say</button>
 </div>
 <div class="card">
  <h2>Başlık</h2>
  <div id="fresh-retitle" style="font-size:12px;color:#8b949e;margin-bottom:6px"></div>
  <button class="act" onclick="run('retitle_preview')">Başlık önerilerini göster</button>
  <button class="act risky" onclick="runConfirm('retitle_apply','Başlıklar GÜNCELLENECEK. Emin misin?')">Başlıkları GÜNCELLE</button>
  <button class="act risky" onclick="runConfirm('retitle_apply_desc','Başlık+açıklama GÜNCELLENECEK. Emin misin?')">Başlık + açıklama GÜNCELLE</button>
 </div>
 <div class="card">
  <h2>Öğrenme <span style="font-weight:normal;color:#8b949e;font-size:12px">(her Pazartesi otomatik yenilenir - elle çalıştırmak zorunlu değil)</span></h2>
  <div id="fresh-optimize" style="font-size:12px;color:#8b949e"></div>
  <button class="act" onclick="run('optimize')">Performans raporunu yenile</button>
  <div id="fresh-reference" style="font-size:12px;color:#8b949e;margin-top:6px"></div>
  <button class="act" onclick="run('reference')">Referans kanal analizini yenile</button>
  <div id="fresh-engagement" style="font-size:12px;color:#8b949e;margin-top:6px"></div>
  <button class="act" onclick="run('engagement')">Etkileşim sinyalini yenile (yorum+paylaşım)</button>
  <div style="margin-top:10px">
   <button class="act" onclick="run('backfill_dry')">Playlist sınıflandırma (önizle)</button>
   <button class="act risky" onclick="runConfirm('backfill_apply','Playlistler GÜNCELLENECEK. Emin misin?')">Playlistleri GÜNCELLE</button>
  </div>
 </div>
 <div class="card wide"><h2>Çıktı</h2><pre class="log" id="jobOut"></pre></div>
</div>

<div class="tab" id="tab-hesap">
 <div class="card">
  <h2>YouTube Hesabı</h2>
  <div id="acctStatus">yukleniyor...</div>
  <button class="act primary" onclick="reconnect()">Yeniden Bağlan</button>
  <div id="acctOut" style="margin-top:10px"></div>
 </div>
</div>

<div class="tab" id="tab-telefon">
 <div class="card">
  <h2>Telefondan Yönet</h2>
  <p style="color:#8b949e;margin-top:0">Bu uygulamanın tamamını telefonundan açar (onay, yayın, konsey, bakım). Link <b>gizli anahtar içerir</b> — kimseyle paylaşma. Link, uygulama her yeniden başladığında <b>değişir</b>.</p>
  <div id="phoneState">yükleniyor...</div>
  <div style="margin-top:10px">
   <button class="act primary" onclick="phoneStart()">Telefonu Bağla</button>
   <button class="act risky" onclick="phoneStop()">Bağlantıyı Kapat</button>
  </div>
  <div id="phoneLinkBox" style="display:none;margin-top:14px">
   <label>Telefonda aç (linki kopyala ya da QR'ı telefon kamerasıyla okut)</label>
   <input type="text" id="phoneLink" readonly onclick="this.select()">
   <button class="act" style="margin-top:6px" onclick="copyPhone()">Linki kopyala</button>
   <div id="phoneQr" style="background:#fff;display:inline-block;padding:8px;border-radius:8px;margin-top:10px;max-width:220px"></div>
  </div>
 </div>
<div class="card">
  <h2>Güvenlik (PIN)</h2>
  <p style="color:#8b949e;margin-top:0">Uzaktan (telefon/tablet) <b>uygulamayı yeniden başlat, port kapat, otomatik başlat, LAN aç/kapat</b> gibi işlemler PIN sorar. PIN belirlenmediyse bu işlemler uzaktan kapalıdır. <b>Kod düzenleme uzaktan HİÇ açılmaz</b> (yalnızca bu bilgisayardaki pencere).</p>
  <div id="pinState" style="margin-bottom:8px"></div>
  <input type="password" id="pinInput" placeholder="yeni PIN (en az 6 karakter) — yalnızca bilgisayardan belirlenir">
  <div style="margin-top:6px">
   <button class="act primary" onclick="setPin()">PIN belirle / değiştir</button>
   <button class="act risky" onclick="clearPin()">PIN'i sil</button>
   <button class="act" onclick="lockNow()">Kilitle (oturumu kapat)</button>
  </div>
 </div>
 <div class="card">
  <h2>Aynı Wi-Fi'den Erişim <span style="font-weight:normal;color:#8b949e;font-size:12px">(internetsiz, tablet/telefon)</span></h2>
  <label><input type="checkbox" id="lanChk" style="width:auto" onchange="setLan(this.checked)"> Aynı Wi-Fi'deki cihazlar için aç <span style="color:#8b949e">(uygulamayı yeniden başlatınca geçerli olur; Windows güvenlik duvarı izin isteyebilir)</span></label>
  <div id="lanBox" style="margin-top:8px;font-size:13px"></div>
 </div>
</div>

<div class="tab" id="tab-bakim">
 <div class="card">
  <h2>Sistem Kontrolü <span style="font-weight:normal;color:#8b949e;font-size:12px">(eksik program / anahtar var mı)</span></h2>
  <button class="act primary" onclick="loadSelfcheck()">Kontrol et</button>
  <div id="selfcheckBox" style="margin-top:10px"></div>
 </div>
 <div class="card">
  <h2>Onarım</h2>
  <button class="act" onclick="maintOrphans()">Öksüz yayın süreçlerini temizle</button>
  <button class="act" onclick="voiceStart()">Ses sunucusunu başlat</button>
  <button class="act risky" onclick="voiceStop()">Ses sunucusunu durdur</button>
  <span id="voicePill" class="pill" style="margin-left:8px">...</span>
  <div id="maintOut" style="margin-top:8px;font-size:12px;color:#8b949e"></div>
 </div>
 <div class="card">
  <h2>Derin test <span style="font-weight:normal;color:#8b949e;font-size:12px">(güvenlik, kod düzenleme, karar kuralları, veri, altyapı — 50+ kontrol; her gün kendisi de çalışır)</span></h2>
  <button class="act primary" onclick="atRun()">Derin testi şimdi çalıştır (~20 sn)</button> <span id="atStatus" style="font-size:12px;color:#8b949e"></span>
  <div id="atBox" style="margin-top:8px"></div>
 </div>
 <div class="card">
  <h2>Portlar <span style="font-weight:normal;color:#8b949e;font-size:12px">(kim hangi portu tutuyor)</span></h2>
  <button class="act" onclick="loadPorts()">Yenile</button>
  <div id="portsBox" style="margin-top:8px"></div>
 </div>
 <div class="card">
  <h2>Zamanlanmış Görevler <span style="font-weight:normal;color:#8b949e;font-size:12px">(günlük otomatik üretim)</span></h2>
  <button class="act" onclick="loadTasks()">Yenile</button>
  <div id="tasksBox" style="margin-top:8px"></div>
  <div style="margin-top:10px;border-top:1px solid #21262d;padding-top:10px">
   <span style="color:#8b949e;font-size:12px">Bir gün üretim başarısız olduysa (Logda "motor durdu" görürsen) elle yeniden başlat — planlı görevle aynı işi yapar, HERKESE AÇIK video yayınlayabilir (hassas olan yine onay bekler):</span><br>
   <button class="act risky" onclick="runDaily('morning')">Sabah formatını şimdi çalıştır</button>
   <button class="act risky" onclick="runDaily('evening')">Akşam formatını şimdi çalıştır</button>
   <span id="dailyOut" style="font-size:12px;color:#8b949e"></span>
  </div>
 </div>
 <div class="card wide">
  <h2>Loglar</h2>
  <select id="logSelect" class="dayp" onchange="loadLog()"></select>
  <pre class="log" id="logBox" style="margin-top:8px"></pre>
 </div>
 <div class="card">
  <h2>Yedek &amp; Otomatik Başlatma</h2>
  <button class="act primary" onclick="doBackup()">Yedek al (zip)</button>
  <button class="act" onclick="mkShortcuts()">Kısayolları yeniden oluştur (masaüstü + Başlat menüsü)</button>
  <span id="backupOut" style="font-size:12px;color:#8b949e"></span>
  <div style="margin-top:10px">
   <label><input type="checkbox" id="autostartChk" style="width:auto" onchange="setAutostart(this.checked)"> Windows açılışında bu uygulamayı otomatik başlat</label>
  </div>
 </div>
<div class="card">
  <h2>Kendini Test Et <span style="font-weight:normal;color:#8b949e;font-size:12px">(kod düzenledikten sonra "bozdum mu?")</span></h2>
  <button class="act primary" onclick="runSelftest()">Testi çalıştır</button>
  <button class="act risky" onclick="restartApp()">Uygulamayı yeniden başlat</button>
  <div id="lastGoodInfo" style="font-size:12px;color:#8b949e;margin-top:6px"></div>
  <div id="selftestOut" style="margin-top:8px"></div>
 </div>
</div>

<div class="tab" id="tab-analiz">
 <div class="card wide">
  <h2>🧪 Ne işe yaradı? <span style="font-weight:normal;color:#8b949e;font-size:12px">(sütun, başlık kalıbı, hashtag, yayın günü — 'Dönemine göre' = videonun, ±10 gün içinde yayınlanan videoların medyanına oranı (1.0 = tipik); örnek az olduğu için YÖN gösterir, kanıt değildir)</span></h2>
  <button class="act primary" onclick="ogLoad()">Karneyi çıkar</button> <span id="ogSt" style="font-size:12px;color:#8b949e"></span>
  <div id="ogBox" style="margin-top:8px"></div>
 </div>
 <div class="card">
  <h2>Kanal Göstergeleri <span style="font-weight:normal;color:#8b949e;font-size:12px" id="anTs"></span></h2>
  <div id="anKpis" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px"></div>
  <div style="margin-top:10px"><button class="act primary" onclick="anRefresh()">YouTube'dan yenile (30-60 sn)</button> <span id="anStatus" style="font-size:12px;color:#8b949e"></span></div>
 </div>
 <div class="card"><h2>Günlük izlenme (son 28 gün)</h2><div id="anChart"></div></div>
 <div class="card"><h2>Trafik kaynakları (28 gün)</h2><div id="anTraffic"></div></div>
 <div class="card"><h2>En çok izlenen videolar</h2><div id="anTopViews"></div></div>
 <div class="card"><h2>En yüksek etkileşim oranı <span style="font-weight:normal;color:#8b949e;font-size:12px">(yorum+paylaşım / 1000 izlenme)</span></h2><div id="anTopEng"></div></div>
 <div class="card"><h2>En iyi izlenme tutma oranı</h2><div id="anBestRet"></div></div>
 <div class="card">
  <h2>Analiz Ayarları <span style="font-weight:normal;color:#8b949e;font-size:12px">(eşikler ve uyarı kuralları)</span></h2>
  <div id="anCfg"></div>
  <button class="act primary" onclick="anSaveCfg()">Ayarları kaydet</button> <span id="anCfgStatus" style="font-size:12px;color:#8b949e"></span>
 </div>
 <div class="card">
  <h2>Analizi ve hata kurallarını kodla düzenle</h2>
  <div style="color:#8b949e;font-size:12px;margin-bottom:6px">Tıkla → Kod sekmesinde açılır (yalnızca bu bilgisayarda düzenlenir; her kayıt yedeklenir).</div>
  <div id="anChips"></div>
 </div>
</div>

<div class="tab" id="tab-takip">
 <div class="card">
  <h2>🚀 Büyüme makinesi <span style="font-weight:normal;color:#8b949e;font-size:12px">(1000 izlenme başına — hedef: izleyiciyi yorum, paylaşım ve aboneye çevirmek)</span></h2>
  <div id="tkFunnel"></div>
 </div>
 <div class="card">
  <h2>Ne yapmalıyım? <span style="font-weight:normal;color:#8b949e;font-size:12px" id="tkTs"></span></h2>
  <div style="color:#8b949e;font-size:12px;margin-bottom:8px">Sistem veriyi kendisi izler (6 saatte bir yeniler) ve kurallarla karar üretir. Her kararın <b>neden</b> çıktığı yazılıdır. "Yapıldı" dersen listeden düşer.</div>
  <div id="tkDecisions"></div>
  <button class="act primary" onclick="tkRefresh()">Şimdi yenile (30-60 sn)</button> <span id="tkStatus" style="font-size:12px;color:#8b949e"></span>
 </div>
 <div class="card">
  <h2>🎙 Sesli konuşma kararı <span style="font-weight:normal;color:#8b949e;font-size:12px">(canlı yayında ve sesli görüşmede ne söylensin?)</span></h2>
  <div id="tkVoice"></div>
 </div>
 <div class="card"><h2>Video takibi <span style="font-weight:normal;color:#8b949e;font-size:12px">(her videonun rakamı, hashtag'i ve yargısı)</span></h2><div id="tkVideos"></div></div>
 <div class="card"><h2>Hashtag performansı</h2><div style="color:#8b949e;font-size:12px">Ortalama izlenme; az videoda kullanılanlar için (n) küçükse kesin sonuç sayma.</div><div id="tkHash"></div></div>
 <div class="card"><h2>Etiket (tag) performansı</h2><div id="tkTags"></div></div>
 <div class="card"><h2>Bu rakam ne demek?</h2><div id="tkGloss"></div></div>
</div>

<div class="tab" id="tab-asistan">
 <div class="card">
  <h2>Komut Asistanı <span style="font-weight:normal;color:#8b949e;font-size:12px">(yaz ya da mikrofona konuş — yapay zeka PLANLAR, işi sistem yapar)</span></h2>
  <div style="color:#8b949e;font-size:13px;margin-bottom:8px">Burası <b>sistem işletme</b> içindir — durum sorma, bakım, ayar. Video üretmek/yayınlamak için <button class="act" style="padding:2px 10px" onclick="gotoTab('onay')">🎬 Üret &amp; Yayınla</button> sekmesine git.</div>
  <textarea id="asstText" placeholder="Örn: Sistemin durumu ne? / Canlı yayın bağlantı testi yap / Ses sunucusunu başlat"></textarea>
  <div style="margin-top:8px">
   <button class="act primary" id="asstBtn" onclick="asstSend()">Gönder</button>
   <button class="act" id="asstMic" type="button">🎤 Konuş</button>
   <span id="asstStatus" style="color:#8b949e;font-size:12px;margin-left:8px"></span>
  </div>
  <div id="asstOut" style="margin-top:12px"></div>
 </div>
 <div class="card"><h2>Yapabildiklerim</h2><div id="asstCatalog" style="font-size:13px"></div></div>
</div>

<div class="tab" id="tab-kod">
 <div class="card" id="kodLocked" style="display:none">
  <h2>Kod düzenleme kapalı</h2>
  <p>Kod düzenleme <b>yalnızca bilgisayardaki uygulama penceresinden</b> yapılır. Güvenlik gereği telefon/tablet/internet üzerinden hiç açılmaz.</p>
 </div>
 <div id="kodUI">
  <div class="card">
   <h2>Kod <span style="font-weight:normal;color:#8b949e;font-size:12px">(sadece bu bilgisayarda · kendi API anahtarlarınla · her kayıt yedeklenir)</span></h2>
   <div id="kodChips" style="margin-bottom:8px"></div>
   <input type="text" id="kodSearch" placeholder="dosya ara (örn: mission_control, .bat, HELP)" oninput="kodTree()">
   <select id="kodFile" size="7" style="width:100%;margin-top:8px" onchange="kodOpen()"></select>
   <div style="margin-top:6px;color:#8b949e;font-size:12px">Korumalı (açılmaz): .env, token/PIN dosyaları, mission_control.bat, restore_last_good.py, security.py</div>
  </div>
  <div class="card">
   <h2 id="kodTitle">Dosya seçilmedi</h2>
   <textarea id="kodEditor" spellcheck="false" style="min-height:320px;font-family:Consolas,monospace;font-size:13px;white-space:pre;overflow:auto"></textarea>
   <div style="margin-top:8px">
    <button class="act primary" onclick="kodSave()">Kaydet</button>
    <button class="act" onclick="kodBackups()">Yedekler / geri al</button>
    <button class="act risky" onclick="restartApp()">Uygulamayı yeniden başlat</button>
    <span id="kodStatus" style="font-size:12px;color:#8b949e;margin-left:6px"></span>
   </div>
   <div id="kodBackups" style="margin-top:8px"></div>
  </div>
  <div class="card">
   <h2>Yapay zeka ile değiştir <span style="font-weight:normal;color:#8b949e;font-size:12px">(önce FARKI görürsün, onaylamadan yazılmaz)</span></h2>
   <textarea id="kodInstr" placeholder="Ne değişsin? Örn: 'Telefon sekmesindeki başlığı büyüt' — yukarıdan bir dosya seç ya da aşağıya yeni dosya yolu yaz"></textarea>
   <input type="text" id="kodNewPath" placeholder="(opsiyonel) YENİ dosya yolu, örn: yardimci_arac.py" style="margin-top:6px">
   <div style="margin-top:6px">
    <select id="kodProvider" class="dayp"><option value="anthropic">Claude (Anthropic API)</option><option value="gemini">Gemini</option><option value="openai">OpenAI</option></select>
    <button class="act primary" onclick="kodPropose('edit')">Değişiklik öner</button>
    <button class="act" onclick="kodPropose('ask')">Bu dosyayı açıkla</button>
    <button class="act" id="kodMic" type="button">🎤 Konuş</button>
    <span id="kodAiStatus" style="font-size:12px;color:#8b949e"></span>
   </div>
   <div style="margin-top:6px;color:#8b949e;font-size:12px">Dosya içeriği seçtiğin yapay zeka sağlayıcısına gönderilir (kendi API anahtarınla). Gizli dosyalar hiç gönderilmez.</div>
   <div id="kodProposal" style="margin-top:10px"></div>
  </div>
 </div>
</div>

<div class="tab" id="tab-yardim">
 <div class="card">
  <h2>Sorun Çözücü <span style="font-weight:normal;color:#8b949e;font-size:12px">(yapay zeka; sadece yönlendirir, hiçbir şey çalıştırmaz)</span></h2>
  <textarea id="helpText" placeholder="Sorunu yaz ya da hata ekranının görüntüsünü buraya yapıştır (Ctrl+V)..."></textarea>
  <div id="helpImgBox" style="display:none;margin-top:8px">
   <img id="helpImg" style="max-width:180px;max-height:120px;border-radius:6px;border:1px solid #30363d;display:block">
   <button class="act risky" style="display:inline-block;width:auto;padding:4px 10px;margin-top:4px" onclick="clearHelpImage()">Resmi kaldır</button>
  </div>
  <div style="margin-top:8px">
   <button class="act primary" id="helpBtn" onclick="askHelp()">Sor</button>
   <span id="helpStatus" style="color:#8b949e;font-size:12px;margin-left:8px"></span>
  </div>
  <div id="helpAnswer" style="margin-top:12px;white-space:pre-wrap"></div>
 </div>
 <div class="card wide">
  <h2>El Kitabı</h2>
  <pre class="log" id="manualBox" style="max-height:none;white-space:pre-wrap"></pre>
 </div>
</div>

</main>
<script>
const $ = s => document.querySelector(s);
document.querySelectorAll('nav button').forEach(b => b.onclick = () => {
  document.querySelectorAll('nav button').forEach(x=>x.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
  b.classList.add('active'); $('#tab-'+b.dataset.tab).classList.add('active');
  if (typeof onTab === 'function') onTab(b.dataset.tab);
});

const JH = {'Content-Type':'application/json'};
async function api(path, opts) {
  let r = await fetch(path, opts);
  let j = await r.json().catch(()=>({error:'sunucu cevabı okunamadı ('+r.status+')'}));
  if (r.status === 403 && j.need === 'pin') {
    const pin = prompt('Bu işlem için PIN gir:');
    if (pin) {
      const u = await (await fetch('/api/security/unlock',{method:'POST',headers:JH,body:JSON.stringify({pin})})).json();
      if (u.ok) { r = await fetch(path, opts); j = await r.json().catch(()=>({})); } else alert(u.error || 'PIN hatalı');
    }
  } else if (r.status === 403 && j.need === 'setpin') alert(j.error);
  return j;
}

async function refreshStatus() {
  const s = await api('/api/status');
  $('#statusBox').innerHTML = `
    <div class="row"><span>Ses sunucusu (:8124)</span><span class="pill ${s.voice_up?'ok':'bad'}">${s.voice_up?'HAZIR':'KAPALI'}</span></div>
    ${s.voice_up? '' : `<div style="font-size:12px;color:#8b949e;padding:2px 0 8px">Aura'nın kendi sesini üreten program. Uygulama yeniden başlatılınca kapanır (uygulamanın alt programıdır); açık kalması şart değil, canlı yayını başlatınca kendisi açılır. Elle açmak için: <button class="act" style="padding:2px 10px" onclick="voiceStart().then(()=>setTimeout(refreshStatus,2000))">Ses sunucusunu başlat</button> (40-90 sn sürer; ana Aura'nın :8123 ses sunucusunu kapatır).</div>`}
    <div class="row"><span>Canlı yayın</span><span class="pill ${s.live_running?'ok':'bad'}">${s.live_running?'AÇIK':'KAPALI'}</span></div>
    ${s.live_running? '' : `<div style="font-size:12px;color:#8b949e;padding:2px 0 8px">Şu an YouTube'a canlı yayın yapılmıyor (normal). Başlatmak için <button class="act" style="padding:2px 10px" onclick="gotoTab('live')">Canlı Yayın sekmesine git</button> → "Yayını başlat".</div>`}
    ${s.live_watch_url? `<div class="row"><span>İzleme linki</span><a href="${s.live_watch_url}" target="_blank">${s.live_watch_url}</a></div>`:''}
    <div class="row"><span>Bugünün videosu</span><span class="pill ${s.today_video&&s.today_video.video_id ? (s.today_video_pending?'warn':'ok') : 'bad'}">${s.today_video&&s.today_video.video_id ? (s.today_video_pending?'ONAY BEKLİYOR':'YAYINLANDI') : 'HENÜZ YOK'}</span></div>
    <div style="font-size:12px;color:#8b949e;padding:2px 0 8px">${s.today_video&&s.today_video.video_id ? `<a href="https://youtu.be/${s.today_video.video_id}" target="_blank">https://youtu.be/${s.today_video.video_id}</a>` : "Otomatik zamanlayıcı kapalı — istediğin an kendin üretirsin."} <button class="act" style="padding:2px 10px;margin-left:6px" onclick="gotoTab('onay')">🎬 Üret &amp; Yayınla</button></div>
    ${s.today_topic? '' : `<div style="font-size:12px;color:#8b949e;padding:2px 0 8px">Günlük üretim bugün henüz çalışmadı; konu o zaman seçilir. Zamanlı görev kendisi çalıştırır, istersen <button class="act" style="padding:2px 10px" onclick="gotoTab('bakim')">Bakım</button> sekmesinden elle başlat.</div>`}
    <div class="row"><span>YouTube</span><span>${s.youtube}</span></div>
    ${s.gemini_quota_exhausted? '<div class="row"><span>⚠ Gemini kredisi</span><span class="pill warn">TÜKENDİ</span></div>':''}
  `;
  $('#voiceStatus').innerHTML = `<span>durum</span><span class="pill ${s.voice_up?'ok':'bad'}">${s.voice_up?'HAZIR':'KAPALI'}</span>`;
}

async function loadFreshness(){
  const rows = await api('/api/freshness');
  for (const r of rows) {
    const el = $('#fresh-'+r.key);
    if (!el) continue;
    let txt;
    if (r.age_days === null) txt = 'hiç çalışmadı';
    else if (r.age_days < 1) txt = 'bugün yenilendi';
    else txt = `${Math.round(r.age_days)} gün önce yenilendi`;
    const badge = r.stale ? `<span class="pill warn" style="margin-left:6px">${r.auto_weekly?'YAKINDA OTOMATİK ÇALIŞACAK':'GÜNCEL DEĞİL'}</span>` : `<span class="pill ok" style="margin-left:6px">GÜNCEL</span>`;
    el.innerHTML = txt + badge;
  }
}

async function loadIssues(){
  const rows = (await api('/api/known_issues')).filter(r => r.status !== 'cozuldu');
  if (!rows.length) { $('#issuesCard').style.display='none'; return; }
  $('#issuesCard').style.display='block';
  $('#issuesBox').innerHTML = rows.map(r => `
    <div class="row" style="display:block;padding:10px 0">
      <div><span class="pill ${r.severity==='high'?'bad':'warn'}">${r.severity}</span> <b>${r.title}</b></div>
      <div style="color:#8b949e;font-size:12px;margin-top:4px">${r.date} — ${r.detail}</div>
      <button class="act" style="margin-top:8px" onclick="diagnose('${r.id}')">Kök nedeni göster (canlı kontrol)</button>
      <div id="diag-${r.id}" style="margin-top:8px"></div>
    </div>`).join('');
}
async function diagnose(id){
  const el = $('#diag-'+id);
  el.innerHTML = 'kontrol ediliyor...';
  const d = await api('/api/diagnose?id='+id);
  el.innerHTML = `<div class="log" style="background:#010409;border:1px solid #30363d;border-radius:8px;padding:10px;font-size:12px">
    <div style="color:#8b949e">Kontrol saati: ${d.checked_at}</div>
    ${d.findings.map(f=>`<div style="margin-top:4px">• ${f}</div>`).join('')}
  </div>`;
}
async function loadInterventions(){
  const rows = await api('/api/interventions');
  const box = document.getElementById('intervBox');
  if (!box) return;
  box.innerHTML = rows.length ? rows.map(r => {
    const t = new Date(r.ts*1000).toLocaleString('tr-TR');
    return `<div class="row"><span>${t} — ${r.event}</span><span style="color:#8b949e;font-size:12px">${r.detail}</span></div>`;
  }).join('') : '(kayıt yok - hiç otomatik yedeğe düşülmedi)';
}

var _voiceWant = null, _voiceTimer = null;
function voicePaint(up){
  const el = $('#voicePill'); if(!el) return;
  if(_voiceWant==='up' && !up){ el.className='pill'; el.style.cssText='margin-left:8px;background:#d29922;color:#000'; el.textContent='BAŞLATILIYOR… (40-90 sn)'; return; }
  if(_voiceWant==='down' && up){ el.className='pill'; el.style.cssText='margin-left:8px;background:#d29922;color:#000'; el.textContent='DURDURULUYOR…'; return; }
  _voiceWant = null; el.style.cssText='margin-left:8px';
  el.className = 'pill ' + (up ? 'ok' : 'bad'); el.textContent = up ? 'ÇALIŞIYOR' : 'DURDU';
}
async function voicePoll(){
  try { const s = await api('/api/status'); voicePaint(!!s.voice_up); } catch(e){}
  if(_voiceWant && !_voiceTimer){ _voiceTimer = setInterval(async()=>{ await voicePoll(); if(!_voiceWant){ clearInterval(_voiceTimer); _voiceTimer=null; loadPorts(); } }, 3000); }
}
async function voiceStart(){ _voiceWant='up'; voicePaint(false); await api('/api/voice/start',{method:'POST'}); voicePoll(); refreshStatus(); }
async function voiceStop(){ _voiceWant='down'; voicePaint(true); await api('/api/voice/stop',{method:'POST'}); voicePoll(); refreshStatus(); }

async function liveStart(test){
  const body = JSON.stringify({
    agenda: $('#agendaText').value, title: $('#titleText').value,
    public: $('#publicChk').checked, test: test, auto_agenda: !$('#agendaText').value.trim(),
  });
  const r = await api('/api/live/start', {method:'POST', headers:{'Content-Type':'application/json'}, body});
  if(!r.ok) alert('HATA: '+r.error);
  refreshStatus();
}
async function liveStop(){ await api('/api/live/stop',{method:'POST'}); refreshStatus(); }
async function liveCmd(action){ await api('/api/live/cmd',{method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({action})}); }

async function pollLive(){
  const log = await api('/api/live/log');
  $('#liveLog').textContent = (log.lines||[]).join('\n');
  $('#liveLog').scrollTop = $('#liveLog').scrollHeight;
  const st = await api('/api/live/state');
  if(st){
    $('#liveControls').style.display='block';
    $('#liveState').innerHTML = `<div class="row"><span>Konuşan</span><span>${st.speaking||'-'}</span></div>
      <div class="row"><span>Gündem</span><span>${st.agenda||'-'}</span></div>
      <div class="row"><span>Duraklatıldı</span><span>${st.paused?'evet':'hayır'}</span></div>`;
  } else { $('#liveControls').style.display='none'; $('#liveState').innerHTML=''; }
}

async function run(action){
  $('#jobOut').textContent = 'çalışıyor...';
  const r = await api(`/api/run?action=${action}`, {method:'POST'});
  if(r.error){ $('#jobOut').textContent = 'HATA: '+r.error; return; }
  pollJob(r.job);
}
function runConfirm(action, msg){
  if(!confirm(msg)) return;
  $('#jobOut').textContent = 'çalışıyor...';
  api(`/api/run?action=${action}&confirm=EVET`, {method:'POST'}).then(r=> r.job? pollJob(r.job) : $('#jobOut').textContent='HATA: '+r.error);
}
async function pollJob(jid){
  const j = await api(`/api/job/${jid}`);
  if(j.status==='running'){ setTimeout(()=>pollJob(jid), 2000); return; }
  $('#jobOut').textContent = j.out || '(çıktı yok)';
  loadFreshness();
}

async function loadDays(){
  const days = await api('/api/days');
  $('#daySelect').innerHTML = days.map(d=>`<option value="${d}">${d}</option>`).join('');
  if(days.length) loadDay();
}
async function loadDay(){
  const day = $('#daySelect').value;
  const d = await api(`/api/day?date=${day}`);
  const plan = d.plan || {};
  let html = `<p><b>Karar:</b> ${plan.decision||'-'}</p>`;
  if(plan.angles && plan.angles.length) html += `<p><b>Açılar:</b><ul>${plan.angles.map(a=>`<li>${a}</li>`).join('')}</ul></p>`;
  if(plan.council_pitches && plan.council_pitches.length){
    html += '<p><b>Konsey önerileri:</b></p>';
    for(const p of plan.council_pitches) html += `<p><span class="persona ${p.name.toLowerCase()}">${p.name}:</span> ${p.pitch}</p>`;
  }
  if(plan.scoring_notes) html += `<details><summary>Aura'nın puanlama gerekçesi</summary><pre class="log">${plan.scoring_notes}</pre></details>`;
  const hist = d.history || [];
  if(hist.length > 1 || (hist.length===1 && !d.uploaded)){
    html += `<hr style="border-color:#30363d;margin:14px 0"><p style="color:#8b949e;font-size:12px">Bu gün <b>${hist.length}</b> kez konsey toplandı (yukarıdaki, en sonuncusu). Aşağıda hepsi — hangisi gerçekten video oldu, hangisi sadece toplantıyla kaldı:</p>`;
    hist.slice().reverse().forEach((h,i)=>{
      const badge = h.led_to_video ? '<span class="pill ok">✔ bu video oldu</span>' : '<span class="pill">video olmadı</span>';
      html += `<details style="margin:6px 0"><summary>${(h.ts||'').replace('T',' ')} — ${badge} — ${(h.decision||'').slice(0,90)}</summary>`;
      html += `<div style="padding:8px 0 8px 12px">`;
      if(h.angles && h.angles.length) html += `<p><b>Açılar:</b><ul>${h.angles.map(a=>`<li>${a}</li>`).join('')}</ul></p>`;
      (h.council_pitches||[]).forEach(p=>{ html += `<p><span class="persona ${p.name.toLowerCase()}">${p.name}:</span> ${p.pitch}</p>`; });
      html += `</div></details>`;
    });
  }
  $('#dayDetail').innerHTML = html;
}

let _pastedImage = null;  // {base64, mime}
$('#askText').addEventListener('paste', (e) => {
  for (const item of e.clipboardData.items) {
    if (item.type.startsWith('image/')) {
      const file = item.getAsFile();
      const reader = new FileReader();
      reader.onload = () => {
        _pastedImage = {base64: reader.result.split(',')[1], mime: item.type};
        $('#imgPreview').src = reader.result;
        $('#imgPreviewBox').style.display = 'block';
      };
      reader.readAsDataURL(file);
      e.preventDefault();
      return;
    }
  }
});
function clearImage(){ _pastedImage = null; $('#imgPreviewBox').style.display = 'none'; }

async function askCouncil(){
  const q = $('#askText').value.trim();
  if(!q && !_pastedImage) return;
  $('#askText').disabled = true;
  document.querySelector('#tab-kararlar button.primary').disabled = true;
  $('#askStatus').textContent = 'Konsey tartışıyor (30-60sn sürebilir, resim varsa biraz daha)...';
  $('#askTurns').innerHTML = '';
  const body = {question: q};
  if (_pastedImage) { body.image_base64 = _pastedImage.base64; body.image_mime = _pastedImage.mime; }
  const r = await api('/api/ask', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
  if(r.error){ $('#askStatus').textContent = 'HATA: '+r.error; $('#askText').disabled=false; document.querySelector('#tab-kararlar button.primary').disabled=false; return; }
  clearImage();
  pollAsk(r.job);
}
async function pollAsk(jid){
  const j = await api(`/api/job/${jid}`);
  if(j.status==='running'){ setTimeout(()=>pollAsk(jid), 2000); return; }
  $('#askText').disabled = false;
  document.querySelector('#tab-kararlar button.primary').disabled = false;
  if(!j.transcript){ $('#askStatus').textContent = 'HATA: '+(j.out||'bilinmeyen'); return; }
  $('#askStatus').textContent = 'Tamamlandı.';
  $('#askTurns').innerHTML = j.transcript.map((t,i) => {
    const last = i === j.transcript.length-1;
    return `<div class="card" style="margin-bottom:8px${last?';border-color:#d29922':''}">
      <span class="persona ${t.speaker}">${t.name}</span>${last?' — <b>KONSEY KARARI</b>':''}
      <div style="margin-top:6px">${t.text}</div>
    </div>`;
  }).join('');
  $('#askText').value = '';
  loadChat();
}

async function loadChat(){
  const h = await api('/api/council_chat');
  $('#chatHistory').innerHTML = (h||[]).slice().reverse().slice(0,20).map(s => {
    const t = new Date(s.ts*1000).toLocaleString('tr-TR');
    const body = (s.transcript||[]).map(m=>`<p><span class="persona ${m.speaker}">${m.name}:</span> ${m.text}</p>`).join('');
    return `<details><summary>${t} — ${s.question}</summary>${body}</details>`;
  }).join('') || '(kayıt yok)';
}

async function loadPredictions(){
  const d = await api('/api/predictions');
  const sc = d.scorecard || {};
  $('#predScore').innerHTML = `<span>İsabet: ${sc.hit||0} / Iskala: ${sc.miss||0} / Açık: ${sc.open||0}</span><span class="pill">${sc.accuracy||'n/a'}</span>`;
  $('#predList').innerHTML = (d.rows||[]).map(r => `
    <div class="card" style="margin-bottom:8px">
      <div><b>${r.claim}</b></div>
      <div style="color:#8b949e;font-size:12px">${r.made} → ${r.resolves_by} | ${r.entity||''}</div>
      <div class="pill ${r.status==='hit'?'ok':(r.status==='miss'||r.status==='invalid'?'bad':'warn')}">${r.status}</div>
      ${r.status==='open'? `<div style="margin-top:6px">
        <button class="act" onclick="resolvePred('${r.id}','hit')">İsabet say</button>
        <button class="act" onclick="resolvePred('${r.id}','miss')">Iskala say</button>
        <button class="act risky" onclick="resolvePred('${r.id}','invalid')">Geçersiz say</button>
      </div>`:''}
    </div>`).join('');
}
async function resolvePred(id, status){
  await api('/api/predictions/resolve', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({id, status, note:'panelden elle isaretlendi'})});
  loadPredictions();
}

async function uretBaslat(){
  if(!confirm('Yeni bir video üretilecek (2-4 dk sürer) ve hassas bir iddia yoksa DOĞRUDAN herkese açık yayınlanacak. Devam edilsin mi?')) return;
  $('#uretStatus').textContent = 'üretiliyor (2-4 dk)...';
  const r = await api('/api/maint/daily', {method:'POST', headers:JH, body: JSON.stringify({kind:'morning'})});
  $('#uretStatus').textContent = r.ok===false ? ('HATA: '+(r.error||'başlatılamadı')) : 'başlatıldı — bittiğinde aşağıda görünecek.';
  setTimeout(()=>{ refreshStatus(); loadUretBugun(); loadPending(); }, 4*60*1000);
}
async function loadUretBugun(){
  const s = await api('/api/status');
  const box = $('#uretBugun');
  if(!s.today_video || !s.today_video.video_id){ box.innerHTML = `<p style="color:#8b949e">Bugün henüz video üretilmedi.</p><p>${s.today_topic? ('Son seçilen konu: '+s.today_topic) : ''}</p>`; return; }
  const link = `https://youtu.be/${s.today_video.video_id}`;
  box.innerHTML = s.today_video_pending
    ? `<p>🟠 Bugün 1 video üretildi, <b>onayını bekliyor</b>.</p><p><a href="${link}" target="_blank">${link}</a></p><button class="act" onclick="gotoTab('onay');setTimeout(()=>window.scrollTo(0,document.body.scrollHeight),100)">Aşağıda onay listesine git</button>`
    : `<p>🟢 Bugün 1 video üretildi ve <b>yayınlandı</b>.</p><p><a href="${link}" target="_blank">${link}</a></p>`;
}
async function loadPending(){
  const rows = await api('/api/pending');
  $('#pendingList').innerHTML = rows.length ? rows.map(r => `
    <div class="card" style="margin-bottom:8px">
      <div><b>${r.title||r.video_id}</b></div>
      <div style="color:#8b949e;font-size:12px">taraf: ${r.entity||'-'} | şiddet: ${r.severity} | ${r.date}</div>
      <div style="margin:6px 0">${r.reason||''}</div>
      <a href="https://youtu.be/${r.video_id}" target="_blank">https://youtu.be/${r.video_id}</a>
      <div style="margin-top:8px">
        <button class="act primary" onclick="approvePending('${r.video_id}')">Onayla ve Yayınla</button>
        <button class="act risky" onclick="rejectPending('${r.video_id}')">Reddet (kuyruktan çıkar)</button>
      </div>
    </div>`).join('') : '(bekleyen yok)';
}
async function approvePending(id){
  if(!confirm('Bu video HERKESE AÇIK yayınlanacak. Emin misin?')) return;
  const r = await api('/api/pending/approve', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({video_id:id})});
  pollJob(r.job); setTimeout(loadPending, 3000);
}
async function rejectPending(id){
  await api('/api/pending/reject', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({video_id:id})});
  loadPending();
}

async function loadAccount(){
  const a = await api('/api/account');
  $('#acctStatus').innerHTML = a.connected
    ? `<div class="row"><span>Durum</span><span class="pill ok">BAĞLI</span></div><div class="row"><span>Erişim tokeni</span><span>${(a.expiry||'').slice(0,16)}</span></div>`
    : `<div class="row"><span>Durum</span><span class="pill bad">BAĞLI DEĞİL</span></div>`;
}
async function reconnect(){
  $('#acctOut').textContent = 'Bağlantı isteniyor...';
  const r = await api('/api/account/reconnect', {method:'POST'});
  pollReconnect(r.job);
}
async function pollReconnect(jid){
  const j = await api(`/api/job/${jid}`);
  if(j.auth_url) $('#acctOut').innerHTML = `Bu linki KENDİ tarayıcında aç ve onayla:<br><a href="${j.auth_url}" target="_blank">${j.auth_url}</a>`;
  if(j.status==='running'){ setTimeout(()=>pollReconnect(jid), 1500); return; }
  if(!j.auth_url) $('#acctOut').textContent = j.out || 'tamamlandı';
  loadAccount();
}

function bgEsc(t){ return String(t==null?'':t).replace(/[&<>"]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
async function bgJob(jid, el){
  for(;;){
    const j = await api('/api/job/'+jid);
    if(j.status!=='running'){ if(el) el.textContent = j.out || '(çıktı yok)'; return j; }
    if(el) el.textContent = 'çalışıyor… '+Math.round((Date.now()/1000)-(j.started||0))+' sn';
    await new Promise(r=>setTimeout(r,2000));
  }
}
var _bgSel = new Set(), _bgVideos = [], _bgKontrolN = 0;
async function bgLoad(){
  const d = await api('/api/bugun/durum');
  if(d.error){ $('#bgDurum').textContent = d.error; return; }
  const sc = $('#bgSayac'); sc.textContent = d.adet+'/'+d.limit+' video'; sc.className = 'pill '+(d.dolu?'bad':'ok');
  $('#bgDurum').innerHTML = 'Ses sunucusu: <span class="pill '+(d.ses_hazir?'ok':'bad')+'">'+(d.ses_hazir?'ÇALIŞIYOR':'DURDU')+'</span>'
    + (d.ses_hazir?'':' <button class="act" onclick="gotoTab(\'bakim\')">Bakım → başlat</button>')
    + ' · Bugünkü paket: '+(d.paket?'hazır':'yok')+(d.dolu?' · <b>günlük sınır doldu</b>':'');
  const sel = $('#bgReceipt'), cur = sel.value; sel.innerHTML = '<option value="">(yok — sayfadan otomatik)</option>'+d.receipts.map(r=>'<option>'+bgEsc(r)+'</option>').join(''); sel.value = cur;
  _bgVideos = d.videolar||[];
  $('#bgVideolar').innerHTML = _bgVideos.length ? 'Bugünün videoları: '+_bgVideos.map(v=>'<a href="https://youtu.be/'+bgEsc(v.video_id)+'" target="_blank">'+bgEsc(v.video_id)+'</a>').join(' · ') : 'Bugün henüz video yok.';
  $('#bgKontrol').innerHTML = (d.kontrol||[]).map((k,i)=>'<label style="display:block;font-size:13px"><input type="checkbox" class="bgChk"> '+bgEsc(k)+'</label>').join('');
  _bgKontrolN = (d.kontrol||[]).length;
  const g = await api('/api/bugun/gundem'); bgAdayCiz(g);
}
function bgAdayCiz(g){
  const a = (g&&g.adaylar)||[];
  $('#bgGundemSt').textContent = g&&g.zaman ? 'son yenileme: '+g.zaman.replace('T',' ') : 'henüz çekilmedi'
  if(g&&g.rapor) $('#bgGundemSt').textContent += ' · '+g.rapor.join(' · ')+' · konuya uygun: '+(g.uygun_sayi==null?'?':g.uygun_sayi);
  $('#bgAdaylar').innerHTML = a.length ? a.map((x,i)=>'<div class="row" style="display:block;border-bottom:1px solid #21262d;padding:6px 0"><b>'+x.puan+'</b> '+bgEsc(x.title)+'<div style="font-size:12px;color:#8b949e">'+bgEsc(x.alan)+' · '+x.haber_sayisi+' haber '+(x.etiketler||[]).map(e=>'<span class="pill ok">'+bgEsc(e)+'</span>').join(' ')+(x.engel?' <span class="pill bad">'+bgEsc(x.engel)+'</span>':'')+'</div>'+(x.engel?'':'<button class="act" style="margin-top:3px" onclick="bgSec('+i+')">Seç</button>')+'</div>').join('') : '<span style="color:#8b949e">Aday yok. «Gündemi yenile»ye bas.</span>';
  window._bgAday = a;
}
async function bgSutun(s){
  if(s==='receipt'){ window._bgSutun='receipt'; return bgAnaliz('receipt'); }
  const r = await api('/api/bugun/sutun_onay',{method:'POST',headers:JH,body:JSON.stringify({sutun:s})});
  if(!r.ok){ $('#bgAnalizSt').textContent='HATA: '+r.error; return; }
  window._bgSutun = s; bgAnalizPoll(); bgGuven(); bgSutunEtiket();
  $('#bgOut').scrollIntoView({behavior:'smooth',block:'center'});
}
function bgSutunEtiket(){ const e=$('#bgSutunEtiket'); if(e) e.textContent = 'Seçili sütun: '+(window._bgSutun||'receipt'); }
function bgSec(i){ $('#bgUrl').value = window._bgAday[i].url; bgKaynak(); }
async function bgGundem(){
  $('#bgGundemSt').textContent = 'çekiliyor…';
  const r = await api('/api/bugun/gundem',{method:'POST'});
  await bgJob(r.job, $('#bgGundemSt')); bgLoad();
}
async function bgKaynak(){
  const url = $('#bgUrl').value.trim(); if(!url){ $('#bgKaynakSt').textContent='Adres yaz.'; return; }
  $('#bgKaynakSt').textContent = 'sayfa çekiliyor…'; $('#bgKanit').innerHTML='';
  const r = await api('/api/bugun/kaynak',{method:'POST',headers:JH,body:JSON.stringify({url, claim_key: window._bgClaimKey||''})});
  if(!r.ok){ $('#bgKaynakSt').textContent = 'HATA: '+(r.error||'?'); return; }
  $('#bgKaynakSt').textContent = r.title+' — '+r.cumle_sayisi+' cümle'+(r.birincil?' · birincil kaynak':' · ⚠ birincil kaynak listesinde değil');
  _bgSel = new Set(r.onerilen);
  $('#bgKanit').innerHTML = '<div style="font-size:13px;margin-bottom:4px"><b>İddia cümlesi:</b> '+(r.claim?bgEsc(r.claim):'<i>sayfada bulunamadı</i>')+'</div>'
    + r.adaylar.map(c=>'<label style="display:block;font-size:13px;padding:2px 0"><input type="checkbox" '+(_bgSel.has(c.no)?'checked':'')+' onchange="bgTick('+c.no+',this.checked)"> <b>'+c.no+'.</b> '+bgEsc(c.metin.slice(0,260))+'</label>').join('');
}
function bgTick(n, on){ if(on) _bgSel.add(n); else _bgSel.delete(n); }
async function bgPaket(){
  const facts = $('#bgFacts').value.split(';').map(x=>x.trim()).filter(Boolean);
  const r = await api('/api/bugun/paket',{method:'POST',headers:JH,body:JSON.stringify({secim:[..._bgSel],facts})});
  $('#bgPaketSt').textContent = r.ok ? ('Hazır: '+r.kanit+' kanıt'+(r.iddia?'':' (iddia cümlesi yok)')+(r.uyarilar&&r.uyarilar.length?' · UYARI: '+r.uyarilar.join(' | '):'')) : 'HATA: '+r.error;
  bgLoad();
}
async function bgAdim(kind){
  const out = $('#bgOut'); out.textContent = 'başlıyor…';
  const r = await api('/api/bugun/'+kind,{method:'POST',headers:JH,body:JSON.stringify({receipt:$('#bgReceipt').value, sutun: window._bgSutun||'receipt'})});
  if(r.error){ out.textContent = 'HATA: '+r.error; return; }
  await bgJob(r.job, out); bgLoad();
}
async function bgYayinla(){
  if(!_bgVideos.length){ $('#bgYayinSt').textContent='Bugün yüklenmiş video yok.'; return; }
  const v = _bgVideos[_bgVideos.length-1].video_id;
  const n = document.querySelectorAll('.bgChk:checked').length;
  if(!confirm('Video '+v+' HERKESE AÇIK yayınlanacak. Emin misin?')) return;
  const r = await api('/api/bugun/yayinla',{method:'POST',headers:JH,body:JSON.stringify({video_id:v,onay:$('#bgOnay').value,isaretli:n})});
  if(r.error){ $('#bgYayinSt').textContent='HATA: '+r.error; return; }
  await bgJob(r.job, $('#bgYayinSt')); $('#bgOnay').value=''; bgLoad();
}
var _bgAnalizTimer = null;
async function bgAnaliz(sutun){
  $('#bgAnalizSt').textContent = 'başlıyor…';
  const r = await api('/api/bugun/analiz',{method:'POST',headers:JH,body:JSON.stringify({sutun: (typeof sutun==='string'?sutun:'')})});
  if(r.error){ $('#bgAnalizSt').textContent = 'HATA: '+r.error; return; }
  bgAnalizPoll();
}
async function bgAnalizPoll(){
  clearTimeout(_bgAnalizTimer);
  const d = await api('/api/bugun/analiz');
  bgAnalizCiz(d);
  if(d.durum==='calisiyor') _bgAnalizTimer = setTimeout(bgAnalizPoll, 3000);
}
function bgAnalizCiz(d){
  const AD = {veri:'1/5 Kanal verisi ve sütun sonuçları analiz ediliyor…', konu:'2/5 Haber adayları taranıyor…', sayfa:'3/5 Aday sayfaları okunuyor (iddia ve kanıt var mı)…', tartisma:'4/5 Konsey tartışıyor…', bitti:'Bitti'};
  $('#bgAnalizSt').textContent = d.durum==='calisiyor' ? (AD[d.adim]||'çalışıyor…') : (d.durum==='yok'?'':'');
  { const n=new Date(), yy=n.getFullYear()+'-'+String(n.getMonth()+1).padStart(2,'0')+'-'+String(n.getDate()).padStart(2,'0'); if(d.basladi && d.basladi.slice(0,10)!==yy) $('#bgAnalizSt').textContent = '(son analiz '+d.basladi.slice(0,10)+' tarihli, bugün için yeniden başlat)'; }
  const box = $('#bgAnalizBox'); if(!d.adaylar && d.durum!=='aday_yok' && !d.sutunlar){ box.innerHTML=''; return; }
  const k = d.karar||{}, ad = d.adaylar||[];
  const bul = id => ad.find(a=>a.id===id);
  let h = '';
  if(d.sutunlar){
    const o = d.sutun_oneri||{}, SN = {}; d.sutunlar.forEach(r=>SN[r.sutun]=r);
    h += '<div style="border:1px solid #30363d;border-radius:8px;padding:10px;margin-bottom:8px"><div style="font-size:12px;color:#8b949e">SÜTUN ÖNERİSİ ('+bgEsc(o.mod||'')+')</div>'
      + '<div style="font-size:16px;margin:4px 0"><b>'+bgEsc((SN[o.sutun]||{}).ad||o.sutun)+'</b></div><div>'+bgEsc(o.neden||'')+'</div>'
      + '<table style="width:100%;font-size:13px;margin-top:8px;border-collapse:collapse"><tr style="color:#8b949e;text-align:left"><th>Sütun</th><th>Deneme</th><th>Ort. izlenme</th><th>Dönemine göre</th><th>Ort. yorum</th><th>Ort. abone</th><th>Med. tutma %</th><th></th></tr>'
      + d.sutunlar.filter(r=>r.aktif||r.deneme).map(r=>'<tr><td>'+bgEsc(r.ad)+(r.aktif?'':' <span style="color:#8b949e">(bugün kapalı)</span>')+'</td><td>'+r.deneme+'</td><td>'+(r.ort_izlenme==null?'-':r.ort_izlenme)+'</td><td>'+(r.med_goreli==null?'-':r.med_goreli+'x')+'</td><td>'+(r.ort_yorum==null?'-':r.ort_yorum)+'</td><td>'+(r.ort_abone==null?'-':r.ort_abone)+'</td><td>'+(r.med_tutma==null?'-':r.med_tutma)+'</td><td>'+(r.aktif&&r.sutun!=='diger'?'<button class="act'+(r.sutun===o.sutun?' primary':'')+'" onclick="bgSutun(\''+r.sutun+'\')">'+(r.sutun==='receipt'?'Receipt adaylarını analiz et':'Bu sütunla devam')+'</button>':'')+'</td></tr>').join('')
      + '</table>' + (((SN.diger||{}).ornek||[]).length?'<details style="margin-top:6px"><summary style="font-size:13px">Sınıflanamayan videolar ('+SN.diger.deneme+') — örnek başlıklar</summary>'+SN.diger.ornek.map(t=>'<div style="font-size:12px;color:#8b949e">• '+bgEsc(t)+'</div>').join('')+'</details>':'') + '<div style="font-size:12px;color:#8b949e;margin-top:6px">Her sütun en az 3 kez denenmeden elenmez; örnek az olduğu için bu sonuçlar yön gösterir, kanıt değildir.</div>'
      + (d.sutun_onay?'<div style="margin-top:6px;color:#3fb950">Seçilen sütun: '+bgEsc((SN[d.sutun_onay.secim]||{}).ad||d.sutun_onay.secim)+(d.sutun_onay.degisti?' (öneriden farklı)':'')+'. Aşağıdan 4 · Üret\'e bas.</div>':'')+'</div>';
  }
  h += d.gundem_mesaj ? '<div style="font-size:12px;color:#8b949e;margin-bottom:6px">Kaynak taraması: '+bgEsc(d.gundem_mesaj)+'</div>' : '';
  if(d.durum==='aday_yok') h += '<div style="margin-bottom:6px"><b>Bugün için uygun aday bulunamadı</b> (sayfasında şirketin kendi iddiası ve yeterli kanıt olan haber çıkmadı). Gündemi biraz sonra yenile ya da aşağıya kendi adresini yapıştır.</div>';
  if(k.secim && bul(k.secim)){
    const a = bul(k.secim);
    h += '<div style="border:1px solid #1f6feb;border-radius:8px;padding:10px;margin-bottom:8px"><div style="font-size:12px;color:#8b949e">'+(k.kaynak==='konsey'?'KONSEY ÖNERİSİ':k.kaynak==='tek-aday'?'TEK ADAY (tartışma yapılmadı)':'KURAL TABANLI ÖNERİ (Konsey geçerli seçim üretmedi)')+'</div>'
      + '<div style="font-size:16px;margin:4px 0"><b>'+bgEsc(a.title)+'</b></div><div style="font-size:12px;color:#8b949e">'+bgEsc(a.alan)+' · puan '+a.puan+'</div>'
      + ((a.hazir&&a.hazir.iddia)?'<div style="margin-top:6px;font-size:13px"><b>Sayfadaki iddia (kodla okundu):</b> “'+bgEsc(a.hazir.iddia)+'” · kanıt cümlesi: '+a.hazir.kanit+'</div>':'')
      + '<div style="margin-top:6px"><b>Gerekçe:</b> '+bgEsc(k.gerekce)+'</div>'+(k.aci?'<div><b>Açı:</b> '+bgEsc(k.aci)+'</div>':'')
      + '<div style="margin-top:8px"><button class="act primary" onclick="bgOnay(\''+k.secim+'\')">Onayla ve kaynağı çek</button> '
      + (k.alternatif||[]).map(i=>bul(i)?'<button class="act" onclick="bgOnay(\''+i+'\')">Bunu seç: '+bgEsc(bul(i).title.slice(0,40))+'…</button>':'').join(' ')
      + ' <button class="act" onclick="bgRed()">Hiçbiri, yeniden analiz</button></div>'
      + (d.onay?'<div style="font-size:12px;color:#8b949e;margin-top:6px">Onaylanan: '+bgEsc(d.onay.secim)+(d.onay.degisti?' (Konsey önerisinden farklı)':'')+'</div>':'')+'</div>';
  }
  if((d.elenen||[]).length) h += '<details><summary>Elenen adaylar ('+d.elenen.length+') — sayfasında iddia/kanıt yok</summary>'+d.elenen.map(a=>'<div style="font-size:13px;padding:3px 0">'+bgEsc(a.title)+' <span style="color:#8b949e">('+bgEsc(a.alan)+') → '+bgEsc((a.hazir||{}).hata||'')+'</span></div>').join('')+'</details>';
  h += '<details><summary>Adaylar ('+ad.length+')</summary>'+ad.map(a=>'<div style="font-size:13px;padding:3px 0"><b>'+a.id+'</b> '+bgEsc(a.title)+' <span style="color:#8b949e">('+bgEsc(a.alan)+', puan '+a.puan+')</span></div>').join('')+'</details>';
  if(d.veri) h += '<details><summary>Kanal verisi özeti</summary><pre style="white-space:pre-wrap;font-size:12px">'+bgEsc(JSON.stringify(d.veri.sinyaller||d.veri,null,1))+(d.veri.kanal_ok?'':'\nUYARI: kanal verisi alınamadı: '+bgEsc(d.veri.kanal_hata||''))+'</pre></details>';
  if(d.transcript && d.transcript.length) h += '<details><summary>Konsey tartışması</summary>'+d.transcript.map(t=>'<div style="margin:6px 0;font-size:13px"><b>'+bgEsc(t.name||t.speaker)+':</b> '+bgEsc(t.text)+'</div>').join('')+'</details>';
  if(d.tartisma_hata) h += '<div style="color:#f85149;font-size:12px">Tartışma hatası: '+bgEsc(d.tartisma_hata)+'</div>';
  box.innerHTML = h;
}
async function bgOnay(id){
  const r = await api('/api/bugun/onay',{method:'POST',headers:JH,body:JSON.stringify({secim:id})});
  if(!r.ok){ $('#bgAnalizSt').textContent = 'HATA: '+r.error; return; }
  window._bgSutun='receipt'; bgSutunEtiket(); $('#bgUrl').value = r.url; window._bgClaimKey = r.iddia_anahtar||''; bgAnalizPoll(); bgGuven(); bgKaynak();
  $('#bgUrl').scrollIntoView({behavior:'smooth',block:'center'});
}
async function bgRed(){ await api('/api/bugun/red',{method:'POST'}); bgAnaliz(); }
async function bgGuven(){
  const g = await api('/api/bugun/guven'); if(g.error) return;
  const c = ok => ok?'<span class="pill ok">✓</span>':'<span class="pill bad">✗</span>';
  $('#bgGuven').innerHTML = '<b>Otomatiğe geçiş ölçütü</b> (son '+g.gun+' gün): '
    + c(g.sartlar.ihlal_yok)+' koruma ihlali '+g.ihlal+' · '
    + c(g.sartlar.onay_orani)+' öneri onayı '+g.degismeden_onay+'/'+g.oneri+' (en az %70 ve '+g.gun+' öneri) · '
    + c(g.sartlar.retention)+' izlemeye devam '+(g.retention==null?'(Studio\'dan gir)':g.retention+'%')+' (taban %'+g.taban+') '
    + '<input id="bgRet" placeholder="%" style="width:60px"> <button class="act" onclick="bgRetKaydet()">Kaydet</button>'
    + (g.otomatige_hazir?' · <b style="color:#3fb950">Üçü de tamam: otomatiğe geçiş önerilebilir.</b>':'');
}
async function bgRetKaydet(){ const r = await api('/api/bugun/guven/retention',{method:'POST',headers:JH,body:JSON.stringify({deger:$('#bgRet').value})}); if(!r.ok) alert(r.error); bgGuven(); }
async function bgPaylas(pl){
  const r = await api('/api/bugun/paylas',{method:'POST',headers:JH,body:JSON.stringify({platform:pl})});
  if(!r.ok){ $('#bgPaylasBox').textContent = 'HATA: '+r.error; return; }
  const f = (e,t)=> t ? '<div style="margin:6px 0"><div style="font-size:12px;color:#8b949e">'+e+'</div><textarea readonly rows="3" style="width:100%;max-width:640px" onclick="this.select()">'+bgEsc(t)+'</textarea></div>' : '';
  $('#bgPaylasBox').innerHTML = f('Başlık',r.baslik)+f('Metin',r.govde)+f('İlk yorum',r.ilk_yorum)
    + (r.uyari&&r.uyari.length?'<div style="color:#f85149">UYARI (paylaşma, düzelt): '+bgEsc(r.uyari.join(' | '))+'</div>':'')
    + '<div style="font-size:12px;color:#8b949e">'+bgEsc(r.not||'')+'</div>'
    + '<button class="act" onclick="bgPaylastim(\''+pl+'\')">Paylaştım (kaydet)</button>';
}
async function bgPaylastim(pl){ await api('/api/bugun/paylastim',{method:'POST',headers:JH,body:JSON.stringify({platform:pl})}); $('#bgPaylasBox').insertAdjacentHTML('beforeend','<div style="color:#3fb950">Kaydedildi.</div>'); }

function foldTab(hostId, guests){
  const host = $('#tab-'+hostId);
  guests.forEach(([id,title,open])=>{
    const g = $('#tab-'+id); if(!g) return;
    const d = document.createElement('details'); d.className='fold'; d.dataset.guest=id;
    const sm = document.createElement('summary'); sm.textContent = title; d.appendChild(sm);
    g.classList.add('guest'); d.appendChild(g); host.appendChild(d);
    d.addEventListener('toggle', ()=>{ if(d.open && typeof onTab==='function') onTab(id); });
    if(open) d.open = true;
  });
}
foldTab('sistem', [['durum','Durum',true],['bakim','Bakım ve onarım',false],['hesap','Hesap (YouTube bağlantısı)',false],['telefon','Telefon bağlantısı',false]]);
foldTab('analiz', [['takip','Büyüme kararları',false],['tahmin','Tahmin defteri (motorun kendini sınaması)',false]]);
foldTab('bugun', [['kararlar','Konsey arşivi (geçmiş tartışmalar)',false],['dagitim','Gelişmiş paylaşım araçları (Dağıtım)',false]]);

async function ogLoad(){
  $('#ogSt').textContent='hesaplanıyor…';
  const d = await api('/api/ogrenme');
  if(!d.ok){ $('#ogSt').textContent='HATA/veri yok: '+(d.error||'tracker verisi yok, Büyüme Kararları\'ndan "Şimdi yenile"ye bas'); return; }
  $('#ogSt').textContent = d.n+' video'; const k=d.karne, B=k.bolumler;
  const tab=(baslik,rows)=>'<div style="margin-top:10px"><b>'+baslik+'</b><table style="width:100%;font-size:13px;border-collapse:collapse"><tr style="color:#8b949e;text-align:left"><th>Grup</th><th>n</th><th>Med. izlenme</th><th>Dönemine göre</th><th>Med. tutma %</th><th>Abone/1000</th><th>Yorum/1000</th><th>Güven</th></tr>'
    +rows.map(r=>'<tr><td>'+bgEsc(r.ad)+'</td><td>'+r.n+'</td><td>'+(r.med_izlenme==null?'-':r.med_izlenme)+'</td><td>'+(r.med_goreli==null?'-':r.med_goreli+'x')+'</td><td>'+(r.med_tutma==null?'-':r.med_tutma)+'</td><td>'+(r.abone_1000==null?'-':r.abone_1000)+'</td><td>'+(r.yorum_1000==null?'-':r.yorum_1000)+'</td><td style="color:'+(r.guven==='çok az'?'#f85149':r.guven==='yön'?'#d29922':'#3fb950')+'">'+r.guven+'</td></tr>').join('')+'</table></div>';
  $('#ogBox').innerHTML = '<div>Genel: '+k.genel.n+' video · medyan izlenme '+k.genel.med_izlenme+' · medyan tutma %'+k.genel.med_tutma+' · abone/1000 '+k.genel.abone_1000+' · yorum/1000 '+k.genel.yorum_1000+'</div>'
    + (k.oneriler.length?'<div style="margin-top:8px"><b>Deneme önerileri</b>'+k.oneriler.map(o=>'<div style="font-size:13px">• '+bgEsc(o.metin)+'</div>').join('')+'</div>':'<div style="margin-top:8px;color:#8b949e">Henüz belirgin (n≥5 ve ≥%30 fark) bir kalıp yok.</div>')
    + '<div style="margin-top:8px"><b>Önerilen hashtag seti (deneme):</b> '+bgEsc(d.hashtag.hashtagler.join(' '))+'<div style="font-size:12px;color:#8b949e">'+bgEsc(d.hashtag.dayanak.join(' · '))+' — '+bgEsc(d.hashtag.not)+'</div></div>'
    + tab('Sütun',B.sutun)+tab('Başlıkta sayı',B.sayi)+tab('Başlık biçimi',B.soru)+tab('Başlık uzunluğu',B.uzunluk)+tab('Yayın günü',B.gun)+tab('Hashtag (marka etiketleri hariç, n≥3)',B.hashtag);
}
function onTab(name){
  if(name==='analiz') ogLoad();
  if(name==='bugun'){ bgLoad(); bgGuven(); bgAnalizPoll(); }
  if(name==='telefon') phoneRefresh();
  if(name==='onay'){ loadUretBugun(); loadPending(); }
  if(name==='bakim'){ atLoad(); voicePoll(); loadPorts(); loadTasks(); loadLogs(); loadAutostart(); loadLastGood(); }
  if(name==='asistan') loadCatalog();
  if(name==='analiz') anLoad();
  if(name==='takip') tkLoad();
  if(name==='kod') kodChips();
  if(name==='kod') kodInit();
  if(name==='yardim') loadManual();
}

/* ---- telefon ---- */
let _phoneTimer=null;
async function phoneRefresh(){
  const s = await api('/api/phone');
  phoneExtras(s);
  let html;
  if(!s.cloudflared) html = '<span class="pill bad">cloudflared kurulu değil</span> Bakım &gt; Sistem Kontrolü sekmesine bak.';
  else if(s.running && s.link) html = '<span class="pill ok">BAĞLI</span> <span style="color:#8b949e;font-size:12px">Link ilk dakikada açılmazsa 1 dakika bekleyip tekrar dene.</span>';
  else if(s.starting) html = '<span class="pill warn">bağlanıyor... (bazen 1 dakikaya kadar sürer)</span>';
  else html = '<span class="pill bad">KAPALI</span>';
  $('#phoneState').innerHTML = html;
  const box = $('#phoneLinkBox');
  if(s.link){ box.style.display='block'; $('#phoneLink').value = s.link; $('#phoneQr').innerHTML = s.qr_svg || '(QR için: python -m pip install qrcode)'; }
  else box.style.display='none';
  clearTimeout(_phoneTimer);
  if(s.starting) _phoneTimer = setTimeout(phoneRefresh, 2000);
}
async function phoneStart(){ await api('/api/phone/start',{method:'POST'}); phoneRefresh(); }
async function phoneStop(){ await api('/api/phone/stop',{method:'POST'}); phoneRefresh(); }
function copyPhone(){ const el=$('#phoneLink'); el.select(); try{ navigator.clipboard.writeText(el.value); }catch(e){ document.execCommand('copy'); } }

/* ---- bakim ---- */
async function loadSelfcheck(){
  $('#selfcheckBox').textContent='kontrol ediliyor...';
  const rows = await api('/api/selfcheck');
  const bad = rows.filter(r=>!r.ok && !r.optional).length;
  $('#selfcheckBox').innerHTML = `<div style="margin-bottom:6px">${bad? `<span class="pill bad">${bad} EKSİK</span>` : '<span class="pill ok">HER ŞEY TAMAM</span>'}</div>` +
    rows.map(r=>`<div class="row" style="display:block"><span class="pill ${r.ok?'ok':(r.optional?'warn':'bad')}">${r.ok?'OK':(r.optional?'opsiyonel':'EKSİK')}</span> ${r.name} <span style="color:#8b949e;font-size:12px">— ${r.detail}</span>${r.ok?'':`<div style="color:#d29922;font-size:12px;margin-top:2px">Çözüm: ${r.fix}</div>`}</div>`).join('');
}
async function maintOrphans(){
  if(!confirm('Yayın sürecinden kalan öksüz chrome/node/ffmpeg/live_aura süreçleri kapatılacak (normal Chrome tarayıcına dokunulmaz). Devam?')) return;
  $('#maintOut').textContent='temizleniyor...';
  const r = await api('/api/maint/orphans',{method:'POST'});
  $('#maintOut').textContent = r.ok ? (r.killed.length? 'Kapatıldı: '+r.killed.join(', ') : 'Temizlenecek öksüz süreç yoktu.') : 'HATA: '+r.error;
}
async function loadPorts(){
  const rows = await api('/api/ports');
  $('#portsBox').innerHTML = rows.map(r=>`<div class="row" style="display:block"><b>:${r.port}</b> ${r.pid? `<span class="pill ok">AÇIK</span> pid ${r.pid} <span style="color:#8b949e;font-size:12px">${r.name||''}</span>` : '<span class="pill">boş</span>'}<div style="color:#8b949e;font-size:12px">${r.label}${r.pid && r.cmd? ' — '+r.cmd : ''}</div>${r.pid && [8123,8124,8790,8791,8796].includes(r.port)? `<button class="act risky" style="margin-top:4px" onclick="killPort(${r.port})">Bu portu kapat</button>`:''}</div>`).join('');
}
async function killPort(p){
  const warn = p===8123 ? 'DİKKAT: Bu, ANA Aura uygulamasının ses sunucusu. Kapatırsan ana uygulamanın sesi (Voice Mesh) durur. Sign Council canlı yayını için gerekli olabilir. Kapatılsın mı?' : ('Port '+p+' sahibi süreç kapatılacak. Devam?');
  if(!confirm(warn)) return;
  const r = await api('/api/maint/killport',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({port:p})});
  $('#maintOut').textContent = r.ok ? ('Port '+p+': '+r.result) : ('HATA: '+r.error);
  loadPorts();
}
async function loadTasks(){
  const rows = await api('/api/tasks');
  $('#tasksBox').innerHTML = rows.length ? rows.map(r=>`<div class="row" style="display:block"><b>${r.name}</b> <span class="pill ${r.result_text==='BASARILI'||r.result_text==='su an calisiyor'?'ok':(r.result_text==='hic calismadi'?'warn':'bad')}">${r.result_text}</span>
    <div style="color:#8b949e;font-size:12px">son: ${r.last||'-'} · sonraki: ${r.next||'-'} · durum: ${r.state} · ${r.only_when_logged_on? 'sadece oturum açıkken çalışır' : 'oturum açık olmasa da çalışır'}</div></div>`).join('') : '(SignCouncil* görevi bulunamadı)';
}
async function runDaily(kind){
  if(!confirm('Günlük üretim şimdi başlayacak (10-20 dk sürer) ve HERKESE AÇIK bir Short yayınlayabilir. Devam edilsin mi?')) return;
  const r = await api('/api/maint/daily',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({kind})});
  $('#dailyOut').textContent = r.ok ? 'Başlatıldı ('+r.started+') — ilerlemeyi aşağıdaki Loglar bölümünden izle.' : 'HATA: '+r.error;
  setTimeout(loadLogs, 4000);
}
async function loadLogs(){
  const rows = await api('/api/logs');
  $('#logSelect').innerHTML = rows.map(r=>`<option value="${r.name}">${r.name==='capture'?'yayın yakalama logu':r.name} — ${r.mtime}</option>`).join('');
  if(rows.length) loadLog();
}
async function loadLog(){
  const f = $('#logSelect').value;
  const d = await api('/api/logtail?f='+encodeURIComponent(f));
  $('#logBox').textContent = d.text; $('#logBox').scrollTop = $('#logBox').scrollHeight;
}
async function mkShortcuts(){
  const r = await api('/api/maint/shortcuts',{method:'POST'});
  $('#backupOut').textContent = r.ok ? ('Kısayollar hazır: '+r.created.length+' adet (simgeli, küçültülmüş konsol).') : ('HATA: '+(r.error||'kısayol oluşturulamadı'));
}
async function doBackup(){
  $('#backupOut').textContent='yedekleniyor...';
  const r = await api('/api/maint/backup',{method:'POST'});
  pollBackup(r.job);
}
async function pollBackup(jid){
  const j = await api('/api/job/'+jid);
  if(j.status==='running'){ setTimeout(()=>pollBackup(jid),1500); return; }
  $('#backupOut').textContent = j.out;
}
async function loadAutostart(){ const d = await api('/api/autostart'); $('#autostartChk').checked = !!d.enabled; }
async function setAutostart(on){ const d = await api('/api/autostart',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({enabled:on})}); $('#autostartChk').checked = !!d.enabled; }

/* ---- yardim / sorun cozucu ---- */
let _helpImage=null;
$('#helpText').addEventListener('paste', (e)=>{
  for(const item of e.clipboardData.items){
    if(item.type.startsWith('image/')){
      const reader=new FileReader();
      reader.onload=()=>{ _helpImage={base64:reader.result.split(',')[1], mime:item.type}; $('#helpImg').src=reader.result; $('#helpImgBox').style.display='block'; };
      reader.readAsDataURL(item.getAsFile()); e.preventDefault(); return;
    }
  }
});
function clearHelpImage(){ _helpImage=null; $('#helpImgBox').style.display='none'; }
async function askHelp(){
  const q=$('#helpText').value.trim();
  if(!q && !_helpImage) return;
  $('#helpBtn').disabled=true; $('#helpStatus').textContent='düşünüyor...'; $('#helpAnswer').textContent='';
  const body={question:q}; if(_helpImage){ body.image_base64=_helpImage.base64; body.image_mime=_helpImage.mime; }
  const r=await api('/api/help/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  clearHelpImage(); pollHelp(r.job);
}
async function pollHelp(jid){
  const j=await api('/api/job/'+jid);
  if(j.status==='running'){ setTimeout(()=>pollHelp(jid),1500); return; }
  $('#helpBtn').disabled=false;
  if(!j.answer){ $('#helpStatus').textContent='HATA'; $('#helpAnswer').textContent=j.out||'bilinmeyen hata'; return; }
  $('#helpStatus').textContent=''; $('#helpAnswer').textContent=j.answer;
}
async function loadManual(){ if($('#manualBox').textContent) return; const d=await api('/api/manual'); $('#manualBox').textContent=d.text; }


/* ---- uyari cubugu ---- */
const _FOLD_HOST = {durum:'sistem',bakim:'sistem',hesap:'sistem',telefon:'sistem',takip:'analiz',tahmin:'analiz',kararlar:'bugun',dagitim:'bugun',onay:'bugun',live:'sistem',yardim:'sistem'};
function gotoTab(name){
  const host = _FOLD_HOST[name] || name;
  const b = document.querySelector('nav button[data-tab="'+host+'"]'); if(b) b.click();
  const g = document.querySelector('#tab-'+name); const d = g && g.closest && g.closest('details');
  if(d){ d.open = true; setTimeout(()=>d.scrollIntoView({behavior:'smooth',block:'start'}),50); }
}
async function loadAlerts(){
  const rows = await api('/api/alerts');
  const bar = $('#alertBar'); bar.innerHTML='';
  (Array.isArray(rows)?rows:[]).forEach(a=>{
    const d=document.createElement('div'); d.className='alert '+a.level;
    const sp=document.createElement('span'); sp.textContent=a.text; d.appendChild(sp);
    if(a.tab){ const b=document.createElement('button'); b.textContent='Git'; b.onclick=()=>gotoTab(a.tab); d.appendChild(b); }
    if(a.ackable){ const b=document.createElement('button'); b.textContent='Tamam, gördüm'; b.onclick=async()=>{ await api('/api/alerts/ack',{method:'POST',headers:JH,body:JSON.stringify({id:a.id})}); loadAlerts(); }; d.appendChild(b); }
    bar.appendChild(d);
  });
}

/* ---- mikrofon (Turkce dikte) ---- */
function attachMic(btn, ta){
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if(!btn) return;
  if(!SR){ btn.style.display='none'; return; }
  let rec=null, on=false;
  btn.onclick=()=>{
    if(on){ rec.stop(); return; }
    rec=new SR(); rec.lang='tr-TR'; rec.interimResults=true; rec.continuous=false;
    const base = ta.value ? ta.value+' ' : '';
    rec.onresult=e=>{ let t=''; for(const r of e.results) t+=r[0].transcript; ta.value=base+t; };
    const done=()=>{ on=false; btn.textContent='🎤 Konuş'; };
    rec.onend=done; rec.onerror=done;
    try{ rec.start(); on=true; btn.textContent='⏹ Durdur'; }catch(e){ done(); }
  };
}

/* ---- asistan ---- */
async function loadCatalog(){
  if($('#asstCatalog').childElementCount) return;
  const rows = await api('/api/assistant/actions');
  const box=$('#asstCatalog');
  (Array.isArray(rows)?rows:[]).forEach(a=>{
    const d=document.createElement('div'); d.className='row'; d.style.display='block';
    const pill=document.createElement('span'); pill.className='pill '+(a.risk==='safe'?'ok':'warn'); pill.textContent=a.risk==='safe'?'otomatik':(a.sensitive?'onay+PIN':'onay ister');
    d.appendChild(pill); d.appendChild(document.createTextNode(' '+a.name+' — '+a.desc)); box.appendChild(d);
  });
}
async function asstSend(){
  const t=$('#asstText').value.trim(); if(!t) return;
  $('#asstBtn').disabled=true; $('#asstStatus').textContent='planlıyor...'; $('#asstOut').innerHTML='';
  const r=await api('/api/assistant/plan',{method:'POST',headers:JH,body:JSON.stringify({text:t})});
  if(!r.job){ $('#asstBtn').disabled=false; $('#asstStatus').textContent='HATA'; return; }
  pollPlan(r.job);
}
async function pollPlan(jid){
  const j=await api('/api/job/'+jid);
  if(j.status==='running'){ setTimeout(()=>pollPlan(jid),1200); return; }
  $('#asstBtn').disabled=false; $('#asstStatus').textContent='';
  if(!j.plan){ $('#asstOut').textContent='HATA: '+(j.out||'plan alınamadı'); return; }
  renderPlan(j.plan);
}
function mkCard(){ const d=document.createElement('div'); d.className='card'; d.style.marginBottom='8px'; return d; }
function renderPlan(plan){
  const box=$('#asstOut'); box.innerHTML='';
  if(plan.say){
    const d=mkCard(); const h=document.createElement('div'); h.style.cssText='color:#8b949e;font-size:12px'; h.textContent='Asistanın planı / yorumu (yapay zeka — işlem yapmaz, sonuçlar aşağıda sistemden gelir)';
    const p=document.createElement('div'); p.textContent=plan.say; d.appendChild(h); d.appendChild(p); box.appendChild(d);
  }
  (plan.steps||[]).forEach(st=>{
    const d=mkCard();
    const head=document.createElement('div');
    const pill=document.createElement('span'); pill.className='pill '+(st.risk==='safe'?'ok':'warn'); pill.textContent=st.risk==='safe'?'otomatik':(st.sensitive?'onay+PIN':'onay ister');
    head.appendChild(pill); head.appendChild(document.createTextNode(' '+st.action+' '+(Object.keys(st.params||{}).length?JSON.stringify(st.params):'')));
    const desc=document.createElement('div'); desc.style.cssText='color:#8b949e;font-size:12px'; desc.textContent=st.desc;
    const res=document.createElement('div'); res.className='step-res';
    d.appendChild(head); d.appendChild(desc); d.appendChild(res);
    if(st.risk==='safe'){ runStep(st,res); }
    else { const b=document.createElement('button'); b.className='act primary'; b.textContent='Çalıştır (onayla)'; b.style.marginTop='6px';
      b.onclick=()=>{ if(confirm('Bu işlem çalıştırılsın mı?\n\n'+st.action+' '+JSON.stringify(st.params||{})+'\n'+st.desc)){ b.remove(); runStep(st,res); } }; d.appendChild(b); }
    box.appendChild(d);
  });
}
async function runStep(st, res){
  res.textContent='çalışıyor...';
  const r=await api('/api/assistant/exec',{method:'POST',headers:JH,body:JSON.stringify({action:st.action,params:st.params})});
  if(r.error){ res.style.color='#f85149'; res.textContent='SONUÇ (sistem): HATA — '+r.error; return; }
  res.style.color=''; res.textContent='SONUÇ (sistem): '+(r.message||'tamam');
  if(r.job) pollStepJob(r.job,res);
}
async function pollStepJob(jid,res){
  const j=await api('/api/job/'+jid);
  if(j.status==='running'){ setTimeout(()=>pollStepJob(jid,res),2000); return; }
  let txt='';
  if(j.transcript) txt=j.transcript.map(t=>t.name+': '+t.text).join('\n\n');
  else if(j.rows) txt=j.rows.map(r=>(r.ok?'✓ ':'✗ ')+r.name+(r.detail?' — '+r.detail:'')).join('\n');
  else txt=j.out||'';
  res.textContent='SONUÇ (sistem): tamamlandı\n'+txt;
}

/* ---- kod ---- */
let _kod = {path:null, hash:null, pid:null};
function kodLockedUI(){ $('#kodLocked').style.display='block'; $('#kodUI').style.display='none'; }
async function kodInit(){ await kodTree(); }
async function kodTree(){
  const rows = await api('/api/code/tree?q='+encodeURIComponent($('#kodSearch').value||''));
  if(rows && rows.need==='local'){ kodLockedUI(); return; }
  $('#kodLocked').style.display='none'; $('#kodUI').style.display='block';
  const sel=$('#kodFile'); sel.innerHTML='';
  (Array.isArray(rows)?rows:[]).forEach(r=>{ const o=document.createElement('option'); o.value=r.path; o.textContent=r.path+'  ('+Math.round(r.size/1024)+' KB · '+r.mtime+')'; sel.appendChild(o); });
}
async function kodOpen(){
  const path=$('#kodFile').value; if(!path) return;
  const r=await api('/api/code/read?path='+encodeURIComponent(path));
  if(r.error){ $('#kodStatus').textContent='HATA: '+r.error; return; }
  _kod.path=r.path; _kod.hash=r.hash;
  $('#kodTitle').textContent=r.path+'  ('+r.lines+' satır)'; $('#kodEditor').value=r.content; $('#kodStatus').textContent=''; $('#kodBackups').innerHTML='';
}
async function kodSave(){
  if(!_kod.path){ $('#kodStatus').textContent='önce dosya seç'; return; }
  const r=await api('/api/code/write',{method:'POST',headers:JH,body:JSON.stringify({path:_kod.path,content:$('#kodEditor').value,hash:_kod.hash})});
  if(!r.ok){ $('#kodStatus').style.color='#f85149'; $('#kodStatus').textContent='KAYDEDİLMEDİ: '+(r.error||'?'); return; }
  $('#kodStatus').style.color='#3fb950'; $('#kodStatus').textContent='Kaydedildi (yedek: '+r.backup+'). .py ise değişiklik yeniden başlatınca geçerli olur.';
  const again=await api('/api/code/read?path='+encodeURIComponent(_kod.path)); if(again.hash) _kod.hash=again.hash;
}
async function kodBackups(){
  if(!_kod.path) return;
  const rows=await api('/api/code/backups?path='+encodeURIComponent(_kod.path));
  const box=$('#kodBackups'); box.innerHTML='';
  if(!Array.isArray(rows)||!rows.length){ box.textContent='(bu dosya için yedek yok)'; return; }
  rows.forEach(b=>{ const d=document.createElement('div'); d.className='row'; const sp=document.createElement('span'); sp.textContent=b.name+' ('+b.kb+' KB)';
    const bt=document.createElement('button'); bt.className='act'; bt.textContent='Bu sürüme dön'; bt.onclick=async()=>{ if(!confirm('Dosya bu yedeğe döndürülecek (şimdiki hali de yedeklenir). Devam?')) return;
      const r=await api('/api/code/restore',{method:'POST',headers:JH,body:JSON.stringify({path:_kod.path,name:b.name})}); $('#kodStatus').textContent=r.ok?'Geri alındı.':('HATA: '+r.error); kodOpen(); };
    d.appendChild(sp); d.appendChild(bt); box.appendChild(d); });
}
async function kodPropose(mode){
  const path=($('#kodNewPath').value||'').trim()||$('#kodFile').value;
  const instr=$('#kodInstr').value.trim();
  if(!path){ $('#kodAiStatus').textContent='önce dosya seç ya da yeni yol yaz'; return; }
  if(!instr){ $('#kodAiStatus').textContent='ne yapılacağını yaz'; return; }
  $('#kodAiStatus').textContent='yapay zeka çalışıyor (30-90 sn)...'; $('#kodProposal').innerHTML='';
  const r=await api('/api/code/propose',{method:'POST',headers:JH,body:JSON.stringify({path,instruction:instr,provider:$('#kodProvider').value,mode})});
  if(!r.job){ $('#kodAiStatus').textContent='HATA: '+(r.error||'?'); return; }
  pollProposal(r.job);
}
async function pollProposal(jid){
  const j=await api('/api/job/'+jid);
  if(j.status==='running'){ setTimeout(()=>pollProposal(jid),2000); return; }
  $('#kodAiStatus').textContent='';
  const box=$('#kodProposal'); box.innerHTML='';
  if(!j.result){ box.textContent=j.out||'HATA'; return; }
  const res=j.result;
  if(res.answer!==undefined){ const d=document.createElement('div'); d.style.whiteSpace='pre-wrap'; d.textContent=res.answer; box.appendChild(d); return; }
  const sum=document.createElement('div'); sum.style.marginBottom='8px'; sum.textContent=res.summary||''; box.appendChild(sum);
  (res.warnings||[]).forEach(w=>{ const d=document.createElement('div'); d.className='pill warn'; d.style.display='block'; d.style.margin='4px 0'; d.textContent=w; box.appendChild(d); });
  if(res.diff){
    const df=document.createElement('div'); df.className='diff';
    res.diff.split('\n').forEach(l=>{ const sp=document.createElement('div'); sp.textContent=l||' '; if(l.startsWith('+')&&!l.startsWith('+++')) sp.className='add'; else if(l.startsWith('-')&&!l.startsWith('---')) sp.className='del'; else if(l.startsWith('@@')) sp.className='hunk'; df.appendChild(sp); });
    box.appendChild(df);
  }
  if(res.valid && res.pid){
    const ap=document.createElement('button'); ap.className='act primary'; ap.style.marginTop='8px'; ap.textContent='Uygula (yedek alınır, sözdizimi denetlenir)';
    ap.onclick=async()=>{ const r=await api('/api/code/apply',{method:'POST',headers:JH,body:JSON.stringify({pid:res.pid})});
      if(!r.ok){ box.appendChild(document.createTextNode(' HATA: '+(r.error||'?'))); return; }
      box.innerHTML=''; const ok=document.createElement('div'); ok.style.color='#3fb950'; ok.textContent='Uygulandı: '+r.path+' (yedek '+r.backup+'). Değişiklik yeniden başlatınca geçerli olur — önce Bakım > Kendini test et.'; box.appendChild(ok);
      $('#kodNewPath').value=''; await kodTree(); if(_kod.path===r.path) kodOpen(); };
    const cn=document.createElement('button'); cn.className='act'; cn.style.marginTop='8px'; cn.textContent='Vazgeç'; cn.onclick=()=>{ box.innerHTML=''; };
    box.appendChild(ap); box.appendChild(cn);
  }
}

/* ---- bakim: kendini test / yeniden baslat ---- */
async function runSelftest(){
  $('#selftestOut').textContent='test ediliyor (30-60 sn)...';
  const r=await api('/api/selftest/run',{method:'POST'}); pollSelftest(r.job);
}
async function pollSelftest(jid){
  const j=await api('/api/job/'+jid);
  if(j.status==='running'){ setTimeout(()=>pollSelftest(jid),2000); return; }
  const box=$('#selftestOut'); box.innerHTML='';
  const head=document.createElement('div'); head.style.marginBottom='6px'; head.textContent=j.out||''; box.appendChild(head);
  (j.rows||[]).forEach(r=>{ const d=document.createElement('div'); d.className='row'; const a=document.createElement('span'); a.textContent=r.name; const b=document.createElement('span'); b.className='pill '+(r.ok?'ok':'bad'); b.textContent=r.ok?('OK '+(r.detail||'')):('SORUN '+(r.detail||'')); d.appendChild(a); d.appendChild(b); box.appendChild(d); });
}
async function loadLastGood(){ const d=await api('/api/lastgood'); $('#lastGoodInfo').textContent = d.info ? ('Son çalışan sürüm kaydı: '+d.info.when+' ('+d.info.files+' dosya) — uygulama kod hatasıyla açılamazsa otomatik geri yüklenir.') : 'Henüz "son çalışan sürüm" kaydı yok (uygulama 30 sn sağlıklı çalışınca alınır).'; }
async function restartApp(){
  if(!confirm('Uygulama kapanıp yeniden açılacak (10-20 sn). Telefondan bağlıysan bağlantı kopar; yeni link için bilgisayardan Telefon > Telefonu Bağla yapılmalı. Devam?')) return;
  const r=await api('/api/maint/restart',{method:'POST'}); alert(r.message||r.error||'istek gönderildi');
}

/* ---- telefon: pin + lan ---- */
async function phoneExtras(s){
  $('#lanChk').checked = !!s.lan_setting;
  let t='';
  if(s.lan_active) t = 'AKTİF. Aynı Wi-Fi\'deki cihazlarda aç:<br>'+(s.lan_urls||[]).map(u=>'<b>'+u.label+'</b><br><code style="word-break:break-all">'+u.url+'</code>').join('<br><br>');
  else if(s.lan_setting) t = 'Ayar açık — uygulama yeniden başlayınca aktif olur.';
  else t = 'Kapalı.';
  $('#lanBox').innerHTML = t;
  const sec = await api('/api/security/status');
  $('#pinState').innerHTML = (sec.pin_set?'<span class="pill ok">PIN belirlenmiş</span>':'<span class="pill warn">PIN yok — hassas işlemler uzaktan kapalı</span>')+' '+(sec.local?'<span class="pill">yerel pencere</span>':(sec.unlocked?'<span class="pill ok">kilit açık</span>':'<span class="pill warn">uzak — kilitli</span>'));
}
async function setPin(){ const pin=$('#pinInput').value; const r=await api('/api/security/setpin',{method:'POST',headers:JH,body:JSON.stringify({pin})}); alert(r.ok?'PIN belirlendi.':(r.error||'HATA')); $('#pinInput').value=''; phoneRefresh(); }
async function clearPin(){ if(!confirm('PIN silinsin mi? (Uzaktan hassas işlemler kapanır)')) return; const r=await api('/api/security/clearpin',{method:'POST'}); alert(r.ok?'PIN silindi.':(r.error||'HATA')); phoneRefresh(); }
async function lockNow(){ await api('/api/security/lock',{method:'POST'}); phoneRefresh(); }
async function setLan(on){ const r=await api('/api/settings/lan',{method:'POST',headers:JH,body:JSON.stringify({enabled:on})}); if(r.error) alert(r.error); phoneRefresh(); }


/* ---- takip & kararlar ---- */
function tkEl(tag, txt, css){ const e=document.createElement(tag); if(txt!==undefined) e.textContent=txt; if(css) e.style.cssText=css; return e; }
const TK_VERDICT = {guclu:['GÜÇLÜ','ok'], orta:['ORTA',''], zayif:['ZAYIF','bad'], yeni:['YENİ','']};
async function tkLoad(){
  const d = await api('/api/tracker');
  $('#tkTs').textContent = d.tracker ? ('· veri: '+d.tracker.ts.replace('T',' ')+' ('+d.age_hours+' saat önce)') : '· veri yok — "Şimdi yenile"ye bas';
  // buyume makinesi
  const fb=$('#tkFunnel'); fb.innerHTML='';
  const fn=d.funnel;
  if(!fn){ fb.textContent='Analiz raporu yok - Analiz sekmesinden yenile.'; }
  else {
    fb.appendChild(tkEl('div','Huni (son 28 gün): '+fmt(fn.views)+' izlenme (önceki 28 gün: '+fmt(fn.prev_views)+')','color:#8b949e;font-size:12px;margin-bottom:6px'));
    fn.rows.forEach(r=>{
      const row=tkEl('div',undefined,'margin:8px 0');
      const head=tkEl('div',undefined,'display:flex;justify-content:space-between;font-size:13px');
      head.appendChild(tkEl('span',r.label+' — '+r.cur+' / 1000 izlenme  (önceki: '+r.prev+', toplam '+r.total+')'));
      head.appendChild(tkEl('span',r.target?('hedef '+r.target+'  ·  %'+r.pct):'','color:'+(r.pct>=100?'#3fb950':r.pct>=50?'#d29922':'#f85149')));
      row.appendChild(head);
      if(r.target){ const bar=tkEl('div',undefined,'height:8px;background:#21262d;border-radius:4px;overflow:hidden;margin-top:3px'); bar.appendChild(tkEl('div',undefined,'height:8px;width:'+Math.min(100,r.pct)+'%;background:'+(r.pct>=100?'#3fb950':r.pct>=50?'#d29922':'#f85149'))); row.appendChild(bar); }
      fb.appendChild(row);
    });
    if(fn.new){ fb.appendChild(tkEl('div','Yeni kurallarla üretilenler (26 Eylül+): '+fn.new.n+' video, '+fmt(fn.new.views)+' izlenme → abone '+fn.new.subs+' · yorum '+fn.new.comments+' · paylaşım '+fn.new.shares+' (/1000)','margin-top:8px;font-size:13px;color:#8b949e')); }
    else fb.appendChild(tkEl('div','Yeni kurallarla (sesli takip çağrısı, kapanış sorusu) üretilen video henüz yok — ilk video yarın 18:00.','margin-top:8px;font-size:13px;color:#8b949e'));
  }
  // kararlar
  const box=$('#tkDecisions'); box.innerHTML='';
  const dec=d.decisions||[];
  if(!dec.length) box.appendChild(tkEl('div','Açık karar yok — her şey yolunda görünüyor.','color:#3fb950'));
  dec.forEach(x=>{
    const c=tkEl('div',undefined,'border:1px solid #30363d;border-radius:8px;padding:10px;margin:8px 0;'+(x.status!=='open'?'opacity:.55':''));
    c.appendChild(tkEl('div',(x.level==='bad'?'🔴 ':x.level==='warn'?'🟠 ':'🔵 ')+x.title,'font-weight:600'));
    c.appendChild(tkEl('div','Neden: '+x.why,'font-size:13px;color:#8b949e;margin-top:3px'));
    c.appendChild(tkEl('div','Ne yapmalı: '+x.advice,'font-size:13px;margin-top:3px'));
    const b=tkEl('div',undefined,'margin-top:6px');
    if(x.tab){ const g=tkEl('button','Git'); g.className='act'; g.onclick=()=>gotoTab(x.tab); b.appendChild(g); }
    if(x.live){ const g=tkEl('button','🎙 Canlıya söyle'); g.className='act'; g.onclick=async()=>{ const r=await api('/api/live/cmd',{method:'POST',headers:JH,body:JSON.stringify(x.live)}); alert(r&&r.ok?'Canlı yayına gönderildi.':'Gönderilemedi: '+((r&&r.error)||'canlı yayın açık değil')); }; b.appendChild(g); }
    if(x.apply && x.status==='open'){
      const g=tkEl('button','✅ '+x.apply); g.className='act primary'; g.onclick=()=>tkApply(x,g); b.appendChild(g);
    }
    if(x.status==='open'){
      [['Yapıldı','done'],['Yoksay','dismissed']].forEach(([t,st])=>{ const g=tkEl('button',t); g.className='act'; g.onclick=async()=>{ await api('/api/tracker/decision',{method:'POST',headers:JH,body:JSON.stringify({id:x.id,status:st})}); tkLoad(); }; b.appendChild(g); });
    } else {
      b.appendChild(tkEl('span',(x.status==='done'?'✔ yapıldı ':'yoksayıldı ')+(x.ts||'').replace('T',' '),'font-size:12px;color:#8b949e;margin-right:8px'));
      const g=tkEl('button','Geri aç'); g.className='act'; g.onclick=async()=>{ await api('/api/tracker/decision',{method:'POST',headers:JH,body:JSON.stringify({id:x.id,status:'open'})}); tkLoad(); }; b.appendChild(g);
    }
    c.appendChild(b); box.appendChild(c);
  });
  // sesli karar
  const v=d.voice||{}; const vb=$('#tkVoice'); vb.innerHTML='';
  vb.appendChild(tkEl('div','Kapanış cümlesi: '+(v.cta||'-'),'font-weight:600'));
  vb.appendChild(tkEl('div','Konu ipucu: '+(v.topic_hint||'serbest (konsey seçer)'),'margin-top:4px'));
  vb.appendChild(tkEl('div','Kullanılacak ses: '+(v.tts||'-')+' · en çok '+(v.max_sentence_words||'-')+' kelimelik cümleler','margin-top:4px'));
  vb.appendChild(tkEl('div','Neden bu karar?','margin-top:8px;color:#8b949e;font-size:12px'));
  (v.reasons||[]).forEach(r=>vb.appendChild(tkEl('div','• '+r,'font-size:13px')));
  const vr=tkEl('div',undefined,'margin-top:8px');
  const b1=tkEl('button','🎙 Kapanış cümlesini canlıya söyle'); b1.className='act primary'; b1.onclick=async()=>{ const r=await api('/api/live/cmd',{method:'POST',headers:JH,body:JSON.stringify({action:'say',text:v.cta})}); alert(r&&r.ok?'Gönderildi.':'Gönderilemedi: '+((r&&r.error)||'canlı yayın açık değil')); };
  vr.appendChild(b1);
  if(v.topic_hint){ const b2=tkEl('button','Konu ipucunu canlı konu yap'); b2.className='act'; b2.onclick=async()=>{ const r=await api('/api/live/cmd',{method:'POST',headers:JH,body:JSON.stringify({action:'topic',text:v.topic_hint})}); alert(r&&r.ok?'Gönderildi.':'Gönderilemedi: '+((r&&r.error)||'canlı yayın açık değil')); }; vr.appendChild(b2); }
  vb.appendChild(vr);
  const rl=tkEl('div','Kurallar: '+(v.rules||[]).join('  |  '),'margin-top:8px;font-size:12px;color:#8b949e'); vb.appendChild(rl);
  // videolar
  const t=d.tracker; const vids=(t&&t.videos)||[];
  const vbx=$('#tkVideos'); vbx.innerHTML='';
  if(vids.length){
    const tb=document.createElement('table'); tb.className='tbl'; tb.style.tableLayout='auto';
    const hr=tb.insertRow(); ['Video','Yargı','İzlenme','Yorum','Paylaşım','Tutma','Hashtag\'ler','Neden?'].forEach(h=>{ const th=document.createElement('th'); th.textContent=h; hr.appendChild(th); });
    vids.slice().sort((a,b)=>b.views-a.views).forEach(x=>{
      const r=tb.insertRow(); const vd=TK_VERDICT[x.verdict]||['-',''];
      const cells=[x.title+' ('+x.published+')', null, fmt(x.views), x.comments, x.shares, '%'+x.retention, (x.hashtags||[]).join(' '), (x.why||[]).join(' ')];
      cells.forEach((c,i)=>{ const td=r.insertCell(); if(i===1){ const sp=tkEl('span',vd[0]); sp.className='pill '+vd[1]; td.appendChild(sp); } else { td.textContent=c; if(i===7) td.style.cssText='font-size:12px;color:#8b949e'; } });
    });
    vbx.appendChild(tb);
  } else vbx.textContent='Veri yok.';
  const stat=(sel,rows)=>{ const bx=$(sel); bx.innerHTML=''; if(!rows||!rows.length){ bx.textContent='Veri yok.'; return; }
    const tb=document.createElement('table'); tb.className='tbl'; tb.style.tableLayout='auto';
    const hr=tb.insertRow(); ['Ad','Kaç videoda (n)','Ort. izlenme','Ort. etkileşim','Ort. tutma'].forEach(h=>{ const th=document.createElement('th'); th.textContent=h; hr.appendChild(th); });
    rows.forEach(e=>{ const r=tb.insertRow(); [e.name,e.n,fmt(e.avg_views),e.avg_rate,'%'+e.avg_ret].forEach(c=>{ r.insertCell().textContent=c; }); });
    bx.appendChild(tb); };
  stat('#tkHash', t&&t.hashtag_stats); stat('#tkTags', t&&t.tag_stats);
  const gb=$('#tkGloss'); gb.innerHTML='';
  (d.glossary||[]).forEach(g=>{ const r=tkEl('div',undefined,'margin:8px 0'); r.appendChild(tkEl('b',g[0])); r.appendChild(tkEl('div',g[1],'font-size:13px')); r.appendChild(tkEl('div','Ne işe yarar: '+g[2],'font-size:12px;color:#8b949e')); gb.appendChild(r); });
}
async function tkApply(x,btn){
  btn.disabled=true; const old=btn.textContent; btn.textContent='hazırlanıyor...';
  const pv=await api('/api/tracker/preview',{method:'POST',headers:JH,body:JSON.stringify({id:x.id})});
  btn.disabled=false; btn.textContent=old;
  if(!confirm((pv.text||'Uygulanacak.')+'\n\nOnaylıyor musun?')) return;
  btn.disabled=true; btn.textContent='uygulanıyor...';
  const r=await api('/api/tracker/apply',{method:'POST',headers:JH,body:JSON.stringify({id:x.id,items:pv.items})});
  if(r.job){ (async function poll(){ const j=await api('/api/job/'+r.job); if(j.status==='running'){ setTimeout(poll,2000); return; }
      let m=j.out; try{ const o=JSON.parse(j.out); m=o.message||o.error||j.out; }catch(e){} alert(m); tkLoad(); })(); }
  else { alert(r.message||r.error||'tamam'); tkLoad(); }
}
async function atLoad(){
  const d=await api('/api/autotest/last'); const box=$('#atBox'); box.innerHTML='';
  if(!d.rows){ box.textContent='Henüz çalışmadı.'; return; }
  const bad=d.rows.filter(r=>!r.ok);
  const h=tkEl('div',(d.failed?'🔴 ':'🟢 ')+d.passed+'/'+d.total+' geçti — '+d.failed+' hata, '+d.warned+' uyarı  ('+d.ts.replace('T',' ')+')','font-weight:600;margin-bottom:6px'); box.appendChild(h);
  bad.forEach(r=>box.appendChild(tkEl('div',(r.level==='warn'?'🟠 ':'🔴 ')+'['+r.group+'] '+r.name+(r.detail?' — '+r.detail:''),'font-size:13px')));
  const det=document.createElement('details'); det.appendChild(tkEl('summary','Tüm kontroller','cursor:pointer;color:#8b949e;font-size:12px;margin-top:6px'));
  d.rows.forEach(r=>det.appendChild(tkEl('div',(r.ok?'✔ ':'✖ ')+'['+r.group+'] '+r.name,'font-size:12px;color:'+(r.ok?'#8b949e':'#f85149'))));
  box.appendChild(det);
}
async function atRun(){
  $('#atStatus').textContent='çalışıyor...';
  const r=await api('/api/autotest/run',{method:'POST'});
  (async function poll(){ const j=await api('/api/job/'+r.job); if(j.status==='running'){ setTimeout(poll,2000); return; } $('#atStatus').textContent=j.out||''; atLoad(); })();
}
async function tkRefresh(){
  $('#tkStatus').textContent='yenileniyor...';
  const r=await api('/api/tracker/refresh',{method:'POST'});
  (async function poll(){ const j=await api('/api/job/'+r.job); if(j.status==='running'){ setTimeout(poll,2000); return; } $('#tkStatus').textContent=j.out||''; tkLoad(); })();
}

/* ---- analiz sekmesi ---- */
const AN_CHIPS = {
  'Veri analizi': [['analytics_report.py','rapor (bu sekme)'],['analysis_config.py','esik/ayar tanimlari'],['engagement_signal.py','etkilesim sinyali'],['optimize_loop.py','erisim x tutma'],['analyze_channel.py','icerik modeli'],['analyze_video.py','video teshisi'],['reference_mine.py','referans kanallar'],['ledger.py','tahmin defteri'],['tracker.py','takip + karar kurallari + sesli karar']],
  'Hata yönetimi / uyarılar': [['providers.py','saglayici hata+yedek'],['health.py','uyarilar, kendini test'],['maintenance.py','bakim/onarim'],['render_audio.py','ses yedegi'],['aura_engine.py','gunluk uretim akisi'],['retitle_agent.py','baslik guncelleme']]
};
function chipsInto(box){
  box.innerHTML='';
  Object.entries(AN_CHIPS).forEach(([grp,items])=>{
    const t=document.createElement('div'); t.style.cssText='color:#8b949e;font-size:12px;margin-top:6px'; t.textContent=grp; box.appendChild(t);
    items.forEach(([f,d])=>{ const c=document.createElement('span'); c.className='chip'; c.textContent=f+' — '+d; c.onclick=()=>kodGo(f); box.appendChild(c); });
  });
  const c2=document.createElement('span'); c2.className='chip'; c2.textContent='_engine/analysis_config.json (ayar dosyasi)'; c2.title='JSON ayar dosyasi yalnizca panel formundan degisir'; c2.style.opacity='.6'; box.appendChild(c2);
}
function kodChips(){ chipsInto($('#kodChips')); }
async function kodGo(name){
  gotoTab('kod'); await sleepMs(300);
  $('#kodSearch').value=name; await kodTree();
  const sel=$('#kodFile'); for(let i=0;i<sel.options.length;i++){ if(sel.options[i].value===name){ sel.selectedIndex=i; break; } }
  await kodOpen();
}
const sleepMs = ms => new Promise(r=>setTimeout(r,ms));
function fmt(n){ return (n===undefined||n===null)?'-':Number(n).toLocaleString('tr-TR'); }
function delta(c,p){ if(!p) return ''; const d=(c-p)/p*100; return `<small class="${d>=0?'up':'down'}">${d>=0?'▲':'▼'} %${Math.abs(d).toFixed(0)} (önceki 28 gün: ${fmt(p)})</small>`; }
async function anLoad(){
  chipsInto($('#anChips'));
  const d = await api('/api/analytics');
  const r = d.report;
  if(!r){ $('#anKpis').textContent='Rapor henüz yok - "YouTube\'dan yenile" ye bas.'; anCfg(); return; }
  $('#anTs').textContent = '· rapor: '+r.ts.replace('T',' ')+' ('+d.age_hours+' saat önce)';
  const c=r.cur, p=r.prev;
  const kp=[['İzlenme',c.views,p.views],['Beğeni',c.likes,p.likes],['Yorum',c.comments,p.comments],['Paylaşım',c.shares,p.shares],['Yeni abone',c.subscribersGained,p.subscribersGained]];
  $('#anKpis').innerHTML = kp.map(k=>`<div class="kpi"><small>${k[0]} (28 gün)</small><b>${fmt(k[1])}</b>${delta(k[1],k[2])}</div>`).join('') +
    `<div class="kpi"><small>Ort. izlenme oranı</small><b>%${(c.averageViewPercentage||0).toFixed(1)}</b><small>${c.averageViewDuration||0} sn ortalama</small></div>` +
    `<div class="kpi"><small>Kanal toplamı</small><b>${fmt(r.channel.subs)} abone</b><small>${fmt(r.channel.views)} izlenme · ${r.public_videos} herkese açık video</small></div>`;
  // gunluk grafik
  const dl=r.daily||[]; const mx=Math.max(1,...dl.map(x=>x.views)); const W=560,H=120,bw=W/Math.max(1,dl.length);
  $('#anChart').innerHTML = `<svg viewBox="0 0 ${W} ${H+18}" style="width:100%;height:auto">` + dl.map((x,i)=>{ const h=Math.max(1,x.views/mx*H); return `<rect x="${(i*bw+1).toFixed(1)}" y="${(H-h).toFixed(1)}" width="${(bw-2).toFixed(1)}" height="${h.toFixed(1)}" fill="#1f6feb"><title>${x.day}: ${x.views} izlenme, ${x.subs} abone</title></rect>`; }).join('') + `<text x="0" y="${H+14}" fill="#8b949e" font-size="10">${dl.length?dl[0].day:''}</text><text x="${W}" y="${H+14}" fill="#8b949e" font-size="10" text-anchor="end">${dl.length?dl[dl.length-1].day:''} · en yüksek ${fmt(mx)}</text></svg>`;
  const tm=Math.max(1,...(r.traffic||[]).map(t=>t.views));
  $('#anTraffic').innerHTML=(r.traffic||[]).map(t=>`<div style="margin:6px 0"><div style="display:flex;justify-content:space-between"><span>${t.source}</span><span>${fmt(t.views)}</span></div><div class="bar" style="width:${(t.views/tm*100).toFixed(0)}%"></div></div>`).join('');
  const tbl=(rows,extra)=>'<table class="tbl"><tr><th>Video</th><th>İzlenme</th><th>Beğeni</th><th>Yorum</th><th>Paylaşım</th><th>Tutma</th><th>Oran</th></tr>'+rows.map(v=>`<tr><td></td><td>${fmt(v.views)}</td><td>${v.likes}</td><td>${v.comments}</td><td>${v.shares}</td><td>%${v.retention}</td><td>${v.rate}</td></tr>`).join('')+'</table>';
  [['#anTopViews',r.top_views],['#anTopEng',r.top_engagement],['#anBestRet',r.best_retention]].forEach(([sel,rows])=>{
    const box=$(sel); box.innerHTML=tbl(rows||[]); const trs=box.querySelectorAll('tr'); (rows||[]).forEach((v,i)=>{ trs[i+1].firstChild.textContent=v.title+'  ('+v.published+')'; });
    const w=box.querySelector('table'); w.style.tableLayout='auto';
  });
  anCfg();
}
async function anRefresh(){
  $('#anStatus').textContent='yenileniyor...';
  const r=await api('/api/analytics/refresh',{method:'POST'});
  (async function poll(){ const j=await api('/api/job/'+r.job); if(j.status==='running'){ setTimeout(poll,2000); return; } $('#anStatus').textContent=j.out||''; anLoad(); })();
}
async function anCfg(){
  const rows=await api('/api/analysis_config'); const box=$('#anCfg'); box.innerHTML='';
  (Array.isArray(rows)?rows:[]).forEach(x=>{
    const d=document.createElement('div'); d.style.margin='8px 0';
    const l=document.createElement('label'); l.textContent=x.label+'  (varsayılan: '+x.default+')'; d.appendChild(l);
    const i=document.createElement('input'); i.type=x.type==='str'?'text':'number'; i.id='cfg_'+x.key; i.value=x.value; if(x.type!=='str'){ i.min=x.min; i.max=x.max; i.step=x.type==='float'?'0.5':'1'; } d.appendChild(i);
    const h=document.createElement('div'); h.style.cssText='color:#8b949e;font-size:12px'; h.textContent=x.help; d.appendChild(h); box.appendChild(d);
  });
}
async function anSaveCfg(){
  const vals={}; document.querySelectorAll('#anCfg input').forEach(i=>{ vals[i.id.replace('cfg_','')]=i.value; });
  const r=await api('/api/analysis_config',{method:'POST',headers:JH,body:JSON.stringify({values:vals})});
  $('#anCfgStatus').style.color=r.ok?'#3fb950':'#f85149'; $('#anCfgStatus').textContent=r.ok?'Kaydedildi (bir sonraki analizde geçerli olur).':(r.errors||[r.error||'HATA']).join('; ');
}

attachMic($('#asstMic'), $('#asstText'));
attachMic($('#kodMic'), $('#kodInstr'));

bgLoad(); bgGuven(); bgAnalizPoll(); refreshStatus(); loadDays(); loadChat(); loadPredictions(); loadUretBugun(); loadPending(); loadAccount(); loadFreshness(); loadIssues(); loadInterventions(); loadAlerts(); setInterval(loadAlerts, 30000);
setInterval(refreshStatus, 5000);
setInterval(pollLive, 2000);
</script>
</body></html>"""


# =====================================================================
# HTTP handler
# =====================================================================
class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _json(self, obj, code=200, headers=None):
        if code >= 400 and not getattr(self, "_body_read", False):
            # reddedilen POST'un govdesini oku: okunmadan kapanirsa istemci baglanti-kesildi (RST) gorur
            self._body_read = True
            try:
                self.rfile.read(min(int(self.headers.get("Content-Length", 0) or 0), 1_000_000))
            except Exception:
                pass
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _sens(self):
        """Hassas islem izni: yerel = serbest; uzak = PIN gerekir (security.py)."""
        r = security.check_sensitive(self, PORT)
        if r is None:
            return True
        self._json({"error": r[1], "need": r[0]}, 403)
        return False

    def _local_only(self):
        """KOD DUZENLEME yalnizca bilgisayardaki pencereden (yerel). Tunel/LAN uzerinden
        HIC acilmaz: uzaktan kod calistirma yuzeyi olusturmamak icin bilincli karar."""
        if security.is_local(self, PORT):
            return True
        self._json({"error": "Kod duzenleme yalnizca bilgisayardaki uygulama penceresinden yapilir "
                             "(guvenlik: uzaktan/telefondan acilmaz).", "need": "local"}, 403)
        return False

    def _client(self):
        return self.headers.get("Cf-Connecting-Ip") or self.client_address[0]

    def _body(self):
        self._body_read = True
        n = int(self.headers.get("Content-Length", 0) or 0)
        try:
            return json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return {}

    def _cookie_key(self):
        for part in (self.headers.get("Cookie") or "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == "mc_key":
                return v
        return ""

    def _authed(self, q):
        cand = [self._cookie_key(), (q.get("key", [""])[0]), self.headers.get("X-MC-Key", "")]
        return any(c and secrets.compare_digest(c, TOKEN) for c in cand)

    def _deny(self):
        body = ("Yetkisiz. Uygulamayi masaustu kisayolundan ac ya da Telefon sekmesindeki "
                "linki kullan.").encode("utf-8")
        self.send_response(403)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if not self._authed(q):
            return self._deny()
        if u.path == "/":
            body = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            if q.get("key", [""])[0]:
                self.send_header("Set-Cookie", f"mc_key={TOKEN}; Path=/; HttpOnly; SameSite=Lax; Max-Age=31536000")
            self.end_headers()
            self.wfile.write(body)
        elif u.path == "/api/bugun/durum":
            self._json(bugun_durum_full())
        elif u.path == "/api/bugun/gundem":
            self._json(bugun.gundem_oku())
        elif u.path == "/api/bugun/analiz":
            self._json(analiz.son() or {"durum": "yok"})
        elif u.path == "/api/bugun/guven":
            self._json(analiz.guven_durumu())
        elif u.path == "/api/ogrenme":
            try:
                vids = (tracker.load() or {}).get("videos", [])
                self._json({"ok": bool(vids), "karne": ogrenme.karne(vids), "hashtag": ogrenme.hashtag_onerisi(vids), "n": len(vids)})
            except Exception as e:
                self._json({"ok": False, "error": f"{type(e).__name__}: {e}"})
        elif u.path == "/api/phone":
            self._json(phone_status())
        elif u.path == "/api/alerts":
            self._json(alerts_now())
        elif u.path == "/api/analytics":
            rep_ = analytics_report.load_report()
            self._json({"report": rep_, "age_hours": round((time.time() - os.path.getmtime(analytics_report.OUT)) / 3600, 1)
                        if rep_ else None})
        elif u.path == "/api/tracker":
            self._json({"tracker": tracker.load(), "age_hours": tracker.age_hours(), "decisions": tracker.decisions(),
                        "voice": tracker.voice_plan(), "glossary": tracker.GLOSSARY, "funnel": tracker.funnel()})
        elif u.path == "/api/autotest/last":
            self._json(autotest.last() or {})
        elif u.path == "/api/analysis_config":
            self._json(analysis_config.schema_for_ui())
        elif u.path == "/api/lastgood":
            self._json({"info": health.last_good_info()})
        elif u.path == "/api/security/status":
            self._json({"pin_set": security.pin_is_set(), "local": security.is_local(self, PORT),
                        "unlocked": security.check_sensitive(self, PORT) is None})
        elif u.path == "/api/assistant/actions":
            self._json(assistant.catalog())
        elif u.path == "/api/code/tree":
            if self._local_only():
                self._json(codeassist.tree(q.get("q", [""])[0]))
        elif u.path == "/api/code/read":
            if self._local_only():
                try:
                    self._json(codeassist.read_file(q.get("path", [""])[0]))
                except codeassist.CodeError as e:
                    self._json({"error": str(e)}, 400)
        elif u.path == "/api/code/backups":
            if self._local_only():
                try:
                    self._json(codeassist.list_backups(q.get("path", [""])[0]))
                except codeassist.CodeError as e:
                    self._json({"error": str(e)}, 400)
        elif u.path == "/api/selfcheck":
            self._json(maintenance.selfcheck())
        elif u.path == "/api/ports":
            self._json(maintenance.port_report())
        elif u.path == "/api/tasks":
            self._json(maintenance.scheduled_tasks())
        elif u.path == "/api/logs":
            self._json(maintenance.list_logs())
        elif u.path == "/api/logtail":
            self._json({"text": maintenance.tail_log(q.get("f", [""])[0], 200)})
        elif u.path == "/api/autostart":
            self._json({"enabled": maintenance.autostart_status()})
        elif u.path == "/api/manual":
            self._json({"text": manual_text()})
        elif u.path == "/api/status":
            self._json(status_summary())
        elif u.path == "/api/freshness":
            self._json(freshness_summary())
        elif u.path == "/api/known_issues":
            self._json(known_issues())
        elif u.path == "/api/interventions":
            rows = _read_json(os.path.join(ENGINE, "interventions.json"), [])
            self._json(list(reversed(rows))[:30])
        elif u.path == "/api/diagnose":
            self._json(diagnose(q.get("id", [""])[0]))
        elif u.path == "/api/days":
            self._json(list_days())
        elif u.path == "/api/day":
            self._json(day_detail(q.get("date", [""])[0]) or {})
        elif u.path == "/api/council_chat":
            self._json(_read_json(os.path.join(ENGINE, "council_chat_history.json"), []))
        elif u.path == "/api/predictions":
            import ledger
            self._json({"rows": ledger.list_rows(), "scorecard": ledger.scorecard()})
        elif u.path == "/api/pending":
            self._json(_read_json(os.path.join(ENGINE, "pending_approval.json"), []))
        elif u.path == "/api/account":
            self._json(account_status())
        elif u.path == "/api/voice/log":
            self._json({"lines": list(_VOICE["log"])[-200:]})
        elif u.path == "/api/live/log":
            self._json({"lines": list(_LIVE["log"])[-200:]})
        elif u.path == "/api/live/state":
            self._json(live_state())
        elif u.path.startswith("/api/job/"):
            jid = u.path.rsplit("/", 1)[-1]
            j = _JOBS.get(jid)
            self._json(j if j else {"error": "is bulunamadi"}, 200 if j else 404)
        else:
            self.send_response(404); self.end_headers()

    def do_POST(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        if not self._authed(q):
            return self._deny()

        if u.path == "/api/bugun/gundem":
            return self._json({"job": _run_py_job(bugun.gundem_yenile)})
        if u.path == "/api/bugun/analiz":
            return self._json(bugun_analiz_baslat(str(self._body().get("sutun") or "")[:20]))
        if u.path == "/api/bugun/sutun_onay":
            return self._json(analiz.sutun_onayla(str(self._body().get("sutun", ""))[:20]))
        if u.path == "/api/bugun/onay":
            return self._json(analiz.onayla(str(self._body().get("secim", ""))[:8]))
        if u.path == "/api/bugun/red":
            return self._json(analiz.reddet())
        if u.path == "/api/bugun/guven/retention":
            return self._json(analiz.retention_kaydet(self._body().get("deger")))
        if u.path == "/api/bugun/paylas":
            b = self._body()
            pk = _read_json(bugun._son_paket(True), {}) if bugun._son_paket(True) else {}
            vids = bugun.bugun_durum()["videolar"]
            return self._json(bugun.paylasim_taslak(str(b.get("platform", "")), pk, vids[-1]["video_id"] if vids else ""))
        if u.path == "/api/bugun/paylastim":
            b = self._body()
            vids = bugun.bugun_durum()["videolar"]
            return self._json(bugun.paylasim_kaydet(str(b.get("platform", ""))[:20], vids[-1]["video_id"] if vids else ""))
        if u.path == "/api/bugun/kaynak":
            b = self._body()
            return self._json(bugun.kaynak_analiz(str(b.get("url", ""))[:600], str(b.get("claim_key") or "state-of-the-art")[:80]))
        if u.path == "/api/bugun/paket":
            b = self._body()
            sec = [x for x in (b.get("secim") or []) if isinstance(x, int)][:12]
            facts = [str(x)[:200] for x in (b.get("facts") or [])][:8]
            return self._json(bugun.kaynak_paketle(sec, facts))
        if u.path in ("/api/bugun/plan", "/api/bugun/rapor"):
            b = self._body()
            return self._json(bugun_job(u.path.rsplit("/", 1)[-1], str(b.get("receipt") or ""), str(b.get("sutun") or "receipt")))
        if u.path == "/api/bugun/uret":
            if not self._sens():
                return
            b = self._body()
            return self._json(bugun_job("uret", str(b.get("receipt") or ""), str(b.get("sutun") or "receipt")))
        if u.path == "/api/bugun/yayinla":
            if not self._sens():
                return
            b = self._body()
            return self._json(bugun_yayinla(str(b.get("video_id") or ""), str(b.get("onay") or ""), b.get("isaretli")))
        if u.path == "/api/phone/start":
            return self._json(tunnel_start())
        if u.path == "/api/phone/stop":
            return self._json(tunnel_stop())
        if u.path == "/api/maint/orphans":
            if live_alive():
                return self._json({"ok": False, "error": "Canli yayin acikken yapilmaz - once yayini durdur."})
            return self._json({"ok": True, "killed": maintenance.orphan_cleanup()})
        if u.path == "/api/maint/killport":
            if not self._sens():
                return
            return self._json(maintenance.kill_port_owner(int(self._body().get("port", 0) or 0)))
        if u.path == "/api/maint/restart":
            if not self._sens():
                return
            return self._json(restart_app())
        if u.path == "/api/tracker/decision":
            b = self._body()
            return self._json(tracker.set_status(str(b.get("id", ""))[:60], b.get("status", "")))
        if u.path == "/api/tracker/preview":
            b = self._body()
            return self._json(_run_sync(tracker_actions.preview, str(b.get("id", ""))))
        if u.path == "/api/tracker/apply":
            if not self._sens():
                return
            b = self._body()
            did = str(b.get("id", ""))
            return self._json({"job": _run_py_job(lambda: json.dumps(
                tracker_actions.apply(did, b.get("items")), ensure_ascii=False))})
        if u.path == "/api/autotest/run":
            def _at():
                r = autotest.run(f"http://127.0.0.1:{PORT}")
                return f"{r['passed']}/{r['total']} gecti, {r['failed']} hata, {r['warned']} uyari"
            return self._json({"job": _run_py_job(_at)})
        if u.path == "/api/tracker/refresh":
            def _tk():
                r = tracker.refresh()
                return f"yenilendi: {len(r['videos'])} video, {len(r['hashtag_stats'])} hashtag"
            return self._json({"job": _run_py_job(_tk)})
        if u.path == "/api/analytics/refresh":
            jid = uuid.uuid4().hex[:10]
            _JOBS[jid] = {"status": "running", "out": ""}

            def _go_an(jid=jid):
                try:
                    r = analytics_report.build_report()
                    _JOBS[jid]["out"] = "yenilendi: " + str(r["cur"].get("views")) + " izlenme (son 28 gun)"
                except Exception as e:
                    _JOBS[jid]["out"] = "[HATA] " + health.friendly_error(e)
                _JOBS[jid]["status"] = "done"

            threading.Thread(target=_go_an, daemon=True).start()
            return self._json({"job": jid})
        if u.path == "/api/analysis_config":
            if not self._sens():
                return
            return self._json(analysis_config.save(self._body().get("values") or {}))
        if u.path == "/api/selftest/run":
            return self._json({"job": _selftest_job()})
        if u.path == "/api/alerts/ack":
            return self._json(health.ack_alert(str(self._body().get("id", ""))[:120]))
        if u.path == "/api/security/unlock":
            r = security.verify_pin(self._body().get("pin", ""), self._client())
            if not r.get("ok"):
                return self._json({"ok": False, "error": r["error"]}, 403)
            return self._json({"ok": True}, headers={"Set-Cookie": "mc_unlock=" + r["token"] + "; Path=/; HttpOnly; SameSite=Lax; Max-Age=" + str(security.SESSION_TTL)})
        if u.path == "/api/security/lock":
            security.drop_session(security.cookie_value(self, "mc_unlock"))
            return self._json({"ok": True}, headers={"Set-Cookie": "mc_unlock=; Path=/; Max-Age=0"})
        if u.path in ("/api/security/setpin", "/api/security/clearpin"):
            if not security.is_local(self, PORT):
                return self._json({"error": "PIN yalnizca bilgisayardaki uygulamadan belirlenir/silinir."}, 403)
            if u.path.endswith("clearpin"):
                return self._json(security.clear_pin())
            return self._json(security.set_pin(self._body().get("pin", "")))
        if u.path == "/api/settings/lan":
            if not self._sens():
                return
            set_setting("lan", bool(self._body().get("enabled")))
            return self._json({"ok": True, "restart_needed": True})
        if u.path == "/api/assistant/plan":
            text = (self._body().get("text") or "").strip()
            if not text:
                return self._json({"error": "bos"}, 400)
            return self._json({"job": _assistant_plan_job(text)})
        if u.path == "/api/assistant/exec":
            b = self._body()
            name = b.get("action")
            a = assistant.ACTIONS.get(name)
            if not a:
                return self._json({"ok": False, "error": "bilinmeyen islem"}, 400)
            if a["sensitive"] and not self._sens():
                return
            return self._json(assistant.execute(name, b.get("params")))
        if u.path == "/api/code/write":
            if not self._local_only():
                return
            b = self._body()
            try:
                return self._json(codeassist.write_file(b.get("path", ""), b.get("content", ""), b.get("hash")))
            except codeassist.CodeError as e:
                return self._json({"ok": False, "error": str(e)}, 400)
        if u.path == "/api/code/restore":
            if not self._local_only():
                return
            b = self._body()
            try:
                return self._json(codeassist.restore_backup(b.get("path", ""), b.get("name", "")))
            except codeassist.CodeError as e:
                return self._json({"ok": False, "error": str(e)}, 400)
        if u.path == "/api/code/apply":
            if not self._local_only():
                return
            try:
                return self._json(codeassist.apply_proposal(self._body().get("pid", "")))
            except codeassist.CodeError as e:
                return self._json({"ok": False, "error": str(e)}, 400)
        if u.path == "/api/code/propose":
            if not self._local_only():
                return
            b = self._body()
            jid = uuid.uuid4().hex[:10]
            _JOBS[jid] = {"status": "running", "out": ""}

            def _go_prop(jid=jid, b=b):
                try:
                    _JOBS[jid]["result"] = codeassist.propose(b.get("path", ""), b.get("instruction", ""),
                                                             b.get("provider") or "anthropic", b.get("mode") or "edit")
                except codeassist.CodeError as e:
                    _JOBS[jid]["out"] = "[HATA] " + str(e)
                except Exception as e:
                    _JOBS[jid]["out"] = "[HATA] " + health.friendly_error(e)
                _JOBS[jid]["status"] = "done"

            threading.Thread(target=_go_prop, daemon=True).start()
            return self._json({"job": jid})
        if u.path == "/api/maint/shortcuts":
            if not self._sens():
                return
            return self._json(maintenance.install_shortcuts())
        if u.path == "/api/maint/daily":
            if not self._sens():  # 27 Eyl 2026: gercek public video uretebilir - once PIN acigi kapatildi
                return
            return self._json(maintenance.run_daily_now(self._body().get("kind", "")))
        if u.path == "/api/maint/backup":
            return self._json({"job": _run_py_job(maintenance.make_backup)})
        if u.path == "/api/autostart":
            if not self._sens():
                return
            return self._json(maintenance.autostart_set(bool(self._body().get("enabled"))))
        if u.path == "/api/help/ask":
            b = self._body()
            question = (b.get("question") or "").strip()
            if not question and not b.get("image_base64"):
                return self._json({"error": "soru bos"}, 400)
            question = question or "Ekteki ekran goruntusundeki sorunu coz."
            jid = uuid.uuid4().hex[:10]
            _JOBS[jid] = {"status": "running", "out": ""}

            def _go_help(jid=jid, question=question, im=b.get("image_base64"), mime=b.get("image_mime")):
                try:
                    help_ask(jid, question, im, mime)
                except Exception as e:
                    _JOBS[jid]["out"] = "[HATA] " + health.friendly_error(e)
                _JOBS[jid]["status"] = "done"

            threading.Thread(target=_go_help, daemon=True).start()
            return self._json({"job": jid})

        if u.path == "/api/run":
            action = q.get("action", [""])[0]
            confirm = q.get("confirm", [""])[0] == "EVET"
            if action in _RISKY:
                if not confirm:
                    return self._json({"error": "confirm=EVET gerekli"}, 400)
                return self._json({"job": _run_job(_RISKY[action])})
            if action in _SAFE:
                return self._json({"job": _run_job(_SAFE[action])})
            return self._json({"error": f"bilinmeyen islem: {action}"}, 400)

        if u.path == "/api/voice/start":
            return self._json(start_voice())
        if u.path == "/api/voice/stop":
            return self._json(stop_voice())

        if u.path == "/api/live/start":
            b = self._body()
            return self._json(start_show(agenda=b.get("agenda", ""), auto_agenda=b.get("auto_agenda", False),
                                         public=b.get("public", True), test=b.get("test", False),
                                         duration=b.get("duration", 2400), title=b.get("title", "")))
        if u.path == "/api/live/stop":
            return self._json(stop_show())
        if u.path == "/api/live/cmd":
            b = self._body()
            return self._json(live_cmd(b.get("action", ""), b.get("who", ""), b.get("text", "")))

        if u.path == "/api/predictions/resolve":
            b = self._body()
            import ledger
            try:
                ledger.resolve_manual(b.get("id"), b.get("status"), b.get("note", ""))
                return self._json({"ok": True})
            except Exception as e:
                return self._json({"ok": False, "error": str(e)}, 400)

        if u.path == "/api/pending/approve":
            if not self._sens():  # 27 Eyl 2026: gercek public yayin - PIN acigi kapatildi
                return
            b = self._body()
            from publish_youtube import publish_video
            return self._json({"job": _run_py_job(publish_video, b.get("video_id"))})
        if u.path == "/api/pending/reject":
            b = self._body()
            pending_reject(b.get("video_id"))
            return self._json({"ok": True})

        if u.path == "/api/ask":
            b = self._body()
            question = (b.get("question") or "").strip()
            image_b64 = b.get("image_base64")
            image_mime = b.get("image_mime")
            if not question and not image_b64:
                return self._json({"error": "soru bos"}, 400)
            if not question:
                question = "Ekteki ekran görüntüsünü değerlendirin."
            jid = uuid.uuid4().hex[:10]
            _JOBS[jid] = {"status": "running", "out": ""}

            def _go(jid=jid, question=question, image_b64=image_b64, image_mime=image_mime):
                try:
                    ask_council(jid, question, image_b64, image_mime)
                except Exception as e:
                    _JOBS[jid]["out"] = "[HATA] " + health.friendly_error(e)
                _JOBS[jid]["status"] = "done"

            threading.Thread(target=_go, daemon=True).start()
            return self._json({"job": jid})

        if u.path == "/api/account/reconnect":
            jid = uuid.uuid4().hex[:10]
            _JOBS[jid] = {"status": "running", "out": ""}
            threading.Thread(target=reconnect_youtube, args=(jid,), daemon=True).start()
            return self._json({"job": jid})

        self.send_response(404); self.end_headers()


# =====================================================================
# ayarlar (LAN erisimi), yeniden baslatma, uyarilar, asistan eylemleri
# =====================================================================
_SETTINGS_PATH = os.path.join(ENGINE, "settings.json")


def settings():
    d = _read_json(_SETTINGS_PATH, {})
    return d if isinstance(d, dict) else {}


def set_setting(key, value):
    d = settings()
    d[key] = value
    os.makedirs(ENGINE, exist_ok=True)
    json.dump(d, open(_SETTINGS_PATH, "w", encoding="utf-8"), indent=1)


def lan_ips():
    import socket
    ips = set()
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            if not ip.startswith("127."):
                ips.add(ip)
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    return sorted(ips)


def restart_app():
    """Uygulamayi kapatip mission_control.bat ile yeniden acar (kod duzenlemesinden
    sonra gerekli). ping = konsolsuz ortamda calisan bekleme (timeout calismaz)."""
    bat = os.path.join(HERE, "mission_control.bat")

    def _go():
        time.sleep(1.5)
        shutdown_children()
        subprocess.Popen(f'ping -n 5 127.0.0.1 >nul & start "" "{bat}"', shell=True, cwd=HERE,
                         creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.5)
        os._exit(0)

    threading.Thread(target=_go, daemon=True).start()
    return {"ok": True, "message": "Uygulama yeniden basliyor (10-20 sn). Telefondan bagliysan baglanti kopar."}


_ALERT_CACHE = {"ts": 0, "tasks": []}


def alerts_now():
    if time.time() - _ALERT_CACHE["ts"] > 90:
        try:
            _ALERT_CACHE["tasks"] = maintenance.scheduled_tasks()
        except Exception:
            pass
        _ALERT_CACHE["ts"] = time.time()
    return health.alerts(_ALERT_CACHE["tasks"])


def _start_council_job(question):
    jid = uuid.uuid4().hex[:10]
    _JOBS[jid] = {"status": "running", "out": ""}

    def _go():
        try:
            ask_council(jid, question)
        except Exception as e:
            _JOBS[jid]["out"] = "[HATA] " + health.friendly_error(e)
        _JOBS[jid]["status"] = "done"

    threading.Thread(target=_go, daemon=True).start()
    return jid


def _selftest_job():
    jid = uuid.uuid4().hex[:10]
    _JOBS[jid] = {"status": "running", "out": ""}

    def _go():
        try:
            rows = health.selftest(f"http://127.0.0.1:{PORT}", TOKEN)
            _JOBS[jid]["rows"] = rows
            bad = [r for r in rows if not r["ok"]]
            _JOBS[jid]["out"] = "HER SEY TAMAM" if not bad else f"{len(bad)} SORUN: " + "; ".join(
                f"{r['name']} ({r['detail']})" for r in bad[:4])
        except Exception as e:
            _JOBS[jid]["out"] = "[HATA] " + health.friendly_error(e)
        _JOBS[jid]["status"] = "done"

    threading.Thread(target=_go, daemon=True).start()
    return jid


def _assistant_plan_job(text):
    jid = uuid.uuid4().hex[:10]
    _JOBS[jid] = {"status": "running", "out": ""}

    def _go():
        try:
            from providers import call_gemini
            state = {"durum": status_summary(), "uyarilar": [a["text"] for a in alerts_now()][:6],
                     "onay_bekleyen": len(_read_json(os.path.join(ENGINE, "pending_approval.json"), []))}
            _JOBS[jid]["plan"] = assistant.plan(call_gemini, text, state)
        except Exception as e:
            _JOBS[jid]["out"] = "[HATA] " + health.friendly_error(e)
        _JOBS[jid]["status"] = "done"

    threading.Thread(target=_go, daemon=True).start()
    return jid


def _register_actions():
    R = assistant.register

    def durum(p):
        s = status_summary()
        return {"message": f"Ses sunucusu: {'HAZIR' if s['voice_up'] else 'kapali'} | Canli yayin: "
                           f"{'ACIK' if s['live_running'] else 'kapali'} | Bugunun konusu: {s['today_topic'] or '(yok)'} | "
                           f"YouTube: {s['youtube']}"}

    R("durum", "Sistemin genel durumunu ozetler (ses sunucusu, canli yayin, bugunun konusu, YouTube).", "safe", {}, durum)
    R("uyarilar", "Aktif uyarilari listeler (basarisiz uretim, gorev hatasi vb.).", "safe", {},
      lambda p: {"message": "\n".join(f"[{a['level']}] {a['text']}" for a in alerts_now()) or "Uyari yok."})
    R("onay_listesi", "Onay bekleyen (private yuklenmis, hassas) videolari listeler.", "safe", {},
      lambda p: {"message": "\n".join(f"{r['video_id']} - {r['title']} ({r.get('reason','')[:100]})"
                                      for r in _read_json(os.path.join(ENGINE, "pending_approval.json"), [])) or "Bekleyen yok."})

    def tahmin(p):
        import ledger
        return {"message": str(ledger.scorecard())}

    R("tahmin_ozeti", "Tahmin defteri skor kartini verir.", "safe", {}, tahmin)
    R("telefon_durumu", "Telefon/tablet baglantisinin acik olup olmadigini ve linkini gosterir.", "safe", {},
      lambda p: {"message": (phone_status().get("link") or "Telefon baglantisi kapali.")})
    R("portlar", "Hangi portlari hangi programin tuttugunu listeler.", "safe", {},
      lambda p: {"message": "\n".join(f":{r['port']} {'AÇIK pid '+str(r['pid']) if r['pid'] else 'bos'} - {r['label'][:60]}"
                                      for r in maintenance.port_report())})

    def gorevler(p):
        rows = maintenance.scheduled_tasks()
        return {"message": "\n".join(f"{r['name']}: {r['result_text']} (son {r['last']}, sonraki {r['next']})" for r in rows) or "Gorev yok."}

    R("gorevler", "Zamanlanmis gunluk uretim gorevlerinin son durumunu verir.", "safe", {}, gorevler)

    def sistem(p):
        bad = [r for r in maintenance.selfcheck() if not r["ok"] and not r["optional"]]
        return {"message": "Eksik yok." if not bad else "\n".join(f"EKSIK: {r['name']} - {r['fix']}" for r in bad)}

    R("sistem_kontrolu", "Eksik program/anahtar var mi kontrol eder.", "safe", {}, sistem)
    R("konsey_sor", "5 yapay zeka konseyine bir soru sorar (Turkce tartisir, Aura karar verir).", "safe",
      {"question": "str"}, lambda p: {"job": _start_council_job(p.get("question") or "Bugun ne yapmaliyiz?"), "job_kind": "council",
                                       "message": "Konsey tartisiyor..."})
    R("kendini_test", "Uygulamanin butun uclarini ve kodunu test eder (kod duzenledikten sonra).", "safe", {},
      lambda p: {"job": _selftest_job(), "message": "Test basladi..."})
    R("yedek_al", "Projenin yedegini alir (zip).", "safe", {},
      lambda p: {"job": _run_py_job(maintenance.make_backup), "message": "Yedekleniyor..."})

    def ogrenme(p):
        w = p.get("which") or "engagement"
        if w not in ("optimize", "reference", "engagement"):
            return {"ok": False, "error": "which: optimize | reference | engagement"}
        return {"job": _run_job(_SAFE[w]), "message": f"{w} yenileniyor..."}

    R("ogrenme_yenile", "Ogrenme raporunu yeniler. which = optimize | reference | engagement.", "safe", {"which": "str"}, ogrenme)
    R("baslik_onizle", "Baslik onerilerini (degistirmeden) gosterir.", "safe", {},
      lambda p: {"job": _run_job(_SAFE["retitle_preview"]), "message": "Baslik onerileri hazirlaniyor..."})

    def analiz_ozeti(p):
        r = analytics_report.load_report()
        if not r:
            return {"message": "Analiz raporu henuz yok - analiz_yenile calistir."}
        c, pv = r["cur"], r["prev"]
        top = r["top_views"][0] if r["top_views"] else {}
        return {"message": f"Son 28 gun: {c.get('views')} izlenme (onceki 28 gun {pv.get('views')}), {c.get('likes')} begeni, "
                           f"{c.get('comments')} yorum, {c.get('subscribersGained')} yeni abone; abone toplami {r['channel']['subs']}. "
                           f"En cok izlenen: {top.get('title','-')} ({top.get('views','-')}). Rapor: {r['ts']}"}

    R("analiz_ozeti", "Kanalin son analiz raporunun ozetini verir (izlenme, begeni, yorum, abone, en iyi video).", "safe", {}, analiz_ozeti)
    R("analiz_yenile", "Kanal analiz raporunu YouTube'dan yeniden ceker (30-60 sn).", "safe", {},
      lambda p: {"job": _run_py_job(lambda: analytics_report.build_report() and "Analiz raporu yenilendi"), "message": "Analiz yenileniyor..."})
    # ---- onay gerektirenler ----
    R("telefon_bagla", "Telefon/tablet icin gizli internet baglantisi acar (link uretir).", "confirm", {},
      lambda p: {**tunnel_start(), "message": "Tunel aciliyor - Telefon sekmesinden linki al."})
    R("telefon_kapat", "Telefon/tablet baglantisini kapatir.", "safe", {}, lambda p: {**tunnel_stop(), "message": "Kapatildi."})
    R("ses_baslat", "Sign Council ses sunucusunu baslatir (baska ses sunucularini kapatir).", "confirm", {},
      lambda p: {**start_voice(), "message": "Ses sunucusu basliyor (40-90 sn)."})
    R("ses_durdur", "Ses sunucusunu durdurur.", "confirm", {}, lambda p: {**stop_voice(), "message": "Durduruldu."})
    R("yayin_baslat", "Canli yayini baslatir. test=true sadece baglanti testi; public=true herkese acik; agenda bos = Aura secer.",
      "confirm", {"test": "bool", "public": "bool", "agenda": "str"},
      lambda p: {**start_show(agenda=p.get("agenda", ""), auto_agenda=not (p.get("agenda") or "").strip(),
                              public=p.get("public", False), test=p.get("test", False)), "message": "Yayin baslatiliyor."})
    R("yayin_durdur", "Canli yayini temiz sekilde durdurur.", "confirm", {}, lambda p: {**stop_show(), "message": "Durdurma istegi gonderildi."})
    R("onayla", "Onay bekleyen bir videoyu HERKESE ACIK yayinlar. video_id gerekir.", "confirm", {"video_id": "str"},
      lambda p: _approve(p))
    R("reddet", "Onay kuyrugundaki videoyu kuyruktan cikarir (video YouTube'da private kalir).", "confirm", {"video_id": "str"},
      lambda p: (pending_reject(p.get("video_id")), {"message": "Kuyruktan cikarildi."})[1])
    R("gunluk_uretim", "Gunluk uretimi elle baslatir (HERKESE ACIK Short cikarabilir). kind = morning | evening.",
      "confirm", {"kind": "str"}, lambda p: {**maintenance.run_daily_now(p.get("kind") or "morning"), "message": "Uretim baslatildi - loglardan izle."},
      sensitive=True)
    R("oksuz_temizle", "Yayindan kalan oksuz chrome/node/ffmpeg surecleri kapatir.", "confirm", {},
      lambda p: ({"ok": False, "error": "Canli yayin acikken yapilmaz"} if live_alive() else {"killed": maintenance.orphan_cleanup(), "message": "Temizlendi."}))
    R("baslik_uygula", "Baslik onerilerini YouTube'a UYGULAR (yedek alir). desc=true aciklamayi da gunceller.", "confirm",
      {"desc": "bool"}, lambda p: {"job": _run_job(_RISKY["retitle_apply_desc" if p.get("desc") else "retitle_apply"]),
                                   "message": "Basliklar guncelleniyor..."})
    R("playlist_uygula", "Playlist siniflandirmasini YouTube'a UYGULAR.", "confirm", {},
      lambda p: {"job": _run_job(_RISKY["backfill_apply"]), "message": "Playlistler guncelleniyor..."})
    # ---- PIN gerektirenler (uzaktan) ----
    R("uygulamayi_yeniden_baslat", "Uygulamayi kapatip yeniden acar.", "confirm", {}, lambda p: restart_app(), sensitive=True)
    R("port_kapat", "Bir portun sahibi programi kapatir (8123/8124/8790/8791/8796).", "confirm", {"port": "int"},
      lambda p: maintenance.kill_port_owner(p.get("port", 0)), sensitive=True)
    R("otomatik_baslat", "Windows acilisinda uygulamanin otomatik baslamasini ac/kapat. enabled=true|false.", "confirm",
      {"enabled": "bool"}, lambda p: maintenance.autostart_set(p.get("enabled", False)), sensitive=True)


def _approve(p):
    from publish_youtube import publish_video
    vid = (p.get("video_id") or "").strip()
    if not vid:
        return {"ok": False, "error": "video_id gerekli"}
    return {"job": _run_py_job(publish_video, vid), "message": f"{vid} yayinlaniyor..."}


def local_url():
    return f"http://127.0.0.1:{PORT}/?key={TOKEN}"


def server_already_running():
    """Baska bir Mission Control ayni portta zaten calisiyor mu? (ayni anahtarla sorgular)"""
    try:
        req = urllib.request.Request(f"http://127.0.0.1:{PORT}/api/status", headers={"X-MC-Key": TOKEN})
        with urllib.request.urlopen(req, timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def _snapshot_when_healthy():
    """Uygulama 30 sn saglikli calistiktan sonra kodun 'son calisan surum'
    kopyasini alir (kod bozulursa mission_control.bat bunu geri yukler)."""
    time.sleep(30)
    if server_already_running():
        try:
            health.snapshot_last_good()
        except Exception as e:
            print(f"[snapshot hatasi] {e}")


class _QuietServer(ThreadingHTTPServer):
    """Pencere/tarayici istegi yarida kesince (yenileme, sekme degisimi) olusan zararsiz
    baglanti-koptu hatalarini konsola uzun traceback olarak basmaz; gercek hatalar yine gorunur.

    2 Ekim 2026 bulgusu: HTTPServer'in varsayilani allow_reuse_address=True - Windows'ta bu,
    SO_REUSEADDR'in Linux'taki (sadece TIME_WAIT) davranisindan FARKLI calisiyor ve zaten
    dinleyen bir porta IKINCI bir surecin de SESSIZCE baglanip dinlemesine izin veriyor.
    Boylece iki mission_control.py ayni anda 8800'u dinleyip istekleri rastgele bolusturuyordu
    (biri eski kodu calistiriyor olabilir - tutarsiz/eski cevaplar). server_already_running()
    kontrolu buna karsi birincil savunma ama yarisma durumuna karsi IKINCI katman: bu bayrak
    kapaliyken OS, port doluyken ikinci bind'i HATAYLA reddeder (sessiz degil, gorunur crash)."""
    daemon_threads = True
    allow_reuse_address = False

    def handle_error(self, request, client_address):
        if isinstance(sys.exc_info()[1], (ConnectionError, TimeoutError)):
            return
        super().handle_error(request, client_address)


def main():
    host = "0.0.0.0" if settings().get("lan") else "127.0.0.1"
    try:
        srv = _QuietServer((host, PORT), Handler)
    except OSError as e:
        print(f"[!] Port {PORT} zaten baska bir Mission Control tarafindan kullaniliyor - bu kopya acilmiyor ({e}).")
        return
    _BOUND_HOST["host"] = host
    print(f"Mission Control -> {local_url()}" + ("   (LAN erisimi ACIK)" if host == "0.0.0.0" else ""))
    threading.Thread(target=_snapshot_when_healthy, daemon=True).start()
    threading.Thread(target=tracker.auto_loop, daemon=True).start()
    threading.Thread(target=_autotest_loop, daemon=True).start()
    srv.serve_forever()


_register_actions()

if __name__ == "__main__":
    main()
