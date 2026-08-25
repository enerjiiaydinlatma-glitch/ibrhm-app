"""
The Apex Chamber - Sign Council'in gorsel "studyosu". 4 farkli LLM
saglayicisina (OpenAI, Anthropic, Groq, Gemini) ayri ayri sorulan studyo
tasarim onerilerinin ortak noktalarindan insa edildi (bkz. ask_studio_design.py,
25 Agustos 2026 - hepsi bagimsiz olarak ayni 6 ogeye isaret etti):

  1. Merkezi "meclis" duzeni - 5 ajan kendi kaidesinde, konusan one cikiyor
  2. Perspektifle uzayan sutunlar (yakinda net, uzakta bulanik) - olcek illuzyonu
  3. Tepeden dusen volumetrik spot isik huzmeleri
  4. Havada asili merkezi LED panel - bolumun konusuyla ilgili gorsel/ikon
  5. Yansiyan zemin - hibrit fiziksel/sanal his
  6. Kamera: yavas push-in + konusanin altinda nabiz gibi parlayan halka

Gercek zamanli 3D/XR motoru YOK - bu tamamen PIL katmanlama + ffmpeg
kamera hareketiyle yaratilan bir illuzyon (bkz. ask_studio_design.py'deki
teknik kisit notu).
"""
import math
import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from generate_avatars import CARDS
from shapes import SHAPE_FNS, SHAPE_TEXT_OFFSET_Y

FONT_DIR = r"C:\Windows\Fonts"
BG = "#0a0c10"
ACCENT = "#5fd4c4"

# Meclis'teki 5 sabit koltuk sirasi (soldan saga) - "Aura merkezde/yuksekte"
# onerisi: Aura ortada, digerleri iki yaninda.
SEAT_ORDER = ["alpha", "beta", "aura", "gamma", "delta"]


def _font(name, size):
    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)


def _centered_text(draw, cx, y, text, font, fill):
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    draw.text((cx - w / 2, y), text, font=font, fill=fill)


def _draw_columns(draw, w, h):
    """Perspektifle uzayan sutun sildueleri - yakinda net/genis, uzakta
    ince/bulanik. Goz otomatik olcek cikarimi yapiyor (Claude'un onerisi,
    ask_studio_design.py)."""
    # Sol ve sag kenardan merkeze dogru, kucule kucule 7'ser sutun.
    for side in (-1, 1):
        for i in range(7):
            t = i / 6  # 0 = en disardaki/en yakin, 1 = merkeze en yakin/en uzak
            x = w / 2 + side * (w / 2 + 40) * (1 - t) ** 1.6
            col_w = 70 * (1 - t) + 6
            shade = int(14 + 10 * (1 - t))
            draw.rectangle((x - col_w / 2, 0, x + col_w / 2, h), fill=(shade, shade + 3, shade + 8))
            draw.line((x, 0, x, h), fill=(shade + 18, shade + 24, shade + 32), width=max(1, int(2 * (1 - t))))


def _draw_floor(img, w, h, horizon_y):
    """Zemin: perspektif izgara + hafif yansima hissi (ust katmanin
    ters cevrilip dusuk opacity ile alta bindirilmesi)."""
    draw = ImageDraw.Draw(img, "RGBA")
    cx = w / 2
    grid_color = (95, 212, 196, 40)
    for i in range(-8, 9):
        x_top = cx + i * 18
        x_bottom = cx + i * 160
        draw.line((x_top, horizon_y, x_bottom, h), fill=grid_color, width=1)
    for r in range(1, 6):
        y = horizon_y + r * (h - horizon_y) / 6
        spread = (y - horizon_y) / (h - horizon_y) * (w * 0.55)
        draw.line((cx - spread, y, cx + spread, y), fill=grid_color, width=1)

    # Yansima: ust yariyi (gokyuzu/sutunlar) ters cevirip dusuk opacityle
    # zeminin ustune bindir - "hibrit fiziksel" his (Gemini onerisi).
    reflect_src = img.crop((0, 0, w, horizon_y)).transpose(Image.FLIP_TOP_BOTTOM)
    reflect_src = reflect_src.resize((w, h - horizon_y))
    reflect_src.putalpha(35)
    img.alpha_composite(reflect_src, (0, horizon_y))


def _draw_led_panel(draw, cx, y, w, h, glow_color):
    """Havada asili merkezi LED panel - dekor + ileride gercek haber
    gorseli/ikonu icin yer tutucu cerceve."""
    draw.rectangle((cx - w / 2, y, cx + w / 2, y + h), outline=glow_color + (160,), width=2)
    draw.rectangle((cx - w / 2 + 6, y + 6, cx + w / 2 - 6, y + h - 6), fill=(10, 14, 18, 210))
    # Asma kablosu
    draw.line((cx, 0, cx, y), fill=glow_color + (90,), width=2)
    draw.line((cx - w / 2 + 14, 0, cx - w / 2 + 14, y), fill=glow_color + (60,), width=1)
    draw.line((cx + w / 2 - 14, 0, cx + w / 2 - 14, y), fill=glow_color + (60,), width=1)


def build_chamber_bg(w, h, seat_r=None, seat_cy=None, skip_seat=None,
                      horizon_ratio=0.60, panel_w_ratio=0.22, panel_h_ratio=0.16,
                      panel_h_basis="h"):
    """Sahnenin sabit mimarisi - bolum boyunca degismiyor, bir kere
    uretilip her tur icin yeniden kullanilabilir (performans).
    skip_seat: o an 'kahraman' olarak on plana cikan ajanin sonuk koltugu
    cizilmez - aksi halde buyuk sekil ile arkasindaki sonuk kopyasi
    cakisip tuhaf duruyor (ilk testte tespit edildi).
    Dikey (Shorts, 1080x1920) formatta panel_h_basis='w' kullanilmali -
    yoksa LED panel h*0.16 ile orantisiz derecede uzun cikiyor."""
    img = Image.new("RGB", (w, h), BG)
    draw = ImageDraw.Draw(img, "RGBA")

    horizon_y = int(h * horizon_ratio)
    _draw_columns(draw, w, h)

    # Ust ortam isigi (cok hafif, genel atmosfer)
    ambient = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    adraw = ImageDraw.Draw(ambient)
    adraw.ellipse((w * 0.15, -h * 0.3, w * 0.85, horizon_y), fill=(255, 255, 255, 10))
    ambient = ambient.filter(ImageFilter.GaussianBlur(120))
    img = Image.alpha_composite(img.convert("RGBA"), ambient)

    img = img.convert("RGBA")
    _draw_floor(img, w, h, horizon_y)
    draw = ImageDraw.Draw(img, "RGBA")

    # LED panel (tavanda asili)
    panel_h_base = w if panel_h_basis == "w" else h
    _draw_led_panel(draw, w / 2, int(h * 0.06), int(w * panel_w_ratio), int(panel_h_base * panel_h_ratio), (95, 212, 196))

    # Sabit 5 koltuk - kucuk, sonuk, arka planda (Aura ortada/yuksekte)
    if seat_r is None:
        seat_r = int(h * 0.055)
    if seat_cy is None:
        seat_cy = int(h * 0.40)
    n = len(SEAT_ORDER)
    spacing = w * 0.62 / (n - 1)
    start_x = w / 2 - spacing * (n - 1) / 2
    skip_set = {skip_seat} if isinstance(skip_seat, str) else set(skip_seat or ())
    for i, key in enumerate(SEAT_ORDER):
        if key in skip_set:
            continue
        spec = CARDS[key]
        x = start_x + spacing * i
        y = seat_cy - (seat_r * 0.6 if key == "aura" else 0)  # Aura hafifce yuksekte
        # Kaide
        draw.polygon(
            [(x - seat_r * 0.9, y + seat_r * 0.9), (x + seat_r * 0.9, y + seat_r * 0.9),
             (x + seat_r * 0.6, y + seat_r * 1.5), (x - seat_r * 0.6, y + seat_r * 1.5)],
            fill=(16, 20, 26, 255),
        )
        # Sonuk sekil (dusuk opacity, "koltukta oturuyor" hissi)
        fill_rgba = tuple(int(spec["fill"].lstrip("#")[j:j+2], 16) for j in (0, 2, 4)) + (70,)
        SHAPE_FNS[spec["shape"]](draw, x, y, seat_r, fill_rgba)

    return img.convert("RGB")


def _glow_at(base_rgba, cx, cy, r, color_rgb, blur=70, alpha=255):
    glow = Image.new("RGBA", base_rgba.size, (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gdraw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=color_rgb + (alpha,))
    glow = glow.filter(ImageFilter.GaussianBlur(blur))
    base_rgba.alpha_composite(glow)


def make_hero_frame(chamber_bg, persona_key, out_path, hero_cx_ratio=0.5, hero_cy_ratio=0.40, hero_r_ratio=0.145, r_basis="h"):
    """Sahit sahnenin uzerine, o an konusan ajani buyuk/aydinlatilmis
    olarak on plana cikartir - 'biri one cikip spota giriyor' hissi."""
    w, h = chamber_bg.size
    img = chamber_bg.convert("RGBA").copy()
    draw = ImageDraw.Draw(img, "RGBA")

    spec = CARDS[persona_key]
    fill_rgb = tuple(int(spec["fill"].lstrip("#")[j:j+2], 16) for j in (0, 2, 4))
    r_base = w if r_basis == "w" else h
    cx, cy, r = int(w * hero_cx_ratio), int(h * hero_cy_ratio), int(r_base * hero_r_ratio)

    # Tepeden volumetrik spot konisi
    spot = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(spot)
    sdraw.polygon([(cx - r * 0.5, 0), (cx + r * 0.5, 0), (cx + r * 1.9, cy + r * 1.4), (cx - r * 1.9, cy + r * 1.4)],
                  fill=fill_rgb + (26,))
    spot = spot.filter(ImageFilter.GaussianBlur(35))
    img.alpha_composite(spot)
    draw = ImageDraw.Draw(img, "RGBA")

    # Kahraman parlamasi + sekil
    _glow_at(img, cx, cy, int(r * 1.7), fill_rgb, blur=60, alpha=150)
    SHAPE_FNS[spec["shape"]](draw, cx, cy, r, spec["fill"])

    mono_font = _font("segoeuib.ttf", int(r * 0.62))
    text_y = cy - int(r * 0.42) + int(SHAPE_TEXT_OFFSET_Y[spec["shape"]] * (r / 130))
    _centered_text(draw, cx, text_y, spec["monogram"], mono_font, spec["text_on_fill"])

    name_font = _font("segoeuib.ttf", int(r * 0.34))
    _centered_text(draw, cx, cy + r + int(r * 0.18), spec["name"], name_font, "#edeef0")

    # Aydinlik zemin havuzu (spot'un zeminde biraktigi elips)
    pool = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(pool)
    pdraw.ellipse((cx - r * 1.6, cy + r * 1.2, cx + r * 1.6, cy + r * 2.0), fill=fill_rgb + (30,))
    pool = pool.filter(ImageFilter.GaussianBlur(20))
    img.alpha_composite(pool)

    img = img.convert("RGB")
    if out_path:
        img.save(out_path)
    return img


def make_two_shot_frame(chamber_bg, speaker_key, target_key, out_path, r_basis="h",
                         cy_ratio=0.40, r_main_ratio=0.125, r_target_ratio=0.105,
                         cx_speaker_ratio=0.30, cx_target_ratio=0.72):
    """Aura (ya da baska bir ajan) birini DOGRUDAN cagirdiginda: konusan
    solda buyuk, hedef alinan sagda one cikip aydinlaniyor, aralarinda
    ince bir 'isaret' isik cizgisi beliriyor - yuz/karakter olmadan
    'sana soruyorum' enerjisi (kullanicinin istedigi 'sen Beta neden
    boylesin' hissi, bkz. sohbet, 25 Agustos 2026)."""
    w, h = chamber_bg.size
    img = chamber_bg.convert("RGBA").copy()
    draw = ImageDraw.Draw(img, "RGBA")

    speaker_spec = CARDS[speaker_key]
    target_spec = CARDS[target_key]
    speaker_rgb = tuple(int(speaker_spec["fill"].lstrip("#")[j:j+2], 16) for j in (0, 2, 4))
    target_rgb = tuple(int(target_spec["fill"].lstrip("#")[j:j+2], 16) for j in (0, 2, 4))

    r_base = w if r_basis == "w" else h
    cy = int(h * cy_ratio)
    r_main = int(r_base * r_main_ratio)
    r_target = int(r_base * r_target_ratio)
    cx_speaker = int(w * cx_speaker_ratio)
    cx_target = int(w * cx_target_ratio)

    # Isaret isik cizgisi (konusandan hedefe) - once cizilir, sekiller ustune biner
    beam = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(beam)
    bdraw.line((cx_speaker + r_main, cy - r_main * 0.2, cx_target - r_target, cy - r_target * 0.1),
               fill=speaker_rgb + (130,), width=4)
    beam = beam.filter(ImageFilter.GaussianBlur(3))
    img.alpha_composite(beam)
    draw = ImageDraw.Draw(img, "RGBA")

    # Konusan (sol, ana aydinlatma)
    _glow_at(img, cx_speaker, cy, int(r_main * 1.6), speaker_rgb, blur=55, alpha=140)
    SHAPE_FNS[speaker_spec["shape"]](draw, cx_speaker, cy, r_main, speaker_spec["fill"])
    mono_font = _font("segoeuib.ttf", int(r_main * 0.6))
    _centered_text(draw, cx_speaker, cy - int(r_main * 0.4), speaker_spec["monogram"], mono_font, speaker_spec["text_on_fill"])
    name_font = _font("segoeuib.ttf", int(r_main * 0.32))
    _centered_text(draw, cx_speaker, cy + r_main + int(r_main * 0.15), speaker_spec["name"], name_font, "#edeef0")

    # Hedef (sag, "cagrildi" aydinlatmasi - biraz daha kucuk ama net vurgulu)
    _glow_at(img, cx_target, cy, int(r_target * 1.7), target_rgb, blur=55, alpha=160)
    SHAPE_FNS[target_spec["shape"]](draw, cx_target, cy, r_target, target_spec["fill"])
    mono_font2 = _font("segoeuib.ttf", int(r_target * 0.6))
    _centered_text(draw, cx_target, cy - int(r_target * 0.4), target_spec["monogram"], mono_font2, target_spec["text_on_fill"])
    name_font2 = _font("segoeuib.ttf", int(r_target * 0.32))
    _centered_text(draw, cx_target, cy + r_target + int(r_target * 0.15), target_spec["name"], name_font2, "#edeef0")

    img = img.convert("RGB")
    if out_path:
        img.save(out_path)
    return img


# Aura'nin bir turu, baska bir ajani DOGRUDAN cagirdiginda metin genelde
# "İsim, ..." ile basliyor (TURN_PLAN direktifleri boyle kurgulaniyor,
# bkz. episodes/*.py). Tam veri akisini (turn_plan -> transcript) yeniden
# kurmak yerine, bu guvenilir yazi kalibindan hedefi cikariyoruz.
def detect_callout_target(speaker_key, text):
    if speaker_key not in ("aura",):
        return None
    for key, spec in CARDS.items():
        if key == speaker_key:
            continue
        name = spec["name"].capitalize()
        if text.strip().startswith(name + ","):
            return key
    return None
