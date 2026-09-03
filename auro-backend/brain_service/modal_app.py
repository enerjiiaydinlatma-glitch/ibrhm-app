"""Aura Brain Mesh - serverless GPU (Modal). Faz 2 secenek C.

`brain_service/server.py`'nin bulut karsiligi: kendi GPU'na bagimli
degil, saniye basi odeme, kullanilmayinca SIFIRA olcekleniyor (soguk
baslama ~20-40s, sonra sicak). vLLM ile OpenAI-uyumlu /v1/chat/completions
sunar + konusma logunu bir Modal Volume'a yazar (Faz 3 egitim verisi).

Kurulum (bir kez):
    pip install modal
    modal token new
    modal secret create aura-brain-secret AURA_BRAIN_KEY=<railway'deki ile ayni>
    modal deploy auro-backend/brain_service/modal_app.py

Cikan URL (or. https://<org>--aura-brain-serve.modal.run) -> Railway:
    AURA_BRAIN_URL = o URL
    AURA_BRAIN_KEY = yukaridaki secret ile ayni
    AURA_BRAIN_MODEL = aura

Model degistirmek: MODEL_ID'yi degistir + `modal deploy` tekrar.
GPU degistirmek: @app.function(gpu=...) - "A10G" (ucuz, 7-8B'ye yeter) /
"A100-40GB" (14-32B) / "H100" (70B).
"""
import json
import os
import time
from datetime import datetime, timezone

import modal

# --- ayarlar ---
# 2026-09-03: Qwen2.5-7B Turkcesi Aura icin yetersizdi (bozuk gramer/uydurma
# kelime). 14B'ye cikildi. A100 Modal'da odeme yontemi ister; onun yerine
# 14B-AWQ (4-bit, ~9GB) A10G'ye sigar ve UCRETSIZ katmanda kalir - kalite
# fp16'ya cok yakin. Odeme yontemi eklenirse: MODEL_ID=Qwen/Qwen2.5-14B-
# Instruct (veya 32B-Instruct-AWQ) + AURA_BRAIN_GPU=A100-40GB.
MODEL_ID = os.environ.get("AURA_BRAIN_MODEL_ID", "Qwen/Qwen2.5-14B-Instruct-AWQ")
GPU = os.environ.get("AURA_BRAIN_GPU", "A10G")
MAX_MODEL_LEN = int(os.environ.get("AURA_BRAIN_MAX_LEN", "8192"))

app = modal.App("aura-brain")

# vLLM. transformers'i <5'e sabitliyoruz - Modal'in pypi aynasi aksi halde
# vllm 0.6.3 ile uyumsuz transformers 5.x cekiyor (model yuklerken cokerdi).
vllm_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "vllm==0.6.3",
        "transformers<5",
        "fastapi",
        "huggingface_hub[hf_transfer]",
    )
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
)

# Model cache + konusma logu icin kalici disk.
cache_vol = modal.Volume.from_name("aura-brain-cache", create_if_missing=True)
log_vol = modal.Volume.from_name("aura-brain-logs", create_if_missing=True)

BRAIN_KEY = None  # secret'tan run-time'da


@app.function(
    image=vllm_image,
    gpu=GPU,
    volumes={"/root/.cache/huggingface": cache_vol, "/logs": log_vol},
    secrets=[modal.Secret.from_name("aura-brain-secret")],
    scaledown_window=300,   # 5 dk bosta kalinca kapan
    timeout=600,
)
@modal.concurrent(max_inputs=8)
@modal.asgi_app()
def serve():
    import fastapi
    from vllm import LLM, SamplingParams

    key = os.environ.get("AURA_BRAIN_KEY", "").strip()
    llm = LLM(model=MODEL_ID, max_model_len=MAX_MODEL_LEN, gpu_memory_utilization=0.92)

    web = fastapi.FastAPI(title="Aura Brain (Modal)")

    def _check(req: fastapi.Request):
        if not key:
            return
        got = req.headers.get("x-brain-key", "")
        auth = req.headers.get("authorization", "")
        if not got and auth.lower().startswith("bearer "):
            got = auth[7:].strip()
        if got != key:
            raise fastapi.HTTPException(401, "gecersiz anahtar")

    def _log(messages, reply, meta):
        try:
            row = {"ts": datetime.now(timezone.utc).isoformat(),
                   "messages": messages, "reply": reply, **meta}
            with open("/logs/conversations.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            log_vol.commit()
        except Exception as e:
            print("log yazilamadi:", e)

    @web.get("/health")
    def health():
        return {"status": "ok", "model": MODEL_ID, "gpu": GPU}

    @web.post("/v1/chat/completions")
    async def chat_completions(req: fastapi.Request):
        _check(req)
        body = await req.json()
        messages = body.get("messages") or []
        if not messages:
            raise fastapi.HTTPException(400, "messages bos")
        sp = SamplingParams(
            temperature=body.get("temperature", 0.8),
            max_tokens=body.get("max_tokens", 1024),
        )
        t0 = time.time()
        out = llm.chat(messages, sp)
        reply = out[0].outputs[0].text.strip()
        elapsed = round(time.time() - t0, 2)
        _log(messages, reply, {"model": MODEL_ID, "elapsed_s": elapsed, "ok": True})
        return {
            "id": "aura-" + str(int(t0)),
            "object": "chat.completion",
            "model": MODEL_ID,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": reply},
                        "finish_reason": "stop"}],
        }

    return web
