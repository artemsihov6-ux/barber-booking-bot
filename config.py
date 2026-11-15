"""Настройки бота. Всё, что меняется под конкретного клиента, лежит здесь."""
import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()



def _ids(name: str) -> set[int]:
    return {int(x) for x in os.getenv(name, "").replace(" ", "").split(",") if x}


# --- Мессенджеры ---
TG = "tg"
MAX = "max"
PLATFORM_TITLES = {TG: "Telegram", MAX: "MAX"}

# --- Секреты и окружение (берутся из .env) ---
# Запускаются те боты, для которых задан токен: Telegram, MAX или оба сразу.
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS = _ids("ADMIN_IDS")
MAX_BOT_TOKEN = os.getenv("MAX_BOT_TOKEN", "").strip()
MAX_ADMIN_IDS = _ids("MAX_ADMIN_IDS")
ADMINS = {TG: ADMIN_IDS, MAX: MAX_ADMIN_IDS}
TZ =ZoneInfo(os.getenv("TIMEZONE", "Europe/Moscow"))
DB_PATH = os.getenv("DB_PATH", "bookings.db")

# --- Информация о бизнесе ---
BUSINESS_NAME = "BarberShop «Борода»"
ADDRESS = "г. Москва, ул. Примерная, 1"
PHONE = "+7 (900) 000-00-00"

# --- Расписание ---
WORK_DAYS = {0, 1, 2, 3, 4, 5}  # 0 = понедельник ... 6 = воскресенье
WORK_START_HOUR = 10            # открытие
WORK_END_HOUR = 20              # закрытие (последняя услуга должна закончиться к этому часу)
SLOT_STEP_MIN = 30              # шаг сетки времени
DAYS_AHEAD = 7                  # на сколько дней вперёд можно записаться
REMIND_BEFORE_MIN = 120         # за сколько минут напоминать клиенту


@dataclass(frozen=True)
class Service:
    id: str
    title: str
    price: int      # ₽
    duration: int   # минуты


SERVICES = [
    Service("cut", "Мужская стрижка", 1500, 60),
    Service("beard", "Стрижка бороды", 900, 30),
    Service("combo", "Стрижка + борода", 2200, 90),
    Service("kids", "Детская стрижка", 1000, 30),
]
SERVICES_BY_ID = {s.id: s for s in SERVICES}
