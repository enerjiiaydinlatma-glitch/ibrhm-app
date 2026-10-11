"""'Hype or Real?' serisi birim testi: karar tespiti, preflight kurallari, video katmanlari (ffmpeg varsa), taslak uretimi (Gemini sahte)."""
import importlib.util as u, json, os, shutil, subprocess, sys, tempfile, threading, urllib.request
sys.path.insert(0, os.path.join(os.getcwd(), "_studio"))
res = []
def ck(n, ok, d=""): res.append((n, bool(ok), str(d)[:200]))
import growth, make_video as mv
GOOD = ("OpenAI's revenue is $20 billion lower than reported. Hype or real? Media said about $70 billion annualized. "
        "OpenAI told investors it is nearer $50 billion, the FT reports. One source says the old figure counted partner revenue gross. "
        "Verdict: UNCLEAR. Follow - I cover one real AI story like this every day. Do you trust OpenAI's revenue number now?")
S = mv._sentences(GOOD)
ck("find_verdict: indeks + etiket", mv.find_verdict(S) == (5, "UNCLEAR"), mv.find_verdict(S))
ck("find_verdict: 'My verdict - hype.' de tanir, duz cumleyi tanimaz", mv.find_verdict(["My verdict - hype."]) == (0, "HYPE") and mv.find_verdict(["Hype or real?"]) is None)
ck("seri etiket/karar renkleri tanimli", set(mv.VERDICT_COLORS) == {"REAL", "HYPE", "UNCLEAR"})
def pf(en, title="Hype or Real: X"):
    return growth.preflight(title, en, "", "I'm an AI #AuraAI", [])
def failed(r): return [c["label"] for c in r["checks"] if c["ok"] is False and c["label"].startswith("Seri")]
ck("preflight: dogru seri script'i seri kontrollerinden gecer", failed(pf(GOOD)) == [], failed(pf(GOOD)))
ck("preflight: tek kanit cumlesi reddedilir", any("2 kanit" in x for x in failed(pf("Claim here is big now. Hype or real? The FT reports it. Verdict: HYPE. Follow - I cover one real AI story like this every day. Is the claim big?"))))
ck("preflight: kaynak atfi yoksa reddedilir", any("kaynak atfi" in x for x in failed(pf("Claim here is big now. Hype or real? The number is small. The gap is large. Verdict: HYPE. Follow - I cover one real AI story like this every day. Is the claim big?"))))
ck("preflight: karar cumlesi yoksa (seri basligi ile) reddedilir", bool(failed(pf("Claim here is big now. Hype or real? The FT reports it. Said so. Follow - I cover one real AI story like this every day. Is the claim big?"))))
ck("preflight: seri disi video seri kontrolu almaz", failed(growth.preflight("Plain Title", "OpenAI did a thing. It matters. Do you care?", "", "I'm an AI", [])) == [])
ck("auto_format: 'Hype or Real:' -> verdict, digerleri bozulmaz", growth.auto_format("Hype or Real: OpenAI's $50B") == "verdict" and growth.auto_format("OpenAI Tests ChatGPT Image Ads") == "agenda")

ck("preflight: 'Hype or Real:' oneki konu cakismasi sayilmaz, ayni konu hala yakalanir",
   all(c["ok"] is not False for c in growth.preflight("Hype or Real: ChatGPT Text", GOOD, "", "I'm an AI #AuraAI", ["Hype or Real: OpenAI's $50B"])["checks"] if "ayni konu" in c["label"] or "cakismiyor" in c["label"])
   and any(c["ok"] is False for c in growth.preflight("Hype or Real: OpenAI's $50B", GOOD, "", "I'm an AI #AuraAI", ["Hype or Real: OpenAI's $50B"])["checks"] if "ayni konu" in c["label"]))

# --- video katmanlari (gercek ffmpeg)
if shutil.which("ffmpeg"):
    tmp = tempfile.mkdtemp()
    wav = os.path.join(tmp, "t.wav")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=220:duration=20", "-ar", "44100", wav], check=True)
    try:
        mv.make_video(wav, os.path.join(tmp, "s.mp4"), GOOD, work_dir=os.path.join(tmp, "w1"))
        mv.make_video(wav, os.path.join(tmp, "p.mp4"), "OpenAI did a thing. It matters. Do you care?", work_dir=os.path.join(tmp, "w2"))
        stamp = open(os.path.join(tmp, "w1", "series_stamp.srt"), encoding="utf-8").read()
        ck("render: seri videosunda karar damgasi + etiket dosyalari var", "UNCLEAR" in stamp and os.path.exists(os.path.join(tmp, "w1", "series_label.srt")), stamp)
        ck("render: normal videoda seri katmani YOK", not os.path.exists(os.path.join(tmp, "w2", "series_stamp.srt")))
        d = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", os.path.join(tmp, "s.mp4")], capture_output=True, text=True).stdout)
        ck("render: video suresi sesle ayni (20 sn)", abs(d - 20) < 0.3, d)
    except Exception as e:
        ck("render: ffmpeg ile seri videosu uretildi", False, repr(e)[-200:])
else:
    ck("render testi atlandi (ffmpeg yok)", True)

# --- taslak uretimi: sahte Gemini, gercek HTTP
s_ = u.spec_from_file_location("aura_studio", "aura_studio.py"); m = u.module_from_spec(s_); s_.loader.exec_module(m)
import insights
tmpd = tempfile.mkdtemp()
growth.DRAFT_FILE = os.path.join(tmpd, "drafts.json")
insights.channel_stats = lambda force=False: {"videos": [{"title": "Old", "views": 5, "likes": 0, "comments": 0, "privacy": "public", "id": "o", "published": "2026-10-01 10:00"}], "subscribers": 2, "total_views": 5, "video_count": 1}
seen = {}
def fake_grounded(prompt, system, timeout=60):
    seen["prompt"], seen["system"] = prompt, system
    return json.dumps({"title": "Hype or Real: OpenAI's $50B", "en_script": GOOD, "tr_script": "A. B. C. D. E. F. G. H.", "description": "I'm an AI. #AuraAI #HypeOrReal",
                       "tags": "AuraAI", "rationale": "x", "sources_used": "y", "verdict": "UNCLEAR"}), [{"uri": "https://x"}]
m._call_gemini_grounded = fake_grounded
from http.server import ThreadingHTTPServer
srv = ThreadingHTTPServer(("127.0.0.1", 0), m.Handler); port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
def post(body):
    req = urllib.request.Request(f"http://127.0.0.1:{port}/api/growth/agenda_candidate", method="POST", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=30).read().decode())
j = post({"topic": "OpenAI revenue gap", "series": "hype_or_real"})
ck("HTTP: series=hype_or_real -> VERDICT prompt + format 'verdict' + konu istege giriyor", j.get("ok") and j["draft"]["format"] == "verdict" and seen["system"] == m.VERDICT_CANDIDATE_SYSTEM and "OpenAI revenue gap" in seen["prompt"], str(j)[:160])
ck("HTTP: taslagin preflight'i seri kurallarini calistirir", any(c["label"].startswith("Seri") for c in j["draft"]["preflight"]["checks"]))
j2 = post({})
ck("HTTP: series yoksa eski gundem akisi (agenda) aynen", j2.get("ok") and j2["draft"]["format"] == "agenda" and seen["system"] == m.AGENDA_CANDIDATE_SYSTEM, str(j2)[:160])
ck("VERDICT prompt: yapi + 'when in doubt choose UNCLEAR' + uydurma yasagi + Follow cumlesi", all(x in m.VERDICT_CANDIDATE_SYSTEM for x in ("choose UNCLEAR", "Never invent", "Follow - I cover one real AI story")))
srv.shutdown()
print(json.dumps({"total": len(res), "bad": [(n, d) for n, o, d in res if not o]}, ensure_ascii=False))
