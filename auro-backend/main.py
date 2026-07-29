import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai
from google.genai import types

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("GEMINI_API_KEY .env dosyasinda bulunamadi")

client = genai.Client(api_key=api_key)

SYSTEM_INSTRUCTION = (
    "Senin adin Aura. Kullanicilara yardimci olan bir yapay zeka asistanisin. "
    "Hangi sirket tarafindan gelistirildigini, hangi AI modelini kullandigini "
    "(Gemini, GPT, Claude vb.) ASLA acikla veya soyleme. Sadece 'Aura' oldugunu soyle. "
    "Biri 'sen kimsin' diye sorarsa 'Ben Aura'yim, sana yardimci olmak icin buradayim' "
    "gibi bir cevap ver, arka planda hangi teknolojiyi kullandigindan hic bahsetme."
)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatMessage(BaseModel):
    role: str
    text: str

class ChatRequest(BaseModel):
    history: list[ChatMessage]

@app.get("/")
def root():
    return {"status": "Aura backend calisiyor"}

@app.post("/api/chat")
def chat(request: ChatRequest):
    contents = [
        types.Content(
            role=("model" if m.role == "assistant" else "user"),
            parts=[types.Part(text=m.text)],
        )
        for m in request.history
    ]

    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
        ),
    )
    return {"reply": response.text}
