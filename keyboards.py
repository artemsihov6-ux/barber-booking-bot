"""Клавиатуры и callback-данные для inline-кнопок."""
from datetime import date, datetime

from aiogram.filters.callback_data import CallbackData
from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config
from utils import fmt_date

# --- Тексты кнопок главного меню ---
BTN_BOOK = "📅 Записаться"
BTN_MY = "🗂 Мои записи"
BTN_PRICES = "💈 Услуги и цены"
BTN_CONTACTS = "📍 Контакты"


# --- Callback-данные (aiogram сам упаковывает/распаковывает их) ---
class ServiceCb(CallbackData, prefix="srv"):
    id: str


class DateCb(CallbackData, prefix="day"):
    value: str  # YYYY-MM-DD


class TimeCb(CallbackData, prefix="tm"):
    value: str  # HHMM (двоеточие нельзя: это разделитель в callback_data)


class BackCb(CallbackData, prefix="back"):
    to: str  # services | dates


class ConfirmCb(CallbackData, prefix="cfm"):
    action: str  # yes | no


class CancelCb(CallbackData, prefix="cnl"):
    id: int


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_BOOK)],
            [KeyboardButton(text=BTN_MY), KeyboardButton(text=BTN_PRICES)],
            [KeyboardButton(text=BTN_CONTACTS)],
        ],
        resize_keyboard=True,
    )


def phone_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Отправить мой номер", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def services_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for s in config.SERVICES:
        b.button(text=f"{s.title} — {s.price} ₽", callback_data=ServiceCb(id=s.id))
    b.adjust(1)
    return b.as_markup()


def dates_kb(dates: list[date]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for d in dates:
        b.button(text=fmt_date(d), callback_data=DateCb(value=d.isoformat()))
    b.adjust(2)
    b.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=BackCb(to="services").pack()))
    return b.as_markup()


def times_kb(slots: list[datetime]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for t in slots:
        b.button(text=f"{t:%H:%M}", callback_data=TimeCb(value=f"{t:%H%M}"))
    b.adjust(4)
    b.row(InlineKeyboardButton(text="⬅️ Назад", callback_data=BackCb(to="dates").pack()))
    return b.as_markup()


def confirm_kb() -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    b.button(text="✅ Подтвердить", callback_data=ConfirmCb(action="yes"))
    b.button(text="✖️ Отмена", callback_data=ConfirmCb(action="no"))
    b.adjust(2)
    return b.as_markup()


def cancel_list_kb(bookings: list[dict]) -> InlineKeyboardMarkup:
    b = InlineKeyboardBuilder()
    for item in bookings:
        b.button(text=f"❌ Отменить #{item['id']}", callback_data=CancelCb(id=item["id"]))
    b.adjust(2)
    return b.as_markup()
