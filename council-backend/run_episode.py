"""
Konsey bolumunu calistirip transkripti kaydeder.

Kullanim:
    python run_episode.py bolum_0
"""
import argparse
import importlib
import json
import os
from datetime import datetime, timezone

from orchestrator import run_episode
from personas import PERSONAS

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("episode", help="episodes/ altindaki modul adi, orn. bolum_0")
    args = parser.parse_args()

    episode = importlib.import_module(f"episodes.{args.episode}")
    transcript = run_episode(episode.TOPIC, episode.TURN_PLAN)

    print(f"\n=== {args.episode} | {episode.TOPIC} ===\n")
    for turn in transcript:
        name = PERSONAS[turn["speaker"]]["display_name"]
        print(f"[{name}] {turn['text']}\n")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    out_path = os.path.join(OUTPUT_DIR, f"{args.episode}-{stamp}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            {"topic": episode.TOPIC, "transcript": transcript},
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"Transkript kaydedildi: {out_path}")


if __name__ == "__main__":
    main()
