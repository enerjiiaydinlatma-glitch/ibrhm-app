"""TikTok senkron esleme: birebir aciklama + baslik-anahtar-kelime (fuzzy) yedegi; tek kaynak aciklama (tiktok_description)."""
import json, os, sys
sys.path.insert(0, os.path.join(os.getcwd(), "_studio"))
import insights, growth
res = []
def ck(n, ok, d=""): res.append((n, bool(ok), str(d)[:240]))
rows = [(f"y{i}", t, insights._title_tokens(t)) for i, t in enumerate([
    "Inside Derinkuyu: 2 Stops", "Inside Derinkuyu: Who Hid Here?", "Inside CERN: 2 Stops", "Inside Lake Vostok: 2 Stops",
    "Inside the Great Pyramid: 3 Stops", "Great Pyramid: How Did It Go Up?", "Robot Store Shift: 4 of 6 Passed", "Inside Easter Island: 2 Stops", "Easter Island: How Did They Move?"])]
cap = {
 "derinkuyu2": "Inside Derinkuyu: come with me to 2 stops in Cappadocia's underground city. Round stone doors... #Derinkuyu",
 "who": "Derinkuyu underground city: who hid inside? Levels open to visitors since 1969... Reply with one word.",
 "cern": "Inside CERN: magnets colder than outer space, the 2012 discovery of a Higgs-like particle...",
 "vostok": "Lake Vostok: come with me under almost four kilometers of Antarctic ice...",
 "pyr": "Inside the Great Pyramid: come with me to 3 stops. The Grand Gallery, the King's Chamber...",
 "robot": "Six humanoid robots worked a Shanghai convenience store for 24 hours. The company reports 1,730 tasks; four robots passed the final test, two fell short. No independent check yet. Real progress, or marketing? Vote below. I'm Aura, an AI. #Robots #Humanoid #AgiBot",
 "easter": "Moai statue in Easter Island: come inside the quarry where the statues were carved from volcanic ash...",
}
def m(c):
    r = insights._fuzzy_match(c, rows, set()); return r[1] if r else None
ck("Derinkuyu '2 stops' -> dogru video", m(cap["derinkuyu2"]) == "Inside Derinkuyu: 2 Stops", m(cap["derinkuyu2"]))
ck("Derinkuyu 'who hid' -> daha spesifik baslik", m(cap["who"]) == "Inside Derinkuyu: Who Hid Here?", m(cap["who"]))
ck("CERN", m(cap["cern"]) == "Inside CERN: 2 Stops", m(cap["cern"]))
ck("Vostok ('Lake Vostok:' ile baslayan aciklama)", m(cap["vostok"]) == "Inside Lake Vostok: 2 Stops", m(cap["vostok"]))
ck("Buyuk Piramit: 'Inside' ile baslayan aciklama -> Tour videosu (eski video degil)", m(cap["pyr"]) == "Inside the Great Pyramid: 3 Stops", m(cap["pyr"]))
ck("Easter Island ('Moai statue...') -> Tour videosu", m(cap["easter"]) == "Inside Easter Island: 2 Stops", m(cap["easter"]))
ck("Robot haberi: 'robots' (cogul) basliktaki 'Robot' ile eslesir (2026-11-27 canli veride bos kalmisti)", m(cap["robot"]) == "Robot Store Shift: 4 of 6 Passed", m(cap["robot"]))
ck("alakasiz aciklama eslesmez", m("Best pasta recipe tonight #food") is None)
used = set(); a = insights._fuzzy_match(cap["cern"], rows, used); used.add(a[0]); b = insights._fuzzy_match(cap["cern"], rows, used)
ck("bir YouTube videosu bir senkronda iki kez kullanilmaz", a and b is None, (a, b))
d = growth.draft_add.__code__.co_consts
ck("draft_add tiktok_description alanini tasir", "tiktok_description" in d, "")
ck("agent create_draft semasinda tiktok_description var", any("tiktok_description" in json.dumps(t) for t in __import__("agent").TOOLS))
bad = [n for n, ok, d in res if not ok]
for n, ok, d in res: print(("OK  " if ok else "FAIL"), n, "" if ok else d)
print(json.dumps({"total": len(res), "bad": bad}))
sys.exit(1 if bad else 0)
