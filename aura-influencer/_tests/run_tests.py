"""Aura Influencer Studio - tam test paketi.  Kullanim:  python _tests/run_tests.py [--quick]
Panel PROJENIN GECICI KOPYASINDA baslatilir; gercek dosyalar degismez.
--quick: yavas testleri (60 sn PIN kilidi beklemesi, canli AI cagrisi, TTS) atlar.
"""
import glob
import json
import os
import py_compile
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUICK = "--quick" in sys.argv
PORT = 8898
BASE = f"http://127.0.0.1:{PORT}"
RES = []


def check(name, ok, detail=""):
    RES.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail and not ok else ""), flush=True)


def skip(name, why):
    RES.append((name, None, why))
    print(f"SKIP {name}  [{why}]", flush=True)


def http(method, path, body=None, headers=None, timeout=60):
    h = dict(headers or {})
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            code = r.status
    except urllib.error.HTTPError as e:
        raw, code = e.read(), e.code
    try:
        return code, json.loads(raw)
    except Exception:
        return code, raw


def main():
    tmp = tempfile.mkdtemp(prefix="aura_test_")
    work = os.path.join(tmp, "proj")
    shutil.copytree(ROOT, work, ignore=shutil.ignore_patterns(
        "output", "_video_work", "uploads", "__pycache__", "_backups", "_tests", "*.log", "_safe_restart_log.txt", "_panel_run_log.txt", "code_pin.txt"))
    envsrc = os.path.join(ROOT, "..", "council-backend", ".env")
    if os.path.exists(envsrc):
        os.makedirs(os.path.join(tmp, "council-backend"), exist_ok=True)
        shutil.copy2(envsrc, os.path.join(tmp, "council-backend", ".env"))
    for d in ("output", "uploads", "documents"):
        os.makedirs(os.path.join(work, "_studio", d), exist_ok=True)
    _src_out = os.path.join(ROOT, "_studio", "output")
    if os.path.isdir(_src_out):  # zip/indirme testleri icin 2 gercek video kopyala
        for _f in sorted((f for f in os.listdir(_src_out) if f.endswith(".mp4")),
                         key=lambda f: os.path.getmtime(os.path.join(_src_out, f)), reverse=True)[:2]:
            shutil.copy2(os.path.join(_src_out, _f), os.path.join(work, "_studio", "output", _f))

    # ---------- 1) STATIK ----------
    for f in [os.path.join(ROOT, "aura_studio.py")] + glob.glob(os.path.join(ROOT, "_studio", "*.py")):
        try:
            py_compile.compile(f, doraise=True)
            check(f"derleme {os.path.basename(f)}", True)
        except Exception as e:
            check(f"derleme {os.path.basename(f)}", False, str(e)[:200])
    r = subprocess.run([sys.executable, "-W", "error::SyntaxWarning", "-c",
                        "import ast,sys;ast.parse(open(sys.argv[1],encoding='utf-8').read())",
                        os.path.join(ROOT, "aura_studio.py")], capture_output=True, text=True)
    check("aura_studio.py SyntaxWarning yok", r.returncode == 0, r.stderr[-200:])
    imp = subprocess.run([sys.executable, "-c",
                          "import importlib.util as u,re,json;s=u.spec_from_file_location('c','aura_studio.py');"
                          "m=u.module_from_spec(s);s.loader.exec_module(m);"
                          "js='\\n'.join(re.findall(r'<script>(.*?)</script>',m.PAGE,re.S));"
                          "open('_page_test.js','w',encoding='utf-8').write(js);print('OK')"],
                         cwd=work, capture_output=True, text=True)
    check("aura_studio.py import (NameError vb. yok)", "OK" in imp.stdout, imp.stderr[-300:])

    page_ok = subprocess.run([sys.executable, "-c", "import importlib.util as u;s=u.spec_from_file_location('c','aura_studio.py');m=u.module_from_spec(s);s.loader.exec_module(m);"
                              "P=m.PAGE;assert 'Sign Council' not in P and 'view-council' not in P;"
                              "assert all(x in P for x in ('view-insights','tt_dl','autoTags','codeSetImage','insSend','view-comments','cmPost','cmPinDone','tt_zip_list','ai_usage','codeSetProv','ttCopyEl','tt_done_btn','insAudit','max-width:820px','tkSave','anAuth','in_trend','view-growth','gmCandidates','gmPre','rp_pre','gmApply','gmPublish','gm_tt','gm_exps','mdHtml'));print('UI_OK')"],
                             cwd=work, capture_output=True, text=True)
    check("arayuz: Sign Council yok, yeni bolumler var", "UI_OK" in page_ok.stdout, page_ok.stderr[-200:])
    al = subprocess.run([sys.executable, "-c", "import importlib.util as u,re;s=u.spec_from_file_location('c','aura_studio.py');m=u.module_from_spec(s);s.loader.exec_module(m);"
                         "en='One thing. Two things. Three things. Four things.';tr='Bir sey. Iki sey daha burada ama uc sey de var gercekten. Dort sey.';out=m._align_tr_to_en(en,tr);"
                         "n=lambda t:len([x for x in re.split(r'(?<=[.!?])[ ]+',t.strip()) if x]);"
                         "assert n(out)==4,out;assert m._align_tr_to_en('A. B.','Tek.')=='Tek.';"
                         "t,d,msg=m._auto_tags('T','x','A,B','desc #A');assert (t,d,msg)==('A,B','desc #A','');print('ALIGN_OK')"],
                        cwd=work, capture_output=True, text=True)
    check("TR cumle sayisi EN'e esitlenir + otomatik etiket mevcut etiketi ezmez", "ALIGN_OK" in al.stdout, al.stderr[-300:] + al.stdout[-200:])
    if os.path.exists(os.path.join(ROOT, "_tests", "agent_unit.py")):
        shutil.copy2(os.path.join(ROOT, "_tests", "agent_unit.py"), os.path.join(work, "_agent_unit.py"))
        au = subprocess.run([sys.executable, "_agent_unit.py"], cwd=work, capture_output=True, text=True, timeout=180, env=dict(os.environ, AURA_NO_OPEN="1", AURA_STUDIO_PORT="8890"))
        try:
            jr = json.loads(au.stdout.strip().splitlines()[-1])
            check(f"Studio Asistani birim testleri ({jr['total']} kontrol)", not jr["bad"], str(jr["bad"])[:300])
        except Exception as ex:
            check("Studio Asistani birim testleri", False, (au.stderr[-400:] + au.stdout[-300:]) or repr(ex))
    if os.path.exists(os.path.join(ROOT, "_tests", "tr_unit.py")):
        shutil.copy2(os.path.join(ROOT, "_tests", "tr_unit.py"), os.path.join(work, "_tr_unit.py"))
        tu = subprocess.run([sys.executable, "_tr_unit.py"], cwd=work, capture_output=True, text=True, timeout=120, env=dict(os.environ, AURA_NO_OPEN="1", AURA_STUDIO_PORT="8889"))
        try:
            jr = json.loads(tu.stdout.strip().splitlines()[-1])
            check(f"Turkce CC garantisi birim testleri ({jr['total']} kontrol)", not jr["bad"], str(jr["bad"])[:300])
        except Exception as ex:
            check("Turkce CC garantisi birim testleri", False, (tu.stderr[-400:] + tu.stdout[-300:]) or repr(ex))
    if os.path.exists(os.path.join(ROOT, "_tests", "learner_unit.py")):
        shutil.copy2(os.path.join(ROOT, "_tests", "learner_unit.py"), os.path.join(work, "_learner_unit.py"))
        lu = subprocess.run([sys.executable, "_learner_unit.py"], cwd=work, capture_output=True, text=True, timeout=300, env=dict(os.environ, AURA_NO_OPEN="1"))
        try:
            jr = json.loads(lu.stdout.strip().splitlines()[-1])
            check(f"Ogrenen sistem birim testleri ({jr['total']} kontrol)", not jr["bad"], str(jr["bad"])[:300])
        except Exception as ex:
            check("Ogrenen sistem birim testleri", False, (lu.stderr[-400:] + lu.stdout[-300:]) or repr(ex))
    if os.path.exists(os.path.join(ROOT, "_tests", "today_unit.py")):
        shutil.copy2(os.path.join(ROOT, "_tests", "today_unit.py"), os.path.join(work, "_today_unit.py"))
        tdu = subprocess.run([sys.executable, "_today_unit.py"], cwd=work, capture_output=True, text=True, timeout=120, env=dict(os.environ, AURA_NO_OPEN="1", AURA_STUDIO_PORT="8891"))
        try:
            jr = json.loads(tdu.stdout.strip().splitlines()[-1])
            check(f"Bugun ana yuzu birim testleri ({jr['total']} kontrol)", not jr["bad"], str(jr["bad"])[:300])
        except Exception as ex:
            check("Bugun ana yuzu birim testleri", False, (tdu.stderr[-400:] + tdu.stdout[-300:]) or repr(ex))
    if os.path.exists(os.path.join(ROOT, "_tests", "series_unit.py")):
        shutil.copy2(os.path.join(ROOT, "_tests", "series_unit.py"), os.path.join(work, "_series_unit.py"))
        su = subprocess.run([sys.executable, "_series_unit.py"], cwd=work, capture_output=True, text=True, timeout=300, env=dict(os.environ, AURA_NO_OPEN="1"))
        try:
            jr = json.loads(su.stdout.strip().splitlines()[-1])
            check(f"Hype or Real serisi birim testleri ({jr['total']} kontrol)", not jr["bad"], str(jr["bad"])[:300])
        except Exception as ex:
            check("Hype or Real serisi birim testleri", False, (su.stderr[-400:] + su.stdout[-300:]) or repr(ex))
    node = shutil.which("node")
    if node and os.path.exists(os.path.join(work, "_page_test.js")):
        r = subprocess.run([node, "--check", "_page_test.js"], cwd=work, capture_output=True, text=True)
        check("web arayuzu JavaScript sozdizimi", r.returncode == 0, r.stderr[-300:])
    else:
        skip("JS sozdizimi", "node yok")
    if node and os.path.exists(os.path.join(work, "_page_test.js")) and os.path.exists(os.path.join(ROOT, "_tests", "pin_loop.js")):
        r = subprocess.run([node, os.path.join(ROOT, "_tests", "pin_loop.js"), os.path.join(work, "_page_test.js")], capture_output=True, text=True, timeout=30)
        check("PIN'siz halde asistan arka plan sorgusu prompt ACMAZ (pencere kilitlenme regresyonu)", "RESULT {\"prompts\":0}" in r.stdout, r.stdout[-200:] + r.stderr[-200:])
    bat = open(os.path.join(ROOT, "AuraCommandCenter.bat"), "rb").read()
    check(".bat CRLF", b"\r\n" in bat and b"\n" not in bat.replace(b"\r\n", b""))
    gi = open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
    for s in ("client_secret.json", "token.json", "access_token.txt", "code_pin.txt", "_backups"):
        check(f".gitignore {s}", s in gi)

    # ---------- 2) VERI ----------
    days = json.load(open(os.path.join(ROOT, "_studio", "day_status.json"), encoding="utf-8"))
    nums = [d["day"] for d in days]
    # Siralama + tekillik sart; mutlak ardisiklik SART DEGIL - kalitesiz/yanlislikla yayinlanan bir
    # gun operator onayiyla YouTube'dan silinip day_status'tan cikarilabilir (bkz. Gun 40 olayi,
    # 2026-10-04), bu durumda bilincli bir bosluk (ör. 39->41) birakilir, hata degildir.
    check("day_status gunler artan+tekil", nums == sorted(set(nums)) and len(nums) == len(set(nums)), str(nums))
    check("day_status >=24 gun", len(nums) >= 24)
    sys.path.insert(0, os.path.join(ROOT, "_studio"))
    try:
        import subtitles
        op = os.path.join(tmp, "t.srt")
        subtitles.build_srt([("Hello there. This is Aura, an AI.", 0.0, 6.0), ("A second line here.", 6.0, 3.0)], op)
        srt = open(op, encoding="utf-8").read()
        check("build_srt uretir", "-->" in srt and "Aura" in srt and srt.count("-->") >= 2, srt[:100])
    except Exception as e:
        check("build_srt", False, repr(e))
    if not QUICK:
        pass

    # ---------- 3) SUNUCU ----------
    env = dict(os.environ, AURA_NO_OPEN="1", AURA_STUDIO_PORT=str(PORT), PYTHONIOENCODING="utf-8")
    logf = open(os.path.join(tmp, "server.log"), "w", encoding="utf-8")
    srv = subprocess.Popen([sys.executable, "aura_studio.py"], cwd=work, env=env, stdout=logf, stderr=subprocess.STDOUT)
    try:
        for _ in range(40):
            try:
                if http("GET", "/api/history")[0] == 200:
                    break
            except Exception:
                time.sleep(1)
        code, _ = http("GET", "/")
        check("ana sayfa 200 (loopback)", code == 200)
        token = open(os.path.join(work, "_studio", "access_token.txt"), encoding="utf-8").read().strip()
        tun = {"Cf-Connecting-Ip": "1.2.3.4", "Cf-Ray": "abc"}
        check("tunel + token yok -> 401", http("GET", "/api/status", headers=tun)[0] == 401)
        check("tunel + yanlis token -> 401", http("GET", "/api/status?key=yanlis", headers=tun)[0] == 401)
        check("tunel + dogru token -> 200", http("GET", f"/api/status?key={token}", headers=tun)[0] == 200)
        check("tunel + token yok POST -> 401", http("POST", "/api/save_doc", {"content": "x"}, headers=tun)[0] == 401)
        for p in ("/api/day_status", "/api/videos", "/api/docs", "/api/tunnel_status", "/api/tailscale_status",
                  "/api/voice_mesh_status", "/api/history"):
            c, _ = http("GET", p)
            check(f"GET {p}", c == 200, str(c))
        check("bilinmeyen yol 404", http("GET", "/api/yok")[0] == 404)

        # ---- kod modu guvenligi ----
        pin = open(os.path.join(work, "_studio", "code_pin.txt"), encoding="utf-8").read().strip() \
            if os.path.exists(os.path.join(work, "_studio", "code_pin.txt")) else None
        http("GET", "/api/code/files")  # PIN dosyasi ilk istekte olusur
        pin = open(os.path.join(work, "_studio", "code_pin.txt"), encoding="utf-8").read().strip()
        check("PIN 8 hane rakam", bool(re.fullmatch(r"\d{8}", pin)))
        P = {"X-Code-Pin": pin}
        check("kod: PIN yok -> 403", http("GET", "/api/code/files")[0] == 403)
        check("kod: tunel basligi + dogru PIN + dogru token -> 403",
              http("GET", f"/api/code/files?key={token}", headers=dict(P, **tun))[0] == 403)
        c, d = http("GET", "/api/code/files", headers=P)
        files = d.get("files", []) if isinstance(d, dict) else []
        check("kod: dogru PIN -> dosya listesi", c == 200 and "aura_studio.py" in files, str(c))
        check("kod: listede gizli dosya yok", not any(x in files for x in
              ("_studio/token.json", "_studio/client_secret.json", "_studio/access_token.txt", "_studio/code_pin.txt")))
        check("kod: listede output/uploads yok", not any(x.startswith(("_studio/output", "_studio/uploads")) for x in files))
        bad = ["../CLAUDE.md", "..\\CLAUDE.md", "/etc/passwd", "C:/Windows/win.ini", "_studio/../../x.py",
               "_studio/token.json", "_studio/client_secret.json", "_studio/access_token.txt", "_studio/code_pin.txt",
               "_studio/safe_restart.py", "_studio/conversation.json", "yeni_dosya.py", "_studio/output/x.txt",
               "%2e%2e/CLAUDE.md", "aura_studio.py\x00.txt", "", "_studio", "AuraCommandCenter.exe"]
        for b in bad:
            c, d = http("GET", "/api/code/file?path=" + urllib.request.quote(b), headers=P)
            check(f"kod okuma reddi {b!r}", isinstance(d, dict) and d.get("ok") is False, str(d)[:100])
            c, d = http("POST", "/api/code/save", {"path": b, "content": "x"}, headers=P)
            check(f"kod yazma reddi {b!r}", isinstance(d, dict) and d.get("ok") is False, str(d)[:100])
        # kayit/yedek/geri yukle - README.md (LF), .bat (CRLF)
        rel = "README.md"
        orig = open(os.path.join(work, rel), "rb").read()
        c, d = http("GET", f"/api/code/file?path={rel}", headers=P)
        text = d["content"]
        c, d = http("POST", "/api/code/save", {"path": rel, "content": text + "\nTEST-SATIRI\n"}, headers=P)
        check("kod: kaydet ok+yedek", d.get("ok") and d.get("backup"), str(d))
        check("kod: dosya degisti", b"TEST-SATIRI" in open(os.path.join(work, rel), "rb").read())
        c, d = http("GET", f"/api/code/backups?path={rel}", headers=P)
        baks = d.get("backups", [])
        check("kod: yedek listede", len(baks) >= 1, str(d))
        c, d = http("POST", "/api/code/restore", {"path": rel, "backup": baks[0]}, headers=P)
        after = open(os.path.join(work, rel), "rb").read()
        check("kod: geri yukleme BIREBIR (bayt)", d.get("ok") and after == orig, str(d))
        c, d = http("POST", "/api/code/restore", {"path": rel, "backup": "../../etc/x.bak"}, headers=P)
        check("kod: yedek yolu gecisi reddi", d.get("ok") is False)
        b0 = open(os.path.join(work, "AuraCommandCenter.bat"), "rb").read()
        c, d = http("GET", "/api/code/file?path=AuraCommandCenter.bat", headers=P)
        c, d = http("POST", "/api/code/save", {"path": "AuraCommandCenter.bat",
                                                "content": d["content"] + "rem test\n"}, headers=P)
        nb = open(os.path.join(work, "AuraCommandCenter.bat"), "rb").read()
        check(".bat kaydi CRLF korur", d.get("ok") and b"\r\n" in nb and b"\n" not in nb.replace(b"\r\n", b""))
        c, d = http("POST", "/api/code/save", {"path": "_studio/day_status.json", "content": "{bozuk"}, headers=P)
        check("gecersiz JSON reddi", d.get("ok") is False)
        c, d = http("POST", "/api/code/save", {"path": "_studio/subtitles.py", "content": "def x(:\n"}, headers=P)
        check("py sozdizimi hatasi reddi", d.get("ok") is False)
        c, d = http("POST", "/api/code/save", {"path": "_studio/subtitles.py", "content": "x = '\\d'\n"}, headers=P)
        check("py SyntaxWarning (gecersiz kacis) reddi", d.get("ok") is False, str(d)[:120])
        c, d = http("GET", "/api/code/file?path=aura_studio.py", headers=P)
        st = d["content"]
        c, d = http("POST", "/api/code/save", {"path": "aura_studio.py",
                    "content": st.replace("def main():", "kacak_isim_1\ndef main():", 1)}, headers=P)
        check("aura_studio import hatasi reddi", d.get("ok") is False)
        # apply atomikligi
        c, d = http("POST", "/api/code/apply", {"path": rel, "edits": [
            {"search": "Aura", "replace": "AURA"}]}, headers=P)
        check("apply: belirsiz (cok eslesen) SEARCH reddi", d.get("ok") is False, str(d)[:120])
        c, d = http("POST", "/api/code/apply", {"path": rel, "edits": [
            {"search": "", "replace": "x"}]}, headers=P)
        check("apply: bos SEARCH reddi", d.get("ok") is False)
        check("apply hatasinda dosya degismedi", open(os.path.join(work, rel), "rb").read() == orig)
        # eszamanli
        import concurrent.futures as cf
        with cf.ThreadPoolExecutor(8) as ex:
            rs = list(ex.map(lambda _: http("GET", "/api/code/files", headers=P)[0], range(16)))
        check("16 eszamanli istek", all(x == 200 for x in rs), str(rs))

        # ---- canli AI ----
        if QUICK:
            skip("kod AI onerisi", "--quick")
        else:
            c, d = http("POST", "/api/code/ai", {"path": "_studio/subtitles.py",
                        "instruction": "build_srt fonksiyonunun ustune Turkce bir aciklama yorumu ekle. Sadece oneri."}, headers=P, timeout=200)
            check("kod AI yanit verdi", isinstance(d, dict) and d.get("ok") and len(d.get("reply", "")) > 20, str(d)[:200])
            if isinstance(d, dict) and d.get("ok"):
                check("kod AI SEARCH/REPLACE blogu uretti", len(d.get("edits", [])) >= 1, d.get("reply", "")[:300])
                if d.get("edits"):
                    c, a = http("POST", "/api/code/apply", {"path": "_studio/subtitles.py", "edits": d["edits"]}, headers=P)
                    check("AI onerisi uygulanabilir + derlenir", a.get("ok"), str(a)[:200])


        # ---- analiz / yorum / hashtag / TikTok paketi ----
        c, d = http("GET", "/api/insights/stats")
        check("analiz: kanal + video istatistigi (gercek API)", isinstance(d, dict) and d.get("ok") and len(d.get("videos", [])) >= 20
              and d.get("channel_id") == "UClYXgzueuL-eMTId2IZ7aNA", str(d)[:150])
        check("analiz: tunel + token yok -> 401", http("GET", "/api/insights/stats", headers=tun)[0] == 401)
        vid = d["videos"][0]["id"] if isinstance(d, dict) and d.get("videos") else ""
        c, d2 = http("GET", "/api/insights/comments?video_id=" + vid)
        check("analiz: yorum listesi", isinstance(d2, dict) and d2.get("ok") is True, str(d2)[:150])
        c, d3 = http("POST", "/api/insights/post_reply", {"parent_id": "x", "text": ""})
        check("yorum: bos yanit reddi (gonderilmez)", isinstance(d3, dict) and d3.get("ok") is False)
        c, d4 = http("GET", "/api/tiktok_meta")
        check("tiktok_meta doner", c == 200 and isinstance(d4, dict) and len(d4) >= 10, str(c))
        vids = http("GET", "/api/videos")[1]
        if vids:
            cc, _ = http("GET", "/download/" + urllib.request.quote(vids[0]))
            check("video indirme 200", cc == 200)
        for bad_dl in ("..%2Faccess_token.txt", "..%2F..%2Faura_studio.py", "x.py", "nonexist.mp4"):
            cc, _ = http("GET", "/download/" + bad_dl)
            check(f"indirme reddi {bad_dl}", cc == 404, str(cc))
        cc, _ = http("GET", "/download/" + urllib.request.quote(vids[0] if vids else "a.mp4"), headers=tun)
        check("indirme: tunel + token yok -> 401", cc == 401)
        if QUICK:
            skip("hashtag AI", "--quick")
        else:
            c, d5 = http("POST", "/api/insights/hashtags", {"title": "You Are Being Replaced", "script": "AI will not take your job."}, timeout=90)
            check("hashtag onerisi (#AuraAI dahil)", isinstance(d5, dict) and d5.get("ok") and "#AuraAI" in d5.get("tags", "") and d5["tags"].count("#") >= 6, str(d5)[:200])
            png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
            c, d6 = http("POST", "/api/code/ai", {"path": "_studio/subtitles.py", "instruction": "Bu gorselde ne var? Sadece bir cumleyle acikla, duzenleme onerme.", "image": png, "mime": "image/png"}, headers=P, timeout=200)
            check("kod AI gorselli istek calisir", isinstance(d6, dict) and d6.get("ok") and len(d6.get("reply", "")) > 5, str(d6)[:200])

        c, d7 = http("POST", "/api/insights/post_comment", {"video_id": "x", "text": "", "pin": True})
        check("yorum: bos metin reddi (post_comment)", isinstance(d7, dict) and d7.get("ok") is False)
        c, d8 = http("GET", "/api/insights/pins")
        check("sabit yorum listesi (pins) doner", isinstance(d8, dict) and d8.get("ok") is True and isinstance(d8.get("pins"), dict))
        check("pins: tunel + token yok -> 401", http("GET", "/api/insights/pins", headers=tun)[0] == 401)
        try:
            import insights as _ins, tempfile as _tf
            _ins.PINS_FILE = os.path.join(_tf.mkdtemp(), "p.json")
            e = _ins.pins_add("VID123", "T", "CID9", "hello")
            ok1 = e["link"].endswith("watch?v=VID123&lc=CID9") and not e["pinned"]
            _ins.pins_done("CID9")
            check("pins: ekle -> link dogru -> sabitledim isaretle", ok1 and _ins.pins_load()["CID9"]["pinned"] is True)
        except Exception as ex:
            check("pins birim testi", False, repr(ex))

        # ---- TikTok zip + AI kullanim/ayar ----
        vids2 = http("GET", "/api/videos")[1]
        req = urllib.request.Request(BASE + "/api/tiktok_zip?v=" + urllib.request.quote(",".join(vids2[:2] + ["../aura_studio.py"])))
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                zraw = r.read()
            import zipfile, io
            zn = zipfile.ZipFile(io.BytesIO(zraw)).namelist()
            check("tiktok zip: mp4 + aciklama + ACIKLAMALAR.txt", "ACIKLAMALAR.txt" in zn and sum(x.endswith(".mp4") for x in zn) == len(vids2[:2])
                  and sum(x.endswith(".txt") for x in zn) == len(vids2[:2]) + 1 and not any(".py" in x for x in zn), str(zn))
        except Exception as ex:
            check("tiktok zip", False, repr(ex))
        try:
            urllib.request.urlopen(urllib.request.Request(BASE + "/api/tiktok_zip?v=nonexist.mp4"), timeout=10)
            check("tiktok zip: var olmayan video reddi", False)
        except urllib.error.HTTPError as ex:
            check("tiktok zip: var olmayan video reddi", ex.code == 404)
        check("tiktok zip: tunel + token yok -> 401", http("GET", "/api/tiktok_zip?v=a.mp4", headers=tun)[0] == 401)
        c, us = http("GET", "/api/ai_usage")
        check("ai_usage doner (varsayilan kod saglayicisi Gemini)", isinstance(us, dict) and us.get("code_prefer") == "Gemini", str(us)[:120])
        c, s1 = http("POST", "/api/code/ai_settings", {"code_prefer": "Groq"}, headers=P)
        check("ai ayari degisir (PIN ile)", s1.get("ok") and s1.get("code_prefer") == "Groq", str(s1))
        c, s2 = http("POST", "/api/code/ai_settings", {"code_prefer": "Groq"})
        check("ai ayari PIN'siz reddedilir", c == 403)
        c, s3 = http("POST", "/api/code/ai_settings", {"code_prefer": "evil"}, headers=P)
        check("ai ayari gecersiz deger reddi", s3.get("ok") is False)
        http("POST", "/api/code/ai_settings", {"code_prefer": "Gemini"}, headers=P)

        c, pk = http("GET", "/api/tiktok_pack?video=" + urllib.request.quote(vids2[0] if vids2 else "x.mp4"))
        check("tiktok_pack: aciklama + indirme linki + youtube linki alanlari", isinstance(pk, dict) and pk.get("ok") and "description" in pk and "download_link" in pk and "youtube_link" in pk, str(pk)[:200])
        if isinstance(pk, dict) and pk.get("download_link"):
            check("tiktok_pack: indirme linki anahtarli ve dogru yol", "/download/" in pk["download_link"] and "key=" in pk["download_link"], pk["download_link"][:80])
        check("tiktok_pack: tunel + token yok -> 401", http("GET", "/api/tiktok_pack?video=a.mp4", headers=tun)[0] == 401)

        c, au = http("POST", "/api/insights/audit", {"question": "kisa ozet"}, timeout=200) if not QUICK else (0, {})
        if QUICK:
            skip("strateji analizi (AI)", "--quick")
        else:
            check("strateji analizi: gercek veriyle yanit + veri ozeti", isinstance(au, dict) and au.get("ok") and "REAL" not in au.get("text", "")[:0] and "subscribers" in au.get("digest", "") and len(au.get("text", "")) > 200, str(au)[:200])
        check("strateji analizi: tunel + token yok -> 401", http("POST", "/api/insights/audit", {}, headers=tun)[0] == 401)

        c, tr_ = http("GET", "/api/insights/trend")
        check("trend: seri + deltas alanlari", isinstance(tr_, dict) and tr_.get("ok") and "series" in tr_ and "deltas" in tr_, str(tr_)[:150])
        c, an_ = http("GET", "/api/insights/analytics")
        check("analytics: yetki yoksa acik durum doner (hata degil)", isinstance(an_, dict) and an_.get("ok") and "status" in an_, str(an_)[:150])
        c, tk0 = http("GET", "/api/insights/tiktok")
        check("tiktok elle giris: liste doner", isinstance(tk0, dict) and tk0.get("ok") and "latest" in tk0)
        c, tk1 = http("POST", "/api/insights/tiktok_add", {"video_id": "TESTID", "title": "TEST", "views": 12, "likes": 3, "comments": 1, "shares": 2})
        check("tiktok elle giris: kayit", isinstance(tk1, dict) and tk1.get("ok") and tk1["row"]["views"] == 12, str(tk1)[:150])
        c, tk2 = http("POST", "/api/insights/tiktok_add", {"video_id": "X", "title": "T", "views": -5})
        check("tiktok elle giris: negatif sayi reddi", isinstance(tk2, dict) and tk2.get("ok") is False, str(tk2)[:150])
        c, tk3 = http("POST", "/api/insights/tiktok_add", {"video_id": "X", "title": "T", "views": "abc"})
        check("tiktok elle giris: metin reddi", isinstance(tk3, dict) and tk3.get("ok") is False)
        check("analytics_auth: tunel basligiyla reddedilir", http("POST", "/api/insights/analytics_auth", {}, headers=dict(tun, **{"X-Forwarded": "1"}))[0] in (401, 403))

        c, gs = http("GET", "/api/growth/state")
        check("makine: format tablosu + medyan", isinstance(gs, dict) and gs.get("ok") and len(gs.get("groups", [])) >= 3 and "median_views" in gs, str(gs)[:150])
        c, gt = http("POST", "/api/growth/tag", {"video_id": "TESTID", "format": "template"})
        check("makine: format etiketi kaydi", isinstance(gt, dict) and gt.get("ok") is True)
        c, gt2 = http("POST", "/api/growth/tag", {"video_id": "TESTID", "format": "evil"})
        check("makine: gecersiz format reddi", isinstance(gt2, dict) and gt2.get("ok") is False)
        good_en = "Stop pasting long prompts. Use one line instead. Prompt: act as an editor and cut this to ten words. Which prompt will you try?"
        c, pf1 = http("POST", "/api/growth/preflight", {"title": "One Line Prompt Fix", "en_text": good_en, "tr_text": "", "description": "I'm Aura, an AI. #AuraAI"})
        check("on kontrol: iyi taslak yuksek skor", isinstance(pf1, dict) and pf1.get("ok") and pf1["score"] >= pf1["of"] - 2, str(pf1)[:200])
        bad_en = "Bu Turkce bir script. I improve with each video and I analyze without bias. This will make you a millionaire immediately."
        c, pf2 = http("POST", "/api/growth/preflight", {"title": "Aura Day 9: The Pareto (80/20) AI Prompt 🔥", "en_text": bad_en, "tr_text": "", "description": ""})
        labels_failed = [x["label"] for x in pf2.get("checks", []) if x["ok"] is False] if isinstance(pf2, dict) else []
        check("on kontrol: kotu taslak yakalanir (TR karakter, iddia, abartili vaat, tekrar, emoji)",
              len(labels_failed) >= 4 and pf2["score"] < pf1["score"], str(labels_failed))
        check("makine: tunel + token yok -> 401", http("POST", "/api/growth/candidates", {}, headers=tun)[0] == 401)
        if not QUICK:
            c, gc = http("POST", "/api/growth/candidates", {}, timeout=240)
            check("makine: 3 aday + on kontrol", isinstance(gc, dict) and gc.get("ok") and len(gc.get("drafts", [])) == 3 and all(x.get("preflight") and x["status"] == "taslak" for x in gc["drafts"]), str(gc)[:200])

        # ---- makine v2: aksiyon uygula / taslak / deney / yayin korumasi ----
        c, gs2 = http("GET", "/api/growth/state")
        check("makine: kpi + deneyler + taslaklar + aksiyonlar alanlari", isinstance(gs2, dict) and all(k in gs2 for k in ("kpi", "experiments", "drafts", "actions", "reports")), str(list(gs2)[:12]))
        check("makine: format tablosunda TikTok sutunlari", isinstance(gs2, dict) and all("tt_n" in g for g in gs2.get("groups", [])))
        vid_ids = [v["id"] for v in gs2.get("videos", [])[:1]]
        wd = os.path.join(work, "_studio")
        acts = [{"id": "aa000001", "type": "retag", "video_id": vid_ids[0], "format": "identity", "title": "t", "why": "test", "status": "bekliyor"},
                {"id": "aa000002", "type": "experiment", "name": "Test deney", "hypothesis": "h", "format": "template", "target_n": 3, "why": "test", "status": "bekliyor"},
                {"id": "aa000003", "type": "draft", "title": "Test Draft Title", "en_script": "One. Two. Three?", "tr_script": "Bir. Iki. Uc?", "description": "d", "tags": "a", "format": "template", "why": "test", "status": "bekliyor"},
                {"id": "aa000004", "type": "retag", "video_id": vid_ids[0], "format": "other", "title": "t", "why": "reddedilecek", "status": "bekliyor"}]
        json.dump(acts, open(os.path.join(wd, "actions.json"), "w", encoding="utf-8"))
        c, ap1 = http("POST", "/api/growth/apply", {"id": "aa000001"})
        check("aksiyon uygula: etiket degisir", isinstance(ap1, dict) and ap1.get("ok"), str(ap1))
        c, ap2 = http("POST", "/api/growth/apply", {"id": "aa000002"})
        check("aksiyon uygula: deney baslar", isinstance(ap2, dict) and ap2.get("ok"), str(ap2))
        c, ap3 = http("POST", "/api/growth/apply", {"id": "aa000003"})
        check("aksiyon uygula: taslak olusur", isinstance(ap3, dict) and ap3.get("ok"), str(ap3))
        c, ap1b = http("POST", "/api/growth/apply", {"id": "aa000001"})
        check("ayni aksiyon ikinci kez uygulanamaz", isinstance(ap1b, dict) and ap1b.get("ok") is False)
        http("POST", "/api/growth/dismiss", {"id": "aa000004"})
        c, gs3 = http("GET", "/api/growth/state")
        check("aksiyonlar islenince kuyruktan cikar", isinstance(gs3, dict) and gs3["actions"] == [], str(gs3.get("actions"))[:100])
        check("deney listede ve olgunlasmadigi icin 'toplaniyor'", isinstance(gs3, dict) and any(e["name"] == "Test deney" and "toplaniyor" in e["verdict"] for e in gs3["experiments"]), str(gs3.get("experiments"))[:200])
        d0 = next((d for d in gs3.get("drafts", []) if d["title"] == "Test Draft Title"), None)
        check("taslak listede", d0 is not None)
        # yayin korumalari (gercek yayin YOK)
        c, pb1 = http("POST", "/api/growth/publish_draft", {"id": d0["id"]})
        check("yayin: confirm olmadan reddedilir", isinstance(pb1, dict) and pb1.get("ok") is False and "onay" in pb1.get("error", "").lower(), str(pb1))
        c, pb2 = http("POST", "/api/growth/publish_draft", {"id": d0["id"], "confirm": True})
        check("yayin: render edilmemis taslak reddedilir", isinstance(pb2, dict) and pb2.get("ok") is False and "render" in pb2.get("error", "").lower(), str(pb2))
        drafts_path = os.path.join(wd, "drafts.json")
        dr = json.load(open(drafts_path, encoding="utf-8"))
        pub_title = next((r["title"] for r in json.load(open(os.path.join(wd, "day_status.json"), encoding="utf-8")) if r.get("youtube")), "x")
        for x in dr:
            if x["id"] == d0["id"]:
                x["video"] = "fake.mp4"; x["title"] = pub_title
        json.dump(dr, open(drafts_path, "w", encoding="utf-8"))
        c, pb3 = http("POST", "/api/growth/publish_draft", {"id": d0["id"], "confirm": True})
        check("yayin: zaten yayinlanmis baslik engellenir (cift yayin korumasi)", isinstance(pb3, dict) and pb3.get("ok") is False and "zaten" in pb3.get("error", ""), str(pb3))
        http("POST", "/api/growth/draft_delete", {"id": d0["id"]})
        for e in gs3["experiments"]:
            http("POST", "/api/growth/exp_delete", {"id": e["id"]})
        c, gs4 = http("GET", "/api/growth/state")
        check("test taslagi ve testi deneyi silinir", isinstance(gs4, dict) and not any(d["id"] == d0["id"] for d in gs4["drafts"]) and not any(e["name"] == "Test deney" for e in gs4["experiments"]))
        check("makine v2: tunel + token yok -> 401 (apply/publish/render)", all(http("POST", pth, {"id": "x", "confirm": True}, headers=tun)[0] == 401 for pth in ("/api/growth/apply", "/api/growth/publish_draft", "/api/growth/render_draft", "/api/growth/actions")))
        if not QUICK:
            c, ga = http("POST", "/api/growth/actions", {}, timeout=300)
            check("aksiyon plani uretimi (AI)", isinstance(ga, dict) and ga.get("ok") and ga.get("added", 0) >= 1, str(ga)[:200])
            c, gs5 = http("GET", "/api/growth/state")
            types = {a["type"] for a in gs5.get("actions", [])}
            check("aksiyonlar gecerli turde", types <= {"experiment", "draft", "retag"} and len(types) >= 1, str(types))
            for a in gs5.get("actions", []):
                http("POST", "/api/growth/dismiss", {"id": a["id"]})

        c, rp0 = http("POST", "/api/growth/render_publish_draft", {"id": "x"})
        check("render+yayin: confirm olmadan reddedilir", isinstance(rp0, dict) and rp0.get("ok") is False and "onay" in rp0.get("error", "").lower(), str(rp0))
        check("render+yayin: tunel + token yok -> 401", http("POST", "/api/growth/render_publish_draft", {"id": "x", "confirm": True}, headers=tun)[0] == 401)

        # ---- Studio Asistani (HTTP) ----
        check("asistan: PIN yok -> 403", http("GET", "/api/agent/poll")[0] == 403)
        check("asistan: acik tunel basligi + PIN + token -> 403", http("GET", f"/api/agent/poll?key={token}", headers=dict(P, **tun))[0] == 403)
        check("asistan: send PIN yok -> 403", http("POST", "/api/agent/send", {"message": "x"})[0] == 403)
        c, ag0 = http("GET", "/api/agent/poll", headers=P)
        check("asistan: PIN ile poll", c == 200 and isinstance(ag0, dict) and ag0.get("ok") and "events" in ag0, str(ag0)[:100])
        c, ag1 = http("POST", "/api/agent/send", {"message": "   "}, headers=P)
        check("asistan: bos mesaj reddi", isinstance(ag1, dict) and ag1.get("ok") is False)
        check("asistan: ayarlar reset/undo/cancel calisir", all(http("POST", pth, {}, headers=P)[1].get("ok") in (True, False) for pth in ("/api/agent/cancel", "/api/agent/undo", "/api/agent/reset")))
        if not QUICK:
            readme_before = open(os.path.join(work, "README.md"), "rb").read()
            c, ag2 = http("POST", "/api/agent/send", {"message": "Sadece README.md dosyasinin ilk 5 satirini read_file ile oku ve tek cumleyle ozetle. HICBIR SEY DEGISTIRME."}, headers=P)
            check("asistan (canli model): mesaj kabul", isinstance(ag2, dict) and ag2.get("ok"), str(ag2))
            evs, last = [], 0
            for _ in range(120):
                time.sleep(2)
                c, pj = http("GET", f"/api/agent/poll?since={last}", headers=P)
                evs += pj.get("events", []); last = pj.get("last", last)
                if not pj.get("running") and any(e["t"] == "done" for e in evs):
                    break
            kinds = [e["t"] for e in evs]
            check("asistan (canli model): arac kullandi + cevap verdi", "tool" in kinds and "text" in kinds and any(e["t"] == "tool" and e["txt"].startswith("read_file") for e in evs), str(kinds)[:200])
            check("asistan (canli model): dosyaya dokunmadi", open(os.path.join(work, "README.md"), "rb").read() == readme_before)
            http("POST", "/api/agent/reset", {}, headers=P)

        # ---- panel yeniden baslatma + otomatik geri alma ----
        p_main = os.path.join(work, "aura_studio.py")
        good = open(p_main, "rb").read()
        c, d = http("POST", "/api/code/save", {"path": "aura_studio.py",
                    "content": st.replace("# ---------------- KOD MODU (", "# ---------------- KOD MODU T (", 1)}, headers=P)
        check("aura_studio.py yedekli kayit", d.get("ok"), str(d)[:200])
        cur = open(p_main, "rb").read().decode("utf-8")
        open(p_main, "wb").write(cur.replace("def main():", "raise RuntimeError('kasitli cokme')\ndef main():", 1).encode("utf-8"))
        c, d = http("POST", "/api/code/restart_panel", {}, headers=P)
        check("restart_panel kabul", d.get("ok"), str(d))
        log = os.path.join(work, "_studio", "_safe_restart_log.txt")
        ok = False
        for _ in range(90):
            time.sleep(1)
            try:
                lt = open(log, encoding="utf-8").read() if os.path.exists(log) else ""
                if "saglikli" in lt.lower() or "Yedekle panel acildi" in lt:
                    if http("GET", "/api/history", timeout=3)[0] == 200:
                        ok = True
                        break
            except Exception:
                pass
        check("cokme sonrasi panel kendini onardi", ok)
        _pm = open(p_main, "rb").read()
        check("bozuk kod geri alindi", b"kasitli cokme" not in _pm, open(log, encoding="utf-8").read() if os.path.exists(log) else "log yok")
        check("safe_restart geri yukleme kaydi",
              os.path.exists(log) and "Geri yuklendi" in open(log, encoding="utf-8").read())
        # ---- PIN kilidi ----
        for i in range(5):
            http("GET", "/api/code/files", headers={"X-Code-Pin": "00000000"})
        c, _ = http("GET", "/api/code/files", headers=P)
        check("5 yanlis PIN -> kilit (dogru PIN de 403)", c == 403, str(c))
        if QUICK:
            skip("kilit sonrasi acilma", "--quick")
        else:
            time.sleep(62)
            c, _ = http("GET", "/api/code/files", headers=P)
            check("60 sn sonra kilit acilir", c == 200, str(c))

    finally:
        try:
            import psutil
            for c in psutil.net_connections("tcp"):
                if c.status == "LISTEN" and c.laddr.port == PORT and c.pid:
                    psutil.Process(c.pid).kill()
        except Exception:
            pass
        try:
            srv.kill()
        except Exception:
            pass
        logf.close()

    # ---------- 4) GERCEK SISTEM (salt-okunur) ----------
    try:
        with urllib.request.urlopen("http://127.0.0.1:8123/health", timeout=8) as r:
            h = json.loads(r.read())
        check("Voice Mesh /health model_loaded", h.get("model_loaded"), str(h)[:150])
    except Exception as e:
        check("Voice Mesh /health", False, repr(e)[:150])
    try:
        ts = subprocess.run([r"C:\Program Files\Tailscale\tailscale.exe", "status"], capture_output=True, text=True, timeout=15)
        check("Tailscale bagli", ts.returncode == 0 and "enerji-elektrik" in ts.stdout, ts.stdout[:150] + ts.stderr[:100])
        ip = subprocess.run([r"C:\Program Files\Tailscale\tailscale.exe", "ip", "-4"], capture_output=True, text=True, timeout=15).stdout.strip()
        try:
            with urllib.request.urlopen(f"http://{ip}:8795/", timeout=6) as r:
                check("panel Tailscale IP'den erisilir (PC'den)", r.status in (200, 401))
        except urllib.error.HTTPError as e:
            check("panel Tailscale IP'den erisilir (PC'den)", e.code == 401)
        except Exception as e:
            check("panel Tailscale IP'den erisilir (PC'den)", False, repr(e)[:150])
    except Exception as e:
        check("Tailscale", False, repr(e)[:150])
    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from google.auth.transport.requests import Request
        creds = Credentials.from_authorized_user_file(os.path.join(ROOT, "_studio", "token.json"))
        if not creds.valid:
            creds.refresh(Request())
        yt = build("youtube", "v3", credentials=creds)
        ch = yt.channels().list(part="id,snippet", mine=True).execute()
        check("YouTube API: kanal AURA (UClYXgzueuL-eMTId2IZ7aNA)",
              ch["items"] and ch["items"][0]["id"] == "UClYXgzueuL-eMTId2IZ7aNA", str(ch)[:150])
    except Exception as e:
        check("YouTube API", False, repr(e)[:200])

    shutil.rmtree(tmp, ignore_errors=True)
    ok = sum(1 for _, s, _ in RES if s is True)
    bad_ = [(n, dt) for n, s, dt in RES if s is False]
    sk = sum(1 for _, s, _ in RES if s is None)
    print(f"\n=== {ok} gecti, {len(bad_)} basarisiz, {sk} atlandi ===")
    for n, dt in bad_:
        print("BASARISIZ:", n, "|", dt[:200])
    return 1 if bad_ else 0


if __name__ == "__main__":
    sys.exit(main())
