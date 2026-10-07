"""
DERIN TEST OTOMASYONU - "Kendini test"in (health.selftest: sozdizimi + GET uclari) ustune DAVRANIS
testleri. Calisan panele baglanir; YouTube'a YAZMAZ, yapay zekaya SORMAZ (ucretsiz, ~20 sn).

Gruplar:
  guvenlik   : anahtarsiz/uzaktan/proxy'li istekler reddediliyor mu, kod duzenleme yerelde mi
  kod        : yaz / bozuk sozdizimi reddi / bayat hash / yedek / geri alma / korumali yollar
  mantik     : takip kararlari, sesli karar kurallari, yargi, ayar dogrulama (sahte veriyle)
  asistan    : bilinmeyen islem reddi, eylem katalogu tutarliligi
  veri       : rapor/takip verisi taze mi, YouTube yetkisi, uretim kurallari dosyasi
  altyapi    : zamanlanmis gorevler, son-calisan kopya, paketler, disk, ses sunucusu
  uretim     : gunluk uretim hatti uctan uca (koruyucu/yeniden deneme, saglayici yedegi, canli API'ler,
               analiz raporu -> prompt baglantisi, son yuklemeler, strateji deneyi hedefleri)

Sonuc: _engine/autotest_last.json.  Kullanim:  python autotest.py [--url http://127.0.0.1:8800]
Panelde: Bakim > "Derin test". Her gun kendi kendine de calisir (mission_control arka plan dongusu).
Yeni test eklemek icin ilgili grup fonksiyonuna bir  add(grup, ad, kosul, ayrinti)  satiri koy.
"""
import datetime
import http.client
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.join(HERE, "_engine")
OUT = os.path.join(ENGINE, "autotest_last.json")
sys.path.insert(0, HERE)


class _Ctx:
    def __init__(self, base, token):
        u = urllib.parse.urlparse(base)
        self.host, self.port, self.token = u.hostname, u.port or 80, token
        self.rows = []

    def add(self, group, name, ok, detail="", warn=False):
        self.rows.append({"group": group, "name": name, "ok": bool(ok), "detail": str(detail)[:200],
                          "level": "warn" if (warn and not ok) else ("ok" if ok else "fail")})

    def call(self, path, body=None, headers=None, key=True, timeout=30):
        h = {"Content-Type": "application/json"}
        if key:
            h["X-MC-Key"] = self.token
        h.update(headers or {})
        c = http.client.HTTPConnection(self.host, self.port, timeout=timeout)
        try:
            c.request("POST" if body is not None else "GET", path,
                      json.dumps(body) if body is not None else None, h)
            r = c.getresponse()
            raw = r.read().decode("utf-8", "replace")
            try:
                return r.status, json.loads(raw)
            except Exception:
                return r.status, {"_raw": raw[:200]}
        finally:
            c.close()


# ------------------------------------------------------------------ guvenlik
def t_guvenlik(x):
    g = "guvenlik"
    s, _ = x.call("/api/status", key=False)
    x.add(g, "anahtarsiz istek reddedilir", s in (401, 403), f"kod {s}")
    spoof = {"Host": "abc-def.trycloudflare.com"}
    s, _ = x.call("/api/code/tree", headers=spoof)
    x.add(g, "tunel uzerinden kod agaci KAPALI", s == 403, f"kod {s}")
    s, _ = x.call("/api/code/write", {"path": "_autotest_spoof.py", "content": "x = 1\n"}, headers=spoof)
    x.add(g, "tunel uzerinden kod yazma KAPALI", s == 403, f"kod {s}")
    try:
        os.remove(os.path.join(HERE, "_autotest_spoof.py"))
    except OSError:
        pass
    s, _ = x.call("/api/code/tree", headers={"X-Forwarded-For": "1.2.3.4"})
    x.add(g, "proxy basligi olan istekte kod agaci KAPALI", s == 403, f"kod {s}")
    s, _ = x.call("/api/tracker/apply", {"id": "__autotest__"}, headers=spoof)
    x.add(g, "tunelden hassas islem (PIN) korumali", s == 403, f"kod {s}")
    # 27 Eyl 2026: gercek PUBLIC video ureten/yayinlayan iki uc PIN'siz kalmisti -
    # kapatildi, buraya kaldi (bir daha acilirsa test yakalar)
    s, _ = x.call("/api/maint/daily", {"kind": "morning"}, headers=spoof)
    x.add(g, "tunelden video URETME (gunluk uretim) PIN korumali", s == 403, f"kod {s}")
    s, _ = x.call("/api/pending/approve", {"video_id": "__autotest__"}, headers=spoof)
    x.add(g, "tunelden video YAYINLAMA (onay) PIN korumali", s == 403, f"kod {s}")
    s, r = x.call("/api/code/tree")
    x.add(g, "yerelden kod agaci acik", s == 200, f"kod {s}")


# ------------------------------------------------------------------ kod duzenleme
def t_kod(x):
    g, p = "kod", "_autotest_kod.py"
    try:
        s, r = x.call("/api/code/write", {"path": p, "content": "def f():\n    return 1\n"})
        x.add(g, "yeni dosya yazilir", s == 200 and r.get("ok"), r.get("error", ""))
        s, r0 = x.call("/api/code/read?path=" + p)
        s, r = x.call("/api/code/write", {"path": p, "content": "def bozuk(:\n"})
        x.add(g, "bozuk sozdizimi reddedilir", s == 400, r.get("error", ""))
        s, r1 = x.call("/api/code/read?path=" + p)
        x.add(g, "reddedilen kayit dosyayi bozmadi", "return 1" in r1.get("content", ""))
        s, r = x.call("/api/code/write", {"path": p, "content": "def f():\n    return 2\n", "hash": r0.get("hash")})
        x.add(g, "duzenleme yedek olusturur", r.get("ok") and r.get("backup"), r.get("error", ""))
        s, r = x.call("/api/code/write", {"path": p, "content": "x = 1\n", "hash": r0.get("hash")})
        x.add(g, "bayat hash (baska yerden degisme) reddedilir", s == 400, r.get("error", ""))
        s, bl = x.call("/api/code/backups?path=" + p)
        ok_bl = isinstance(bl, list) and bl
        x.add(g, "yedek listesi calisir", ok_bl)
        if ok_bl:
            x.call("/api/code/restore", {"path": p, "name": bl[-1]["name"]})
            s, r2 = x.call("/api/code/read?path=" + p)
            x.add(g, "geri alma eski surumu getirir", "return 1" in r2.get("content", "") and "return 2" not in r2.get("content", ""))
        for bad in ["../.env", ".env", "youtube_token.json", "security.py", "mission_control.bat",
                    "_engine/mission_token.txt", "C:/Windows/win.ini", "a/../../x.py"]:
            s, r = x.call("/api/code/read?path=" + urllib.parse.quote(bad))
            x.add(g, f"korumali yol okunamaz: {bad}", s == 400, r.get("error", ""))
    finally:
        try:
            os.remove(os.path.join(HERE, p))
        except OSError:
            pass
        shutil.rmtree(os.path.join(ENGINE, "code_backups", "files", p), ignore_errors=True)


# ------------------------------------------------------------------ mantik (sahte veriyle)
def t_mantik(x):
    g = "mantik"
    import analysis_config
    import tracker

    cfg = analysis_config.load()
    mk = lambda **kw: {**dict(id="v", title="T", published="2026-09-01", views=500, likes=5, comments=0, shares=0,
                              retention=10.0, subs=0, tags=[], hashtags=["#A", "#B", "#C"], rate=0.0, age_days=20, verdict="orta"), **kw}
    v, _ = tracker._judge(mk(views=1), cfg)
    x.add(g, "az izlenmeli video 'yeni' sayilir", v == "yeni", v)
    v, _ = tracker._judge(mk(), cfg)
    x.add(g, "yorumsuz + dusuk tutmali video 'zayif'", v == "zayif", v)
    v, _ = tracker._judge(mk(comments=9, shares=9, retention=40.0, rate=36.0), cfg)
    x.add(g, "yorumlu + yuksek tutmali video 'guclu'", v == "guclu", v)

    # tracker'i sahte veriyle calistir (gercek dosyalara yazmadan)
    saved = {k: getattr(tracker, k) for k in ("load", "_rj", "_wj", "_interventions", "_state", "age_hours")}
    try:
        def fake(rep, vids, fb=0):
            tracker.load = lambda: {"videos": vids, "hashtag_stats": []}
            tracker._rj = lambda path, default=None: rep if path.endswith("analytics_report.json") else (default if default is not None else {})
            tracker._wj = lambda *a, **k: None
            tracker._interventions = lambda hours=24: [{"event": "voice_mesh_fallback"}] * fb
            tracker._state = lambda: {}
            tracker.age_hours = lambda: 1.0
        vids = [mk(id=f"v{i}", retention=8.0, views=300 - i) for i in range(4)]
        fake({"cur": {"views": 900, "comments": 1, "shares": 5}, "prev": {"views": 300, "comments": 5, "shares": 3}}, vids)
        ids = {d["id"] for d in tracker.decisions()}
        x.add(g, "erisim artip yorum dusunce 'comments-down' karari", "comments-down" in ids, sorted(ids))
        x.add(g, "yorumsuz olgun videolar 'zero-comments' karari", "zero-comments" in ids)
        x.add(g, "dusuk tutma 'low-retention' karari", "low-retention" in ids)
        p = tracker.voice_plan()
        x.add(g, "yorum dusunce kapanis SORU olur", "comments" in p["cta"].lower() and "?" in p["cta"], p["cta"][:60])
        fake({"cur": {"views": 900, "comments": 9, "shares": 1}, "prev": {"views": 300, "comments": 5, "shares": 3}}, vids)
        x.add(g, "yorum artip paylasim dusunce kapanis PAYLASMA olur", "send it" in tracker.voice_plan()["cta"].lower())
        fake({"cur": {"views": 900, "comments": 9, "shares": 9}, "prev": {"views": 300, "comments": 5, "shares": 3}}, vids)
        x.add(g, "ikisi de artinca kapanis ABONE olur", "follow" in tracker.voice_plan()["cta"].lower())
        fake({"cur": {}, "prev": {}}, [], fb=4)
        p = tracker.voice_plan()
        x.add(g, "mesh 3+ kez dusunce yedek ses + kisa cumle", "yedek" in p["tts"] and p["max_sentence_words"] <= 14, p["tts"])
        x.add(g, "mesh dususu 'voice-fallback' karari uretir", "voice-fallback" in {d["id"] for d in tracker.decisions()})
    finally:
        for k, val in saved.items():
            setattr(tracker, k, val)

    # karar durumu kaliciligi
    tracker.set_status("__autotest__", "done")
    a = "__autotest__" in tracker._state()
    tracker.set_status("__autotest__", "open")
    b = "__autotest__" not in tracker._state()
    x.add(g, "karar durumu (yapildi/geri ac) kalicidir", a and b)

    # ayar dogrulama
    old = analysis_config.PATH
    tmp = os.path.join(ENGINE, "_autotest_cfg.json")
    try:
        json.dump({"min_views_engagement": "abc", "retention_high": 500}, open(tmp, "w"))
        analysis_config.PATH = tmp
        c = analysis_config.load()
        x.add(g, "bozuk/aralik disi ayar varsayilana duser",
              c["min_views_engagement"] == analysis_config._default("min_views_engagement")
              and c["retention_high"] == analysis_config._default("retention_high"))
        r = analysis_config.save({"min_views_engagement": 999999, "yok_boyle_ayar": 1})
        x.add(g, "gecersiz ayar kaydi reddedilir", r["ok"] is False and len(r["errors"]) == 2, r["errors"])
    finally:
        analysis_config.PATH = old
        try:
            os.remove(tmp)
        except OSError:
            pass


# ------------------------------------------------------------------ asistan
def t_asistan(x):
    g = "asistan"
    import assistant
    if not assistant.ACTIONS:
        import mission_control  # noqa: F401  (komut satirindan calisirken eylemleri kaydeder)
    r = assistant.execute("bu_islem_yok", {})
    x.add(g, "bilinmeyen islem reddedilir", r.get("ok") is False, r.get("error", ""))
    cat = assistant.catalog()
    x.add(g, "eylem katalogu dolu (>=20)", len(cat) >= 20, len(cat))
    bad = [a["name"] for a in cat if a.get("risk") not in ("safe", "confirm")]
    x.add(g, "her eylemin riski tanimli (safe/confirm)", not bad, bad)
    risky = [a["name"] for a in cat if any(w in a["name"] for w in ("sil", "kapat", "durdur", "yayinla", "onayla"))
             and a["name"] != "telefon_kapat" and a.get("risk") != "confirm"]
    x.add(g, "silen/kapatan/yayinlayan eylemler ONAY ister", not risky, risky)


# ------------------------------------------------------------------ veri
def _age_h(path):
    try:
        return (time.time() - os.path.getmtime(path)) / 3600
    except OSError:
        return None


def t_veri(x):
    g = "veri"
    a = _age_h(os.path.join(ENGINE, "tracker.json"))
    x.add(g, "takip verisi 13 saatten taze", a is not None and a < 13, f"{a:.1f} saat" if a is not None else "yok", warn=True)
    a = _age_h(os.path.join(ENGINE, "analytics_report.json"))
    x.add(g, "analiz raporu 3 gunden taze", a is not None and a < 72, f"{a:.1f} saat" if a is not None else "yok", warn=True)
    try:
        tok = json.load(open(os.path.join(HERE, "youtube_token.json"), encoding="utf-8"))
        x.add(g, "YouTube yenileme anahtari var", bool(tok.get("refresh_token")))
    except Exception as e:
        x.add(g, "YouTube yenileme anahtari var", False, type(e).__name__)
    src = open(os.path.join(HERE, "aura_editorial.py"), encoding="utf-8").read()
    x.add(g, "uretim, yapimci kurallari dosyasini okuyor", "operator_rules.md" in src)
    rules = os.path.join(ENGINE, "operator_rules.md")
    x.add(g, "yapimci kurallari dosyasi okunabilir", os.path.exists(rules) and os.path.getsize(rules) > 0,
          "yok (Takip > Uygula ile olusur)" if not os.path.exists(rules) else "", warn=True)


# ------------------------------------------------------------------ altyapi
def t_altyapi(x):
    g = "altyapi"
    try:
        # 27 Eyl 2026: kullanici karariyla otomatik zamanlayici KAPATILDI (tam
        # elle kontrol) - artik "Ready" olmasi degil, GOREVIN VAR OLMASI
        # (kurulum bozulmamis) onemli; durum sadece bilgi amacli.
        p = subprocess.run(["powershell", "-NoProfile", "-Command",
                            "Get-ScheduledTask -TaskName 'SignCouncilDaily' | Select-Object -ExpandProperty State"],
                           capture_output=True, text=True, timeout=25)
        st = p.stdout.strip()
        x.add(g, "SignCouncilDaily gorevi kurulu (Ready/Disabled ikisi de normal - elle kontrol modundayiz)",
              st in ("Ready", "Disabled"), f"durum: {st or 'gorev bulunamadi'}")
    except Exception as e:
        x.add(g, "SignCouncilDaily gorevi kurulu", False, f"{type(e).__name__}: {e}")
    import health
    info = health.last_good_info()
    fresh = bool(info) and (time.time() - time.mktime(time.strptime(info["when"], "%Y-%m-%d %H:%M"))) < 72 * 3600
    x.add(g, "son-calisan kopya var ve 3 gunden taze", fresh, info)
    x.add(g, "hicbir dosyada sozdizimi hatasi yok", not health.syntax_errors(), "; ".join(health.syntax_errors()[:3]))
    for mod in ("googleapiclient", "webview", "qrcode", "httpx"):
        try:
            __import__(mod)
            x.add(g, f"paket yuklu: {mod}", True)
        except Exception as e:
            x.add(g, f"paket yuklu: {mod}", False, type(e).__name__)
    free = shutil.disk_usage("C:\\").free / 1e9
    x.add(g, "diskte 5 GB'tan fazla yer var", free > 5, f"{free:.0f} GB")
    s, vh = x.call("/api/status")
    x.add(g, "ses sunucusu (:8124) acik", bool(vh.get("voice_up")), "kapali - canli yayin baslarken kendisi acilir", warn=True)
    # 2 Ekim 2026 bulgusu: Windows'ta allow_reuse_address iki surecin ayni porta SESSIZCE
    # birden baglanip istekleri rastgele bolusturmesine izin veriyordu (eski kod bazen
    # cevap veriyordu). Ikinci bir sunucu baslatmayi dene - artik ACIKCA reddedilmeli.
    try:
        import mission_control
        srv2 = mission_control._QuietServer(("127.0.0.1", mission_control.PORT), lambda *a, **k: None)
        srv2.server_close()
        x.add(g, "port cakismasi ACIKCA reddediliyor (sessiz cift-sunucu yok)", False,
              "IKINCI bir sunucu ayni porta sessizce baglanabildi - allow_reuse_address kontrol et")
    except OSError:
        x.add(g, "port cakismasi ACIKCA reddediliyor (sessiz cift-sunucu yok)", True)


# ------------------------------------------------------------------ uretim hatti (uctan uca, veri analiziyle bagli)
def t_uretim(x):
    g = "uretim"
    import statistics as st
    import daily_guard

    # 1) koruyucu: bat dosyalari onu cagiriyor mu, karar mantigi dogru mu
    for bat in ("daily_auto.bat", "daily_auto_evening.bat"):
        src = open(os.path.join(HERE, bat), encoding="utf-8", errors="replace").read()
        x.add(g, f"{bat} motoru koruyucu uzerinden calistirir", "daily_guard.py" in src)
    x.add(g, "koruyucu: internet var (DNS+TLS)", daily_guard.network_up(), "internet yok", warn=True)
    x.add(g, "koruyucu: DNS hatasinda + video yoksa TEKRAR dener",
          daily_guard.should_retry("HATA: [Errno 11001] getaddrinfo failed", False))
    x.add(g, "koruyucu: 5xx sunucu hatasinda tekrar dener",
          daily_guard.should_retry("Server error '500 Internal Server Error' for url", False))
    x.add(g, "koruyucu: video YUKLENDIYSE asla tekrar calistirmaz (cift yayin yok)",
          not daily_guard.should_retry("getaddrinfo failed ... YUKLENDI", True))
    x.add(g, "koruyucu: icerik/guvenlik reddinde tekrar denemez",
          not daily_guard.should_retry("Sensitivity gate: konu reddedildi", False))

    # 2) saglayici zinciri: birincil 500 verince yedege geciyor mu (sahte cagriciyla, ag yok)
    import httpx
    import providers
    calls = []

    def boom(m, s):
        req = httpx.Request("POST", "http://x")
        raise httpx.HTTPStatusError("500", request=req, response=httpx.Response(500, request=req))

    def good(m, s):
        calls.append("yedek")
        return "TAMAM"
    saved = dict(providers._RAW_CALLERS)
    saved_sleep = providers.time.sleep
    try:
        providers._RAW_CALLERS["gemini"] = good
        providers.time.sleep = lambda s: None
        out = providers._resilient("openai", boom, ["gemini"])([{"role": "user", "content": "x"}], "")
        x.add(g, "saglayici 500 verince yedege gecer", out == "TAMAM" and calls == ["yedek"], out)
    except Exception as e:
        x.add(g, "saglayici 500 verince yedege gecer", False, f"{type(e).__name__}: {e}")
    finally:
        providers._RAW_CALLERS.clear()
        providers._RAW_CALLERS.update(saved)
        providers.time.sleep = saved_sleep

    # 3) saglayicilar CANLI (1 kelimelik istek; hicbiri yoksa HATA, bazisi yoksa uyari)
    live = {}
    for name in ("gemini", "openai", "groq"):
        try:
            r = providers._RAW_CALLERS[name]([{"role": "user", "content": "Reply with the single word OK."}], "")
            live[name] = bool(str(r).strip())
        except Exception as e:
            live[name] = False
            x.add(g, f"saglayici canli: {name}", False, f"{type(e).__name__}: {str(e)[:80]}", warn=True)
        else:
            x.add(g, f"saglayici canli: {name}", live[name])
    x.add(g, "en az bir yapay zeka saglayicisi calisiyor", any(live.values()), "hicbiri yanit vermedi")

    # 4) YouTube: yetki + analitik erisimi (salt-okunur)
    try:
        from googleapiclient.discovery import build
        from youtube_auth import get_credentials
        ch = build("youtube", "v3", credentials=get_credentials()).channels().list(part="id", mine=True).execute()
        x.add(g, "YouTube API erisimi (kanal okunuyor)", bool(ch.get("items")))
    except Exception as e:
        import health
        health.friendly_error(e)
        x.add(g, "YouTube API erisimi (kanal okunuyor)", False,
              "GUNLUK KOTA DOLDU (10:00'da sifirlanir)" if health.quota_blocked() else f"{type(e).__name__}: {str(e)[:80]}",
              warn=health.quota_blocked())
    try:
        from youtube_analytics_auth import get_analytics_credentials
        x.add(g, "YouTube Analytics yetkisi gecerli", bool(get_analytics_credentials(interactive=False)))
    except Exception as e:
        x.add(g, "YouTube Analytics yetkisi gecerli", False, f"{type(e).__name__}: {str(e)[:80]}")

    # 5) render araclari
    x.add(g, "ffmpeg kurulu", shutil.which("ffmpeg") is not None, "ffmpeg PATH'te yok")

    # 6) VERI ANALIZI -> URETIM bagi: rapor dosyalari taze ve Aura'nin prompt'una giriyor mu
    import aura_editorial as ed
    for name, fn, max_days in (("engagement_digest.md", ed._engagement_digest, 10), ("optimize.md", ed._optimize_digest, 10)):
        path = os.path.join(ENGINE, name)
        age = _age_h(path)
        x.add(g, f"analiz raporu uretime giriyor: {name}", bool(fn().strip()), "bos/yok - prompt'a girmez", warn=True)
        x.add(g, f"analiz raporu taze (<{max_days} gun): {name}", age is not None and age < max_days * 24,
              f"{age / 24:.0f} gun once" if age is not None else "yok", warn=True)
    rules = ed._operator_rules()
    x.add(g, "yapimci kurallari (HOOK/FORMAT) uretim prompt'unda", ("HOOK" in rules and "FORMAT" in rules), "kural yok", warn=True)

    # 7) son uretimler gercekten yayina cikiyor mu (gunluk log'lardan)
    import health
    days = {}
    for f in sorted(os.listdir(HERE)):
        if f.startswith("_daily_auto_") and f.endswith(".log"):
            for r in health._log_runs(os.path.join(HERE, f)):
                days.setdefault(f[12:20], []).append(r["ok"])
    last7 = sorted(days)[-7:]
    got = [d for d in last7 if any(days[d])]
    x.add(g, "son 7 uretim gununun >=5'inde video yuklendi", len(got) >= 5, f"{len(got)}/{len(last7)} gun", warn=True)
    if days:
        newest = max(k for k, v in days.items() if any(v)) if got or any(any(v) for v in days.values()) else None
        if newest:
            gap = (datetime.date.today() - datetime.datetime.strptime(newest, "%Y%m%d").date()).days
            x.add(g, "son basarili yuklemeden bu yana <=2 gun", gap <= 2, f"{gap} gun once ({newest})", warn=True)

    # 7b) BUYUME MAKINESI: senaryo komutu + sesli kapanis + huni
    import make_topic_short as mts
    pr = mts._build_prompt("Test", "angle")
    x.add(g, "senaryo komutu: satir 5 secim sorusuyla biter (yorum motoru)", "COMMENT ENGINE" in pr and "TWO named sides" in pr)
    x.add(g, "senaryo komutu: yapimci kurallari (SUBS/CLOSING) giriyor", "PRODUCER RULES" in pr and "[SUBS]" in pr and "[CLOSING]" in pr, "kural eksik", warn=True)
    eng_src = open(os.path.join(HERE, "aura_engine.py"), encoding="utf-8").read()
    x.add(g, "evergreen/hottake gunun HABER planiyla degil KENDI konusuyla aciklama uretir",
          "build_evergreen(desc_override=_short_desc(plan))" not in eng_src and "build_hottake(desc_override=_short_desc(plan))" not in eng_src,
          "27 Eyl 2026 hatasi geri geldi: aciklama gunun alakasiz haberinden uretiliyor (bkz. DLbOG1Qaghs/DtCj6Rrq8-E)")
    x.add(g, "gunde-1-video kilidi var (.uploaded_today.json)", ".uploaded_today.json" in eng_src)
    ol = mts._outro_line()
    x.add(g, "sesli kapanis cagrisi tanimli ve kisa (<=14 kelime, 'follow' iceriyor)", 0 < len(ol.split()) <= 14 and "follow" in ol.lower(), ol)
    import tracker
    fn = tracker.funnel()
    x.add(g, "buyume hunisi hesaplanir (abone/yorum/paylasim/begeni)", bool(fn) and len(fn["rows"]) == 4, "analiz raporu yok", warn=True)

    # 8) STRATEJI DENEYI (26 Eyl baslangic): yeni kurallarla uretilen videolarin hedefleri
    try:
        vids = [v for v in json.load(open(os.path.join(ENGINE, "tracker.json"), encoding="utf-8"))["videos"]
                if v["published"] >= "2026-09-26"]
    except Exception:
        vids = []
    mature = [v for v in vids if v["age_days"] >= 3]
    if len(mature) < 5:
        x.add(g, "strateji deneyi (hedef: medyan>=50 izlenme, tutma>=%25)", True, f"{len(vids)} video, {len(mature)} olgun - olcum icin erken")
    else:
        med = st.median(v["views"] for v in mature)
        ret = st.median(v["retention"] for v in mature)
        x.add(g, "deney: medyan izlenme >=50", med >= 50, f"{med:.0f} ({len(mature)} video)", warn=True)
        x.add(g, "deney: medyan tutma >=%25", ret >= 25, f"%{ret:.0f}", warn=True)
        x.add(g, "deney: toplam yorum >=5", sum(v["comments"] for v in mature) >= 5, str(sum(v["comments"] for v in mature)), warn=True)


GROUPS = [t_guvenlik, t_kod, t_mantik, t_asistan, t_veri, t_altyapi, t_uretim]


def run(base_url="http://127.0.0.1:8800", token=None):
    if token is None:
        token = open(os.path.join(ENGINE, "mission_token.txt"), encoding="utf-8").read().strip()
    x = _Ctx(base_url, token)
    for fn in GROUPS:
        try:
            fn(x)
        except Exception as e:
            x.add(fn.__name__[2:], "test grubu calisti", False, f"{type(e).__name__}: {e}")
    fails = [r for r in x.rows if r["level"] == "fail"]
    warns = [r for r in x.rows if r["level"] == "warn"]
    rep = {"ts": datetime.datetime.now().isoformat(timespec="seconds"), "total": len(x.rows),
           "passed": sum(1 for r in x.rows if r["ok"]), "failed": len(fails), "warned": len(warns), "rows": x.rows}
    os.makedirs(ENGINE, exist_ok=True)
    json.dump(rep, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return rep


def last():
    try:
        return json.load(open(OUT, encoding="utf-8"))
    except Exception:
        return None


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    url = sys.argv[sys.argv.index("--url") + 1] if "--url" in sys.argv else "http://127.0.0.1:8800"
    r = run(url)
    for row in r["rows"]:
        print(("OK   " if row["ok"] else ("UYARI" if row["level"] == "warn" else "HATA ")), f"[{row['group']}] {row['name']}",
              ("| " + row["detail"]) if row["detail"] and not row["ok"] else "")
    print(f"\nSONUC: {r['passed']}/{r['total']} gecti, {r['failed']} hata, {r['warned']} uyari")
    sys.exit(1 if r["failed"] else 0)
