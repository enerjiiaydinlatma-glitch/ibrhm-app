"""
Bir bolumun transkriptinden, ard arda gelen 2 FARKLI ajanin (Aura haric -
o moderator, "catisan" taraf degil) birbirine cevap verdigi anlari bulup
dikey (1080x1920) "catisma" Shorts'lari uretir. Ayni ses klipleri
(render_audio.py ciktisi) yeniden kullanilir - yeniden TTS uretmez.

Neden 2'li catisma formati: 25 Agustos 2026'da OpenAI/Anthropic/Groq/Gemini'ye
ayri ayri sordugumuz kanal buyume analizinde 4'u de BAGIMSIZ olarak ayni
seyi soyledi - "5 ajani 60 saniyeye sigdirmaya calismak" izleyiciyi
kaybettiriyor, tek bir carpici iddia + ona verilen tepki yeterli
(bkz. ask_growth_advice.py). Eski tek-tur format tamamen birakildi.

Kullanim:
    python make_shorts.py output/bolum_3-20260824-151351.json
    python make_shorts.py output/bolum_3-20260824-151351.json --upload
"""
import argparse
import json
import os
import re
import subprocess
import sys
import textwrap

sys.stdout.reconfigure(errors="replace")

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from chamber_scene import SEAT_ORDER, build_chamber_bg, make_hero_frame
from generate_avatars import CARDS
from personas import PERSONAS

# Dikey (1080x1920) "The Apex Chamber" ayarlari - yatay (1280x720) versiyonuna
# gore olcekler farkli olmali, aksi halde LED panel/kahraman orantisiz cikar
# (bkz. chamber_scene.py, panel_h_basis notu).
CHAMBER_KW = dict(horizon_ratio=0.46, panel_w_ratio=0.55, panel_h_ratio=0.16, panel_h_basis="w")
HERO_KW = dict(hero_cy_ratio=0.29, hero_r_ratio=0.20, r_basis="w")

FONT_DIR = r"C:\Windows\Fonts"
VW, VH = 1080, 1920
BG = "#12151b"
ACCENT = "#5fd4c4"
INK = "#edeef0"

SHAPE_CY = 560
SHAPE_R = 210
CAPTION_TOP = 900
CAPTION_BOTTOM = 1780

MIN_WORDS = 40
MAX_WORDS = 180
# 2 yarinin toplami bunu asarsa Short cok uzar (~110sn ustu) - o cifti atla.
# (Mevcut ses klipleri tam-tur uzunlugunda, cumle-bazli kirpma icin yeniden
# TTS gerekir - bu v1'de yok, bkz. modul basi not.)
MAX_COMBINED_WORDS = 260


def _font(name, size):
    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)


def _centered_text(draw, cx, y, text, font, fill):
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    draw.text((cx - w / 2, y), text, font=font, fill=fill)


def _fit_caption(text, max_height):
    for size in (56, 48, 42, 36, 31, 27):
        wrap_width = 20 + (56 - size)
        lines = textwrap.fill(text, width=wrap_width).split("\n")
        line_height = int(size * 1.4)
        needed = line_height * len(lines)
        last = (size, lines, line_height)
        if needed <= max_height:
            return last
    return last


def make_short_frame(persona_key, text, out_path):
    # "The Apex Chamber" (bkz. chamber_scene.py) - dikey olcekle. Dar
    # genislikte 5 koltuk + buyuk kahraman sigmiyor/cakisiyor (ilk testte
    # tespit edildi) - dikeyde sadece mimari + kahraman gosteriliyor.
    chamber_bg = build_chamber_bg(VW, VH, skip_seat=set(SEAT_ORDER), **CHAMBER_KW)
    img = make_hero_frame(chamber_bg, persona_key, None, **HERO_KW).convert("RGBA")
    draw = ImageDraw.Draw(img, "RGBA")
    cx = VW // 2

    # Altyazi
    size, lines, line_height = _fit_caption(text, CAPTION_BOTTOM - CAPTION_TOP)
    font = _font("segoeuib.ttf", size)
    block_height = line_height * len(lines)
    y = CAPTION_TOP + (CAPTION_BOTTOM - CAPTION_TOP - block_height) / 2
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_w = bbox[2] - bbox[0]
        draw.text(((VW - line_w) / 2, y), line, font=font, fill=INK)
        y += line_height

    # Marka alt bilgisi
    brand_font = _font("segoeuib.ttf", 34)
    _centered_text(draw, cx, VH - 90, "SIGN COUNCIL", brand_font, ACCENT)

    img.convert("RGB").save(out_path)


def _render_half_segment(tag, persona_key, text, audio_path, out_dir):
    """Catisma Short'unun tek bir yarisi (bir ajanin karesi+sesi)."""
    frame_path = os.path.join(out_dir, f"{tag}_frame.png")
    make_short_frame(persona_key, text, frame_path)

    segment_path = os.path.join(out_dir, f"{tag}_segment.mp4")
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-loop", "1", "-i", frame_path,
            "-i", audio_path,
            "-vf", f"scale={VW*2}:{VH*2},zoompan=z='min(zoom+0.0006,1.08)':d=1:s={VW}x{VH}:fps=25,eq=brightness='0.035*sin(2*PI*t/2.2)'",
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


def render_clash_short(pair_index, turn_a, turn_b, audio_a, audio_b, out_dir):
    """Iki ardisik, farkli ajanin turunu tek bir 'catisma' Short'unda
    birlestirir: once A'nin iddiasi, hemen ardindan B'nin tepkisi -
    ortada kesme yok, direkt kesim (bkz. modul basi aciklama)."""
    tag_prefix = f"clash_{pair_index:02d}"
    seg_a = _render_half_segment(f"{tag_prefix}a_{turn_a['speaker']}", turn_a["speaker"], turn_a["text"], audio_a, out_dir)
    seg_b = _render_half_segment(f"{tag_prefix}b_{turn_b['speaker']}", turn_b["speaker"], turn_b["text"], audio_b, out_dir)

    concat_list = os.path.join(out_dir, f"{tag_prefix}_concat.txt")
    with open(concat_list, "w", encoding="utf-8") as f:
        f.write(f"file '{os.path.abspath(seg_a)}'\n")
        f.write(f"file '{os.path.abspath(seg_b)}'\n")

    out_path = os.path.join(out_dir, f"{tag_prefix}_{turn_a['speaker']}_vs_{turn_b['speaker']}.mp4")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list, "-c", "copy", out_path],
        check=True,
        capture_output=True,
    )
    return out_path


def _hook_title(text):
    """Turun icinden en carpici, kisa parcayi baslik olarak secer: once
    tam bir cumleyi, olmazsa virgulle ayrilan ilk anlamli parcayi, o da
    olmazsa kelime sinirinda kirpilmis metni dener."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    candidates = [s.strip(" .!?") for s in sentences if 4 <= len(s.split()) <= 13]
    if candidates:
        hook = candidates[0]
    else:
        clauses = re.split(r",\s+", sentences[0].strip(" .!?"))
        clause_candidates = [c for c in clauses if 4 <= len(c.split()) <= 13]
        if clause_candidates:
            hook = clause_candidates[0]
        else:
            words = text.split()
            hook = " ".join(words[:12])
    hook = hook[0].upper() + hook[1:] if hook else hook
    return hook


def _clash_title(turn_a, turn_b):
    """B'nin tepki cumlesini one cikaran baslik - Anthropic/Gemini/Groq'un
    ortak onerisi: 'tek carpici iddia + tepki' (bkz. ask_growth_advice.py)."""
    name_a = PERSONAS[turn_a["speaker"]]["display_name"]
    name_b = PERSONAS[turn_b["speaker"]]["display_name"]
    hook_b = _hook_title(turn_b["text"])
    title = f"{name_a} vs {name_b}: {hook_b}"
    # YouTube video basligi sert siniri 100 karakter - " #shorts" (8
    # karakter) icin yer birakiyoruz. Once bu sinirin ustune ciktik
    # (95+8=103), gercek yuklemede "invalid title" hatasi verdi.
    return title[:90].rstrip() + " #shorts"


def select_clash_pairs(transcript):
    """Ardisik, FARKLI iki ajanin (ikisi de Aura degil - o moderator,
    catisan taraf degil) turlerini bulur. Her iki yari da uzunluk
    sinirlari icinde olmali, toplam da Short'u asiri uzatmamali."""
    pairs = []
    for i in range(len(transcript) - 1):
        a, b = transcript[i], transcript[i + 1]
        if a["speaker"] == "aura" or b["speaker"] == "aura":
            continue
        if a["speaker"] == b["speaker"]:
            continue
        wa, wb = len(a["text"].split()), len(b["text"].split())
        if not (MIN_WORDS <= wa <= MAX_WORDS and MIN_WORDS <= wb <= MAX_WORDS):
            continue
        if wa + wb > MAX_COMBINED_WORDS:
            continue
        pairs.append((i, i + 1))
    return pairs


def make_shorts(transcript_path, upload=False):
    with open(transcript_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    episode_name = os.path.splitext(os.path.basename(transcript_path))[0]
    audio_dir = os.path.join(os.path.dirname(__file__), "output", "audio", episode_name)
    out_dir = os.path.join(os.path.dirname(__file__), "output", "shorts", episode_name)
    os.makedirs(out_dir, exist_ok=True)

    transcript = data["transcript"]
    pairs = select_clash_pairs(transcript)
    print(f"{len(transcript)} turdan {len(pairs)} catisma cifti secildi.")

    results = []
    for pair_idx, (i, j) in enumerate(pairs):
        turn_a, turn_b = transcript[i], transcript[j]
        audio_a = os.path.join(audio_dir, f"{i:02d}_{turn_a['speaker']}.mp3")
        audio_b = os.path.join(audio_dir, f"{j:02d}_{turn_b['speaker']}.mp3")
        if not (os.path.exists(audio_a) and os.path.exists(audio_b)):
            print(f"[{i:02d}-{j:02d}] ses eksik, atlandi")
            continue

        title = _clash_title(turn_a, turn_b)
        print(f"[{i:02d}-{j:02d}] \"{title}\"")
        out_path = render_clash_short(pair_idx, turn_a, turn_b, audio_a, audio_b, out_dir)
        combined_text = f"{turn_a['text']}\n\n{turn_b['text']}"
        results.append({"path": out_path, "title": title, "speaker": f"{turn_a['speaker']}_vs_{turn_b['speaker']}", "text": combined_text})

    print(f"\n{len(results)} catisma Short'u uretildi -> {out_dir}")

    if upload:
        from upload_youtube import upload_video
        for r in results:
            desc = r["text"] + "\n\nSign Council - 5 Minds. Zero Humans.\n#AI #shorts #SignCouncil"
            vid = upload_video(r["path"], r["title"], desc, tags=["AI", "shorts", "SignCouncil"], privacy_status="private")
            r["video_id"] = vid
        print("\nTum Short'lar 'private' olarak yuklendi - yayinlamak icin manuel onay gerekir.")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("transcript", help="run_episode.py ciktisi olan JSON dosyasi")
    parser.add_argument("--upload", action="store_true", help="uretilen Short'lari private olarak YouTube'a yukle")
    args = parser.parse_args()
    make_shorts(args.transcript, upload=args.upload)
