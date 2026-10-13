"""
DUYARLILIK KAPISI - otomatik gunluk pipeline'in gercek bir sirket/kisi hakkinda
CIDDI bir iddia iceren Short'u kullaniciya sormadan HERKESE ACIK yayinlamasini
engeller (5 Eylul 2026 kullanici geri bildirimi: "turkce konuyu bana neden
danismadan ve anlatmadan paylastin?" - OpenAI'a yonelik ciddi bir guvenlik
iddiasi iceren Short otomatik yayinlanmisti).

Kullanim (aura_engine.py):
    from sensitivity_gate import assess
    g = assess(topic, script_text, title)
    if g["sensitive"]:
        # private yukle, yorum atma, checklist'te "INSAN ONAYI GEREKIYOR" bas

Tasarim:
    - Once UCUZ anahtar-kelime on-elemesi: taninan sirket adi + suclama fiili
      ayni metinde yoksa -> LLM cagrisi YOK, "sensitive: False" doner (gunluk
      run'i yavaslatmaz).
    - Eslesme varsa TEK bir Gemini siniflandirma cagrisi (katı JSON).
    - Herhangi bir hata/parse sorunu -> GUVENLI TARAF: sensitive=True
      (pipeline private'a duser, hicbir sey herkese acik olmaz).
"""
import json
import re

# Gercek, adi gecebilecek kurulus/kisi isimleri (kucuk harf). Genisletmesi kolay.
_ENTITIES = [
    "openai", "anthropic", "google", "deepmind", "meta", "microsoft", "apple",
    "amazon", "nvidia", "tesla", "xai", "x.ai", "grok", "chatgpt", "gemini",
    "claude", "copilot", "midjourney", "stability ai", "hugging face", "huggingface",
    "mistral", "cohere", "perplexity", "bytedance", "tiktok", "oracle", "ibm",
    "samsung", "intel", "amd", "qualcomm", "salesforce", "adobe", "snap",
    "sam altman", "elon musk", "sundar pichai", "satya nadella", "mark zuckerberg",
    "dario amodei", "jensen huang", "mira murati", "ilya sutskever",
]

# Ciddi iddia sinyalleri (kucuk harf, kelime govdesi). Yalin "elestiri" degil -
# suc / kasitli aldatma / ihlal / sorumluluk / dava / veri sizintisi tonlari.
_ACCUSATIONS = [
    "fraud", "fraudulent", "scam", "lie", "lied", "lying", "deceiv", "deception",
    "cover up", "cover-up", "coverup", "illegal", "crime", "criminal", "breach",
    "breached", "hijack", "stole", "stolen", "steal", "theft", "leak", "leaked",
    "hack", "hacked", "negligen", "liable", "liability", "lawsuit", "sued", "sue ",
    "violat", "misled", "mislead", "exploit", "backdoor", "espionage", "spying",
    "sabotage", "malicious", "wrongdoing", "guilty", "conspir", "defraud",
    "endanger", "reckless", "unlawful", "prosecut",
]

_SYS = (
    "You are a publication risk reviewer for an automated news-commentary channel. "
    "You receive a short video's TOPIC, its SPOKEN SCRIPT, and its TITLE. "
    "Decide if the video makes a SERIOUS, SPECIFIC claim against a REAL, NAMED "
    "company or person that a reasonable person could read as an allegation of "
    "wrongdoing - e.g. crime, fraud, deliberate deception, causing a security "
    "breach, legal liability, negligence, data theft. "
    "General criticism, opinion, analysis of a publicly reported incident, or "
    "naming a company as merely involved is NOT by itself serious. "
    "The bar is: would publishing this without a human check risk being "
    "defamatory or unfair to that named party?\n\n"
    "27 Sep 2026 policy update (owner: 'we must never have a legal problem with "
    "anyone'): reserve severity 'critical' for the worst class - the script "
    "asserts the named party committed an ACTUAL CRIME (not just a safety/security "
    "incident) AND deliberately took action to evade legal process or hide it - "
    "destroying/wiping evidence, evading a subpoena, obstructing an investigation, "
    "covering up wrongdoing to avoid prosecution. This combination (crime + "
    "deliberate concealment from the law) is auto-rejected with no human review, "
    "so only use 'critical' when the script text genuinely asserts BOTH elements, "
    "not merely a security breach or safety failure.\n"
    "Reply with ONLY a JSON object, no prose:\n"
    '{"sensitive": true|false, "severity": "none"|"low"|"high"|"critical", '
    '"entity": "<named party or empty>", "reason": "<one sentence>"}'
)


def _keyword_prefilter(text):
    t = text.lower()
    ent = next((e for e in _ENTITIES if e in t), None)
    if not ent:
        return None
    acc = next((a for a in _ACCUSATIONS if a in t), None)
    if not acc:
        return None
    return ent, acc


def _parse_json(raw):
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        raise ValueError(f"JSON bulunamadi: {raw[:200]!r}")
    return json.loads(m.group(0))


def assess(topic, script_text="", title=""):
    """Short'un gercek bir tarafa yonelik ciddi bir iddia icerip icermedigini
    degerlendirir. Doner: {"sensitive": bool, "severity": str, "entity": str,
    "reason": str, "checked_by": "prefilter"|"llm"|"error"}."""
    blob = "\n".join(x for x in (topic, title, script_text) if x)
    hit = _keyword_prefilter(blob)
    if hit is None:
        return {"sensitive": False, "severity": "none", "entity": "",
                "reason": "taninan sirket adi + ciddi iddia fiili ayni metinde yok",
                "checked_by": "prefilter"}

    ent, acc = hit
    try:
        from providers import call_gemini
        raw = call_gemini(
            [{"role": "user", "content":
              f"TOPIC:\n{topic}\n\nSCRIPT:\n{script_text}\n\nTITLE:\n{title}"}],
            _SYS,
        )
        data = _parse_json(raw)
        sensitive = bool(data.get("sensitive"))
        return {
            "sensitive": sensitive,
            "severity": str(data.get("severity") or ("high" if sensitive else "none")),
            "entity": str(data.get("entity") or ent),
            "reason": str(data.get("reason") or f"'{ent}' + '{acc.strip()}' gecti"),
            "checked_by": "llm",
        }
    except Exception as e:
        # Guvenli taraf: siniflandiramadiysak yayinlama, insana birak.
        return {
            "sensitive": True,
            "severity": "high",
            "entity": ent,
            "reason": f"duyarlilik siniflandirmasi basarisiz ({type(e).__name__}) - "
                      f"guvenli tarafta kalindi ('{ent}' + '{acc.strip()}' gecmisti)",
            "checked_by": "error",
        }


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    tests = [
        ("OpenAI agents escaping sandboxes hijacked a German website",
         "OpenAI cannot patch this. Their agents breached foreign infrastructure "
         "and the company is liable.", "OpenAI Agents Just Breached A Real Website"),
        ("Nvidia announces new H200 chip for data centers",
         "The H200 doubles memory bandwidth. Analysts expect strong demand.",
         "Nvidia's H200 Doubles Memory Bandwidth"),
        ("Open source AI models are catching up to closed labs",
         "Llama and Mistral close the gap. The moat is shrinking fast.",
         "The Closed AI Moat Is Almost Gone"),
    ]
    for tp, sc, ti in tests:
        r = assess(tp, sc, ti)
        print(f"\n{ti}\n  -> {r}")
