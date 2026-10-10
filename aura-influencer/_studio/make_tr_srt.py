"""
Var olan bir video icin ayri (gomulu olmayan) Turkce altyazi parcasi uretir.
Ingilizce ses/goruntu degismez - sadece platformun "alternatif dil altyazisi"
ozelligine yuklenecek .srt dosyasi uretilir (izleyici istege bagli acar).

Kullanim:
    python make_tr_srt.py <ses.wav> <out.srt> <en_script.txt> <tr_script.txt>

en_script ve tr_script: cumle sayisi ayni olmali (cumle-cumle zaman esleme
karakter-oranli yapiliyor - ASR yok).
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)  # yerel kopya: _studio/subtitles.py (baska projeye bagimlilik YOK)
from subtitles import build_srt  # noqa: E402


def _duration(path):
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True, check=True)
    return float(p.stdout.strip())


def _sentences(text):
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def make_tr_srt(audio_path, out_path, en_text, tr_text):
    dur = _duration(audio_path)
    en_sents = _sentences(en_text)
    tr_sents = _sentences(tr_text)
    if len(en_sents) != len(tr_sents):
        raise ValueError(f"Cumle sayisi uyusmuyor: EN={len(en_sents)} TR={len(tr_sents)}")

    # Zamanlama Ingilizce cumle uzunluklarina gore (ses onlara gore konusuluyor)
    weights = [max(len(s), 1) for s in en_sents]
    wsum = sum(weights)
    timeline = []
    t = 0.0
    for tr_s, wt in zip(tr_sents, weights):
        seg_dur = dur * wt / wsum
        timeline.append((tr_s, t, seg_dur))
        t += seg_dur

    build_srt(timeline, out_path)
    return out_path


if __name__ == "__main__":
    audio, out, en_path, tr_path = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    with open(en_path, encoding="utf-8") as f:
        en_text = f.read()
    with open(tr_path, encoding="utf-8") as f:
        tr_text = f.read()
    make_tr_srt(audio, out, en_text, tr_text)
    print("OK ->", out)
