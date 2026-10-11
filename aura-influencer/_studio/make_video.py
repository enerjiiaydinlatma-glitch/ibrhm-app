"""
Aura influencer - ilk video otomatik montaj.
Yuzsuz strateji: koyu arka plan + ses-senkronlu waveform + kelime akan altyazi.

_studio/subtitles.py (SRT uretimi, ASR yok - script metni
zaten bilindigi icin karaktere-oranli zamanlama) GENEL AMACLI, Sign Council'e
ozgu degil - bu yuzden kutuphane olarak import ediliyor. Kod/veri PAYLASIMI
degil, sadece stateless bir yardimci fonksiyonun tekrar kullanimi.

Kullanim:
    python make_video.py <ses.wav> <cikti.mp4> "Tam script metni..."
"""
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)  # yerel kopya: _studio/subtitles.py (baska projeye bagimlilik YOK)
from subtitles import build_srt  # noqa: E402

W, H = 1080, 1920

# "Hype or Real?" serisi (2026-10-10): script'te "Verdict: REAL|HYPE|UNCLEAR." cumlesi varsa videoda seri etiketi (ust, surekli)
# ve o cumle sirasinda buyuk karar damgasi (orta) gosterilir. ASS renkleri BGR: &H00BBGGRR.
VERDICT_RE = re.compile(r"^\s*(?:my\s+)?verdict\s*[:\-]\s*(real|hype|unclear)\b", re.I)
VERDICT_COLORS = {"REAL": "&H0050B93F", "HYPE": "&H003E88F0", "UNCLEAR": "&H002299D2"}
SERIES_LABEL = "HYPE OR REAL?"


def find_verdict(sentences):
    """(index, 'REAL'|'HYPE'|'UNCLEAR') ya da None."""
    for i, s_ in enumerate(sentences):
        m = VERDICT_RE.match(s_)
        if m:
            return i, m.group(1).upper()
    return None


def _run(args, cwd=None):
    p = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("ffmpeg hatasi:\n" + (p.stderr[-2500:] if p.stderr else "?"))
    return p


def _duration(path):
    p = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True, check=True)
    return float(p.stdout.strip())


def _sentences(text):
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def make_video(audio_path, out_path, script_text, work_dir=None):
    work = work_dir or os.path.join(HERE, "_video_work")
    os.makedirs(work, exist_ok=True)

    dur = _duration(audio_path)

    # Cumleleri karakter uzunluguna oranli sureyle diz - ASR yok, script bilinen.
    sents = _sentences(script_text)
    weights = [max(len(s), 1) for s in sents]
    wsum = sum(weights)
    timeline = []
    t = 0.0
    for s, wt in zip(sents, weights):
        seg_dur = dur * wt / wsum
        timeline.append((s, t, seg_dur))
        t += seg_dur

    srt_name = "captions.srt"
    build_srt(timeline, os.path.join(work, srt_name))

    # seri katmanlari (sadece karar cumlesi olan videolarda)
    extra_vf = ""
    v = find_verdict(sents)
    if v:
        vi, verdict = v
        from subtitles import _ts
        with open(os.path.join(work, "series_label.srt"), "w", encoding="utf-8") as f:
            f.write(f"1\n{_ts(0)} --> {_ts(dur)}\n{SERIES_LABEL}\n")
        _, vt0, vdur = timeline[vi]
        with open(os.path.join(work, "series_stamp.srt"), "w", encoding="utf-8") as f:
            f.write(f"1\n{_ts(vt0)} --> {_ts(vt0 + vdur)}\nVERDICT:\n{verdict}\n")
        label_style = ("FontName=Segoe UI,Bold=1,Fontsize=11,PrimaryColour=&H00FFB07C,OutlineColour=&H00101010,"
                       "BorderStyle=1,Outline=2,Shadow=0,Alignment=6,MarginV=90")  # SSA numaralandirma: 6 = ust-orta
        stamp_style = (f"FontName=Segoe UI,Bold=1,Fontsize=24,PrimaryColour={VERDICT_COLORS[verdict]},OutlineColour=&H00101010,"
                       "BorderStyle=1,Outline=3,Shadow=0,Alignment=10,MarginV=0")  # SSA numaralandirma: 10 = orta-orta (1-3 alt, 5-7 ust, 9-11 orta)
        extra_vf = (f",subtitles=series_label.srt:force_style='{label_style}'"
                    f",subtitles=series_stamp.srt:force_style='{stamp_style}'")

    base = os.path.join(work, "_base.mp4")
    # koyu arka plan + ortada mor ses-dalgasi (showwaves) - gercek ses-senkronlu
    vf = (
        f"color=c=0x0b0710:s={W}x{H}:d={dur:.3f}[bg];"
        f"[1:a]showwaves=s={W-160}x300:mode=cline:colors=0xB07CFF:scale=sqrt:rate=25,"
        f"format=rgba[wave];"
        f"[0:v][wave]overlay=(W-w)/2:(H-h)/2:shortest=1,format=yuv420p[v]"  # [0:v] = giris 0 (renk kaynagi); [bg] etiketi bazi ffmpeg surumlerinde hata verir
    )
    _run([
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=c=0x0b0710:s={W}x{H}:d={dur:.3f}",
        "-i", audio_path,
        "-filter_complex", vf.split(";", 1)[1],
        "-map", "[v]", "-map", "1:a",
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
        "-r", "25", "-fps_mode", "cfr", "-t", f"{dur:.3f}",
        base,
    ])

    fs, mv = 15, 60
    style = (
        f"FontName=Segoe UI,Fontsize={fs},PrimaryColour=&H00FFFFFF,"
        f"OutlineColour=&H00101010,BorderStyle=1,Outline=2,Shadow=0,"
        f"Alignment=2,MarginV={mv}"
    )
    _run([
        "ffmpeg", "-y", "-i", os.path.abspath(base),
        "-vf", f"subtitles={srt_name}:force_style='{style}'" + extra_vf,
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-c:a", "copy", os.path.abspath(out_path),
    ], cwd=work)
    return out_path


if __name__ == "__main__":
    audio, out, text = sys.argv[1], sys.argv[2], sys.argv[3]
    make_video(audio, out, text)
    print("OK ->", out)
