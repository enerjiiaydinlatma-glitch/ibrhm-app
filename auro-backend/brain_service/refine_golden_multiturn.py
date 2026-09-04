"""Cok-turlu oz-elestiri R&D motoru: multiturn_scenarios.jsonl'deki (arc,
system, user_turns) tohumlarindan COK TURLU baglam iceren golden ornekler
uretir. refine_golden.py'nin ayni 3-gecisli (taslak -> elestiri -> nihai)
mantigi, ama HER TUR bir onceki turlerin GERCEK (nihai/refine edilmis)
baglaminda uretiliyor - boylece egitim verisi sadece "iyi tek-tur yanit"
degil, "onceki turleri dogru hatirlayip kullanma" ornegi de icerir (bkz.
multiturn_stress.py'nin canli Aura'da olcttugu AYNI yetenek, GENEL 4.80/5).

Her arc N kullanici turu icin N AYRI golden ornek uretir (1..N turluk
ARTAN baglamla, en kisadan en uzuna) - 10 arc x ~5-6 tur ~= 50-60 yeni
ornek. golden_set.jsonl'deki tek-turlu orneklerden FARKLI olarak "messages"
alani burada birden fazla user/assistant cifti icerebilir - eval_brain.py
ve prepare_training_data.py bunu zaten oldugu gibi tasir (system + N mesaj
+ reply), degisiklik gerekmiyor.

Kullanim:
    python refine_golden_multiturn.py --in multiturn_scenarios.jsonl \
        --out multiturn_refined.jsonl [--limit N]

Cikti INSAN INCELEMESI gerektirir - iyi olanlarin (_draft/_critique
cikarilmis) reply'sini golden_set.jsonl'e tasi.
"""
import argparse
import json
import os
import sys
import time

from refine_golden import AURA_RUBRIC, _client, gen, gkey

HERE = os.path.dirname(os.path.abspath(__file__))


def _history_text(messages: list[dict]) -> str:
    lines = []
    for m in messages:
        role = "Kullanici" if m["role"] == "user" else "Aura"
        lines.append(f"{role}: {m['content']}")
    return "\n".join(lines)


def refine_turn(cl, types, system: str, history: list[dict], user_turn: str):
    history_block = _history_text(history)
    history_prefix = f"ONCEKI KONUSMA:\n{history_block}\n\n" if history_block else ""

    draft = gen(
        cl, types,
        f"{system}\n\n{history_prefix}Kullanici (yeni mesaj): {user_turn}\n\n"
        "Aura olarak, ONCEKI KONUSMAYI dogru hatirlayarak yanitla "
        "(sadece yaniti yaz):",
        0.7,
    )

    critique = gen(
        cl, types,
        f"{AURA_RUBRIC}\n\n{history_prefix}KULLANICI (yeni mesaj): {user_turn}\n"
        f"AURA'NIN TASLAK YANITI:\n{draft}\n\n"
        "Bu taslagi Aura rubrigine gore acimasizca elestir - ozellikle "
        "onceki konusmayi DOGRU hatirlayip hatirlamadigina (uydurma/celiski/"
        "unutma var mi) dikkat et. Somut kusurlari madde madde yaz. Iyi "
        "yanlarini da 1 cumleyle belirt.",
        0.3,
    )

    final = gen(
        cl, types,
        f"{system}\n\n{history_prefix}KULLANICI (yeni mesaj): {user_turn}\n\n"
        f"TASLAK:\n{draft}\n\nELESTIRI:\n{critique}\n\n"
        "Elestirideki her kusuru gidererek yaniti YENIDEN yaz - onceki "
        "konusmayi dogru kullanarak. Aura'nin sesiyle, sicak ve akici "
        "Turkce. Sadece nihai yaniti yaz, aciklama ekleme.",
        0.6,
    )
    return draft, critique, final


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--in", dest="inp",
        default=os.path.join(HERE, "multiturn_scenarios.jsonl"),
    )
    ap.add_argument(
        "--out", default=os.path.join(HERE, "multiturn_refined.jsonl")
    )
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    k = gkey()
    cl, types = _client(k)
    arcs = [json.loads(l) for l in open(args.inp, encoding="utf-8") if l.strip()]
    if args.limit:
        arcs = arcs[: args.limit]
    print(f"{len(arcs)} arc -> {args.out}\n")

    n = 0
    with open(args.out, "w", encoding="utf-8") as f:
        for arc in arcs:
            system = arc["system"]
            turns = arc.get("user_turns", [])
            history: list[dict] = []  # NIHAI (refine edilmis) yanitlarla
            for i, user_turn in enumerate(turns, start=1):
                try:
                    draft, crit, final = refine_turn(cl, types, system, history, user_turn)
                except Exception as e:
                    print(f"  [{arc.get('arc', '?')} #{i}] HATA: {type(e).__name__}: {e}")
                    time.sleep(3)
                    break
                messages = (
                    [{"role": "system", "content": system}]
                    + history
                    + [{"role": "user", "content": user_turn}]
                )
                row = {
                    "scenario": f"{arc.get('arc', '?')}#{i}",
                    "messages": messages,
                    "reply": final,
                    "provider": "refined",
                    "_draft": draft,
                    "_critique": crit,
                }
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                n += 1
                print(
                    f"  [{arc.get('arc', '?')} #{i}/{len(turns)}] "
                    f"taslak {len(draft)} -> nihai {len(final)} krkt"
                )
                history = history + [
                    {"role": "user", "content": user_turn},
                    {"role": "assistant", "content": final},
                ]
                time.sleep(1)

    print(f"\n{n} aday yazildi: {args.out}")
    print("INSAN INCELEMESI: _draft/_critique alanlarina bak, iyi olanlari (bu")
    print("iki alani cikararak) golden_set.jsonl'e tasi.")


if __name__ == "__main__":
    sys.exit(main())
