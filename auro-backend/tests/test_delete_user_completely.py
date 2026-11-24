"""delete_user_completely testleri (Paket 1 / madde B1: eskiden
friends/stories/location_gifts tablolarini HIC silmiyordu - bu tablolar
artik hicbir endpoint tarafindan yazilmiyor ama ozellik kaldirilmadan
ONCE olusmus satirlar kalici kalabiliyordu).
Calistirma (auro-backend klasorunden):  python -m pytest tests/test_delete_user_completely.py -q
"""
import os
import sys
import tempfile

_TMP = tempfile.mkdtemp(prefix="aura_delete_user_test_")
os.environ["DB_DIR"] = _TMP
os.environ.setdefault("GEMINI_API_KEY", "test-key-not-real")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import aura_memory  # noqa: E402
import database  # noqa: E402

database.init_db()
aura_memory.init_memory_db()


def _make_user(email: str) -> dict:
    user = database.create_user(email, "sifre123", name="Test")
    assert user is not None
    return user


def _count(table: str, where: str, *params) -> int:
    with database.db_cursor() as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) AS c FROM {table} WHERE {where}", params)
        return cursor.fetchone()["c"]


def test_delete_user_completely_removes_legacy_social_rows():
    user = _make_user("sil-sosyal@test.aura")
    other = _make_user("sil-sosyal-arkadas@test.aura")

    with database.db_cursor(commit=True) as conn:
        # dogrudan SQL ile - artik hicbir endpoint bu tablolara yazmiyor,
        # ama eski/legacy satirlari simule etmek icin.
        conn.execute(
            "INSERT INTO friends (user_id, friend_user_id, friend_name) VALUES (?, ?, ?)",
            (user["id"], other["id"], "Eski Arkadas"),
        )
        conn.execute(
            "INSERT INTO friends (user_id, friend_user_id, friend_name) VALUES (?, ?, ?)",
            (other["id"], user["id"], "Silinecek Kullanici"),
        )
        conn.execute(
            "INSERT INTO stories (user_id, content) VALUES (?, ?)",
            (user["id"], "eski bir hikaye"),
        )
        conn.execute(
            "INSERT INTO location_gifts (sender_id, recipient_id, lat, lon) VALUES (?, ?, ?, ?)",
            (user["id"], other["id"], 41.0, 29.0),
        )
        conn.execute(
            "INSERT INTO location_gifts (sender_id, recipient_id, lat, lon) VALUES (?, ?, ?, ?)",
            (other["id"], user["id"], 41.0, 29.0),
        )

    database.delete_user_completely(user["id"])

    # user'a referans veren TUM satirlar (hangi sutunda olursa olsun) gitmis olmali.
    assert _count("friends", "user_id = ? OR friend_user_id = ?", user["id"], user["id"]) == 0
    assert _count("stories", "user_id = ?", user["id"]) == 0
    assert _count("location_gifts", "sender_id = ? OR recipient_id = ?", user["id"], user["id"]) == 0
    # digerine ait, user'a referans vermeyen satirlar DOKUNULMADAN kalmali.
    assert database.get_user_by_email("sil-sosyal-arkadas@test.aura") is not None


def test_delete_user_completely_removes_the_user_row():
    user = _make_user("sil-kullanici@test.aura")
    database.delete_user_completely(user["id"])
    assert database.get_user_by_email("sil-kullanici@test.aura") is None
