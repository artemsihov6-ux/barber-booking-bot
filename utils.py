"""Общие помощники: текущее время, форматирование дат, уведомления админам."""
import logging
from datetime import date, datetime

from aiogram import Bot

import config

log = logging.getLogger(__name__)

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


async def notify_admins(bot: Bot, text: str) -> None:
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text)
        except Exception as e:  # админ мог не запустить бота или заблокировать его
            log.warning("Не удалось уведомить админа %s: %s", admin_id, e)
