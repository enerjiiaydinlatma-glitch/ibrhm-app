import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Optional, List, Dict, Any


from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# database.py ile ayni sozlesme: DB_DIR verilirse (Railway kalici disk)
# oraya, yoksa proje klasorune (yerel gelistirme) yazilir.
DB_DIR = os.getenv("DB_DIR", BASE_DIR)
DB_PATH = os.path.join(DB_DIR, "aura.db")


# ============================================================
# DATABASE
# ============================================================

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # database.py'deki ayni gerekce: ayni anda iki istek ayni satira
    # yazmaya calisirsa SQLite'in ANINDA "database is locked" hatasi
    # vermesini onlemek icin bir bekleme penceresi taniyoruz.
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


@contextmanager
def db_cursor(commit: bool = False):
    """
    database.py'deki db_cursor ile AYNI amac (kasitli olarak burada da
    tekrarlandi - bu modul kendi baglantisini kendi yonetiyor, ortak bir
    import'a bagimli olmasin diye). Kod sagligi taramasinda bulundu: bu
    dosyadaki HER fonksiyon `conn = get_db(); ...; conn.close()`
    deseniyle yaziliyordu - aralarinda bir exception olursa `conn.close()`
    hic calismiyordu (baglanti sizintisi riski). Artik try/finally ile
    HER durumda baglanti kapatiliyor. `commit=True` verilirse, blok
    hatasiz bitince (normal return dahil) otomatik commit yapilir.
    """
    conn = get_db()
    try:
        yield conn
        if commit:
            conn.commit()
    finally:
        conn.close()


def init_memory_db():
    """
    Aura Memory 2.0 tablolarini olusturur.
    Mevcut Aura tablolarina dokunmaz.
    """

    with db_cursor(commit=True) as conn:
        cursor = conn.cursor()

        # --------------------------------------------------------
        # LONG-TERM MEMORIES
        # --------------------------------------------------------

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,

                category TEXT NOT NULL,
                memory_key TEXT NOT NULL,
                memory_value TEXT NOT NULL,

                confidence REAL DEFAULT 0.5,
                importance REAL DEFAULT 0.5,

                source_message_id INTEGER,

                status TEXT DEFAULT 'active',

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_used_at TIMESTAMP,

                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )

        # --------------------------------------------------------
        # MEMORY CANDIDATES
        # --------------------------------------------------------

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,

                category TEXT NOT NULL,
                memory_key TEXT NOT NULL,
                memory_value TEXT NOT NULL,

                confidence REAL DEFAULT 0.5,

                source_message_id INTEGER,

                status TEXT DEFAULT 'candidate',

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )

        # --------------------------------------------------------
        # MEMORY EVENTS
        # --------------------------------------------------------

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                user_id INTEGER NOT NULL,
                memory_id INTEGER,

                event_type TEXT NOT NULL,

                event_data TEXT,

                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (memory_id) REFERENCES memories(id)
            )
            """
        )

        # --------------------------------------------------------
        # INDEXES
        # --------------------------------------------------------

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_memories_user
            ON memories(user_id)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_memories_status
            ON memories(user_id, status)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_candidates_user
            ON memory_candidates(user_id)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_candidates_status
            ON memory_candidates(user_id, status)
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_memory_events_user
            ON memory_events(user_id)
            """
        )


# ============================================================
# MEMORY EVENTS
# ============================================================

def add_memory_event(
    user_id: int,
    event_type: str,
    memory_id: Optional[int] = None,
    event_data: Optional[Dict[str, Any]] = None,
):
    data = None

    if event_data is not None:
        data = json.dumps(
            event_data,
            ensure_ascii=False,
        )

    with db_cursor(commit=True) as conn:
        conn.execute(
            """
            INSERT INTO memory_events
            (
                user_id,
                memory_id,
                event_type,
                event_data
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                user_id,
                memory_id,
                event_type,
                data,
            ),
        )


# ============================================================
# CANDIDATES
# ============================================================

def add_candidate(
    user_id: int,
    category: str,
    memory_key: str,
    memory_value: str,
    confidence: float = 0.5,
    source_message_id: Optional[int] = None,
) -> int:

    with db_cursor(commit=True) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO memory_candidates
            (
                user_id,
                category,
                memory_key,
                memory_value,
                confidence,
                source_message_id
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                category,
                memory_key,
                memory_value,
                confidence,
                source_message_id,
            ),
        )
        candidate_id = cursor.lastrowid

    return candidate_id


def get_candidates(
    user_id: int,
    status: str = "candidate",
) -> List[dict]:

    with db_cursor() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT *
            FROM memory_candidates
            WHERE user_id = ?
            AND status = ?
            ORDER BY updated_at DESC
            """,
            (
                user_id,
                status,
            ),
        )
        rows = cursor.fetchall()

    return [dict(row) for row in rows]


# ============================================================
# LONG-TERM MEMORY
# ============================================================

def add_memory(
    user_id: int,
    category: str,
    memory_key: str,
    memory_value: str,
    confidence: float = 0.8,
    importance: float = 0.5,
    source_message_id: Optional[int] = None,
) -> int:

    with db_cursor(commit=True) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO memories
            (
                user_id,
                category,
                memory_key,
                memory_value,
                confidence,
                importance,
                source_message_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                category,
                memory_key,
                memory_value,
                confidence,
                importance,
                source_message_id,
            ),
        )
        memory_id = cursor.lastrowid

    add_memory_event(
        user_id=user_id,
        memory_id=memory_id,
        event_type="created",
        event_data={
            "category": category,
            "key": memory_key,
        },
    )

    return memory_id


def get_memories(
    user_id: int,
    status: str = "active",
) -> List[dict]:

    with db_cursor() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT *
            FROM memories
            WHERE user_id = ?
            AND status = ?
            ORDER BY importance DESC, updated_at DESC
            """,
            (
                user_id,
                status,
            ),
        )
        rows = cursor.fetchall()

    return [dict(row) for row in rows]


def find_active_memory(
    user_id: int,
    category: str,
    memory_key: str,
) -> Optional[dict]:
    """
    Ayni kullanici+kategori+anahtar icin zaten aktif bir hafiza kaydi
    var mi diye bakar (kucuk/buyuk harf duyarsiz). Upsert icin kullanilir.
    """

    with db_cursor() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT *
            FROM memories
            WHERE user_id = ?
            AND status = 'active'
            AND category = ?
            AND LOWER(memory_key) = LOWER(?)
            """,
            (
                user_id,
                category,
                memory_key,
            ),
        )
        row = cursor.fetchone()

    return dict(row) if row else None


def promote_candidate_to_memory(
    user_id: int,
    category: str,
    memory_key: str,
    memory_value: str,
    confidence: float,
    source_message_id: Optional[int] = None,
) -> int:
    """
    Bir memory candidate'i aktif hafizaya tasir (upsert).
    Ayni user+category+key icin aktif kayit varsa deger/confidence
    guncellenir, yoksa yeni aktif hafiza olusturulur.
    """

    existing = find_active_memory(user_id, category, memory_key)

    if existing:
        update_memory(
            user_id=user_id,
            memory_id=existing["id"],
            memory_value=memory_value,
            confidence=confidence,
        )
        return existing["id"]

    return add_memory(
        user_id=user_id,
        category=category,
        memory_key=memory_key,
        memory_value=memory_value,
        confidence=confidence,
        importance=confidence,
        source_message_id=source_message_id,
    )


def get_memory(
    user_id: int,
    memory_id: int,
) -> Optional[dict]:

    with db_cursor() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT *
            FROM memories
            WHERE id = ?
            AND user_id = ?
            """,
            (
                memory_id,
                user_id,
            ),
        )
        row = cursor.fetchone()

    return dict(row) if row else None


# ============================================================
# UPDATE MEMORY
# ============================================================

def update_memory(
    user_id: int,
    memory_id: int,
    memory_value: Optional[str] = None,
    confidence: Optional[float] = None,
    importance: Optional[float] = None,
) -> bool:

    fields = []
    values = []

    if memory_value is not None:
        fields.append("memory_value = ?")
        values.append(memory_value)

    if confidence is not None:
        fields.append("confidence = ?")
        values.append(confidence)

    if importance is not None:
        fields.append("importance = ?")
        values.append(importance)

    if not fields:
        return False

    fields.append(
        "updated_at = CURRENT_TIMESTAMP"
    )

    values.extend(
        [
            memory_id,
            user_id,
        ]
    )

    with db_cursor(commit=True) as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"""
            UPDATE memories
            SET {", ".join(fields)}
            WHERE id = ?
            AND user_id = ?
            """,
            values,
        )
        changed = cursor.rowcount > 0

    if changed:
        add_memory_event(
            user_id=user_id,
            memory_id=memory_id,
            event_type="updated",
        )

    return changed


# ============================================================
# FORGET MEMORY
# ============================================================

def forget_memory(
    user_id: int,
    memory_id: int,
) -> bool:

    with db_cursor(commit=True) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE memories
            SET status = 'forgotten',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            AND user_id = ?
            """,
            (
                memory_id,
                user_id,
            ),
        )
        changed = cursor.rowcount > 0

    if changed:
        add_memory_event(
            user_id=user_id,
            memory_id=memory_id,
            event_type="forgotten",
        )

    return changed


def clear_memories(user_id: int):
    with db_cursor(commit=True) as conn:
        conn.execute(
            """
            UPDATE memories
            SET status = 'forgotten',
                updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
            AND status = 'active'
            """,
            (user_id,),
        )

    add_memory_event(
        user_id=user_id,
        event_type="clear_all",
    )


# ============================================================
# MEMORY CONTEXT
# ============================================================

def get_memory_context(
    user_id: int,
    max_memories: int = 20,
) -> str:

    memories = get_memories(user_id)[:max_memories]

    if not memories:
        return ""

    lines = [
        "KULLANICI HAFIZASI:",
    ]

    for memory in memories:

        category = memory.get("category", "")
        value = memory.get("memory_value", "")

        if not value:
            continue

        lines.append(
            f"- [{category}] {value}"
        )

    if len(lines) == 1:
        return ""

    return "\n".join(lines)


# ============================================================
# MEMORY USAGE
# ============================================================

def mark_memory_used(
    user_id: int,
    memory_id: int,
):

    with db_cursor(commit=True) as conn:
        conn.execute(
            """
            UPDATE memories
            SET last_used_at = CURRENT_TIMESTAMP
            WHERE id = ?
            AND user_id = ?
            """,
            (
                memory_id,
                user_id,
            ),
        )

    add_memory_event(
        user_id=user_id,
        memory_id=memory_id,
        event_type="used",
    )


# ============================================================
# INITIALIZATION
# ============================================================

if __name__ == "__main__":
    init_memory_db()
    print("Aura Memory 2.0 database hazir.")
