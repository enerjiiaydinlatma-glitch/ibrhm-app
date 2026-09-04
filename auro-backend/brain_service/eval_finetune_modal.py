"""Aura fine-tune DEGERLENDIRME sunucusu (Modal) - finetune_modal.py'nin
egittigi LoRA'yi eval_brain.py'nin bekledigi /v1/chat/completions
sekliyle sunar.

SADECE degerlendirme icindir - production brain (modal_app.py, Qwen-14B-AWQ,
prompted/fine-tune edilmemis) ile ILGISIZ, tamamen AYRI bir Modal app +
GPU. Bu ikisini birbirine karistirma: modal_app.py canli/prod adayi,
bu dosya sadece "LoRA'mizin karnesi ne" sorusuna cevap arayan tek seferlik
bir olcum araci.

Zincir: finetune_modal.py (egitim, aura-ft-out volume'una /aura-lora yazar)
    -> BU (o adapter'i yukleyip sunar) -> eval_brain.py (28 test + Gemini yargic)

Kullanim:
    modal deploy eval_finetune_modal.py
    python eval_brain.py --url https://<...>--aura-finetune-eval-serve.modal.run \
        --key <AURA_FT_EVAL_KEY degeri> --model aura-ft
"""
import os

import modal

BASE_HINT = os.environ.get("FT_BASE", "unsloth/Qwen2.5-7B-Instruct-bnb-4bit")
GPU = os.environ.get("FT_EVAL_GPU", "A10G")
MAXLEN = int(os.environ.get("FT_MAXLEN", "2048"))

app = modal.App("aura-finetune-eval")

# finetune_modal.py'deki AYNI kutuphane seti (ayni surumlerle yuklendigi
# icin ayni uyumluluk sorunlarindan kacinilir) + fastapi/peft (sunum icin).
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "unsloth",
        "transformers<5",
        "hf_transfer",
        "rich",
        "fastapi",
        "peft",
    )
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
)

# finetune_modal.py'nin yazdigi AYNI volume - /aura-lora klasoru orada.
out_vol = modal.Volume.from_name("aura-ft-out", create_if_missing=True)


@app.function(
    image=image,
    gpu=GPU,
    volumes={"/out": out_vol},
    secrets=[modal.Secret.from_name("aura-ft-eval-secret")],
    scaledown_window=300,
    timeout=600,
)
@modal.concurrent(max_inputs=4)
@modal.asgi_app()
def serve():
    import fastapi
    from unsloth import FastLanguageModel

    key = os.environ.get("AURA_FT_EVAL_KEY", "").strip()

    # unsloth'un kendi resmi deseni: save_pretrained() ile kaydedilmis bir
    # LoRA klasoru dogrudan from_pretrained()'a verilirse, taban modeli +
    # adaptoru OTOMATIK birlikte yukler (ayrica PeftModel.from_pretrained
    # cagirmaya gerek yok).
    model, tok = FastLanguageModel.from_pretrained(
        model_name="/out/aura-lora",
        max_seq_length=MAXLEN,
        load_in_4bit=True,
    )
    FastLanguageModel.for_inference(model)

    web = fastapi.FastAPI(title="Aura Fine-tune Eval (gecici, sadece olcum)")

    def _check(req: fastapi.Request):
        if not key:
            return
        got = req.headers.get("x-brain-key", "")
        auth = req.headers.get("authorization", "")
        if not got and auth.lower().startswith("bearer "):
            got = auth[7:].strip()
        if got != key:
            raise fastapi.HTTPException(401, "gecersiz anahtar")

    @web.get("/health")
    def health():
        return {"status": "ok", "base": BASE_HINT, "adapter": "/out/aura-lora"}

    @web.post("/v1/chat/completions")
    async def chat_completions(req: fastapi.Request):
        _check(req)
        body = await req.json()
        messages = body.get("messages") or []
        if not messages:
            raise fastapi.HTTPException(400, "messages bos")

        inputs = tok.apply_chat_template(
            messages,
            tokenize=True,
            add_generation_prompt=True,
            return_tensors="pt",
        ).to("cuda")

        out = model.generate(
            input_ids=inputs,
            max_new_tokens=body.get("max_tokens", 512),
            temperature=body.get("temperature", 0.7),
            do_sample=True,
            use_cache=True,
        )
        reply = tok.decode(out[0][inputs.shape[1]:], skip_special_tokens=True).strip()

        return {
            "id": "aura-ft-eval",
            "object": "chat.completion",
            "model": "aura-ft",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": reply},
                    "finish_reason": "stop",
                }
            ],
        }

    return web
