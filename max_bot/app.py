"""Запуск бота в мессенджере MAX (long polling)."""
import logging

from maxapi import Bot, Dispatcher
from maxapi.enums.parse_mode import ParseMode
from maxapi.types import BotCommand

import config
import notify

from .handlers import router

log = logging.getLogger(__name__)


async def run() -> None:
    # auto_requests=False: не дёргать API за данными чата на каждое событие, они нам не нужны
    bot = Bot(config.MAX_BOT_TOKEN, parse_mode=ParseMode.HTML, auto_requests=False)
    dp = Dispatcher()
    dp.include_routers(router)

    notify.register(config.MAX, lambda user_id, text: bot.send_message(user_id=user_id, text=text))
    try:
        try:
            await bot.set_commands(
                BotCommand(name="start", description="Главное меню"),
                BotCommand(name="book", description="Записаться"),
                BotCommand(name="my", description="Мои записи"),
            )
        except Exception as e:  # подсказки команд необязательны, бот работает и без них
            log.warning("Не удалось задать список команд MAX: %s", e)
        await dp.start_polling(bot)
    finally:
        notify.unregister(config.MAX)
        await bot.close_session()
