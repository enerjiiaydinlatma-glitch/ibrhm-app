import sqlite3
import json
import hashlib
import secrets
import bcrypt
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# DB_DIR ortam degiskeni verilirse (ornek: Railway'de kalici disk
# baglantisi /data) veritabani oraya yazilir - aksi halde eskisi gibi
# proje klasorune (yerel gelistirme icin degismiyor).
DB_DIR = os.getenv("DB_DIR", BASE_DIR)
DB_PATH = os.path.join(DB_DIR, "aura.db")

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Kod sagligi taramasinda bulunan bir baska risk: hicbir yerde busy
    # timeout ayarlanmamisti. Varsayilan (0) ile, ayni anda iki istek ayni
    # satira yazmaya calisirsa SQLite ANINDA "database is locked" hatasi
    # firlatiyordu. 5 saniyelik bir bekleme penceresi, kisa sureli
    # cakismalarin sessizce (retry ile) cozulmesini saglar.
    conn.execute("PRAGMA busy_timeout = 5000")
    # GECE DENETIMI BULGUSU: varsayilan rollback-journal modunda TEK bir
    # yazici TUM okuyuculari kilitliyor - yogun trafikte "database is
    # locked" hatalarinin busy_timeout'u bile asma riski vardi. WAL
    # modunda okuyucular yazma sirasinda bloklanmiyor (SQLite'in kendi
    # onerdigi, es zamanlilik icin standart ayar). Bu PRAGMA veritabani
    # DOSYASININ kendisinde kalici olarak saklanir - bir kez calismasi
    # yeterli, ama idempotent oldugu icin her baglantida calistirmak
    # zararsiz.
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def db_cursor(commit: bool = False):
    """
    Tum DB fonksiyonlarinin ortak baglanti noktasi. KOD SAGLIGI
    TARAMASINDA BULUNDU: daha once her fonksiyon kendi basina
    `conn = get_db(); ...; conn.close()` deseniyle yaziliyordu -
    aralarinda bir exception olusursa (sqlite3.OperationalError,
    IntegrityError, tip hatasi vb.) `conn.close()` satirina hic
    ulasilmiyordu, baglanti acik kaliyordu. Yogun trafik + ara sira hata
    altinda bu, zamanla acik dosya tanimlayicisi/baglanti birikmesine
    yol acabilirdi. Artik try/finally ile HER durumda (basari ya da
    hata) baglanti kapatiliyor. `commit=True` verilirse, blok hatasiz
    bitince (normal return dahil) otomatik commit yapilir.
    """
    conn = get_db()
    try:
        yield conn
        if commit:
            conn.commit()
    finally:
        conn.close()


def init_db():
    with db_cursor(commit=True) as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name TEXT DEFAULT '',
                warmth TEXT DEFAULT 'sicak',
                formality TEXT DEFAULT 'samimi',
                humor TEXT DEFAULT 'orta',
                directness TEXT DEFAULT 'dengeli',
                notes TEXT DEFAULT '',
                location_lat REAL,
                location_lon REAL,
                location_city TEXT,
                weather_enabled INTEGER DEFAULT 1,
                activity_enabled INTEGER DEFAULT 1,
                mood_tracking_enabled INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Mevcut (zaten var olan) users tablosuna sonradan eklenen sutunlar.
        # SQLite "ALTER TABLE ... ADD COLUMN IF NOT EXISTS" desteklemiyor,
        # bu yuzden dene/basarisiz-olursa-yoksay deseni kullaniliyor - tablo
        # daha once olusturulmus (CREATE IF NOT EXISTS calismadi) durumlarda
        # da sutunlarin var oldugundan emin olunuyor.
        for migration in (
            "ALTER TABLE users ADD COLUMN tier TEXT DEFAULT 'free'",
            "ALTER TABLE users ADD COLUMN is_anonymous INTEGER DEFAULT 1",
            "ALTER TABLE users ADD COLUMN daily_message_count INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN daily_voice_seconds INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN usage_date TEXT DEFAULT ''",
            "ALTER TABLE users ADD COLUMN daily_tts_chars INTEGER DEFAULT 0",
            # Ton ayarlari (warmth/formality/humor/directness) artik elle
            # secilen dropdown degil - Aura kullanicinin konusma tarzindan
            # bu 4 ekseni kendi kendine ogreniyor (0.0-1.0 arasi, EMA ile
            # yavasca guncellenen bir "stil vektoru"). Eski TEXT kolonlar
            # DURUYOR (geriye donuk uyumluluk + ilk tohum degeri icin).
            # BULUNDU (yerel testte): DEFAULT 0.5 verirsek, bu backfill
            # SADECE su an DB'de VAR OLAN satirlari duzeltir - migration'dan
            # SONRA (yani sunucu yeniden baslamadan) kayit olan HER YENI
            # kullanici (pratikte gelecekteki neredeyse herkes) duz notr
            # 0.5 ile kalir, oysa eski sistemde varsayilan zaten "sicak/
            # samimi" idi. Kolon varsayilanini dogrudan o eski varsayilana
            # esitliyoruz (0.85=sicak/samimi) ki her YENI INSERT otomatik
            # dogru tohumla gelsin - asagidaki UPDATE ise SADECE bu
            # migrasyondan ONCE kullanicinin BILEREK farkli bir sey
            # sectigi (ornegin 'mesafeli') satirlari duzeltmek icin var.
            "ALTER TABLE users ADD COLUMN style_warmth REAL DEFAULT 0.85",
            "ALTER TABLE users ADD COLUMN style_formality REAL DEFAULT 0.85",
            "ALTER TABLE users ADD COLUMN style_humor REAL DEFAULT 0.5",
            "ALTER TABLE users ADD COLUMN style_directness REAL DEFAULT 0.5",
            "ALTER TABLE users ADD COLUMN style_sample_count INTEGER DEFAULT 0",
            # Kod-kelime ile "gizli mod" (2026-08-26, kullanici istegi -
            # "kilitli sozler kelimeler"). secret_phrase_hash HIC acik
            # metin tutmuyor (bcrypt, sifreyle ayni desen).
            "ALTER TABLE users ADD COLUMN secret_phrase_hash TEXT",
            "ALTER TABLE users ADD COLUMN hidden_mode_active INTEGER DEFAULT 0",
            # Reklam/gorunurluk analitigi (2026-08-27, kullanici istegi -
            # gece raporunda "reklam oncesi analitik/gorunurluk eksikligi"
            # en kritik bulgu olarak isaretlenmisti, o zamandan beri
            # cozulmemisti). Serbest metin - hangi reklam/kanaldan geldigini
            # (ornek: "instagram_agustos") istemcinin ?src= URL parametresinden
            # yakalayip kayit aninda gonderdigi deger.
            "ALTER TABLE users ADD COLUMN acquisition_source TEXT DEFAULT ''",
        ):
            try:
                cursor.execute(migration)
            except sqlite3.OperationalError:
                pass  # sutun zaten var

        # Tohumlama: kullanicinin ONCEDEN elle sectigi ton (varsa) yeni
        # otomatik stil vektorunun baslangic noktasi olsun - sifirdan
        # notr (0.5) baslamasin. SADECE style_sample_count = 0 olan
        # satirlarda calisir (henuz hic gercek ogrenme olmamis) - bu
        # yuzden her init_db()'de tekrar calismasi zararsiz (idempotent):
        # bir kullanici icin ogrenme baslar baslamaz sample_count artar
        # ve bu UPDATE bir daha o satiri etkilemez.
        cursor.execute("""
            UPDATE users SET
                style_warmth = CASE warmth WHEN 'mesafeli' THEN 0.15 WHEN 'sicak' THEN 0.85 ELSE 0.5 END,
                style_formality = CASE formality WHEN 'resmi' THEN 0.15 WHEN 'samimi' THEN 0.85 ELSE 0.5 END,
                style_humor = CASE humor WHEN 'dusuk' THEN 0.15 WHEN 'yuksek' THEN 0.85 ELSE 0.5 END,
                style_directness = CASE directness WHEN 'yumusak' THEN 0.15 WHEN 'dogrudan' THEN 0.85 ELSE 0.5 END
            WHERE style_sample_count = 0
        """)

        # KENDI KENDINI INCELEME BULGUSU: is_anonymous'u dogru yazmaya
        # baslamak (create_user artik is_anonymous_bootstrap'i isliyor)
        # SADECE BUNDAN SONRAKI kayitlari kapsar - bu satir olmadan,
        # bu duzeltmeden ONCE olusmus TUM gercek hesaplar (muhtemelen
        # mevcut kullanicilarin tamami) hala is_anonymous=1 ile kalir
        # ve /api/auth/claim'in hesap-devralma korumasi ONLAR icin HALA
        # devreye girmez - tam da kapatmaya calistigimiz aciğin kendisi.
        # Anonim hesaplarin e-posta deseni sabit ve tahmin edilebilir
        # (anonymous_<stamp>@aura.local) - bu desene UYMAYAN, hala
        # is_anonymous=1 olan HER satir aslinda gercek bir kayittir, tek
        # seferlik (ama idempotent - tekrar calistirmak zararsiz) bir
        # geriye-donuk duzeltmeyle isaretliyoruz.
        cursor.execute(
            "UPDATE users SET is_anonymous = 0 "
            "WHERE is_anonymous = 1 AND email NOT LIKE 'anonymous\\_%@aura.local' ESCAPE '\\'"
        )

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token TEXT UNIQUE NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                text TEXT NOT NULL,
                emotion_detected TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        try:
            cursor.execute("ALTER TABLE messages ADD COLUMN hidden INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # sutun zaten var

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mood_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                mood TEXT NOT NULL,
                intensity INTEGER DEFAULT 5,
                context TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        # Hatirlatmalar (2026-08-26, kullanici istegi): "haftaya persembe
        # maca gidecegim, bilet almam lazim" gibi mesajlardan cikarilan,
        # GELECEKTEKI bir tarihe bagli hatirlatmalar. event_at = etkinligin
        # kendisi, remind_at = kullaniciya hatirlatilmasi gereken tarih
        # (genelde event_at'ten ONCE). delivered: istemci bunu yerel bir
        # bildirim olarak zamanladiktan/gosterdikten sonra 1 yapar - sunucu
        # tarafinda gercek bir "gonderim" yok, sadece istemcinin tekrar
        # tekrar ayni hatirlatmayi zamanlamamasi icin bir isaret.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                description TEXT NOT NULL,
                event_at TEXT NOT NULL,
                remind_at TEXT NOT NULL,
                delivered INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS friends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                friend_user_id INTEGER,
                friend_name TEXT NOT NULL,
                friend_phone TEXT,
                friend_email TEXT,
                aura_shared INTEGER DEFAULT 0,
                closeness_level INTEGER DEFAULT 5,
                status TEXT DEFAULT 'pending',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        # GUVENLIK TARAMASI BULGUSU: send_friend_request'teki INSERT OR
        # IGNORE hicbir seyi gercekten "ignore" etmiyordu - (user_id,
        # friend_user_id) uzerinde UNIQUE kisitlama olmadigi icin ayni
        # istek tekrar tekrar gonderilince sinirsiz coklanan satir
        # olusuyordu (DB sismesi + IDOR spam yuzeyi). Mevcut veride
        # coklanan satir olmadigi dogrulanip guvenle eklendi.
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_friends_unique_pair
            ON friends(user_id, friend_user_id)
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                content TEXT NOT NULL,
                image_url TEXT,
                visible_to TEXT DEFAULT 'friends',
                expires_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS location_gifts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER NOT NULL,
                recipient_id INTEGER,
                recipient_name TEXT,
                gift_type TEXT,
                gift_message TEXT,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                location_name TEXT,
                is_claimed INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                claimed_at TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                pattern_type TEXT,
                pattern_data TEXT,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # GECE DENETIMI BULGUSU: init_db() suraya kadar sadece
        # idx_friends_unique_pair'i olusturuyordu - en cok buyuyecek ve
        # en sik WHERE user_id=? ile sorgulanacak tablolarin (messages,
        # mood_logs, sessions, user_patterns) HICBIR indeksi yoktu. Az
        # sayida kullanicida fark etmez ama veri buyudukce her sorgu
        # tam tablo taramasina donerdi. Ekleme maliyeti dusuk, simdiden
        # eklemek gelecekteki bir performans sorununu onceden onluyor.
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_user_ts "
            "ON messages(user_id, timestamp DESC)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_mood_logs_user_ts "
            "ON mood_logs(user_id, timestamp DESC)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_user "
            "ON sessions(user_id)"
        )
        # sessions.token zaten UNIQUE NOT NULL - SQLite bunun icin otomatik
        # bir indeks olusturuyor, ayrica bir tane daha eklemek gereksiz.
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_user_patterns_user "
            "ON user_patterns(user_id)"
        )


# --- AUTH ---

def hash_password(password: str) -> str:
    # Kod sagligi taramasinda bulundu: onceki hali salt'siz, tek turlu
    # SHA-256'ydi - DB sizarsa hizli/GPU brute-force'a acikti. bcrypt
    # (salt'li, yavas, ayarlanabilir maliyetli) kullaniyoruz artik.
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _is_legacy_sha256_hash(stored_hash: str) -> bool:
    """Eski (bcrypt oncesi) hash'ler duz 64 karakterlik hex SHA-256'ydi."""
    return len(stored_hash) == 64 and all(c in "0123456789abcdef" for c in stored_hash.lower())


def _verify_password(password: str, stored_hash: str) -> bool:
    if _is_legacy_sha256_hash(stored_hash):
        return hashlib.sha256(password.encode()).hexdigest() == stored_hash
    try:
        return bcrypt.checkpw(password.encode(), stored_hash.encode())
    except (ValueError, TypeError):
        return False


def create_user(
    email: str, password: str, name: str = "", is_anonymous: bool = False,
    acquisition_source: str = "",
) -> Optional[dict]:
    # GECE DENETIMI BULGUSU: is_anonymous ONCEDEN hic verilmiyordu, bu
    # yuzden semanin varsayilani (1) her zaman gecerli oluyordu - GERCEK
    # kayitlar bile "anonim/henuz claim edilmemis" sayiliyordu, ve
    # /api/auth/claim'deki "zaten claim edilmis hesabi tekrar claim
    # etmeyi engelle" korumasi (main.py) hicbir gercek kayit icin
    # devreye girmiyordu. Cagiran taraf (main.py) artik istemcinin
    # ACIKCA bildirdigi is_anonymous_bootstrap degerini buraya tasiyor.
    try:
        with db_cursor(commit=True) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (email, password_hash, name, is_anonymous, acquisition_source) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    email.lower().strip(), hash_password(password), name, int(is_anonymous),
                    acquisition_source.strip()[:100],
                )
            )
            user_id = cursor.lastrowid
        return get_user(user_id)
    except sqlite3.IntegrityError:
        return None


def authenticate_user(email: str, password: str) -> Optional[dict]:
    # bcrypt her cagrida farkli bir salt urettigi icin artik SQL
    # WHERE'de dogrudan karsilastirma yapilamiyor - once email'e gore
    # kullaniciyi cekip, sifreyi Python tarafinda dogruluyoruz.
    with db_cursor(commit=True) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email.lower().strip(),))
        row = cursor.fetchone()
        if not row:
            return None

        user = dict(row)
        if not _verify_password(password, user["password_hash"]):
            return None

        # Sessiz migrasyon: eski SHA-256 hash basariyla dogrulandiysa, simdi
        # bcrypt ile yeniden yazip guvenligi kullanici fark etmeden artir.
        if _is_legacy_sha256_hash(user["password_hash"]):
            cursor.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (hash_password(password), user["id"]),
            )

        return user


def create_session(user_id: int, days: int = 30) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(days=days)
    with db_cursor(commit=True) as conn:
        conn.execute(
            "INSERT INTO sessions (user_id, token, expires_at) VALUES (?, ?, ?)",
            (user_id, token, expires_at)
        )
    return token


def get_user_by_token(token: str) -> Optional[dict]:
    with db_cursor() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT u.* FROM users u
               JOIN sessions s ON u.id = s.user_id
               WHERE s.token = ? AND s.expires_at > datetime('now')""",
            (token,)
        )
        row = cursor.fetchone()
    return dict(row) if row else None


def delete_session(token: str):
    with db_cursor(commit=True) as conn:
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))


def enforce_single_session(user_id: int):
    """
    Bu kullaniciya ait TUM oturumlari (diger cihazlar dahil) siler.
    'free' tier kullanicilar icin yeni bir session olusturulmadan HEMEN
    ONCE cagrilir - boylece yeni cihazdan giris, eski cihazin oturumunu
    dusurur (ayni anda tek cihaz kurali). 'pro' tier icin cagrilmaz.
    """
    with db_cursor(commit=True) as conn:
        conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))


def revoke_other_sessions(user_id: int, keep_token: str):
    """
    GECE DENETIMI BULGUSU: claim_account (kimlik degistirme) daha once
    HICBIR oturumu iptal etmiyordu - sizmis/calinmis eski bir token,
    kullanici sifresini/emailini degistirdikten SONRA bile calismaya
    devam ederdi (standart "sifreni degistir, saldirgan disari atilsin"
    beklentisinin tam tersi). Bu, DEGISTIRMEYI yapan cagrida kullanilan
    token (keep_token) haric TUMUNU siler - kullanici kendi cihazindan
    atilmaz, ama diger tum eski oturumlar gecersiz olur.
    """
    with db_cursor(commit=True) as conn:
        conn.execute(
            "DELETE FROM sessions WHERE user_id = ? AND token != ?",
            (user_id, keep_token),
        )


def claim_account(user_id: int, email: str, password: str) -> bool:
    """
    Anonim (rastgele email/sifreyle olusturulmus) bir hesabi, kullanicinin
    KENDI belirledigi gercek email/sifreyle gercek, hatirlanabilir bir
    hesaba cevirir. YENI bir kullanici satiri OLUSTURMAZ - ayni satir
    guncellenir, boylece tum gecmis/hafiza korunur. Email baskasina
    aitse (UNIQUE ihlali) False doner.
    """
    try:
        with db_cursor(commit=True) as conn:
            conn.execute(
                "UPDATE users SET email = ?, password_hash = ?, is_anonymous = 0 WHERE id = ?",
                (email.lower().strip(), hash_password(password), user_id),
            )
        return True
    except sqlite3.IntegrityError:
        return False


# --- KULLANIM LIMITI (free tier) ---

def _today_str() -> str:
    return datetime.now().date().isoformat()


def _reset_usage_if_new_day(cursor, user_id: int, usage_date: str) -> bool:
    """
    Kaydedilen usage_date bugunden farkliysa (ya da hic yoksa),
    sayaclari sifirlar ve bugunun tarihini yazar. Sifirlama olduysa
    True doner - cagiran taraf yerel degiskenini de 0'a cekebilsin.
    """
    today = _today_str()
    if usage_date != today:
        cursor.execute(
            "UPDATE users SET daily_message_count = 0, daily_voice_seconds = 0, "
            "daily_tts_chars = 0, usage_date = ? WHERE id = ?",
            (today, user_id),
        )
        return True
    return False


def check_and_increment_message_usage(user_id: int, daily_limit: int = 30) -> bool:
    """
    Gunluk mesaj sayacini kontrol eder. Limit doluysa (ARTIRMADAN)
    False doner - cagiran taraf Gemini/Groq'u cagirmadan, kullaniciya
    "limit doldu" cevabi dondurmeli. Limit dolmadiysa sayaci 1 artirip
    True doner.

    Kod sagligi taramasinda bulundu: onceki hali "oku (SELECT), sonra
    karar ver, sonra yaz (UPDATE)" seklindeydi - tek bir atomik islem
    degildi. Ayni kullanicidan neredeyse eszamanli iki istek gelirse
    (cift tiklama, ag retry'i, iki cihaz), ikisi de ayni sayaci (orn. 29)
    okuyup ikisi de limitin dolmadigini sanip GECEBILIYORDU - gunluk
    sinir bu sekilde asilabiliyordu. Artik artis islemi TEK bir UPDATE
    sorgusunun WHERE kosuluna tasindi - SQLite yazma islemlerini
    sirayla isledigi icin (bkz. get_db()'deki busy_timeout), iki
    eszamanli istekten sadece biri `daily_message_count < daily_limit`
    kosulunu gerceklestigi anda karsilayabilir.
    """
    with db_cursor(commit=True) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT daily_message_count, usage_date FROM users WHERE id = ?",
            (user_id,),
        )
        row = cursor.fetchone()
        if not row:
            return True  # kullanici bulunamadiysa engelleme (guvenli varsayilan)

        # Gun degistiyse once sayaclari sifirla - bu adim hala oku-sonra-
        # yaz ama gun degisimi son derece nadir (kullanici basina gunde
        # bir kez) oldugu icin pratikte yarisma riski yok.
        _reset_usage_if_new_day(cursor, user_id, row["usage_date"])

        # ATOMIK artis: sadece limit altindaysa satiri guncelle. rowcount
        # > 0 ise bu istek GERCEKTEN artirmis demektir.
        cursor.execute(
            "UPDATE users SET daily_message_count = daily_message_count + 1 "
            "WHERE id = ? AND daily_message_count < ?",
            (user_id, daily_limit),
        )
        return cursor.rowcount > 0


def check_and_increment_tts_usage(user_id: int, char_count: int, daily_limit: int = 8000) -> bool:
    """
    KENDI KENDINI INCELEME BULGUSU: /api/tts once GUNLUK MESAJ sayacini
    paylasiyordu - ama istemci Aura'nin HER cevabini otomatik seslendirdigi
    icin (chat_screen.dart), bu ucretsiz kullanicinin 30 mesajlik gunluk
    hakkini fiilen 15'e dusuruyordu (her tur hem /api/chat hem /api/tts
    sayaci artiriyordu). ElevenLabs zaten KARAKTER basina ucretlendiriyor,
    o yuzden ayri, karakter-tabanli kendi bütçesi daha dogru bir sinir -
    ne sohbet hakkini paylasip yaniltici sekilde azaltiyor, ne de
    sinirsiz kaliyor. 8000 karakter ~ gunde 30 orta uzunlukta cevabı
    seslendirmeye kabaca denk (mesaj limitiyle ayni buyuklukte, ayri
    bir havuzdan).
    """
    with db_cursor(commit=True) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT daily_tts_chars, usage_date FROM users WHERE id = ?",
            (user_id,),
        )
        row = cursor.fetchone()
        if not row:
            return True  # kullanici bulunamadiysa engelleme (guvenli varsayilan)

        _reset_usage_if_new_day(cursor, user_id, row["usage_date"])

        cursor.execute(
            "UPDATE users SET daily_tts_chars = daily_tts_chars + ? "
            "WHERE id = ? AND daily_tts_chars + ? <= ?",
            (char_count, user_id, char_count, daily_limit),
        )
        return cursor.rowcount > 0


def get_voice_usage_seconds(user_id: int) -> int:
    """Gun kontrolu yapar (gerekirse sifirlar) ve mevcut gunluk sesli
    goruşme saniyesini doner."""
    with db_cursor(commit=True) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT daily_voice_seconds, usage_date FROM users WHERE id = ?",
            (user_id,),
        )
        row = cursor.fetchone()
        if not row:
            return 0

        seconds = row["daily_voice_seconds"]
        if _reset_usage_if_new_day(cursor, user_id, row["usage_date"]):
            seconds = 0

        return seconds


def add_voice_usage_seconds(user_id: int, seconds: int):
    """Bir sesli goruşme bittiginde gecen sureyi gunluk sayaca ekler."""
    if seconds <= 0:
        return
    with db_cursor(commit=True) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT usage_date FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            _reset_usage_if_new_day(cursor, user_id, row["usage_date"])
        cursor.execute(
            "UPDATE users SET daily_voice_seconds = daily_voice_seconds + ? WHERE id = ?",
            (seconds, user_id),
        )


# --- USER ---

def get_user(user_id: int) -> dict:
    with db_cursor() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
    return dict(row) if row else {}


def get_user_by_email(email: str) -> Optional[dict]:
    with db_cursor() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email.lower().strip(),))
        row = cursor.fetchone()
    return dict(row) if row else None


def update_user(user_id: int, **kwargs) -> dict:
    # NOT: warmth/formality/humor/directness KASITLI OLARAK burada degil -
    # bunlar artik elle guncellenmiyor, style_* alanlari uzerinden Aura'nin
    # kendi kendine ogrenmesiyle degisiyor (bkz. update_style_vector).
    allowed = ['name', 'notes', 'location_lat', 'location_lon', 'location_city',
               'weather_enabled', 'activity_enabled', 'mood_tracking_enabled']
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return get_user(user_id)
    set_clause = ", ".join([f"{k} = ?" for k in fields.keys()])
    values = list(fields.values()) + [user_id]
    with db_cursor(commit=True) as conn:
        conn.execute(f"UPDATE users SET {set_clause} WHERE id = ?", values)
    return get_user(user_id)


# --- OTOMATIK USLUP (STIL VEKTORU) ---
# Ton dropdown'lari kaldirildi - Aura artik kullanicinin konusma tarzindan
# 4 ekseni (warmth/formality/humor/directness) kendi kendine cikarip,
# ani tek-mesajlik sapmalarin kalici sanilmamasi icin EMA (ustel hareketli
# ortalama) ile YAVASCA guncelliyor. Degerler hep 0.0-1.0 arasinda.
STYLE_EMA_ALPHA = 0.15
STYLE_AXES = ("warmth", "formality", "humor", "directness")


def style_vector_from_user(user: dict) -> dict:
    """get_style_vector ile AYNI cikti - ama zaten elde bir 'user' satiri
    (SELECT u.* ile gelen, style_* kolonlarini ZATEN iceren) varsa YENIDEN
    DB'ye gitmez. BULUNDU (verimlilik incelemesi): build_system_instruction
    her /api/chat isteginde bu degeri ayri bir SELECT * FROM users ile
    yeniden cekiyordu - oysa cagiran taraf zaten TAM satiri elinde
    tutuyordu (get_current_user)."""
    return {
        axis: user.get(f"style_{axis}") if user.get(f"style_{axis}") is not None else 0.5
        for axis in STYLE_AXES
    } | {"sample_count": user.get("style_sample_count") or 0}


def get_style_vector(user_id: int) -> dict:
    return style_vector_from_user(get_user(user_id))


def update_style_vector(user_id: int, signals: dict) -> None:
    """signals: {"warmth": 0.85, ...} - sadece GERCEK kanit bulunan
    eksenler icerir, digerleri hic gonderilmez (o eksen degismez)."""
    signals = {k: v for k, v in signals.items() if k in STYLE_AXES and v is not None}
    if not signals:
        return
    with db_cursor(commit=True) as conn:
        cursor = conn.cursor()
        cols = ", ".join(f"style_{axis}" for axis in signals)
        cursor.execute(f"SELECT {cols} FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        if not row:
            return
        current = dict(row)
        updates = {}
        for axis, observed in signals.items():
            col = f"style_{axis}"
            old = current[col] if current[col] is not None else 0.5
            new_value = old + STYLE_EMA_ALPHA * (observed - old)
            updates[col] = max(0.0, min(1.0, new_value))
        set_clause = ", ".join(f"{k} = ?" for k in updates) + ", style_sample_count = style_sample_count + 1"
        values = list(updates.values()) + [user_id]
        cursor.execute(f"UPDATE users SET {set_clause} WHERE id = ?", values)


# --- MESSAGES ---

def add_message(user_id: int, role: str, text: str, emotion: Optional[str] = None, hidden: bool = False):
    with db_cursor(commit=True) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO messages (user_id, role, text, emotion_detected, hidden) VALUES (?, ?, ?, ?, ?)",
            (user_id, role, text, emotion, int(hidden))
        )
        message_id = cursor.lastrowid
    return message_id


def get_messages(user_id: int, limit: int = 100, include_hidden: bool = True) -> List[dict]:
    # NOT: include_hidden VARSAYILAN OLARAK True - bu fonksiyon AURA'NIN
    # KENDI SOHBET BAGLAMINI (AI'ya giden gecmis) olusturmak icin de
    # kullaniliyor (main.py /api/chat) - gizli mod aktifken bile Aura
    # sohbetin baglamini kaybetmemeli. SADECE kullaniciya gorunen
    # /api/history gibi yerlerde include_hidden=False acikca gecilir.
    with db_cursor() as conn:
        cursor = conn.cursor()
        # KRITIK DUZELTME: onceki hali "ORDER BY timestamp LIMIT ?" idi -
        # DESC OLMADAN, yani her zaman kullanicinin en ESKI N mesajini
        # donduruyordu. Kullanici toplam mesaj sayisi limit'i (100) gectiginde
        # (free tier ile ~2 gunde oluyor), sohbet baglami/AI'ya giden gecmis
        # sonsuza dek o eski mesajlarda donup kaliyordu - hicbir hata/log
        # olmadan (kod sagligi taramasinda bulundu). Simdi en SON N mesaj
        # DESC ile cekilip, cagiran taraflarin bekledigi kronolojik (eskiden
        # yeniye) sira icin Python tarafinda ters cevriliyor. `id DESC` ikinci
        # siralama olcutu, ayni saniyeye denk gelen mesajlarin ekleniş sirasini
        # korur (timestamp tek basina ayirt edici olmayabilir).
        if include_hidden:
            cursor.execute(
                "SELECT * FROM messages WHERE user_id = ? ORDER BY timestamp DESC, id DESC LIMIT ?",
                (user_id, limit)
            )
        else:
            cursor.execute(
                "SELECT * FROM messages WHERE user_id = ? AND hidden = 0 "
                "ORDER BY timestamp DESC, id DESC LIMIT ?",
                (user_id, limit)
            )
        rows = cursor.fetchall()
    return [dict(row) for row in reversed(rows)]


def get_hidden_messages(user_id: int, limit: int = 200) -> List[dict]:
    with db_cursor() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM messages WHERE user_id = ? AND hidden = 1 "
            "ORDER BY timestamp DESC, id DESC LIMIT ?",
            (user_id, limit)
        )
        rows = cursor.fetchall()
    return [dict(row) for row in reversed(rows)]


def clear_messages(user_id: int):
    with db_cursor(commit=True) as conn:
        conn.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))


# --- KOD-KELIME ILE GIZLI MOD ---
# Kullanici istegi (2026-08-26): "kilitli sozler kelimeler" - sohbette
# kendi belirledigi bir cumleyi TEK BASINA bir mesaj olarak gonderince
# Aura fark ettirmeden gizli moda gecer/cikar, o andan itibarenki
# konusma normal gecmiste GORUNMEZ (PIN/biyometrik ile acilan ayri bir
# ekranda goruntulenir). Kasitli olarak SUBSTRING eslesmesi degil, TAM
# mesaj eslesmesi ariyoruz - hem yanlislikla tetiklenmeyi onler hem de
# ifadeyi acik metin yerine bcrypt hash olarak saklayabilmemizi saglar
# (parolayla ayni guvenlik duzeyi).

def fold_turkish_i(text: str) -> str:
    """
    KOD INCELEMESI BULGUSU (2026-08-27, tam-yolculuk entegrasyon testinde
    bulundu): Python'un .lower()'i Turkce'ye OZGU I/i/İ/ı ayrimini
    locale-farkinda yapmiyor - "yıldız" (Turkce dotless ı, U+0131)
    .lower() sonrasinda bile "yildiz" (ASCII i, U+0069) ile FARKLI kalıyor.
    Bu, aura_memory.py'de memory_key normalizasyonu icin daha once bulunup
    duzeltilen AYNI sinif hata (bkz. o dosyadaki "İ/I/ı ozel harfleri"
    yorumu) - burada GENEL bir yardimci fonksiyona cikarildi ki
    GUVENLIK-KRITIK tum karsilastirma noktalari (gizli mod kod cumlesi,
    main.py'deki kriz/ruh-hali anahtar kelime tespiti) AYNI korumayi
    paylassin. Once Turkce I-varyantlarini TEK bir kanonik forma
    katliyoruz, SONRA standart .lower() guvenle uygulanabiliyor.
    """
    return text.replace("İ", "i").replace("I", "i").replace("ı", "i")


def _normalize_secret_phrase(phrase: str) -> str:
    # SOMUT KANIT: "yildiz tozu" (ASCII i) ile kullanicinin klavye/IME/
    # ses-transkripsiyonuyla yazabilecegi "yıldız tozu" (Turkce dotless
    # ı) .lower() sonrasi bile FARKLI kalıyordu - kullanici kendi kod
    # cumlesini "dogru" yazdigini dusunse bile gizli mod SESSIZCE
    # acilmayabilirdi (kritik bir gizlilik basarisizligi). bkz.
    # fold_turkish_i.
    return fold_turkish_i(phrase).strip().lower()


def set_secret_phrase(user_id: int, phrase: str) -> None:
    normalized = _normalize_secret_phrase(phrase)
    hashed = bcrypt.hashpw(normalized.encode(), bcrypt.gensalt()).decode()
    with db_cursor(commit=True) as conn:
        conn.execute(
            "UPDATE users SET secret_phrase_hash = ?, hidden_mode_active = 0 WHERE id = ?",
            (hashed, user_id)
        )


def clear_secret_phrase(user_id: int) -> None:
    with db_cursor(commit=True) as conn:
        conn.execute(
            "UPDATE users SET secret_phrase_hash = NULL, hidden_mode_active = 0 WHERE id = ?",
            (user_id,)
        )


def has_secret_phrase(user_id: int) -> bool:
    user = get_user(user_id)
    return bool(user.get("secret_phrase_hash"))


def is_hidden_mode_active(user_id: int, user: Optional[dict] = None) -> bool:
    # BULUNDU (verimlilik incelemesi): cagiran taraf (main.py /api/chat)
    # zaten TAM kullanici satirini elinde tutuyordu (get_current_user) -
    # onu opsiyonel olarak kabul edip gereksiz bir SELECT * FROM users
    # daha yapmaktan kaciniyoruz. Verilmezse eskisi gibi DB'den okur.
    if user is None:
        user = get_user(user_id)
    return bool(user.get("hidden_mode_active"))


def check_and_toggle_secret_phrase(user_id: int, message_text: str, user: Optional[dict] = None) -> bool:
    """Mesaj TAM OLARAK kullanicinin kod cumlesiyle eslesirse gizli modu
    ac/kapa ve True dondur (eslesme oldu = bu mesaj asla normal gecmiste
    gorunmemeli). Eslesme yoksa (ya da kod cumlesi hic belirlenmemisse)
    HICBIR SEYI degistirmeden False doner."""
    if user is None:
        user = get_user(user_id)
    stored_hash = user.get("secret_phrase_hash")
    if not stored_hash:
        return False
    # Ucuz on-eleme: bir "kod cumlesi" kisa olmali - bcrypt.checkpw
    # (bilerek YAVAS) her mesajda calismasin diye once uzunluk kontrolu.
    normalized = _normalize_secret_phrase(message_text)
    if len(normalized) > 80:
        return False
    # KOD INCELEMESI BULGUSU (2026-08-27, sesli yedek modu eklenince):
    # kod cumlesi TIPIK OLARAK yazarak (noktalamasiz) belirleniyor, ama
    # sesli yedek modda (Groq Whisper) ayni cumle soylenince transkript
    # sona bir nokta/virgul EKLEYEBILIYOR - bcrypt tam-metin karsilastirmasi
    # bu farkla sessizce basarisiz olup gizli modun hic acilmamasina (ya da
    # gizli bir mesajin yanlislikla GORUNUR kaydedilmesine) yol acabilirdi.
    # set_secret_phrase() cumleyi degistirmeden (sadece strip+lower) hash'liyor,
    # o yuzden STORED HASH'e dokunmadan, gelen ADAY metni sondaki yaygin
    # noktalama isaretlerinden ARINDIRILMIS haliyle de deniyoruz - orijinal
    # (noktalamali) hali zaten ilk once denenir, hicbir davranis kaybolmaz.
    #
    # GERIYE-UYUMLULUK DUZELTMESI (aynı gun, ilk fix'ten hemen sonra kendi
    # kendimi inceleyip buldum): _normalize_secret_phrase'e Turkce I-varyant
    # katlama (İ/I/ı -> i) EKLENINCE, bu katlamayi DEGISTIREN bir karakter
    # ICEREN kod cumlesini DAHA ONCE belirlemis kullanicilarin STORED HASH'i
    # ARTIK ESKI (katlanmamis) normalizasyonla hesaplanmis durumda kaliyor -
    # yeni normalizasyonla asla eslesmezdi (somut ornek: "yıldız" ESKI
    # normalizasyonda "yıldız" olarak kaliyordu/hash'lendi, YENI normalizasyon
    # "yildiz"a katliyor - ayni metin bile artik eski hash'iyle eslesmezdi).
    # Cozum: LEGACY (fold'suz) normalizasyonu da ayri bir aday olarak
    # deniyoruz - boylece fold'dan ONCE belirlenmis kod cumleleri CALISMAYA
    # DEVAM EDIYOR, fold SADECE YENI eslesme ihtimallerini EKLIYOR.
    legacy_normalized = message_text.strip().lower()
    candidates = [normalized]
    if legacy_normalized != normalized:
        candidates.append(legacy_normalized)
    for base in list(candidates):
        stripped_punct = base.rstrip(".,!?;:…\"'")
        if stripped_punct and stripped_punct != base and stripped_punct not in candidates:
            candidates.append(stripped_punct)
    matched = False
    for candidate in candidates:
        try:
            if bcrypt.checkpw(candidate.encode(), stored_hash.encode()):
                matched = True
                break
        except (ValueError, TypeError):
            return False
    if not matched:
        return False
    with db_cursor(commit=True) as conn:
        conn.execute(
            "UPDATE users SET hidden_mode_active = CASE hidden_mode_active WHEN 1 THEN 0 ELSE 1 END "
            "WHERE id = ?",
            (user_id,)
        )
    return True


# --- HATIRLATMALAR ---

def add_reminder(user_id: int, description: str, event_at: str, remind_at: str) -> int:
    with db_cursor(commit=True) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO reminders (user_id, description, event_at, remind_at) "
            "VALUES (?, ?, ?, ?)",
            (user_id, description, event_at, remind_at)
        )
        return cursor.lastrowid


def has_active_reminder_on_date(user_id: int, event_at: str) -> bool:
    """BULUNDU (kod incelemesi): kullanici ayni etkinlikten birden fazla
    mesajda bahsederse (ornek: "persembe mac var, bilet almam lazim"
    sonra baska bir mesajda "unutma persembe mac var") her ikisi de
    ayri ayri hatirlatma cikarimini gecip coklanan bildirim uretiyordu.
    Kusursuz bir cozum degil (aynı gunde GERCEKTEN iki farkli etkinlik
    varsa ikincisi atlanir) ama coklanan bildirim can sikiciligindan
    daha iyi bir bedel."""
    with db_cursor() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM reminders WHERE user_id = ? AND event_at = ? LIMIT 1",
            (user_id, event_at)
        )
        return cursor.fetchone() is not None


def get_active_reminders(user_id: int) -> List[dict]:
    """Etkinlik tarihi henuz gecmemis TUM hatirlatmalar - istemci bunlari
    yerel bildirim olarak zamanlar (delivered olsa bile tekrar zamanlamak
    zararsiz, bildirim ID'si sabit oldugu icin isletim sistemi ayni ID'yi
    gunceller/tekilleştirir)."""
    with db_cursor() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM reminders WHERE user_id = ? AND date(event_at) >= date('now') "
            "ORDER BY remind_at ASC",
            (user_id,)
        )
        rows = cursor.fetchall()
    return [dict(row) for row in rows]


def mark_reminder_delivered(user_id: int, reminder_id: int) -> None:
    with db_cursor(commit=True) as conn:
        conn.execute(
            "UPDATE reminders SET delivered = 1 WHERE id = ? AND user_id = ?",
            (reminder_id, user_id)
        )


def delete_reminder(user_id: int, reminder_id: int) -> None:
    with db_cursor(commit=True) as conn:
        conn.execute(
            "DELETE FROM reminders WHERE id = ? AND user_id = ?",
            (reminder_id, user_id)
        )


def get_due_reminders_for_nudge(user_id: int, days_ahead: int = 1) -> Optional[dict]:
    """Sohbet ici proaktif hatirlatma icin: remind_at bugune kadar gelmis
    (bugun dahil, gecmis kalmis olsa bile) ama kullaniciya HENUZ sohbette
    hic bahsedilmemis (delivered=0) hatirlatmalar."""
    with db_cursor() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM reminders WHERE user_id = ? AND delivered = 0 "
            "AND date(remind_at) <= date('now', ?) ORDER BY remind_at ASC LIMIT 1",
            (user_id, f"+{days_ahead} day")
        )
        row = cursor.fetchone()
    return dict(row) if row else None


# --- MOOD ---

def add_mood(user_id: int, mood: str, intensity: int = 5, context: str = ""):
    with db_cursor(commit=True) as conn:
        conn.execute(
            "INSERT INTO mood_logs (user_id, mood, intensity, context) VALUES (?, ?, ?, ?)",
            (user_id, mood, intensity, context)
        )


def get_recent_moods(user_id: int, days: int = 7) -> List[dict]:
    with db_cursor() as conn:
        cursor = conn.cursor()
        # Kod sagligi taramasinda bulundu: `days` daha once f-string ile
        # dogrudan SQL'e gomuluyordu - su an hep sabit bir degerle
        # cagrildigi icin aktif bir risk yoktu, ama ileride bu fonksiyon
        # kullanici girdisiyle parametrize edilirse enjeksiyon riski
        # olustururdu. Artik tam parametrize edildi.
        cursor.execute(
            """SELECT * FROM mood_logs
               WHERE user_id = ? AND timestamp >= datetime('now', ? || ' days')
               ORDER BY timestamp DESC""",
            (user_id, f"-{int(days)}")
        )
        rows = cursor.fetchall()
    return [dict(row) for row in rows]


def get_mood_summary(user_id: int) -> dict:
    with db_cursor() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT mood, COUNT(*) as count FROM mood_logs
               WHERE user_id = ? AND timestamp >= datetime('now', '-30 days')
               GROUP BY mood ORDER BY count DESC""",
            (user_id,)
        )
        rows = cursor.fetchall()
    return {row['mood']: row['count'] for row in rows}


# Sosyal katman (arkadas + story feed) fonksiyonlari BILEREK kaldirildi
# (2026-08-25) - bkz. main.py'deki ayni not. Tablolar (friends, stories)
# veri kaybini onlemek icin veritabani semasinda kaldi ama hicbir
# endpoint artik onlara dokunmuyor - erisilemez, zararsiz.


# --- PATTERNS ---

def add_pattern(user_id: int, pattern_type: str, data: dict):
    with db_cursor(commit=True) as conn:
        conn.execute(
            "INSERT INTO user_patterns (user_id, pattern_type, pattern_data) VALUES (?, ?, ?)",
            (user_id, pattern_type, json.dumps(data, ensure_ascii=False))
        )


def get_patterns(user_id: int, pattern_type: Optional[str] = None) -> List[dict]:
    with db_cursor() as conn:
        cursor = conn.cursor()
        if pattern_type:
            cursor.execute(
                "SELECT * FROM user_patterns WHERE user_id = ? AND pattern_type = ? ORDER BY detected_at DESC",
                (user_id, pattern_type)
            )
        else:
            cursor.execute(
                "SELECT * FROM user_patterns WHERE user_id = ? ORDER BY detected_at DESC",
                (user_id,)
            )
        rows = cursor.fetchall()
    return [dict(row) for row in rows]


# --- ANALITIK (2026-08-24, reklam kampanyasi sirasinda kullaniciya
# hicbir gorunurluk olmadigi tespit edildi - yeni istemci-tarafi
# olay izleme eklemek yerine, zaten var olan verilerden [users,
# messages tablolari] anlamli toplu istatistikler cikariyoruz. Sifir
# yeni bagimlilik, sifir yeni riskli client kodu.) ---

def get_admin_stats() -> dict:
    with db_cursor() as conn:
        cursor = conn.cursor()

        def scalar(sql: str, params: tuple = ()) -> int:
            cursor.execute(sql, params)
            row = cursor.fetchone()
            return (row[0] if row and row[0] is not None else 0)

        total_users = scalar("SELECT COUNT(*) FROM users")
        new_today = scalar(
            "SELECT COUNT(*) FROM users WHERE date(created_at) = date('now')"
        )
        new_7d = scalar(
            "SELECT COUNT(*) FROM users WHERE created_at >= date('now', '-7 days')"
        )
        claimed = scalar("SELECT COUNT(*) FROM users WHERE is_anonymous = 0")
        anonymous = scalar("SELECT COUNT(*) FROM users WHERE is_anonymous != 0")
        pro_users = scalar("SELECT COUNT(*) FROM users WHERE tier = 'pro'")

        messages_total = scalar("SELECT COUNT(*) FROM messages")
        messages_today = scalar(
            "SELECT COUNT(*) FROM messages WHERE date(timestamp) = date('now')"
        )
        active_users_today = scalar(
            "SELECT COUNT(DISTINCT user_id) FROM messages WHERE date(timestamp) = date('now')"
        )

        # Bugunku kullanim sayaclari sadece usage_date=bugun olan
        # kullanicilarda anlamli (baskalari henuz o gun hic kullanmamis
        # ya da sayac dunku deger, ilk kullanimda otomatik sifirlanacak).
        voice_seconds_today = scalar(
            "SELECT SUM(daily_voice_seconds) FROM users WHERE usage_date = date('now')"
        )
        messages_counted_today = scalar(
            "SELECT SUM(daily_message_count) FROM users WHERE usage_date = date('now')"
        )
        users_at_message_limit_today = scalar(
            "SELECT COUNT(*) FROM users WHERE usage_date = date('now') "
            "AND tier != 'pro' AND daily_message_count >= 30"
        )
        users_at_voice_limit_today = scalar(
            "SELECT COUNT(*) FROM users WHERE usage_date = date('now') "
            "AND tier != 'pro' AND daily_voice_seconds >= 600"
        )

        # Reklam/gorunurluk analitigi (2026-08-27): son 30 gunde kaynaga
        # (acquisition_source) gore yeni kullanici kirilimi - hangi
        # reklam/kanalin gercekten kullanici getirdigini gormek icin.
        # Bos kaynak (organik/dogrudan/eski istemci) "belirtilmemis"
        # olarak grupanıyor.
        cursor.execute(
            """
            SELECT
                CASE WHEN TRIM(COALESCE(acquisition_source, '')) = ''
                     THEN 'belirtilmemis' ELSE acquisition_source END AS source,
                COUNT(*) AS count
            FROM users
            WHERE created_at >= date('now', '-30 days')
            GROUP BY source
            ORDER BY count DESC
            """
        )
        acquisition_breakdown_30d = [
            {"source": row[0], "count": row[1]} for row in cursor.fetchall()
        ]

        # Reklam etkinligini degerlendirmenin diger yarisi: kac kisi
        # GETIRILDI degil, kac kisi GERI GELDI. 2-14 gun once kayit olan
        # kullanicilardan, kayit olduklari GUNUN ERTESI GUNU en az bir
        # mesaj gonderenlerin orani ("gun-1 elde tutma"). Cok yeni kayitlar
        # (son 2 gun) disarida tutuluyor - henuz "ertesi gun"leri
        # gecmemis olabilirler, dahil edilirlerse oran yapay dusuk cikar.
        day1_eligible = scalar(
            "SELECT COUNT(*) FROM users WHERE date(created_at) "
            "BETWEEN date('now', '-14 days') AND date('now', '-2 days')"
        )
        day1_returned = scalar(
            """
            SELECT COUNT(*) FROM users u WHERE date(u.created_at)
            BETWEEN date('now', '-14 days') AND date('now', '-2 days')
            AND EXISTS (
                SELECT 1 FROM messages m WHERE m.user_id = u.id
                AND date(m.timestamp) = date(u.created_at, '+1 day')
            )
            """
        )
        day1_retention_pct = (
            round(100 * day1_returned / day1_eligible, 1) if day1_eligible else None
        )

    return {
        "total_users": total_users,
        "new_users_today": new_today,
        "new_users_7d": new_7d,
        "claimed_accounts": claimed,
        "anonymous_accounts": anonymous,
        "pro_users": pro_users,
        "messages_total": messages_total,
        "messages_today": messages_today,
        "active_users_today": active_users_today,
        "voice_seconds_today": voice_seconds_today,
        "messages_counted_today": messages_counted_today,
        "users_at_message_limit_today": users_at_message_limit_today,
        "users_at_voice_limit_today": users_at_voice_limit_today,
        "acquisition_breakdown_30d": acquisition_breakdown_30d,
        "day1_retention_pct": day1_retention_pct,
        "day1_eligible": day1_eligible,
    }
