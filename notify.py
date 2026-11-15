"""Отправка сообщений пользователям и админам в любом из запущенных мессенджеров.

Каждый бот при старте регистрирует свою функцию отправки. Общий код (напоминания,
уведомления о записях и отменах) не знает, Telegram это или MAX: он вызывает send()
с платформой, на которой клиент оформил запись.
"""
import logging
from collections.abc import Awaitable, Callable

import config

log = logging.getLogger(__name__)

Sender = Callable[[int, str], Awaitable[object]]  # (user_id, html_text)

_senders: dict[str, Sender] = {}


def register(platform: str, sender: Sender) -> None:
    _senders[platform] = sender


def unregister(platform: str) -> None:
    _senders.pop(platform, None)


def platforms() -> list[str]:
    """Мессенджеры, боты которых запущены в этом процессе."""
    return list(_senders)


async def send(platform: str, user_id: int, text: str) -> bool:
    """Отправляет сообщение и не бросает исключений: возвращает, доставлено ли оно."""
    sender = _senders.get(platform)
    if sender is None:
        log.warning("Бот %s не запущен, сообщение для %s не отправлено", platform, user_id)
        return False
    try:
        await sender(user_id, text)
    except Exception as e:  # пользователь мог не запустить бота или заблокировать его
        log.warning("Не удалось отправить сообщение %s:%s: %s", platform, user_id, e)
        return False
    return True


async def admins(text: str) -> None:
    """Уведомляет админов во всех запущенных мессенджерах."""
    for platform in platforms():
        for admin_id in config.ADMINS[platform]:
            await send(platform, admin_id, text)
