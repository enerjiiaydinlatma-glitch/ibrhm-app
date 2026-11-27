"""Konsey: 5 saglayici paralel DANISMAN; hata izolasyonu; redteam VERDICT; trend modunda yalniz Gemini arar; sert kurallar istemde; endpoint PIN'siz 403."""
import importlib.util as u, json, os, sys, threading, time, urllib.request
sys.path.insert(0, os.path.join(os.getcwd(), "_studio"))
s = u.spec_from_file_location("aura_studio", "aura_studio.py"); m = u.module_from_spec(s); s.loader.exec_module(m)
res = []
def ck(n, ok, d=""): res.append((n, bool(ok), str(d)[:240]))
seen = {}
def mk(name, text, delay=0.0, boom=False):
    def fn(messages, system, timeout=45):
        seen[name] = (messages, system)
        time.sleep(delay)
        if boom: raise RuntimeError("kota doldu")
        return text
    return fn
m.COUNCIL_MEMBERS = [("Gemini", lambda: True, mk("Gemini", "VERDICT: FIX\n- kaynak yok", 0.2)), ("Anthropic", lambda: True, mk("Anthropic", "VERDICT: OK\nsorun yok", 0.2)),
                     ("OpenAI", lambda: True, mk("OpenAI", "x", boom=True)), ("Grok", lambda: False, mk("Grok", "yok")), ("Groq", lambda: True, mk("Groq", "VERDICT: BLOCK\nsahte baslik", 0.2))]
m._ai_usage_add = lambda *a, **k: None
t0 = time.time()
r = m._council_run("redteam", "", "TITLE: T\nEN: Test.")
dt = time.time() - t0
ck("anahtari olmayan uye (Grok) atlanir, 4 yanit", r["ok"] and [a["name"] for a in r["answers"]] == ["Gemini", "Anthropic", "OpenAI", "Groq"], [a["name"] for a in r.get("answers", [])])
ck("uyeler PARALEL (0.2 sn gecikmeli 3 uye <0.6 sn)", dt < 0.6, dt)
ck("bir uyenin hatasi digerlerini bozmaz, hata gorunur", next(a for a in r["answers"] if a["name"] == "OpenAI")["error"] and r["answers"][0]["text"], r["answers"][2])
vd = {a["name"]: a["verdict"] for a in r["answers"]}
ck("redteam VERDICT ayristirilir (FIX/OK/BLOCK)", vd["Gemini"] == "FIX" and vd["Anthropic"] == "OK" and vd["Groq"] == "BLOCK" and vd["OpenAI"] is None, vd)
sysm = seen["Gemini"][1]
ck("istemde SERT KURALLAR ve danisman rolu var", "never invent facts" in sysm and "ADVISOR" in sysm and "not negotiable" in sysm)
ck("not: konsey hakem degil", "danismandir" in r["note"])
ck("gecersiz mod reddedilir", not m._council_run("vote", "x")["ok"])
ck("fikir modunda bos soru reddedilir", not m._council_run("ideas", "")["ok"])
calls = []
m._call_gemini_grounded = lambda q, sys_, timeout=60: (calls.append(q) or ("1) Story A (2026-11-20)", [{"title": "Src", "uri": "https://x.example"}]))
r2 = m._council_run("react", "science news")
ck("trend modu: kaynakli arama yapilir, kaynak doner", r2["ok"] and calls and r2["sources"][0]["uri"] == "https://x.example", r2)
ck("trend modu: diger uyelere KAYNAKLI liste gider (kendileri arama yapmaz)", "SOURCED TREND LIST" in seen["Anthropic"][0][0]["content"] and "Story A" in seen["Anthropic"][0][0]["content"])
def bad(q, s_, timeout=60): raise RuntimeError("anahtar yok")
m._call_gemini_grounded = bad
r3 = m._council_run("react", "x")
ck("trend aramasi basarisizsa UYDURMA YOK: acik hata", not r3["ok"] and "yapilamadi" in r3["error"], r3)
ag = m._agent_council("ideas", "bir fikir")
ck("agent araci: tum yanitlari ve notu tek metinde doner", "[Gemini" in ag and "danismandir" in ag, ag[:120])
from http.server import ThreadingHTTPServer
srv = ThreadingHTTPServer(("127.0.0.1", 0), m.Handler); port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
req = urllib.request.Request(f"http://127.0.0.1:{port}/api/council", method="POST", data=json.dumps({"mode": "ideas", "question": "x"}).encode(), headers={"Content-Type": "application/json"})
try: code = urllib.request.urlopen(req, timeout=20).status
except urllib.error.HTTPError as e: code = e.code
ck("HTTP POST /api/council: PIN'siz 403 (404 degil: yol tanimli)", code == 403, code)
import agent
ck("agent TOOLS'ta council var", "council" in {t["name"] for t in agent.TOOLS})
bad_ = [n for n, ok, d in res if not ok]
for n, ok, d in res: print(("OK  " if ok else "FAIL"), n, "" if ok else d)
print(json.dumps({"total": len(res), "bad": bad_}))
sys.exit(1 if bad_ else 0)
