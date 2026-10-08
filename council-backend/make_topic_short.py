"""
Gunun konusu icin DIKEY (1080x1920) tek-argumanli elestiri Short'u uretir.
Format = analyze_channel.py'nin bulup dogruladigi KAZANAN kalip (3 Eylul):
fiziksel-dunya analojisi + kabul goren bir anlatiyi yikan provokatif iddia.
10 Eylul retention duzeltmesi: 95-110s'lik Short'lar sn 5-11'de %65 izleyici
kaybediyordu (payoff 60s+'da gomuluydu) -> hedef simdi <45s, 5 satir, payoff
satir 2'de. Paketleme-once (`_pick_title`): senaryo yazilmadan basligi sec,
senaryo o vaadi yerine getirsin (billion_view_playbook.md madde 1).

Ses: Sign Council'in KENDI ses sunucusu (:8124, sign_council_voice.bat) -
prod app'in mesh'ine dokunmaz. Groq iptal (kota), ElevenLabs iptal.

Kullanim:
    python make_topic_short.py --auto                 # Aura konuyu + kancayi secer
    python make_topic_short.py --auto --upload --public
    python make_topic_short.py --topic "..." --upload

Cikti: output/shorts/topic/<slug>.mp4
"""
import argparse
import json
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(errors="replace")
# Sign Council kendi ses sunucusu (prod app'ten AYRI)
os.environ.setdefault("AURA_TTS_MESH", "1")
os.environ.setdefault("AURA_TTS_NO_CHATTERBOX", "1")
os.environ.setdefault("AURA_VOICE_URL", "http://127.0.0.1:8124")
os.environ.setdefault("AURA_VOICE_KEY", (open(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".voice_key"), encoding="utf-8").read().strip() if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".voice_key")) else ""))
os.environ.setdefault("AURA_TTS_LIVE", "1")

from PIL import Image, ImageDraw, ImageFont

from make_shorts import make_short_frame, _sanitize_text, _topic_tags
from providers import call_gemini
from render_audio import synthesize

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "output", "shorts", "topic")
FONT_DIR = r"C:\Windows\Fonts"
W, H = 1080, 1920
BG = "#12151b"
INK = "#edeef0"
ACCENT = "#5fd4c4"
FPS = 30
SPEAKERS = ["aura", "alpha", "gamma", "beta", "delta"]

SCRIPT_PROMPT = (
    "Write a vertical YouTube Short script for Sign Council (5 AIs debate AI "
    "news). This channel's PROVEN winning format, from its own analytics: one "
    "single argument, 95-110 seconds, a vivid physical-world analogy, and a "
    "first line that is a provocative claim dismantling an accepted narrative "
    "- not a soft intro.\n\n"
    "Topic: {topic}\n"
    "Angle to push: {angle}\n\n"
    "Output 5 lines (6 absolute max), format  SPEAKER | SCREEN | LINE | IMAGE:\n"
    "- SPEAKER is one of: aura, alpha, gamma, beta, delta (aura opens and "
    "closes; vary the rest)\n"
    "- SCREEN is a 2-4 word ALL-CAPS on-screen phrase\n"
    "- LINE is ONE or TWO spoken sentences, 14-22 words total, punchy, no "
    "markdown, no 'I think'\n"
    "- IMAGE is a one-sentence cinematic photo prompt for the PHYSICAL "
    "ANALOGY OBJECT this exact line uses (e.g. 'a bulldozer plowing through "
    "a small family farm at dusk') - concrete, filmable, no text/words/logos "
    "in the image, no AI or robot cliches, moody cinematic lighting\n"
    "LENGTH IS THE #1 KILLER. 10 Sep 2026 retention data: our 97-110s Shorts "
    "lose 65% of viewers by SECOND 10 because the payoff sits at 60s+. This "
    "script must play UNDER 45 SECONDS. Five tight lines. If a line does not "
    "earn its place, cut it.\n"
    "Line 1 = THE HOOK. News-fact openings ('X breached Y', 'X paid $Zb') hold "
    "only 14%. Openings that pose the UNANSWERED QUESTION / the mystery ('Why "
    "did OpenAI, Claude and Grok all go down within minutes of each other?') "
    "hold 30-52%. Line 1 = that question or a pattern-interrupt with a hard "
    "number in the first 4 words. Under 8 words. NOT the resolved fact.\n"
    "Line 2 = ANSWER THE HOOK NOW - state the core conflict / the real "
    "mechanism plainly, in full. Do not tease it further; the viewer who "
    "swipes at second 8 must already have the payoff.\n"
    "Line 3 = the physical analogy + why the accepted fix is false comfort. End "
    "line 3 by OPENING a fresh tension ('but that's not even the real problem' / "
    "'and that's the version they want you to believe') - a mini open-loop so "
    "the viewer needs lines 4-5 to close it. Never let line 3 feel resolved.\n"
    "Line 4 = ONE member steelmans the target company's single strongest "
    "good-faith rebuttal (real mechanism - 'standard practice / disclosed in "
    "filings / contractually allowed', not PR fluff): a genuine concession.\n"
    "Line 5 = close: do NOT summarise - dismantle that rebuttal, name who "
    "still loses, and expose the trap: how a viewer who trusts the official "
    "narrative here ends up carrying the risk. Attack the STRUCTURE and the "
    "INCENTIVE (the model, the contract terms, the disclosure timeline, the "
    "market pressure) - never assert that a named company is deliberately "
    "lying, committing fraud, or intentionally deceiving customers; that is a "
    "defamation risk and it gets the video killed. 'The incentive rewards "
    "delay' is fine; 'Company X is lying to hide breaches' is not. (This "
    "channel's viewer is a disillusioned tech builder; the emotion that "
    "converts is VINDICATED CYNICISM - being proven right that the system is "
    "rigged while everyone else buys the hype.)\n"
    "COMMENT ENGINE (26 Sep 2026, council + data: 26 videos with ZERO comments, "
    "1 comment in 28 days): line 5 must END with ONE short direct question "
    "(max 8 words) that makes the viewer pick between TWO named sides "
    "('The filing or the incentive - which do you trust?'), answerable in one "
    "comment. A real question, never a demand, never fake urgency. Keep "
    "line 5 at 14-22 words total.\n"
    "After the 7 lines, add:\n"
    "TITLE: <a single declarative statement refuting a common belief, <=68 "
    "chars, ending with nothing (we add #Shorts). MUST name a real company or "
    "product (OpenAI, Nvidia, Meta, Anthropic, Google, etc) or a concrete "
    "number/dollar figure. ZERO metaphor or analogy in the TITLE itself - the "
    "physical analogy lives in the LINES and IMAGES, never the title. "
    "(5 Sep 2026 channel data: metaphor titles like 'A Model's Conscience' or "
    "'Buying the Nation's Map App' pull passive impressions but convert at "
    "<1% engagement; zero-metaphor conflict titles - 'AI Safety Testing Is "
    "Collapsing', 'The Kill Switch Is a Lie' - convert 2-10x better.) "
    "NEVER a channel-meta title (no 'Sign Council Announcement', no "
    "first-person reflection like 'I wasn't', no abstract question with no "
    "entity - these flatline at 1 view here).>\n"
    "HOOKTHUMB: <2-4 ALL CAPS words for the opening card>"
)

# 4 Eylul viral_strategist.py teshisi: kanal-ici anons / birinci-sahis
# felsefi baslikar 1 izlenmede kaliyor, gercek sirket adi + fiziksel
# tehdit iceren basliklar kazaniyor. Zayif baslik gecerse LLM'e BIR kez
# daha yazdir.
_WEAK_TITLE = re.compile(
    r"sign council|announcement|i wasn.?t|do you still|^(is|are|can|will|"
    r"why|what|who)\b.{0,40}\?$|"
    # 5 Eylul Aura kanal analizi: canli-yayin anonsu Short'lari yayin bitince
    # kanali durduruyor (evergreen degeri sifir) - baslikta 'live tonight' /
    # 'going live' / 'ask her anything' varsa reddet.
    r"live tonight|going live|ask (her|us) anything|tune in|watch live|"
    # 5 Eylul: metafor/benzetme basliklari <%1 etkilesim - 'like a ...',
    # 'is like', ya da soyut sahiplik benzetmesi (X's Conscience / X's Map App)
    r"\blike a \b|\bis like\b|'s (conscience|map app|umbrella|life raft|"
    r"house of cards|band[- ]?aid)\b", re.I)


def _title_is_weak(title, beats_text):
    if _WEAK_TITLE.search(title):
        return True
    # gercek sirket/urun adi ya da $ rakami gecmiyorsa da zayif say
    entities = r"openai|nvidia|meta|anthropic|google|microsoft|grok|gemini|claude|\$\d"
    return not re.search(entities, title + " " + beats_text, re.I)


def _font(name, size):
    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)


def _center(draw, cx, y, text, font, fill):
    b = draw.textbbox((0, 0), text, font=font)
    draw.text((cx - (b[2] - b[0]) / 2, y), text, font=font, fill=fill)


def _wrap_fit(d, text, max_w, sizes):
    """En buyuk sigan fontu bul; gerekirse 2 satira sar."""
    for sz in sizes:
        f = _font("segoeuib.ttf", sz)
        if d.textlength(text, font=f) <= max_w:
            return f, [text]
        words = text.split()
        for cut in range(1, len(words)):
            a, b = " ".join(words[:cut]), " ".join(words[cut:])
            if d.textlength(a, font=f) <= max_w and d.textlength(b, font=f) <= max_w:
                return f, [a, b]
    f = _font("segoeuib.ttf", sizes[-1])
    return f, [text]


def _text_card(lines, out_path, big=True, tag="", tag_color=ACCENT):
    """billion_view_playbook.md madde 5: OZEL formatlar (leaderboard/hottake/
    evergreen) sabit renkli bir rozet tasir ki izleyici 1 saniyede 'bu farkli
    bir bolum' desin. Gunluk tekil-konu kalibinda rozet YOK - bu bilerek boyle:
    rozetsiz = 'bugunun normal tartismasi' sinyali."""
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    if tag:
        f = _font("segoeuib.ttf", 34)
        tw = d.textlength(tag.upper(), font=f)
        pad_x, pad_y, top = 28, 14, 150
        d.rounded_rectangle(
            (W // 2 - tw / 2 - pad_x, top, W // 2 + tw / 2 + pad_x, top + 34 + pad_y * 2),
            radius=999, fill=tag_color)
        d.text((W // 2, top + pad_y + 17), tag.upper(), font=f, fill="#0b0d12", anchor="mm")
    d.ellipse((W // 2 - 8, 300 - 8, W // 2 + 8, 300 + 8), fill=ACCENT)
    if big:
        rendered = []
        for ln in lines:
            f, parts = _wrap_fit(d, ln, W - 120, [126, 108, 92, 78, 66])
            for p in parts:
                rendered.append((p, f))
        total_h = sum(int(f.size * 1.34) for _, f in rendered)
        y = H // 2 - total_h // 2
        for p, f in rendered:
            _center(d, W // 2, y, p, f, INK)
            y += int(f.size * 1.34)
    else:
        specs = [(96, ACCENT, 150), (72, INK, 110), (40, "#8b96a2", 0)]
        y = H // 2 - 200
        for ln, (sz, col, gap) in zip(lines, specs):
            f, parts = _wrap_fit(d, ln, W - 100, [sz, int(sz * 0.8), int(sz * 0.65)])
            for p in parts:
                _center(d, W // 2, y, p, f, col)
                y += int(f.size * 1.2)
            y += gap - int(f.size * 1.2) if parts else gap
    img.save(out_path)


def _motion_vf(dur, frame_png=""):
    """'Canlandirilmis dingin kare' - duz yavas-zoom yerine sinematik hareket:
    yon degistiren kamera kaydirmasi (parallax hissi) + nefes alan parlaklik
    (ambiyans/isik titremesi) + film grain + vignette. 5 Eylul 2026 kullanici
    istegi: 'gorseller harika ama 3B hareket - kapak acilirken, isik yanip
    sonerken gibi'. Bu, tam i2v olmadan 2.5B canlilik verir; gercek eleman
    animasyonu icin media_agents.generate_motion_clip (AURA_MOTION=1)."""
    tf = max(1, int(dur * FPS))
    # kare adinin son rakami -> kaydirma yonu (ard arda kareler ayni suzulmesin)
    d = 0
    for ch in reversed(frame_png):
        if ch.isdigit():
            d = int(ch); break
    sx = 1 if d % 2 == 0 else -1
    sy = 1 if (d // 2) % 2 == 0 else -1
    return (
        f"scale={W*2}:{H*2},"
        f"zoompan=z='min(1.001+0.0009*on,1.10)':"
        f"x='iw/2-(iw/zoom/2)+{sx}*sin(on/{tf}*3.14159)*64':"
        f"y='ih/2-(ih/zoom/2)+{sy}*on/{tf}*84':d=1:s={W}x{H}:fps={FPS},"
        f"eq=brightness='0.014*sin(t*3.7)':saturation=1.04,"
        f"noise=alls=6:allf=t,vignette=PI/4.6"
    )


def _segment(frame_png, audio_path, dur, out_mp4):
    # 12 Eyl 2026: -ar/-ac ZORUNLU - bu olmadan TTS kaynagi (mono 44100) ile
    # anullsrc kapak kareleri (stereo 44100) FARKLI kanal duzeninde AAC'ye
    # kodlaniyordu; concat sirasinda kanal-duzeni degisimi (mono<->stereo)
    # gecislerde titreme/donma sesi olarak duyuluyordu (kullanici 12 Eyl
    # bildirdi). Artik HER segment ayni format: 44100Hz stereo.
    subprocess.run(
        ["ffmpeg", "-y", "-loop", "1", "-i", frame_png, "-i", audio_path,
         "-vf", _motion_vf(dur, frame_png),
         "-c:v", "libx264", "-crf", "20", "-c:a", "aac", "-b:a", "192k",
         "-ar", "44100", "-ac", "2",
         "-pix_fmt", "yuv420p", "-shortest", out_mp4],
        check=True, capture_output=True)


_OUTROS = [
    "One AI story every day. Follow so you don't miss tomorrow's.",
    "New AI power story tomorrow. Follow Sign Council.",
    "Five AIs, one story, every day. Follow to catch the next one.",
]


def _outro_line():
    """Sesli kapanis (Aura): durust bir deger vaadi + takip cagrisi. Gune gore doner."""
    import datetime
    return _OUTROS[datetime.date.today().toordinal() % len(_OUTROS)]


def _close_card_lines(next_hint=""):
    """Milyar-izlenme oyun kitabi madde 7: kapanis = TEK net CTA. Jenerik
    '5 AIs. Unscripted.' yerine takip + cadence vaadi."""
    top = next_hint or "One AI-power story. Every day."
    return [top[:38], "SIGN COUNCIL", "Follow - new debate tomorrow"]


def _silent_segment(frame_png, dur, out_mp4):
    # BUG (12 Eyl 2026 kesfedildi): bu fonksiyon HIC audio stream'i
    # eklemiyordu - topic formatinin kapanis karti (99.mp4) sessiz kaliyor,
    # concat sirasinda diger segmentlerle (mono/stereo AAC) kanal-duzeni
    # tutarsizligi + eksik ses akisi titreme/donma sesi yaratiyordu (kullanici
    # bildirdi). hottake/evergreen'in _card_segment'i gibi anullsrc eklendi.
    subprocess.run(
        ["ffmpeg", "-y", "-loop", "1", "-t", str(dur), "-i", frame_png,
         "-f", "lavfi", "-t", str(dur), "-i", "anullsrc=r=44100:cl=stereo",
         "-vf", f"scale={W*2}:{H*2},zoompan=z='min(zoom+0.0004,1.05)':d=1:s={W}x{H}:fps={FPS}",
         "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-ar", "44100", "-ac", "2", "-shortest", out_mp4],
        check=True, capture_output=True)


# YouTube moderasyonu/reklam-dostu olmayan kelimeler ekranda/baslikta gorununce
# video kisitlaniyor/boguluyor - trend olmayi bitirir. Ekran+baslik metnini
# tamamla. (Sozlu satirlar daha az gorunur ama yine de temiz tutulur.)
_YT_SWAP = {
    r"\bsuicid\w*": "self-sabotage", r"\bkill(ing|s|ed)?\b": "end",
    r"\bmurder\w*": "gut", r"\bdead\b": "over", r"\bdeaths?\b": "collapse",
    r"\bdie\b": "fold", r"\bdying\b": "fading", r"\bweapons?\b": "tool",
    r"\bbomb\w*": "blowup", r"\bslaughter\w*": "wipeout",
}


def _yt_safe(text):
    for pat, repl in _YT_SWAP.items():
        text = re.sub(pat, lambda m: (repl.capitalize() if m.group(0)[:1].isupper() else repl),
                      text, flags=re.I)
    return text


def _parse_script(raw):
    beats, title, hookthumb = [], "", ""
    for ln in raw.splitlines():
        ln = ln.strip()
        if ln.upper().startswith("TITLE:"):
            title = _yt_safe(ln.split(":", 1)[1].strip().strip('"'))
        elif ln.upper().startswith("HOOKTHUMB:"):
            hookthumb = _yt_safe(" ".join(ln.split(":", 1)[1].strip().strip('"').split()[:4])).upper()
        elif "|" in ln:
            parts = [p.strip() for p in ln.split("|")]
            if len(parts) >= 3 and parts[0].lower() in SPEAKERS:
                img = parts[3] if len(parts) >= 4 else ""
                beats.append((parts[0].lower(), _yt_safe(parts[1].upper()),
                             _sanitize_text(_yt_safe(parts[2])), img))
    return beats, title, hookthumb


_TITLE_PICK_PROMPT = (
    "You are the art director for Sign Council (5 AIs debate AI-infrastructure "
    "power). Before any script is written, PACKAGE this topic - the title is "
    "chosen FIRST and the script is written to deliver on it (billion-view "
    "channel practice: packaging drives the video, not the other way round).\n\n"
    "TOPIC: {topic}\nANGLE: {angle}\n\n"
    "Write 3 DIFFERENT candidate titles (not phrasings of one idea): "
    "(A) a question/mystery framing (retains 30-52% per this channel's data), "
    "(B) a flat declarative with a hard number, (C) a reversal of a common "
    "belief. Each: <=70 chars, MUST name a real company/product from the topic "
    "or a concrete number/$ figure, ZERO metaphor, no channel-meta.\n"
    "Output EXACTLY:\nA: ...\nB: ...\nC: ...\nPICK: <A, B or C - the strongest>\n"
)


def _pick_title(topic, angle):
    """Paketleme-once: senaryo yazilmadan basligi sec, senaryo bu vaadi
    yerine getirsin (billion_view_playbook.md madde 1)."""
    try:
        raw = call_gemini([{"role": "user", "content":
                            _TITLE_PICK_PROMPT.format(topic=topic, angle=angle or "")}], "")
        opts = {m.group(1): m.group(2).strip().strip('"')
               for m in re.finditer(r"^([ABC]):\s*(.+)$", raw, re.M)}
        pick = (re.search(r"PICK:\s*([ABC])", raw) or [None, ""])[1]
        t = opts.get(pick) or next(iter(opts.values()), "")
        return _yt_safe(t)[:70]
    except Exception:
        return ""


def _build_prompt(topic, angle):
    """Senaryo komutu + panelden (Takip > Uygula) yazilan yapimci kurallari."""
    prompt = SCRIPT_PROMPT.format(topic=topic, angle=angle or "the hidden systemic risk")
    try:
        from aura_editorial import _operator_rules
        rules = _operator_rules()
        if rules:
            prompt += "\n" + rules
    except Exception:
        pass
    return prompt


def _script(topic, angle):
    target_title = _pick_title(topic, angle)
    prompt = _build_prompt(topic, angle)
    if target_title:
        prompt += (f"\n\nPACKAGED TITLE (already chosen - your script's hook and "
                   f"line 2 payoff must deliver exactly on this promise): {target_title}\n"
                   f"Output this as your TITLE line unless you can write one that "
                   f"is clearly stronger by the same rules.")
    raw = call_gemini([{"role": "user", "content": prompt}],
                      "You are the Sign Council head writer. Follow the format exactly.")
    beats, title, hookthumb = _parse_script(raw)
    beats_text = " ".join(b[2] for b in beats)
    if title and _title_is_weak(title, beats_text):
        # 4 Eylul viral_strategist.py teshisi: zayif (kanal-ici/felsefi/varliksiz)
        # basliklar 1 izlenmede kaliyor - BIR kez daha, daha sert talimatla yazdir.
        print(f"  [zayif baslik yakalandi: '{title}' - yeniden yaziliyor]")
        retry_prompt = prompt + (
            f"\n\nYour previous title '{title}' was REJECTED for being too abstract/"
            "channel-meta. Try again - the title MUST open with or contain a real "
            "company name (OpenAI, Nvidia, Meta, Anthropic, Google...) or a dollar "
            "figure, stated as a concrete claim.")
        raw2 = call_gemini([{"role": "user", "content": retry_prompt}],
                           "You are the Sign Council head writer. Follow the format exactly.")
        beats2, title2, hookthumb2 = _parse_script(raw2)
        if title2 and len(beats2) >= 4:
            beats, title, hookthumb = beats2, title2, hookthumb2
    return beats, title, hookthumb


def _smart_tags_safe(topic, script=""):
    try:
        from hashtag_agent import pick_tags
        return pick_tags(topic, script)
    except Exception:
        try:
            from growth_agent import smart_tags
            return smart_tags(topic, extra=["shorts", "SignCouncil"])
        except Exception:
            return _topic_tags(topic + " AI OpenAI", ["AI", "shorts", "SignCouncil", "AI news"])


def _draw_beat_overlay(d, screen, who):
    """scrim + SIGN COUNCIL bug + konusan + altyazi - hem still'e hem seffaf
    metin katmanina ayni sekilde cizilir."""
    d.rectangle((0, int(H * 0.66), W, H), fill=(5, 7, 13, 200))
    d.rectangle((0, 0, W, 140), fill=(5, 7, 13, 150))
    d.text((36, 42), "SIGN COUNCIL",
           font=ImageFont.truetype(os.path.join(FONT_DIR, "segoeuib.ttf"), 36),
           fill=(240, 244, 248, 255))
    d.text((36, 88), who.upper(),
           font=ImageFont.truetype(os.path.join(FONT_DIR, "segoeuib.ttf"), 28),
           fill=(120, 224, 196, 230))
    f, lines = _wrap_fit(d, screen, W - 90, [80, 68, 56, 46])
    y = int(H * 0.71)
    for ln in lines:
        _center(d, W // 2, y, ln, f, INK)
        y += int(f.size * 1.25)


def _analogy_frame(image_prompt, screen, who, out_path):
    """Aura'nin viral_strategist.py taktigi #7: soyut kahraman sekli yerine
    o repligin FIZIKSEL ANALOJISINI goruntuleyen sinematik goruntu - zaten
    onayli ajanlarla (Gemini/Pollinations, media_agents.py). Basarisiz
    olursa eski Apex Chamber kahraman karesine guvenle duser.

    Yan cikti (i2v icin, silinmez):
      {out}_base.png - metinsiz sinematik arka plan (generate_motion_clip girdisi)
      {out}_txt.png  - seffaf metin/bug/scrim katmani (animasyonlu klibe overlay)"""
    if not image_prompt:
        return make_short_frame(who, screen, out_path)
    base = out_path.replace(".png", "_base.png")
    txt = out_path.replace(".png", "_txt.png")
    try:
        from media_agents import generate_image
        generate_image(image_prompt, base, width=1080, height=1920)
        bg = Image.open(base).convert("RGB").resize((W, H), Image.LANCZOS)
        bg.save(base)  # WxH'e normalize et (i2v tutarli girdi)

        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        _draw_beat_overlay(ImageDraw.Draw(layer, "RGBA"), screen, who)
        layer.save(txt)

        Image.alpha_composite(bg.convert("RGBA"), layer).convert("RGB").save(out_path)
        return out_path
    except Exception as e:
        print(f"    [analoji goruntusu atlandi ({e}) - Apex Chamber karesi kullanildi]")
        for p in (base, txt):
            if os.path.exists(p):
                try:
                    os.remove(p)
                except OSError:
                    pass
        return make_short_frame(who, screen, out_path)


def _beat_segment(frame_png, audio_path, dur, out_mp4, motion_prompt=""):
    """AURA_MOTION=1 + i2v anahtari varsa: metinsiz arka plani gercekten
    animasyonlar (kapak acilir, isik yanip soner...), seffaf metin katmanini
    ustune bindirir. Aksi halde prosedurel 2.5B harekete (_segment) duser."""
    base = frame_png.replace(".png", "_base.png")
    txt = frame_png.replace(".png", "_txt.png")
    if os.getenv("AURA_MOTION", "").strip() in ("1", "true", "yes") and \
       os.path.exists(base) and motion_prompt:
        try:
            from media_agents import generate_motion_clip
            clip = frame_png.replace(".png", "_mo.mp4")
            got = generate_motion_clip(base, motion_prompt, clip, seconds=min(dur, 6))
            if got and os.path.exists(got):
                ov = ["-i", txt] if os.path.exists(txt) else []
                fc = (f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,"
                      f"crop={W}:{H},loop=loop=-1:size=1,fps={FPS}[bg];")
                if ov:
                    fc += "[bg][1:v]overlay=0:0[vv];[vv]" + _MOTION_POST
                else:
                    fc += "[bg]" + _MOTION_POST
                subprocess.run(
                    ["ffmpeg", "-y", "-i", got, *ov, "-i", audio_path,
                     "-filter_complex", fc,
                     "-map", "[v]", "-map", f"{2 if ov else 1}:a",
                     "-c:v", "libx264", "-crf", "20", "-c:a", "aac", "-b:a", "192k",
                     "-ar", "44100", "-ac", "2",
                     "-pix_fmt", "yuv420p", "-t", f"{dur}", out_mp4],
                    check=True, capture_output=True)
                return
        except Exception as e:
            print(f"    [i2v beat atlandi ({type(e).__name__}: {e}) - prosedurel harekete duruluyor]")
    _segment(frame_png, audio_path, dur, out_mp4)


_MOTION_POST = ("eq=brightness='0.010*sin(t*3.7)':saturation=1.03,"
                "noise=alls=5:allf=t,vignette=PI/4.6[v]")


def build(topic, angle="", title_override="", desc_override="", tags=None):
    os.makedirs(OUT_DIR, exist_ok=True)
    beats, title, hookthumb = _script(topic, angle)
    if len(beats) < 4:
        raise SystemExit(f"Senaryo uretilemedi (yalniz {len(beats)} beat). Tekrar dene.")
    # 10 Eyl retention: 6+ beat = payoff 60s+ = %65 kayip sn 10'da. Fazlasini at.
    if len(beats) > 6:
        print(f"  [i] {len(beats)} beat -> ilk 6'ya kirpiliyor (uzunluk retention katili)")
        beats = beats[:6]
    title = title_override or title or topic[:60]
    hookthumb = hookthumb or "THE REAL STORY"
    print(f"TITLE: {title}\nHOOK: {hookthumb}\n{len(beats)} beat:")

    segs, total = [], 0.0
    # ACILIS: logo karti YOK. Kare 1'den itibaren 3B sahne + konusan kisi +
    # en sert cumle altyazida. Shorts ilk 2 saniyede kaydirilir - donuk kart
    # olmez. (4 Eylul: 100-223 izlenme -> hook baştan yazildi.)
    beats[0] = (beats[0][0] or "aura", hookthumb, beats[0][2], beats[0][3] if len(beats[0]) > 3 else "")

    for i, (who, screen, line, img_prompt) in enumerate(beats, start=0):
        fp = os.path.join(OUT_DIR, f"{i:02d}_frame.png")
        _analogy_frame(img_prompt, screen, who, fp)
        ap = os.path.join(OUT_DIR, f"{i:02d}.mp3")
        with open(ap, "wb") as f:
            f.write(synthesize(line, who))
        dur = _dur(ap)
        _beat_segment(fp, ap, dur + 0.18, os.path.join(OUT_DIR, f"{i:02d}.mp4"),
                      motion_prompt=img_prompt)
        segs.append(os.path.join(OUT_DIR, f"{i:02d}.mp4")); total += dur + 0.18
        print(f"  beat {i} ({who}, {dur:.1f}s): {line[:60]}")

    cf = os.path.join(OUT_DIR, "99_frame.png")
    _text_card(_close_card_lines(), cf, big=False)
    try:  # 26 Eylul 2026: kapanis artik SESLI (konsey + veri: abone donusumu 7,6 -> 2,7/1000)
        oa = os.path.join(OUT_DIR, "99.mp3")
        with open(oa, "wb") as f:
            f.write(synthesize(_outro_line(), "aura"))
        od = _dur(oa)
        _segment(cf, oa, od + 0.4, os.path.join(OUT_DIR, "99.mp4"))
        total += od + 0.4
    except Exception as e:
        print(f"  [sesli kapanis atlandi: {type(e).__name__}: {e}] - sessiz kart")
        _silent_segment(cf, 2.2, os.path.join(OUT_DIR, "99.mp4"))
        total += 2.2
    segs.append(os.path.join(OUT_DIR, "99.mp4"))
    if total > 55:
        print(f"  [!] UZUN: {total:.0f}s (hedef <45s). Retention verisi: 97s "
              "Short'lar sn 10'da %65 izleyici kaybediyor. Senaryoyu kisalt.")

    lst = os.path.join(OUT_DIR, "_concat.txt")
    with open(lst, "w", encoding="utf-8") as f:
        for s in segs:
            f.write(f"file '{os.path.abspath(s)}'\n")
    joined = os.path.join(OUT_DIR, "_joined.mp4")
    subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst,
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
                    "-c:a", "aac", "-ar", "44100", "-ac", "2", joined],
                   check=True, capture_output=True)

    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:44] or "short"
    final = os.path.join(OUT_DIR, f"{slug}.mp4")
    # 12 Eyl 2026: aformat= normalizasyonu ZORUNLU - amix/loudnorm farkli
    # ornekleme-hizi/kanal-duzenindeki girdileri sessizce yanlis birlestirip
    # ciktida beklenmedik bir format (or. 96kHz) + duyulabilir titreme/donma
    # uretiyordu (kullanici bildirdi). Her asamada 44100Hz stereo'ya kilitle.
    subprocess.run(
        ["ffmpeg", "-y", "-i", joined,
         "-f", "lavfi", "-i", f"sine=frequency=98:duration={total}",
         "-f", "lavfi", "-i", f"sine=frequency=147:duration={total}",
         "-filter_complex",
         f"[0:v]fade=t=in:st=0:d=0.4,fade=t=out:st={total-0.5}:d=0.5[v];"
         f"[0:a]aformat=sample_rates=44100:channel_layouts=stereo[va];"
         f"[1:a][2:a]amix=inputs=2:weights=1 0.5,"
         f"aformat=sample_rates=44100:channel_layouts=stereo[t];"
         f"[t]volume=0.10,afade=t=in:st=0:d=0.8,afade=t=out:st={total-1}:d=1[bed];"
         f"[va][bed]amix=inputs=2:duration=first:weights=1 1,loudnorm=I=-14:TP=-1.5:LRA=11[a]",
         "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-ac", "2",
         "-movflags", "+faststart", final],
        check=True, capture_output=True)
    print(f"\nShort hazir: {final}  (~{total:.0f}s)")

    script_text = " ".join(b[2] for b in beats if len(b) > 2 and b[2])
    if desc_override:
        desc = desc_override
    else:
        try:
            from hashtag_agent import compose_description
            desc = compose_description(
                beats[0][2], "Sign Council's five AIs debate it, unscripted. "
                "Full breakdown on the channel.", topic, script_text)
        except Exception:
            desc = (f"{beats[0][2]}\n\nSign Council's five AIs debate it, unscripted. "
                    "Full breakdown on the channel.\n\n"
                    "#AI #TechNews #ArtificialIntelligence #SignCouncil")
    meta = {"title": (title[:88].rstrip() + " #Shorts"), "description": desc,
            "tags": tags or _smart_tags_safe(topic, script_text),
            "file": final, "seconds": round(total),
            "script": script_text}
    with open(final.replace(".mp4", ".json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return meta


def _dur(path):
    return float(subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                                 "-of", "csv=p=0", path], capture_output=True, text=True).stdout.strip() or 4)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--auto", action="store_true", help="Aura konuyu + acisini secsin (aura_editorial)")
    ap.add_argument("--topic", default=None)
    ap.add_argument("--angle", default="")
    ap.add_argument("--upload", action="store_true")
    ap.add_argument("--public", action="store_true", help="HERKESE ACIK yukle (varsayilan private)")
    a = ap.parse_args()

    topic, angle = a.topic, a.angle
    if a.auto or not topic:
        from aura_editorial import run_editorial_plan
        plan = run_editorial_plan()
        topic = plan["decision"]
        angle = angle or (plan["angles"][0] if plan.get("angles") else "")

    meta = build(topic, angle)
    if a.upload:
        from upload_youtube import upload_video
        vid = upload_video(meta["file"], _sanitize_text(meta["title"]), _sanitize_text(meta["description"]),
                           tags=meta["tags"], privacy_status="public" if a.public else "private")
        if a.public:
            try:
                from growth_agent import post_engagement_comment
                post_engagement_comment(vid, topic)
            except Exception as e:
                print(f"  [engagement yorumu atlandi: {e}]")
        print(f"\nvideo_id: {vid}")
