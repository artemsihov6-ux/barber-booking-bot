"""Тексты списков записей для клиента и для админа."""
import html

from aiogram.types import InlineKeyboardMarkup

import config
import db
from keyboards import cancel_list_kb
from utils import fmt_dt, from_ts, now


def service_title(service_id: str) -> str:
    service = config.SERVICES_BY_ID.get(service_id)
    return service.title if service else service_id


def booking_summary(b: dict) -> str:
    return f"#{b['id']} · {fmt_dt(from_ts(b['start_ts']))} · {service_title(b['service_id'])}"


async def render_user_list(user_id: int) -> tuple[str, InlineKeyboardMarkup | None]:
    items = await db.user_upcoming(user_id, int(now().timestamp()))
    if not items:
        return "У вас нет предстоящих записей. Нажмите «📅 Записаться» 🙂", None
    lines = ["<b>Ваши записи:</b>", ""] + [booking_summary(b) for b in items]
    return "\n".join(lines), cancel_list_kb(items)


async def render_admin_list() -> tuple[str, InlineKeyboardMarkup | None]:
    items = await db.all_upcoming(int(now().timestamp()))
    if not items:
        return "🛠 <b>Админка</b>\n\nПредстоящих записей нет.", None
    lines = ["🛠 <b>Предстоящие записи:</b>", ""]
    for b in items:
        lines.append(booking_summary(b))
        lines.append(f"    👤 {html.escape(b['client_name'])}, 📞 {html.escape(b['phone'])}")
    return "\n".join(lines), cancel_list_kb(items)
