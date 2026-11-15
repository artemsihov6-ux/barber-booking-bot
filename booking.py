"""Создание и отмена записи: общая логика для всех мессенджеров, включая уведомления."""
import asyncio
import time
from enum import Enum

import config
import db
import notify
import views
from slots import is_free
from utils import from_ts

# Защита от двойного бронирования, если двое жмут «Подтвердить» одновременно
# (в том числе один в Telegram, другой в MAX).
_lock = asyncio.Lock()


async def create(
    platform: str, user_id: int, client_name: str, phone: str,
    service: config.Service, start_ts: int,
) -> dict | None:
    """Создаёт запись и уведомляет админов. None, если это время уже заняли."""
    async with _lock:
        if not await is_free(from_ts(start_ts), service.duration):
            return None
        # если до визита меньше окна напоминания, отдельное напоминание не нужно
        too_soon = start_ts - time.time() <= config.REMIND_BEFORE_MIN * 60
        booking_id = await db.create_booking(
            platform=platform,
            user_id=user_id,
            client_name=client_name,
            phone=phone,
            service_id=service.id,
            start_ts=start_ts,
            duration=service.duration,
            reminded=too_soon,
        )
    booking = await db.get_booking(booking_id)
    await notify.admins(views.admin_new_booking(booking))
    return booking


class Cancel(Enum):
    NOT_FOUND = "not_found"   # записи нет или она чужая
    ALREADY = "already"       # уже отменена
    BY_OWNER = "owner"        # отменил сам клиент
    BY_ADMIN = "admin"        # отменил мастер


async def cancel(booking_id: int, platform: str, user_id: int) -> Cancel:
    """Отменяет запись от имени пользователя user_id и рассылает уведомления."""
    b = await db.get_booking(booking_id)
    is_owner = b is not None and b["platform"] == platform and b["user_id"] == user_id
    is_admin = user_id in config.ADMINS[platform]

    if b is None or not (is_owner or is_admin):
        return Cancel.NOT_FOUND
    if not await db.cancel_booking(booking_id):
        return Cancel.ALREADY

    if is_owner:
        await notify.admins(views.admin_client_cancelled(b))
        return Cancel.BY_OWNER
    # клиент мог записаться в другом мессенджере: пишем туда, где он оформил запись
    await notify.send(b["platform"], b["user_id"], views.cancelled_by_master(b))
    return Cancel.BY_ADMIN
