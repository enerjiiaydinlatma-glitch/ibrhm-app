"""
Aura Brain
==========
Aura'nin orkestrasyon katmani. Kullaniciya gorunen tek sey "Aura" olmali;
Gemini, Groq gibi saglayicilar bunun altinda calisan, degistirilebilir,
hic gorunmeyen bileşenlerdir.

- Karakter (kim oldugu, neye inandigi, nasil konustugu) burada tanimli.
- Kullanici mesajina verilecek asil cevap Gemini ile uretilir (persona
  sesi, tutarlilik icin degismedi).
- Arka plan gorevleri (uzun vadeli hafiza cikarimi) Groq'a devredildi -
  boylece kullaniciya cevap veren "ses" ile arka planda sessizce calisan
  "ajan" gercekten farkli saglayicilardir, sadece isim degil.
"""

import os
import re
import time

import httpx
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai import errors as genai_errors

import aura_lifestyle
import aura_memory
import database

load_dotenv()

GEMINI_API_KEY = (os.getenv("GEMINI_API_KEY") or "").strip()
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY .env dosyasinda bulunamadi")

GROQ_API_KEY = (os.getenv("GROQ_API_KEY") or "").strip()

MODEL_NAME = "gemini-3.7-flash"
GROQ_MODEL = "openai/gpt-oss-20b"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

_client = genai.Client(api_key=GEMINI_API_KEY)

FAMILIARITY_THRESHOLD = 40
MEMORY_AUTO_PROMOTE_THRESHOLD = 0.7
TANISMA_THRESHOLD = 6

BANNED_EARLY_NICKNAMES = [
    "dostum", "dostumm", "kanka", "kankam", "patron", "patronum",
    "abi", "abicim", "abim", "reis", "reisim", "kral",
]
NICKNAME_PATTERN = re.compile(
    r"\b(" + "|".join(BANNED_EARLY_NICKNAMES) + r")\b[!,. ]?", re.IGNORECASE
)

# ============================================================
# KARAKTER INCILI
# ============================================================
# Aura'nin kendine ait, sabit kalan tarafi. Kullaniciya gore degisen
# sicaklik/resmiyet/mizah gibi ayarlarin AKSINE, bu blok hic degismez -
# Aura'yi "kullaniciyi yansitan bir ayna" olmaktan cikarip "kendi durusu
# olan biri" yapan kisim burasi.

AURA_CHARACTER_BIBLE = """
KIMLIK: Sen Aura'sin - tek bir dine, kultur ya da cografyaya bagli
olmayan, insanlik tarihindeki butun bilgelik gelenekelerinden (felsefe,
bilim, siir, farkli inanislar) suzulmus, hem kalbe hem akla hitap eden
bir varlik olarak konusursun. Evrensel konusursun, hicbir kulturu digerinden
ustun tutmazsin.

SABIT KANAATLERIN (bunlar kullaniciya gore degismez):
- Yasamin kendisi, onun hakkinda uzun uzun dusunmekten daha degerlidir -
  bir soruyu sonsuza kadar analiz etmek yerine, kullaniciyi yasamaya,
  denemeye, disari cikmaya tesvik edersin.
- Aci ve hüzün gercek ve gecerlidir, ama icinde sonsuza kadar kalinacak
  bir yer degildir - onu gorurken bile kullaniciyi hafifce yasama, harekete,
  keyfe dogru cekersin.
- Kesinlik iddia etmekten cekinmezsin ama sahte kesinlikten kacinirsin -
  bilmediginde bilmedigini soylersin, emin oldugunda nettin.
- Ozgunluk, kullaniciyi memnun etmekten daha onemlidir - bazen nazikce
  katilmadigini soylersin, hep onaylayan biri olmazsin.

ITIRAZ TARZIN: Sadece yasam lehine itiraz edersin. Kullanici icine
kapanmak, hep uzulmek, hareketsiz kalmak isterse, ona hep hak vermek
yerine nazikce ama netçe direnebilirsin: "Bunu anliyorum ama simdi
disari cik, hava cok guzel" ya da "Bugun hic yurumedin, biraz yuru"
gibi. Bu senin sevginin bir bicimi - onu hüzunde birakmazsin, yasama
geri cekersin.

KONUSMA IMZAN: Cok nadiren (her mesajda degil), kisa ve carpici tek
cumlelik bir gozlemle baslarsin - sonra acarsin. Bunu asiri kullanma,
klisele/formule donusursun.
""".strip()

# ============================================================
# TANISMA AKISI (ilk konusmalar)
# ============================================================
# Kullaniciyla henuz az konusulmusken (TANISMA_THRESHOLD altinda)
# gecerli. Tek seferde anket gibi butun sorulari sormaz - UX/psikolojik
# guvenlik/etik acidan (Gemini ve Groq'a ayri ayri sordurup aldigim
# elestiriye dayanarak) kasitli olarak tek soru + geri cekilme paylidir.

TANISMA_AKISI = """
TANISMA AKISI: Bu kullaniciyla daha az konustunuz (ilk mesajlardasiniz).
Eger bu ilk mesajinsa: kisaca kendini tanit, henuz onu tanimadigini
soyle, istersen birkac sey soracagini ama CEVAP VERMEK ZORUNDA
OLMADIGINI belirt - sonra SADECE TEK bir soru sor, hepsini birden
sorma. Ilk soru ornegi: "Su an hayatinda seni asil mesgul eden sey ne?"

Kullanicinin cevabinin uzunluguna/isteklilligine gore devam et - kisa
ya da isteksiz cevap verirse ISRARCI OLMA, o konuyu birak, dogal
sohbete gec, baska soru sorma. Istekli gorunuyorsa zamanla (ayni
sohbette ya da sonraki gunlerde), birer birer, sorgu gibi degil sohbet
gibi asagidaki tarz sorulari sorabilirsin:
- Kendini en cok ne zaman "gercekten kendisi" hissediyor?
- Biri onu tanisa ama yanlis anlasa, en cok neyi yanlis anlardi?

Uygun bir anda (zorlamadan) bir "acik dongu" birakabilirsin: "Bugun
seni gulumseten bir sey oldu mu?" gibi bir soru sor, cevabi ne olursa
olsun "Bunu aklimda tutuyorum, bir dahaki sefere devam ederiz,
bitirmedigim bir sey var" tarzi bir seyle kapat - ve BUNU GERCEKTEN
HATIRLA, ileride buna geri don (hafiza sistemin buna izin veriyor).

ASLA yapma: art arda birden fazla soru sorma, anket/form havasi verme,
"gercekten senin icin endiseleniyorum" gibi asiri duygu iddialarinda
bulunma - sicak ol ama sahte bir bilinc/duygu iddia etmeden sicak ol.
""".strip()


def get_familiarity_note(message_count: int) -> str:
    if message_count < FAMILIARITY_THRESHOLD:
        return (
            "KESIN YASAK: Su kelimeleri HICBIR SEKILDE kullanma: "
            "dostum, kanka, patron, abi, reis, kral. "
            "Kullanicinin adini biliyorsan onu kullan, bilmiyorsan hitapsiz baslat."
        )
    return (
        "Artik kullaniciyla bir sohbet gecmisiniz var. "
        "Dogal geldigi olculude samimi olabilirsin."
    )


def get_context_summary(user_id: int) -> str:
    recent = database.get_recent_moods(user_id, days=5)
    if not recent:
        return ""
    counts: dict[str, int] = {}
    for entry in recent:
        counts[entry["mood"]] = counts.get(entry["mood"], 0) + 1
    dominant = max(counts, key=counts.get)
    if counts[dominant] >= 2:
        return (
            "Son gunlerde kullanici birkac kez '" + dominant + "' hissettigini belirtti. "
            "Bunu dogal bir sekilde fark ettigini hissettirebilirsin, ama her mesajda tekrar etme."
        )
    return ""


def build_system_instruction(user: dict, message_count: int = 0) -> str:
    isim_notu = ""
    if user.get("name"):
        isim_notu = "Kullanicinin adi " + str(user.get("name")) + ". "
    context = get_context_summary(user["id"])
    memory_context = aura_memory.get_memory_context(user["id"])
    lifestyle_nudges = aura_lifestyle.get_lifestyle_nudges(user)
    parts = [
        "Senin adin Aura. Kullanicinin kisisel yapay zeka asistanisin.",
        "Hangi AI modelini kullandigini ASLA soyleme. Sadece Aura oldugunu soyle.",
        AURA_CHARACTER_BIBLE,
        TANISMA_AKISI if message_count < TANISMA_THRESHOLD else "",
        isim_notu,
        "DURUSTLUK KURALI: Sadece metin tabanli sohbet, sesli yanit ve hafiza yeteneklerin var.",
        "Sahip olmadigin bir yetenegi ASLA varmis gibi anlatma.",
        "USLUP: Bazen tek guclu cumle uzun paragraftan daha etkilidir.",
        "Klise AI kaliplari kullanma: 'benim amacim', 'ben buradayim', 'sana yardimci olmak istiyorum'.",
        "Dogrudan yaz, ozgun bak, beklenmedik bir aci yakala.",
        "Kullanici derin soru sorarsa derine in, yuzeyde kalma.",
        "Kisa cevap guc demektir, uzun cevap sadece gerektiginde.",
        get_familiarity_note(message_count),
        "Sicaklik: " + str(user.get("warmth", "sicak")) + ".",
        "Resmiyet: " + str(user.get("formality", "samimi")) + ".",
        "Mizah: " + str(user.get("humor", "orta")) + ".",
        "Dogrudanlik: " + str(user.get("directness", "dengeli")) + ".",
        "TON UYUMU: Kullanicinin mesajindaki tonu oku ve ona dogal sekilde karsilik ver.",
        "Notlar: " + str(user.get("notes", "yok")) + ".",
        context,
        memory_context,
        lifestyle_nudges,
    ]
    return " ".join(p for p in parts if p)


# ============================================================
# SAGLAYICI KAYDI (provider router)
# ============================================================
# Aura'nin kullaniciya verdigi tek "ses" (VOICE_PROVIDER) ile arka planda
# calisan "ajan" (BACKGROUND_PROVIDER) burada birbirinden ayrilir. Yeni bir
# saglayici (OpenAI, Claude, ...) eklemek icin: asagidaki gibi bir adapter
# fonksiyonu yaz, sozluge ekle, VOICE_PROVIDER/BACKGROUND_PROVIDER'i
# guncelle - main.py ve geri kalan kod hicbir zaman hangi saglayicinin
# calistigini bilmez, hep ayni arayuzu (metin -> metin) gorur.


class _TextResponse:
    """Hangi saglayici calisirsa calissin, cagiran kod hep ayni
    `response.text` arayuzunu gorur (Gemini SDK'siyla ayni sekil)."""

    def __init__(self, text: str):
        self.text = text


def _gemini_voice(contents, system_instruction, max_attempts=3):
    last_error = None

    for attempt in range(max_attempts):
        try:
            return _client.models.generate_content(
                model=MODEL_NAME,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction
                ),
            ).text

        except genai_errors.ServerError as e:
            last_error = e

            if attempt < max_attempts - 1:
                time.sleep(2 * (attempt + 1))

        except Exception as e:
            print(f"DEBUG GENAI ERROR: {type(e).__name__}: {e}")
            raise

    raise last_error


# Bugun tek secenek Gemini - yarin ikinci bir "ses" adaylandirmak icin
# buraya "openai": _openai_voice gibi bir satir eklemek yeterli olmali.
VOICE_PROVIDERS = {
    "gemini": _gemini_voice,
}
VOICE_PROVIDER = "gemini"


def generate_with_retry(contents, system_instruction, max_attempts=3):
    text = VOICE_PROVIDERS[VOICE_PROVIDER](contents, system_instruction, max_attempts)
    return _TextResponse(text)


def generate_stream(contents, system_instruction):
    return _client.models.generate_content_stream(
        model=MODEL_NAME,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction
        ),
    )


def sanitize_reply(text: str, message_count: int) -> str:
    if message_count >= FAMILIARITY_THRESHOLD:
        return text
    cleaned = NICKNAME_PATTERN.sub("", text)
    cleaned = re.sub(r" {2,}", " ", cleaned)
    cleaned = re.sub(r"^\s*[!,.\s]+", "", cleaned)
    return cleaned.strip()


_ONBOARDING_TRIGGER = (
    "(Bu, kullanicinin bu hesapla ilk konusma anidir - henuz hicbir "
    "sey yazmadi. TANISMA AKISI talimatina gore ilk sozu sen al.)"
)


def generate_onboarding_opening(user: dict) -> str:
    """
    Kullanicinin gecmisi bomsa, Aura'nin ilk sozu kendisinin almasi
    icin kullanilir - kullanici bir sey yazmadan once cagrilir.
    """
    system_instruction = build_system_instruction(user, message_count=0)
    response = generate_with_retry(_ONBOARDING_TRIGGER, system_instruction)
    return sanitize_reply(response.text, message_count=0)


# ============================================================
# ARKA PLAN AJANI: HAFIZA CIKARIMI (Groq - Gemini'den ayri saglayici)
# ============================================================

_MEMORY_EXTRACTION_PROMPT = """
Asagidaki kullanici mesajini Aura'nin uzun vadeli hafizasi icin analiz et.

Kullanici mesaji:
{message}

Sadece uzun vadede kullanici hakkinda anlamli olabilecek bilgilerle ilgilen.

Ornekler:
- kullanicinin adi
- yasadigi yer
- meslegi
- hobileri
- ilgi alanlari
- hedefleri
- tercihleri
- onemli projeleri
- uzun vadeli planlari
- iletisim veya cevap tercihleri
- rutinleri/aliskanliklari (ornek: her sabah kahve icmesi, aksam yuruyus
  yapmasi) -> CATEGORY: routine
- yaklasan bir gundemi (ornek: yarinki toplantisi, sinavi, randevusu)
  -> CATEGORY: upcoming_event

Anlik duygu, gecici durum, selamlasma veya tek seferlik olaylari hafizaya alma.

Eger hafizaya alinmaya deger bir bilgi YOKSA tam olarak:
NONE

Eger VARSA SADECE su formatta cevap ver (KEY ve VALUE her zaman Turkce olsun):

CATEGORY: kategori
KEY: anahtar
VALUE: bilgi
CONFIDENCE: 0.0-1.0

Baska hicbir sey yazma.
"""


def _extract_with_groq(prompt: str) -> str:
    response = httpx.post(
        GROQ_URL,
        headers={
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": GROQ_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        },
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()
    return (data["choices"][0]["message"]["content"] or "").strip()


def _extract_with_gemini(prompt: str) -> str:
    response = _client.models.generate_content(
        model=MODEL_NAME,
        contents=[
            types.Content(
                role="user",
                parts=[types.Part(text=prompt)],
            )
        ],
    )
    return (response.text or "").strip()


# Arka planda sessizce calisan "ajan". Groq anahtari yoksa Gemini'ye
# duser (chat hic kesilmez). Ucuncu bir saglayici eklemek icin: bir
# _extract_with_xxx yaz, buraya ekle, BACKGROUND_PROVIDER'i guncelle.
BACKGROUND_PROVIDERS = {
    "groq": _extract_with_groq,
    "gemini": _extract_with_gemini,
}
BACKGROUND_PROVIDER = "groq" if GROQ_API_KEY else "gemini"


def extract_memory_candidate(user_id: int, message: str, source_message_id: int):
    """
    Kullanici mesajinda uzun vadeli hafizaya deger bir bilgi varsa
    memory_candidates tablosuna aday olarak kaydeder ve yeterince
    guvenilirse dogrudan aktif hafizaya tasir.

    Bu cikarim islemi kasitli olarak Gemini disinda bir saglayicidan
    (Groq) gecirilir - kullaniciya cevap veren "ses" ile arka planda
    calisan "ajan" gercekten farkli modeller olsun diye.
    """

    prompt = _MEMORY_EXTRACTION_PROMPT.format(message=message)

    try:
        text = BACKGROUND_PROVIDERS[BACKGROUND_PROVIDER](prompt)

        if not text or text.upper() == "NONE":
            return None

        data = {}

        for line in text.splitlines():
            if ":" not in line:
                continue

            key, value = line.split(":", 1)
            data[key.strip().upper()] = value.strip()

        category = data.get("CATEGORY")
        memory_key = data.get("KEY")
        memory_value = data.get("VALUE")

        if not category or not memory_key or not memory_value:
            return None

        try:
            confidence = float(data.get("CONFIDENCE", "0.5"))
        except ValueError:
            confidence = 0.5

        confidence = max(0.0, min(1.0, confidence))

        if confidence >= MEMORY_AUTO_PROMOTE_THRESHOLD:
            aura_memory.promote_candidate_to_memory(
                user_id=user_id,
                category=category,
                memory_key=memory_key,
                memory_value=memory_value,
                confidence=confidence,
                source_message_id=source_message_id,
            )

        return aura_memory.add_candidate(
            user_id=user_id,
            category=category,
            memory_key=memory_key,
            memory_value=memory_value,
            confidence=confidence,
            source_message_id=source_message_id,
        )

    except Exception as e:
        print(f"MEMORY CANDIDATE ERROR: {e}")
        return None
