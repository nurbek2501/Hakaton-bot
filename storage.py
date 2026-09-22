# -*- coding: utf-8 -*-
"""
SQLite bilan ishlash.

Jadvallar:
  sessions      - har bir foydalanuvchining joriy holati (qaysi savolda, javoblari)
  submissions   - muvaffaqiyatli yuborilganlar: faqat user_id va vaqt
  registrations - (ixtiyoriy, KEEP_LOCAL_COPY=1) /export uchun javoblar nusxasi
  processed     - qayta ishlangan Telegram update’lar (bir xabar ikki marta ishlanmasin)
  clicks        - tugmani tez-tez ikki marta bosishdan himoya
"""
import functools
import json
import os
import random
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bot.db")

# O‘zbekiston vaqti (UTC+5, yozgi vaqt yo‘q)
TZ = timezone(timedelta(hours=5))

# Holatlar
IDLE = "idle"            # hech narsa to‘ldirmayapti
FILLING = "filling"      # savollarga javob beryapti
REVIEW = "review"        # xulosani ko‘ryapti, tasdiqlashi kerak
SENDING = "sending"      # Formaga yuborilmoqda (ikki marta bosishdan himoya)
FAILED = "failed"        # yuborishda xatolik, qayta yuborish kutilmoqda
STOPPED = "stopped"      # shartlarga mos kelmadi


def now_str():
    return datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S")


@contextmanager
def _conn():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()  # commit bo‘lmagan o‘zgarishlar bekor bo‘ladi (rollback)


_sleep = time.sleep


def retry_locked(fn):
    """Baza band bo‘lsa («database is locked») - butun amalni qayta urinadi.
    Bir nechta worker bir vaqtda yozganda yuz beradi (masalan, pullik tarifda 3 ta worker).
    Har bir funksiya bitta tranzaksiya: xato bo‘lsa to‘liq bekor bo‘ladi - qayta urinish xavfsiz."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        for attempt in range(6):
            try:
                return fn(*args, **kwargs)
            except sqlite3.OperationalError as e:
                msg = str(e).lower()
                if ("locked" not in msg and "busy" not in msg) or attempt == 5:
                    raise
                _sleep(random.uniform(0.05, 0.25) * (attempt + 1))
    return wrapper


def init_db():
    # WAL rejimi tarmoq fayl tizimida (PythonAnywhere) bazani buzishi mumkin, shuning uchun
    # standart (DELETE) jurnal rejimi. Baza band bo‘lsa - keyingi ishga tushishda o‘tkaziladi
    try:
        with _conn() as c:
            c.execute("PRAGMA journal_mode=DELETE")
    except sqlite3.OperationalError:
        pass
    with _conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS processed (
                k  TEXT PRIMARY KEY,
                ts REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS clicks (
                user_id INTEGER NOT NULL,
                k       TEXT    NOT NULL,
                ts      REAL    NOT NULL,
                PRIMARY KEY (user_id, k)
            );
            CREATE TABLE IF NOT EXISTS sessions (
                user_id    INTEGER PRIMARY KEY,
                status     TEXT    NOT NULL DEFAULT 'idle',
                step       INTEGER NOT NULL DEFAULT 0,
                sub        TEXT,
                answers    TEXT    NOT NULL DEFAULT '{}',
                updated_at TEXT
            );
            CREATE TABLE IF NOT EXISTS submissions (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER NOT NULL,
                submitted_at TEXT    NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_sub_user ON submissions(user_id);
            CREATE TABLE IF NOT EXISTS registrations (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER NOT NULL,
                submitted_at TEXT    NOT NULL,
                sent_to_form INTEGER NOT NULL DEFAULT 1,
                answers      TEXT    NOT NULL
            );
            """
        )
        # Eski bazaga yangi ustunlar (bir martalik migratsiya):
        #   shown    - foydalanuvchiga haqiqatan ko‘rsatilgan oxirgi savol raqami
        #   asked_id - o‘sha savol xabarining message_id si
        cols = {r["name"] for r in c.execute("PRAGMA table_info(sessions)")}
        if "shown" not in cols:
            c.execute("ALTER TABLE sessions ADD COLUMN shown INTEGER")
            c.execute("UPDATE sessions SET shown=step")
        if "asked_id" not in cols:
            c.execute("ALTER TABLE sessions ADD COLUMN asked_id INTEGER NOT NULL DEFAULT 0")


@retry_locked
def get_session(user_id, stale_minutes=10):
    """Foydalanuvchi holatini qaytaradi (yo‘q bo‘lsa - bo‘sh holat).
    Yuborish paytida server qayta ishga tushib, SENDING holatida «qotib» qolgan anketa
    10 daqiqadan keyin FAILED ga o‘tkaziladi - foydalanuvchi uni qayta yubora oladi."""
    with _conn() as c:
        row = c.execute("SELECT * FROM sessions WHERE user_id=?", (user_id,)).fetchone()
        if row and row["status"] == SENDING:
            cutoff = (datetime.now(TZ) - timedelta(minutes=stale_minutes)).strftime("%Y-%m-%d %H:%M:%S")
            if (row["updated_at"] or "") < cutoff:
                c.execute("UPDATE sessions SET status=? WHERE user_id=? AND status=?",
                          (FAILED, user_id, SENDING))
                row = c.execute("SELECT * FROM sessions WHERE user_id=?", (user_id,)).fetchone()
    if not row:
        return {"user_id": user_id, "status": IDLE, "step": 0, "sub": None, "answers": {},
                "shown": -1, "asked_id": 0}
    return {
        "user_id": row["user_id"],
        "status": row["status"],
        "step": row["step"],
        "sub": row["sub"],
        "answers": json.loads(row["answers"] or "{}"),
        "shown": row["shown"] if row["shown"] is not None else -1,
        "asked_id": row["asked_id"] or 0,
    }


@retry_locked
def mark_shown(user_id, step, message_id):
    """Savol foydalanuvchiga yetib bordi: qaysi savol va uning message_id si saqlanadi.
    Shundan oldin yuborilgan (message_id kichik) xabarlar joriy savolga javob hisoblanmaydi."""
    with _conn() as c:
        c.execute("UPDATE sessions SET shown=?, asked_id=? WHERE user_id=? AND step=?",
                  (step, message_id, user_id, step))


@retry_locked
def claim(key, keep_days=3):
    """Kalitni «band» qiladi. Birinchi marta - True, takror - False.
    Telegram bir update’ni qayta yuborsa, u ikkinchi marta ishlanmasligi uchun."""
    now = time.time()
    with _conn() as c:
        cur = c.execute("INSERT OR IGNORE INTO processed (k, ts) VALUES (?, ?)", (key, now))
        if random.random() < 0.01:  # vaqti-vaqti bilan eski yozuvlarni tozalaymiz
            c.execute("DELETE FROM processed WHERE ts < ?", (now - keep_days * 86400,))
        return cur.rowcount == 1


@retry_locked
def debounce(user_id, key, seconds=1.5):
    """Bir xil tugma `seconds` ichida qayta bosilsa - False (e’tiborsiz qoldiriladi)."""
    now = time.time()
    with _conn() as c:
        cur = c.execute("UPDATE clicks SET ts=? WHERE user_id=? AND k=? AND ts < ?",
                        (now, user_id, key, now - seconds))
        if cur.rowcount:
            return True
        cur = c.execute("INSERT OR IGNORE INTO clicks (user_id, k, ts) VALUES (?, ?, ?)",
                        (user_id, key, now))
        return cur.rowcount == 1


@retry_locked
def save_session(s):
    with _conn() as c:
        c.execute(
            """
            INSERT INTO sessions (user_id, status, step, sub, answers, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                status=excluded.status, step=excluded.step, sub=excluded.sub,
                answers=excluded.answers, updated_at=excluded.updated_at
            """,
            (s["user_id"], s["status"], s["step"], s.get("sub"),
             json.dumps(s["answers"], ensure_ascii=False), now_str()),
        )


@retry_locked
def append_item(user_id, key, item, group_id=None, limit=10):
    """Javoblar ro‘yxatiga (masalan, loyiha fayllari) bitta element qo‘shadi.
    Tranzaksiya ichida bajariladi: albomdagi fayllar bir vaqtda kelsa ham yo‘qolmaydi.
    Qaytaradi: (jami_soni, yangi_albom_mi) yoki limitdan oshsa (None, False)."""
    conn = sqlite3.connect(DB_PATH, timeout=30, isolation_level=None)
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute("SELECT answers, sub FROM sessions WHERE user_id=?",
                           (user_id,)).fetchone()
        answers = json.loads(row[0]) if row else {}
        old_sub = row[1] if row else None
        items = answers.get(key)
        items = items if isinstance(items, list) else []
        if len(items) >= limit:
            conn.execute("ROLLBACK")
            return None, False
        items.append(item)
        answers[key] = items
        new_sub = f"mg:{group_id}" if group_id else None
        conn.execute("UPDATE sessions SET answers=?, sub=?, updated_at=? WHERE user_id=?",
                     (json.dumps(answers, ensure_ascii=False), new_sub, now_str(), user_id))
        conn.execute("COMMIT")
        return len(items), not group_id or old_sub != new_sub
    except Exception:
        if conn.in_transaction:  # BEGIN ning o‘zi «band» bo‘lsa, tranzaksiya ochilmagan
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


@retry_locked
def set_status_if(user_id, expected, new_status):
    """Holatni atomar almashtiradi: faqat joriy holat `expected` ichida bo‘lsa.
    True qaytarsa - almashtirildi (ikki marta yuborishning oldini oladi)."""
    marks = ",".join("?" * len(expected))
    with _conn() as c:
        cur = c.execute(
            f"UPDATE sessions SET status=?, updated_at=? WHERE user_id=? AND status IN ({marks})",
            (new_status, now_str(), user_id, *expected),
        )
        return cur.rowcount == 1


def reset_session(user_id, status=IDLE):
    """Holatni va javoblarni tozalaydi."""
    save_session({"user_id": user_id, "status": status, "step": 0, "sub": None, "answers": {}})


@retry_locked
def mark_submitted(user_id, answers=None):
    """Muvaffaqiyatli yuborildi: shaxsiy ma’lumotlar sessiyadan o‘chiriladi,
    faqat user_id va vaqt qoladi. KEEP_LOCAL_COPY=1 bo‘lsa - nusxa registrations ga."""
    ts = now_str()
    with _conn() as c:
        c.execute("INSERT INTO submissions (user_id, submitted_at) VALUES (?, ?)", (user_id, ts))
        if answers is not None:
            c.execute(
                "INSERT INTO registrations (user_id, submitted_at, sent_to_form, answers) "
                "VALUES (?, ?, 1, ?)",
                (user_id, ts, json.dumps(answers, ensure_ascii=False)),
            )
        c.execute(
            "UPDATE sessions SET status=?, step=0, sub=NULL, answers='{}', updated_at=? "
            "WHERE user_id=?",
            (IDLE, ts, user_id),
        )


@retry_locked
def has_submitted(user_id):
    with _conn() as c:
        row = c.execute("SELECT 1 FROM submissions WHERE user_id=? LIMIT 1", (user_id,)).fetchone()
    return row is not None


@retry_locked
def stats():
    with _conn() as c:
        total = c.execute("SELECT COUNT(*) FROM submissions").fetchone()[0]
        users = c.execute("SELECT COUNT(DISTINCT user_id) FROM submissions").fetchone()[0]
        filling = c.execute("SELECT COUNT(*) FROM sessions WHERE status IN (?, ?)",
                            (FILLING, REVIEW)).fetchone()[0]
    return {"total": total, "users": users, "filling": filling, "failed": len(failed_user_ids())}


@retry_locked
def export_rows():
    """/export uchun: saqlangan nusxalar + yuborilmay qolgan javoblar.
    Qaytaradi: [(user_id, vaqt, holat, answers_dict), ...]"""
    rows = []
    with _conn() as c:
        for r in c.execute("SELECT user_id, submitted_at, answers FROM registrations ORDER BY id"):
            rows.append((r["user_id"], r["submitted_at"], "Formaga yuborilgan",
                         json.loads(r["answers"])))
        for r in c.execute("SELECT user_id, updated_at, answers FROM sessions WHERE status=?",
                           (FAILED,)):
            rows.append((r["user_id"], r["updated_at"], "Yuborilmagan (xatolik)",
                         json.loads(r["answers"])))
    return rows


@retry_locked
def failed_user_ids(stale_minutes=10):
    """Formaga yuborilmay qolganlar ro‘yxati.
    Uzoq vaqt SENDING holatida «qotib» qolganlar (masalan, yuborish paytida server qayta
    ishga tushgan bo‘lsa) ham FAILED ga o‘tkaziladi - ular ham qayta yuboriladi."""
    cutoff = (datetime.now(TZ) - timedelta(minutes=stale_minutes)).strftime("%Y-%m-%d %H:%M:%S")
    with _conn() as c:
        c.execute("UPDATE sessions SET status=? WHERE status=? AND updated_at < ?",
                  (FAILED, SENDING, cutoff))
        return [r[0] for r in c.execute(
            "SELECT user_id FROM sessions WHERE status=? ORDER BY updated_at", (FAILED,))]
