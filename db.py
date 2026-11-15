"""Работа с базой SQLite: создание таблицы и все запросы к записям."""
import time

import aiosqlite

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS bookings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    client_name TEXT    NOT NULL,
    phone       TEXT    NOT NULL,
    service_id  TEXT    NOT NULL,
    start_ts    INTEGER NOT NULL,          -- unix-время начала
    duration    INTEGER NOT NULL,          -- минуты
    status      TEXT    NOT NULL DEFAULT 'active',  -- active | cancelled
    reminded    INTEGER NOT NULL DEFAULT 0,
    created_at  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_bookings_start ON bookings(start_ts);
CREATE INDEX IF NOT EXISTS idx_bookings_user ON bookings(user_id);
"""


async def init_db() -> None:
    async with aiosqlite.connect(config.DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()


async def _fetch(query: str, params: tuple = ()) -> list[dict]:
    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cur:
            return [dict(row) for row in await cur.fetchall()]


async def _execute(query: str, params: tuple = ()) -> tuple[int, int]:
    """Возвращает (lastrowid, rowcount)."""
    async with aiosqlite.connect(config.DB_PATH) as db:
        cur = await db.execute(query, params)
        await db.commit()
        return cur.lastrowid, cur.rowcount


async def bookings_between(start_ts: int, end_ts: int) -> list[dict]:
    return await _fetch(
        "SELECT * FROM bookings WHERE status = 'active' AND start_ts >= ? AND start_ts < ?",
        (start_ts, end_ts),
    )


async def create_booking(
    user_id: int, client_name: str, phone: str, service_id: str,
    start_ts: int, duration: int, reminded: bool,
) -> int:
    booking_id, _ = await _execute(
        """INSERT INTO bookings
           (user_id, client_name, phone, service_id, start_ts, duration, reminded, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (user_id, client_name, phone, service_id, start_ts, duration,
         int(reminded), int(time.time())),
    )
    return booking_id


async def get_booking(booking_id: int) -> dict | None:
    rows = await _fetch("SELECT * FROM bookings WHERE id = ?", (booking_id,))
    return rows[0] if rows else None


async def user_upcoming(user_id: int, now_ts: int) -> list[dict]:
    return await _fetch(
        """SELECT * FROM bookings
           WHERE user_id = ? AND status = 'active' AND start_ts > ?
           ORDER BY start_ts""",
        (user_id, now_ts),
    )


async def all_upcoming(now_ts: int, limit: int = 30) -> list[dict]:
    return await _fetch(
        """SELECT * FROM bookings
           WHERE status = 'active' AND start_ts > ?
           ORDER BY start_ts LIMIT ?""",
        (now_ts, limit),
    )


async def cancel_booking(booking_id: int) -> bool:
    _, changed = await _execute(
        "UPDATE bookings SET status = 'cancelled' WHERE id = ? AND status = 'active'",
        (booking_id,),
    )
    return changed > 0


async def due_reminders(now_ts: int, until_ts: int) -> list[dict]:
    return await _fetch(
        """SELECT * FROM bookings
           WHERE status = 'active' AND reminded = 0 AND start_ts > ? AND start_ts <= ?""",
        (now_ts, until_ts),
    )


async def mark_reminded(booking_id: int) -> None:
    await _execute("UPDATE bookings SET reminded = 1 WHERE id = ?", (booking_id,))
