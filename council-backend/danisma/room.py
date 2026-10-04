"""
Danisma Odasi - cekirdek mantik (arayuzden bagimsiz).

Sign Council'in YouTube karakterlerinden BAGIMSIZ: gercek veri paketiyle,
kor ilk tur + capraz elestiri + takip sorulariyla calisan bir calisma masasi.
Saglayici katmani (providers.py) ayni, personalar/orkestrator kullanilmaz.

Ilkeler (ilk iki turdaki sorunlardan cikarildi):
- KOR TUR: uyeler birbirinin cevabini gormeden cevaplar (dusunce akisi yok).
- ZORUNLU SEMA: iddia + kanit + guven; "bilmiyorum" hakki. Kaynaksiz sayi
  otomatik isaretlenir (bkz. flag_unsupported_numbers).
- GERCEK VERI: secilen repo dosyalari soruyla birlikte gider.
- Anahtar degerleri ASLA ciktiya/loga girmez (redact).
"""
import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor

import providers
from providers import PROVIDER_CALLERS, MissingApiKeyError

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SESSIONS_DIR = os.path.join(REPO_ROOT, "docs", "danisma")
MAX_CONTEXT_CHARS = 40_000

# saglayici anahtari -> (gorunen ad, anahtar degiskeni)
PROVIDERS = {
    "gemini": ("Gemini", "GEMINI_API_KEY"),
    "openai": ("OpenAI (GPT)", "OPENAI_API_KEY"),
    "anthropic": ("Anthropic (Claude API)", "ANTHROPIC_API_KEY"),
    "xai": ("xAI (Grok)", "XAI_API_KEY"),
    "groq": ("Groq (acik model)", "GROQ_API_KEY"),
}

# Varsayilan roller: soruya gore arayuzden degistirilebilir.
DEFAULT_ROLES = [
    "Urun ve gorsel tasarim stratejisti",
    "Psikolog / etik uzmani (bagimlilik, kirilgan kullanici)",
    "Teknik mimar (Flutter, performans, backend)",
    "Supheci denetci (iddialari yikar, rakam/kanit ister)",
    "Pazar ve rakip analisti",
]

_pool = ThreadPoolExecutor(max_workers=8)


# ---------------------------------------------------------------- guvenlik
def _secrets():
    vals = [
        providers.GEMINI_API_KEY, providers.OPENAI_API_KEY,
        providers.ANTHROPIC_API_KEY, providers.XAI_API_KEY,
        providers.GROQ_API_KEY,
    ]
    return [v for v in vals if v and len(v) >= 8]


def redact(text):
    text = str(text)
    for s in _secrets():
        text = text.replace(s, "[ANAHTAR]")
    return text


# ------------------------------------------------------------------- uyeler
def key_present(provider):
    return bool(getattr(providers, PROVIDERS[provider][1], ""))


def _call(provider, messages, system):
    return PROVIDER_CALLERS[provider](messages, system)


def probe_provider(provider):
    """Kucuk bir istekle anahtarin GERCEKTEN calistigini dogrular."""
    name, env_var = PROVIDERS[provider]
    if not key_present(provider):
        return {"provider": provider, "name": name, "status": "yok",
                "detail": f"{env_var} bos/tanimsiz"}
    t0 = time.time()
    try:
        out = _call(provider, [{"role": "user", "content": "Sadece 'tamam' yaz."}],
                    "Kisa cevap ver.")
        if not out.strip():
            return {"provider": provider, "name": name, "status": "hata",
                    "detail": "bos cevap dondu"}
        return {"provider": provider, "name": name, "status": "ok",
                "detail": f"{time.time() - t0:.1f} sn"}
    except Exception as e:  # noqa: BLE001 - arayuze sade mesaj gerekir
        return {"provider": provider, "name": name, "status": "hata",
                "detail": redact(f"{type(e).__name__}: {e}")[:240]}


def probe_all():
    futures = {p: _pool.submit(probe_provider, p) for p in PROVIDERS}
    return [futures[p].result() for p in PROVIDERS]


# --------------------------------------------------------------- veri paketi
def load_context(paths):
    """Repo icinden dosya okur; repo disina cikmayi engeller."""
    chunks, used = [], 0
    for rel in paths:
        rel = rel.strip().replace("\\", "/")
        if not rel:
            continue
        full = os.path.abspath(os.path.join(REPO_ROOT, rel))
        if not full.startswith(REPO_ROOT + os.sep) or not os.path.isfile(full):
            chunks.append(f"### {rel}\n[DOSYA BULUNAMADI]")
            continue
        with open(full, encoding="utf-8", errors="replace") as f:
            body = f.read()
        room = MAX_CONTEXT_CHARS - used
        if room <= 0:
            chunks.append(f"### {rel}\n[LIMIT ASILDI, atlandi]")
            continue
        body = body[:room]
        used += len(body)
        chunks.append(f"### {rel}\n{body}")
    return "\n\n".join(chunks)


# ------------------------------------------------------------------ istemler
SCHEMA_NOTE = """CIKTI BICIMI - yalnizca gecerli JSON, baska hicbir sey yazma:
{
  "cevap": "kisa ana cevap (en fazla 150 kelime, Turkce)",
  "iddialar": [
    {"metin": "tek bir somut iddia",
     "kanit": "baglamdaki hangi dosya/satirdan ya da hangi bilinen gercekten; yoksa 'dogrulanmadi'",
     "guven": "yuksek | orta | dusuk"}
  ],
  "oneriler": ["uygulanabilir somut oneri"],
  "bilmiyorum": ["emin olmadigin ya da veri gerektiren konular"]
}
KURALLAR:
- Kaynagi olmayan rakam, yuzde, maliyet, tarih UYDURMA. Bilmiyorsan 'bilmiyorum' listesine yaz.
- Jenerik cumle (sakin bir isik, kullanici ile uyum, vb.) yasak; uygulanabilir somutluk.
- Rakip iddiasi yapiyorsan nereden bildigini kanit alaninda belirt, emin degilsen 'dogrulanmadi'.
- Rolun disina cikma, ama baska uzmanligin hatasini gorursen belirt."""


def _system(role, phase_note):
    return (
        f"Sen bir danisma odasinin uyesisin. Rolun: {role}.\n"
        "Soruyu soran, Aura adli bir yapay zeka yoldas uygulamasinin sahibi; "
        "gercek bir urun karari icin ortak calisiyorsunuz. Dogrudan ve durust ol.\n"
        f"{phase_note}\n\n{SCHEMA_NOTE}"
    )


def _parse(raw):
    """Saglayicilar farkli bicimde dondurur; JSON'u toleransli ayikla."""
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if fence:
        text = fence.group(1)
    else:
        a, b = text.find("{"), text.rfind("}")
        if a != -1 and b > a:
            text = text[a:b + 1]
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            data.setdefault("cevap", "")
            data.setdefault("iddialar", [])
            data.setdefault("oneriler", [])
            data.setdefault("bilmiyorum", [])
            return data, True
    except json.JSONDecodeError:
        pass
    return {"cevap": raw.strip(), "iddialar": [], "oneriler": [],
            "bilmiyorum": [], }, False


_NUM = re.compile(r"\d")


def flag_unsupported_numbers(parsed):
    """Rakam iceren iddia + kanitsiz/dogrulanmadi -> uyari."""
    warns = []
    for c in parsed.get("iddialar", []):
        if not isinstance(c, dict):
            continue
        txt, ev = str(c.get("metin", "")), str(c.get("kanit", "")).lower()
        if _NUM.search(txt) and (not ev.strip() or "dogrulanmad" in ev
                                 or "doğrulanmad" in ev):
            warns.append(f"Kaynaksiz sayi: {txt[:140]}")
    if _NUM.search(parsed.get("cevap", "")) and not parsed.get("iddialar"):
        warns.append("Ana cevapta sayi var ama iddia/kanit listesi bos.")
    return warns


# ------------------------------------------------------------------- turlar
def _ask_member(m, user_text, system):
    try:
        raw = _call(m["provider"], [{"role": "user", "content": user_text}], system)
        parsed, ok = _parse(redact(raw))
        return {"member": m["id"], "label": m["label"], "role": m["role"],
                "ok": True, "json_ok": ok, "data": parsed,
                "warnings": flag_unsupported_numbers(parsed)}
    except MissingApiKeyError as e:
        return {"member": m["id"], "label": m["label"], "role": m["role"],
                "ok": False, "error": redact(e)}
    except Exception as e:  # noqa: BLE001
        return {"member": m["id"], "label": m["label"], "role": m["role"],
                "ok": False, "error": redact(f"{type(e).__name__}: {e}")[:300]}


def _run_round(members, user_text_for, phase_note):
    futs = [_pool.submit(_ask_member, m, user_text_for(m),
                         _system(m["role"], phase_note)) for m in members]
    return [f.result() for f in futs]


def blind_round(members, question, context):
    def text(_m):
        return (f"SORU:\n{question}\n\nVERI PAKETI (gercek dosyalar):\n{context}\n")
    return _run_round(
        members, text,
        "KOR TUR: diger uyelerin ne dedigini BILMIYORSUN. Kendi uzmanligindan, bagimsiz cevapla.")


def _digest(answers, exclude_member=None):
    parts = []
    for a in answers:
        if a["member"] == exclude_member or not a.get("ok", True):
            continue
        d = a["data"]
        parts.append(
            f"--- {a['role']} ---\nCevap: {d.get('cevap','')}\n"
            f"Iddialar: {json.dumps(d.get('iddialar', []), ensure_ascii=False)}\n"
            f"Oneriler: {json.dumps(d.get('oneriler', []), ensure_ascii=False)}")
    return "\n\n".join(parts)


def critique_round(members, question, context, answers):
    def text(m):
        return (f"SORU:\n{question}\n\nVERI PAKETI:\n{context}\n\n"
                f"DIGER UYELERIN KOR TUR CEVAPLARI (rol etiketiyle):\n"
                f"{_digest(answers, exclude_member=m['id'])}\n")
    return _run_round(
        members, text,
        "CAPRAZ ELESTIRI TURU: yukaridaki cevaplarin EN ZAYIF noktasini rolunden bul "
        "(uydurma/kaynaksiz rakam, jenerik cumle, etik risk, uygulanamazlik). "
        "'cevap' alanina: hangi fikre katiliyorsun/katilmiyorsun ve nihai guncel onerin. "
        "'iddialar' alanina: bulduklarin hatalar, kanit alanina hangi cevaptan aldigini yaz.")


def followup_round(members, question, context, history, text):
    def msg(m):
        return (f"ILK SORU:\n{question}\n\nVERI PAKETI:\n{context}\n\n"
                f"ONCEKI TARTISMA (ozet):\n{history}\n\n"
                f"YENI SORU/YONERGE (sahibinden):\n{text}\n")
    return _run_round(members, msg,
                      "TAKIP: sahibi yeni bir soru ya da yonerge verdi. Rolunden cevapla.")


# ---------------------------------------------------------------- kayit
def new_session_id():
    return time.strftime("%Y%m%d-%H%M%S")


def save_session(session):
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    base = os.path.join(SESSIONS_DIR, session["id"])
    with open(base + ".json", "w", encoding="utf-8") as f:
        json.dump(session, f, ensure_ascii=False, indent=2)
    with open(base + ".md", "w", encoding="utf-8") as f:
        f.write(render_markdown(session))


def render_markdown(s):
    out = [f"# Danisma Odasi oturumu {s['id']}\n", f"**Soru:** {s['question']}\n",
           "**Veri paketi:** " + ", ".join(s.get("context_paths", [])) + "\n"]
    for r in s["rounds"]:
        out.append(f"\n## {r['title']}\n")
        for a in r["answers"]:
            out.append(f"### {a['label']} - {a['role']}\n")
            if not a.get("ok", True):
                out.append(f"_Hata:_ {a.get('error')}\n")
                continue
            d = a["data"]
            out.append(f"{d.get('cevap','')}\n")
            for c in d.get("iddialar", []):
                if isinstance(c, dict):
                    out.append(f"- **Iddia:** {c.get('metin')} _(kanit: {c.get('kanit')}, guven: {c.get('guven')})_")
            for o in d.get("oneriler", []):
                out.append(f"- Oneri: {o}")
            for b in d.get("bilmiyorum", []):
                out.append(f"- Bilmiyorum: {b}")
            for w in a.get("warnings", []):
                out.append(f"- WARN {w}")
            out.append("")
    return "\n".join(out) + "\n"
