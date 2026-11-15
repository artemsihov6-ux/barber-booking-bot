"""Клавиатуры MAX. Здесь нет нижней клавиатуры, как в Telegram: всё меню на inline-кнопках."""
from datetime import date, datetime

from maxapi.enums.intent import Intent
from maxapi.filters.callback_payload import CallbackPayload
from maxapi.types import CallbackButton, RequestContactButton
from maxapi.types.attachments.buttons.attachment_button import AttachmentButton
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder

import config
from utils import fmt_date


# --- Данные кнопок (maxapi сам упаковывает/распаковывает их, разделитель «|») ---
class MenuCb(CallbackPayload, prefix="menu"):
    action: str  # home | book | my | prices | contacts


class ServiceCb(CallbackPayload, prefix="srv"):
    id: str


class DateCb(CallbackPayload, prefix="day"):
    value: str  # YYYY-MM-DD


class TimeCb(CallbackPayload, prefix="tm"):
    value: str  # HHMM


class BackCb(CallbackPayload, prefix="back"):
    to: str  # services | dates


class ConfirmCb(CallbackPayload, prefix="cfm"):
    action: str  # yes | no


class CancelCb(CallbackPayload, prefix="cnl"):
    id: int


def _btn(text: str, payload: CallbackPayload, intent: Intent = Intent.DEFAULT) -> CallbackButton:
    return CallbackButton(text=text, payload=payload.pack(), intent=intent)


def _home() -> CallbackButton:
    return _btn("⬅️ В меню", MenuCb(action="home"))


def main_menu() -> AttachmentButton:
    b = InlineKeyboardBuilder()
    b.row(_btn("📅 Записаться", MenuCb(action="book"), Intent.POSITIVE))
    b.row(
        _btn("🗂 Мои записи", MenuCb(action="my")),
        _btn("💈 Услуги и цены", MenuCb(action="prices")),
    )
    b.row(_btn("📍 Контакты", MenuCb(action="contacts")))
    return b.as_markup()


def home_kb() -> AttachmentButton:
    return InlineKeyboardBuilder().row(_home()).as_markup()


def services_kb() -> AttachmentButton:
    b = InlineKeyboardBuilder()
    for s in config.SERVICES:
        b.row(_btn(f"{s.title} — {s.price} ₽", ServiceCb(id=s.id)))
    b.row(_home())
    return b.as_markup()


def _grid(buttons: list[CallbackButton], width: int, *last_row: CallbackButton) -> AttachmentButton:
    b = InlineKeyboardBuilder()
    for i in range(0, len(buttons), width):
        b.row(*buttons[i:i + width])
    if last_row:
        b.row(*last_row)
    return b.as_markup()


def dates_kb(dates: list[date]) -> AttachmentButton:
    buttons = [_btn(fmt_date(d), DateCb(value=d.isoformat())) for d in dates]
    return _grid(buttons, 2, _btn("⬅️ Назад", BackCb(to="services")))


def times_kb(slots: list[datetime]) -> AttachmentButton:
    buttons = [_btn(f"{t:%H:%M}", TimeCb(value=f"{t:%H%M}")) for t in slots]
    return _grid(buttons, 4, _btn("⬅️ Назад", BackCb(to="dates")))


def _abort() -> CallbackButton:
    return _btn("✖️ Отмена", ConfirmCb(action="no"), Intent.NEGATIVE)


def abort_kb() -> AttachmentButton:
    return InlineKeyboardBuilder().row(_abort()).as_markup()


def phone_kb() -> AttachmentButton:
    b = InlineKeyboardBuilder()
    b.row(RequestContactButton(text="📱 Отправить мой номер"))
    b.row(_abort())
    return b.as_markup()


def confirm_kb() -> AttachmentButton:
    b = InlineKeyboardBuilder()
    b.row(_btn("✅ Подтвердить", ConfirmCb(action="yes"), Intent.POSITIVE), _abort())
    return b.as_markup()


def cancel_list_kb(bookings: list[dict], *, with_home: bool) -> AttachmentButton | None:
    buttons = [_btn(f"❌ Отменить #{b['id']}", CancelCb(id=b["id"])) for b in bookings]
    if not buttons and not with_home:
        return None
    return _grid(buttons, 2, *([_home()] if with_home else []))
