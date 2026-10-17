"""KAYNAKLI RAKAM BANKASI - Konsey senaryolarinda yalniz burada kaynagi olan rakamlar kullanilabilir.

Neden: iddialı/rakamli video merak uyandirir ama modelin uydurdugu rakam hem yaniltir hem kanali riske atar. Bu yuzden:
- Senaryo promptuna konuya uyan olgular (cumle + kaynak) verilir; model YALNIZ bunlardaki rakamlari kullanabilir.
- konsey_format.kontrol: metinde bankada olmayan (ve konunun kendi sorusunda gecmeyen) buyuk rakam/birimli rakam/yil -> RAKAM_KAYNAK, senaryo reddedilir.
- Videoda kullanilan olgularin kaynaklari aciklamaya 'Sources:' satiri olarak eklenir.
Her olgu bir 'tur' tasir: 'kaynak' (kaynakta aynen yazar) | 'turetilmis' (kaynaktaki rakamdan kendi aritmetigimiz; videoda 'roughly' denir).
Yeni olgu eklerken: rakami ve URL'yi gercek bir kaynaktan dogrula; emin degilsen EKLEME. Bilinmeyeni 'yaklasik' diye yazma.
Konu degerlendirme: konu = konsey_konular id'si.
"""
import re

import konsey_konular

OLGULAR = [
    {"id": "buz_toplam", "konular": [30, 79, 80],
     "olgu": "If all the ice on land melted, the sea would rise by about 60 meters.",
     "sayilar": ["60"], "tur": "kaynak", "kaynak": "NASA Sea Level Change",
     "url": "https://sealevel.nasa.gov/understanding-sea-level/global-sea-level/ice-melt"},
    {"id": "gronland", "konular": [30, 79],
     "olgu": "Greenland's ice alone holds about 7 meters of sea level.",
     "sayilar": ["7"], "tur": "kaynak", "kaynak": "Scientific American",
     "url": "https://www.scientificamerican.com/article/how-much-will-global-warming-raise-sea-levels"},
    {"id": "buz_ceyrek", "konular": [79],
     "olgu": "A quarter of that ice would raise the sea roughly 15 meters (60 meters divided by four).",
     "sayilar": ["15"], "tur": "turetilmis", "kaynak": "NASA figure, our own arithmetic",
     "url": "https://sealevel.nasa.gov/understanding-sea-level/global-sea-level/ice-melt"},
    {"id": "deniz_1880", "konular": [29, 30, 31, 32, 33, 79],
     "olgu": "Sea level has already risen about 8 to 9 inches (roughly 20 to 23 centimeters) since 1880.",
     "sayilar": ["8", "9", "20", "23", "1880"], "tur": "kaynak", "kaynak": "NASA Earthdata climate indicators",
     "url": "https://www.earthdata.nasa.gov/topics/climate-indicators"},
    {"id": "isinlanma_143", "konular": [65, 66],
     "olgu": "In 2012, scientists teleported the quantum state of a light particle across 143 kilometers. No object or person has been teleported.",
     "sayilar": ["2012", "143"], "tur": "kaynak", "kaynak": "Max Planck Institute of Quantum Optics",
     "url": "https://www.mpq.mpg.de/4860079/12_09_06"},
    {"id": "kara_delik_2019", "konular": [69, 70],
     "olgu": "The first photo of a black hole was released in 2019.",
     "sayilar": ["2019"], "tur": "kaynak", "kaynak": "Astronomy magazine",
     "url": "https://www.astronomy.com/science/event-horizon-telescope-releases-first-ever-black-hole-image/"},
    {"id": "crispr_2023", "konular": [72, 73],
     "olgu": "In 2023, the first CRISPR gene-editing therapy was approved. Nothing like it exists for height or looks.",
     "sayilar": ["2023"], "tur": "kaynak", "kaynak": "STAT News",
     "url": "https://www.statnews.com/2023/12/08/fda-approves-casgevy-crispr-based-medicine-for-treatment-of-sickle-cell-disease/"},
]

# '10 ve ustu' sayilar, birimli sayilar ve yazi ile yazilmis onluk/yuzluk sayilar kaynak ister; '3 fees' gibi kucuk sayimlar serbest.
_SAYI = re.compile(r"\d[\d,]*(?:\.\d+)?")
_BIRIM = re.compile(r"^\s*(?:-|\s)?(?:m|km|cm|mm|meters?|metres?|kilomet\w+|centimet\w+|feet|foot|ft|inch(?:es)?|miles?|degrees?|years?|days?|months?|hours?|%)\b", re.I)
_YAZILI = re.compile(r"\b(?:twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|dozens)\b", re.I)


def konu_id(topic):
    t = (topic or "").strip().lower()
    return next((k["id"] for k in konsey_konular.KONULAR if k["konu"].lower() == t), None)


def olgular(topic):
    """Konuya uyan olgular (liste); konu havuzda yoksa bos."""
    i = konu_id(topic)
    return [o for o in OLGULAR if i in o["konular"]] if i is not None else []


def _norm(s):
    return s.replace(",", "").rstrip(".")


def izinli_sayilar(topic):
    """Konunun kendi sorusundaki rakamlar (varsayim) + konuya ait olgulardaki rakamlar."""
    izin = {_norm(m.group(0)) for m in _SAYI.finditer(topic or "")}
    for o in olgular(topic):
        izin |= set(o["sayilar"])
    return izin


def yasakli_rakamlar(metin, topic):
    """Metindeki kaynaksiz 'buyuk' rakamlar/yazili sayilar. Bos liste = temiz."""
    izin = izinli_sayilar(topic)
    konu_kelime = {w.lower() for w in _YAZILI.findall(topic or "")}
    out = []
    for m in _SAYI.finditer(metin or ""):
        s = _norm(m.group(0))
        try:
            buyuk = float(s) >= 10
        except ValueError:
            buyuk = False
        if (buyuk or _BIRIM.match(metin[m.end():])) and s not in izin:
            out.append(s)
    for w in _YAZILI.findall(metin or ""):
        if w.lower() not in konu_kelime:
            out.append(w.lower())
    return sorted(set(out))


def prompt_bolumu(topic):
    """Senaryo promptuna eklenecek metin; olgu yoksa 'rakam kullanma'."""
    ol = olgular(topic)
    if not ol:
        return ("\n\nNUMBERS: this topic has no verified facts. Use NO numbers of 10 or more, no measurements, no years, no spelled-out "
                "large numbers (twenty, hundred, thousand). Small counts ('three fees') are fine.")
    satir = "\n".join(f"- {o['olgu']}" + (" [our own arithmetic: say 'roughly']" if o["tur"] == "turetilmis" else "") for o in ol)
    return ("\n\nVERIFIED FACTS (the ONLY numbers, measurements and years you may use; use at least one in the script, ideally in the "
            "hook or the closing line; copy each number exactly, never round or invent another):\n" + satir +
            "\nThe topic's own what-if numbers (for example '20 centimeters') are the premise and may be repeated. "
            "State facts plainly; never add any other figure, percentage or date.")


def kaynak_satiri(topic, metin):
    """Metinde rakami gecen olgularin kaynaklari: 'Sources: ...' (yoksa bos). Aciklamaya eklenir."""
    kul = []
    for o in olgular(topic):
        if any(re.search(rf"(?<![\d.]){re.escape(n)}(?![\d])", metin or "") for n in o["sayilar"]):
            kul.append(o)
    if not kul:
        return ""
    parcalar = []
    for o in kul:
        etiket = o["kaynak"] + (" (rough arithmetic)" if o["tur"] == "turetilmis" else "")
        parcalar.append(f"{etiket}: {o['url']}")
    return "Sources: " + " | ".join(parcalar)
