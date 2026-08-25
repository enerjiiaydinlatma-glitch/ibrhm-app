"""
Aura'nin (kisisel asistan UYGULAMASI - Sign Council'daki show karakteri
DEGIL, gercek Flutter+FastAPI urunu) gercek ozellik setini 4 farkli LLM
saglayicisina AYRI AYRI verip derin, elestirel bir urun analizi ister.

Ozellik listesi kod tabanindan (auro-backend/, lib/) cikarildi - tahmin
degil. bkz. ask_growth_advice.py / ask_aura_critique.py (ayni desen).

Kullanim:
    python ask_aura_app_analysis.py
"""
import sys

sys.stdout.reconfigure(errors="replace")

from providers import PROVIDER_CALLERS, MissingApiKeyError

APP_BRIEF = """
Asagida "Aura" adli, gercekten gelistirilmis (canli, kullanicisi olan) bir
kisisel AI asistan uygulamasinin GERCEK ozellik listesi var (Flutter mobil
uygulama + FastAPI backend, tek gelistirici tarafindan yapildi):

TEMEL SOHBET:
- Metin sohbeti (normal + streaming)
- Gercek zamanli SESLI konusma - kullanici konusurken AI'yi KESEBILIYOR
  (interrupt/barge-in destekli, Gemini Live API uzerinden WebSocket relay)
- TTS (metin-konusma) ayri endpoint olarak da mevcut

HAFIZA VE KISISELLESTIRME:
- Kalici hafiza sistemi (SQLite) - konusmalardan otomatik "hafiza adayi"
  cikarir, guven skoruna gore hafizaya terfi ettirir
- Kullanici hafizalari goruntuleyebilir/silebilir (kullanici kontrolu var)
- "Familiarity threshold" - AI'nin ton/samimiyet seviyesi zamanla,
  kademeli olarak degisiyor (ilk gunlerde "kanka/dostum" gibi sahte-samimi
  hitaplar YASAKLI - bilincli bir tasarim karari)

PROAKTIF "YASAM" FARKINDALIGI (lifestyle nudges):
- Hava durumuna gore dogal referans (Open-Meteo API, gercek konum)
- Kullanicinin bahsettigi rutinleri (kahve, yuruyus vb.) takip edip uzun
  suredir bahsedilmemisse hatirlatma sinyali uretme
- Bahsedilen ama sonucu takip edilmemis gundem/etkinlikleri (sinav,
  toplanti) fark etme
- Davranis oruntusu (pattern) tespiti ve icgoru uretme

SOSYAL KATMAN (diger AI asistanlarinda genelde OLMAYAN bir sey):
- Arkadas sistemi (istek gonder/kabul et/liste)
- "Story" feed'i - kullanicilar AI ile ilgili icerik paylasabiliyor,
  feed'de goruntuleniyor
- /api/analyze ve /api/story adli uretim uclari (detay verilmedi)

MIMARI KARAR: kullaniciya cevap veren "ses" (Gemini) ile arka planda
sessizce hafiza cikaran "ajan" (Groq) BILINCLI olarak farkli saglayicilar -
yani tek bir monolit model degil, gorev-bazli boluk var.

Soru - dublansiz, somut, Turkce cevap ver (en fazla 180 kelime):
1. ChatGPT/Claude/Gemini/Grok gibi ana akim AI asistan uygulamalarinda
   OLUP Aura'da OLMAYAN, gercekten onemli 2-3 sey ne?
2. Aura'da olup o ana akim uygulamalarda GENELDE olmayan, gercek bir
   avantaj sayilabilecek sey ne? (Varsa - yoksa "yok" de, ovgu icin
   uydurma.)
3. Bu ozellik setine bakarak, Aura'nin bundan sonra gelistirmesi gereken
   EN ONEMLI 2 sey ne? (Konsept degil, somut/uygulanabilir olsun.)
4. Sosyal katman (arkadas + story feed) bir kisisel AI asistaninda
   gercekten mantikli mi, yoksa odak dagitan bir ek mi? Dogrudan cevap ver.
"""

PROVIDERS_TO_ASK = {
    "OpenAI (GPT)": "openai",
    "Anthropic (Claude)": "anthropic",
    "Groq (acik model)": "groq",
    "Gemini": "gemini",
}

SYSTEM = (
    "You are a blunt, senior AI product strategist reviewing a real, "
    "shipped consumer AI app for the first time. No flattery, no hedging. "
    "Ground every claim in the specific facts given - do not invent "
    "features. Respond in Turkish."
)


def main():
    print("=== Aura UYGULAMASI - 4 bagimsiz AI derin analiz ===\n")
    for label, provider_key in PROVIDERS_TO_ASK.items():
        caller = PROVIDER_CALLERS[provider_key]
        try:
            answer = caller([{"role": "user", "content": APP_BRIEF}], SYSTEM)
        except MissingApiKeyError as e:
            answer = f"[ATLANDI - {e}]"
        except Exception as e:
            answer = f"[HATA - {type(e).__name__}: {e}]"
        print(f"--- {label} ---")
        print(answer)
        print()


if __name__ == "__main__":
    main()
