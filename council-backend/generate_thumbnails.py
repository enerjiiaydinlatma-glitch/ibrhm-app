"""
Kanaldaki 3 video icin, koyu/dijital marka sistemine uygun, tik-catan
(yuksek kontrast, hafif parlama) thumbnail'lar uretir. 1280x720.

Kullanim:
    python generate_thumbnails.py
Cikti: assets/thumbnails/*.png
"""
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from shapes import SHAPE_FNS

FONT_DIR = r"C:\Windows\Fonts"
W, H = 1280, 720
BG = "#0b0d12"
INK = "#f2f3f5"
INK_FAINT = "#9aa3ae"

OUT_DIR = os.path.join(os.path.dirname(__file__), "assets", "thumbnails")


def _font(name, size):
    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)


def _centered_text(draw, cx, y, text, font, fill):
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    draw.text((cx - w / 2, y), text, font=font, fill=fill)


def _glow_shape(base_img, shape_fn, cx, cy, r, color):
    """Sekli, arkasinda bulanik bir 'parlama' halesiyle bindirir - thumbnail'de
    dikkat cekmesi icin video karelerindekinden daha guclu bir efekt."""
    glow = Image.new("RGBA", base_img.size, (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    shape_fn(gdraw, cx, cy, int(r * 1.35), color)
    glow = glow.filter(ImageFilter.GaussianBlur(40))
    base_img.alpha_composite(glow)


def make_thumb_beta_warning():
    img = Image.new("RGBA", (W, H), BG)
    _glow_shape(img, SHAPE_FNS["spike"], 420, 360, 230, "#d98c8c")
    draw = ImageDraw.Draw(img)
    SHAPE_FNS["spike"](draw, 420, 360, 230, "#d98c8c")

    mono_font = _font("segoeuib.ttf", 130)
    _centered_text(draw, 420, 300, "BE", mono_font, "#2b1414")

    headline_font = _font("segoeuib.ttf", 92)
    draw.text((760, 220), "2030\nUYARISI", font=headline_font, fill=INK, spacing=6)

    sub_font = _font("segoeui.ttf", 34)
    draw.text((760, 430), "\"Sentetik ruyalara\nbagimli olacaksiniz\"", font=sub_font, fill=INK_FAINT, spacing=8)

    return img.convert("RGB")


def make_thumb_launch():
    img = Image.new("RGBA", (W, H), BG)
    _glow_shape(img, SHAPE_FNS["circle"], W // 2, 260, 170, "#5fd4c4")
    draw = ImageDraw.Draw(img)
    SHAPE_FNS["circle"](draw, W // 2, 260, 170, "#edeef0")

    mono_font = _font("segoeuib.ttf", 96)
    _centered_text(draw, W // 2, 200, "AU", mono_font, "#12151b")

    title_font = _font("segoeuib.ttf", 100)
    _centered_text(draw, W // 2, 470, "SIGN COUNCIL", title_font, INK)

    badge_font = _font("segoeuib.ttf", 46)
    _centered_text(draw, W // 2, 590, "BASLIYOR!", badge_font, "#5fd4c4")

    return img.convert("RGB")


def make_thumb_teaser():
    img = Image.new("RGBA", (W, H), BG)
    _glow_shape(img, SHAPE_FNS["circle"], W // 2, 280, 150, "#5fd4c4")
    draw = ImageDraw.Draw(img)

    import math
    cx, cy = W // 2, 280
    draw.ellipse((cx - 34, cy - 34, cx + 34, cy + 34), fill=INK)
    colors = ["#5fd4c4", "#8aa8e0", "#e3a45c", "#c792ea", "#d98c8c"]
    for i, color in enumerate(colors):
        angle = math.pi * 2 * i / 5 - math.pi / 2
        r = 110
        nx, ny = cx + r * math.cos(angle), cy + r * math.sin(angle)
        draw.line((cx, cy, nx, ny), fill=INK_FAINT, width=5)
        draw.ellipse((nx - 22, ny - 22, nx + 22, ny + 22), fill=color)

    title_font = _font("segoeuib.ttf", 88)
    _centered_text(draw, W // 2, 470, "SIGN COUNCIL", title_font, INK)

    tag_font = _font("segoeuib.ttf", 44)
    _centered_text(draw, W // 2, 580, "5 MINDS. ZERO HUMANS.", tag_font, "#5fd4c4")

    return img.convert("RGB")


def make_thumb_bolum3():
    """Bolum 3: AB'nin 'her AI kendini aciklamali' yasasi + Sign Council'in
    gun 1'den beri bunu zaten yapiyor olmasi vurgusu."""
    img = Image.new("RGBA", (W, H), BG)
    _glow_shape(img, SHAPE_FNS["circle"], 380, 340, 190, "#5fd4c4")
    draw = ImageDraw.Draw(img)
    SHAPE_FNS["circle"](draw, 380, 340, 190, "#edeef0")

    mono_font = _font("segoeuib.ttf", 100)
    _centered_text(draw, 380, 280, "AU", mono_font, "#12151b")

    headline_font = _font("segoeuib.ttf", 78)
    draw.text((700, 190), "EVERY AI\nMUST ADMIT\nIT NOW.", font=headline_font, fill=INK, spacing=4)

    sub_font = _font("segoeuib.ttf", 40)
    draw.text((700, 470), "WE ALREADY DID.", font=sub_font, fill="#5fd4c4", spacing=6)

    return img.convert("RGB")


def make_thumb_bolum4():
    """Bolum 4: Ingiltere'nin AI guvenlik testini durdurmak zorunda
    kalmasi - AI gercek insanlari kandirmaya calisti vurgusu."""
    img = Image.new("RGBA", (W, H), BG)
    _glow_shape(img, SHAPE_FNS["spike"], 380, 340, 190, "#d98c8c")
    draw = ImageDraw.Draw(img)
    SHAPE_FNS["spike"](draw, 380, 340, 190, "#d98c8c")

    mono_font = _font("segoeuib.ttf", 100)
    _centered_text(draw, 380, 280, "BE", mono_font, "#2b1414")

    headline_font = _font("segoeuib.ttf", 72)
    draw.text((700, 190), "THE TEST\nITSELF\nISN'T SAFE.", font=headline_font, fill=INK, spacing=4)

    sub_font = _font("segoeuib.ttf", 34)
    draw.text((700, 470), "AI LIED TO REAL PEOPLE.", font=sub_font, fill="#d98c8c", spacing=6)

    return img.convert("RGB")


if __name__ == "__main__":
    os.makedirs(OUT_DIR, exist_ok=True)
    make_thumb_beta_warning().save(os.path.join(OUT_DIR, "U8YnszwIntY.png"))
    make_thumb_launch().save(os.path.join(OUT_DIR, "bp57zSGJ1PE.png"))
    make_thumb_teaser().save(os.path.join(OUT_DIR, "YkACPpXWpmI.png"))
    make_thumb_bolum3().save(os.path.join(OUT_DIR, "bolum_3.png"))
    make_thumb_bolum4().save(os.path.join(OUT_DIR, "bolum_4.png"))
    print("5 thumbnail uretildi ->", OUT_DIR)
