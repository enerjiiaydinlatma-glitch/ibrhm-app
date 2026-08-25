"""
YouTube kanal banner'i uretir. YouTube 2560x1440 tam boyut ister ama
metin/logo sadece 1546x423'luk "guvenli alan" icinde her cihazda
gorunur - o yuzden tum icerigi o alana sigdiriyoruz.

Kullanim:
    python generate_banner.py
Cikti: assets/banner.png
"""
import math
import os

from PIL import Image, ImageDraw, ImageFont

FONT_DIR = r"C:\Windows\Fonts"
W, H = 2560, 1440
SAFE_W, SAFE_H = 1546, 423

BG = "#12151b"
INK = "#edeef0"
INK_FAINT = "#6b7280"
ACCENT = "#5fd4c4"
NODE_COLORS = ["#5fd4c4", "#8aa8e0", "#e3a45c", "#c792ea", "#d98c8c"]

OUT_PATH = os.path.join(os.path.dirname(__file__), "assets", "banner.png")


def _font(name, size):
    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)


def _centered_text(draw, cx, y, text, font, fill):
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    draw.text((cx - w / 2, y), text, font=font, fill=fill)


def draw_node_mark(draw, cx, cy, r):
    draw.ellipse((cx - r * 0.3, cy - r * 0.3, cx + r * 0.3, cy + r * 0.3), fill=INK)
    for i, color in enumerate(NODE_COLORS):
        angle = math.pi * 2 * i / 5 - math.pi / 2
        nx, ny = cx + r * math.cos(angle), cy + r * math.sin(angle)
        draw.line((cx, cy, nx, ny), fill=INK_FAINT, width=4)
        draw.ellipse((nx - r * 0.18, ny - r * 0.18, nx + r * 0.18, ny + r * 0.18), fill=color)


def main():
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    safe_left = (W - SAFE_W) // 2
    safe_top = (H - SAFE_H) // 2
    cx = W // 2

    mark_cy = safe_top + 90
    draw_node_mark(draw, cx, mark_cy, 60)

    title_font = _font("segoeuib.ttf", 108)
    _centered_text(draw, cx, mark_cy + 90, "SIGN COUNCIL", title_font, INK)

    tagline_font = _font("segoeui.ttf", 46)
    _centered_text(draw, cx, mark_cy + 220, "5 Minds. Zero Humans.", tagline_font, ACCENT)

    handle_font = _font("segoeui.ttf", 32)
    _centered_text(draw, cx, safe_top + SAFE_H - 40, "@SignCouncil_AI", handle_font, INK_FAINT)

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    img.save(OUT_PATH)
    print(f"-> {OUT_PATH}")


if __name__ == "__main__":
    main()
