"""forget_memory / clear_memories gercekten SILIYOR mu testleri
(Paket 1 / madde B2: eskiden sadece status='forgotten' isaretliyordu,
satir DB'de kaliyordu).
Calistirma (auro-backend klasorunden):  python -m pytest tests/test_aura_memory_forget.py -q
"""
import os
import sys
import tempfile

_TMP = tempfile.mkdtemp(prefix="aura_memory_forget_test_")
os.environ["DB_DIR"] = _TMP
os.environ.setdefault("GEMINI_API_KEY", "test-key-not-real")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import aura_memory  # noqa: E402
import database  # noqa: E402

database.init_db()
aura_memory.init_memory_db()


def _row_count(user_id: int) -> int:
    with aura_memory.db_cursor() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS c FROM memories WHERE user_id = ?", (user_id,))
        return cursor.fetchone()["c"]


def _make_user(email: str) -> dict:
    user = database.create_user(email, "sifre123", name="Test")
    assert user is not None
    return user


def test_forget_memory_deletes_the_row_not_just_marks_it():
    user = _make_user("hafiza-unut-1@test.aura")
    memory_id = aura_memory.add_memory(user["id"], "hobi", "sevdigi_spor", "yuzme")
    assert _row_count(user["id"]) == 1

    ok = aura_memory.forget_memory(user["id"], memory_id)
    assert ok is True
    # eskiden burada satir hala vardi (sadece status='forgotten') - artik
    # satir TAMAMEN gitmis olmali.
    assert _row_count(user["id"]) == 0
    assert aura_memory.get_memory(user["id"], memory_id) is None


def test_forget_memory_cannot_delete_another_users_memory():
    owner = _make_user("hafiza-unut-2a@test.aura")
    other = _make_user("hafiza-unut-2b@test.aura")
    memory_id = aura_memory.add_memory(owner["id"], "hobi", "sevdigi_renk", "mavi")

    ok = aura_memory.forget_memory(other["id"], memory_id)
    assert ok is False
    assert _row_count(owner["id"]) == 1


def test_clear_memories_deletes_all_active_rows():
    user = _make_user("hafiza-unut-3@test.aura")
    aura_memory.add_memory(user["id"], "hobi", "sevdigi_spor", "yuzme")
    aura_memory.add_memory(user["id"], "hobi", "sevdigi_kitap", "roman")
    assert _row_count(user["id"]) == 2

    aura_memory.clear_memories(user["id"])
    assert _row_count(user["id"]) == 0
