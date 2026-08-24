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
        ):
            try:
                cursor.execute(migration)
            except sqlite3.OperationalError:
                pass  # sutun zaten var

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


def create_user(email: str, password: str, name: str = "") -> Optional[dict]:
    try:
        with db_cursor(commit=True) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (email, password_hash, name) VALUES (?, ?, ?)",
                (email.lower().strip(), hash_password(password), name)
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
            "UPDATE users SET daily_message_count = 0, daily_voice_seconds = 0, usage_date = ? WHERE id = ?",
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
    allowed = ['name', 'warmth', 'formality', 'humor', 'directness',
               'notes', 'location_lat', 'location_lon', 'location_city',
               'weather_enabled', 'activity_enabled', 'mood_tracking_enabled']
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return get_user(user_id)
    set_clause = ", ".join([f"{k} = ?" for k in fields.keys()])
    values = list(fields.values()) + [user_id]
    with db_cursor(commit=True) as conn:
        conn.execute(f"UPDATE users SET {set_clause} WHERE id = ?", values)
    return get_user(user_id)


# --- MESSAGES ---

def add_message(user_id: int, role: str, text: str, emotion: Optional[str] = None):
    with db_cursor(commit=True) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO messages (user_id, role, text, emotion_detected) VALUES (?, ?, ?, ?)",
            (user_id, role, text, emotion)
        )
        message_id = cursor.lastrowid
    return message_id


def get_messages(user_id: int, limit: int = 100) -> List[dict]:
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
        cursor.execute(
            "SELECT * FROM messages WHERE user_id = ? ORDER BY timestamp DESC, id DESC LIMIT ?",
            (user_id, limit)
        )
        rows = cursor.fetchall()
    return [dict(row) for row in reversed(rows)]


def clear_messages(user_id: int):
    with db_cursor(commit=True) as conn:
        conn.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))


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


# --- FRIENDS ---

def send_friend_request(user_id: int, friend_email: str) -> bool:
    friend = get_user_by_email(friend_email)
    if not friend:
        return False
    with db_cursor(commit=True) as conn:
        conn.execute(
            """INSERT OR IGNORE INTO friends
               (user_id, friend_user_id, friend_name, friend_email, status)
               VALUES (?, ?, ?, ?, 'pending')""",
            (user_id, friend['id'], friend.get('name', ''), friend_email)
        )
    return True


def accept_friend_request(friendship_id: int, caller_user_id: int) -> bool:
    """
    GUVENLIK TARAMASI BULGUSU (IDOR): daha once caller'in bu istegin
    ALICISI (friend_user_id) olup olmadigi HIC kontrol edilmiyordu -
    istegi GONDEREN kullanici da (friendship_id'yi bilerek/tahmin ederek)
    kendi istegini kendisi onaylayabiliyordu, bu da hedef kullanicinin
    onayi olmadan onun 'arkadasa ozel' hikayelerine erisim kazandiriyordu.
    Artik sadece caller GERCEKTEN o istegin alicisiysa satir guncelleniyor.
    """
    with db_cursor(commit=True) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE friends SET status = 'accepted' WHERE id = ? AND friend_user_id = ?",
            (friendship_id, caller_user_id)
        )
        return cursor.rowcount > 0


def get_friends(user_id: int) -> List[dict]:
    with db_cursor() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM friends WHERE user_id = ? AND status = 'accepted'",
            (user_id,)
        )
        rows = cursor.fetchall()
    return [dict(row) for row in rows]


def get_friend_requests(user_id: int) -> List[dict]:
    with db_cursor() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT f.*, u.name as sender_name, u.email as sender_email
               FROM friends f JOIN users u ON f.user_id = u.id
               WHERE f.friend_user_id = ? AND f.status = 'pending'""",
            (user_id,)
        )
        rows = cursor.fetchall()
    return [dict(row) for row in rows]


# --- STORIES ---

def add_story(user_id: int, content: str, image_url: str = "", hours: int = 24) -> dict:
    expires_at = datetime.now() + timedelta(hours=hours)
    with db_cursor(commit=True) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO stories (user_id, content, image_url, expires_at) VALUES (?, ?, ?, ?)",
            (user_id, content, image_url, expires_at)
        )
        story_id = cursor.lastrowid
    return get_story(story_id)


def get_story(story_id: int) -> dict:
    with db_cursor() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM stories WHERE id = ?", (story_id,))
        row = cursor.fetchone()
    return dict(row) if row else {}


def get_friend_stories(user_id: int) -> List[dict]:
    with db_cursor() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT s.*, u.name as author_name FROM stories s
               JOIN users u ON s.user_id = u.id
               JOIN friends f ON (f.friend_user_id = s.user_id AND f.user_id = ?)
               WHERE s.expires_at > datetime('now') AND f.status = 'accepted'
               ORDER BY s.created_at DESC""",
            (user_id,)
        )
        rows = cursor.fetchall()
    return [dict(row) for row in rows]


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
