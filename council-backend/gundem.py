"""
Gundem tespit motoru (Sign Council Rundown, Segment 04).

Bu SADECE meta veri (baslik, konu, hacim) topluyor - baska hic kimsenin
videosunu/icerigini indirmiyor, kopyalamiyor, "calmiyoruz". Iki kaynak,
ikisi de resmi/yasal:
  1) YouTube Data API - "Science & Technology" kategorisinde su anki
     trend videolarin BASLIKLARI (kendi OAuth yetkimizle, resmi endpoint)
  2) GDELT Doc API - acik, ucretsiz, kimlik gerektirmeyen resmi bir haber
     indeksi - "artificial intelligence" gecen son haberlerin basliklari

Cikti, insan onayina sunulacak bir "konu brifi" - hicbir sey otomatik
yayina gitmiyor (Segment 04: "Insan onayi" adimi hala zorunlu).

Kullanim:
    python gundem.py
"""
import re
import sys
import time
from collections import Counter

import httpx

# Windows konsolu (cp1254 vb.) her Unicode karakteri yazdiramiyor - bir
# baslikta emoji/ozel karakter varsa print() cokuyordu. Cikan karakterleri
# sessizce degistirerek devam et.
sys.stdout.reconfigure(errors="replace")

from googleapiclient.discovery import build
from youtube_auth import get_credentials

STOPWORDS = {
    "the", "a", "an", "of", "to", "in", "on", "for", "and", "is", "are",
    "with", "at", "by", "from", "this", "that", "it", "as", "be", "will",
    "how", "what", "why", "new", "says", "after", "over", "into", "its",
    "ai", "video", "youtube",
    # ilk testte tek bir cok-izlenen videonun sıradan kelimeleri
    "many", "could", "have", "has", "had", "would", "should", "you",
    "your", "get", "got", "just", "now", "out", "up", "down", "arrived",
    "not", "but", "than", "then", "when", "were", "was", "can", "does",
    "did", "yet", "still", "here", "there", "our", "their", "his", "her",
}


def fetch_youtube_trending(region="US", category_id="28", max_results=15):
    """'Science & Technology' kategorisinde su anki resmi trend listesi."""
    creds = get_credentials()
    youtube = build("youtube", "v3", credentials=creds)
    resp = youtube.videos().list(
        part="snippet,statistics",
        chart="mostPopular",
        regionCode=region,
        videoCategoryId=category_id,
        maxResults=max_results,
    ).execute()
    return [
        {
            "title": it["snippet"]["title"],
            "views": int(it["statistics"].get("viewCount", 0)),
            "source": "youtube_trending",
        }
        for it in resp.get("items", [])
    ]


def fetch_gdelt_ai_news(query="artificial intelligence", max_records=25):
    """GDELT Doc API - acik/ucretsiz, kimlik gerektirmiyor. Son 24 saatin
    'artificial intelligence' gecen haber basliklari."""
    url = "https://api.gdeltproject.org/api/v2/doc/doc"
    params = {
        "query": query,
        "mode": "ArtList",
        "maxrecords": str(max_records),
        "format": "json",
        "sort": "DateDesc",
        "timespan": "24h",
    }
    # GDELT'in ucretsiz servisi zaman zaman 429 (hiz siniri) veriyor -
    # bir kere kisa bir bekleyisle tekrar deniyoruz, hala olmazsa cagiran
    # taraf (main) zaten bunu nazikce atliyor.
    for attempt in range(2):
        r = httpx.get(url, params=params, timeout=20)
        if r.status_code == 429 and attempt == 0:
            time.sleep(3)
            continue
        r.raise_for_status()
        break
    data = r.json()
    return [
        {"title": a["title"], "views": 0, "source": "gdelt_news"}
        for a in data.get("articles", [])
    ]


def _strip_hashtags(title):
    """Baslik sonuna eklenmis '#tag #tag2' turu hashtag spami, gercek
    konuyu anlatmaz (bkz. ilk test: '#carterpcs #tech #gaming #pcgaming'
    gercek bir 'gundem konusu' degildi, sadece video etiketiydi)."""
    return re.sub(r"#\w+", " ", title)


def score_topics(items, top_n=8):
    """Basliklardaki anlamli kelimeleri, hem kac farkli baslikta gectigine
    HEM de o basligin izlenme sayisina gore agirlikli puanlar - cok
    izlenen bir videoda gecen kelime, az izlenen 3 videoda gecen kelimeden
    daha fazla agirlik tasir. Hashtag'ler puanlamaya hic girmiyor.

    ONEMLI: bu fonksiyonu YouTube (yuksek izlenme) ve GDELT (izlenme=0)
    gibi cok farkli olcekli kaynaklari TEK listede karistirarak cagirma -
    ilk testte tek bir yuksek-izlenmeli oyun/donanim videosu, alakasiz
    kelimeleriyle (store/gaming/exabyte) gercek AI haber sinyalini (GDELT)
    tamamen bogdu. Kaynaklari ayri ayri skorla, ayri listeler olarak sun."""
    scores = Counter()
    examples = {}
    for item in items:
        clean_title = _strip_hashtags(item["title"])
        words = re.findall(r"[a-zA-Z][a-zA-Z\-']{3,}", clean_title.lower())
        weight = 1 + min(item.get("views", 0) / 500_000, 10)
        seen_in_title = set()
        for w in words:
            if w in STOPWORDS or w in seen_in_title:
                continue
            seen_in_title.add(w)
            scores[w] += weight
            examples.setdefault(w, item["title"])
    return scores.most_common(top_n), examples


def main():
    print("YouTube trend (Science & Technology) cekiliyor...")
    try:
        yt_items = fetch_youtube_trending()
    except Exception as e:
        print(f"  UYARI: YouTube trend cekilemedi ({type(e).__name__}: {e})")
        yt_items = []

    print("GDELT haber indeksi cekiliyor...")
    try:
        news_items = fetch_gdelt_ai_news()
    except Exception as e:
        print(f"  UYARI: GDELT cekilemedi ({type(e).__name__}: {e})")
        news_items = []

    print(f"\nToplam {len(yt_items)} YouTube basligi + {len(news_items)} haber basligi\n")

    print("=== GERCEK AI HABER GUNDEMI (GDELT, insan onayi bekliyor) ===")
    print("Bolum konusu adaylari icin asil bakilmasi gereken liste bu.\n")
    if news_items:
        news_words, news_examples = score_topics(news_items)
        for word, score in news_words:
            print(f"- '{word}' (puan: {score:.1f}) -> orn: \"{news_examples[word]}\"")
    else:
        print("(GDELT'ten veri gelmedi)")

    print("\n=== YOUTUBE 'SCIENCE & TECHNOLOGY' TRENDI (sadece format/ilham icin) ===")
    print("Bu genelde oyun/donanim agirlikli cikiyor - AI konu secimi icin degil,")
    print("'ne tarz basliklar/hook'lar izleniyor' fikrini gormek icin.\n")
    if yt_items:
        yt_words, yt_examples = score_topics(yt_items)
        for word, score in yt_words:
            print(f"- '{word}' (puan: {score:.1f}) -> orn: \"{yt_examples[word]}\"")
    else:
        print("(YouTube trend verisi gelmedi)")

    print("\nBu liste otomatik olarak hicbir yere yayinlanmadi. Bir konuyu")
    print("secip yeni bir episodes/bolum_X.py dosyasi olarak yazmak hala")
    print("elle/onayli bir adim.")


if __name__ == "__main__":
    main()
