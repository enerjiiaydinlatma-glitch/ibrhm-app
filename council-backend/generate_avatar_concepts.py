"""
Karsilastirma sayfasi: mevcut "daire + monogram" stiliyle, "geometrik
kisilik formu" alternatifini yan yana gosterir. Hicbir API anahtari
gerektirmez - sadece bir tasarim tartismasi girdisi.

Kullanim:
    python generate_avatar_concepts.py
Cikti: assets/avatar_concepts.png
"""
import os

from PIL import Image, ImageDraw, ImageFont

from shapes import SHAPE_FNS

OUT_DIR = os.path.join(os.path.dirname(__file__), "assets")
FONT_DIR = r"C:\Windows\Fonts"

BG = "#12151b"
INK = "#edeef0"
INK_FAINT = "#6b7280"
PANEL = "#1a1f27"

SPECS = {
    "aura": {"color": "#edeef0", "name": "AURA", "shape": "circle"},
    "alpha": {"color": "#e3a45c", "name": "ALPHA", "shape": "triangle"},
    "beta": {"color": "#d98c8c", "name": "BETA", "shape": "spike"},
    "gamma": {"color": "#c792ea", "name": "GAMMA", "shape": "squircle"},
    "delta": {"color": "#8aa8e0", "name": "DELTA", "shape": "hexagon"},
}

COL_W = 256
ROW_H = 320
W = COL_W * 5
H = ROW_H * 2 + 90


def _font(name, size):
    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)


def _centered_text(draw, cx, y, text, font, fill):
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    draw.text((cx - w / 2, y), text, font=font, fill=fill)


def render():
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    label_font = _font("segoeuib.ttf", 26)
    name_font = _font("segoeuib.ttf", 30)
    caption_font = _font("segoeui.ttf", 22)

    _centered_text(draw, W // 2, 20, "A: MEVCUT (daire + monogram)", label_font, INK_FAINT)
    _centered_text(draw, W // 2, ROW_H + 55, "B: ONERI (geometrik kisilik formu)", label_font, INK_FAINT)

    row_a_y = 95 + ROW_H // 2 - 40
    row_b_y = 95 + ROW_H + ROW_H // 2 - 40

    for i, (key, spec) in enumerate(SPECS.items()):
        cx = COL_W * i + COL_W // 2

        # A satiri: hepsi daire (mevcut stil)
        SHAPE_FNS["circle"](draw, cx, row_a_y, 70, spec["color"])
        _centered_text(draw, cx, row_a_y + 90, spec["name"], name_font, INK)

        # B satiri: kisiliğe gore farkli form
        SHAPE_FNS[spec["shape"]](draw, cx, row_b_y, 70, spec["color"])
        _centered_text(draw, cx, row_b_y + 90, spec["name"], name_font, INK)

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, "avatar_concepts.png")
    img.save(out_path)
    print(f"-> {out_path}")


if __name__ == "__main__":
    render()
