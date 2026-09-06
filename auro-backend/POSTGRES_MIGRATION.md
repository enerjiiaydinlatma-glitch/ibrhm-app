# SQLite → PostgreSQL geçişi (yatay ölçek)

**Amaç:** tek `aura.db` dosyası + tek konteyner = ilk trafik dalgasında kilitlenme
riski. PostgreSQL'e geçince backend yatay ölçeklenebilir (birden çok worker /
replica aynı veritabanını paylaşır).

## Mevcut durum (2026-09-06)

- `db_compat.py` eklendi: **çift-mod** bağlantı katmanı.
  - `DATABASE_URL` env **YOK** → SQLite (bugünkü davranış, **bayt-bayt aynı**).
  - `DATABASE_URL` env **VAR** → PostgreSQL (psycopg 3).
- `database.get_db()` ve `aura_memory.get_db()` artık `db_compat.get_conn()`
  çağırıyor. Çağrı yerlerindeki SQL **değişmedi**.
- `requirements.txt`'e `psycopg[binary]==3.2.3` eklendi (PG yokken kullanılmıyor).
- SQLite passthrough yerelde doğrulandı: kayıt / oturum / token çözümü /
  mesaj / feedback / `get_admin_stats` (7 adet `date('now')` sorgusu) — hepsi geçti.

## Senin yapman gereken (tek adım)

1. Railway panelinde proje → **+ New → Database → Add PostgreSQL**.
2. Railway `DATABASE_URL`'i backend servisine **otomatik enjekte eder**
   (Variables sekmesinde görünür). Elle bir şey girmene gerek yok.
3. Bana "PG eklendi" de.

## Bundan sonra bende olan doğrulama turu

`DATABASE_URL` set olunca `db_compat` PG yoluna geçer. Şu maddeleri canlıya
güvenmeden önce PG'ye karşı koşacağım:

- [ ] **Şema kurulumu:** `init_db()` + `init_memory_db()` DDL'i PG'de sorunsuz
      çalışıyor mu (`INTEGER PRIMARY KEY AUTOINCREMENT` → IDENTITY çevirisi,
      `CURRENT_TIMESTAMP`, `TIMESTAMP` tipleri).
- [ ] **Migration guard'ları:** `except sqlite3.OperationalError` blokları
      (zaten-uygulanmış migration'ı yutar) PG'de `psycopg.errors.DuplicateColumn`
      yakalamalı — `db_compat`'e ortak `OperationalError`/`IntegrityError`
      alias'ları ekleyip bu ~6 handler'ı ona bağlayacağım.
- [ ] **Tarih semantiği:** `sessions.expires_at` karşılaştırması
      (`datetime('now')`), `usage_date = date('now')` limit sorguları — PG'de
      metin/timestamp tip uyumu + UTC. Gerekirse ilgili ~10 sorguyu Python'da
      hesaplanan değer bind ederek engine-bağımsız hale getireceğim.
- [ ] **`lastrowid`:** `INSERT ... RETURNING id` enjeksiyonu tüm INSERT'lerde
      doğru id veriyor mu (özellikle `add_message`, `create_user`, `add_reminder`,
      `add_reply_feedback`).
- [ ] **Satır erişimi:** `row[0]` (pozisyonel, 4 yer) + `row["x"]` + `dict(row)`
      hepsi PG `_Row` ile çalışıyor mu.
- [ ] **Veri taşıma:** canlı `aura.db` (Railway `/data` volume) içeriğini PG'ye
      kopyalama scripti (`sqlite3 → pg`), tek seferlik, kayıpsız.
- [ ] **E2E:** üretim kopyası üzerinde kayıt→sohbet→hafıza çıkarımı→hatırlatma
      →feedback→hesap silme tam akışı.
- [ ] **Geri dönüş planı:** `DATABASE_URL`'i kaldırınca anında SQLite'a döner
      (kod değişikliği yok) — geçiş sırasında güvenlik ağı.

## Not

`db_compat.py` SQLite yolunu **kasıtlı olarak hiç değiştirmedi**. Bu dosyaları
merge etmek üretimde (PG eklenene kadar) hiçbir davranışı değiştirmez.
