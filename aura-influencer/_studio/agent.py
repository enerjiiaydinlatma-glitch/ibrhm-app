"""Studio Asistani: panelin icinde, Claude Code gibi konusarak dosya okuyan/arayan/duzenleyen/test calistiran ajan.

GUVENLIK MODELI (asistan gercek araclara sahip oldugu icin katidir):
- Sadece PC'den veya Tailscale'den + PIN ile erisilir (aura_studio._code_allowed); acik tunelden ASLA.
- Dosya araclari aura_studio'nun kod modu kurallarini kullanir: sadece proje klasoru, izinli uzantilar, gizli dosyalar
  (token/client_secret/.env/PIN) YASAK, her yazimda otomatik yedek + derleme/import kontrolu.
- Keyfi shell YOK. Sadece: dosya listele/oku/ara/duzenle/olustur, test paketini calistir, kanal verisini oku.
- YouTube'a yayin, yorum gonderme, TikTok, silme araclari YOK: bunlar insan onayli panel dugmeleri olarak kalir.
- Yeniden baslatma asistan tarafindan yapilmaz; arayuz "Paneli yeniden baslat" dugmesi gosterir (insan tiklar).
"""
import json
import os
import re
import subprocess
import sys
import threading
import time

D = {}          # aura_studio'nun verdigi bagimliliklar (configure)
LOCK = threading.Lock()
TEST_LOCK = threading.Lock()
STATE = {"messages": [], "events": [], "running": False, "cancel": False, "changes": [], "needs_restart": False, "turns": 0}
MAX_ROUNDS = 16
MAX_RESULT_CHARS = 12000


def configure(**kw):
    D.update(kw)
    _load()


def _sess_file():
    return os.path.join(D["studio_dir"], "agent_session.json")


def _load():
    try:
        s = json.load(open(_sess_file(), encoding="utf-8"))
        STATE["messages"] = s.get("messages", [])
        STATE["events"] = s.get("events", [])
        STATE["changes"] = s.get("changes", [])
        STATE["needs_restart"] = s.get("needs_restart", False)
    except Exception:
        pass


def _save():
    try:
        ev = STATE["events"][-400:]
        json.dump({"messages": STATE["messages"][-60:], "events": ev, "changes": STATE["changes"],
                   "needs_restart": STATE["needs_restart"]}, open(_sess_file(), "w", encoding="utf-8"), ensure_ascii=False)
    except Exception:
        pass


def emit(kind, txt, **extra):
    ev = {"i": (STATE["events"][-1]["i"] + 1) if STATE["events"] else 1, "t": kind, "txt": txt, "ts": time.strftime("%H:%M:%S")}
    ev.update(extra)
    STATE["events"].append(ev)
    return ev


SYSTEM = """Sen "Studio Asistani"sin: Aura Influencer Studio panelinin (aura_studio.py + _studio/*.py) icinde calisan, operatorle Turkce konusan bir yazilim ve buyume asistanisin.
Operator seninle Claude Code ile konusur gibi konusur; sen dosyalari okur, aratir, DUZENLER, test calistirir ve kanal verisine bakarak yardim edersin.

ARACLAR: list_files, read_file, search, edit_file, create_file, run_tests, get_data. Baska arac YOK: yayin, yorum gonderme, silme, TikTok, kabuk komutu sende yok
(bunlar insan onayli panel dugmeleri). Yapamadigin bir seyi yaptigini ASLA soyleme; sadece araclarin gercekten dondurdugu sonuclari rapor et.

CALISMA KURALLARI
- Duzenlemeden once ilgili kismi read_file/search ile OKU. edit_file tam ve benzersiz eslesme ister; kucuk, hedefli degisiklik yap.
- Python dosyasini degistirdikten sonra (basit metin/dokuman degilse) run_tests ile dogrula (quick=true). Basarisizsa dur, sebebi acikla, duzelt; asla "gecti" deme eger gecmediyse.
- Degisiklikler otomatik yedeklenir; operator "geri al" diyebilir. Panel kodu degistiyse operatore "Paneli yeniden baslat" gerektigini soyle (sen baslatamazsin).
- Cevaplar kisa, net, Turkce. Kod parcalarini uzun uzun yapistirma; ne degistirdigini 2-5 maddeyle ozetle.
- Buyume/strateji sorularinda get_data ile GERCEK sayilari al; veride olmayan metrik uydurma (CTR, gelir...). Orneklem cok kucuk: sonuclari hipotez olarak sun.

PROJE KURALLARI (asla esnetme)
- Aura HER ZAMAN acikca yapay zeka oldugunu soyler; cinsel icerik yok; sahte metrik/alinti/aciliyet uydurma yok; ana Aura uygulamasi kapali beta.
- Disari giden icerik Ingilizce; Turkce sadece operatorle konusma ve TR altyazi.
- Gizli dosyalara (token, client_secret, .env, PIN) dokunma/ acma.

TEKNIK TUZAKLAR
- aura_studio.py'de web arayuzu (PAGE) NORMAL (raw olmayan) uc-tirnakli Python stringidir: PAGE icinde ters egik cizgi kullanma; JS icinde satir sonu icin String.fromCharCode(10),
  tek tirnak yerine cift tirnak/HTML varligi kullan (aksi halde Python kacis dizisi JS'i bozar). Degisiklikten sonra run_tests bunu yakalar (JS sozdizimi testi).
- .bat dosyalari CRLF olmali (sistem otomatik yapar). Windows'tasin.
- Buyuk dosya (aura_studio.py ~3000 satir): once search ile yeri bul, sonra read_file ile ilgili satir araligini oku.
"""

TOOLS = [
    {"name": "list_files", "description": "Duzenlenebilir proje dosyalarini listele (boyutlariyla).",
     "input_schema": {"type": "object", "properties": {}}},
    {"name": "read_file", "description": "Bir proje dosyasini satir numaralariyla oku (en fazla 250 satir/istek).",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "start_line": {"type": "integer"}, "end_line": {"type": "integer"}},
                      "required": ["path"]}},
    {"name": "search", "description": "Proje dosyalarinda regex ara (en fazla 40 eslesme). path_contains ile dosya adini daralt.",
     "input_schema": {"type": "object", "properties": {"pattern": {"type": "string"}, "path_contains": {"type": "string"}},
                      "required": ["pattern"]}},
    {"name": "edit_file", "description": "Mevcut dosyada old_text -> new_text degistir. old_text dosyada TAM 1 kez gecmeli. Otomatik yedek + sozdizimi/import kontrolu; hatali ise yazilmaz.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}},
                      "required": ["path", "old_text", "new_text"]}},
    {"name": "create_file", "description": "Yeni dosya olustur (var olani EZMEZ). Sadece izinli uzantilar (.py .md .txt .json .html .js .css .bat) ve proje klasoru.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
    {"name": "run_tests", "description": "Test paketini calistir (izole kopyada, gercek dosyalara dokunmaz). quick=true ~2 dk, yavas canli AI testlerini atlar.",
     "input_schema": {"type": "object", "properties": {"quick": {"type": "boolean"}}}},
    {"name": "get_data", "description": "Kanalin GERCEK verisini oku: YouTube sayilari, tutma, format tablosu, TikTok (elle girilen). Salt okunur.",
     "input_schema": {"type": "object", "properties": {}}},
]


# ------------------------------------------------------------------ araclar
def _clip(s, n=MAX_RESULT_CHARS):
    s = str(s)
    return s if len(s) <= n else s[:n] + f"\n...[kirpildi, toplam {len(s)} karakter]"


def t_list_files(_a):
    root = os.path.realpath(D["here"])
    rows = []
    for rel in D["code_list"]()[:300]:
        try:
            rows.append(f"{rel}  ({os.path.getsize(os.path.join(root, rel))} B)")
        except Exception:
            rows.append(rel)
    return "\n".join(rows)


def t_read_file(a):
    _full, text, _crlf = D["code_read"](a.get("path", ""))
    lines = text.split("\n")
    s = max(1, int(a.get("start_line") or 1))
    e = min(len(lines), int(a.get("end_line") or (s + 199)), s + 249)
    out = [f"{i:>5}| {lines[i - 1]}" for i in range(s, e + 1)]
    return f"# {a.get('path')}  satir {s}-{e} / {len(lines)}\n" + "\n".join(out)


def t_search(a):
    try:
        rx = re.compile(a.get("pattern", ""))
    except re.error as ex:
        return f"Gecersiz regex: {ex}"
    sub = (a.get("path_contains") or "").lower()
    root = os.path.realpath(D["here"])
    hits = []
    for rel in D["code_list"]():
        if sub and sub not in rel.lower():
            continue
        try:
            text = open(os.path.join(root, rel), encoding="utf-8", errors="replace").read()
        except Exception:
            continue
        for i, ln in enumerate(text.split("\n"), 1):
            if rx.search(ln):
                hits.append(f"{rel}:{i}: {ln.strip()[:160]}")
                if len(hits) >= 40:
                    return "\n".join(hits) + "\n(40 eslesmede kesildi)"
    return "\n".join(hits) or "Eslesme yok."


def _track(rel, res):
    if res.get("ok"):
        STATE["changes"].append({"rel": rel, "backup": res.get("backup")})
        if rel.endswith(".py"):
            STATE["needs_restart"] = True


def t_edit_file(a):
    rel = a.get("path", "")
    _full, text, _crlf = D["code_read"](rel)
    old, new = a.get("old_text", ""), a.get("new_text", "")
    if not old.strip():
        return "HATA: old_text bos."
    n = text.count(old)
    if n != 1:
        return f"HATA: old_text dosyada {n} kez bulundu (tam 1 olmali). Daha fazla baglam ekleyip tekrar dene."
    if old == new:
        return "HATA: degisiklik yok."
    res = D["code_write"](rel, text.replace(old, new, 1))
    _track(rel, res)
    return "OK: yazildi, yedek: " + str(res.get("backup")) if res.get("ok") else "YAZILMADI: " + str(res.get("error"))


def t_create_file(a):
    rel = (a.get("path") or "").replace("\\", "/").lstrip("/")
    root = os.path.realpath(D["here"])
    full = os.path.realpath(os.path.join(root, rel))
    ext = os.path.splitext(full)[1].lower()
    if not full.startswith(root + os.sep):
        return "HATA: yol proje disinda."
    if ext not in {".py", ".md", ".txt", ".json", ".html", ".js", ".css", ".bat"}:
        return "HATA: bu uzanti olusturulamaz."
    parts = rel.split("/")
    if any(p in D["skip_dirs"] for p in parts[:-1]) or os.path.basename(full) in D["deny_names"] or parts[-1].startswith("."):
        return "HATA: bu konumda/adla dosya olusturulamaz."
    if os.path.exists(full):
        return "HATA: dosya zaten var (edit_file kullan)."
    content = str(a.get("content", "")).replace("\r\n", "\n")
    err = D["code_check"](full, content)
    if err:
        return "OLUSTURULMADI: " + err
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8", newline="") as f:
        f.write(content.replace("\n", "\r\n") if ext == ".bat" else content)
    STATE["changes"].append({"rel": rel, "created": True})
    if ext == ".py":
        STATE["needs_restart"] = True
    return "OK: olusturuldu " + rel


def t_run_tests(a):
    if not TEST_LOCK.acquire(blocking=False):
        return "Baska bir test suruyor, bekle."
    try:
        script = os.path.join(D["here"], "_tests", "run_tests.py")
        if not os.path.exists(script):
            return "HATA: _tests/run_tests.py yok."
        args = [sys.executable, script] + (["--quick"] if a.get("quick", True) else [])
        r = subprocess.run(args, cwd=D["here"], capture_output=True, text=True, timeout=900, encoding="utf-8", errors="replace")
        lines = (r.stdout or "").splitlines()
        bad = [x for x in lines if x.startswith(("FAIL", "BASARISIZ"))]
        tail = [x for x in lines if x.startswith("===")]
        return _clip("\n".join(tail + bad[:25]) or (r.stdout or "")[-2000:] + (r.stderr or "")[-1500:], 5000)
    except subprocess.TimeoutExpired:
        return "HATA: testler zaman asimina ugradi."
    finally:
        TEST_LOCK.release()


def t_get_data(_a):
    return _clip(D["data"](), 9000)


TOOL_FUNCS = {"list_files": t_list_files, "read_file": t_read_file, "search": t_search, "edit_file": t_edit_file,
              "create_file": t_create_file, "run_tests": t_run_tests, "get_data": t_get_data}


def exec_tool(name, args):
    fn = TOOL_FUNCS.get(name)
    if not fn:
        return f"Bilinmeyen arac: {name}"
    try:
        return _clip(fn(args or {}))
    except Exception as e:
        return f"ARAC HATASI ({type(e).__name__}): {str(e)[:400]}"


def summarize_call(name, a):
    a = a or {}
    if name == "read_file":
        return f"{a.get('path')} ({a.get('start_line', 1)}-{a.get('end_line', '')})"
    if name == "search":
        return f"/{a.get('pattern')}/ {a.get('path_contains') or ''}"
    if name in ("edit_file", "create_file"):
        return str(a.get("path"))
    if name == "run_tests":
        return "quick" if a.get("quick", True) else "tam"
    return ""


# ------------------------------------------------------------------ model + dongu
def llm(messages, system, tools):
    """Anthropic Messages API (arac kullanimi). Testte D['llm'] ile degistirilebilir."""
    if D.get("llm"):
        return D["llm"](messages, system, tools)
    import httpx
    body = {"model": os.getenv("COUNCIL_ANTHROPIC_MODEL", "claude-sonnet-5"), "max_tokens": 4096, "system": system,
            "messages": messages, "tools": tools, "thinking": {"type": "disabled"}}
    last = None
    for attempt in range(3):
        try:
            r = httpx.post("https://api.anthropic.com/v1/messages", timeout=180,
                           headers={"x-api-key": D["api_key"](), "anthropic-version": "2023-06-01", "content-type": "application/json"}, json=body)
            if r.status_code in (429, 500, 502, 503, 529):
                last = f"HTTP {r.status_code}"
                time.sleep(3 * (attempt + 1))
                continue
            r.raise_for_status()
            d = r.json()
            try:
                u = d.get("usage", {})
                D["usage_add"]("Anthropic", u.get("input_tokens", 0) * 4, u.get("output_tokens", 0) * 4)
            except Exception:
                pass
            return d
        except Exception as e:
            last = f"{type(e).__name__}: {str(e)[:200]}"
            time.sleep(2)
    raise RuntimeError("Model cagrisi basarisiz: " + str(last))


def _trim(messages):
    total = sum(len(json.dumps(m, ensure_ascii=False)) for m in messages)
    if total < 350000:
        return messages
    out = []
    for idx, m in enumerate(messages):
        if idx < len(messages) - 8 and isinstance(m.get("content"), list):
            blocks = []
            for b in m["content"]:
                if b.get("type") == "tool_result":
                    b = dict(b)
                    b["content"] = "[eski arac sonucu kirpildi]"
                blocks.append(b)
            m = {"role": m["role"], "content": blocks}
        out.append(m)
    return out


def run_turn(text, image_b64=None, image_mime=None):
    with LOCK:
        if STATE["running"]:
            return False
        STATE["running"] = True
        STATE["cancel"] = False
    try:
        STATE["turns"] += 1
        emit("user", text, has_image=bool(image_b64))
        content = []
        if image_b64:
            content.append({"type": "image", "source": {"type": "base64", "media_type": image_mime or "image/png", "data": image_b64}})
        content.append({"type": "text", "text": text})
        STATE["messages"].append({"role": "user", "content": content})
        for _ in range(MAX_ROUNDS):
            if STATE["cancel"]:
                emit("error", "Durduruldu.")
                break
            resp = llm(_trim(STATE["messages"]), SYSTEM, TOOLS)
            blocks = [b for b in resp.get("content", []) if b.get("type") in ("text", "tool_use")]
            STATE["messages"].append({"role": "assistant", "content": blocks or [{"type": "text", "text": "(bos yanit)"}]})
            for b in blocks:
                if b["type"] == "text" and b["text"].strip():
                    emit("text", b["text"])
            uses = [b for b in blocks if b["type"] == "tool_use"]
            if not uses:
                if resp.get("stop_reason") == "max_tokens":
                    emit("error", "Yanit uzunluk sinirinda kesildi; 'devam et' yazabilirsin.")
                break
            results = []
            for tu in uses:
                emit("tool", tu["name"] + " " + summarize_call(tu["name"], tu.get("input")))
                out = exec_tool(tu["name"], tu.get("input"))
                emit("result", _clip(out, 1500), tool=tu["name"], ok=not out.startswith(("HATA", "YAZILMADI", "OLUSTURULMADI", "ARAC HATASI")))
                results.append({"type": "tool_result", "tool_use_id": tu["id"], "content": out})
            STATE["messages"].append({"role": "user", "content": results})
            _save()
        else:
            emit("error", f"{MAX_ROUNDS} tur sinirina ulasildi; 'devam et' yazarak surdurebilirsin.")
    except Exception as e:
        emit("error", f"{type(e).__name__}: {str(e)[:300]}")
        # yarim kalan arac cagrisi mesaj gecmisini bozmasin
        while STATE["messages"] and STATE["messages"][-1]["role"] == "assistant" and any(
                b.get("type") == "tool_use" for b in STATE["messages"][-1].get("content", [])):
            STATE["messages"].pop()
    finally:
        STATE["running"] = False
        emit("done", "")
        _save()
    return True


def send(text, image_b64=None, image_mime=None):
    text = (text or "").strip()
    if not text:
        return {"ok": False, "error": "Bos mesaj."}
    if STATE["running"]:
        return {"ok": False, "error": "Asistan hala calisiyor."}
    threading.Thread(target=run_turn, args=(text, image_b64, image_mime), daemon=True).start()
    return {"ok": True}


def poll(since=0):
    return {"ok": True, "running": STATE["running"], "needs_restart": STATE["needs_restart"], "changes": len(STATE["changes"]),
            "events": [e for e in STATE["events"] if e["i"] > since], "last": STATE["events"][-1]["i"] if STATE["events"] else 0}


def reset():
    if STATE["running"]:
        return {"ok": False, "error": "Calisirken sifirlanamaz."}
    STATE.update({"messages": [], "events": [], "changes": [], "needs_restart": False})
    _save()
    return {"ok": True}


def cancel():
    STATE["cancel"] = True
    return {"ok": True}


def undo():
    if STATE["running"]:
        return {"ok": False, "error": "Calisirken geri alinamaz."}
    done, errs = [], []
    for ch in reversed(STATE["changes"]):
        try:
            if ch.get("created"):
                p = os.path.join(D["here"], ch["rel"])
                if os.path.exists(p):
                    os.remove(p)
                done.append("silindi: " + ch["rel"])
            elif ch.get("backup"):
                res = D["code_restore"](ch["rel"], ch["backup"])
                (done if res.get("ok") else errs).append(("geri yuklendi: " if res.get("ok") else "geri alinamadi: ") + ch["rel"] + ("" if res.get("ok") else " - " + str(res.get("error"))))
        except Exception as e:
            errs.append(f"{ch.get('rel')}: {e}")
    STATE["changes"] = []
    emit("text", "Geri alma: " + ("; ".join(done) or "yapilacak degisiklik yoktu") + ("  HATALAR: " + "; ".join(errs) if errs else ""))
    _save()
    return {"ok": not errs, "done": done, "errors": errs}
