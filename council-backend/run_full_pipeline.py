"""
Bir bolumu bastan sona tek komutla uretir: metin -> ses -> video -> Shorts.
Anahtarlar hazir oldugunda (bkz. README) sadece bunu calistirmak yeterli.

Kullanim:
    python run_full_pipeline.py bolum_0
    python run_full_pipeline.py bolum_1
    python run_full_pipeline.py bolum_3 --no-shorts   # Shorts adimini atla
"""
import argparse
import importlib
import json
import os
from datetime import datetime, timezone

from make_shorts import make_shorts
from orchestrator import run_episode
from personas import PERSONAS
from render_audio import render as render_audio
from render_video import render as render_video

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("episode", help="episodes/ altindaki modul adi, orn. bolum_0")
    parser.add_argument("--no-shorts", action="store_true", help="Shorts uretim adimini atla")
    args = parser.parse_args()

    episode = importlib.import_module(f"episodes.{args.episode}")

    print(f"=== 1/3 Metin uretimi: {args.episode} ===")
    transcript = run_episode(episode.TOPIC, episode.TURN_PLAN)
    for turn in transcript:
        name = PERSONAS[turn["speaker"]]["display_name"]
        print(f"[{name}] {turn['text'][:120]}{'...' if len(turn['text']) > 120 else ''}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    transcript_path = os.path.join(OUTPUT_DIR, f"{args.episode}-{stamp}.json")
    with open(transcript_path, "w", encoding="utf-8") as f:
        json.dump(
            {"topic": episode.TOPIC, "transcript": transcript},
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"Transkript kaydedildi: {transcript_path}\n")

    print("=== 2/3 Ses uretimi ===")
    render_audio(transcript_path)

    print("\n=== 3/4 Video uretimi ===")
    render_video(transcript_path)

    if not args.no_shorts:
        print("\n=== 4/4 Shorts uretimi (dikey klipler) ===")
        make_shorts(transcript_path, upload=False)
        print("Shorts private olarak yuklenmedi - once inceleyin, sonra:")
        print(f"  python make_shorts.py {transcript_path} --upload")


if __name__ == "__main__":
    main()
