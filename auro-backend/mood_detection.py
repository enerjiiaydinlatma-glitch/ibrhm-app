"""
Sohbet mesajindan ruh hali (hale rengi icin) tespiti.

main.py'den cikarildi (2026-10-04, bkz. docs/MOOD_IYILESTIRME_PLANI.md) ki
dis bagimliligi olmadan test edilebilsin. KRIZ tespiti (_CRISIS_KEYWORDS)
bu modulun DISINDA, main.py'de kalir ve bu modulden etkilenmez.

Eski davranisa gore degisenler:
- OLUMSUZLAMA: "yorgun degilim" / "not happy" artik etiket uretmez (ters
  duyguya CEVRILMEZ - sadece sayilmaz, hale onceki rengini korur).
- COKLU DUYGU: mesajdaki TUM duygular (mesajdaki sirayla) doner; eskiden
  sozlukteki sira belirliyordu, mesajdaki degil.
- TAM KELIME: "sad" gibi kisa Ingilizce kelimeler artik "sadece" icinde
  eslesmiyor (eskiden "Sadece bir soru..." -> "uzgun" cikiyordu).
"""
import re

import database

MOOD_KEYWORDS = {
    "mutlu": ["mutlu", "harika", "super", "süper", "keyifli", "sevindim",
              "happy", "great", "wonderful", "delighted"],
    "uzgun": ["uzgun", "üzgün", "kotu", "kötü", "berbat", "canim sikkin", "moralim bozuk",
              # "down" duz alt-dize eslesmesiyle "downtown"/"download"
              # gibi alakasiz kelimeleri yakaliyordu - cikarildi,
              # "feeling down" gibi spesifik ifade kaldi.
              "sad", "upset", "feeling down", "depressed", "unhappy"],
    "yorgun": ["yorgun", "bitkinim", "halsiz", "uykum var",
               "tired", "exhausted", "sleepy", "worn out"],
    "stresli": ["stresli", "kaygili", "endiseli", "endişeli", "gergin", "sinirliyim",
                "stressed", "anxious", "worried", "nervous", "irritated"],
    "enerjik": ["enerjik", "heyecanliyim", "motiveyim", "haziriyim",
                "energetic", "excited", "motivated", "pumped"],
}

# Bu kelimelerde SONEK kabul edilmez (Turkce kelimeler "yorgunum" gibi
# sonek alir, bunlar almaz): kelimenin tamami eslesmeli.
_WHOLE_WORD = {
    "super", "süper", "sad", "upset", "happy", "great", "wonderful",
    "delighted", "unhappy", "depressed", "tired", "exhausted", "sleepy",
    "stressed", "anxious", "worried", "nervous", "irritated", "energetic",
    "excited", "motivated", "pumped",
}

_NEGATION_BEFORE = {
    "not", "never", "no", "isnt", "arent", "wasnt", "werent",
    "dont", "doesnt", "didnt", "cant", "cannot", "wont",
}
_NEGATION_AFTER_EXACT = {"yok"}
_NEGATION_WINDOW = 2  # kelime

_SENTENCE_END = re.compile(r"[.!?;\n]")
_WORD = re.compile(r"[\w']+")


def _fold(text: str) -> str:
    text = text.replace("’", "'")
    text = database.fold_turkish_diacritics(database.fold_turkish_i(text)).lower()
    return re.sub(r"[ \t]+", " ", text)


def _compile():
    compiled = []
    for mood, words in MOOD_KEYWORDS.items():
        seen = set()
        for original in words:
            kw = _fold(original)
            if kw in seen:
                continue
            seen.add(kw)
            tail = r"(?!\w)" if original in _WHOLE_WORD else ""
            compiled.append((mood, re.compile(r"(?<!\w)" + re.escape(kw) + tail)))
    return compiled


_PATTERNS = _compile()


def _negated(folded: str, start: int, end: int) -> bool:
    """Eslesmenin yakininda (ayni cumlede) olumsuzlama var mi?"""
    sentence_start = 0
    for m in _SENTENCE_END.finditer(folded, 0, start):
        sentence_start = m.end()
    before = _WORD.findall(folded[sentence_start:start])[-_NEGATION_WINDOW:]
    if any(w in _NEGATION_BEFORE or w.endswith("n't") for w in before):
        return True

    word_end = end
    while word_end < len(folded) and re.match(r"\w", folded[word_end]):
        word_end += 1
    rest = folded[word_end:]
    cut = _SENTENCE_END.search(rest)
    if cut:
        rest = rest[:cut.start()]
    after = _WORD.findall(rest)[:_NEGATION_WINDOW]
    return any(w.startswith("degil") or w in _NEGATION_AFTER_EXACT for w in after)


def detect_moods(text: str) -> list[str]:
    """Mesajdaki olumsuzlanmamis duygular, mesajdaki ilk gorulme sirasiyla."""
    folded = _fold(text)
    first_seen: dict[str, int] = {}
    for mood, pattern in _PATTERNS:
        for m in pattern.finditer(folded):
            if _negated(folded, m.start(), m.end()):
                continue
            if mood not in first_seen or m.start() < first_seen[mood]:
                first_seen[mood] = m.start()
    return sorted(first_seen, key=first_seen.get)


def detect_mood(text: str) -> str | None:
    """Geriye uyumluluk: ilk duygu ya da None."""
    moods = detect_moods(text)
    return moods[0] if moods else None
