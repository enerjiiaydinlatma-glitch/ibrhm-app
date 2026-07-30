import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

DB_PATH = "aura.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT DEFAULT 'Dostum',
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
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER DEFAULT 1,
            role TEXT NOT NULL,
            text TEXT NOT NULL,
            emotion_detected TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mood_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER DEFAULT 1,
            mood TEXT NOT NULL,
            intensity INTEGER DEFAULT 5,
            context TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS friends (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER DEFAULT 1,
            friend_name TEXT NOT NULL,
            friend_phone TEXT,
            friend_email TEXT,
            aura_shared INTEGER DEFAULT 0,
            closeness_level INTEGER DEFAULT 5,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS location_gifts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER DEFAULT 1,
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
            user_id INTEGER DEFAULT 1,
            pattern_type TEXT,
            pattern_data TEXT,
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("SELECT id FROM users WHERE id = 1")
    if not cursor.fetchone():
        cursor.execute("""
            INSERT INTO users (id, name, warmth, formality, humor, directness, notes)
            VALUES (1, 'Dostum', 'sicak', 'samimi', 'orta', 'dengeli', 'yok')
        """)
    
    conn.commit()
    conn.close()

def get_user(user_id: int = 1) -> dict:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return {}

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

def add_message(user_id: int, role: str, text: str, emotion: Optional[str] = None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO messages (user_id, role, text, emotion_detected) VALUES (?, ?, ?, ?)",
        (user_id, role, text, emotion)
    )
    conn.commit()
    conn.close()

def get_messages(user_id: int = 1, limit: int = 100) -> List[dict]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM messages WHERE user_id = ? ORDER BY timestamp LIMIT ?",
        (user_id, limit)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def add_mood(user_id: int, mood: str, intensity: int = 5, context: str = ""):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO mood_logs (user_id, mood, intensity, context) VALUES (?, ?, ?, ?)",
        (user_id, mood, intensity, context)
    )
    conn.commit()
    conn.close()

def get_recent_moods(user_id: int = 1, days: int = 7) -> List[dict]:
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

def get_mood_summary(user_id: int = 1) -> dict:
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

def add_friend(user_id: int, name: str, phone: str = "", email: str = "", closeness: int = 5, notes: str = ""):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO friends (user_id, friend_name, friend_phone, friend_email, closeness_level, notes) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, name, phone, email, closeness, notes)
    )
    conn.commit()
    conn.close()

def get_friends(user_id: int = 1) -> List[dict]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM friends WHERE user_id = ?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def share_aura(friend_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE friends SET aura_shared = 1 WHERE id = ?", (friend_id,))
    conn.commit()
    conn.close()

def add_gift(sender_id: int, recipient_id: Optional[int], recipient_name: str, 
             gift_type: str, message: str, lat: float, lon: float, location_name: str = ""):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO location_gifts 
           (sender_id, recipient_id, recipient_name, gift_type, gift_message, lat, lon, location_name)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (sender_id, recipient_id, recipient_name, gift_type, message, lat, lon, location_name)
    )
    conn.commit()
    conn.close()

def get_nearby_gifts(lat: float, lon: float, radius_km: float = 1.0) -> List[dict]:
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        """SELECT *, 
           (6371 * acos(cos(radians(?)) * cos(radians(lat)) * 
           cos(radians(lon) - radians(?)) + sin(radians(?)) * sin(radians(lat)))) AS distance
           FROM location_gifts
           WHERE is_claimed = 0
           HAVING distance < ?
           ORDER BY distance""",
        (lat, lon, lat, radius_km)
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def claim_gift(gift_id: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE location_gifts SET is_claimed = 1, claimed_at = CURRENT_TIMESTAMP WHERE id = ?",
        (gift_id,)
    )
    conn.commit()
    conn.close()

def add_pattern(user_id: int, pattern_type: str, data: dict):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO user_patterns (user_id, pattern_type, pattern_data) VALUES (?, ?, ?)",
        (user_id, pattern_type, json.dumps(data, ensure_ascii=False))
    )
    conn.commit()
    conn.close()

def get_patterns(user_id: int = 1, pattern_type: Optional[str] = None) -> List[dict]:
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
