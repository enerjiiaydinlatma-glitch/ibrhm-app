"""Test hesaplarini (email'i @test.local ile biten) ve onlara bagli TUM
satirlari veritabanindan siler.

QA sirasinda gercek /api/auth/register ucuna acilan test hesaplari
(fulltest+..., deployck+... hepsi @test.local) production SQLite'ta
birikiyor - bunlari toplu temizler.

Kullanim (auro-backend/ icinden, veya Railway shell'de):
    python cleanup_test_users.py            # KURU CALISMA - sadece raporlar
    python cleanup_test_users.py --apply    # gercekten siler (tek transaction)

DB_DIR ortam degiskenini kullanir (Railway'de /data) - app ile ayni dosya.
Guvenlik: eslesme sayisi --max-delete'i (varsayilan 500) asarsa, yanlis
desenle gercek kullanicilari silmemek icin durur (--force ile gecilir).
"""
import argparse
import os
import sqlite3
import sys

# database.py ile AYNI cozumleme - ama o modulu import etmiyoruz (bcrypt vb.
# agir bagimliliklari var; bu script tek basina, Railway shell'de de kossun).
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(os.getenv("DB_DIR", _BASE_DIR), "aura.db")

# (tablo, sutun) - kullaniciya bagli her satir. Silme sirasi onemsiz
# (FK ON DELETE yok, elle siliyoruz) ama users EN SON.
_USER_REFS = [
    ("sessions", "user_id"),
    ("messages", "user_id"),
    ("mood_logs", "user_id"),
    ("reminders", "user_id"),
    ("friends", "user_id"),
    ("friends", "friend_user_id"),
    ("stories", "user_id"),
    ("user_patterns", "user_id"),
    ("memories", "user_id"),
    ("memory_candidates", "user_id"),
    ("memory_events", "user_id"),
    ("location_gifts", "sender_id"),
    ("location_gifts", "recipient_id"),
]

EMAIL_PATTERN = "%@test.local"


def _table_exists(conn, name: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="gercekten sil (yoksa kuru calisma)")
    ap.add_argument("--max-delete", type=int, default=500, help="bu sayidan fazla kullanici eslersirse dur")
    ap.add_argument("--force", action="store_true", help="--max-delete sinirini yoksay")
    ap.add_argument("--pattern", default=EMAIL_PATTERN, help="email LIKE deseni (varsayilan %%@test.local)")
    args = ap.parse_args()

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    print(f"DB: {DB_PATH}")
    print(f"Desen: email LIKE {args.pattern!r}\n")

    rows = conn.execute(
        "SELECT id, email, name, created_at FROM users WHERE email LIKE ? ORDER BY id",
        (args.pattern,),
    ).fetchall()
    if not rows:
        print("Eslesen test hesabi yok - yapacak bir sey yok.")
        return 0

    ids = [r["id"] for r in rows]
    print(f"{len(ids)} test hesabi eslesti:")
    for r in rows:
        print(f"  #{r['id']:<5} {r['email']:<40} {r['name'] or ''}  ({r['created_at']})")

    if len(ids) > args.max_delete and not args.force:
        print(
            f"\nDUR: {len(ids)} > --max-delete={args.max_delete}. Desen cok genis "
            f"olabilir - kontrol et, kasitliysa --force ekle."
        )
        return 2

    placeholders = ",".join("?" * len(ids))
    print("\nBagli satirlar:")
    plan = []
    for table, col in _USER_REFS:
        if not _table_exists(conn, table):
            continue
        n = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {col} IN ({placeholders})", ids
        ).fetchone()[0]
        if n:
            print(f"  {table}.{col}: {n}")
            plan.append((table, col, n))
    print(f"  users: {len(ids)}")

    if not args.apply:
        print("\n(KURU CALISMA - hicbir sey silinmedi. Gercekten silmek icin --apply)")
        return 0

    try:
        conn.execute("BEGIN")
        for table, col, _ in plan:
            conn.execute(f"DELETE FROM {table} WHERE {col} IN ({placeholders})", ids)
        conn.execute(f"DELETE FROM users WHERE id IN ({placeholders})", ids)
        conn.execute("COMMIT")
    except Exception as e:
        conn.execute("ROLLBACK")
        print(f"\nHATA - geri alindi: {e}")
        return 1

    print(f"\nSILINDI: {len(ids)} hesap + bagli satirlar. Transaction commit edildi.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
