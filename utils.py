"""Общие помощники: текущее время, форматирование дат, разбор телефона."""
import re
from datetime import date, datetime

import config

WEEKDAYS = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
MONTHS = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]


def now() -> datetime:
    return datetime.now(config.TZ)


def fmt_date(d: date) -> str:
    """'пт, 7 ноября'"""
    return f"{WEEKDAYS[d.weekday()]}, {d.day} {MONTHS[d.month - 1]}"


def fmt_dt(dt: datetime) -> str:
    """'пт, 7 ноября в 14:30'"""
    return f"{fmt_date(dt.date())} в {dt:%H:%M}"


def from_ts(ts: int) -> datetime:
    return datetime.fromtimestamp(ts, config.TZ)


def normalize_phone(raw: str) -> str | None:
    """Телефон в виде '+7…' или None, если на номер это не похоже."""
    digits = re.sub(r"\D", "", raw)
    if not 10 <= len(digits) <= 15:
        return None
    return raw.strip() if raw.strip().startswith("+") else f"+{digits}"
