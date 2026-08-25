"""
Konsey ajanlari icin saglayici katmani.

auro-backend/aura_brain.py ile HICBIR baglantisi yok - bu modul kendi .env
dosyasini okur, uygulamadaki kullanici verisine/hafizasina hicbir zaman
erisemez. Yeni bir saglayici eklemek icin: asagidaki gibi bir call_x()
fonksiyonu yaz, PROVIDER_CALLERS sozlugune ekle, personas.py'de ilgili
ajanin "provider" degerini guncelle.

NOT: XAI_API_KEY (Grok / xAI) ile auro-backend/.env icindeki GROQ_API_KEY
(Groq - hizli acik model altyapisi) FARKLI seylerdir, isimleri birbirine
cok benziyor. Beta ajani icin gereken xAI'nin Grok modeli, Groq degil.
"""
import os

import httpx
from dotenv import load_dotenv
from google import genai
from google.genai import types as genai_types

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

GEMINI_API_KEY = (os.getenv("GEMINI_API_KEY") or "").strip()
OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY") or "").strip()
ANTHROPIC_API_KEY = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
XAI_API_KEY = (os.getenv("XAI_API_KEY") or "").strip()
# Groq (LPU altyapisi, acik modelleri hizli calistiran ayri bir sirket -
# xAI'nin Grok modeliyle KARISTIRILMASIN) - auro-backend/.env'deki ile
# ayni deger kullanilabilir, zaten var, yeni hesap gerekmiyor.
GROQ_API_KEY = (os.getenv("GROQ_API_KEY") or "").strip()

GEMINI_MODEL = os.getenv("COUNCIL_GEMINI_MODEL", "gemini-3.6-flash")
OPENAI_MODEL = os.getenv("COUNCIL_OPENAI_MODEL", "gpt-4o")
ANTHROPIC_MODEL = os.getenv("COUNCIL_ANTHROPIC_MODEL", "claude-sonnet-5")
XAI_MODEL = os.getenv("COUNCIL_XAI_MODEL", "grok-4")
GROQ_MODEL = os.getenv("COUNCIL_GROQ_MODEL", "openai/gpt-oss-120b")

TIMEOUT = 30

_gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None


class MissingApiKeyError(RuntimeError):
    def __init__(self, provider, env_var):
        super().__init__(
            f"{provider} icin API anahtari yok - council-backend/.env "
            f"dosyasina {env_var} ekleyin"
        )


def call_gemini(messages, system_instruction):
    if _gemini_client is None:
        raise MissingApiKeyError("Gemini", "GEMINI_API_KEY")

    contents = [
        genai_types.Content(
            role=("model" if m["role"] == "assistant" else "user"),
            parts=[genai_types.Part(text=m["content"])],
        )
        for m in messages
    ]
    response = _gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=contents,
        config=genai_types.GenerateContentConfig(
            system_instruction=system_instruction
        ),
    )
    return (response.text or "").strip()


def call_openai(messages, system_instruction):
    if not OPENAI_API_KEY:
        raise MissingApiKeyError("OpenAI", "OPENAI_API_KEY")

    payload_messages = [{"role": "system", "content": system_instruction}] + messages
    response = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": OPENAI_MODEL,
            "messages": payload_messages,
            "temperature": 0.7,
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    return (data["choices"][0]["message"]["content"] or "").strip()


def call_anthropic(messages, system_instruction):
    if not ANTHROPIC_API_KEY:
        raise MissingApiKeyError("Anthropic", "ANTHROPIC_API_KEY")

    response = httpx.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json={
            "model": ANTHROPIC_MODEL,
            "system": system_instruction,
            "messages": messages,
            # 400 cok dusuktu, gercek testte Gamma'nin cevabi cumle
            # ortasinda kesildi - Turkce yanit persona'nin "3-5 cumle"
            # talimatina ragmen bunu asabiliyor.
            "max_tokens": 1024,
            # KRITIK BUG (25 Agu 2026, ask_aura_app_analysis.py testinde
            # tesadufen yakalandi): "claude-sonnet-5" varsayilan olarak
            # "extended thinking" moduna giriyor - uzun/karmasik promptlarda
            # dusunme adimi tek basina 1024 token'lik butceyi tuketip
            # HICBIR metin uretilmeden kesilebiliyor (sessiz bos cevap,
            # hata firlatmiyor). Thinking'i acikca kapatmak bunu onluyor -
            # dogrulandi: ayni prompt thinking kapaliyken duzgun metin
            # dondurdu.
            "thinking": {"type": "disabled"},
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    return "".join(block.get("text", "") for block in data.get("content", [])).strip()


def call_xai(messages, system_instruction):
    if not XAI_API_KEY:
        raise MissingApiKeyError("xAI", "XAI_API_KEY")

    payload_messages = [{"role": "system", "content": system_instruction}] + messages
    response = httpx.post(
        "https://api.x.ai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {XAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": XAI_MODEL,
            "messages": payload_messages,
            "temperature": 0.8,
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    return (data["choices"][0]["message"]["content"] or "").strip()


def call_groq(messages, system_instruction):
    if not GROQ_API_KEY:
        raise MissingApiKeyError("Groq", "GROQ_API_KEY")

    payload_messages = [{"role": "system", "content": system_instruction}] + messages
    response = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": GROQ_MODEL,
            "messages": payload_messages,
            "temperature": 0.8,
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    return (data["choices"][0]["message"]["content"] or "").strip()


PROVIDER_CALLERS = {
    "gemini": call_gemini,
    "openai": call_openai,
    "anthropic": call_anthropic,
    "xai": call_xai,
    "groq": call_groq,
}
