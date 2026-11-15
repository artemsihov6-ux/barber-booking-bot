"""Тексты сообщений, общие для всех мессенджеров (HTML-разметка понятна и Telegram, и MAX)."""
import html

import config
import db
from utils import fmt_date, fmt_dt, from_ts, now


def service_title(service_id: str) -> str:
    service = config.SERVICES_BY_ID.get(service_id)
    return service.title if service else service_id


def booking_summary(b: dict) -> str:
    return f"#{b['id']} · {fmt_dt(from_ts(b['start_ts']))} · {service_title(b['service_id'])}"


def client_line(b: dict) -> str:
    return f"👤 {html.escape(b['client_name'])}, 📞 {html.escape(b['phone'])}"


# ---------- Меню ----------

def welcome(first_name: str) -> str:
    return (
        f"Привет, {html.escape(first_name)}! 👋\n"
        f"Я бот записи в <b>{config.BUSINESS_NAME}</b>.\n\n"
        "Запишитесь в пару нажатий, а я напомню о визите заранее."
    )


def prices() -> str:
    lines = ["💈 <b>Услуги и цены</b>", ""]
    lines += [f"• {s.title} — <b>{s.price} ₽</b> ({s.duration} мин)" for s in config.SERVICES]
    return "\n".join(lines)


def contacts() -> str:
    return (
        f"📍 <b>{config.BUSINESS_NAME}</b>\n"
        f"Адрес: {config.ADDRESS}\n"
        f"Телефон: {config.PHONE}\n"
        f"Работаем: {config.WORK_START_HOUR}:00–{config.WORK_END_HOUR}:00"
    )


# ---------- Шаги записи ----------

NO_FREE_DAYS = (
    "😔 На ближайшие дни свободных окон нет. Попробуйте позже или позвоните нам: " + config.PHONE
)
SLOT_TAKEN = "😔 Увы, это время только что заняли. Начните запись заново."


def pick_day(service: config.Service) -> str:
    return f"<b>{service.title}</b> — {service.price} ₽\n\nВыберите день:"


def pick_time(service: config.Service, day) -> str:
    return f"<b>{service.title}</b>, {fmt_date(day)}\n\nВыберите время:"


def check(data: dict) -> str:
    """Экран подтверждения. data: service_id, start_ts, client_name, phone."""
    service = config.SERVICES_BY_ID[data["service_id"]]
    return (
        "<b>Проверьте запись:</b>\n\n"
        f"💈 {service.title} — {service.price} ₽\n"
        f"🗓 {fmt_dt(from_ts(data['start_ts']))}\n"
        f"👤 {html.escape(data['client_name'])}\n"
        f"📞 {html.escape(data['phone'])}"
    )


def booked(b: dict) -> str:
    return (
        f"✅ <b>Вы записаны!</b> (запись #{b['id']})\n\n"
        f"💈 {service_title(b['service_id'])}\n🗓 {fmt_dt(from_ts(b['start_ts']))}\n"
        f"📍 {config.ADDRESS}\n\n"
        "Напомню о визите заранее. Отменить можно в разделе «🗂 Мои записи»."
    )


# ---------- Уведомления ----------

def reminder(b: dict) -> str:
    return (
        "⏰ <b>Напоминание</b>\n\n"
        f"Вы записаны: {service_title(b['service_id'])}\n"
        f"🗓 {fmt_dt(from_ts(b['start_ts']))}\n📍 {config.ADDRESS}\n\n"
        "Если планы поменялись, отмените запись в «🗂 Мои записи»."
    )


def admin_new_booking(b: dict) -> str:
    return (
        f"🆕 <b>Новая запись #{b['id']}</b> ({config.PLATFORM_TITLES[b['platform']]})\n"
        f"💈 {service_title(b['service_id'])}\n🗓 {fmt_dt(from_ts(b['start_ts']))}\n"
        + client_line(b)
    )


def admin_client_cancelled(b: dict) -> str:
    return f"❌ <b>Клиент отменил запись</b>\n{booking_summary(b)}\n{client_line(b)}"


def cancelled_by_master(b: dict) -> str:
    return (
        f"❌ Ваша запись отменена мастером:\n{booking_summary(b)}\n\n"
        f"Вопросы можно задать по телефону {config.PHONE}"
    )


# ---------- Списки записей ----------

async def user_list(platform: str, user_id: int) -> tuple[str, list[dict]]:
    """Текст и сами записи: по ним мессенджер строит кнопки отмены."""
    items = await db.user_upcoming(platform, user_id, int(now().timestamp()))
    if not items:
        return "У вас нет предстоящих записей. Нажмите «📅 Записаться» 🙂", []
    lines = ["<b>Ваши записи:</b>", ""] + [booking_summary(b) for b in items]
    return "\n".join(lines), items


async def admin_list() -> tuple[str, list[dict]]:
    items = await db.all_upcoming(int(now().timestamp()))
    if not items:
        return "🛠 <b>Админка</b>\n\nПредстоящих записей нет.", []
    lines = ["🛠 <b>Предстоящие записи:</b>", ""]
    for b in items:
        lines.append(booking_summary(b))
        lines.append(f"    {client_line(b)} · {config.PLATFORM_TITLES[b['platform']]}")
    return "\n".join(lines), items
