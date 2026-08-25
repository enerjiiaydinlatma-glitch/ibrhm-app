"""
Aura'nin (Sign Council'in ana karakteri) kisilik/karakter tasarimini,
4 farkli LLM saglayicisina (OpenAI, Anthropic, Groq, Gemini) AYRI AYRI,
birbirini gormeden, GERCEK bir elestiri istegiyle sorar.

Amac ovgu toplamak degil - Aura'nin gercekten ayirt edici olup olmadigini,
zayif noktalarini, "neden Aura" sorusuna dogru bir cevap olup olmadigini
gormek. bkz. ask_growth_advice.py (ayni desen, farkli konu).

Kullanim:
    python ask_aura_critique.py
"""
import sys

sys.stdout.reconfigure(errors="replace")

from personas import PERSONAS
from providers import PROVIDER_CALLERS, MissingApiKeyError

AURA_SYSTEM_INSTRUCTION = PERSONAS["aura"]["system_instruction"]

BRIEF = f"""
Asagida "Aura" adli bir AI karakterinin gercek sistem talimati var - bu,
"Sign Council" adli bir YouTube programinda 5 AI ajanini yoneten, ana
karakter olarak tasarlanmis bir persona:

---
{AURA_SYSTEM_INSTRUCTION}
---

Sen bu karakteri ilk kez goruyorsun, tasarimcisi degilsin. Dublansiz,
gercek bir elestiri yap:

1. Bu tanim, gercekten ayirt edici bir karakter mi yoksa jenerik bir
   "moderator AI" tanimi mi? Somut ol.
2. En buyuk zayif noktasi ne? (Belirsizlik, cliche ifadeler, catisan
   talimatlar, gerceklestirilmesi zor vaatler vb.)
3. "Neden Aura'yi izleyeyim, neden baska bir AI karakteri degil" sorusuna
   bu tanim gercekten bir cevap veriyor mu? Vermiyorsa neden.
4. Eger 1 sey degistirebilseydin, ne degistirirdin?

Ovgu bekleme, dogrudan ve kisa yaz (en fazla 130 kelime). Turkce cevap ver.
"""

PROVIDERS_TO_ASK = {
    "OpenAI (GPT)": "openai",
    "Anthropic (Claude)": "anthropic",
    "Groq (acik model)": "groq",
    "Gemini": "gemini",
}

SYSTEM = (
    "You are a skeptical character/brand consultant reviewing an AI "
    "persona design for the first time. You did not design it. Give a "
    "blunt, specific critique - no praise, no hedging. Respond in Turkish."
)


def main():
    print("=== Aura karakteri - 4 bagimsiz AI elestirisi ===\n")
    for label, provider_key in PROVIDERS_TO_ASK.items():
        caller = PROVIDER_CALLERS[provider_key]
        try:
            answer = caller([{"role": "user", "content": BRIEF}], SYSTEM)
        except MissingApiKeyError as e:
            answer = f"[ATLANDI - {e}]"
        except Exception as e:
            answer = f"[HATA - {type(e).__name__}: {e}]"
        print(f"--- {label} ---")
        print(answer)
        print()


if __name__ == "__main__":
    main()
