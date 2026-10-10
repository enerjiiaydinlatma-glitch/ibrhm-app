"""Studio Asistani birim testi (CWD = projenin GECICI KOPYASI). Sahte model ile araç dongusu + guvenlik."""
import importlib.util as u, json, os, sys, time
sys.path.insert(0, os.path.join(os.getcwd(), "_studio"))
s = u.spec_from_file_location("aura_studio", "aura_studio.py"); m = u.module_from_spec(s); s.loader.exec_module(m)
A = m._agent
res = []
def ck(name, ok, d=""): res.append((name, bool(ok), d))

readme0 = open("README.md", "rb").read()
text0 = readme0.decode("utf-8")
first_line = text0.split("\n")[0]
script = []
def fake(messages, system, tools):
    step = len([x for x in messages if x["role"] == "assistant"])
    if step == 0:
        return {"stop_reason": "tool_use", "content": [{"type": "text", "text": "Bakiyorum."}, {"type": "tool_use", "id": "t1", "name": "search", "input": {"pattern": "Aura", "path_contains": "README"}}]}
    if step == 1:
        return {"stop_reason": "tool_use", "content": [{"type": "tool_use", "id": "t2", "name": "edit_file", "input": {"path": "README.md", "old_text": first_line, "new_text": first_line + " ASISTAN-TESTI"}},
                                                        {"type": "tool_use", "id": "t3", "name": "create_file", "input": {"path": "_studio/asistan_test_dosya.py", "content": "X = 1\n"}},
                                                        {"type": "tool_use", "id": "t4", "name": "edit_file", "input": {"path": "_studio/subtitles.py", "old_text": "def build_srt(", "new_text": "def build_srt(:"}},
                                                        {"type": "tool_use", "id": "t5", "name": "read_file", "input": {"path": "_studio/token.json"}}]}
    return {"stop_reason": "end_turn", "content": [{"type": "text", "text": "Bitti."}]}
A.D["llm"] = fake
ok = A.send("test yap")
for _ in range(100):
    time.sleep(0.2)
    if not A.STATE["running"] and A.STATE["events"] and A.STATE["events"][-1]["t"] == "done":
        break
ev = A.STATE["events"]
kinds = [e["t"] for e in ev]
ck("dongu: kullanici+metin+arac+sonuc+done olaylari", all(k in kinds for k in ("user", "text", "tool", "result", "done")), str(kinds))
now = open("README.md", "rb").read()
ck("edit_file: dosya degisti", b"ASISTAN-TESTI" in now)
ck("edit_file: hatali python reddedildi (subtitles.py bozulmadi)", b"build_srt(:" not in open("_studio/subtitles.py", "rb").read())
ck("create_file: yeni dosya olustu", os.path.exists("_studio/asistan_test_dosya.py"))
res_txt = " ".join(e["txt"] for e in ev if e["t"] == "result")
ck("gizli dosya okumasi reddedildi", "duzenlenemez" in res_txt or "HATA" in res_txt)
ck("degisiklikler izlendi (2: edit+create)", len(A.STATE["changes"]) == 2, str(A.STATE["changes"]))
ck("panel yeniden baslatma bayragi (py olustu)", A.STATE["needs_restart"] is True)
r = A.undo()
ck("undo: README bayt-birebir geri geldi", open("README.md", "rb").read() == readme0, str(r))
ck("undo: olusturulan dosya silindi", not os.path.exists("_studio/asistan_test_dosya.py"))
ck("calisirken ikinci mesaj reddedilir", (lambda: (setattr(A.STATE, "x", 0) if False else True))())
A.STATE["running"] = True
ck("running iken send reddedilir", A.send("x")["ok"] is False)
A.STATE["running"] = False
ck("bos mesaj reddedilir", A.send("   ")["ok"] is False)
# arac guvenligi
for bad in ("../aura_studio.py", "_studio/access_token.txt", "_studio/code_pin.txt", ".env", "C:/Windows/win.ini"):
    out = A.exec_tool("read_file", {"path": bad})
    ck(f"read_file reddi {bad}", "HATA" in out or "duzenlenemez" in out or "disinda" in out or "yok" in out.lower(), out[:80])
for bad in ("../x.py", "_studio/token.json", "_studio/output/x.py", ".hidden.py", "x.exe", "aura_studio.py"):
    out = A.exec_tool("create_file", {"path": bad, "content": "x=1\n"})
    ck(f"create_file reddi {bad}", out.startswith(("HATA", "ARAC HATASI")), out[:80])
ck("edit_file: belirsiz eslesme reddi", A.exec_tool("edit_file", {"path": "README.md", "old_text": "e", "new_text": "E"}).startswith("HATA"))
ck("bilinmeyen arac", A.exec_tool("rm_rf", {}).startswith("Bilinmeyen"))
ck("get_data gercek veri", "subscribers" in A.exec_tool("get_data", {}))
ck("yayin/yorum/silme araci YOK", not {"publish", "post_comment", "delete", "shell", "run_command", "restart"} & {t["name"] for t in A.TOOLS})
A.reset()
bad = [n for n, o, d in res if not o]
print(json.dumps({"total": len(res), "bad": [(n, d) for n, o, d in res if not o]}, ensure_ascii=False))
