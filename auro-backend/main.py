import os
import time
import httpx
import aura_brain
import aura_memory
import aura_voice
import base64
from collections import defaultdict, deque
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Header, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
from google import genai
from google.genai import types
from google.genai import errors as genai_errors
import database

load_dotenv()

api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
if not api_key:
    raise RuntimeError("GEMINI_API_KEY .env dosyasinda bulunamadi")
# Kod sagligi taramasinda bulundu: burada anahtarin ilk/son karakterlerini
# ve uzunlugunu production loglarina yazan bir debug print vardi (401
# hatasini teshis etmek icin eklenmisti, o sorun cozuldu) - gereksiz bir
# bilgi sizintisi yuzeyiydi, kaldirildi.

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "").strip()

VOICE_IDS = {
    "male": "9OXwpKJw7rW6WI0ORNzm",
    "female": "iLcCq17FevxNYSk6Hgi7",
}

# Ucretsiz (free) tier gunluk kullanim limiti. 'pro' tier bundan muaf.
# Rakip uygulama arastirmasina (Replika/Character.AI) ve kullanicinin
# onayina dayanarak belirlendi.
LIMIT_DAILY_MESSAGES = 30
LIMIT_REACHED_REPLY = "Bugünkü ücretsiz mesaj hakkın doldu (30/30 mesaj). Yarın sıfırlanacak."

client = genai.Client(api_key=api_key)
database.init_db()
aura_memory.init_memory_db()
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    # Kod sagligi taramasinda bulundu: allow_origins=["*"] ile
    # allow_credentials=True birlikte kullanmak tarayici spesifikasyonuna
    # gore anlamsiz/gecersiz bir kombinasyon (credentialed istekler
    # wildcard origin ile calismaz). Bu API tum kimlik dogrulamayi
    # Authorization: Bearer header'i ile yapiyor (cookie kullanmiyor),
    # yani allow_credentials'a hic ihtiyac yok.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Aura'nin Flutter web derlemesi (2026-08-24, kullaniciya telefonundan
# - Mac/Xcode gerektiren native iOS build yerine - bugun erisim vermek
# icin eklendi). Onceden derlenip web_static/'e kopyalanmis statik
# dosyalar - /app altinda ayni Railway servisinden sunuluyor, ayri bir
# host/CORS derdi yok. html=True: eslesmeyen alt yollarda index.html'e
# duser (Flutter'in kendi client-side yonlendirmesi icin SPA fallback).
if os.path.isdir("web_static"):
    app.mount("/app", StaticFiles(directory="web_static", html=True), name="web_app")

RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX_REQUESTS = 30
request_log = defaultdict(deque)

MAX_HISTORY_MESSAGES = 20


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



class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str = ""

class LoginRequest(BaseModel):
    email: str
    password: str

class ClaimAccountRequest(BaseModel):
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
    location_lat: Optional[float] = None
    location_lon: Optional[float] = None
    location_city: Optional[str] = None
    weather_enabled: Optional[bool] = None
    activity_enabled: Optional[bool] = None
    mood_tracking_enabled: Optional[bool] = None

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
    # 'free' tier: ayni anda tek cihazda oturum kurali - yeni cihazdan
    # giris, eski cihazin oturumunu dusurur. 'pro' tier bundan muaf
    # (ayni anda birden fazla cihaz - bu Pro'ya ozgu bir avantaj).
    if user.get("tier") != "pro":
        database.enforce_single_session(user["id"])
    token = database.create_session(user["id"])
    return {"token": token, "user": _safe_user(user)}


@app.post("/api/auth/claim")
def claim_account(req: ClaimAccountRequest, authorization: Optional[str] = Header(None)):
    """
    Anonim (kullanicinin hic gormedigi, rastgele email/sifreyle
    olusturulmus) hesabi, kullanicinin KENDI belirledigi gercek
    email/sifreyle hatirlanabilir bir hesaba cevirir - ayni kullanici
    satiri guncellenir, tum gecmis/hafiza korunur.
    """
    user = get_current_user(authorization)
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Sifre en az 6 karakter olmali.")
    success = database.claim_account(user["id"], req.email, req.password)
    if not success:
        raise HTTPException(status_code=409, detail="Bu email zaten kayitli.")
    return _safe_user(database.get_user(user["id"]))


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


@app.get("/api/memories")
def get_memories(authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    return aura_memory.get_memories(user["id"])


@app.delete("/api/memories/{memory_id}")
def delete_memory(memory_id: int, authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    ok = aura_memory.forget_memory(user["id"], memory_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Hafiza bulunamadi")
    return {"status": "silindi"}


@app.get("/api/history")
def get_history(authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    return database.get_messages(user["id"])


@app.delete("/api/history")
def clear_history(authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    database.clear_messages(user["id"])
    return {"status": "gecmis temizlendi"}


@app.get("/api/chat/greeting")
def chat_greeting(authorization: Optional[str] = Header(None)):
    """
    Kullanicinin gecmisi bomsa Aura'nin ilk sozu kendisinin almasi icin.
    Gecmis doluysa hicbir sey uretmez (reply: null) - tanisma akisi
    sadece gercekten ilk kez gelen kullanicida tetiklenir.
    """
    user = get_current_user(authorization)
    past_messages = database.get_messages(user["id"])
    if past_messages:
        return {"reply": None}
    reply_text = aura_brain.generate_onboarding_opening(user)
    database.add_message(user["id"], "assistant", reply_text)
    return {"reply": reply_text}


@app.post("/api/chat")
def chat(request: ChatRequest, authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    mood = detect_mood(request.message)
    if mood:
        database.add_mood(user["id"], mood, context=request.message[:100])
    user_message_id = database.add_message(user["id"], "user", request.message)

    # Ucretsiz (free) tier gunluk mesaj limiti - Pro kullanicilar muaf.
    # Kullanicinin mesaji yine de kaydedildi (yukarida) - sadece pahali
    # islemler (hafiza cikarimi, pattern analizi, AI cagrisi) atlaniyor.
    if user.get("tier") != "pro" and not database.check_and_increment_message_usage(
        user["id"], LIMIT_DAILY_MESSAGES
    ):
        return {"reply": LIMIT_REACHED_REPLY, "limit_reached": True}

    aura_brain.extract_memory_candidate(user["id"], request.message, user_message_id)
    past_messages = database.get_messages(user["id"])
    message_count = len(past_messages)
    aura_brain.analyze_patterns(user["id"], message_count)
    recent_messages = past_messages[-MAX_HISTORY_MESSAGES:]
    contents = [
        types.Content(
            role=("model" if m["role"] == "assistant" else "user"),
            parts=[types.Part(text=m["text"])],
        )
        for m in recent_messages
    ]
    try:
        response = aura_brain.generate_with_retry(contents, aura_brain.build_system_instruction(user, message_count))
        reply_text = response.text
    except genai_errors.ServerError:
        reply_text = "Su an biraz yogunum, bir dakika sonra tekrar dener misin?"
    reply_text = aura_brain.sanitize_reply(reply_text, message_count)
    database.add_message(user["id"], "assistant", reply_text)
    return {"reply": reply_text}


@app.post("/api/chat/stream")
def chat_stream(request: ChatRequest, authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    mood = detect_mood(request.message)
    if mood:
        database.add_mood(user["id"], mood, context=request.message[:100])
    message_id = database.add_message(
    user["id"],
    "user",
    request.message
)
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
    system_instruction = aura_brain.build_system_instruction(user, message_count)

    def event_generator():
        collected = []
        try:
            stream = aura_brain.generate_stream(contents, system_instruction)
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
                full = aura_brain.sanitize_reply(full, message_count)
                database.add_message(user["id"], "assistant", full)

    return StreamingResponse(event_generator(), media_type="text/plain; charset=utf-8")


@app.websocket("/api/voice")
async def voice_endpoint(websocket: WebSocket):
    """
    Gercek zamanli, tam serbest sesli konusma. Token query string'den
    okunur (?token=...) - WebSocket'te custom header web'de guvenilir
    olmadigi icin.
    """
    await aura_voice.handle_voice_session(websocket)


@app.post("/api/tts")
def tts(request: TTSRequest, authorization: Optional[str] = Header(None)):
    # Kod sagligi taramasinda bulundu: bu endpoint hic kimlik dogrulamasi
    # yapmiyordu - giris yapmamis herkes sunucunun ElevenLabs anahtariyla
    # sinirsiz istek atip maliyet/kota tuketebilirdi. Diger tum
    # endpoint'lerle ayni desene getirildi.
    get_current_user(authorization)

    voice_id = VOICE_IDS.get(request.voice, VOICE_IDS["female"])
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
    }

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
        r = httpx.post(
            url,
            json=payload,
            headers=headers,
            timeout=60,
        )

        if r.status_code != 200:
            print(f"ELEVENLABS ERROR STATUS: {r.status_code}")
            print(f"ELEVENLABS ERROR BODY: {r.text}")
            # Ham ElevenLabs hata govdesini (hesap/plan bilgisi icerebilir)
            # istemciye sizdirmiyoruz - detay sadece sunucu logunda kalir.
            raise HTTPException(
                status_code=502,
                detail="Seslendirme şu an başarısız.",
            )

        return Response(
            content=r.content,
            media_type="audio/mpeg",
        )

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="ElevenLabs zaman asimi",
        )


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
            # Kod sagligi taramasinda bulundu: burada aura_brain.py'deki
            # guncel modelden (gemini-3.7-flash) FARKLI, eski bir model
            # adi ("gemini-3.6-flash") kullaniliyordu - tutarli hale
            # getirildi.
            model=aura_brain.MODEL_NAME,
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
        # Ham exception mesaji (potansiyel ic yapilandirma bilgisi
        # icerebilir) artik istemciye sizdirilmiyor - detay sadece
        # sunucu logunda kaliyor.
        print(f"ANALYZE ERROR: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Fotoğraf analiz edilemedi.")


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
            model=aura_brain.MODEL_NAME,
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=system),
        )
        return {"continuation": response.text}
    except Exception as e:
        print(f"STORY ERROR: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Hikaye devam ettirilemedi.")


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
