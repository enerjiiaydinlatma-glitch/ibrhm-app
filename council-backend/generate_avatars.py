"""
Her ajan icin sabit, kart-tarzi bir avatar goruntusu uretir (1280x720,
video karesiyle ayni oran). API anahtari gerektirmez - Segment 05'teki
"gorsel katman" karari burada uygulaniyor: dudak-senkron animasyon degil,
renk kodlu sabit kart + isim etiketi.

Renkler Sign Council Rundown'daki node renkleriyle birebir ayni (marka
tutarliligi). Kullanim:
    python generate_avatars.py
Cikti: assets/avatars/<persona>.png
"""
import os

from PIL import Image, ImageDraw, ImageFont

from shapes import SHAPE_FNS, SHAPE_TEXT_OFFSET_Y

OUT_DIR = os.path.join(os.path.dirname(__file__), "assets", "avatars")
FONT_DIR = r"C:\Windows\Fonts"

BG = "#12151b"
INK = "#edeef0"
INK_FAINT = "#6b7280"

# Karakter/maskot degil, kisilik-formu (bkz. Sign Council Rundown, gorsel
# katman karari): Alpha'nin ucgeni mantik/keskinligi, Beta'nin dikeni
# surtunme/itirazi, Gamma'nin yumusak koseli formu insani tarafi, Delta'nin
# altigeni yapi/sentezi, Aura'nin dairesi merkezi konumu temsil ediyor.
CARDS = {
    "aura": {"monogram": "AU", "shape": "circle", "fill": "#edeef0", "text_on_fill": "#12151b",
              "name": "AURA", "role": "Konsey Lideri"},
    "alpha": {"monogram": "AL", "shape": "triangle", "fill": "#e3a45c", "text_on_fill": "#241705",
              "name": "ALPHA", "role": "Analitik / Ekonomi"},
    "beta": {"monogram": "BE", "shape": "spike", "fill": "#d98c8c", "text_on_fill": "#2b1414",
              "name": "BETA", "role": "Asi / Gercekci"},
    "gamma": {"monogram": "GA", "shape": "squircle", "fill": "#c792ea", "text_on_fill": "#1f1329",
              "name": "GAMMA", "role": "Etik / Felsefe"},
    "delta": {"monogram": "DE", "shape": "hexagon", "fill": "#8aa8e0", "text_on_fill": "#111a2e",
              "name": "DELTA", "role": "Sentez / Altyapi"},
}

W, H = 1280, 720


def _font(name, size):
    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)


def _centered_text(draw, cx, y, text, font, fill):
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    draw.text((cx - w / 2, y), text, font=font, fill=fill)


def make_card(persona_key, spec):
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # NOT: render_video.py altyazi kutusu icin alttan CAPTION_MAX_HEIGHT
    # (260px) kadar sabit yer ayirir - bu yuzden isim/rol her zaman ustte,
    # o bandin disinda kalmali (aksi halde konusma sirasinda alta biner).
    cx, cy, r = W // 2, 190, 130
    SHAPE_FNS[spec["shape"]](draw, cx, cy, r, spec["fill"])

    mono_font = _font("segoeuib.ttf", 82)
    text_y = cy - 54 + SHAPE_TEXT_OFFSET_Y[spec["shape"]]
    _centered_text(draw, cx, text_y, spec["monogram"], mono_font, spec["text_on_fill"])

    name_font = _font("segoeuib.ttf", 60)
    _centered_text(draw, cx, cy + r + 30, spec["name"], name_font, INK)

    role_font = _font("segoeui.ttf", 26)
    _centered_text(draw, cx, cy + r + 100, spec["role"].upper(), role_font, INK_FAINT)

    # Sign Council'in node-grafik kimligini hatirlatan ince alt cizgi
    draw.rectangle((cx - 50, cy + r + 145, cx + 50, cy + r + 149), fill=spec["fill"])

    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, f"{persona_key}.png")
    img.save(out_path)
    print(f"{persona_key} -> {out_path}")


if __name__ == "__main__":
    for key, spec in CARDS.items():
        make_card(key, spec)
