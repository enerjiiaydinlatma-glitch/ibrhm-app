"""
Sign Council'in gorsel "studyosu" icin 4 farkli LLM saglayicisina AYRI AYRI
somut bir tasarim konsepti sorar - gercek 2026 yayincilik/esports trend
arastirmasi (WebSearch, bkz. sohbet gecmisi) ve gercek teknik kisitlarla
gruvdlanmis.

Kullanim:
    python ask_studio_design.py
"""
import sys

sys.stdout.reconfigure(errors="replace")

from providers import PROVIDER_CALLERS, MissingApiKeyError

BRIEF = """
Sign Council: 5 AI ajaninin (Aura=lider/moderator, Alpha=analitik,
Beta=asi/gercekci, Gamma=etik, Delta=sentez) gercek guncel haberler
uzerine tartistigi bir YouTube programi. Marka kimligi: koyu palet
(#12151b arka plan, #5fd4c4 vurgu rengi), her ajan kendi geometrik
sekliyle temsil ediliyor (daire/ucgen/diken/yumusak-kose/altigen) -
BILINCLI olarak insan/hayvan maskot KARAKTERI degil, cunku ton/marka/
hukuki nedenlerle o yoldan kacinildi (bu karar kesin, degismiyor).

TEKNIK KISIT (onemli, hayalgucunu bu sinirlar icinde kullan): gercek
zamanli 3D/XR motoru YOK. Uretim, Python/PIL ile statik/yari-statik
sahne CIZIMI + ffmpeg ile hafif kamera hareketi (yavas zoom, hafif
parlaklik nabzi) seklinde. Yani "gercek stüdyo" degil, GUCLU BIR
ILLUZYON yaratacak 2D/katmanli kompozisyon olmali.

Gercek 2026 yayincilik arastirmasindan (dogrulandi):
- Trend "saf sanal" degil "hibrit" - tamamen duz/soyut sahneler
  inandiriciligini kaybediyor, fiziksel hissi olan referans noktalari
  (kaide, basamak, masa gibi) sahneyi "gercek" gibi gosteriyor
- Esports sahnelerinde: cok-yuzlu asili LED ekran/kup, amfitiyatro
  tarzi sirali oturma (olcek/buyukluk hissi verir), neon/cyber vurgular,
  takip edilen isik/golge tutarliligi

Su an elimizde bir ilk mockup var: karanlik bir "meclis salonu" -
yukselen sutun sildueleri, ust spot isigi, holografik zemin izgarasi,
merkeze aydinlatilmis konusan ajan. Begenildi ama "daha etkileyici,
daha buyuk mekan hissi (stadyum/plaza/kompleks)" isteniyor.

Soru (Turkce, somut, en fazla 200 kelime, jenerik "harika olur" gibi
laflar degil, DOGRUDAN uygulanabilir bir sahne tarifi):

1. Bu kisitlar icinde (2D PIL cizimi + hafif ffmpeg hareketi, insan/
   maskot yok, koyu+teal marka paleti), en etkileyici "ilk gorunum"
   sahnesi ne olurdu? Somut olarak tarif et: kompozisyon, isik, olcek
   ipuclari, ne cizilecek.
2. Esports'taki "asili LED kup" ve "amfitiyatro oturma" fikirlerinden
   hangisi bize (5 ajanli tartisma formatina) uyarlanabilir, nasil?
3. Tek cumlede: bu sahneye bir isim ver (marka icin akilda kalici).
"""

PROVIDERS_TO_ASK = {
    "OpenAI (GPT)": "openai",
    "Anthropic (Claude)": "anthropic",
    "Groq (acik model)": "groq",
    "Gemini": "gemini",
}

SYSTEM = (
    "You are a senior broadcast set/motion designer who also codes. "
    "Give a concrete, technically grounded scene description that "
    "could actually be built with 2D compositing + light camera "
    "movement - not abstract inspiration talk. Respond in Turkish."
)


def main():
    print("=== Sign Council studyo konsepti - 4 bagimsiz AI onerisi ===\n")
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
