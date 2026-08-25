"""
Onceki iki turun (ask_aura_critique.py, ask_aura_app_analysis.py) devami -
kullanicinin 5 keskin takip sorusunu, ayni 4 saglayiciya AYRI AYRI sorar.

Ilk soru icin ONEMLI DUZELTME: /api/analyze GERCEKTEN VAR ve calisiyor
(Gemini vision, fotograf yukleyip nesnel+duygusal analiz aliyor) - ama
main.py'de dogrulandi ki SONUCU DOGRUDAN KULLANICIYA DONUYOR, aura_memory
veya aura_lifestyle'a HICBIR SEKILDE yazilmiyor. Yani ozellik var ama
izole/tek-seferlik, surekli hafiza/rutin sistemine entegre degil.

Kullanim:
    python ask_aura_deep_dive.py
"""
import sys

sys.stdout.reconfigure(errors="replace")

from providers import PROVIDER_CALLERS, MissingApiKeyError

CONTEXT = """
(Onceki turda sana Aura'nin ozellik listesi verilip elestiri istenmisti;
sen de "gorsel/multimodal analiz eksik" ve "familiarity threshold + kademeli
hafiza gercek bir avantaj" gibi bulgular vermistin - simdi ayni konunun
devami, 5 takip sorusu var. Kendi onceki cevabini gormuyorsun, o yuzden
her soruyu bagimsiz, kendi mantiginla cevapla.)

DUZELTME/NETLIK: Aura'nin GERCEKTEN calisan bir /api/analyze endpoint'i
var - kullanici fotograf gonderiyor, Gemini vision ile "nesnel analiz +
duygusal yorum" aliyor. AMA kod dogrulandi: bu sonuc SADECE kullaniciya
donuyor, aura_memory (kalici hafiza) veya aura_lifestyle (rutin/yasam
takibi) sistemine HICBIR sekilde yazilmiyor - izole, tek seferlik bir
ozellik, surekliligi yok.

Su 5 soruyu TEK TEK, numarali, somut ve Turkce cevapla (toplam en fazla
320 kelime, soyut/genel gecmeyen, direkt cevaplar):

1. NETLIK: Yukaridaki duzeltmeyle "gorsel analiz eksik" bulgun degisir mi,
   yoksa asil eksik bu ozelligin surekli/rutin takibe entegre OLMAMASI mi?

2. SOMUTLASTIRMA: Onceki turda Aura'ya bir "imza tik/duruş" onermistin
   (somut, ayirt edici bir davranis kalibi). Bu tikin gercek bir sohbette
   TAM OLARAK nasil goründügüne dair 3 ornek diyalog yaz - soyut degil,
   birebir cümleler (kullanici cümlesi + Aura'nin cevabi).

3. ONCELIKLENDIRME: Tek gelistiricili, sinirli zamanli bir ekip. Onerdigin
   kisilik degisikliklerinden hangisi EN DUSUK EFOR + EN YUKSEK FARK
   YARATMA oranina sahip? Siralayarak yaz.

4. TEST EDILEBILIRLIK: Aura'nin onerdigin yeni kisiliginin gercekten
   "kendine ozgu" olup olmadigini nasil test ederiz? Bir kullaniciya iki
   farkli sohbet asistanindan gelen cevaplari gosterip "hangisi Aura" diye
   sorsak, hangi somut ozellik onu ele verir?

5. EVRIM: Aura'nin "sahte samimiyeti geciktirme" (familiarity threshold)
   mekanizmasi ilk gunlerde calisiyor. 30. gunde, 100. gunde bu mekanizma
   nasil evrilmeli ki iliski gercekten derinlesiyor hissi versin, duz bir
   cizgide kalmasin? Somut bir evrim onerisi ver.
"""

PROVIDERS_TO_ASK = {
    "OpenAI (GPT)": "openai",
    "Anthropic (Claude)": "anthropic",
    "Groq (acik model)": "groq",
    "Gemini": "gemini",
}

SYSTEM = (
    "You are a blunt, senior AI product/character strategist doing a "
    "detailed follow-up review. No flattery, no hedging, no generic "
    "advice - be maximally concrete and literal where asked. Respond in "
    "Turkish."
)


def main():
    print("=== Aura derin inceleme - 5 takip sorusu, 4 bagimsiz AI ===\n")
    for label, provider_key in PROVIDERS_TO_ASK.items():
        caller = PROVIDER_CALLERS[provider_key]
        try:
            answer = caller([{"role": "user", "content": CONTEXT}], SYSTEM)
        except MissingApiKeyError as e:
            answer = f"[ATLANDI - {e}]"
        except Exception as e:
            answer = f"[HATA - {type(e).__name__}: {e}]"
        print(f"--- {label} ---")
        print(answer)
        print()


if __name__ == "__main__":
    main()
