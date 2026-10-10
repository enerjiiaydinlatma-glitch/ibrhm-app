"""
Birebir senkron SRT uretimi.

ASR (Whisper) YOK - seslendirme metnini biz urettigimiz icin her segmentin
tam metnini ve olculmus ses suresini biliyoruz. Segment metnini kisa
alt-cue'lara bolup sureyi karakter sayisina orantili dagitiyoruz; boylece
altyazi tek dev blok halinde durmuyor.
"""
import textwrap


def _ts(sec):
    if sec < 0:
        sec = 0
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000))
    if ms == 1000:
        ms = 0
        s += 1
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _chunks(text, max_chars=84):
    """Metni ~2 satirlik (<=42 char/satir) parcalara ayir."""
    words = text.split()
    out, cur = [], ""
    for w in words:
        if len(cur) + len(w) + 1 > max_chars and cur:
            out.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        out.append(cur)
    return out or [text]


def _wrap2(s):
    lines = textwrap.wrap(s, width=42)
    return "\n".join(lines[:2]) if lines else s


def build_srt(timeline, out_path, lead_in=0.0):
    """timeline: [(text, start_sec, dur_sec), ...] segment bazinda.
    lead_in: title karti gibi segment oncesi bosluk (sn)."""
    cues = []
    for text, start, dur in timeline:
        parts = _chunks(text)
        weights = [max(len(p), 1) for p in parts]
        wsum = sum(weights)
        t = start + lead_in
        for p, wt in zip(parts, weights):
            seg = dur * wt / wsum
            cues.append((t, t + seg, _wrap2(p)))
            t += seg

    with open(out_path, "w", encoding="utf-8") as f:
        for i, (a, b, txt) in enumerate(cues, 1):
            f.write(f"{i}\n{_ts(a)} --> {_ts(b)}\n{txt}\n\n")
    return out_path, cues
