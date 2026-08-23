import sqlite3
import json
import hashlib
import secrets
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
    return conn

def init_db():
    conn = get_db()
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

    conn.commit()
    conn.close()


# --- AUTH ---

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def create_user(email: str, password: str, name: str = "") -> Optional[dict]:
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (email, password_hash, name) VALUES (?, ?, ?)",
            (email.lower().strip(), hash_password(password), name)
        )
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        return get_user(user_id)
    except sqlite3.IntegrityError:
        conn.close()
        return None

def authenticate_user(email: str, password: str) -> Optional[dict]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM users WHERE email = ? AND password_hash = ?",
        (email.lower().strip(), hash_password(password))
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def create_session(user_id: int, days: int = 30) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now() + timedelta(days=days)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO sessions (user_id, token, expires_at) VALUES (?, ?, ?)",
        (user_id, token, expires_at)
    )
    conn.commit()
    conn.close()
    return token

def get_user_by_token(token: str) -> Optional[dict]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT u.* FROM users u
           JOIN sessions s ON u.id = s.user_id
           WHERE s.token = ? AND s.expires_at > datetime('now')""",
        (token,)
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def delete_session(token: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
    conn.commit()
    conn.close()


def enforce_single_session(user_id: int):
    """
    Bu kullaniciya ait TUM oturumlari (diger cihazlar dahil) siler.
    'free' tier kullanicilar icin yeni bir session olusturulmadan HEMEN
    ONCE cagrilir - boylece yeni cihazdan giris, eski cihazin oturumunu
    dusurur (ayni anda tek cihaz kurali). 'pro' tier icin cagrilmaz.
    """
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


def claim_account(user_id: int, email: str, password: str) -> bool:
    """
    Anonim (rastgele email/sifreyle olusturulmus) bir hesabi, kullanicinin
    KENDI belirledigi gercek email/sifreyle gercek, hatirlanabilir bir
    hesaba cevirir. YENI bir kullanici satiri OLUSTURMAZ - ayni satir
    guncellenir, boylece tum gecmis/hafiza korunur. Email baskasina
    aitse (UNIQUE ihlali) False doner.
    """
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE users SET email = ?, password_hash = ?, is_anonymous = 0 WHERE id = ?",
            (email.lower().strip(), hash_password(password), user_id),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


# --- USER ---

def get_user(user_id: int) -> dict:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else {}

def get_user_by_email(email: str) -> Optional[dict]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email.lower().strip(),))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def update_user(user_id: int, **kwargs) -> dict:
    conn = get_db()
    cursor = conn.cursor()
    allowed = ['name', 'warmth', 'formality', 'humor', 'directness',
               'notes', 'location_lat', 'location_lon', 'location_city',
               'weather_enabled', 'activity_enabled', 'mood_tracking_enabled']
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return get_user(user_id)
    set_clause = ", ".join([f"{k} = ?" for k in fields.keys()])
    values = list(fields.values()) + [user_id]
    cursor.execute(f"UPDATE users SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()
    return get_user(user_id)


# --- MESSAGES ---

def add_message(user_id: int, role: str, text: str, emotion: Optional[str] = None):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO messages (user_id, role, text, emotion_detected) VALUES (?, ?, ?, ?)",
        (user_id, role, text, emotion)
    )

    message_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return message_id


def get_messages(user_id: int, limit: int = 100) -> List[dict]:
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM messages WHERE user_id = ? ORDER BY timestamp LIMIT ?",
        (user_id, limit)
    )

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def clear_messages(user_id: int):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM messages WHERE user_id = ?",
        (user_id,)
    )

    conn.commit()
    conn.close()
# --- MOOD ---

def add_mood(user_id: int, mood: str, intensity: int = 5, context: str = ""):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO mood_logs (user_id, mood, intensity, context) VALUES (?, ?, ?, ?)",
        (user_id, mood, intensity, context)
    )
    conn.commit()
    conn.close()

def get_recent_moods(user_id: int, days: int = 7) -> List[dict]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        f"""SELECT * FROM mood_logs
           WHERE user_id = ? AND timestamp >= datetime('now', '-{days} days')
           ORDER BY timestamp DESC""",
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_mood_summary(user_id: int) -> dict:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT mood, COUNT(*) as count FROM mood_logs
           WHERE user_id = ? AND timestamp >= datetime('now', '-30 days')
           GROUP BY mood ORDER BY count DESC""",
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return {row['mood']: row['count'] for row in rows}


# --- FRIENDS ---

def send_friend_request(user_id: int, friend_email: str) -> bool:
    friend = get_user_by_email(friend_email)
    if not friend:
        return False
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT OR IGNORE INTO friends
           (user_id, friend_user_id, friend_name, friend_email, status)
           VALUES (?, ?, ?, ?, 'pending')""",
        (user_id, friend['id'], friend.get('name', ''), friend_email)
    )
    conn.commit()
    conn.close()
    return True

def accept_friend_request(friendship_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE friends SET status = 'accepted' WHERE id = ?",
        (friendship_id,)
    )
    conn.commit()
    conn.close()

def get_friends(user_id: int) -> List[dict]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM friends WHERE user_id = ? AND status = 'accepted'",
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_friend_requests(user_id: int) -> List[dict]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT f.*, u.name as sender_name, u.email as sender_email
           FROM friends f JOIN users u ON f.user_id = u.id
           WHERE f.friend_user_id = ? AND f.status = 'pending'""",
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# --- STORIES ---

def add_story(user_id: int, content: str, image_url: str = "", hours: int = 24) -> dict:
    expires_at = datetime.now() + timedelta(hours=hours)
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO stories (user_id, content, image_url, expires_at) VALUES (?, ?, ?, ?)",
        (user_id, content, image_url, expires_at)
    )
    story_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return get_story(story_id)

def get_story(story_id: int) -> dict:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM stories WHERE id = ?", (story_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else {}

def get_friend_stories(user_id: int) -> List[dict]:
    conn = get_db()
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
    conn.close()
    return [dict(row) for row in rows]


# --- PATTERNS ---

def add_pattern(user_id: int, pattern_type: str, data: dict):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO user_patterns (user_id, pattern_type, pattern_data) VALUES (?, ?, ?)",
        (user_id, pattern_type, json.dumps(data, ensure_ascii=False))
    )
    conn.commit()
    conn.close()

def get_patterns(user_id: int, pattern_type: Optional[str] = None) -> List[dict]:
    conn = get_db()
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
    conn.close()
    return [dict(row) for row in rows]