"""Aura fine-tune koşusu (Modal + Unsloth QLoRA) - Faz 3 son halkası.

Zincir:  prepare_training_data.py  ->  BU  ->  modal_app.py (serve)  ->  eval_brain.py

Kullanim:
    # 1) veriyi hazirla (yerelde):
    python prepare_training_data.py --golden golden_set.jsonl \
        --distill brain_distill.jsonl --out train.jsonl
    # 2) egitim verisini Modal volume'una yukle:
    modal volume put aura-ft-data train.jsonl /train.jsonl
    # 3) kos (A10G'de 7B QLoRA ~30-90 dk; 14B icin GPU="A100-40GB" + odeme yontemi):
    modal run finetune_modal.py
    # 4) cikan adapter: volume aura-ft-out/  ->  modal_app.py'de LoRA olarak yukle
    #    (vLLM: enable_lora=True, LoRARequest ile) veya merge edip MODEL_ID yap.

Ayarlar env ile: FT_BASE, FT_GPU, FT_EPOCHS, FT_LR, FT_RANK, FT_MAXLEN.
"""
import os

import modal

BASE = os.environ.get("FT_BASE", "unsloth/Qwen2.5-7B-Instruct-bnb-4bit")
GPU = os.environ.get("FT_GPU", "A10G")
EPOCHS = float(os.environ.get("FT_EPOCHS", "2"))
LR = float(os.environ.get("FT_LR", "2e-4"))
RANK = int(os.environ.get("FT_RANK", "16"))
MAXLEN = int(os.environ.get("FT_MAXLEN", "2048"))

app = modal.App("aura-finetune")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "unsloth",
        # BULUNDU (2026-09-04, 2. kosu HATASI): "trl<0.12" sabitlemesi guncel
        # unsloth surumuyle UYUMSUZDU - unsloth'un kendi ic "patch" kod-uretimi
        # (UnslothGKDTrainer) eski trl API sekline gore yazilmis varsayimlarla
        # GECERSIZ Python uretip "non-default argument follows default
        # argument" hatasiyla cokuyordu. trl'yi ARTIK sabitlemiyoruz - unsloth
        # kendi bagimlilik cozumlemesiyle UYUMLU bir trl surumunu kendisi
        # secsin (pip'in kendi resolver'i).
        "transformers<5",
        "datasets",
        "hf_transfer",
        # BULUNDU (2026-09-04, ilk kosu HATASI): trl'nin sft_trainer.py'si
        # rich.console.Console import ediyor ama rich hicbir yerde dogrudan
        # bagimlilik olarak listelenmemisti (trl'nin kendi paket metadata'sinda
        # opsiyonel/transitive olarak cozulmuyor) - ModuleNotFoundError ile
        # egitim hic baslamadan cokuyordu.
        "rich",
    )
    .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"})
)

data_vol = modal.Volume.from_name("aura-ft-data", create_if_missing=True)
out_vol = modal.Volume.from_name("aura-ft-out", create_if_missing=True)


@app.function(
    image=image,
    gpu=GPU,
    volumes={"/data": data_vol, "/out": out_vol},
    timeout=60 * 60 * 4,
)
def train():
    import json
    from datasets import Dataset
    from unsloth import FastLanguageModel
    from unsloth.chat_templates import get_chat_template
    from trl import SFTTrainer, SFTConfig

    train_path = "/data/train.jsonl"
    rows = [json.loads(l) for l in open(train_path, encoding="utf-8") if l.strip()]
    print(f"egitim ornegi: {len(rows)}")

    model, tok = FastLanguageModel.from_pretrained(
        model_name=BASE, max_seq_length=MAXLEN, load_in_4bit=True, dtype=None,
    )
    model = FastLanguageModel.get_peft_model(
        model, r=RANK, lora_alpha=RANK * 2, lora_dropout=0.0,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        use_gradient_checkpointing="unsloth", random_state=42,
    )
    tok = get_chat_template(tok, chat_template="qwen-2.5")

    def fmt(ex):
        return {"text": tok.apply_chat_template(ex["messages"], tokenize=False,
                                                add_generation_prompt=False)}

    ds = Dataset.from_list(rows).map(fmt, remove_columns=["messages"])

    trainer = SFTTrainer(
        model=model, tokenizer=tok, train_dataset=ds,
        args=SFTConfig(
            per_device_train_batch_size=2, gradient_accumulation_steps=8,
            warmup_ratio=0.05, num_train_epochs=EPOCHS, learning_rate=LR,
            logging_steps=5, optim="adamw_8bit", weight_decay=0.01,
            lr_scheduler_type="cosine", seed=42, output_dir="/tmp/ckpt",
            dataset_text_field="text", max_seq_length=MAXLEN, report_to="none",
        ),
    )
    trainer.train()

    model.save_pretrained("/out/aura-lora")
    tok.save_pretrained("/out/aura-lora")
    out_vol.commit()
    print("BITTI -> volume aura-ft-out/aura-lora  (LoRA adapter)")
    print("modal_app.py'de: enable_lora=True + LoRARequest('aura','/out/aura-lora'),")
    print("veya:  model = FastLanguageModel.merge_and_unload()  ->  push_to_hub")


@app.local_entrypoint()
def main():
    print(f"base={BASE}  gpu={GPU}  epochs={EPOCHS}  lr={LR}  rank={RANK}")
    train.remote()
