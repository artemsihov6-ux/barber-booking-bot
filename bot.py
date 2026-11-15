"""Точка входа: python bot.py

Запускает ботов тех мессенджеров, для которых в .env задан токен: Telegram (BOT_TOKEN),
MAX (MAX_BOT_TOKEN) или оба сразу. База и расписание у них общие.
"""
import asyncio
import contextlib
import logging
import signal

import config
import db
import notify
from reminders import reminder_loop

log = logging.getLogger(__name__)


async def run_telegram() -> None:
    from aiogram import Bot, Dispatcher
    from aiogram.client.default import DefaultBotProperties
    from aiogram.enums import ParseMode
    from aiogram.fsm.storage.memory import MemoryStorage
    from aiogram.types import BotCommand

    from handlers import admin, client

    bot = Bot(config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(admin.router)   # админский роутер первым, чтобы /admin не съел fallback
    dp.include_router(client.router)

    notify.register(config.TG, lambda user_id, text: bot.send_message(user_id, text))
    try:
        await bot.set_my_commands([
            BotCommand(command="start", description="Главное меню"),
            BotCommand(command="book", description="Записаться"),
            BotCommand(command="my", description="Мои записи"),
        ])
        # сигналы остановки обрабатывает main(): он гасит сразу всех ботов
        await dp.start_polling(bot, handle_signals=False)
    finally:
        notify.unregister(config.TG)
        await bot.session.close()


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    runners = {}
    if config.BOT_TOKEN:
        runners[config.TG] = run_telegram
    if config.MAX_BOT_TOKEN:
        from max_bot.app import run as run_max
        runners[config.MAX] = run_max
    if not runners:
        raise SystemExit(
            "Не задан ни BOT_TOKEN, ни MAX_BOT_TOKEN. Скопируй .env.example в .env и вставь токен."
        )
    for platform in runners:
        if not config.ADMINS[platform]:
            log.warning(
                "%s: список админов пуст, уведомления о записях туда не придут. "
                "Узнай свой ID командой /id.", config.PLATFORM_TITLES[platform],
            )

    await db.init_db()

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):  # Windows: остаётся Ctrl+C
            loop.add_signal_handler(sig, stop.set)

    tasks = [
        asyncio.create_task(run(), name=config.PLATFORM_TITLES[platform])
        for platform, run in runners.items()
    ]
    tasks.append(asyncio.create_task(reminder_loop(), name="reminders"))
    stopper = asyncio.create_task(stop.wait(), name="stop")
    try:
        # работаем до сигнала остановки или пока один из ботов не упадёт
        await asyncio.wait([*tasks, stopper], return_when=asyncio.FIRST_COMPLETED)
    finally:
        failed = [t for t in tasks if t.done() and not t.cancelled() and t.exception()]
        for t in (*tasks, stopper):
            t.cancel()
        await asyncio.gather(*tasks, stopper, return_exceptions=True)
    for t in failed:
        log.error("Бот %s остановился с ошибкой", t.get_name(), exc_info=t.exception())
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
