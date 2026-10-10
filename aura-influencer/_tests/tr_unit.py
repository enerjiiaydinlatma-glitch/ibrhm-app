"""Turkce CC garantisi birim testi (CWD = projenin gecici kopyasi; AI cagrisi sahte)."""
import importlib.util as u, json, os, re, sys
sys.path.insert(0, os.path.join(os.getcwd(), "_studio"))
s = u.spec_from_file_location("aura_studio", "aura_studio.py"); m = u.module_from_spec(s); s.loader.exec_module(m)
res = []
def ck(n, ok, d=""): res.append((n, bool(ok), d))
cnt = lambda x: len([y for y in re.split(r"(?<=[.!?])\s+", x.strip()) if y])
en = "You think AI makes you rich. You search for magic prompts. But you lack discipline. Prove me wrong."
calls = []
def fake_ai(messages, system, prefer=None, timeout=45):
    calls.append(1)
    n = cnt(en)
    return json.dumps(["Cumle %d." % i for i in range(1, n + 1)])
m.call_aura = fake_ai
tr, note = m._ensure_tr(en, "")
ck("bos TR -> otomatik cevrilir, cumle sayisi esit", cnt(tr) == cnt(en) and "otomatik" in note and calls, tr)
calls.clear()
good = "Sen yapay zekanin zengin edecegini sanirsin. Sihirli komutlar ararsin. Ama disiplinin yok. Yanildigimi kanitla."
tr2, note2 = m._ensure_tr(en, good)
ck("uyumlu TR aynen korunur (AI cagrilmaz)", tr2 == good and not calls)
bad = "Sen yapay zekanin zengin edecegini sanirsin. Sihirli komutlar ararsin ama disiplinin yok. Yanildigimi kanitla."
tr3, note3 = m._ensure_tr(en, bad)
ck("bir cumle eksik TR hizalanir/cevrilir ve esitlenir", cnt(tr3) == cnt(en), tr3)
def bad_ai(messages, system, prefer=None, timeout=45):
    return json.dumps(["tek"])
m.call_aura = bad_ai
tr4, note4 = m._ensure_tr(en, "")
ck("cevirisi tutmazsa hata notu doner, bos metin dondurur (sessiz yalan yok)", tr4 == "" and "cevrilemedi" in note4, note4)
import tr_restore
pend = os.path.join(m.STUDIO_DIR, "tr_pending.json")
srt = os.path.join(m.OUTPUT_DIR, "x_tr.srt"); open(srt, "w").write("1\n00:00:00,000 --> 00:00:01,000\nMerhaba.\n")
json.dump({"VID_TEST_1": srt}, open(pend, "w"))
try:
    items, missing = tr_restore.plan()
    ck("tr_restore.plan bekleyen kuyrugu icerir", any(i[1] == "VID_TEST_1" for i in items), str(items)[:200])
except Exception as e:
    ck("tr_restore.plan bekleyen kuyrugu icerir", "VID_TEST_1" in str(e) or False, repr(e)[:150])
os.remove(pend)
ck("gizli kural: AURA_SYSTEM yayin dili kurali", "PUBLISHING LANGUAGE RULE" in m.AURA_SYSTEM)
print(json.dumps({"total": len(res), "bad": [(n, d) for n, o, d in res if not o]}, ensure_ascii=False))
