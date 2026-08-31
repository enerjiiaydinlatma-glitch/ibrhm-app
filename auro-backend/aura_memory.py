import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

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
    # database.py'deki ayni gerekce: WAL modu yazicilarin okuyuculari
    # kilitlemesini onluyor - dosya duzeyinde kalici bir ayar, hangi
    # modulun once baglandigindan bagimsiz her ikisinde de aciyoruz.
    conn.execute("PRAGMA journal_mode = WAL")
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

        # GECE DENETIMI BULGUSU: promote_candidate_to_memory'nin upsert
        # mantigi (once find_active_memory ile oku, sonra ayri bir
        # baglantida yaz) DOGRU ama bunu zorlayan bir DB kisitlamasi
        # yoktu - iki neredeyse es zamanli cagri (cift-tiklama, iki
        # cihaz, ya da bugun erken bulunan coklu-bilgi cikarimi) ayni
        # (user_id, category, memory_key) icin ikisi de "aktif kayit
        # yok" gorup ikisi de INSERT yapabilirdi. find_active_memory
        # LOWER(memory_key) ile karsilastirdigi icin indeks de AYNI
        # normalize edilmis ifadeyi kullanmali. Bugunun erken saatlerinde
        # bulunan "Zeytin/Pamuk" coklanma hatasi TAM OLARAK bu sinifa
        # giriyordu - artik DB seviyesinde de engelleniyor.
        try:
            cursor.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS idx_memories_active_unique
                ON memories(user_id, category, LOWER(memory_key))
                WHERE status = 'active'
                """
            )
        except sqlite3.IntegrityError as e:
            # Mevcut veride ZATEN coklanan aktif kayit varsa indeks
            # olusturulamaz - veriyi SESSIZCE silmek/birlestirmek yerine
            # bunu acikca logluyoruz (elle temizlik gerekiyor demektir).
            print(
                f"UYARI: idx_memories_active_unique olusturulamadi - "
                f"muhtemelen zaten coklanan aktif hafiza kaydi var: {e}"
            )

        # DOGAL HAFIZA (2026-08-27, "Dogal Hafiza Dosyasi" arastirmasindan
        # cikan buluş): kullanici bir hafizayi "hep hatirla" diye
        # sabitleyebilsin diye - sabitlenen kayitlar asagidaki soluklasma
        # hesabindan (bkz. _effective_importance) muaf tutulur. database.py
        # ile ayni desen: SQLite ADD COLUMN IF NOT EXISTS desteklemiyor,
        # dene/basarisiz-olursa-yoksay.
        try:
            cursor.execute("ALTER TABLE memories ADD COLUMN pinned INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # sutun zaten var


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
# DOGAL HAFIZA (soluklasma/gucllenme)
# ============================================================
# "Dogal Hafiza Dosyasi" arastirmasindan cikan buluş (2026-08-27):
# rakiplerin hepsi "her seyi sonsuza kadar hatirlarim" iddiasinda
# yariciyor (Nomi'nin "Identity Core"u, Paradot'un seffaflik defteri,
# Replika'nin "aylar sonra bile hatirlarim" sozu) - Aura'nin bunun
# YERINE gercek bir insan gibi hatirlamasi: bir suredir hic donulmeyen
# bir detay YAVASCA soluklasir (SILINMEZ, sadece geri planda kalir),
# kullanici tekrar tekrar donerse GUCLENIR (bkz. update_memory - her
# guncelleme updated_at'i tazeler, bu da soluklasma saatini sifirlar -
# "gucllenme" icin AYRI bir mekanizma gerekmiyor, zaten var olan
# davranisin dogal bir sonucu). Kullanici isterse bir kaydi "pinned"
# yaparak bu soluklasmadan tamamen muaf tutabilir (bkz. set_memory_pinned).
#
# BILEREK STATELESS/OKUMA-ANINDA: soluklasma DB'deki `importance`
# degerini hicbir zaman KALICI olarak degistirmiyor - sadece OKUMA
# aninda (get_memories) turetilen bir "effective_importance" hesaplaniyor.
# Boylece: (1) hicbir veri kaybi geri donusumsuz degil, (2) zamanlanan
# bir arka plan gorevine (cron) gerek yok, (3) Replika'nin yasadigi
# "hafiza guncellemesi = sessiz veri kaybi = ihanet hissi" sorunu hic
# olusmuyor - stored importance her zaman oldugu gibi duruyor.
DECAY_GRACE_DAYS = 14      # bu sureden once HICBIR soluklasma yok
DECAY_HORIZON_DAYS = 120   # grace suresi bittikten sonra tabana inme suresi
DECAY_FLOOR = 0.15         # asla bunun altina inmez (tamamen "unutulmuyor")
# Bir hafizanin "belirsiz/soluk" sayilip Aura'ya durustce belirsizlik
# ifade etmesi icin verilen esik - effective_importance, orijinal
# importance'in bu orandan daha azina dusmusse (bkz. get_memory_context).
DECAY_UNCERTAIN_RATIO = 0.6


def _effective_importance(importance: float, updated_at: Optional[str], pinned: bool) -> float:
    if pinned or not updated_at:
        return importance
    touched = _parse_memory_timestamp(updated_at)
    if not touched:
        return importance
    days_since_touch = (datetime.now(timezone.utc) - touched).total_seconds() / 86400
    if days_since_touch <= DECAY_GRACE_DAYS:
        return importance
    days_past_grace = days_since_touch - DECAY_GRACE_DAYS
    fraction = min(1.0, days_past_grace / DECAY_HORIZON_DAYS)
    floor = min(DECAY_FLOOR, importance)  # tabani, dusuk-onemli kayitlarda asmayalim
    return importance - (importance - floor) * fraction


def _parse_memory_timestamp(value: Optional[str]):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace(" ", "T")).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


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
    # KENDI KENDINI INCELEME BULGUSU: bugun eklenen tekillik indeksi
    # SQL'in LOWER()'ina dayaniyor - bu ASCII-disi karakterlerde (Turkce
    # ı/İ/I/i) dogru calismiyor (sqlite LOWER('İSİM') -> 'İsİm', 'i'
    # olmuyor). "isik_tercihi" ile "Işık_Tercihi" farkli string sayilip
    # tekillik hic yakalamayabilirdi. Python'un kendi .lower()'i (Unicode
    # farkindaligi SQL'den daha iyi, tek istisna İ/I/ı ozel harfleri) ile
    # DEPOLAMA aninda normalize ederek bu riski buyuk olcude azaltiyoruz.
    memory_key = memory_key.strip().lower()

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
    limit: int = 300,
) -> List[dict]:
    # GECE DENETIMI BULGUSU: bu sorgunun HICBIR LIMIT'i yoktu - her
    # sohbet/sesli turunda (aura_brain.py, aura_lifestyle.py uzerinden)
    # cagriliyor, sonucun sadece ilk 20-40'i kullanilip gerisi atiliyordu.
    # Bugun cok az kullanicida fark etmez ama bir kullanici zamanla
    # binlerce hafiza biriktirirse her mesaj TUM satirlari cekip
    # Python'da atardi. 300 - gercekci hicbir kullanim senaryosunu
    # kesmeyecek kadar cömert, ama sinirsizligi ortadan kaldiriyor.
    with db_cursor() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT *
            FROM memories
            WHERE user_id = ?
            AND status = ?
            ORDER BY importance DESC, updated_at DESC
            LIMIT ?
            """,
            (
                user_id,
                status,
                limit,
            ),
        )
        rows = cursor.fetchall()

    memories = [dict(row) for row in rows]
    # DOGAL HAFIZA: SQL zaten stored importance'a gore sirali getirdi -
    # burada TURETILEN (DB'ye yazilmayan) effective_importance'i hesaplayip
    # gercek sirlamayi ona gore yapiyoruz - soluklasmis kayitlar dogal
    # olarak asagi duser, sabitlenmis (pinned) kayitlar hic etkilenmez.
    # Python'un sort'u stabil oldugu icin esitliklerde SQL'in kendi
    # sirasi (importance DESC, updated_at DESC) korunuyor.
    for m in memories:
        m["effective_importance"] = _effective_importance(
            m.get("importance", 0.5), m.get("updated_at"), bool(m.get("pinned"))
        )
    memories.sort(key=lambda m: m["effective_importance"], reverse=True)
    return memories


def find_active_memory(
    user_id: int,
    category: str,
    memory_key: str,
) -> Optional[dict]:
    """
    Ayni kullanici+kategori+anahtar icin zaten aktif bir hafiza kaydi
    var mi diye bakar (kucuk/buyuk harf duyarsiz). Upsert icin kullanilir.

    NOT: karsilastirma degerini Python'un .lower()'i ile normalize edip
    gonderiyoruz (SQL'in kendi LOWER()'i ASCII-disi/Turkce karakterlerde
    guvenilir degil) - SQL tarafindaki LOWER(memory_key) sadece ekstra
    bir guvenlik agi, artik zaten depolama aninda kucuk harfe cevrilmis
    degerlerle karsilastiriyor.
    """
    memory_key = memory_key.strip().lower()

    with db_cursor() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT *
            FROM memories
            WHERE user_id = ?
            AND status = 'active'
            AND category = ?
            AND LOWER(memory_key) = ?
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

    try:
        return add_memory(
            user_id=user_id,
            category=category,
            memory_key=memory_key,
            memory_value=memory_value,
            confidence=confidence,
            importance=confidence,
            source_message_id=source_message_id,
        )
    except sqlite3.IntegrityError:
        # KENDI KENDINI INCELEME BULGUSU: bugun eklenen kismi UNIQUE
        # indeks (user_id, category, LOWER(memory_key), status='active')
        # TAM DA burada, find_active_memory ile add_memory arasindaki
        # yarista (iki neredeyse es zamanli cagri, ayni yeni bilgiyi
        # ayni anda hafizaya tasimaya calisirsa) tetiklenebilir. Onceden
        # bu exception yakalanmiyordu - extract_memory_candidate'teki
        # cagiran fonksiyona kadar cikip TUM turun geri kalan bloklarini
        # (coklu-bilgi cikariminda ayni mesajdaki diger bilgiler dahil)
        # sessizce iptal ediyordu. Artik: rakip istek zaten kaydetmis
        # demektir - o kaydi bulup GUNCELLEYEREK devam ediyoruz.
        existing = find_active_memory(user_id, category, memory_key)
        if existing:
            update_memory(
                user_id=user_id,
                memory_id=existing["id"],
                memory_value=memory_value,
                confidence=confidence,
            )
            return existing["id"]
        raise


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


def set_memory_pinned(
    user_id: int,
    memory_id: int,
    pinned: bool,
) -> bool:
    """
    DOGAL HAFIZA: kullanici bir kaydi "hep hatirla" diye sabitler/
    sabitlemeyi kaldirirsa cagrilir - sabitlenen kayit yukaridaki
    soluklasma hesabindan (_effective_importance) tamamen muaf olur.
    """
    with db_cursor(commit=True) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE memories
            SET pinned = ?
            WHERE id = ?
            AND user_id = ?
            """,
            (1 if pinned else 0, memory_id, user_id),
        )
        changed = cursor.rowcount > 0

    if changed:
        add_memory_event(
            user_id=user_id,
            memory_id=memory_id,
            event_type="pinned" if pinned else "unpinned",
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
    memories: Optional[List[dict]] = None,
) -> str:
    # VERIMLILIK INCELEMESI BULGUSU (2026-08-27): build_system_instruction
    # her turda bu fonksiyonu VE aura_lifestyle.get_lifestyle_nudges'i
    # (o da kendi icinde 4 ayri nudge fonksiyonunu) cagiriyordu - hepsi
    # AYNI kullanicinin hafizasini birbirinden habersiz, ayri ayri SQLite
    # sorgulariyla cekiyordu. `memories` onceden cekilip verilirse tekrar
    # sorgulanmiyor - davranis AYNEN korunuyor (aynen once oldugu gibi
    # importance/updated_at sirali, sadece kim cektigi degisiyor).
    if memories is None:
        memories = get_memories(user_id)
    memories = memories[:max_memories]

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

        # DOGAL HAFIZA: bir kayit belirgin sekilde soluklasmissa (ve
        # sabitlenmemisse), Aura'ya bunu KESIN bir gercek gibi degil
        # durustce belirsiz sunmasi icin isaretliyoruz - AURA_CHARACTER_
        # BIBLE'daki DOGAL_HAFIZA_ILKESI bu etiketi nasil yorumlayacagini
        # aciklar (bkz. aura_brain.py).
        base_importance = memory.get("importance", 0.5) or 0.5
        eff_importance = memory.get("effective_importance", base_importance)
        is_faded = (
            not memory.get("pinned")
            and base_importance > 0
            and eff_importance < base_importance * DECAY_UNCERTAIN_RATIO
        )
        prefix = "- [SOLUK HAFIZA] " if is_faded else f"- [{category}] "
        lines.append(prefix + value)

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
