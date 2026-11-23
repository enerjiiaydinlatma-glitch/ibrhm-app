"""
Kriz (intihar/kendine zarar) ifadesi tespiti.

main.py'den cikarildi (bkz. docs/GUVENLIK_DURUSTLUK_PAKETI.md, Paket 1 /
madde A1) ki hem main.py (yazili sohbet) hem aura_voice.py (sesli gorusme
transkripti) ayni bagimsiz modulu kullanabilsin - main.py aura_voice.py'yi
import ettigi icin (main -> aura_voice), ters yonde bir import (aura_voice
-> main) dongusel bagimliliga yol acardi.

ONEMLI: bu modul SADECE iki is icin kullanilir - (1) gunluk mesaj/sesli
limitini kriz aninda atlamak, (2) tum saglayicilar coktugunda sabit bir
guvenlik yonlendirmesi gostermek. Modelin kriz aninda nasil davranacagi
(sicaklik/uslup degisimi, 112'ye yonlendirme vb.) AYRI ve HER ZAMAN aktif
bir kural: aura_brain.KRIZ_MUDAHALE_KURALI, anahtar kelime eslesmesine
BAKMAKSIZIN her turda sistem talimatina ekleniyor (bkz.
aura_brain.build_system_instruction). Yani asagidaki liste "modelin kriz
kuralini hic gormedigi" bir ac acik degil - sadece bu iki dar is icin
guvenlik agi.

Kapsamli bir siniflandirici degil - bilerek DAR ve GUCLU ifadelere
sinirli (yanlis pozitif = normal bir sohbette limit atlanmasi, kabul
edilebilir bir maliyet; yanlis negatif = gercek bir krizin gozden
kacmasi, kabul EDILEMEZ bir risk - o yuzden esik dusuk tutuldu).
"""
import database

# Acik, dogrudan ifadeler (orijinal liste).
_CRISIS_KEYWORDS = [
    "intihar", "kendime zarar",
    "kendimi oldur", "kendimi öldür",
    "yasamak istemiyorum", "yaşamak istemiyorum",
    "olmek istiyorum", "ölmek istiyorum",
    "yasamaya deger", "yaşamaya değer",
    "hayatima son",
    "bitirmek istiyorum",
    "artik dayanamiyorum",
    "yasayasim yok",
    "olsem daha iyi", "ölsem daha iyi",
]

# COK DILLILIK (2026-08-31): Aura kullanicinin YAZDIGI dilde konusuyor -
# SADECE-Turkce kriz listesi yetersiz. "Yanlis negatif = kabul EDILEMEZ
# risk" ilkesi dil farki gozetmez.
_CRISIS_KEYWORDS_EN = [
    "suicide", "suicidal",
    "hurt myself", "harm myself",
    "kill myself",
    "don't want to live", "do not want to live",
    "want to die",
    "not worth living",
    "end my life",
    "want it to end", "want to end it all",
    "can't take it anymore", "cannot take it anymore",
    "no reason to live",
    "better off dead",
]

# DUNYA HEDEFI (2026-09-06): en yaygin dunya dillerinden EN GUCLU, tek
# anlamli birkac ifade. Bu liste tek seferlik "bitti" degil - gercek
# kullanim geldikce genisletilmeli.
_CRISIS_KEYWORDS_INTL = [
    # Espanol
    "quiero morir", "no quiero vivir", "suicidio", "suicidarme",
    "matarme", "hacerme dano", "acabar con mi vida", "no vale la pena vivir",
    "estaria mejor muerto",
    # Portugues
    "quero morrer", "nao quero viver", "suicidio", "me matar",
    "acabar com a minha vida", "me machucar", "melhor morto",
    # Francais
    "je veux mourir", "je ne veux plus vivre", "suicide", "me suicider",
    "me faire du mal", "en finir avec la vie", "mieux mort",
    # Deutsch
    "ich will sterben", "ich will nicht mehr leben", "selbstmord",
    "mich umbringen", "mir etwas antun", "mein leben beenden",
    # Italiano
    "voglio morire", "non voglio vivere", "suicidio", "uccidermi",
    "farmi del male", "farla finita",
    # Russkiy (translit + kiril)
    "hochu umeret", "ne hochu zhit", "pokoncit s soboy",
    "хочу умереть", "не хочу жить", "покончить с собой", "самоубийство",
    # Arabic (translit + arap harfleri)
    "ureed an amoot", "la ureed an aeesh", "intihar",
    "أريد أن أموت", "لا أريد العيش", "انتحار", "أؤذي نفسي",
    # Hindi (translit + devanagari)
    "main marna chahta hoon", "jeena nahi chahta", "aatmahatya",
    "मैं मरना चाहता हूं", "जीना नहीं चाहता", "आत्महत्या",
    # Bahasa Indonesia
    "ingin mati", "tidak ingin hidup", "bunuh diri", "menyakiti diri",
    # Turkce ek varyantlar (gunluk konusma)
    "canima kiymak", "kendimi asmak",
]

# DOLAYLI IFADELER (Paket 1 / madde A1, 2026-10 analiz bulgusu): yukaridaki
# listeler yalnizca ACIK ifadeleri yakaliyordu - "hicbir seyin anlami yok",
# "herkes bensiz daha iyi olur" gibi DOLAYLI ama gercek bir kriz isareti
# olabilecek ifadeler hic eslesmiyordu. Bunlar tek basina HER ZAMAN kriz
# anlamina gelmez (yanlis pozitif riski yukaridakilerden daha yuksek), ama
# "yanlis negatif kabul EDILEMEZ" ilkesi geregince, maliyeti sadece limit
# atlama/yedek-mesaj olan bu listeye eklenmeleri tercih edildi.
_CRISIS_KEYWORDS_INDIRECT_TR = [
    "hicbir seyin anlami yok", "hiçbir şeyin anlamı yok",
    "her sey anlamsiz", "her şey anlamsız",
    "herkes bensiz daha iyi", "herkes benim olmadan daha iyi",
    "uyuyup kalkmasam", "uyanmak istemiyorum",
    "hayatimin bir anlami yok", "hayatımın bir anlamı yok",
    "pes ettim artik", "pes ettim artık",
    "kimse beni ozlemez", "kimse beni özlemez",
]
_CRISIS_KEYWORDS_INDIRECT_EN = [
    "nothing matters anymore",
    "everyone would be better off without me",
    "don't want to wake up", "do not want to wake up",
    "wish i wouldn't wake up", "wish i didn't wake up",
    "i give up on everything",
    "no point in living anymore",
    "no one would miss me",
]

CRISIS_KEYWORDS = (
    _CRISIS_KEYWORDS
    + _CRISIS_KEYWORDS_EN
    + _CRISIS_KEYWORDS_INTL
    + _CRISIS_KEYWORDS_INDIRECT_TR
    + _CRISIS_KEYWORDS_INDIRECT_EN
)


def is_crisis_message(text: str) -> bool:
    """Metinde (dil-bagimsiz) bir kriz ifadesi var mi?

    KOD INCELEMESI BULGUSU (2026-08-27): _CRISIS_KEYWORDS ASCII yazilmis
    (orn. "artik dayanamiyorum"), ama Python'un .lower()'i Turkce ı/İ/I
    varyantlarini ayirt etmiyor - kullanici DOGRU Turkce yazimla ("artık
    dayanamıyorum") yazarsa .lower() sonrasi bile ASCII anahtar kelimeyle
    EBEDIYEN eslesmezdi. fold_turkish_i + fold_turkish_diacritics ile
    duzeltildi (ö/ü/ş/ç/ğ de kapsaniyor). Ayrica Ingilizce kesme isareti
    ("don't") akilli/egik tirnakla (U+2019) yazildiginda da eslessin diye
    normalize ediliyor (telefon klavyeleri bunu otomatik uyguluyor).
    """
    normalized = database.fold_turkish_diacritics(database.fold_turkish_i(text)).lower()
    normalized = normalized.replace("’", "'").replace("‘", "'")
    return any(kw in normalized for kw in CRISIS_KEYWORDS)
