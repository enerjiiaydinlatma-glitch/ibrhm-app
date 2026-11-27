"""Studio Asistani yeni araclari: create_draft (on kontrol, yinelenen baslik), list_drafts, note, web_search (anahtarsiz acik hata)."""
import importlib.util as u, json, os, sys, tempfile
sys.path.insert(0, os.path.join(os.getcwd(), "_studio"))
s = u.spec_from_file_location("aura_studio", "aura_studio.py"); m = u.module_from_spec(s); s.loader.exec_module(m)
import growth, agent
res = []
def ck(n, ok, d=""): res.append((n, bool(ok), str(d)[:240]))
store = []
growth.drafts_list = lambda: list(store)
def fake_add(d):
    row = {"id": "t%d" % (len(store) + 1), "status": "taslak", "created": "2026-11-27 10:00", **d}
    store.append(row); return row
growth.draft_add = fake_add
EN = "Who hid inside Derinkuyu? I'm Aura, an AI, in my 3D rebuild, not real footage. Stop one: levels open since 1969. Send this to someone curious. Vote below."
TR = "Derinkuyu'nun icinde kim saklandi? Ben Aura, yapay zekayim; 3B yapimimdayim, gercek goruntu degil. Birinci durak: 1969'dan beri acik katlar. Bunu merakli birine gonder. Asagidan oy ver."
a = {"title": "Inside Test: Who Hid?", "en_script": EN, "tr_script": TR, "description": "Test desc. I'm Aura, an AI; not real footage. #AuraAI", "tags": "AuraAI", "rationale": "test"}
r = agent.exec_tool("create_draft", a)
ck("create_draft: taslak kaydeder, YAYINLANMADI der", "TASLAK KAYDEDILDI" in r and "YAYINLANMADI" in r and len(store) == 1, r)
ck("create_draft: on kontrol sonucu doner", "On kontrol" in r, r)
r2 = agent.exec_tool("create_draft", a)
ck("create_draft: ayni baslik reddedilir", "OLUSTURULMADI" in r2 and len(store) == 1, r2)
r3 = agent.exec_tool("create_draft", {"title": "X"})
ck("create_draft: eksik alan reddedilir", "OLUSTURULMADI" in r3, r3)
b = dict(a, title="Turkce Karakter Testi", en_script="Bu Türkçe bir metin. I'm Aura, an AI.")
r4 = agent.exec_tool("create_draft", b)
ck("create_draft: Turkce karakterli EN script KIRMIZI uyari ile doner (on kontrol)", "KIRMIZI" in r4, r4)
ck("list_drafts: kayitlari listeler", "Inside Test: Who Hid?" in agent.exec_tool("list_drafts", {}))
tmp = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8"); tmp.write("# log\n"); tmp.close()
m.CLAUDE_MD_PATH = tmp.name
rn = agent.exec_tool("note", {"text": "Test   notu\nikinci satir"})
txt = open(tmp.name, encoding="utf-8").read()
ck("note: gunluge tek satir ekler", "eklendi" in rn and "[Studio Asistani] Test notu ikinci satir" in txt, txt[-120:])
ck("note: bos not reddedilir", "HATA" in agent.exec_tool("note", {"text": "  "}))
m._gemini_client = None
rw = agent.exec_tool("web_search", {"query": "cern"})
ck("web_search: Gemini anahtari yoksa ACIK hata (uydurma sonuc yok)", rw.startswith("HATA"), rw)
ck("yeni araclar TOOLS listesinde ve sistem istemi akisi yaziyor", {"web_search", "list_drafts", "create_draft", "note"} <= {t["name"] for t in agent.TOOLS} and "TURKCE ANLAMINI" in agent.SYSTEM)
os.unlink(tmp.name)
bad = [n for n, ok, d in res if not ok]
for n, ok, d in res: print(("OK  " if ok else "FAIL"), n, "" if ok else d)
print(json.dumps({"total": len(res), "bad": bad}))
sys.exit(1 if bad else 0)
