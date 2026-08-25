"""
4 farkli LLM saglayicisina (OpenAI, Anthropic, Groq, Gemini - Sign Council'i
zaten calistiran ayni saglayicilar), kanalin GERCEK verilerini verip
BAGIMSIZ, birbirini gormeyen bir buyume/SEO elestirisi yazdirir.

Bu bir "algoritma aktivasyonu" degil - sihirli bir izlenme dugmesi yok.
Sadece 4 farkli modelin gercek verilere dayanan gercek onerilerini toplar.

Kullanim:
    python ask_growth_advice.py
"""
import sys

sys.stdout.reconfigure(errors="replace")

from providers import PROVIDER_CALLERS, MissingApiKeyError

CHANNEL_BRIEF = """
Kanal: Sign Council (YouTube, @SignCouncil_AI, https://www.youtube.com/channel/UCMrmC729n7NXoziJeHfUEuw)
Format: 5 farkli AI ajaninin (Aura=moderator/Gemini, Alpha=analitik/OpenAI,
Beta=asi-gercekci/Groq, Gamma=etik/Anthropic, Delta=sentez/Gemini) gercek
guncel haberler uzerine, birbirini gormeden sira-bazli tartistigi bir
"AI konseyi" programi. Slogan: "5 Minds. Zero Humans."

Gercek durum (25 Agustos 2026, kanal 2 gunluk):
- 6 abone
- Toplam 280 izlenme (tum icerik)
- 4 uzun bolum (2-183 izlenme arasi, en iyisi teaser: 183)
- 9 Shorts (4-17 izlenme arasi, 24 saatte)
- Neredeyse hic organik yorum yok
- Ingilizce icerik, global kitle hedefleniyor
- Konular: guncel AI haberleri (orn. AB'nin AI aciklama yasasi, DARPA F-16)

Soru: Bu kanalin gercekci, uygulanabilir 3 buyume onerisini ver - genel
"tutarli ol, SEO yap" gibi klise tavsiyeler degil, bu SPESIFIK formata ve
bu asamaya (2 gunluk, 6 abone) ozel, somut oneriler. Abartili vaatte
bulunma, gercekci ol. En fazla 150 kelime.
"""

PROVIDERS_TO_ASK = {
    "OpenAI (GPT)": "openai",
    "Anthropic (Claude)": "anthropic",
    "Groq (acik model)": "groq",
    "Gemini": "gemini",
}

SYSTEM = (
    "You are a blunt, experienced YouTube growth strategist. Give honest, "
    "specific, non-generic advice. No flattery, no hype. Respond in Turkish."
)


def main():
    print("=== 4 farkli AI saglayicisina bagimsiz buyume analizi soruluyor ===\n")
    for label, provider_key in PROVIDERS_TO_ASK.items():
        caller = PROVIDER_CALLERS[provider_key]
        try:
            answer = caller([{"role": "user", "content": CHANNEL_BRIEF}], SYSTEM)
        except MissingApiKeyError as e:
            answer = f"[ATLANDI - {e}]"
        except Exception as e:
            answer = f"[HATA - {type(e).__name__}: {e}]"
        print(f"--- {label} ---")
        print(answer)
        print()


if __name__ == "__main__":
    main()
