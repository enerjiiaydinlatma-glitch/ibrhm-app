"""Receipt karti cizimi (PIL). Model gorseli YOK: dogrulanmis alinti + kaynak seridi + hukum damgasi."""
import os

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
BG, INK, MUTED = "#12151b", "#edeef0", "#8b96a2"
COLORS = {"CLAIM": "#5fd4c4", "EVIDENCE": "#6aa9ff", "THIRD": "#b79cff", "VERDICT": "#ffb020"}
FONT_DIR = r"C:\Windows\Fonts"
FALLBACKS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"]


def font(size, name="segoeuib.ttf"):
    for p in [os.path.join(FONT_DIR, name)] + FALLBACKS:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


def wrap(d, text, f, max_w):
    lines, cur = [], ""
    for w in text.split():
        t = (cur + " " + w).strip()
        if d.textlength(t, font=f) <= max_w:
            cur = t
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def color_for(label):
    u = label.upper()
    for k, c in COLORS.items():
        if k in u:
            return c
    return COLORS["EVIDENCE"]


def render(spec, who, out_path):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    d.text((48, 56), "SIGN COUNCIL", font=font(38), fill=INK)
    d.text((48, 108), (who or "").upper(), font=font(28), fill="#78e0c4")
    label = (spec.get("label") or "").upper()
    col = color_for(label)
    lf = font(40)
    tw = d.textlength(label, font=lf)
    d.rounded_rectangle((W // 2 - tw / 2 - 34, 250, W // 2 + tw / 2 + 34, 250 + 40 + 36), radius=999, fill=col)
    d.text((W // 2, 250 + 38), label, font=lf, fill="#0b0d12", anchor="mm")

    blocks = []
    for q in spec.get("quotes", []):
        for size in (84, 72, 62, 54):
            f = font(size)
            ls = wrap(d, "\u201c" + q + "\u201d", f, W - 150)
            if len(ls) <= 6:
                break
        blocks.append((f, ls))
    stamp = spec.get("stamp", "")
    total = sum(len(ls) * int(f.size * 1.3) + 50 for f, ls in blocks) + (230 if stamp else 0)
    y = max(420, (H - total) // 2)
    for f, ls in blocks:
        for ln in ls:
            d.text((W // 2, y), ln, font=f, fill=INK, anchor="ma")
            y += int(f.size * 1.3)
        y += 50
    if stamp:
        sf = font(78)
        sw = d.textlength(stamp, font=sf)
        top = y + 30
        d.rounded_rectangle((W // 2 - sw / 2 - 44, top, W // 2 + sw / 2 + 44, top + 150), radius=18, outline=col, width=10)
        d.text((W // 2, top + 75), stamp, font=sf, fill=col, anchor="mm")
    d.rectangle((0, H - 190, W, H), fill="#0b0d12")
    d.text((48, H - 160), "SOURCE", font=font(26), fill=MUTED)
    sf2 = font(34)
    for i, ln in enumerate(wrap(d, spec.get("source", ""), sf2, W - 96)[:2]):
        d.text((48, H - 118 + i * 44), ln, font=sf2, fill=INK)
    img.save(out_path)
    return out_path
