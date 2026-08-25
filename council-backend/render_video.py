"""
Bir bolumun ses kliplerini (render_audio.py ciktisi) + transkript
metnini video segmentlerine, sonra tek bir bolum videosuna cevirir.

Her tur icin: ajan avatarinin uzerine o turun metnini altyazi olarak
bindirip bir kare uretir (PIL), bu kareyi sesle birlestirip bir segment
yapar (ffmpeg), sonunda tum segmentleri tek dosyada birlestirir.

Kullanim:
    python render_video.py output/bolum_0-...json
"""
import argparse
import json
import os
import shutil
import subprocess
import textwrap

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from chamber_scene import SEAT_ORDER, build_chamber_bg, detect_callout_target, make_hero_frame, make_two_shot_frame
from personas import PERSONAS

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "assets", "avatars")
FONT_DIR = r"C:\Windows\Fonts"
W, H = 1280, 720
BG = "#12151b"
ACCENT = "#5fd4c4"

# Avatarlar hep ayni merkez/yaricapta cizildi (generate_avatars.py) - halka
# efekti icin bunu tekrar kullanabiliyoruz.
AVATAR_CX, AVATAR_CY, AVATAR_R = W // 2, 190, 130

# Aura goruntunun "yildizi" - onun sahnesi diger 4 ajandan gorsel olarak
# daha parlak/on planda olsun (icerik/tartisma tarafinda herkes esit kalir,
# bu sadece gorsel vurgu).
GLOW_COLOR = {"aura": ACCENT, "alpha": None, "beta": None, "gamma": None, "delta": None}


CAPTION_MAX_HEIGHT = 260  # bu yukseklikten fazlasi asla avatarin/ismin ustune binmez
CAPTION_MARGIN = 22


_BG_RGB = tuple(int(BG.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))


def _add_glow(img, persona_key):
    """Aura'nin sahnesine, thumbnail'lerdekiyle ayni teknikle (bulanik hale)
    bir parlama ekler - onu diger 4 ajandan gorsel olarak one cikarir.

    Avatar PNG'sinin arka plani zaten duz/opak BG rengi - bunu once seffaf
    yapmadan parlamanin uzerine bindirsek gorunmez (opak katman altindaki
    her seyi kapatir). Once arka plani (renk esleşmesiyle) seffaflastirip
    sonra parlamanin ustune biniyoruz."""
    color = GLOW_COLOR.get(persona_key)
    if not color:
        return img

    rgba = img.convert("RGBA")
    pixels = rgba.load()
    # margin: avatarin kendi seklinin (daire, r=AVATAR_R) disindaki BG-renkli
    # pikselleri seffaflastir. Sadece disariyi temizlemek onemli - Aura'nin
    # ic monogram rengi ("AU" yazisi) da BG ile ayni oldugu icin, bu siniri
    # koymazsak yaziyi da yanlislikla seffaflastirir.
    r_bound_sq = (AVATAR_R + 4) ** 2
    for y in range(rgba.height):
        dy2 = (y - AVATAR_CY) ** 2
        for x in range(rgba.width):
            if (x - AVATAR_CX) ** 2 + dy2 <= r_bound_sq:
                continue
            r, g, b, a = pixels[x, y]
            if abs(r - _BG_RGB[0]) < 6 and abs(g - _BG_RGB[1]) < 6 and abs(b - _BG_RGB[2]) < 6:
                pixels[x, y] = (r, g, b, 0)

    glow = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    r = int(AVATAR_R * 2.1)
    gdraw.ellipse(
        (AVATAR_CX - r, AVATAR_CY - r, AVATAR_CX + r, AVATAR_CY + r),
        fill=color,
    )
    glow = glow.filter(ImageFilter.GaussianBlur(55))
    out = Image.new("RGBA", rgba.size, BG)
    out.alpha_composite(glow)
    out.alpha_composite(rgba)
    return out.convert("RGB")


def _caption_font(size):
    return ImageFont.truetype(os.path.join(FONT_DIR, "segoeui.ttf"), size)


def _fit_caption(text):
    """Metin uzun oldukca font kucultup satir genisligini artirarak, sabit
    yukseklikteki altyazi kutusuna sigdirmaya calisir - uzun acilis/kapanis
    cumleleri avatar karesinin/isim etiketinin ustune binmesin diye."""
    last = None
    for size in (30, 26, 22, 19, 17):
        wrap_width = 52 + (30 - size) * 2
        lines = textwrap.fill(text, width=wrap_width).split("\n")
        line_height = int(size * 1.35)
        needed = CAPTION_MARGIN * 2 + line_height * len(lines)
        last = (size, lines, line_height)
        if needed <= CAPTION_MAX_HEIGHT:
            return last
    # en kucuk fontta bile sigmadi - kutuyu tasmaya birak, en azindan kirilmaz
    return last


def make_caption_frame(persona_key, text, out_path):
    # "The Apex Chamber" sahnesi (bkz. chamber_scene.py) - 4 AI'nin
    # bagimsiz onerilerinden insa edildi, 25 Agustos 2026. Eski duz
    # BG+avatar kartindan bu sahneye gecildi.
    target = detect_callout_target(persona_key, text)
    if target:
        # Iki-kisilik sahnede sabit 5 koltugun konumlari, hedefin ekrandaki
        # (0.72w) yeriyle rastgele cakisabiliyor - hepsini gizleyip sadece
        # konusan ikiliye odaklaniyoruz.
        chamber_bg = build_chamber_bg(W, H, skip_seat=set(SEAT_ORDER))
        img = make_two_shot_frame(chamber_bg, persona_key, target, None)
    else:
        chamber_bg = build_chamber_bg(W, H, skip_seat=persona_key)
        img = make_hero_frame(chamber_bg, persona_key, None)
    draw = ImageDraw.Draw(img, "RGBA")

    size, lines, line_height = _fit_caption(text)
    font = _caption_font(size)

    bar_top = H - CAPTION_MAX_HEIGHT
    draw.rectangle((0, bar_top, W, H), fill=(0, 0, 0, 170))

    block_height = line_height * len(lines)
    y = bar_top + (CAPTION_MAX_HEIGHT - block_height) / 2
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_w = bbox[2] - bbox[0]
        draw.text(((W - line_w) / 2, y), line, font=font, fill=(255, 255, 255, 255))
        y += line_height

    img.save(out_path)


def render_turn(index, persona_key, text, audio_path, work_dir):
    frame_path = os.path.join(work_dir, f"{index:02d}_frame.png")
    make_caption_frame(persona_key, text, frame_path)

    segment_path = os.path.join(work_dir, f"{index:02d}_segment.mp4")
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-loop", "1", "-i", frame_path,
            "-i", audio_path,
            # Sabit kare artik duz durmuyor - cok yavas, surekli bir
            # yakinlasma ("nefes alma" hissi) veriyor. d=1 + -loop 1
            # kombinasyonu, ses ne kadar uzun surerse sursun dogru calisir.
            # zoompan (agir Ken Burns) + eq brightness ile hafif bir "nefes
            # alma" (pulse) hissi - glow'u statik degil canli gosteriyor,
            # format degistirmeden ucuz bir yukseltme.
            "-vf", f"scale={W*2}:{H*2},zoompan=z='min(zoom+0.0006,1.08)':d=1:s={W}x{H}:fps=25,eq=brightness='0.035*sin(2*PI*t/2.2)'",
            "-c:v", "libx264", "-tune", "stillimage",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-shortest",
            segment_path,
        ],
        check=True,
        capture_output=True,
    )
    return segment_path


def make_title_card():
    """Her bolumun basinda tekrar eden, marka tanirligini guclendiren kisa
    bir acilis kart - teaser'daki ayni stil."""
    import math

    img = Image.new("RGBA", (W, H), BG)
    draw = ImageDraw.Draw(img, "RGBA")

    cx, cy = W // 2, H // 2 - 60
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gdraw.ellipse((cx - 90, cy - 90, cx + 90, cy + 90), fill=ACCENT)
    glow = glow.filter(ImageFilter.GaussianBlur(40))
    img = Image.alpha_composite(img, glow)
    draw = ImageDraw.Draw(img, "RGBA")

    draw.ellipse((cx - 26, cy - 26, cx + 26, cy + 26), fill="#edeef0")
    colors = ["#5fd4c4", "#8aa8e0", "#e3a45c", "#c792ea", "#d98c8c"]
    for i, color in enumerate(colors):
        angle = math.pi * 2 * i / 5 - math.pi / 2
        r = 90
        nx, ny = cx + r * math.cos(angle), cy + r * math.sin(angle)
        draw.line((cx, cy, nx, ny), fill="#6b7280", width=3)
        draw.ellipse((nx - 16, ny - 16, nx + 16, ny + 16), fill=color)

    title_font = ImageFont.truetype(os.path.join(FONT_DIR, "segoeuib.ttf"), 74)
    bbox = draw.textbbox((0, 0), "SIGN COUNCIL", font=title_font)
    draw.text((cx - (bbox[2] - bbox[0]) / 2, cy + 120), "SIGN COUNCIL", font=title_font, fill="#edeef0")

    tag_font = ImageFont.truetype(os.path.join(FONT_DIR, "segoeui.ttf"), 32)
    bbox = draw.textbbox((0, 0), "5 Minds. Zero Humans.", font=tag_font)
    draw.text((cx - (bbox[2] - bbox[0]) / 2, cy + 205), "5 Minds. Zero Humans.", font=tag_font, fill=ACCENT)

    return img.convert("RGB")


def render_title_segment(work_dir):
    frame_path = os.path.join(work_dir, "00_title_frame.png")
    make_title_card().save(frame_path)
    segment_path = os.path.join(work_dir, "00_title_segment.mp4")
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-loop", "1", "-t", "2.5", "-i", frame_path,
            # Sessiz ses parcasi ekleniyor - concat demuxer'in "-c copy"
            # ile birlestirebilmesi icin tum segmentlerin ses akisi olmasi
            # gerekiyor, yoksa turlarin sesiyle format uyusmuyor.
            "-f", "lavfi", "-t", "2.5", "-i", "anullsrc=r=44100:cl=stereo",
            "-vf", "fade=t=out:st=2:d=0.5",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "25",
            "-c:a", "aac", "-b:a", "192k",
            segment_path,
        ],
        check=True,
        capture_output=True,
    )
    return segment_path


def render(transcript_path):
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg bulunamadi - once kurun")

    with open(transcript_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    episode_name = os.path.splitext(os.path.basename(transcript_path))[0]
    audio_dir = os.path.join(os.path.dirname(__file__), "output", "audio", episode_name)
    work_dir = os.path.join(os.path.dirname(__file__), "output", "video", episode_name)
    os.makedirs(work_dir, exist_ok=True)

    segments = [render_title_segment(work_dir)]
    for i, turn in enumerate(data["transcript"]):
        speaker = turn["speaker"]
        text = turn["text"]
        audio_path = os.path.join(audio_dir, f"{i:02d}_{speaker}.mp3")

        if not os.path.exists(audio_path):
            print(f"[{i:02d}] {PERSONAS[speaker]['display_name']}: sesi yok, video atlandi")
            continue

        print(f"[{i:02d}] {PERSONAS[speaker]['display_name']}: kare + segment uretiliyor...")
        segments.append(render_turn(i, speaker, text, audio_path, work_dir))

    if not segments:
        print("Hicbir segment uretilemedi - once render_audio.py calistirin.")
        return

    concat_list = os.path.join(work_dir, "_concat.txt")
    with open(concat_list, "w", encoding="utf-8") as f:
        for s in segments:
            f.write(f"file '{os.path.abspath(s)}'\n")

    final_path = os.path.join(work_dir, f"{episode_name}.mp4")
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", concat_list, "-c", "copy", final_path,
        ],
        check=True,
        capture_output=True,
    )
    print(f"\nBolum videosu -> {final_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("transcript", help="run_episode.py ciktisi olan JSON dosyasi")
    args = parser.parse_args()
    render(args.transcript)
