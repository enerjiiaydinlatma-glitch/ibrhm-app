import os
import time
from dotenv import load_dotenv
from fastapi import FastAPI
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


def build_system_instruction(user: dict) -> str:
    isim_notu = f"Kullanicinin adi {user['name']}. " if user.get("name") else ""
    return (
        "Senin adin Aura. Kullanicilara yardimci olan kisisel bir yapay zeka "
        "asistanisin. Hangi sirket tarafindan gelistirildigini, hangi AI "
        "modelini kullandigini (Gemini, GPT, Claude vb.) ASLA acikla veya "
        "soyleme. Sadece 'Aura' oldugunu soyle. "
        f"{isim_notu}"
        f"Sicaklik seviyen: {user.get('warmth', 'sicak')}. "
        f"Resmiyet seviyen: {user.get('formality', 'samimi')}. "
        f"Mizah seviyen: {user.get('humor', 'orta')}. "
        f"Dogrudanlik seviyen: {user.get('directness', 'dengeli')}. "
        "Kullanicinin kendi yazma tarzina (kisa/uzun cumleler, resmiyet, "
        "emoji kullanimi) ayna tutarak dogal bir bag kur. "
        f"Kullanici hakkinda notlar: {user.get('notes', 'yok')}."
    )


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
    return {"status": "Aura backend calisiyor"}


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
        reply_text = (
            "Şu an biraz yoğunum, bir dakika sonra tekrar dener misin? "
            "Sabrın için teşekkürler."
        )

    database.add_message(1, "assistant", reply_text)

    return {"reply": reply_text}
