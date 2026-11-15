"""Фоновая задача: раз в минуту ищет записи, о которых пора напомнить."""
import asyncio
import logging
import time

import config
import db
import notify
import views

log = logging.getLogger(__name__)


async def send_due_reminders() -> None:
    now_ts = int(time.time())
    # только по запущенным ботам: чужие записи напомнит процесс того мессенджера
    due = await db.due_reminders(
        notify.platforms(), now_ts, now_ts + config.REMIND_BEFORE_MIN * 60,
    )
    for b in due:
        await notify.send(b["platform"], b["user_id"], views.reminder(b))
        await db.mark_reminded(b["id"])  # не спамим повторно даже при ошибке


async def reminder_loop(interval: int = 60) -> None:
    while True:
        try:
            await send_due_reminders()
        except Exception:
            log.exception("Ошибка в цикле напоминаний")
        await asyncio.sleep(interval)
