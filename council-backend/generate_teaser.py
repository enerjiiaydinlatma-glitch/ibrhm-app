"""
YouTube (Shorts, dikey 1080x1920) icin kisa bir tanitim videosu uretir.
"5 Minds. Zero Humans." konseptini ve 5 ajanin gorsel kimligini tanitir -
ANCAK hicbir AI tarafindan uretilmis diyalog ICERMEZ (Alpha/Beta/Gamma
API anahtarlari henuz yok) - sadece marka/konsept duyurusu.

Muzik: telif riski olmasin diye hazir bir parca degil, tamamen
sentezlenmis (ffmpeg sine) bir ambiyans tonu kullanildi.

Kullanim:
    python generate_teaser.py
Cikti: output/teaser/sign_council_teaser.mp4
"""
import os
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageFont

from shapes import SHAPE_FNS

FONT_DIR = r"C:\Windows\Fonts"
W, H = 1080, 1920
BG = "#12151b"
INK = "#edeef0"
INK_FAINT = "#6b7280"
ACCENT = "#5fd4c4"

WORK_DIR = os.path.join(os.path.dirname(__file__), "output", "teaser")

CARDS = [
    ("alpha", {"monogram": "AL", "shape": "triangle", "fill": "#e3a45c", "text_on_fill": "#241705",
                "name": "ALPHA", "role": "Analytical / Economics",
                "tagline": "Looks at numbers, not feelings."}),
    ("beta", {"monogram": "BE", "shape": "spike", "fill": "#d98c8c", "text_on_fill": "#2b1414",
               "name": "BETA", "role": "Rebel / Realist",
               "tagline": "Asks what no one else will."}),
    ("gamma", {"monogram": "GA", "shape": "squircle", "fill": "#c792ea", "text_on_fill": "#1f1329",
                "name": "GAMMA", "role": "Ethics / Philosophy",
                "tagline": "The mind that won't forget humanity."}),
    ("delta", {"monogram": "DE", "shape": "hexagon", "fill": "#8aa8e0", "text_on_fill": "#111a2e",
                "name": "DELTA", "role": "Synthesis / Infrastructure",
                "tagline": "Turns chaos into clarity."}),
    ("aura", {"monogram": "AU", "shape": "circle", "fill": "#edeef0", "text_on_fill": "#12151b",
               "name": "AURA", "role": "Council Lead",
               "tagline": "Leads the council, delivers the synthesis."}),
]

TITLE_DUR = 2.5
AVATAR_DUR = 1.8
CLOSE_DUR = 3.5
FPS = 30


def _font(name, size):
    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)


def _centered_text(draw, cx, y, text, font, fill):
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    draw.text((cx - w / 2, y), text, font=font, fill=fill)


def draw_node_mark(draw, cx, cy, r=90):
    import math
    draw.ellipse((cx - 26, cy - 26, cx + 26, cy + 26), fill=INK)
    colors = ["#5fd4c4", "#8aa8e0", "#e3a45c", "#c792ea", "#d98c8c"]
    for i, color in enumerate(colors):
        angle = math.pi * 2 * i / 5 - math.pi / 2
        nx, ny = cx + r * 0.9 * math.cos(angle), cy + r * 0.9 * math.sin(angle)
        draw.line((cx, cy, nx, ny), fill=INK_FAINT, width=3)
        draw.ellipse((nx - 16, ny - 16, nx + 16, ny + 16), fill=color)


def make_title_card():
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    cy_mark = H // 2 - 260
    draw_node_mark(draw, W // 2, cy_mark)

    title_font = _font("segoeuib.ttf", 96)
    _centered_text(draw, W // 2, cy_mark + 160, "SIGN COUNCIL", title_font, INK)

    tagline_font = _font("segoeui.ttf", 44)
    _centered_text(draw, W // 2, cy_mark + 280, "5 Minds. Zero Humans.", tagline_font, ACCENT)

    return img


def make_avatar_card(persona_key, spec):
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    cx, cy, r = W // 2, H // 2 - 160, 260
    SHAPE_FNS[spec["shape"]](draw, cx, cy, r, spec["fill"])

    mono_font = _font("segoeuib.ttf", 150)
    offset = 24 if spec["shape"] == "triangle" else 0
    _centered_text(draw, cx, cy - 95 + offset, spec["monogram"], mono_font, spec["text_on_fill"])

    name_font = _font("segoeuib.ttf", 110)
    _centered_text(draw, cx, cy + r + 60, spec["name"], name_font, INK)

    role_font = _font("segoeui.ttf", 46)
    _centered_text(draw, cx, cy + r + 190, spec["role"].upper(), role_font, INK_FAINT)

    # Alt bant: kisa tanitim cumlesi - render_video.py'deki altyazi bandiyla
    # ayni gorsel dil (yayinin gercek altyazi stiliyle tutarli).
    band_top = H - 260
    ImageDraw.Draw(img, "RGBA").rectangle((0, band_top, W, H), fill=(0, 0, 0, 170))
    tagline_font = _font("segoeui.ttf", 52)
    _centered_text(draw, cx, band_top + 95, spec["tagline"], tagline_font, INK)

    return img


def make_closing_card():
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    headline_font = _font("segoeuib.ttf", 100)
    _centered_text(draw, W // 2, H // 2 - 220, "COMING SOON", headline_font, INK)

    sub_font = _font("segoeui.ttf", 42)
    _centered_text(draw, W // 2, H // 2 - 70, "5 minds. Zero humans.", sub_font, INK_FAINT)
    _centered_text(draw, W // 2, H // 2 - 15, "Aura leads the council.", sub_font, INK_FAINT)

    handle_font = _font("segoeuib.ttf", 40)
    _centered_text(draw, W // 2, H - 220, "@SignCouncil_AI", handle_font, ACCENT)

    return img


def render_segment(image, duration, out_path):
    frame_path = out_path.replace(".mp4", "_frame.png")
    image.save(frame_path)
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-loop", "1", "-t", str(duration), "-i", frame_path,
            "-r", str(FPS), "-c:v", "libx264", "-pix_fmt", "yuv420p",
            out_path,
        ],
        check=True, capture_output=True,
    )


def main():
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg bulunamadi")

    os.makedirs(WORK_DIR, exist_ok=True)

    segments = []
    render_segment(make_title_card(), TITLE_DUR, os.path.join(WORK_DIR, "00_title.mp4"))
    segments.append(os.path.join(WORK_DIR, "00_title.mp4"))

    for i, (key, spec) in enumerate(CARDS, start=1):
        path = os.path.join(WORK_DIR, f"{i:02d}_{key}.mp4")
        render_segment(make_avatar_card(key, spec), AVATAR_DUR, path)
        segments.append(path)

    close_path = os.path.join(WORK_DIR, "99_close.mp4")
    render_segment(make_closing_card(), CLOSE_DUR, close_path)
    segments.append(close_path)

    concat_list = os.path.join(WORK_DIR, "_concat.txt")
    with open(concat_list, "w", encoding="utf-8") as f:
        for s in segments:
            f.write(f"file '{os.path.abspath(s)}'\n")

    silent_path = os.path.join(WORK_DIR, "_silent.mp4")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list, "-c", "copy", silent_path],
        check=True, capture_output=True,
    )

    total_dur = TITLE_DUR + AVATAR_DUR * len(CARDS) + CLOSE_DUR
    final_path = os.path.join(WORK_DIR, "sign_council_teaser.mp4")

    # Sentezlenmis, telifsiz bir ambiyans tonu (iki sinuzoid katmani, hazir
    # muzik degil) + loudnorm ile YouTube'un hedefledigi seviyeye (~-14 LUFS)
    # normalize edip tum video icin yumusak giris/cikis (fade).
    # NOT: ilk denemede sadece volume=0.12 ile cikan ses -40dB civarinda
    # kalip pratikte duyulmuyordu - loudnorm bunu duzeltiyor.
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", silent_path,
            "-f", "lavfi", "-i", f"sine=frequency=110:duration={total_dur}",
            "-f", "lavfi", "-i", f"sine=frequency=165:duration={total_dur}",
            "-filter_complex",
            f"[0:v]fade=t=in:st=0:d=0.5,fade=t=out:st={total_dur - 0.5}:d=0.5[v];"
            f"[1:a][2:a]amix=inputs=2:duration=longest:weights=1 0.6[amix];"
            f"[amix]loudnorm=I=-14:TP=-1.5:LRA=11,"
            f"afade=t=in:st=0:d=1,afade=t=out:st={total_dur - 1}:d=1[a]",
            "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            final_path,
        ],
        check=True, capture_output=True,
    )
    print(f"Teaser hazir -> {final_path} ({total_dur:.1f}s)")


if __name__ == "__main__":
    main()
