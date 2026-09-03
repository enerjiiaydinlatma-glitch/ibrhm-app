"""Aura Brain Mesh - muhakeme cekirdegi servisi (Seviye 1b).

Voice Mesh'in (auro-backend/voice_service) muhakeme karsiligi. Aura'nin
KENDI LLM'i icin ince bir sarmalayici: arka planda bir Ollama / vLLM /
llama.cpp instance'i cagirir ama araya SU degeri katar:

  1. KONUSMA LOGU - her istek/yanit, Faz 3 (fine-tune) icin hazir JSONL
     formatinda diske yazilir. Ollama bunu yapmaz; bu veri Aura'nin kendi
     modelini egitmenin yakiti.
  2. ANAHTAR KIMLIGI - tunel uzerinden aciga cikan Ollama'nin kimligi yok;
     burada X-Brain-Key / Bearer zorunlu kilinabilir.
  3. YUK KORUMASI - Voice Mesh'teki gibi: kuyruk dolunca hemen 503, cagiran
     (auro-backend generate_with_retry) hizlica Gemini'ye duser.
  4. MODEL SECIMI - istekteki "model" alanina gore backend model adini
     eslestirir (aura -> gercek model adi), ileride zorluk-bazli yonlendirme.

Calistirma:
    # once arka plan LLM'i (bir kez):
    #   ollama serve            (ayri pencere)
    #   ollama pull qwen2.5:7b-instruct
    set AURA_BRAIN_KEY=uzun-gizli-anahtar
    set BRAIN_BACKEND_URL=http://localhost:11434
    set BRAIN_BACKEND_MODEL=qwen2.5:7b-instruct
    python server.py            # :8130

Uclar:
    GET  /health                        -> {status, backend_ok, model, inflight}
    POST /v1/chat/completions {...}     -> OpenAI-uyumlu yanit (auro-backend
                                          bunu bekliyor). Stream desteklenmez
                                          (Faz 1'de gerek yok - non-stream).
"""
from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timezone

import httpx
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

BRAIN_KEY = (os.getenv("AURA_BRAIN_KEY") or "").strip()
BACKEND_URL = (os.getenv("BRAIN_BACKEND_URL") or "http://localhost:11434").strip().rstrip("/")
BACKEND_MODEL = (os.getenv("BRAIN_BACKEND_MODEL") or "qwen2.5:7b-instruct").strip()
BACKEND_TIMEOUT_S = float(os.getenv("BRAIN_BACKEND_TIMEOUT_S") or "60")
PORT = int(os.getenv("AURA_BRAIN_PORT") or "8130")

# Faz 3 yakiti: her tam tur buraya JSONL olarak eklenir. AURA_BRAIN_LOG=""
# ile kapatilir.
LOG_PATH = (os.getenv("AURA_BRAIN_LOG") or os.path.join(os.path.dirname(__file__), "conversations.jsonl")).strip()

MAX_QUEUE = int(os.getenv("AURA_BRAIN_MAX_QUEUE") or "6")
_inflight = 0
_lock = threading.Lock()
_log_lock = threading.Lock()

app = FastAPI(title="Aura Brain Mesh")
_http = httpx.Client()


def _check_key(x_brain_key: str | None, authorization: str | None) -> None:
    if not BRAIN_KEY:
        return
    supplied = (x_brain_key or "").strip()
    if not supplied and authorization and authorization.lower().startswith("bearer "):
        supplied = authorization[7:].strip()
    if supplied != BRAIN_KEY:
        raise HTTPException(status_code=401, detail="gecersiz anahtar")


def _try_enter() -> bool:
    global _inflight
    with _lock:
        if MAX_QUEUE and _inflight >= MAX_QUEUE:
            return False
        _inflight += 1
        return True


def _leave() -> None:
    global _inflight
    with _lock:
        _inflight = max(0, _inflight - 1)


def _log_turn(messages: list[dict], reply: str, meta: dict) -> None:
    if not LOG_PATH:
        return
    try:
        row = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "messages": messages,
            "reply": reply,
            **meta,
        }
        with _log_lock, open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"[brain] log yazilamadi: {e}", flush=True)


@app.get("/health")
def health():
    backend_ok = False
    try:
        r = _http.get(f"{BACKEND_URL}/api/tags", timeout=5)
        backend_ok = r.status_code == 200
    except Exception:
        try:
            r = _http.get(f"{BACKEND_URL}/v1/models", timeout=5)
            backend_ok = r.status_code == 200
        except Exception:
            backend_ok = False
    return {
        "status": "ok",
        "backend_ok": backend_ok,
        "backend_url": BACKEND_URL,
        "model": BACKEND_MODEL,
        "inflight": _inflight,
        "max_queue": MAX_QUEUE,
        "logging": bool(LOG_PATH),
    }


@app.post("/v1/chat/completions")
def chat_completions(
    body: dict,
    x_brain_key: str | None = Header(default=None),
    authorization: str | None = Header(default=None),
):
    _check_key(x_brain_key, authorization)

    messages = body.get("messages") or []
    if not isinstance(messages, list) or not messages:
        raise HTTPException(status_code=400, detail="messages bos")

    if not _try_enter():
        return JSONResponse(
            status_code=503,
            content={"error": {"message": f"brain mesgul ({_inflight}/{MAX_QUEUE})"}},
            headers={"Retry-After": "3"},
        )

    t0 = time.time()
    try:
        # Arka plan LLM'i de OpenAI-uyumlu /v1/chat/completions konusur
        # (Ollama, vLLM, llama.cpp server, TGI hepsi). "model" alanini
        # backend'in bekledigi ada sabitliyoruz.
        payload = {
            "model": BACKEND_MODEL,
            "messages": messages,
            "temperature": body.get("temperature", 0.8),
            "stream": False,
        }
        if "max_tokens" in body:
            payload["max_tokens"] = body["max_tokens"]

        r = _http.post(
            f"{BACKEND_URL}/v1/chat/completions",
            json=payload,
            timeout=BACKEND_TIMEOUT_S,
        )
        r.raise_for_status()
        data = r.json()
        reply = (data["choices"][0]["message"]["content"] or "").strip()
        elapsed = time.time() - t0
        print(f"[brain] {len(messages)} msg -> {len(reply)} krkt / {elapsed:.1f}s", flush=True)
        _log_turn(messages, reply, {"model": BACKEND_MODEL, "elapsed_s": round(elapsed, 2), "ok": True})

        # auro-backend sadece choices[0].message.content okuyor - backend'in
        # yanitini oldugu gibi geciriyoruz (usage vb. alanlar da gecer).
        return data
    except httpx.HTTPStatusError as e:
        _log_turn(messages, "", {"model": BACKEND_MODEL, "ok": False, "error": f"http-{e.response.status_code}"})
        raise HTTPException(status_code=502, detail=f"backend LLM http-{e.response.status_code}")
    except Exception as e:
        _log_turn(messages, "", {"model": BACKEND_MODEL, "ok": False, "error": type(e).__name__})
        raise HTTPException(status_code=502, detail=f"backend LLM: {type(e).__name__}")
    finally:
        _leave()


if __name__ == "__main__":
    import uvicorn

    print(
        f"[brain] Aura Brain Mesh :{PORT}  (backend: {BACKEND_URL} / {BACKEND_MODEL}, "
        f"log: {'acik' if LOG_PATH else 'kapali'}, anahtar: {'var' if BRAIN_KEY else 'YOK'})",
        flush=True,
    )
    uvicorn.run(app, host="0.0.0.0", port=PORT)
