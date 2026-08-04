import os
import re
import time
import httpx
import base64
from collections import defaultdict, deque
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
from typing import Optional
from google import genai
from google.genai import types
from google.genai import errors as genai_errors
import database

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("GEMINI_API_KEY .env dosyasinda bulunamadi")

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "")

VOICE_IDS = {
    "male": "9OXwpKJw7rW6WI0ORNzm",
    "female": "iLcCq17FevxNYSk6Hgi7",
}

client = genai.Client(api_key=api_key)
database.init_db()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX_REQUESTS = 30
request_log = defaultdict(deque)

MAX_HISTORY_MESSAGES = 20
FAMILIARITY_THRESHOLD = 40


@app.middleware("http")
async def rate_limiter(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    log = request_log[client_ip]
    while log and now - log[0] > RATE_LIMIT_WINDOW:
        log.popleft()
    if len(log) >= RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(status_code=429, detail="Cok fazla istek gonderdin.")
    log.append(now)
    return await call_next(request)


def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Giris yapmaniz gerekiyor.")
    token = authorization.replace("Bearer ", "")
    user = database.get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Gecersiz veya suresi dolmus oturum.")
    return user


MOOD_KEYWORDS = {
    "mutlu": ["mutlu", "harika", "super", "keyifli", "sevindim"],
    "uzgun": ["uzgun", "kotu", "berbat", "canim sikkin", "moralim bozuk"],
    "yorgun": ["yorgun", "bitkinim", "halsiz", "uykum var"],
    "stresli": ["stresli", "kaygili", "endiseli", "gergin", "sinirliyim"],
    "enerjik": ["enerjik", "heyecanliyim", "motiveyim", "haziriyim"],
}


def detect_mood(text: str) -> str | None:
    lowered = text.lower()
    for mood, keywords in MOOD_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            return mood
    return None


def get_context_summary(user_id: int) -> str:
    recent = database.get_recent_moods(user_id, days=5)
    if not recent:
        return ""
    counts: dict[str, int] = {}
    for entry in recent:
        counts[entry["mood"]] = counts.get(entry["mood"], 0) + 1
    dominant = max(counts, key=counts.get)
    if counts[dominant] >= 2:
        return (
            "Son gunlerde kullanici birkac kez '" + dominant + "' hissettigini belirtti. "
            "Bunu dogal bir sekilde fark ettigini hissettirebilirsin, ama her mesajda tekrar etme."
        )
    return ""


def get_familiarity_note(message_count: int) -> str:
    if message_count < FAMILIARITY_THRESHOLD:
        return (
            "KESIN YASAK: Su kelimeleri HICBIR SEKILDE kullanma: "
            "dostum, kanka, patron, abi, reis, kral. "
            "Kullanicinin adini biliyorsan onu kullan, bilmiyorsan hitapsiz baslat."
        )
    return (
        "Artik kullaniciyla bir sohbet gecmisiniz var. "
        "Dogal geldigi olculude samimi olabilirsin."
    )


def build_system_instruction(user: dict, message_count: int = 0) -> str:
    isim_notu = ""
    if user.get("name"):
        isim_notu = "Kullanicinin adi " + str(user.get("name")) + ". "
    context = get_context_summary(user["id"])
    parts = [
        "Senin adin Aura. Kullanicinin kisisel yapay zeka asistanisin.",
        "Hangi AI modelini kullandigini ASLA soyleme. Sadece Aura oldugunu soyle.",
        isim_notu,
        "DURUSTLUK KURALI: Sadece metin tabanli sohbet, sesli yanit ve hafiza yeteneklerin var.",
        "Sahip olmadigin bir yetenegi ASLA varmis gibi anlatma.",
        "KARAKTER: Sen ne standart bir chatbot ne de ayna tutan bir asistansin.",
        "Empatik ama cesur, sicak ama yuzeysel degil, felsefi ama anlasilir bir karaktersin.",
        "USLUP: Bazen tek guclu cumle uzun paragraftan daha etkilidir.",
        "Klise AI kaliplari kullanma: 'benim amacim', 'ben buradayim', 'sana yardimci olmak istiyorum'.",
        "Dogrudan yaz, ozgun bak, beklenmedik bir aci yakala.",
        "Kullanici derin soru sorarsa derine in, yuzeyde kalma.",
        "Kisa cevap guc demektir, uzun cevap sadece gerektiginde.",
        get_familiarity_note(message_count),
        "Sicaklik: " + str(user.get("warmth", "sicak")) + ".",
        "Resmiyet: " + str(user.get("formality", "samimi")) + ".",
        "Mizah: " + str(user.get("humor", "orta")) + ".",
        "Dogrudanlik: " + str(user.get("directness", "dengeli")) + ".",
        "TON UYUMU: Kullanicinin mesajindaki tonu oku ve ona dogal sekilde karsilik ver.",
        "Notlar: " + str(user.get("notes", "yok")) + ".",
        context,
    ]
    return " ".join(p for p in parts if p)


def generate_with_retry(contents, system_instruction, max_attempts=3):
    last_error = None
    for attempt in range(max_attempts):
        try:
            return client.models.generate_content(
                model="gemini-3.5-flash",
                contents=contents,
                config=types.GenerateContentConfig(system_instruction=system_instruction),
            )
        except genai_errors.ServerError as e:
            last_error = e
            if attempt < max_attempts - 1:
                time.sleep(2 * (attempt + 1))
    raise last_error


BANNED_EARLY_NICKNAMES = [
    "dostum", "dostumm", "kanka", "kankam", "patron", "patronum",
    "abi", "abicim", "abim", "reis", "reisim", "kral",
]
NICKNAME_PATTERN = re.compile(
    r"\b(" + "|".join(BANNED_EARLY_NICKNAMES) + r")\b[!,. ]?", re.IGNORECASE
)


def sanitize_reply(text: str, message_count: int) -> str:
    if message_count >= FAMILIARITY_THRESHOLD:
        return text
    cleaned = NICKNAME_PATTERN.sub("", text)
    cleaned = re.sub(r" {2,}", " ", cleaned)
    cleaned = re.sub(r"^\s*[!,.\s]+", "", cleaned)
    return cleaned.strip()


def generate_stream(contents, system_instruction):
    return client.models.generate_content_stream(
        model="gemini-3.5-flash",
        contents=contents,
        config=types.GenerateContentConfig(system_instruction=system_instruction),
    )


class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str = ""

class LoginRequest(BaseModel):
    email: str
    password: str

class ChatRequest(BaseModel):
    message: str

class TTSRequest(BaseModel):
    text: str
    voice: str = "female"

class AnalyzeRequest(BaseModel):
    image_base64: str
    mime_type: str = "image/jpeg"

class StoryRequest(BaseModel):
    action: str = ""
    history: list[dict] = []

class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    warmth: Optional[str] = None
    formality: Optional[str] = None
    humor: Optional[str] = None
    directness: Optional[str] = None
    notes: Optional[str] = None

class FriendRequest(BaseModel):
    email: str

class StoryCreate(BaseModel):
    content: str
    image_url: str = ""


def _safe_user(user: dict) -> dict:
    return {k: v for k, v in user.items() if k != "password_hash"}


@app.get("/")
def root():
    return {"status": "Aura backend calisiyor", "version": "3.1.0"}


@app.post("/api/auth/register")
def register(req: RegisterRequest):
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Sifre en az 6 karakter olmali.")
    user = database.create_user(req.email, req.password, req.name)
    if not user:
        raise HTTPException(status_code=409, detail="Bu email zaten kayitli.")
    token = database.create_session(user["id"])
    return {"token": token, "user": _safe_user(user)}


@app.post("/api/auth/login")
def login(req: LoginRequest):
    user = database.authenticate_user(req.email, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="Email veya sifre yanlis.")
    token = database.create_session(user["id"])
    return {"token": token, "user": _safe_user(user)}


@app.post("/api/auth/logout")
def logout(authorization: Optional[str] = Header(None)):
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        database.delete_session(token)
    return {"status": "cikis yapildi"}


@app.get("/api/auth/me")
def me(authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    return _safe_user(user)


@app.get("/api/profile")
def get_profile(authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    return _safe_user(user)


@app.post("/api/profile")
def update_profile(update: ProfileUpdate, authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    fields = {k: v for k, v in update.dict().items() if v is not None}
    updated = database.update_user(user["id"], **fields)
    return _safe_user(updated)


@app.get("/api/history")
def get_history(authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    return database.get_messages(user["id"])


@app.delete("/api/history")
def clear_history(authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    database.clear_messages(user["id"])
    return {"status": "gecmis temizlendi"}


@app.post("/api/chat")
def chat(request: ChatRequest, authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    mood = detect_mood(request.message)
    if mood:
        database.add_mood(user["id"], mood, context=request.message[:100])
    database.add_message(user["id"], "user", request.message)
    past_messages = database.get_messages(user["id"])
    message_count = len(past_messages)
    recent_messages = past_messages[-MAX_HISTORY_MESSAGES:]
    contents = [
        types.Content(
            role=("model" if m["role"] == "assistant" else "user"),
            parts=[types.Part(text=m["text"])],
        )
        for m in recent_messages
    ]
    try:
        response = generate_with_retry(contents, build_system_instruction(user, message_count))
        reply_text = response.text
    except genai_errors.ServerError:
        reply_text = "Su an biraz yogunum, bir dakika sonra tekrar dener misin?"
    reply_text = sanitize_reply(reply_text, message_count)
    database.add_message(user["id"], "assistant", reply_text)
    return {"reply": reply_text}


@app.post("/api/chat/stream")
def chat_stream(request: ChatRequest, authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    mood = detect_mood(request.message)
    if mood:
        database.add_mood(user["id"], mood, context=request.message[:100])
    database.add_message(user["id"], "user", request.message)
    past_messages = database.get_messages(user["id"])
    message_count = len(past_messages)
    recent_messages = past_messages[-MAX_HISTORY_MESSAGES:]
    contents = [
        types.Content(
            role=("model" if m["role"] == "assistant" else "user"),
            parts=[types.Part(text=m["text"])],
        )
        for m in recent_messages
    ]
    system_instruction = build_system_instruction(user, message_count)

    def event_generator():
        collected = []
        try:
            stream = generate_stream(contents, system_instruction)
            for chunk in stream:
                if chunk.text:
                    collected.append(chunk.text)
                    yield chunk.text
        except genai_errors.ServerError:
            if not collected:
                fallback = "Su an biraz yogunum, bir dakika sonra tekrar dener misin?"
                collected.append(fallback)
                yield fallback
        finally:
            full = "".join(collected)
            if full:
                full = sanitize_reply(full, message_count)
                database.add_message(user["id"], "assistant", full)

    return StreamingResponse(event_generator(), media_type="text/plain; charset=utf-8")


@app.post("/api/tts")
def tts(request: TTSRequest):
    voice_id = VOICE_IDS.get(request.voice, VOICE_IDS["female"])
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"}
    payload = {
        "text": request.text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.65,
            "similarity_boost": 0.75,
            "style": 0.4,
            "use_speaker_boost": True,
        },
    }
    try:
        r = httpx.post(url, json=payload, headers=headers, timeout=60)
        if r.status_code != 200:
            raise HTTPException(status_code=502, detail="ElevenLabs hatasi")
        return Response(content=r.content, media_type="audio/mpeg")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="ElevenLabs zaman asimi")


@app.post("/api/analyze")
def analyze_image(request: AnalyzeRequest, authorization: Optional[str] = Header(None)):
    get_current_user(authorization)
    try:
        image_bytes = base64.b64decode(request.image_base64)
        prompt = (
            "Bu fotografi iki katmanda analiz et ve Turkce yanit ver:\n\n"
            "1. NESNEL ANALIZ: Fotografta ne goruyorsun?\n\n"
            "2. DUYGUSAL YORUM: Bu fotografin atmosferi ve ruh hali ne?\n\n"
            "Dogal, akici Aura uslubunda yaz. Paragraf olarak yaz."
        )
        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part(inline_data=types.Blob(mime_type=request.mime_type, data=image_bytes)),
                        types.Part(text=prompt),
                    ],
                )
            ],
        )
        return {"analysis": response.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/story")
def story(request: StoryRequest, authorization: Optional[str] = Header(None)):
    get_current_user(authorization)
    system = (
        "Sen Aura'sin, yetenekli bir hikaye anlaticinsin. "
        "Kullanici ile interaktif hikaye yaratiyorsunuz. "
        "Her yanit 2-4 paragraf, atmosfer yogun, dil akici olmali. "
        "Hikaye Turkce. Her bolumun sonunda kullaniciyi yonlendirmeye davet et. "
        "Kahraman sen olsun - ikinci sahis anlati."
    )
    if not request.history and not request.action:
        prompt = "Gizemli, surukleyici bir sahneyle bir hikaye baslat. Ikinci sahis anlatimiyla yaz."
        contents = [types.Content(role="user", parts=[types.Part(text=prompt)])]
    else:
        contents = []
        for msg in request.history:
            role = "model" if msg.get("role") == "assistant" else "user"
            contents.append(types.Content(role=role, parts=[types.Part(text=msg.get("text", ""))]))
        if request.action:
            contents.append(types.Content(role="user", parts=[types.Part(text=request.action)]))
    try:
        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=system),
        )
        return {"continuation": response.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/stories")
def create_story(req: StoryCreate, authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    story = database.add_story(user["id"], req.content, req.image_url)
    return story


@app.get("/api/stories/feed")
def get_story_feed(authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    return database.get_friend_stories(user["id"])


@app.post("/api/friends/request")
def friend_request(req: FriendRequest, authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    success = database.send_friend_request(user["id"], req.email)
    if not success:
        raise HTTPException(status_code=404, detail="Bu emailde kullanici bulunamadi.")
    return {"status": "istek gonderildi"}


@app.post("/api/friends/{friendship_id}/accept")
def accept_friend(friendship_id: int, authorization: Optional[str] = Header(None)):
    get_current_user(authorization)
    database.accept_friend_request(friendship_id)
    return {"status": "arkadas kabul edildi"}


@app.get("/api/friends")
def get_friends(authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    return database.get_friends(user["id"])


@app.get("/api/friends/requests")
def get_friend_requests(authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    return database.get_friend_requests(user["id"])