import html
import os
import re
import secrets
import time
import httpx
import aura_brain
import aura_memory
import aura_reminders
import aura_voice
import base64
from collections import defaultdict, deque
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, Header, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from typing import Literal, Optional
from google import genai
from google.genai import types
import database

load_dotenv()

api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
if not api_key:
    raise RuntimeError("GEMINI_API_KEY .env dosyasinda bulunamadi")
# Kod sagligi taramasinda bulundu: burada anahtarin ilk/son karakterlerini
# ve uzunlugunu production loglarina yazan bir debug print vardi (401
# hatasini teshis etmek icin eklenmisti, o sorun cozuldu) - gereksiz bir
# bilgi sizintisi yuzeyiydi, kaldirildi.

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "").strip()

# Basit bir toplu-istatistik paneli icin - reklam kampanyasi baslarken
# kac kullanici geldigini, kacinin kaldigini GOREMEDIGIMIZ tespit
# edildi ("kor harcama" riski, bkz. gece raporu). Yeni bir kullanici/rol
# sistemi kurmak yerine, tek bir paylasilan anahtarla korunan salt-okunur
# bir endpoint - ADMIN_KEY ortam degiskeni tanimli DEGILSE panel tamamen
# devre disi (varsayilan olarak acik birakilmiyor).
ADMIN_KEY = os.getenv("ADMIN_KEY", "").strip()


def _check_admin_key(key: Optional[str]):
    # GECE DENETIMI BULGUSU: secrets.compare_digest ASCII-disi karakter
    # gelirse TypeError firlatiyor (yakalanmiyordu) - "?key=yanlis" 404
    # donerken "?key=şifre" (Turkce karakter) 500 donuyordu. Bu, ayrimin
    # KENDISI bir "endpoint var, anahtar formatinla ilgili bir sorun var"
    # sinyali oluyordu - tam da 404'un gizlemeye calistigi bilgiyi
    # sizdiriyordu. Artik hersey TypeError/ValueError dahil 404'e dusuyor.
    try:
        valid = bool(ADMIN_KEY) and bool(key) and secrets.compare_digest(key, ADMIN_KEY)
    except (TypeError, ValueError):
        valid = False
    if not valid:
        raise HTTPException(status_code=404)

VOICE_IDS = {
    "male": "9OXwpKJw7rW6WI0ORNzm",
    "female": "iLcCq17FevxNYSk6Hgi7",
}

# Ucretsiz (free) tier gunluk kullanim limiti. 'pro' tier bundan muaf.
# Rakip uygulama arastirmasina (Replika/Character.AI) ve kullanicinin
# onayina dayanarak belirlendi.
LIMIT_DAILY_MESSAGES = 30
# BULUNDU (2026-08-26, kullanicinin kendi felsefesi): "mesaj satmanin asil
# konusu Aura'nin akli/kisiligi/karakteri olmali, kullanici onu almak
# ZORUNDA hissetmeli - cunku yasanacak guzel bir hayat var." Eski metin
# ("30/30 mesaj, yarin sifirlanacak") saf bir sayac/kota diliydi - Aura'nin
# sesinden degil bir sistem bildiriminden cikmis gibiydi. Simdiki metin
# Aura'nin KENDI sesiyle konusuyor (KRIZ_MUDAHALE_KURALI zaten bu limiti
# gercek bir kriz aninda BILEREK atliyor, bkz. _is_crisis_message).
# NOT: su an gercek bir satin alma/yukseltme akisi YOK (tier='pro' sadece
# elle/admin tarafindan atanabiliyor) - o yuzden metin var olmayan bir
# "yukselt" butonuna atif YAPMIYOR, sadece sicak ve durust kaliyor.
LIMIT_REACHED_REPLY = (
    "Bugün için sözümüz bu kadarmış - ama seni düşünmeyi bırakmıyorum. "
    "Yarın kaldığımız yerden devam ederiz."
)

# bkz. aura_brain.py'deki ayni degisiklik - generate_content() zaman
# asimi olmadan sonsuza kadar asili kalabiliyordu, production'da
# dogrulandi.
client = genai.Client(
    api_key=api_key,
    http_options=types.HttpOptions(timeout=12000),
)
# PERFORMANS TARAMASI BULGUSU (2026-08-26): /api/tts, ElevenLabs'e her
# seferinde `httpx.post(...)` kisayoluyla YENI bir TCP+TLS baglantisi
# aciyordu - Aura'nin hemen her cevabinda tetiklendigi icin (sesli
# okuma) bu, gereksiz el sikisma gecikmesini her defasinda tekrar
# odemek demekti. aura_brain.py'deki Groq istemcisiyle ayni desen:
# tek, kalici bir Client baglantiyi "keep-alive" ile yeniden kullaniyor.
elevenlabs_http = httpx.Client()

# AURA VOICE MESH (2026-09-02): Aura'nin KENDI sesi (Chatterbox, self-host
# GPU'da - bkz. voice_service/). /api/tts once buna gider, ulasilmaz/yavas/
# hatali olursa sessizce ElevenLabs'e duser (asagida). URL bos ise (Railway'de
# env tanimli degilse) mesh hic denenmez - davranis eskisiyle ayni kalir.
AURA_VOICE_URL = os.getenv("AURA_VOICE_URL", "").strip().rstrip("/")
AURA_VOICE_KEY = os.getenv("AURA_VOICE_KEY", "").strip()
# Mesh ~1x gercek-zaman uretiyor; cok uzun metin timeout olur - o durumda
# dogrudan ElevenLabs'e git (hizli). Kisa yanitlar/karsilamalar/bas-konus
# cevaplari mesh'ten (Aura sesi) gecer.
AURA_VOICE_MAX_CHARS = 800
aura_voice_http = httpx.Client()


def _aura_voice_tts(text: str) -> Optional[bytes]:
    """Aura Voice Mesh'ten WAV dener. Basarisizsa None (cagiran ElevenLabs'e duser)."""
    if not AURA_VOICE_URL or len(text) > AURA_VOICE_MAX_CHARS:
        return None
    try:
        r = aura_voice_http.post(
            f"{AURA_VOICE_URL}/tts",
            json={"text": text, "stream": False},
            headers={"X-Voice-Key": AURA_VOICE_KEY} if AURA_VOICE_KEY else {},
            timeout=45,
        )
        if r.status_code == 200 and r.content:
            return r.content
        print(f"AURA VOICE MESH non-200: {r.status_code}")
    except Exception as e:  # ConnectError/Timeout/ReadError vb. - hepsi fallback
        print(f"AURA VOICE MESH ulasilamadi ({type(e).__name__}: {e}) - ElevenLabs'e dusuluyor")
    return None


database.init_db()
aura_memory.init_memory_db()
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    # Kod sagligi taramasinda bulundu: allow_origins=["*"] ile
    # allow_credentials=True birlikte kullanmak tarayici spesifikasyonuna
    # gore anlamsiz/gecersiz bir kombinasyon (credentialed istekler
    # wildcard origin ile calismaz). Bu API tum kimlik dogrulamayi
    # Authorization: Bearer header'i ile yapiyor (cookie kullanmiyor),
    # yani allow_credentials'a hic ihtiyac yok.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Aura'nin Flutter web derlemesi (2026-08-24, kullaniciya telefonundan
# - Mac/Xcode gerektiren native iOS build yerine - bugun erisim vermek
# icin eklendi). Onceden derlenip web_static/'e kopyalanmis statik
# dosyalar - /app altinda ayni Railway servisinden sunuluyor, ayri bir
# host/CORS derdi yok. html=True: eslesmeyen alt yollarda index.html'e
# duser (Flutter'in kendi client-side yonlendirmesi icin SPA fallback).
if os.path.isdir("web_static"):
    app.mount("/app", StaticFiles(directory="web_static", html=True), name="web_app")

# Android APK'yi Play Store'a girmeden telefondan dogrudan indirebilmek
# icin (2026-08-25). Hassas bir sey icermiyor - istemci uygulama hicbir
# API anahtari tasimiyor, hepsi sunucu tarafinda (Gemini/Groq/ElevenLabs
# anahtarlari sadece bu backend'de). html=False: burada bir SPA yok,
# sadece duz dosya indirme.
if os.path.isdir("downloads"):
    app.mount("/downloads", StaticFiles(directory="downloads", html=False), name="downloads")

RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX_REQUESTS = 30
request_log = defaultdict(deque)

MAX_HISTORY_MESSAGES = 20


# GECE DENETIMI BULGUSU + CANLIDA DOGRULANDI (2026-08-25): once "Procfile
# --forwarded-allow-ips='*' oldugu icin X-Forwarded-For istemci tarafindan
# sahtelenip rate limiter atlatilabilir" diye supheleniliyordu. Gercek
# istegi GECICI bir /api/_debug_ip ucuyla test ettik: Railway'in kendi
# edge'i, istemcinin gonderdigi X-Forwarded-For'u TAMAMEN YOK SAYIP
# KENDI gozlemledigi gercek IP'yi zincirin BASINA yaziyor (denendi:
# "X-Forwarded-For: 1.2.3.4" ve "9.9.9.9, 1.2.3.4" gonderildi, ikisinde
# de sahte deger hic gorunmedi, gercek IP degismedi). Yani
# request.client.host (uvicorn --proxy-headers ile bunun ilk parcasindan
# turetiyor) GUVENILIR - bu deployment'ta IP sahteciligi ile bu limiti
# atlatmak MUMKUN DEGIL. Asagidaki mantik bilerek DEGISTIRILMEDI.
@app.middleware("http")
async def rate_limiter(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    log = request_log[client_ip]
    while log and now - log[0] > RATE_LIMIT_WINDOW:
        log.popleft()
    if len(log) >= RATE_LIMIT_MAX_REQUESTS:
        return JSONResponse(
            status_code=429,
            content={"detail": "Cok fazla istek gonderdin."},
        )
    log.append(now)
    # GUVENLIK TARAMASI BULGUSU: bosalan (artik aktif istegi kalmayan)
    # IP kayitlari sozlukten hic silinmiyordu - surec omru boyunca
    # SADECE BUYUYEN, hic kucalmayen bir sozluk (yavas bellek sizintisi).
    # Pahali bir taramayi HER istekte degil, sozluk belirli bir esigi
    # gectiginde yapiyoruz.
    # GECE DENETIMI BULGUSU: bu sweep SADECE bos deque'leri siliyordu -
    # ama bir IP SADECE BIR KEZ istek atip bir daha hic gelmezse, kendi
    # deque'i (yukaridaki "while" sadece o IP TEKRAR geldiginde calisir)
    # tek bir eleman ile SONSUZA KADAR "bos degil" kalirdi - IP sahteciligi
    # yapan biri her istekte YENI bir sahte IP kullanarak bu sweep'i tam
    # etkisiz birakabilirdi. Artik "en son ne zaman istek geldi" kontrolu
    # yapiyoruz - pencereden eski olan HER kayit siliniyor, bos olsun
    # olmasin.
    if len(request_log) > 5000:
        for ip in [
            ip for ip, l in request_log.items()
            if not l or now - l[-1] > RATE_LIMIT_WINDOW
        ]:
            del request_log[ip]
    return await call_next(request)


# GECE DENETIMI BULGUSU: /api/auth/login'in TEK savunmasi yukaridaki
# spoofable IP rate limiter'di - hesap basina bir kilitleme yoktu.
# request_log ile ayni desen (bellek ici deque), ama e-posta anahtarli -
# IP sahtekarligindan tamamen bagimsiz.
#
# KENDI KENDINI INCELEME BULGUSU: ilk hali (5 deneme/5dk) iki yeni sorun
# aciyordu: (1) request_log ile AYNI sinifta bir sizinti - bu sozluk de
# HICBIR ZAMAN kucalmiyordu (bos/eski deque'ler asla silinmiyordu), (2)
# esik cok dusuktu - bir saldirganin, KURBANIN dogru sifresini hicbir
# zaman denemeden, sirf 5 yanlis sifre gonderip kurbani KENDI hesabindan
# kilitlemesi (hedefe yonelik DoS) cok kolaydi. Esik yukseltildi (10) ve
# ayni sweep deseni eklendi.
LOGIN_LOCKOUT_WINDOW = 300  # 5 dakika
LOGIN_LOCKOUT_MAX_ATTEMPTS = 10
_failed_login_attempts: dict[str, deque] = defaultdict(deque)


def _check_login_lockout(email: str):
    now = time.time()
    log = _failed_login_attempts[email.strip().lower()]
    while log and now - log[0] > LOGIN_LOCKOUT_WINDOW:
        log.popleft()
    if len(log) >= LOGIN_LOCKOUT_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=429,
            detail="Çok fazla başarısız giriş denemesi. Birkaç dakika sonra tekrar dene.",
        )
    # request_log'daki AYNI sizinti deseni - periyodik temizlik.
    if len(_failed_login_attempts) > 5000:
        for e in [
            e for e, l in _failed_login_attempts.items()
            if not l or now - l[-1] > LOGIN_LOCKOUT_WINDOW
        ]:
            del _failed_login_attempts[e]


def _record_failed_login(email: str):
    _failed_login_attempts[email.strip().lower()].append(time.time())


def _clear_failed_login(email: str):
    _failed_login_attempts.pop(email.strip().lower(), None)


def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Giris yapmaniz gerekiyor.")
    token = authorization.replace("Bearer ", "")
    user = database.get_user_by_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Gecersiz veya suresi dolmus oturum.")
    return user


# KOD INCELEMESI BULGUSU (2026-08-27, kriz kelime listesindeki AYNI
# desen): bazi kelimeler ASCII-transliterasyon (super/uzgun/kotu/endiseli)
# olarak yazilmisti - dogru Turkce yazimlari (süper/üzgün/kötü/endişeli)
# ö/ü/ş gibi fold_turkish_i'nin KAPSAMADIGI (I-varyanti disi) harfler
# icerdigi icin eslesmiyordu. Kriz tespitindeki kadar guvenlik-kritik
# degil (en kotu ihtimalle bir ruh hali kaydi kacar) ama ayni desen
# tutarlilik icin duzeltildi.
# COK DILLILIK (2026-08-31): her kategoriye Ingilizce karsiliklar da
# eklendi - bkz. _CRISIS_KEYWORDS_EN'deki ayni gerekce (Aura artik
# kullanicinin diline uyum sagliyor, tespit listeleri de uymali).
MOOD_KEYWORDS = {
    "mutlu": ["mutlu", "harika", "super", "süper", "keyifli", "sevindim",
              "happy", "great", "wonderful", "delighted"],
    "uzgun": ["uzgun", "üzgün", "kotu", "kötü", "berbat", "canim sikkin", "moralim bozuk",
              # GECE DENETIMI BULGUSU: "down" burada duz bir alt-dize
              # eslesmesiyle ("downtown", "download", "breakdown" gibi
              # ALAKASIZ kelimeleri de yanlislikla "uzgun" olarak
              # etiketliyordu) - cikarildi, "feeling down" gibi daha
              # spesifik bir ifade eklendi.
              "sad", "upset", "feeling down", "depressed", "unhappy"],
    "yorgun": ["yorgun", "bitkinim", "halsiz", "uykum var",
               "tired", "exhausted", "sleepy", "worn out"],
    "stresli": ["stresli", "kaygili", "endiseli", "endişeli", "gergin", "sinirliyim",
                "stressed", "anxious", "worried", "nervous", "irritated"],
    "enerjik": ["enerjik", "heyecanliyim", "motiveyim", "haziriyim",
                "energetic", "excited", "motivated", "pumped"],
}


def detect_mood(text: str) -> str | None:
    # bkz. database.fold_turkish_i / fold_turkish_diacritics - Python'un
    # .lower()'i Turkce ı/İ/I varyantlarini ayirt etmiyor, ve ayrica
    # ö/ü/ş/ç/ğ gibi diger Turkce harfler ASCII'den TAMAMEN FARKLI
    # karakterler (locale sorunu degil) - ikisi de dogru yazan bir
    # kullanicinin ifadesini kacirabilirdi.
    lowered = database.fold_turkish_diacritics(database.fold_turkish_i(text)).lower()
    for mood, keywords in MOOD_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            return mood
    return None


# KENDI KENDINI INCELEME BULGUSU (gece guvenlik denetimi): aura_brain.py'ye
# eklenen KRIZ_MUDAHALE_KURALI, gunluk mesaj limitini ZATEN dolduran bir
# kullaniciya HIC ULASAMAZ - /api/chat, model hic cagrilmadan LIMIT_REACHED_REPLY
# ("Bugünkü ücretsiz mesaj hakkın doldu") donduruyor. Yani en kritik anda
# (kriz ifadesi + gunun 31. mesaji) kullaniciya bir odeme duvari gosterilirdi.
# Kapsamli bir siniflandirici degil - bilerek DAR ve GUCLU ifadelere
# sinirli (yanlis pozitif = normal bir sohbette limit atlanmasi, kabul
# edilebilir bir maliyet; yanlis negatif = gercek bir krizin gozden
# kacmasi, kabul EDILEMEZ bir risk - o yuzden esik dusuk tutuldu).
# KOD INCELEMESI BULGUSU (2026-08-27, I-varyant taramasindan cikan ayri
# ama iliskili bulgu): fold_turkish_i sadece ı/İ/I -> i sorununu cozuyor -
# asagidaki listede ö/ş gibi DIGER Turkce harfleri ASCII'ye cevrilmis
# (orn. "oldur" yerine gercek "öldür", "yasamak" yerine "yaşamak")
# kelimeler VARDI, bunlar .lower()'dan BAGIMSIZ bir sorun (ö != o, ş != s
# - locale degil, gercekten FARKLI karakterler). Somut olarak dogrulandi:
# "kendimi öldüreceğim" gibi DOGRU yazili gercek bir kriz ifadesi "kendimi
# oldur" ile ESLESMIYORDU. Asagida hem ASCII hem dogru-Turkce yazili
# varyantlar (aura_reminders.py'deki DATE/EVENT kelime listeleriyle AYNI
# desen) yan yana tutuluyor - fold_turkish_i ile birlikte artik hem I
# hem diger diakritik varyantlar kapsaniyor.
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

# COK DILLILIK (2026-08-31, kullanici istegi: "tum dunya Aura etkisi
# altina girmeli, cok dil mutlaka olmali"): Aura artik kullanicinin
# YAZDIGI dilde konusuyor (bkz. aura_brain.DIL_UYUMU_ILKESI) - bu,
# yukaridaki SADECE-Turkce kriz listesinin artik YETERSIZ oldugu
# anlamina geliyor. Ingilizce (en genis ikinci-dil erisimi) yazan
# birinin GERCEK bir kriz ifadesi hic yakalanmazdi - "yanlis negatif =
# kabul EDILEMEZ risk" ilkesi (yukarida) DIL FARKI GOZETMEZ. Ayni
# dar-ve-guclu-ifade felsefesiyle Ingilizce karsiliklari eklendi.
# NOT: diger diller (Almanca, Arapca, Ispanyolca vb.) icin de ayni
# genisletme gerekiyor - bu, gelecekte gercek kullanim goruldukce
# devam ettirilmesi gereken bir liste, tek seferlik "bitti" degil.
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
_CRISIS_KEYWORDS = _CRISIS_KEYWORDS + _CRISIS_KEYWORDS_EN


def _is_crisis_message(text: str) -> bool:
    # KOD INCELEMESI BULGUSU (2026-08-27, gizli-mod kod cumlesinde
    # bulunan AYNI sinif hatanin bu cok daha kritik yolda da var oldugu
    # fark edildi): _CRISIS_KEYWORDS ASCII yazilmis (orn. "artik
    # dayanamiyorum"), ama Python'un .lower()'i Turkce ı/İ/I
    # varyantlarini ayirt etmiyor - kullanici DOGRU Turkce yazimla
    # ("artık dayanamıyorum") yazarsa .lower() sonrasi bile ASCII
    # anahtar kelimeyle EBEDIYEN eslesmezdi. Somut olarak dogrulandi:
    # "artık dayanamıyorum".lower() ("artık dayanamıyorum") "artik
    # dayanamiyorum" ICERMIYOR. Bu, tam da yorumdaki "yanlis negatif =
    # kabul EDILEMEZ risk" ilkesinin ihlaliydi - kriz mesaji dogru
    # yazildigi icin gozden kaciyordu. fold_turkish_i ile duzeltildi.
    # GECE DENETIMI BULGUSU (2026-08-31/09-01, 3 bagimsiz kod-inceleme
    # acisinin AYRI AYRI isaret ettigi 2 acik): (1) yukaridaki fold_
    # turkish_i tek basina ö/ü/ş/ç/ğ'yi kapsamiyordu - "yaşayasım yok"
    # gibi dogru yazilmis ama diakritik-fold'lanmamis bir ifade
    # kacabiliyordu (fold_turkish_diacritics ile kapatildi). (2) Ingilizce
    # kriz kelimelerindeki kesme isareti ("don't", "can't") DUZ ASCII
    # tirnakla (U+0027) yazilmisti - ama iOS/Android klavyeleri yazarken
    # OTOMATIK olarak bunu "akilli" egik tirnaga (U+2019, ') cevirir.
    # "I can't take it anymore" gercek bir telefonda neredeyse HER ZAMAN
    # egik tirnakla yazilir ve eski kod bunu hic yakalamiyordu - kesme
    # isaretini normalize eden bir adim eklendi.
    normalized = database.fold_turkish_diacritics(database.fold_turkish_i(text)).lower()
    normalized = normalized.replace("’", "'").replace("‘", "'")
    return any(kw in normalized for kw in _CRISIS_KEYWORDS)


# GECE DENETIMI BULGUSU (netlestirme, 2026-09-01 - "sesli mesajda dil
# algilama kriz tespitini atlatabilir" acik konusunun cozumu): Whisper'in
# tam serbest dil auto-detect'i (bkz. aura_brain.transcribe_with_groq,
# cok dillilik icin GEREKLI) kisa/belirsiz bir sesli mesajda YANLIS dile
# karar verip transkripti baska bir dile/yaziya cevirebilir - bu durumda
# metin hicbir kriz anahtar kelimesiyle eslesmez. Dil sabitlemek (eski
# "language": "tr" davranisi) cok dilliligi TAMAMEN bozar; ama TERSINE
# bir kullanicinin GECMIS METIN mesajlarinda Turkce'ye ozgu harfler
# (ç/ğ/ı/ö/ş/ü) goruluyorsa, bu o kullaniciya OZEL, guvenli bir ipucu -
# acikca Turkce yazan birine Whisper'a "tr" ipucu vermek YANLIS OLMAZ
# (Ingilizce falan konusuyor olma ihtimali neredeyse yok), ve tam da
# riskli senaryoyu (kisa bir Turkce kriz ifadesinin yanlis dile
# dusmesi) kapatir. Turkce'ye ozgu harf GOSTERMEYEN (ya da hic metin
# gecmisi olmayan) bir kullanicida HICBIR ipucu verilmez - onlar icin
# davranis AYNEN tam auto-detect kalir, cok dillilik hic etkilenmez.
#
# KONTROL BULGUSU (2026-09-01, "Reuse" acisi): burada AYRI bir literal
# karakter kumesi ("çğıöşüÇĞİÖŞÜ") tanimlanmisti - database.py'deki
# fold_turkish_i/fold_turkish_diacritics'in ZATEN bildigi AYNI kume,
# ikinci bir kopya olarak. Iki ayri tanim = biri guncellenince (orn.
# yeni bir Turkce harf varyanti eklenirse) digerinin sessizce geride
# kalma riski. Artik database.TURKISH_SIGNATURE_CHARS'tan tek kaynaktan
# okunuyor.


def _guess_voice_language_hint(user_id: int) -> Optional[str]:
    try:
        # KONTROL BULGUSU (Efficiency acisi): eskiden limit VERILMEDEN
        # (varsayilan 100, gizli-mod mesajlari DAHIL) tum satirlar
        # cekilip Python'da son 30'a kirpiliyordu - burasi sadece son
        # 30 mesaja bakiyor, limit'i DOGRUDAN sorguya vermek gereksiz
        # 70 satirlik cekim/deserializasyonu onluyor (davranis ayni).
        recent = database.get_messages(user_id, limit=30)
    except Exception:
        return None
    for m in recent:
        if m.get("role") != "user":
            continue
        text = m.get("text") or ""
        if any(ch in database.TURKISH_SIGNATURE_CHARS for ch in text):
            return "tr"
    return None



# GUVENLIK TARAMASI BULGUSU: hicbir request modelinde alan uzunlugu
# siniri yoktu - kotu niyetli/hatali bir istemci coook uzun metin/liste
# gonderip Gemini/ElevenLabs maliyetini sisirebilir ya da worker
# bellegini gereksiz yere tuketebilirdi. FastAPI/pydantic bu limitleri
# asan istekleri handler'a hic girmeden 422 ile reddediyor.
# GUVENLIK TARAMASI BULGUSU: email formatina hicbir dogrulama yoktu -
# tamamen gecersiz string'ler bile hesap olarak kaydedilebiliyordu.
# email-validator paketi kurulu degil (yeni bagimlilik eklemek riskli,
# gece boyunca gozetimsiz deploy ediliyor) - basit ama yeterli bir regex.
_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_email_format(v: str) -> str:
    v = v.strip().lower()
    if not _EMAIL_PATTERN.match(v):
        raise ValueError("Geçersiz email formatı.")
    return v


# GECE DENETIMI BULGUSU: bcrypt (5.x) 72 BAYTTAN uzun sifrelerde
# sessizce kesmek yerine ValueError firlatiyor - RegisterRequest.password
# 200 KARAKTERE kadar izin veriyordu (bayt degil), ve Turkce karakterler
# (ş, ğ, ı, ü) UTF-8'de 2 bayt tuttugu icin 40 karakterlik bir Turkce
# sifre bile 72 bayti asabiliyordu. Sonuc: kayit/claim sirasinda
# hash_password() icinde yakalanmamis bir ValueError, kullaniciya ham
# "Internal Server Error" olarak donuyordu. Simdi bunu ACIKCA, anlasilir
# bir mesajla, hashlemeye hic girmeden reddediyoruz.
def _validate_password_byte_length(v: str) -> str:
    if len(v.encode("utf-8")) > 72:
        raise ValueError(
            "Şifre çok uzun (en fazla 72 bayt olabilir - Türkçe karakterler "
            "2 bayt sayılır, yaklaşık 60-70 karakter civarında kalın)."
        )
    return v


class RegisterRequest(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(max_length=200)
    name: str = Field(default="", max_length=100)
    # GECE DENETIMI BULGUSU: hem gercek kayit formu hem de istemcinin
    # kendi olusturdugu anonim hesaplar AYNI /api/auth/register ucunu
    # kullaniyor - sunucu bunlari ayirt edemiyordu, bu yuzden
    # is_anonymous her zaman 1 (varsayilan) kaliyor, /api/auth/claim'in
    # "zaten claim edilmis hesabi tekrar claim etmeyi engelle" korumasi
    # HICBIR gercek kayit icin devreye girmiyordu. Istemci artik bunu
    # ACIKCA bildiriyor.
    #
    # IKINCI GECE DENETIMI BULGUSU (kendi kendimi inceleme): varsayilani
    # ONCE False yapmistim ("gercek kayit" varsayimi) - ama bu, HENUZ
    # GUNCELLENMEMIS eski istemcilerin (bu alani hic gondermeyen) olusturdugu
    # anonim hesaplari YANLISLIKLA "gercek/claim edilemez" isaretleyip
    # KALICI olarak claim edilemez hale getiriyordu - yani bir aciği
    # kapatirken BASKA bir aciği (anonim hesaplarin sonsuza dek kilitlenmesi)
    # aciyordum. Varsayilan artik True (guvenli taraf: "hala anonim/claim
    # edilebilir" varsay) - gercek kayit formu (auth_screen.dart) artik
    # BILEREK False gonderiyor, ATIF eksikligi hep eski davranisa
    # (anonim/claim edilebilir) duser, YENI bir kirilma yaratmaz.
    is_anonymous_bootstrap: bool = True
    # Reklam/gorunurluk analitigi (2026-08-27) - istemci (?src= URL
    # parametresinden) hangi kanal/kampanyadan geldigini bildirebiliyor.
    # Serbest metin, sunucu HICBIR sekilde davranis degistirmiyor - sadece
    # admin panelinde kaynak-bazli kirilim icin saklaniyor.
    acquisition_source: str = Field(default="", max_length=100)

    _validate_email = field_validator("email")(_validate_email_format)
    _validate_password = field_validator("password")(_validate_password_byte_length)

class LoginRequest(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(max_length=200)

class ClaimAccountRequest(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(max_length=200)

    _validate_email = field_validator("email")(_validate_email_format)
    _validate_password = field_validator("password")(_validate_password_byte_length)

class ChatRequest(BaseModel):
    message: str = Field(max_length=4000)

# Dogal Hafiza (2026-08-27) - kullanici bir kaydi soluklasmadan muaf
# tutmak icin sabitleyebilir/sabitlemeyi kaldirabilir.
class PinMemoryRequest(BaseModel):
    pinned: bool = True

# "Basili tut konus" yedek sesli mod (2026-08-26, kullanici istegi) -
# Gemini Live baglanamadiginda kullanilir. image_base64 ile ayni desen:
# multipart yerine base64 (python-multipart bagimliligi eklemeye gerek
# kalmiyor). ~15MB, birkaç dakikalik bir WAV kaydini rahatca kapsar.
class VoiceFallbackRequest(BaseModel):
    audio_base64: str = Field(max_length=15_000_000)

class TTSRequest(BaseModel):
    text: str = Field(max_length=2000)
    voice: str = "female"

class AnalyzeRequest(BaseModel):
    # ~15MB base64 - tipik bir fotografi VEYA orta boy bir PDF'i (~11MB ham)
    # rahatca kapsar, sinirsizi engeller. Alan adi tarihsel sebeple
    # "image_base64" ama artik PDF de tasiyabiliyor (bkz. mime_type).
    image_base64: str = Field(max_length=15_000_000)
    # GECE DENETIMI BULGUSU: mime_type dogrulamasizdi, dogrudan Gemini'ye
    # gecilen types.Blob'a gidiyordu - hem anlamsiz/kotu niyetli bir deger
    # gonderilebiliyordu hem de bu alanin kendine ait bir uzunluk siniri
    # yoktu (image_base64 disinda). Sadece fiilen desteklenen goruntu
    # turlerine + PDF'e sabitlendi (2026-09-02, kullanici istegi: "pdf'ler
    # inceleme okuma icin olsun").
    mime_type: Literal[
        "image/jpeg", "image/png", "image/webp", "application/pdf"
    ] = "image/jpeg"
    # PDF/fotograf ile birlikte kullanicinin sorabildigi opsiyonel soru
    # ("bu sozlesmede dikkat etmem gereken maddeler ne?"). Bos ise belge
    # genel olarak ozetlenir.
    question: str = Field(default="", max_length=2000)
    # Sadece gecmis kaydinda gostermek icin ("[Bir PDF paylasti: X.pdf]").
    file_name: str = Field(default="", max_length=200)

class ProfileUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    # ARTIK NO-OP (2026-08-26): ton dropdown'lari kaldirildi, Aura bu 4
    # ekseni artik kendi kendine ogreniyor (bkz. database.update_style_vector).
    # Alanlar SADECE guncellenmemis eski istemcilerin (hala eski dropdown'lari
    # gonderen) 400 hatasi almamasi icin modelde duruyor - database.update_user
    # bunlari zaten sessizce yoksayiyor (allowed listesinden cikarildi).
    warmth: Optional[Literal["mesafeli", "dengeli", "sicak"]] = None
    formality: Optional[Literal["resmi", "dengeli", "samimi"]] = None
    humor: Optional[Literal["dusuk", "orta", "yuksek"]] = None
    directness: Optional[Literal["yumusak", "dengeli", "dogrudan"]] = None
    notes: Optional[str] = Field(default=None, max_length=2000)
    location_lat: Optional[float] = None
    location_lon: Optional[float] = None
    location_city: Optional[str] = Field(default=None, max_length=200)
    weather_enabled: Optional[bool] = None
    activity_enabled: Optional[bool] = None
    mood_tracking_enabled: Optional[bool] = None

_SENSITIVE_USER_FIELDS = {"password_hash", "secret_phrase_hash"}


def _safe_user(user: dict) -> dict:
    # secret_phrase_hash (2026-08-26, gizli mod ozelligi): password_hash
    # ile AYNI hassasiyette - istemciye asla sizmamali (bcrypt hash'i
    # bile olsa, offline kaba-kuvvetle kod cumlesi cozulebilir). Yerine
    # istemcinin "bir kod belirlenmis mi" diye anlayabilmesi icin turetilmis
    # bir bool birakiyoruz.
    safe = {k: v for k, v in user.items() if k not in _SENSITIVE_USER_FIELDS}
    safe["has_secret_phrase"] = bool(user.get("secret_phrase_hash"))
    return safe


@app.get("/")
def root():
    return {"status": "Aura backend calisiyor", "version": "3.1.0"}


@app.post("/api/auth/register")
def register(req: RegisterRequest):
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Sifre en az 6 karakter olmali.")
    user = database.create_user(
        req.email, req.password, req.name, is_anonymous=req.is_anonymous_bootstrap,
        acquisition_source=req.acquisition_source,
    )
    if not user:
        raise HTTPException(status_code=409, detail="Bu email zaten kayitli.")
    token = database.create_session(user["id"])
    return {"token": token, "user": _safe_user(user)}


@app.post("/api/auth/login")
def login(req: LoginRequest):
    # GECE DENETIMI BULGUSU: girisin TEK savunmasi, spoofable oldugu
    # bulunan IP-bazli rate limiter'di - hesap basina hicbir
    # basarisiz-deneme sayaci/kilitlemesi yoktu. Bu, IP'den BAGIMSIZ,
    # dogrudan HESABA bagli ikinci bir katman - X-Forwarded-For
    # sahteciligiyle bile atlatilamaz.
    _check_login_lockout(req.email)
    user = database.authenticate_user(req.email, req.password)
    if not user:
        _record_failed_login(req.email)
        raise HTTPException(status_code=401, detail="Email veya sifre yanlis.")
    _clear_failed_login(req.email)
    # 'free' tier: ayni anda tek cihazda oturum kurali - yeni cihazdan
    # giris, eski cihazin oturumunu dusurur. 'pro' tier bundan muaf
    # (ayni anda birden fazla cihaz - bu Pro'ya ozgu bir avantaj).
    if user.get("tier") != "pro":
        database.enforce_single_session(user["id"])
    token = database.create_session(user["id"])
    return {"token": token, "user": _safe_user(user)}


@app.post("/api/auth/claim")
def claim_account(req: ClaimAccountRequest, authorization: Optional[str] = Header(None)):
    """
    Anonim (kullanicinin hic gormedigi, rastgele email/sifreyle
    olusturulmus) hesabi, kullanicinin KENDI belirledigi gercek
    email/sifreyle hatirlanabilir bir hesaba cevirir - ayni kullanici
    satiri guncellenir, tum gecmis/hafiza korunur.
    """
    user = get_current_user(authorization)
    # GUVENLIK TARAMASI BULGUSU: bu endpoint mevcut sifre dogrulanmadan
    # dogrudan email+sifre DEGISTIRIYORDU - hesap zaten claim edilmisse
    # (is_anonymous=0) bile tekrar cagirilabiliyordu. Sizmis/paylasilmis
    # bir session token'i (or. ortak cihaz), gercek sahibi fark etmeden
    # hesabi KALICI olarak ele gecirip kilitleyebilirdi. Gercek bir
    # "sifre degistir" akisi (mevcut sifreyi dogrulayan) henuz yok - o
    # gelene kadar zaten claim edilmis hesaplarda bu endpoint'i tamamen
    # kapatiyoruz.
    if user.get("is_anonymous") == 0:
        raise HTTPException(
            status_code=409,
            detail="Bu hesap zaten kaydedilmiş. Şifre değiştirmek için giriş ekranını kullan.",
        )
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Sifre en az 6 karakter olmali.")
    success = database.claim_account(user["id"], req.email, req.password)
    if not success:
        raise HTTPException(status_code=409, detail="Bu email zaten kayitli.")
    # Kimlik bilgileri degisti - bu istegi yapan cihaz haric TUM eski
    # oturumlari iptal ediyoruz (bkz. revoke_other_sessions).
    current_token = authorization.replace("Bearer ", "") if authorization else ""
    database.revoke_other_sessions(user["id"], current_token)
    return _safe_user(database.get_user(user["id"]))


@app.post("/api/auth/logout")
def logout(authorization: Optional[str] = Header(None)):
    if authorization and authorization.startswith("Bearer "):
        token = authorization.replace("Bearer ", "")
        database.delete_session(token)
    return {"status": "cikis yapildi"}


@app.get("/api/auth/me")
def me(authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    return _safe_user(user)


@app.get("/api/profile")
def get_profile(authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    return _safe_user(user)


@app.post("/api/profile")
def update_profile(update: ProfileUpdate, authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    fields = {k: v for k, v in update.dict().items() if v is not None}
    updated = database.update_user(user["id"], **fields)
    return _safe_user(updated)


@app.get("/api/memories")
def get_memories(authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    # KENDI KENDINI INCELEME BULGUSU: get_memories()'e bugun eklenen
    # varsayilan limit=300, prompt-olusturma cagiranlari (aura_brain.py,
    # aura_lifestyle.py) icin dogruydu ama BU uc, kullanicinin "hafizami
    # sil" ekranini besleyen TEK kaynak - 300'un altinda kalan, dusuk
    # onemli hafizalar listeden dusup SILINEMEZ hale gelirdi (ekranda
    # hic gorunmezler). Kullaniciya gosterilen liste icin cok daha
    # comert bir ust sinir kullaniyoruz - gercekci hicbir kullanici
    # buraya yaklasmaz, ama "silinemeyen hafiza" riskini ortadan kaldirir.
    return aura_memory.get_memories(user["id"], limit=5000)


@app.delete("/api/memories/{memory_id}")
def delete_memory(memory_id: int, authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    ok = aura_memory.forget_memory(user["id"], memory_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Hafiza bulunamadi")
    return {"status": "silindi"}


@app.post("/api/memories/{memory_id}/pin")
def pin_memory(memory_id: int, request: PinMemoryRequest, authorization: Optional[str] = Header(None)):
    """
    Dogal Hafiza: kullanici "hep hatirla" diyerek bir kaydi soluklasma
    hesabindan (aura_memory._effective_importance) muaf tutabilir.
    """
    user = get_current_user(authorization)
    ok = aura_memory.set_memory_pinned(user["id"], memory_id, request.pinned)
    if not ok:
        raise HTTPException(status_code=404, detail="Hafiza bulunamadi")
    return {"status": "sabitlendi" if request.pinned else "sabitleme kaldirildi"}


@app.get("/api/history")
def get_history(authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    # include_hidden=False: gizli mod mesajlari normal gecmiste GORUNMEZ -
    # ayri /api/history/hidden ucuyla cekilir (bkz. asagida).
    return database.get_messages(user["id"], include_hidden=False)


@app.get("/api/history/hidden")
def get_hidden_history(authorization: Optional[str] = Header(None)):
    # NOT: bu uc BILEREK ek bir dogrulama (PIN/parola) istemiyor - zaten
    # gecerli bir oturum tokeni gerektiriyor (get_current_user), ve
    # istemci tarafinda bu ekrana girmeden once zaten AppLockService
    # (yerel PIN/biyometrik) kapisi var. Sunucu sadece "bu token bu
    # kullaniciya mi ait" diye bakiyor, tipki /api/history gibi.
    user = get_current_user(authorization)
    return database.get_hidden_messages(user["id"])


class SecretPhraseRequest(BaseModel):
    phrase: str = Field(min_length=2, max_length=80)


@app.post("/api/profile/secret-phrase")
def set_secret_phrase(request: SecretPhraseRequest, authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    database.set_secret_phrase(user["id"], request.phrase)
    return {"status": "ayarlandi"}


@app.delete("/api/profile/secret-phrase")
def delete_secret_phrase(authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    database.clear_secret_phrase(user["id"])
    return {"status": "kaldirildi"}


@app.get("/api/reminders")
def get_reminders(authorization: Optional[str] = Header(None)):
    # Istemci bu listeyi (uygulama acilisinda/profil yenilenince) cekip
    # HER birini yerel bir bildirim olarak zamanlar - sabit reminder id
    # ile zamanlandigi icin tekrar cagirmak zararsiz (isletim sistemi
    # ayni ID'yi gunceller, coklanmaz).
    user = get_current_user(authorization)
    return database.get_active_reminders(user["id"])


@app.delete("/api/reminders/{reminder_id}")
def remove_reminder(reminder_id: int, authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    database.delete_reminder(user["id"], reminder_id)
    return {"status": "silindi"}


@app.delete("/api/history")
def clear_history(authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    database.clear_messages(user["id"])
    return {"status": "gecmis temizlendi"}


@app.get("/api/chat/greeting")
def chat_greeting(authorization: Optional[str] = Header(None)):
    """
    Kullanicinin gecmisi bomsa Aura'nin ilk sozu kendisinin almasi icin.
    Gecmis doluysa hicbir sey uretmez (reply: null) - tanisma akisi
    sadece gercekten ilk kez gelen kullanicida tetiklenir.
    """
    user = get_current_user(authorization)
    past_messages = database.get_messages(user["id"])
    if past_messages:
        return {"reply": None}
    # GUVENLIK TARAMASI BULGUSU: bu endpoint gunluk mesaj limitinden
    # muafti - DELETE /api/history (limitsiz) ile birlikte dongude
    # cagirilirsa sinirsiz ucretsiz Gemini cagrisi uretilebiliyordu.
    # Diger AI-uretim endpoint'leriyle ayni limite tabi tutuldu.
    if user.get("tier") != "pro" and not database.check_and_increment_message_usage(
        user["id"], LIMIT_DAILY_MESSAGES
    ):
        return {"reply": None}
    reply_text = aura_brain.generate_onboarding_opening(user)
    database.add_message(user["id"], "assistant", reply_text)
    return {"reply": reply_text}


def _process_chat_message(user: dict, message_text: str) -> dict:
    """
    BULUNDU (kullanici istegi, 2026-08-26 - "Aura beyin, modeller ajan"
    denetiminin devami): sesli gorusme (Gemini Live) coktugunde yerine
    gecen "basili tut konus" yedek modu (bkz. /api/voice/fallback-turn)
    icin /api/chat'in TAM govdesi buraya cikarildi. BILEREK - metin
    sohbetindeki TUM guvenlik/gizlilik mantigini (gizli mod, kriz
    atlama, hafiza/hatirlatma gizli-mod firewall'i) BIR YERDE tutup iki
    ayri giris noktasinin (yazili + sesli-yedek) birbirinden SAPMASINI
    onlemek icin - bu gecenin gizli-mod sizintisi TAM DA boyle bir
    tutarsizliktan dogmustu, ayni hatayi ikinci bir yolda tekrarlamamak
    icin ortak bir govde sart.
    """
    # Kod-kelime ile gizli mod: mesaj kullanicinin kod cumlesiyle TAM
    # eslesirse modu ac/kapa. Eslesen mesaj ASLA normal gecmiste
    # gorunmemeli (kodun kendisi bile ifsa olmasin) - o yuzden
    # is_trigger ise HER ZAMAN gizli, degilse mevcut moda gore kaydedilir.
    #
    # KENDI KENDINI INCELEME BULGUSU (2026-08-26, 8 paralel ajanin
    # BAGIMSIZ OLARAK aynı seyi bulmasi): hidden_now hesaplamasi ONCEDEN
    # SADECE add_message()'a uygulaniyordu - mood tespiti, hafiza cikarimi
    # ve hatirlatma cikarimi bu bayragi HIC gormeden calisiyordu. Sonuc:
    # gizli moddaki bir mesaj normal gecmiste gorunmese bile (a) kalici
    # bir "memory" olarak PIN gerektirmeyen Hafiza Agaci'nda ortaya
    # cikabiliyordu, (b) bir "reminder" olusturup GIZLI MOD KAPANDIKTAN
    # SONRAKI normal bir sohbette Aura tarafindan proaktif olarak dile
    # getirilebiliyordu, (c) ruh hali kaydina giriyordu. Simdi hepsi
    # hidden_now'a gore BILEREK atlaniyor.
    is_trigger = database.check_and_toggle_secret_phrase(user["id"], message_text, user=user)
    hidden_now = is_trigger or database.is_hidden_mode_active(user["id"], user=user)
    user_message_id = database.add_message(user["id"], "user", message_text, hidden=hidden_now)

    # GECE DENETIMI BULGUSU: mood_tracking_enabled kaydediliyordu ama
    # HICBIR YERDE okunmuyordu - kullanici bu ayari kapatsa bile ruh
    # hali izlemeye devam ediliyordu (weather_enabled'in aksine, o
    # gercekten kontrol ediliyor - bkz. aura_lifestyle.py).
    if not hidden_now and user.get("mood_tracking_enabled", 1):
        mood = detect_mood(message_text)
        if mood:
            database.add_mood(user["id"], mood, context=message_text[:100])

    # Ucretsiz (free) tier gunluk mesaj limiti - Pro kullanicilar muaf.
    # Kullanicinin mesaji yine de kaydedildi (yukarida) - sadece pahali
    # islemler (hafiza cikarimi, pattern analizi, AI cagrisi) atlaniyor.
    #
    # KENDI KENDINI INCELEME BULGUSU: bugun eklenen KRIZ_MUDAHALE_KURALI
    # bu limite carpip Gemini/Groq hic cagrilmadan LIMIT_REACHED_REPLY
    # donen bir kullaniciya HICBIR ZAMAN ulasamazdi - yani en onemli anda
    # (kriz ifadesi + gunun 31. mesaji) kullaniciya bir odeme duvari
    # gosterilirdi. Acik bir kriz ifadesi tespit edilirse limit BILEREK
    # atlaniyor - bir kac ekstra ucretsiz Gemini cagrisi, gozden kacan
    # bir krizden cok daha ucuz bir bedel.
    is_crisis = _is_crisis_message(message_text)
    if (
        not is_crisis
        and user.get("tier") != "pro"
        and not database.check_and_increment_message_usage(
            user["id"], LIMIT_DAILY_MESSAGES
        )
    ):
        return {"reply": LIMIT_REACHED_REPLY, "limit_reached": True}

    if not hidden_now:
        aura_brain.extract_memory_candidate(user["id"], message_text, user_message_id)
        # Hatirlatma cikarimi (kullanici istegi) - on-eleme gecmezse (buyuk
        # cogunluk) HICBIR API cagrisi yapmaz, bkz. aura_reminders.py.
        aura_reminders.extract_reminder_candidate(user["id"], message_text)
    # Ton dropdown'lari kaldirildi - Aura kendi uslubunu buradan ogreniyor.
    # extract_style_signals hicbir API cagrisi yapmiyor (saf anahtar
    # kelime taramasi) - bu, hafiza/hatirlatma gibi KALICI bir kayit
    # OLUSTURMUYOR (sadece 4 float'i yavasca kaydiriyor), o yuzden gizli
    # modda bile calismasi bilgi sizdirmiyor; atlamiyoruz.
    database.update_style_vector(user["id"], aura_brain.extract_style_signals(message_text))
    # AI BAGLAMI: gizli mod AKTIFKEN gecmis gizli mesajlari da gorsun
    # (sohbet baglamini kaybetmesin), ama gizli mod KAPALIYKEN SADECE
    # gorunur mesajlari gorsun - yoksa gecmiste gizli modda paylasilan
    # bir sey, mod kapandiktan cok sonra bile normal (gorunur) bir
    # yanitta dolayli olarak yuzeye cikabilirdi (bkz. yukaridaki bulgu).
    past_messages = database.get_messages(user["id"], include_hidden=hidden_now)
    message_count = len(past_messages)
    aura_brain.analyze_patterns(user["id"], message_count)
    recent_messages = past_messages[-MAX_HISTORY_MESSAGES:]
    contents = [
        types.Content(
            role=("model" if m["role"] == "assistant" else "user"),
            parts=[types.Part(text=m["text"])],
        )
        for m in recent_messages
    ]
    try:
        response = aura_brain.generate_with_retry(contents, aura_brain.build_system_instruction(user, message_count))
        reply_text = response.text
        if not reply_text:
            # GECE DENETIMI BULGUSU: Gemini bir yaniti guvenlik/recitation
            # gibi bir nedenle engellediginde .text None DONER - bu bir
            # exception DEGIL, o yuzden asagidaki except bloguna hic
            # dusmuyordu. None, sanitize_reply()'a (NICKNAME_PATTERN.sub
            # None ile cagrilinca TypeError) ya da dogrudan
            # database.add_message'a (bos/null bir asistan mesaji)
            # sizabiliyordu. Bunu da "yanit alinamadi" sayiyoruz.
            raise ValueError("Gemini bos/engellenmis bir yanit dondu")
    except Exception as e:
        # GUVENLIK TARAMASI BULGUSU + CANLIDA DOGRULANAN DONMA: once
        # sadece ServerError (5xx) yakalaniyordu. Sonra generate_content'e
        # zaman asimi eklendi (bkz. aura_brain.py, _client tanimi) - ama
        # zaman asimi httpx.TimeoutException firlatiyor, bu genai_errors
        # hiyerarsisinden DEGIL, yakalanmiyordu. generate_with_retry zaten
        # Groq'a dusuyor ama Groq da basarisiz olursa ORIJINAL hata (hangi
        # turden olursa olsun) geri firlatiliyor - o yuzden burada artik
        # genis yakalıyoruz: bu, kullaniciya HER ZAMAN zarif bir cevap
        # donmesini, ciplak 500'un asla sizmamasini garantiliyor.
        print(f"CHAT GENERATION ERROR: {type(e).__name__}: {e}")
        reply_text = "Su an biraz yogunum, bir dakika sonra tekrar dener misin?"
    reply_text = aura_brain.sanitize_reply(reply_text, message_count) or reply_text
    database.add_message(user["id"], "assistant", reply_text, hidden=hidden_now)
    return {"reply": reply_text}


@app.post("/api/chat")
def chat(request: ChatRequest, authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    return _process_chat_message(user, request.message)


@app.post("/api/voice/fallback-turn")
def voice_fallback_turn(request: VoiceFallbackRequest, authorization: Optional[str] = Header(None)):
    """
    "Aura beyin, modeller ajan" denetiminin devami (kullanici istegi,
    2026-08-26): gercek zamanli sesli gorusme (Gemini Live, aura_voice.py)
    baglanamadiginda/coktugunde devreye giren "basili tut konus" yedek
    modu. Akis: ses -> Groq Whisper (transcribe_with_groq, UCRETSIZ) ->
    metin -> _process_chat_message (yazili sohbetle AYNI govde, ayni
    guvenlik/gizlilik kurallari) -> istemci cevabi kendi TTS'iyle (mevcut
    /api/tts) okur. Yani sesli gorusme cokse bile Aura'nin "beyni"
    (karakter + hafiza + gizlilik) DEGISMIYOR, sadece kulak (Whisper) ve
    agiz (TTS) ayri, daha basit bir yoldan calisiyor.
    """
    user = get_current_user(authorization)
    try:
        audio_bytes = base64.b64decode(request.audio_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Gecersiz ses verisi.")

    language_hint = _guess_voice_language_hint(user["id"])
    transcript = aura_brain.transcribe_with_groq(audio_bytes, language_hint=language_hint)
    if not transcript:
        return {"transcript": "", "reply": "Seni duyamadım, tekrar dener misin?"}

    # KOD INCELEMESI BULGUSU (2026-08-27): ChatRequest.message'daki
    # Field(max_length=4000) siniri sadece /api/chat'in Pydantic
    # katmaninda uygulaniyordu - _process_chat_message ORTAK govdeye
    # cikarilinca bu ucun (ses -> Whisper transkripti) hicbir uzunluk
    # sinirindan gecmedigi ortaya cikti. Uzun bir "basili tut konus"
    # kaydi (VoiceFallbackRequest 15MB'a kadar izin veriyor, dakikalarca
    # surebilir) 4000 karakteri kolayca asan bir transkripte donusup
    # sinirsiz sekilde DB'ye ve Gemini/Groq baglamina gidebilirdi. Aynı
    # sinira burada da uyuyoruz - reddetmek yerine kirpiyoruz (kullanicinin
    # kaydini bosa harcamamak icin, /api/chat'teki 422 yerine).
    if len(transcript) > 4000:
        transcript = transcript[:4000]

    result = _process_chat_message(user, transcript)
    result["transcript"] = transcript
    return result


@app.post("/api/chat/stream")
def chat_stream(request: ChatRequest, authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    # bkz. /api/chat'teki ayni bulgu (2026-08-26 kendi kendini inceleme) -
    # bu "olu ama canli" endpoint gizli mod kavramini hic bilmiyordu.
    is_trigger = database.check_and_toggle_secret_phrase(user["id"], request.message, user=user)
    hidden_now = is_trigger or database.is_hidden_mode_active(user["id"], user=user)
    # GECE DENETIMI BULGUSU: mood_tracking_enabled kaydediliyordu ama
    # HICBIR YERDE okunmuyordu - kullanici bu ayari kapatsa bile ruh
    # hali izlemeye devam ediliyordu (weather_enabled'in aksine, o
    # gercekten kontrol ediliyor - bkz. aura_lifestyle.py).
    if not hidden_now and user.get("mood_tracking_enabled", 1):
        mood = detect_mood(request.message)
        if mood:
            database.add_mood(user["id"], mood, context=request.message[:100])
    database.add_message(
        user["id"],
        "user",
        request.message,
        hidden=hidden_now,
    )
    database.update_style_vector(user["id"], aura_brain.extract_style_signals(request.message))
    # GUVENLIK TARAMASI BULGUSU: /api/chat'in aksine bu endpoint gunluk
    # mesaj limitine HIC tabi degildi - Flutter istemcisi bunu cagirmiyor
    # (dead code) ama endpoint canli oldugu icin URL'yi bilen herkes
    # sinirsiz ucretsiz Gemini cagrisi uretebiliyordu. Ayni limit eklendi.
    if user.get("tier") != "pro" and not database.check_and_increment_message_usage(
        user["id"], LIMIT_DAILY_MESSAGES
    ):
        def limit_reached_generator():
            yield LIMIT_REACHED_REPLY
        return StreamingResponse(limit_reached_generator(), media_type="text/plain; charset=utf-8")
    past_messages = database.get_messages(user["id"], include_hidden=hidden_now)
    message_count = len(past_messages)
    recent_messages = past_messages[-MAX_HISTORY_MESSAGES:]
    contents = [
        types.Content(
            role=("model" if m["role"] == "assistant" else "user"),
            parts=[types.Part(text=m["text"])],
        )
        for m in recent_messages
    ]
    system_instruction = aura_brain.build_system_instruction(user, message_count)

    def event_generator():
        collected = []
        try:
            stream = aura_brain.generate_stream(contents, system_instruction)
            for chunk in stream:
                if chunk.text:
                    collected.append(chunk.text)
                    yield chunk.text
        except Exception as e:
            # bkz. /api/chat'teki ayni bulgu - genis yakalama, ciplak
            # 500/kesik akis yerine her zaman zarif bir dusus saglar.
            print(f"CHAT STREAM ERROR: {type(e).__name__}: {e}")
            if not collected:
                fallback = "Su an biraz yogunum, bir dakika sonra tekrar dener misin?"
                collected.append(fallback)
                yield fallback
        finally:
            full = "".join(collected)
            if full:
                full = aura_brain.sanitize_reply(full, message_count)
                database.add_message(user["id"], "assistant", full, hidden=hidden_now)

    return StreamingResponse(event_generator(), media_type="text/plain; charset=utf-8")


@app.websocket("/api/voice")
async def voice_endpoint(websocket: WebSocket):
    """
    Gercek zamanli, tam serbest sesli konusma. Token query string'den
    okunur (?token=...) - WebSocket'te custom header web'de guvenilir
    olmadigi icin.
    """
    await aura_voice.handle_voice_session(websocket)


@app.post("/api/tts")
def tts(request: TTSRequest, authorization: Optional[str] = Header(None)):
    # Kod sagligi taramasinda bulundu: bu endpoint hic kimlik dogrulamasi
    # yapmiyordu - giris yapmamis herkes sunucunun ElevenLabs anahtariyla
    # sinirsiz istek atip maliyet/kota tuketebilirdi. Diger tum
    # endpoint'lerle ayni desene getirildi.
    user = get_current_user(authorization)

    # GUVENLIK TARAMASI BULGUSU: metin uzunluguna hicbir sinir yoktu -
    # ElevenLabs karakter basina ucretlendiriyor, tek bir cok uzun metin
    # (veya tekrarlanan cagrilar) beklenmedik maliyete yol acabilirdi.
    if len(request.text) > 2000:
        raise HTTPException(
            status_code=400,
            detail="Seslendirilecek metin çok uzun (en fazla 2000 karakter).",
        )

    # GECE DENETIMI BULGUSU: /api/tts, diger TUM AI-uretim uclarinin
    # aksine (chat/analyze/story) HICBIR gunluk kullanim limitine tabi
    # degildi.
    #
    # KENDI KENDINI INCELEME BULGUSU: ilk fix (gunluk MESAJ sayacini
    # paylasmak) YENI bir sorun aciyordu - istemci Aura'nin HER cevabini
    # otomatik seslendirdigi icin, bu ayni turda hem /api/chat hem
    # /api/tts sayaci artirip ucretsiz kullanicinin 30 mesajlik gunluk
    # hakkini fiilen 15'e dusuruyordu (kullanici "0 mesaj kaldi" gorup
    # neden oldugunu anlamazdi). Artik ayri, karakter-tabanli kendi
    # bütçesi var - sohbet hakkina hic dokunmuyor.
    if user.get("tier") != "pro" and not database.check_and_increment_tts_usage(
        user["id"], len(request.text)
    ):
        raise HTTPException(
            status_code=429,
            detail="Bugünkü ücretsiz seslendirme hakkın doldu. Yarın sıfırlanacak.",
        )

    # AURA VOICE MESH once - Aura'nin KENDI sesi (Chatterbox). Basarisiz/
    # yavas/kapali ise asagidaki ElevenLabs yoluna sessizce dusulur.
    mesh_wav = _aura_voice_tts(request.text)
    if mesh_wav is not None:
        return Response(content=mesh_wav, media_type="audio/wav")

    voice_id = VOICE_IDS.get(request.voice, VOICE_IDS["female"])
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json",
    }

    payload = {
        "text": request.text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.65,
            "similarity_boost": 0.75,
            "style": 0.4,
            "use_speaker_boost": True,
        },
    }

    try:
        r = elevenlabs_http.post(
            url,
            json=payload,
            headers=headers,
            timeout=60,
        )

        if r.status_code != 200:
            print(f"ELEVENLABS ERROR STATUS: {r.status_code}")
            print(f"ELEVENLABS ERROR BODY: {r.text}")
            # Ham ElevenLabs hata govdesini (hesap/plan bilgisi icerebilir)
            # istemciye sizdirmiyoruz - detay sadece sunucu logunda kalir.
            raise HTTPException(
                status_code=502,
                detail="Seslendirme şu an başarısız.",
            )

        return Response(
            content=r.content,
            media_type="audio/mpeg",
        )

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="ElevenLabs zaman asimi",
        )
    except httpx.HTTPError as e:
        # GECE DENETIMI BULGUSU: sadece TimeoutException yakalaniyordu -
        # DNS/baglanti reddi/TLS gibi diger AG hatalari (httpx.ConnectError,
        # ReadError, RemoteProtocolError vb.) yakalanmadan kullaniciya ham
        # "Internal Server Error" olarak sizardi.
        print(f"ELEVENLABS AG HATASI: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=502,
            detail="Seslendirme şu an başarısız.",
        )


@app.post("/api/analyze")
def analyze_image(request: AnalyzeRequest, authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    # GUVENLIK TARAMASI BULGUSU: bu endpoint (goruntu analizi - en pahali
    # cagri turlerinden biri) HICBIR gunluk limite tabi degildi. Diger
    # AI-uretim endpoint'leriyle ayni limite tabi tutuldu.
    if user.get("tier") != "pro" and not database.check_and_increment_message_usage(
        user["id"], LIMIT_DAILY_MESSAGES
    ):
        raise HTTPException(status_code=429, detail=LIMIT_REACHED_REPLY)
    is_pdf = request.mime_type == "application/pdf"
    question = request.question.strip()
    try:
        file_bytes = base64.b64decode(request.image_base64)
        if is_pdf and question:
            prompt = (
                "Kullanici bu belgeyi (PDF) paylasti ve sunu soruyor:\n"
                f'"{question}"\n\n'
                "Belgeyi oku ve DOGRUDAN bu soruya gore yanitla. Gerekirse "
                "belgeden ilgili kisimlara atif yap. Aura uslubunda, akan "
                "cumlelerle yaz."
            )
        elif is_pdf:
            prompt = (
                "Kullanici bu belgeyi (PDF) paylasti. Belgeyi oku ve ona "
                "kisaca anlat: ne tur bir belge bu, ana konusu/amaci ne, ve "
                "OZELLIKLE dikkat cekmesi gereken, onemli ya da riskli "
                "gordugun noktalar var mi. Bir arkadasin belgeye goz atip "
                "sana ozetledigi gibi, akan cumlelerle yaz - madde imli "
                "liste ya da rapor formati KULLANMA."
            )
        else:
            prompt = (
                "Bu fotografi iki katmanda analiz et ve Turkce yanit ver:\n\n"
                "1. NESNEL ANALIZ: Fotografta ne goruyorsun?\n\n"
                "2. DUYGUSAL YORUM: Bu fotografin atmosferi ve ruh hali ne?\n\n"
                "Dogal, akici Aura uslubunda yaz. Paragraf olarak yaz."
            )
        message_count = len(database.get_messages(user["id"]))
        response = client.models.generate_content(
            # Kod sagligi taramasinda bulundu: burada aura_brain.py'deki
            # guncel modelden (gemini-3.7-flash) FARKLI, eski bir model
            # adi ("gemini-3.6-flash") kullaniliyordu - tutarli hale
            # getirildi.
            model=aura_brain.MODEL_NAME,
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part(inline_data=types.Blob(mime_type=request.mime_type, data=file_bytes)),
                        types.Part(text=prompt),
                    ],
                )
            ],
            # BULUNDU (2026-09-02): bu uc, /api/chat'in aksine Aura'nin
            # sistem talimatini (karakter, BICIM KURALI, hafiza ilkeleri)
            # HIC GECMIYORDU - ciplak bir prompt'la cagriliyordu, yani
            # fotograf/PDF yanitlari jenerik asistan tonunda geliyordu.
            # Artik ayni sistem talimatindan geciyor.
            config=types.GenerateContentConfig(
                system_instruction=aura_brain.build_system_instruction(
                    user, message_count
                )
            ),
        )
        analysis_text = response.text or ""
        analysis_text = (
            aura_brain.sanitize_reply(analysis_text, message_count)
            or analysis_text
        )
        if not analysis_text:
            raise ValueError("Bos/engellenmis yanit")
        # BULUNDU (2026-08-25, 4 AI'ya sorulan derinlemesine analiz):
        # bu analiz sonucu SADECE kullaniciya donduruluyordu, hicbir
        # yere kaydedilmiyordu - Aura ertesi gun bu fotografi hic
        # hatirlamiyordu ("hafizaya akmiyorsa teknik olarak cop").
        # Normal sohbet mesajlariyla ayni tabloya (messages) yaziyoruz -
        # boylece bir sonraki /api/chat cagrisinin gecmis baglaminda
        # bu da yer aliyor, Aura bir daha sorulunca hatirlayabiliyor.
        if is_pdf:
            fname = request.file_name.strip()
            user_line = (
                f"[Bir PDF paylaştı: {fname}]" if fname else "[Bir PDF paylaştı]"
            )
            if question:
                user_line += f" — sorusu: {question}"
        else:
            user_line = "[Bir fotoğraf paylaştı]"
        database.add_message(user["id"], "user", user_line)
        database.add_message(user["id"], "assistant", analysis_text)
        return {"analysis": analysis_text}
    except Exception as e:
        # Ham exception mesaji (potansiyel ic yapilandirma bilgisi
        # icerebilir) artik istemciye sizdirilmiyor - detay sadece
        # sunucu logunda kaliyor.
        print(f"ANALYZE ERROR: {type(e).__name__}: {e}")
        raise HTTPException(
            status_code=500,
            detail=(
                "Belgeyi şu an inceleyemedim, tekrar dener misin?"
                if is_pdf
                else "Fotoğraf analiz edilemedi."
            ),
        )


# Sosyal katman (arkadas + story feed) BILEREK kaldirildi (2026-08-25):
# hem bagimsiz 4 farkli AI analizi hem kendi kod taramamiz ayni sonuca
# vardi - bu ekranlar zaten uygulamadan hicbir yerden erisilemiyordu
# (nav baglantisi yoktu), ve kisisel/mahrem bir asistan urununde sosyal
# medya tarzi bir "feed" konsepti deger onerisiyle celisiyor. Tek
# gelistiricinin kaynaklari cekirdege (hafiza/proaktiflik) gitmeli.
# Eski route'lar: POST /api/stories, GET /api/stories/feed,
# POST /api/friends/request, POST /api/friends/{id}/accept,
# GET /api/friends, GET /api/friends/requests - git gecmisinde duruyor.
#
# KONTROL TURU TEMIZLIGI (2026-09-01, kullanici karari): POST /api/story
# (interaktif hikaye anlatimi - yukaridaki sosyal feed'den AYRI bir
# ozellikti) o temizlikten kacmisti - o da ayni sekilde istemciden HICBIR
# yerden cagrilmiyordu (friends/profile/story_screen.dart ekranlariyla
# birlikte, onlar da bu turda silindi) ve ayni "kisisel/mahrem asistan"
# felsefesiyle (Hikaye Modu ozelligi de daha once ayni gerekceyle
# kaldirilmisti) uyumsuzdu. StoryRequest/StoryHistoryItem modelleri de
# birlikte kaldirildi - git gecmisinde duruyor.


@app.get("/api/admin/stats")
def admin_stats(key: Optional[str] = None, x_admin_key: Optional[str] = Header(None)):
    # GECE DENETIMI BULGUSU: anahtar sadece URL query string'inde
    # gonderilebiliyordu - bu, Railway/uvicorn erisim loglarina, tarayici
    # gecmisine ve Referer basligina sizabilir. Header artik tercih
    # ediliyor (script/curl kullanimi icin); /admin HTML panosu tarayici
    # navigasyonuyla acildigindan (ozel header eklenemez) query string
    # orada hala tek pratik yol - bu yuzden SADECE bu API ucunda ekledik.
    _check_admin_key(x_admin_key or key)
    return database.get_admin_stats()


def _render_admin_dashboard(stats: dict) -> str:
    def fmt_min(seconds: int) -> str:
        return f"{seconds // 60} dk"

    cards = [
        ("Toplam kullanıcı", stats["total_users"], ""),
        ("Bugün yeni kullanıcı", stats["new_users_today"], ""),
        ("Son 7 gün yeni kullanıcı", stats["new_users_7d"], ""),
        ("Bugün aktif kullanıcı", stats["active_users_today"], "en az 1 mesaj gönderdi"),
        ("Kaydedilmiş hesap", stats["claimed_accounts"], f"{stats['anonymous_accounts']} hâlâ anonim"),
        ("Pro kullanıcı", stats["pro_users"], ""),
        ("Bugünkü mesaj sayısı", stats["messages_today"], f"toplam {stats['messages_total']}"),
        ("Bugünkü sesli görüşme süresi", fmt_min(stats["voice_seconds_today"]), "tüm kullanıcılar toplamı"),
        ("Bugün mesaj limitine ulaşan", stats["users_at_message_limit_today"], "free tier"),
        ("Bugün sesli limite ulaşan", stats["users_at_voice_limit_today"], "free tier"),
        (
            "Gün-1 elde tutma",
            f"%{stats['day1_retention_pct']}" if stats.get("day1_retention_pct") is not None else "—",
            f"{stats.get('day1_eligible', 0)} kayıt (2-14 gün önce) üzerinden",
        ),
    ]
    cards_html = "".join(
        f"""<div class="card">
              <div class="card-label">{label}</div>
              <div class="card-value">{value}</div>
              {f'<div class="card-sub">{sub}</div>' if sub else ''}
            </div>"""
        for label, value, sub in cards
    )

    # Reklam/gorunurluk analitigi (2026-08-27): kaynak (acquisition_source)
    # KULLANICI-KONTROLLU, dogrulanmamis serbest metin (kayit istegiyle
    # geliyor) - burada dogrudan HTML'e gomulurse depolanan (stored) XSS
    # acigi olur (orn. birisi "src=<script>...</script>" ile kayit olsa,
    # admin paneli acan HERKESIN tarayicisinda calisirdi). html.escape()
    # ZORUNLU.
    breakdown = stats.get("acquisition_breakdown_30d") or []
    if breakdown:
        rows_html = "".join(
            f"<tr><td>{html.escape(str(row['source']))}</td>"
            f"<td class='num'>{row['count']}</td></tr>"
            for row in breakdown
        )
        breakdown_html = f"""
        <h2>Son 30 gün - kaynağa göre yeni kullanıcı</h2>
        <table class="src-table">
          <thead><tr><th>Kaynak (?src=)</th><th class="num">Yeni kullanıcı</th></tr></thead>
          <tbody>{rows_html}</tbody>
        </table>"""
    else:
        breakdown_html = ""

    return f"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Aura - Panel</title>
<style>
  :root {{ color-scheme: dark; }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 40px 20px;
    background: #0A0A1A;
    background-image: linear-gradient(180deg, #0D0B2A 0%, #0A0A1A 100%);
    color: #EDEAF7;
    font-family: -apple-system, "Segoe UI", sans-serif;
  }}
  h1 {{
    font-size: 1.4rem; font-weight: 600; margin: 0 0 4px;
    display: flex; align-items: center; gap: 10px;
  }}
  h2 {{ font-size: 1rem; font-weight: 600; margin: 36px 0 14px; color: #EDEAF7; }}
  .dot {{ width: 8px; height: 8px; border-radius: 50%; background: #00E676; display: inline-block; }}
  .subtitle {{ color: #8A84A8; font-size: 0.85rem; margin-bottom: 32px; }}
  .grid {{
    display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
    gap: 16px; max-width: 1000px;
  }}
  .card {{
    background: #12122A; border: 1px solid #2A2A4A; border-radius: 14px;
    padding: 20px;
  }}
  .card-label {{ font-size: 0.78rem; color: #8A84A8; margin-bottom: 8px; }}
  .card-value {{ font-size: 1.9rem; font-weight: 600; color: #FFFFFF; font-variant-numeric: tabular-nums; }}
  .card-sub {{ font-size: 0.75rem; color: #6C63FF; margin-top: 4px; }}
  .refresh {{ color: #8A84A8; font-size: 0.75rem; margin-top: 32px; }}
  .src-table {{
    border-collapse: collapse; max-width: 500px; width: 100%;
    background: #12122A; border: 1px solid #2A2A4A; border-radius: 14px; overflow: hidden;
  }}
  .src-table th, .src-table td {{ text-align: left; padding: 10px 16px; font-size: 0.85rem; }}
  .src-table th {{ color: #8A84A8; font-weight: 500; border-bottom: 1px solid #2A2A4A; }}
  .src-table td {{ border-bottom: 1px solid #1E1E3A; }}
  .src-table .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
</style>
</head>
<body>
  <h1><span class="dot"></span>Aura Panel</h1>
  <div class="subtitle">Toplu istatistikler - tek kullanıcı verisi içermez</div>
  <div class="grid">{cards_html}</div>
  {breakdown_html}
  <div class="refresh">Sayfayı yenileyerek güncel veriyi görebilirsin.</div>
</body>
</html>"""


@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(key: Optional[str] = None):
    _check_admin_key(key)
    stats = database.get_admin_stats()
    return _render_admin_dashboard(stats)
