import os
import re
import secrets
import time
import httpx
import aura_brain
import aura_memory
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
LIMIT_REACHED_REPLY = "Bugünkü ücretsiz mesaj hakkın doldu (30/30 mesaj). Yarın sıfırlanacak."

# bkz. aura_brain.py'deki ayni degisiklik - generate_content() zaman
# asimi olmadan sonsuza kadar asili kalabiliyordu, production'da
# dogrulandi.
client = genai.Client(
    api_key=api_key,
    http_options=types.HttpOptions(timeout=12000),
)
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


MOOD_KEYWORDS = {
    "mutlu": ["mutlu", "harika", "super", "keyifli", "sevindim"],
    "uzgun": ["uzgun", "kotu", "berbat", "canim sikkin", "moralim bozuk"],
    "yorgun": ["yorgun", "bitkinim", "halsiz", "uykum var"],
    "stresli": ["stresli", "kaygili", "endiseli", "gergin", "sinirliyim"],
    "enerjik": ["enerjik", "heyecanliyim", "motiveyim", "haziriyim"],
}


def detect_mood(text: str) -> str | None:
    lowered = text.lower()
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
_CRISIS_KEYWORDS = [
    "intihar", "kendime zarar", "kendimi oldur", "yasamak istemiyorum",
    "olmek istiyorum", "yasamaya deger", "hayatima son", "bitirmek istiyorum",
    "artik dayanamiyorum", "yasayasim yok", "olsem daha iyi",
]


def _is_crisis_message(text: str) -> bool:
    lowered = text.lower()
    return any(kw in lowered for kw in _CRISIS_KEYWORDS)



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

class TTSRequest(BaseModel):
    text: str = Field(max_length=2000)
    voice: str = "female"

class AnalyzeRequest(BaseModel):
    # ~15MB base64 - tipik bir fotografi rahatca kapsar, sinirsizi engeller.
    image_base64: str = Field(max_length=15_000_000)
    # GECE DENETIMI BULGUSU: mime_type dogrulamasizdi, dogrudan Gemini'ye
    # gecilen types.Blob'a gidiyordu - hem anlamsiz/kotu niyetli bir deger
    # gonderilebiliyordu hem de bu alanin kendine ait bir uzunluk siniri
    # yoktu (image_base64 disinda). Sadece fiilen desteklenen goruntu
    # turlerine sabitlendi.
    mime_type: Literal["image/jpeg", "image/png", "image/webp"] = "image/jpeg"

# GECE DENETIMI BULGUSU: history onceden list[dict] idi - liste UZUNLUGU
# sinirliydi (max_length=100) ama HER OGENIN kendi icerigi (ozellikle
# 'text') sinirsizdi - client 100 oge x birer MB gonderip tek bir
# istekte Gemini'ye onlarca MB baglam yollatabilirdi (usage sayaci yine
# de sadece 1 hak tuketirdi). Tipli bir alt model, hem boyutu hem
# 'role' degerini (rastgele string yerine sadece iki gecerli deger)
# sinirliyor.
class StoryHistoryItem(BaseModel):
    role: Literal["user", "assistant"] = "user"
    text: str = Field(default="", max_length=4000)

class StoryRequest(BaseModel):
    action: str = Field(default="", max_length=2000)
    history: list[StoryHistoryItem] = Field(default=[], max_length=100)

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

def _safe_user(user: dict) -> dict:
    return {k: v for k, v in user.items() if k != "password_hash"}


@app.get("/")
def root():
    return {"status": "Aura backend calisiyor", "version": "3.1.0"}


@app.post("/api/auth/register")
def register(req: RegisterRequest):
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Sifre en az 6 karakter olmali.")
    user = database.create_user(
        req.email, req.password, req.name, is_anonymous=req.is_anonymous_bootstrap
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


@app.get("/api/history")
def get_history(authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    return database.get_messages(user["id"])


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


@app.post("/api/chat")
def chat(request: ChatRequest, authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    # GECE DENETIMI BULGUSU: mood_tracking_enabled kaydediliyordu ama
    # HICBIR YERDE okunmuyordu - kullanici bu ayari kapatsa bile ruh
    # hali izlemeye devam ediliyordu (weather_enabled'in aksine, o
    # gercekten kontrol ediliyor - bkz. aura_lifestyle.py).
    if user.get("mood_tracking_enabled", 1):
        mood = detect_mood(request.message)
        if mood:
            database.add_mood(user["id"], mood, context=request.message[:100])
    user_message_id = database.add_message(user["id"], "user", request.message)

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
    is_crisis = _is_crisis_message(request.message)
    if (
        not is_crisis
        and user.get("tier") != "pro"
        and not database.check_and_increment_message_usage(
            user["id"], LIMIT_DAILY_MESSAGES
        )
    ):
        return {"reply": LIMIT_REACHED_REPLY, "limit_reached": True}

    aura_brain.extract_memory_candidate(user["id"], request.message, user_message_id)
    # Ton dropdown'lari kaldirildi - Aura kendi uslubunu buradan ogreniyor.
    # extract_style_signals hicbir API cagrisi yapmiyor (saf anahtar
    # kelime taramasi), o yuzden burada ek gecikme/maliyet yok.
    database.update_style_vector(user["id"], aura_brain.extract_style_signals(request.message))
    past_messages = database.get_messages(user["id"])
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
    database.add_message(user["id"], "assistant", reply_text)
    return {"reply": reply_text}


@app.post("/api/chat/stream")
def chat_stream(request: ChatRequest, authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    # GECE DENETIMI BULGUSU: mood_tracking_enabled kaydediliyordu ama
    # HICBIR YERDE okunmuyordu - kullanici bu ayari kapatsa bile ruh
    # hali izlemeye devam ediliyordu (weather_enabled'in aksine, o
    # gercekten kontrol ediliyor - bkz. aura_lifestyle.py).
    if user.get("mood_tracking_enabled", 1):
        mood = detect_mood(request.message)
        if mood:
            database.add_mood(user["id"], mood, context=request.message[:100])
    message_id = database.add_message(
    user["id"],
    "user",
    request.message
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
    past_messages = database.get_messages(user["id"])
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
                database.add_message(user["id"], "assistant", full)

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
        r = httpx.post(
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
    try:
        image_bytes = base64.b64decode(request.image_base64)
        prompt = (
            "Bu fotografi iki katmanda analiz et ve Turkce yanit ver:\n\n"
            "1. NESNEL ANALIZ: Fotografta ne goruyorsun?\n\n"
            "2. DUYGUSAL YORUM: Bu fotografin atmosferi ve ruh hali ne?\n\n"
            "Dogal, akici Aura uslubunda yaz. Paragraf olarak yaz."
        )
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
                        types.Part(inline_data=types.Blob(mime_type=request.mime_type, data=image_bytes)),
                        types.Part(text=prompt),
                    ],
                )
            ],
        )
        analysis_text = response.text
        # BULUNDU (2026-08-25, 4 AI'ya sorulan derinlemesine analiz):
        # bu analiz sonucu SADECE kullaniciya donduruluyordu, hicbir
        # yere kaydedilmiyordu - Aura ertesi gun bu fotografi hic
        # hatirlamiyordu ("hafizaya akmiyorsa teknik olarak cop").
        # Normal sohbet mesajlariyla ayni tabloya (messages) yaziyoruz -
        # boylece bir sonraki /api/chat cagrisinin gecmis baglaminda
        # bu da yer aliyor, Aura bir daha sorulunca hatirlayabiliyor.
        database.add_message(user["id"], "user", "[Bir fotoğraf paylaştı]")
        database.add_message(user["id"], "assistant", analysis_text)
        return {"analysis": analysis_text}
    except Exception as e:
        # Ham exception mesaji (potansiyel ic yapilandirma bilgisi
        # icerebilir) artik istemciye sizdirilmiyor - detay sadece
        # sunucu logunda kaliyor.
        print(f"ANALYZE ERROR: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Fotoğraf analiz edilemedi.")


@app.post("/api/story")
def story(request: StoryRequest, authorization: Optional[str] = Header(None)):
    user = get_current_user(authorization)
    # GUVENLIK TARAMASI BULGUSU: hikaye modu da HICBIR gunluk limite tabi
    # degildi, ustelik client'in gonderdigi 'history' listesi sinirsiz
    # buyuklukte olabiliyordu (her cagrida Gemini'ye tekrar gonderiliyor).
    if user.get("tier") != "pro" and not database.check_and_increment_message_usage(
        user["id"], LIMIT_DAILY_MESSAGES
    ):
        raise HTTPException(status_code=429, detail=LIMIT_REACHED_REPLY)
    system = (
        "Sen Aura'sin, yetenekli bir hikaye anlaticinsin. "
        "Kullanici ile interaktif hikaye yaratiyorsunuz. "
        "Her yanit 2-4 paragraf, atmosfer yogun, dil akici olmali. "
        "Hikaye Turkce. Her bolumun sonunda kullaniciyi yonlendirmeye davet et. "
        "Kahraman sen olsun - ikinci sahis anlati."
    )
    try:
        if not request.history and not request.action:
            prompt = "Gizemli, surukleyici bir sahneyle bir hikaye baslat. Ikinci sahis anlatimiyla yaz."
            contents = [types.Content(role="user", parts=[types.Part(text=prompt)])]
        else:
            contents = []
            # Client'in gonderdigi history sinirsiz buyuklukte olabilirdi -
            # son MAX_HISTORY_MESSAGES kadarina kirpiliyor (diger tum
            # gecmis kullanimlarindaki desenle tutarli).
            for msg in request.history[-MAX_HISTORY_MESSAGES:]:
                role = "model" if msg.role == "assistant" else "user"
                contents.append(types.Content(role=role, parts=[types.Part(text=msg.text)]))
            if request.action:
                contents.append(types.Content(role="user", parts=[types.Part(text=request.action)]))
        response = client.models.generate_content(
            model=aura_brain.MODEL_NAME,
            contents=contents,
            config=types.GenerateContentConfig(system_instruction=system),
        )
        return {"continuation": response.text}
    except Exception as e:
        print(f"STORY ERROR: {type(e).__name__}: {e}")
        raise HTTPException(status_code=500, detail="Hikaye devam ettirilemedi.")


# Sosyal katman (arkadas + story feed) BILEREK kaldirildi (2026-08-25):
# hem bagimsiz 4 farkli AI analizi hem kendi kod taramamiz ayni sonuca
# vardi - bu ekranlar zaten uygulamadan hicbir yerden erisilemiyordu
# (nav baglantisi yoktu), ve kisisel/mahrem bir asistan urununde sosyal
# medya tarzi bir "feed" konsepti deger onerisiyle celisiyor. Tek
# gelistiricinin kaynaklari cekirdege (hafiza/proaktiflik) gitmeli.
# Eski route'lar: POST /api/stories, GET /api/stories/feed,
# POST /api/friends/request, POST /api/friends/{id}/accept,
# GET /api/friends, GET /api/friends/requests - git gecmisinde duruyor.


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
    ]
    cards_html = "".join(
        f"""<div class="card">
              <div class="card-label">{label}</div>
              <div class="card-value">{value}</div>
              {f'<div class="card-sub">{sub}</div>' if sub else ''}
            </div>"""
        for label, value, sub in cards
    )
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
</style>
</head>
<body>
  <h1><span class="dot"></span>Aura Panel</h1>
  <div class="subtitle">Toplu istatistikler - tek kullanıcı verisi içermez</div>
  <div class="grid">{cards_html}</div>
  <div class="refresh">Sayfayı yenileyerek güncel veriyi görebilirsin.</div>
</body>
</html>"""


@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(key: Optional[str] = None):
    _check_admin_key(key)
    stats = database.get_admin_stats()
    return _render_admin_dashboard(stats)
