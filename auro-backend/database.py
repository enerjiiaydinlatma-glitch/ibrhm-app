import sqlite3
from contextlib import contextmanager

DB_PATH = "aura.db"


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                name TEXT,
                warmth TEXT DEFAULT 'sicak',
                formality TEXT DEFAULT 'samimi',
                humor TEXT DEFAULT 'orta',
                directness TEXT DEFAULT 'dengeli',
                notes TEXT DEFAULT ''
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                text TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            INSERT OR IGNORE INTO users (id, name) VALUES (1, NULL)
        """)
        conn.commit()


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def get_user(user_id: int = 1):
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


def update_user(user_id: int, **fields):
    if not fields:
        return
    columns = ", ".join(f"{k} = ?" for k in fields.keys())
    values = list(fields.values()) + [user_id]
    with get_connection() as conn:
        conn.execute(f"UPDATE users SET {columns} WHERE id = ?", values)
        conn.commit()


def add_message(user_id: int, role: str, text: str):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO messages (user_id, role, text) VALUES (?, ?, ?)",
            (user_id, role, text),
        )
        conn.commit()


def get_messages(user_id: int = 1, limit: int = 50):
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT role, text FROM messages WHERE user_id = ? ORDER BY id ASC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]
