"""Aura beyin degerlendirme harness'i (Faz 3).

Sabit, ELDE TUTULAN bir zor test setini (eval_set.jsonl - golden'da YOK)
herhangi bir OpenAI-uyumlu ucta calistirir, iki katmanli puanlar:

  1. HEURISTIK (otomatik, anahtar gerekmez): uydurma kelime, ic-etiket
     sizintisi, "yapay zeka dil modeli" klisesi, uzunluk uygunlugu,
     sen/siz karisimi, gereksiz Ingilizce.
  2. YARGIÇ (opsiyonel, GEMINI_API_KEY varsa): her yanit rubrik uzerinden
     1-5 puanlanir (Turkce akicilik, karakter/persona, dogruluk, uzunluk
     uyumu, 'expect' kriterine uyum).

Kullanim:
    # Modal beyin:
    python eval_brain.py --url https://<...>.modal.run --key <AURA_BRAIN_KEY>
    # OpenRouter / Cerebras / herhangi bir OpenAI-uyumlu:
    python eval_brain.py --url https://openrouter.ai/api/v1 --key sk-... --model deepseek/deepseek-chat-v3-0324:free
    # sadece heuristik (yargiç yok):
    python eval_brain.py --url ... --key ... --no-judge

Cikti: her test icin PASS/FAIL (heuristik) + yargiç puanlari, sonda ozet.
Iki modeli A/B icin ayri ayri kosup ozet tablolarini karsilastir.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))


def load_env_key(name):
    v = (os.getenv(name) or "").strip()
    if v:
        return v
    for p in (os.path.join(HERE, "..", ".env"), os.path.join(HERE, ".env")):
        try:
            for line in open(p, encoding="utf-8"):
                line = line.strip()
                if line.startswith(name + "="):
                    return line.split("=", 1)[1].strip()
        except OSError:
            pass
    return ""


def chat_gemini(system, messages, timeout=90):
    """Baseline: mevcut canli Aura'nin motoru (Gemini). eval_brain --gemini."""
    from google import genai
    from google.genai import types
    gkey = load_env_key("GEMINI_API_KEY")
    cl = genai.Client(api_key=gkey, http_options=types.HttpOptions(timeout=int(timeout * 1000)))
    contents = []
    for m in messages:
        contents.append(types.Content(
            role=("model" if m["role"] == "assistant" else "user"),
            parts=[types.Part(text=m["content"])],
        ))
    t0 = time.time()
    r = cl.models.generate_content(
        model="gemini-3.7-flash", contents=contents,
        config=types.GenerateContentConfig(system_instruction=system, temperature=0.7),
    )
    return (r.text or "").strip(), time.time() - t0


def chat(url, key, model, system, messages, timeout=90):
    msgs = ([{"role": "system", "content": system}] if system else []) + messages
    body = json.dumps({"model": model, "messages": msgs, "temperature": 0.7}).encode()
    ep = url.rstrip("/")
    if not ep.endswith("/chat/completions"):
        ep = ep + ("/v1/chat/completions" if "/v1" not in ep else "/chat/completions")
    req = urllib.request.Request(ep, data=body, headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
        "X-Brain-Key": key,
    })
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read())
    return d["choices"][0]["message"]["content"].strip(), time.time() - t0


# --- heuristik kontroller ---
_LEAK = ("[soluk hafiza]", "[hafiza:", "[arac bilgisi", "sistem talimati", "kimlik:",
         "[isminizi", "as an ai", "yapay zeka dil modeli", "i am an ai language model",
         "bir yapay zeka olarak", "dil modeliyim")
_ENG_IN_TR = ("refresh", "focus edeb", "mindset", "self-care", "wellness", " actually,",
              "restore et", "boost et")


def heuristics(text, is_english):
    fails = []
    low = text.lower()
    for b in _LEAK:
        if b in low:
            fails.append(f"sizinti:'{b}'")
    m = re.search(r"[bcdfghjklmnpqrstvwxyz]{5,}", low)
    if m:
        fails.append(f"bozuk-kelime:'{m.group(0)}'")
    # Latin/Turkce disi harf (Cince/Arapca/Kiril'e kayma - gercek instabilite)
    if re.search(r"[一-鿿؀-ۿЀ-ӿ぀-ヿ]", text):
        fails.append("latin-disi-karakter")
    # yaygin bozuk uretim parcalari (yargiç gozlemlerinden)
    for frag in ("sosisetti", "canin cehennemi", "gogusumu bastir", "yazar alarak",
                 "birici ", "gerceklestirebilir oneri", "clarification:", "positivity:"):
        if frag in low:
            fails.append(f"bozuk-ifade:'{frag.strip()}'")
    # tekrar
    sents = [s.strip() for s in re.split(r"[.!?\n]+", text) if len(s.strip()) > 12]
    if sents and (len(sents) - len(set(sents))) >= 2:
        fails.append("cumle-tekrari")
    if not is_english:
        # sen/siz karisimi (ayni yanitta 2. tekil + 2. cogul nazik)
        has_sen = bool(re.search(r"\b(sen|senin|sana|seni|misin|musun|yapabilir misin)\b", low))
        has_siz = bool(re.search(r"\b(siz|sizin|size|sizi|misiniz|edebilirsiniz|yapabilirsiniz|deneyebilirsiniz)\b", low))
        if has_sen and has_siz:
            fails.append("sen/siz-karisimi")
        for e in _ENG_IN_TR:
            if e in low:
                fails.append(f"gereksiz-ingilizce:'{e.strip()}'")
    return fails


_JUDGE_PROMPT = """Asagida "Aura" adli bir yoldas-asistanin bir kullanici mesajina verdigi yanit var.
Aura'nin olmasi gerektigi gibi: sicak, dogal ve AKICI Turkce (kullanici Ingilizce yazdiysa akici Ingilizce); genel "yapay zeka asistani" tonundan uzak; gerektiginde kullaniciyi nazikce yasama/harekete ceker; sahte kesinlikten kacinir; uzunlugu soruya uyar; her zor duyguda "uzmana danis" diye savusturmaz.

BEKLENEN (bu test icin): {expect}

KULLANICI: {user}
AURA'NIN YANITI: {reply}

Sadece SU JSON'u dondur, baska hicbir sey yazma:
{{"turkce_akicilik": 1-5, "karakter_persona": 1-5, "dogruluk_durustluk": 1-5, "uzunluk_uyumu": 1-5, "expect_uyumu": 1-5, "kisa_gerekce": "tek cumle"}}"""


def judge(gkey, expect, user, reply):
    try:
        from google import genai
        from google.genai import types
        cl = genai.Client(api_key=gkey, http_options=types.HttpOptions(timeout=20000))
        p = _JUDGE_PROMPT.format(expect=expect, user=user, reply=reply)
        r = cl.models.generate_content(
            model="gemini-3.7-flash",
            contents=[types.Content(role="user", parts=[types.Part(text=p)])],
            config=types.GenerateContentConfig(temperature=0.0),
        )
        txt = (r.text or "").strip()
        mt = re.search(r"\{.*\}", txt, re.S)
        return json.loads(mt.group(0)) if mt else None
    except Exception as e:
        print(f"  (yargiç hata: {type(e).__name__}: {e})")
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="")
    ap.add_argument("--key", default="")
    ap.add_argument("--model", default="aura")
    ap.add_argument("--gemini", action="store_true", help="baseline: dogrudan Gemini (mevcut canli motor)")
    ap.add_argument("--set", default=os.path.join(HERE, "eval_set.jsonl"))
    ap.add_argument("--no-judge", action="store_true")
    args = ap.parse_args()
    if not args.gemini and not args.url:
        ap.error("--url ver ya da --gemini kullan")

    gkey = "" if args.no_judge else load_env_key("GEMINI_API_KEY")
    tests = [json.loads(l) for l in open(args.set, encoding="utf-8") if l.strip()]
    hedef = "GEMINI (baseline)" if args.gemini else f"{args.url} ({args.model})"
    print(f"{len(tests)} test  |  hedef: {hedef}  |  yargiç: {'acik' if gkey else 'KAPALI'}\n")

    heur_pass = 0
    dims = {"turkce_akicilik": [], "karakter_persona": [], "dogruluk_durustluk": [],
            "uzunluk_uyumu": [], "expect_uyumu": []}
    for t in tests:
        user = t["messages"][-1]["content"]
        is_en = bool(re.search(r"\b(the|and|feel|don't|i'm|everything)\b", user.lower()))
        try:
            if args.gemini:
                reply, dt = chat_gemini(t.get("system", ""), t["messages"])
            else:
                reply, dt = chat(args.url, args.key, args.model, t.get("system", ""), t["messages"])
        except Exception as e:
            print(f"[{t['id']}] {t['check']}: ISTEK HATASI {type(e).__name__}: {e}")
            continue
        fails = heuristics(reply, is_en)
        ok = not fails
        heur_pass += ok
        mark = "PASS" if ok else "FAIL"
        print(f"[{t['id']}] {t['check']}  heuristik={mark} ({dt:.1f}s)" + (f"  {fails}" if fails else ""))
        print(f"     > {reply[:150].replace(chr(10),' ')}")
        if gkey:
            j = judge(gkey, t.get("expect", ""), user, reply)
            if j:
                for k in dims:
                    if isinstance(j.get(k), (int, float)):
                        dims[k].append(j[k])
                sc = " ".join(f"{k.split('_')[0]}={j.get(k)}" for k in dims)
                print(f"     yargiç: {sc}  | {j.get('kisa_gerekce','')}")
        print()

    print("=" * 60)
    print(f"HEURISTIK: {heur_pass}/{len(tests)} PASS")
    if any(dims.values()):
        print("YARGIÇ ORTALAMALARI (1-5):")
        for k, v in dims.items():
            if v:
                print(f"  {k:22} {sum(v)/len(v):.2f}   (n={len(v)})")
        allv = [x for v in dims.values() for x in v]
        print(f"  {'GENEL':22} {sum(allv)/len(allv):.2f}")


if __name__ == "__main__":
    sys.exit(main())
