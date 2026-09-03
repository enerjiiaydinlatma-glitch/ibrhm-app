"""Faz 3 egitim verisi hazirlama: golden_set + distill logu -> temiz,
tekillestirilmis, egitime hazir JSONL.

Kullanim:
    python prepare_training_data.py \
        --golden golden_set.jsonl \
        --distill /path/to/brain_distill.jsonl \
        --out train.jsonl \
        [--golden-weight 3] [--max-distill 20000] [--min-reply 15] [--max-reply 1200]

Cikti formati (Unsloth / axolotl / TRL SFTTrainer'in bekledigi "messages"):
    {"messages": [{"role":"system",...}, {"role":"user",...}, {"role":"assistant",...}, ...]}
son mesaj her zaman assistant (reply) olur.

Golden ornekleri --golden-weight kadar tekrarlanir (egitimde agirlik).
"""
import argparse
import hashlib
import json
import random
import re
import sys


def load_jsonl(path):
    rows = []
    try:
        with open(path, encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as e:
                    print(f"  atlandi ({path}:{i}): {e}")
    except FileNotFoundError:
        print(f"  UYARI: {path} yok, atlandi")
    return rows


def to_sample(row):
    """golden VEYA distill satirini {messages:[... , assistant]} formatina getir."""
    msgs = list(row.get("messages") or [])
    reply = (row.get("reply") or "").strip()
    if not msgs or not reply:
        return None
    # son mesaj user olmali (reply ona verilecek cevap)
    if msgs[-1].get("role") != "user":
        return None
    msgs = msgs + [{"role": "assistant", "content": reply}]
    # rol/icerik temizligi
    clean = []
    for m in msgs:
        r = m.get("role")
        c = (m.get("content") or "").strip()
        if r not in ("system", "user", "assistant") or not c:
            return None
        clean.append({"role": r, "content": c})
    return {"messages": clean}


def quality_ok(sample, min_reply, max_reply):
    reply = sample["messages"][-1]["content"]
    if not (min_reply <= len(reply) <= max_reply):
        return False, "uzunluk"
    low = reply.lower()
    # ic-etiket / sablon sizintisi
    for bad in ("[soluk hafiza]", "[hafiza:", "[arac bilgisi", "sistem talimati",
                "kimlik:", "[isminizi", "as an ai", "i am an ai language model",
                "yapay zeka dil modeli"):
        if bad in low:
            return False, "sizinti"
    # ust uste 4+ unsuz (bozuk uretim isareti) - sadece ASCII
    if re.search(r"[bcdfghjklmnpqrstvwxyz]{5,}", low):
        return False, "bozuk-kelime"
    # cok fazla tekrar (ayni cumle 3+)
    sents = [s.strip() for s in re.split(r"[.!?\n]+", reply) if len(s.strip()) > 10]
    if sents and len(sents) - len(set(sents)) >= 2:
        return False, "tekrar"
    return True, ""


def sample_key(sample):
    """dedup anahtari: son user + assistant metni."""
    u = next((m["content"] for m in reversed(sample["messages"][:-1]) if m["role"] == "user"), "")
    a = sample["messages"][-1]["content"]
    return hashlib.sha1((u[:200] + "||" + a[:200]).encode("utf-8")).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--golden", default="golden_set.jsonl")
    ap.add_argument("--distill", default="")
    ap.add_argument("--out", default="train.jsonl")
    ap.add_argument("--golden-weight", type=int, default=3)
    ap.add_argument("--max-distill", type=int, default=20000)
    ap.add_argument("--min-reply", type=int, default=4)  # "Persembe." gibi kisa golden'lar gecerli
    ap.add_argument("--max-reply", type=int, default=1400)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    random.seed(args.seed)

    golden = load_jsonl(args.golden)
    distill = load_jsonl(args.distill) if args.distill else []
    print(f"okundu: golden={len(golden)}  distill={len(distill)}")

    seen = set()
    out = []
    stats = {"golden": 0, "distill": 0, "reddedildi": {}}

    def add(row, source, weight=1):
        s = to_sample(row)
        if not s:
            stats["reddedildi"]["sekil"] = stats["reddedildi"].get("sekil", 0) + 1
            return
        ok, why = quality_ok(s, args.min_reply, args.max_reply)
        if not ok:
            stats["reddedildi"][why] = stats["reddedildi"].get(why, 0) + 1
            return
        k = sample_key(s)
        if k in seen:
            stats["reddedildi"]["cift"] = stats["reddedildi"].get("cift", 0) + 1
            return
        seen.add(k)
        for _ in range(weight):
            out.append(s)
        stats[source] += weight if source == "golden" else 1

    for row in golden:
        add(row, "golden", weight=max(1, args.golden_weight))
    random.shuffle(distill)
    for row in distill[: args.max_distill]:
        add(row, "distill")

    random.shuffle(out)
    with open(args.out, "w", encoding="utf-8") as f:
        for s in out:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")

    print(f"\nYAZILDI: {args.out}  ({len(out)} satir; golden x{args.golden_weight} agirlikli)")
    print(f"  golden katki: {stats['golden']}   distill katki: {stats['distill']}")
    print(f"  reddedildi: {stats['reddedildi']}")
    if len(out) < 200:
        print("\n  NOT: <200 ornek. Fine-tune icin en az ~2-3k onerilir - distill logu birikmeli.")


if __name__ == "__main__":
    sys.exit(main())
