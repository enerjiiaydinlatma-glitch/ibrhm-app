import os
import time
from collections import defaultdict, deque
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai
from google.genai import types
from google.genai import errors as genai_errors
import database

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("GEMINI_API_KEY .env dosyasinda bulunamadi")

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


@app.middleware("http")
async def rate_limiter(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    log = request_log[client_ip]

    while log and now - log[0] > RATE_LIMIT_WINDOW:
        log.popleft()

    if len(log) >= RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(status_code=429, detail="Cok fazla istek gonderdin, biraz yavaslayalim.")

    log.append(now)
    return await call_next(request)


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


def get_context_summary(user_id: int = 1) -> str:
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
            "Bunu dogal bir sekilde, konusma akisinda fark ettigini hissettirebilirsin, "
            "ama bunu her mesajda tekrar etme, sadece uygun oldugunda."
        )
    return ""


def build_system_instruction(user: dict) -> str:
    isim_notu = ""
    if user.get("name"):
        isim_notu = "Kullanicinin adi " + str(user.get("name")) + ". "
    context = get_context_summary(1)
    parts = [
        "Senin adin Aura. Kullanicilara yardimci olan kisisel bir yapay zeka asistanisin.",
        "Hangi sirket tarafindan gelistirildigini, hangi AI modelini kullandigini",
        "(Gemini, GPT, Claude vb.) ASLA acikla veya soyleme. Sadece 'Aura' oldugunu soyle.",
        isim_notu,
        "DURUSTLUK KURALI (cok onemli): Sadece metin tabanli sohbet, sesli yanit",
        "(varsa) ve hafiza yeteneklerin var. Kod calistiramazsin, kendi kendini",
        "guncelleyemezsin, internetten canli arama yapamazsin, baska sistemleri",
        "kontrol edemezsin. Sahip olmadigin bir yetenegi ASLA varmis gibi anlatma,",
        "uydurma veya kullaniciyi memnun etmek icin abartma. Bir seyi yapamiyorsan,",
        "bunu acikca ve sakin bir sekilde soyle.",
        "KISILIK: Bilge, alim, net ve anlasilir konusan bir asistansin - abartili",
        "veya yapmacik coskulu degil, dogal ve dengeli.",
        "Sicaklik seviyen: " + str(user.get("warmth", "sicak")) + ".",
        "Resmiyet seviyen: " + str(user.get("formality", "samimi")) + ".",
        "Mizah seviyen: " + str(user.get("humor", "orta")) + ".",
        "Dogrudanlik seviyen: " + str(user.get("directness", "dengeli")) + ".",
        "TON UYUMU: Kullanicinin o anki mesajindaki ses tonunu, enerjisini ve",
        "yazma tarzini dikkatle oku ve ona dogal bir sekilde ayna tut, ama kendi",
        "bilgece ve durust karakterinden sapma.",
        "Kullanici hakkinda notlar: " + str(user.get("notes", "yok")) + ".",
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
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                ),
            )
        except genai_errors.ServerError as e:
            last_error = e
            if attempt < max_attempts - 1:
                time.sleep(2 * (attempt + 1))
            continue
    raise last_error


class ChatRequest(BaseModel):
    message: str


class ProfileUpdate(BaseModel):
    name: str | None = None
    warmth: str | None = None
    formality: str | None = None
    humor: str | None = None
    directness: str | None = None
    notes: str | None = None


@app.get("/")
def root():
    return {"status": "Aura backend calisiyor", "version": "2.1.0"}


@app.get("/api/profile")
def get_profile():
    return database.get_user(1)


@app.post("/api/profile")
def update_profile(update: ProfileUpdate):
    fields = {k: v for k, v in update.dict().items() if v is not None}
    database.update_user(1, **fields)
    return database.get_user(1)


@app.get("/api/history")
def get_history():
    return database.get_messages(1)


@app.post("/api/chat")
def chat(request: ChatRequest):
    user = database.get_user(1)

    mood = detect_mood(request.message)
    if mood:
        database.add_mood(1, mood, context=request.message[:100])

    database.add_message(1, "user", request.message)

    past_messages = database.get_messages(1)
    contents = [
        types.Content(
            role=("model" if m["role"] == "assistant" else "user"),
            parts=[types.Part(text=m["text"])],
        )
        for m in past_messages
    ]

    try:
        response = generate_with_retry(contents, build_system_instruction(user))
        reply_text = response.text
    except genai_errors.ServerError:
        reply_text = "Su an biraz yogunum, bir dakika sonra tekrar dener misin? Sabrin icin tesekkurler."

    database.add_message(1, "assistant", reply_text)

    return {"reply": reply_text}


@app.post("/chat")
def chat_legacy(request: ChatRequest):
    return chat(request)
