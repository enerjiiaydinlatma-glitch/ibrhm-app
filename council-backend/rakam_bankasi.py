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
     "sayilar": ["60"], "onkosul": r"\b(?:all|whole|entire|every)\b", "tur": "kaynak", "kaynak": "NASA Sea Level Change",
     "url": "https://sealevel.nasa.gov/understanding-sea-level/global-sea-level/ice-melt"},
    {"id": "gronland", "konular": [30, 79],
     "olgu": "Greenland's ice alone holds about 7 meters of sea level.",
     "sayilar": ["7"], "onkosul": r"greenland", "tur": "kaynak", "kaynak": "Scientific American",
     "url": "https://www.scientificamerican.com/article/how-much-will-global-warming-raise-sea-levels"},
    {"id": "buz_ceyrek", "konular": [79],
     "olgu": "A quarter of that ice would raise the sea roughly 15 meters (60 meters divided by four).",
     "sayilar": ["15"], "onkosul": r"\bquarter\b", "tur": "turetilmis", "kaynak": "NASA figure, our own arithmetic",
     "url": "https://sealevel.nasa.gov/understanding-sea-level/global-sea-level/ice-melt"},
    {"id": "deniz_1880", "konular": [29, 30, 31, 32, 33, 79],
     "olgu": "Sea level has already risen about 8 to 9 inches (roughly 20 to 23 centimeters) since 1880.",
     "sayilar": ["8", "9", "20", "23", "1880"], "onkosul": r"\b(?:since|already|so far)\b", "tur": "kaynak", "kaynak": "NASA Earthdata climate indicators",
     "url": "https://www.earthdata.nasa.gov/topics/climate-indicators"},
    {"id": "sel_15cm", "konular": [81],
     "olgu": "Just 6 inches (about 15 centimeters) of fast-moving water can knock an adult off their feet.",
     "sayilar": ["6", "15"], "onkosul": r"\b(?:moving|flowing|rushing|fast)\b", "tur": "kaynak", "kaynak": "US National Weather Service flood safety brochure",
     "url": "https://www.weather.gov/media/safety/flood_brochure12A.pdf"},
    {"id": "sel_30cm", "konular": [81],
     "olgu": "12 inches (about 30 centimeters) of flowing water can carry away a small car.",
     "sayilar": ["12", "30"], "onkosul": r"\b(?:moving|flowing|rushing|fast)\b", "tur": "kaynak", "kaynak": "US National Weather Service flood safety brochure",
     "url": "https://www.weather.gov/media/safety/flood_brochure12A.pdf"},
    {"id": "sel_60cm", "konular": [81],
     "olgu": "18 to 24 inches (about 45 to 60 centimeters) of flowing water can carry away trucks, vans and SUVs.",
     "sayilar": ["18", "24", "45", "60"], "onkosul": r"\b(?:moving|flowing|rushing|fast)\b", "tur": "kaynak", "kaynak": "US National Weather Service flood safety brochure",
     "url": "https://www.weather.gov/media/safety/flood_brochure12A.pdf"},
    {"id": "robot_18000", "konular": [76, 84],
     "olgu": "About 18,000 humanoid robots shipped worldwide in 2025, by one research firm's estimate; other estimates range from 13,000 to 20,000.",
     "sayilar": ["18000", "13000", "20000", "2025"], "onkosul": r"\b(?:estimate|estimated|estimates|about|roughly)\b", "tur": "kaynak", "kaynak": "IDC estimate (reported by Jiemian)",
     "url": "https://en.jiemian.com/article/13925066.html"},
    {"id": "magara_sac_actun", "konular": [85, 90],
     "olgu": "In 2018, divers linked two flooded cave systems in Mexico into one: more than 340 kilometers of underwater passages.",
     "sayilar": ["2018", "340"], "onkosul": r"\b(?:cave|caves|flooded|underwater)\b", "tur": "kaynak", "kaynak": "Earth Magazine (cave link, 2018)",
     "url": "https://www.earthmagazine.org/article/worlds-longest-underwater-cave-found-mexico/"},
    {"id": "vostok_4000", "konular": [86],
     "olgu": "Lake Vostok in Antarctica lies about 4,000 meters beneath the ice.",
     "sayilar": ["4000"], "onkosul": r"\b(?:antarctic\w*|beneath|under|below|buried)\b", "tur": "kaynak", "kaynak": "Lake Vostok (encyclopedia summary of survey data)",
     "url": "https://en.wikipedia.org/wiki/Lake_Vostok"},
    {"id": "robotaksi_500000", "konular": [23],
     "olgu": "As of March 2026, one robotaxi operator reported about 500,000 paid driverless rides a week in US cities.",
     "sayilar": ["500000", "2026"], "onkosul": r"\b(?:about|roughly|around|reported|as of)\b", "tur": "kaynak", "kaynak": "Industry press report of a robotaxi operator's weekly rides (secondary source)",
     "url": "https://www.automotiveworld.com/news/waymos-metric-for-2026-success-one-million-weekly-rides/"},
    {"id": "wef_2030_isler", "konular": [25, 27],
     "olgu": "By 2030, employers expect 170 million new jobs and 92 million jobs displaced worldwide, a net gain of 78 million (a survey of employers).",
     "sayilar": ["2030", "170", "92", "78"], "onkosul": r"\b(?:employers|survey|expect\w*)\b", "tur": "kaynak", "kaynak": "World Economic Forum, Future of Jobs Report 2025 (employer survey)",
     "url": "https://weforum.org/press/2025/01/future-of-jobs-report-2025-78-million-new-job-opportunities-by-2030-but-urgent-upskilling-needed-to-prepare-workforces/"},
    {"id": "wef_2030_22", "konular": [25, 27],
     "olgu": "Employers expect job disruption to affect 22% of jobs by 2030.",
     "sayilar": ["22", "2030"], "onkosul": r"\b(?:employers|survey|expect\w*)\b", "tur": "kaynak", "kaynak": "World Economic Forum, Future of Jobs Report 2025 (employer survey)",
     "url": "https://weforum.org/press/2025/01/future-of-jobs-report-2025-78-million-new-job-opportunities-by-2030-but-urgent-upskilling-needed-to-prepare-workforces/"},
    {"id": "unesco_ogretmen_44", "konular": [21],
     "olgu": "UNESCO estimates the world needs about 44 million more teachers by 2030 to give every child primary and secondary school.",
     "sayilar": ["44", "2030"], "onkosul": r"\b(?:estimate\w*|about|roughly)\b", "tur": "kaynak", "kaynak": "UN News (UNESCO teacher shortage estimate)",
     "url": "https://news.un.org/en/story/2024/02/1147067"},
    {"id": "isinlanma_143", "konular": [65, 66],
     "olgu": "In 2012, scientists teleported the quantum state of a light particle across 143 kilometers. No object or person has been teleported.",
     "sayilar": ["2012", "143"], "onkosul": r"\b(?:particle|photon|quantum|light)\b", "tur": "kaynak", "kaynak": "Max Planck Institute of Quantum Optics",
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
    out += sayim_iddialari(metin)
    return sorted(set(out))


# '3 major cities will flood' gibi YER/GRUP sayimi kaynaksiz iddiadir (10'dan kucuk olsa da).
_SAYIM_IDDIA = re.compile(r"\b\d+\s+(?:major\s+|big\s+|biggest\s+|large\s+)?(?:cities|countries|nations|states|continents|people|families|islands)\b", re.I)


def sayim_iddialari(metin):
    return sorted({m.group(0).lower() for m in _SAYIM_IDDIA.finditer(metin or "")})


def _sayi_var(n, metin):
    return re.search(rf"(?<![\d.]){re.escape(n)}(?![\d])", metin or "") is not None


def olgu_rakami_var(metin, topic):
    """Metinde konuya ait bir olgunun rakami geciyor mu?"""
    return any(_sayi_var(n, metin) for o in olgular(topic) for n in o["sayilar"])


def onkosul_eksik(metin, topic):
    """Metinde rakami gecen bir olgunun onkosulu (ornegin 'a quarter', 'all', 'since') metinde yoksa o olgularin id'leri.
    Dogru rakamin yanlis varsayimla kullanilmasini engeller (15 m = buzun DORTTE BIRI; 'buz erirse 15 m' denemez)."""
    out = []
    premis = {_norm(m.group(0)) for m in _SAYI.finditer(topic or "")}     # konunun kendi varsayim rakami (ornegin '20 centimeters') kosul istemez
    for o in olgular(topic):
        if o.get("onkosul") and any(_sayi_var(n, metin) for n in o["sayilar"] if n not in premis) and not re.search(o["onkosul"], metin or "", re.I):
            out.append(o["id"])
    return out


def rakam_kaynakli(hit, topic):
    """claim_lint RAKAM isabeti ('170 million', '22%') konunun bir olgusunda AYNEN (bosluk/buyuk-kucuk harf farksiz) geciyorsa True.
    Yalniz bu durumda Konsey kapisi RAKAM engelini kaldirir; bankada olmayan hicbir milyon/yuzde rakami gecmez."""
    h = re.sub(r"\s+", " ", (hit or "").strip().lower())
    h2 = re.sub(r"\s+%", "%", h)
    for o in olgular(topic):
        t = re.sub(r"\s+", " ", o["olgu"].lower())
        if h and (h in t or h2 in t):
            return True
    return False


def prompt_bolumu(topic):
    """Senaryo promptuna eklenecek metin; olgu yoksa 'rakam kullanma'."""
    ol = olgular(topic)
    if not ol:
        return ("\n\nNUMBERS: this topic has no verified facts. Use NO numbers of 10 or more, no measurements, no years, no spelled-out "
                "large numbers (twenty, hundred, thousand). Small counts ('three fees') are fine.")
    satir = "\n".join(f"- {o['olgu']}" + (" [our own arithmetic: say 'roughly']" if o["tur"] == "turetilmis" else "") for o in ol)
    return ("\n\nVERIFIED FACTS (the ONLY numbers, measurements and years you may use; copy each number exactly, never round or invent another). "
            "Use a fact ONLY when it is directly about the topic's subject, ideally in the hook; NEVER force a number into the closing line or into filler. "
            "If no fact fits naturally, use no numbers at all:\n" + satir +
            "\nThe topic's own what-if numbers (for example '20 centimeters') are the premise and may be repeated. "
            "State facts plainly; never add any other figure, percentage or date. Whenever you use a fact's number, the same script must also say "
            "the condition it depends on (for example 'a quarter of the ice', 'all the ice', 'since 1880', 'a light particle'). "
            "The HOOK must state the topic's premise. Never count or name specific cities, countries or groups. "
            "TITLE (max 40 chars): a plain statement with the verified number when you used one, e.g. 'A quarter of ice means 15 m of sea' (no colon).")


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
