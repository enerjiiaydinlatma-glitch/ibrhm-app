"""
Bolumleri yuruten tur-bazli orkestrator.

Aura her zaman soruyu sorar/yonlendirir, ilgili ajan sirayla cevaplar -
serbest/ust uste konusma YOK (bkz. Sign Council Rundown, Segment 05:
"Konusma sirasi: tur-bazli soru-cevap").
"""
from personas import PERSONAS
from providers import PROVIDER_CALLERS, MissingApiKeyError


def _format_transcript_as_messages(transcript, upcoming_directive):
    """Su ana kadarki transkripti, konusmaci etiketleriyle tek bir
    kullanici mesajina donusturur - her saglayici kendi konusma gecmisi
    formatini farkli bekledigi icin en tutarli/tasinabilir yol bu."""
    lines = [
        f"{PERSONAS[turn['speaker']]['display_name']}: {turn['text']}"
        for turn in transcript
    ]
    lines.append(f"\n[YONERGE] {upcoming_directive}")
    return [{"role": "user", "content": "\n".join(lines)}]


def run_turn(persona_key, topic, transcript, directive):
    persona = PERSONAS[persona_key]
    caller = PROVIDER_CALLERS[persona["provider"]]
    messages = _format_transcript_as_messages(transcript, directive)
    system_instruction = f"{persona['system_instruction']}\n\nBolumun konusu: {topic}"

    try:
        text = caller(messages, system_instruction)
    except MissingApiKeyError as e:
        # Devre kesici: eksik anahtar bolumu durdurmaz, o turu isaretler.
        text = f"[ATLANDI - {e}]"

    transcript.append({"speaker": persona_key, "text": text})
    return text


def run_episode(topic, turn_plan):
    """turn_plan: [{"speaker": "aura", "directive": "..."}, ...] seklinde
    sirali bir liste. Her adim onceki transkripte eklenir, boylece
    sonraki konusmaci oncekileri "gorur"."""
    transcript = []
    for step in turn_plan:
        run_turn(step["speaker"], topic, transcript, step["directive"])
    return transcript
