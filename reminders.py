"""Фоновая задача: раз в минуту ищет записи, о которых пора напомнить."""
import asyncio
import logging
import time

from aiogram import Bot

import config
import db
from utils import fmt_dt, from_ts
from views import service_title

log = logging.getLogger(__name__)


async def send_due_reminders(bot: Bot) -> None:
    now_ts = int(time.time())
    due = await db.due_reminders(now_ts, now_ts + config.REMIND_BEFORE_MIN * 60)
    for b in due:
        try:
            await bot.send_message(
                b["user_id"],
                "⏰ <b>Напоминание</b>\n\n"
                f"Вы записаны: {service_title(b['service_id'])}\n"
                f"🗓 {fmt_dt(from_ts(b['start_ts']))}\n📍 {config.ADDRESS}\n\n"
                "Если планы поменялись, отмените запись в «🗂 Мои записи».",
            )
        except Exception as e:
            log.warning("Напоминание #%s не доставлено: %s", b["id"], e)
        await db.mark_reminded(b["id"])  # не спамим повторно даже при ошибке


async def reminder_loop(bot: Bot, interval: int = 60) -> None:
    while True:
        try:
            await send_due_reminders(bot)
        except Exception:
            log.exception("Ошибка в цикле напоминаний")
        await asyncio.sleep(interval)
