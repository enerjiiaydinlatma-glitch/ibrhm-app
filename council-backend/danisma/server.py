"""
Danisma Odasi - yerel web sunucusu. SADECE 127.0.0.1'e baglanir.

Calistirma (council-backend klasorunden):
    python -m uvicorn danisma.server:app --host 127.0.0.1 --port 8765
Sonra tarayicida http://127.0.0.1:8765
"""
import asyncio
import json
import os

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import room

app = FastAPI(title="Danisma Odasi")
STATIC = os.path.join(os.path.dirname(__file__), "static")
_sessions = {}  # id -> session (bellekte; her adimda diske de yazilir)


class MemberIn(BaseModel):
    id: str
    provider: str
    role: str


class AskIn(BaseModel):
    question: str
    context_paths: list[str] = ["docs/AURA_ANA_YUZ.md"]
    members: list[MemberIn]


class TextIn(BaseModel):
    text: str


class FollowIn(BaseModel):
    text: str
    members: list[str] | None = None  # bos = hepsi


def _members_of(s):
    return s["members"]


def _load(sid):
    s = _sessions.get(sid)
    if s is None:
        path = os.path.join(room.SESSIONS_DIR, sid + ".json")
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                s = _sessions[sid] = json.load(f)
    if s is None:
        raise HTTPException(404, "oturum yok")
    return s


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC, "index.html"))


@app.get("/api/members")
async def members():
    """Her saglayici anahtarini kucuk istekle SINAR; calismayan uye olmaz."""
    results = await asyncio.to_thread(room.probe_all)
    for i, r in enumerate(results):
        r["role"] = room.DEFAULT_ROLES[i % len(room.DEFAULT_ROLES)]
    return results


@app.post("/api/session")
async def start(body: AskIn):
    if not body.question.strip():
        raise HTTPException(400, "soru bos")
    if not body.members:
        raise HTTPException(400, "en az bir uye sec")
    for m in body.members:
        if m.provider not in room.PROVIDERS:
            raise HTTPException(400, f"bilinmeyen saglayici: {m.provider}")
    members = [{"id": m.id, "provider": m.provider, "role": m.role,
                "label": room.PROVIDERS[m.provider][0]} for m in body.members]
    context = room.load_context(body.context_paths)
    sid = room.new_session_id()
    answers = await asyncio.to_thread(room.blind_round, members, body.question, context)
    s = {"id": sid, "question": body.question, "context_paths": body.context_paths,
         "members": members, "claude": None,
         "rounds": [{"title": "Kor tur", "answers": answers}]}
    _sessions[sid] = s
    room.save_session(s)
    return s


@app.post("/api/session/{sid}/claude")
def claude_answer(sid: str, body: TextIn):
    """Claude'un (oturumdaki asistanin) KOR TUR cevabi elle eklenir; capraz
    elestiri turunda diger uyelere ayri uye olarak gosterilir."""
    s = _load(sid)
    s["claude"] = body.text.strip()
    room.save_session(s)
    return {"ok": True}


def _digest_with_claude(s, answers):
    base = room._digest(answers)
    if s.get("claude"):
        base += f"\n\n--- Claude (oturum asistani) ---\nCevap: {s['claude']}"
    return base


@app.post("/api/session/{sid}/critique")
async def critique(sid: str):
    s = _load(sid)
    members = _members_of(s)
    context = room.load_context(s["context_paths"])
    blind = s["rounds"][0]["answers"]
    ok_members = [m for m in members
                  if any(a["member"] == m["id"] and a.get("ok") for a in blind)]
    if not ok_members:
        raise HTTPException(400, "kor turda cevap veren uye yok")
    # Claude cevabini diger uyelere gostermek icin sahte bir "uye" olarak ekle
    answers = list(blind)
    if s.get("claude"):
        answers.append({"member": "claude", "label": "Claude", "role": "Oturum asistani",
                        "ok": True, "data": {"cevap": s["claude"], "iddialar": [],
                                             "oneriler": []}})
    res = await asyncio.to_thread(room.critique_round, ok_members, s["question"],
                                  context, answers)
    s["rounds"].append({"title": "Capraz elestiri", "answers": res})
    room.save_session(s)
    return s


@app.post("/api/session/{sid}/followup")
async def followup(sid: str, body: FollowIn):
    s = _load(sid)
    members = _members_of(s)
    if body.members:
        members = [m for m in members if m["id"] in body.members]
    if not members:
        raise HTTPException(400, "uye bulunamadi")
    context = room.load_context(s["context_paths"])
    history = "\n\n".join(
        f"[{r['title']}]\n{room._digest(r['answers'])}" for r in s["rounds"])
    res = await asyncio.to_thread(room.followup_round, members, s["question"],
                                  context, history, body.text)
    s["rounds"].append({"title": f"Takip: {body.text[:60]}", "answers": res})
    room.save_session(s)
    return s


@app.get("/api/sessions")
def sessions():
    if not os.path.isdir(room.SESSIONS_DIR):
        return []
    ids = sorted((f[:-5] for f in os.listdir(room.SESSIONS_DIR)
                  if f.endswith(".json")), reverse=True)
    return ids[:50]


@app.get("/api/session/{sid}")
def get_session(sid: str):
    return _load(sid)
