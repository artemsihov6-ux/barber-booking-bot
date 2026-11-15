"""Клиентская часть: меню, запись (услуга → день → время → имя → телефон → подтверждение),
просмотр и отмена своих записей."""
import asyncio
import html
import re
import time as time_mod
from datetime import date, datetime, time

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

import config
import db
from keyboards import (
    BTN_BOOK, BTN_CONTACTS, BTN_MY, BTN_PRICES,
    BackCb, CancelCb, ConfirmCb, DateCb, ServiceCb, TimeCb,
    confirm_kb, dates_kb, main_menu, phone_kb, services_kb, times_kb,
)
from slots import free_slots, is_free, working_dates
from utils import fmt_date, fmt_dt, from_ts, notify_admins
from views import booking_summary, render_admin_list, render_user_list, service_title

router = Router()

# Защита от двойного бронирования, если двое жмут «Подтвердить» одновременно.
booking_lock = asyncio.Lock()


class Booking(StatesGroup):
    name = State()
    phone = State()
    confirm = State()


# ---------- Главное меню ----------

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        f"Привет, {html.escape(message.from_user.first_name)}! 👋\n"
        f"Я бот записи в <b>{config.BUSINESS_NAME}</b>.\n\n"
        "Запишитесь в пару нажатий, а я напомню о визите заранее.",
        reply_markup=main_menu(),
    )


@router.message(Command("id"))
async def cmd_id(message: Message) -> None:
    await message.answer(f"Ваш Telegram ID: <code>{message.from_user.id}</code>")


@router.message(F.text == BTN_PRICES)
async def show_prices(message: Message) -> None:
    lines = ["💈 <b>Услуги и цены</b>", ""]
    lines += [f"• {s.title} — <b>{s.price} ₽</b> ({s.duration} мин)" for s in config.SERVICES]
    await message.answer("\n".join(lines))


@router.message(F.text == BTN_CONTACTS)
async def show_contacts(message: Message) -> None:
    await message.answer(
        f"📍 <b>{config.BUSINESS_NAME}</b>\n"
        f"Адрес: {config.ADDRESS}\n"
        f"Телефон: {config.PHONE}\n"
        f"Работаем: {config.WORK_START_HOUR}:00–{config.WORK_END_HOUR}:00"
    )


# ---------- Запись: выбор услуги, дня и времени ----------

@router.message(F.text == BTN_BOOK)
@router.message(Command("book"))
async def book_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Выберите услугу:", reply_markup=services_kb())


async def _service_from_state(state: FSMContext) -> config.Service | None:
    data = await state.get_data()
    return config.SERVICES_BY_ID.get(data.get("service_id", ""))


async def _session_expired(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.answer("Сессия устарела, начните запись заново.", show_alert=True)


async def _show_dates(callback: CallbackQuery, service: config.Service) -> None:
    dates = [d for d in working_dates() if await free_slots(d, service.duration)]
    if not dates:
        await callback.message.edit_text(
            "😔 На ближайшие дни свободных окон нет. Попробуйте позже или позвоните нам: "
            + config.PHONE
        )
        return
    await callback.message.edit_text(
        f"<b>{service.title}</b> — {service.price} ₽\n\nВыберите день:",
        reply_markup=dates_kb(dates),
    )


@router.callback_query(ServiceCb.filter())
async def pick_service(callback: CallbackQuery, callback_data: ServiceCb, state: FSMContext) -> None:
    service = config.SERVICES_BY_ID.get(callback_data.id)
    if not service:
        await callback.answer("Услуга не найдена", show_alert=True)
        return
    await state.clear()
    await state.update_data(service_id=service.id)
    await _show_dates(callback, service)
    await callback.answer()


@router.callback_query(BackCb.filter())
async def go_back(callback: CallbackQuery, callback_data: BackCb, state: FSMContext) -> None:
    if callback_data.to == "services":
        await callback.message.edit_text("Выберите услугу:", reply_markup=services_kb())
    else:
        service = await _service_from_state(state)
        if not service:
            await _session_expired(callback, state)
            return
        await _show_dates(callback, service)
    await callback.answer()


@router.callback_query(DateCb.filter())
async def pick_date(callback: CallbackQuery, callback_data: DateCb, state: FSMContext) -> None:
    service = await _service_from_state(state)
    if not service:
        await _session_expired(callback, state)
        return
    day = date.fromisoformat(callback_data.value)
    slots = await free_slots(day, service.duration)
    if not slots:
        await callback.answer("На этот день окна уже закончились", show_alert=True)
        await _show_dates(callback, service)
        return
    await state.update_data(day=day.isoformat())
    await callback.message.edit_text(
        f"<b>{service.title}</b>, {fmt_date(day)}\n\nВыберите время:",
        reply_markup=times_kb(slots),
    )
    await callback.answer()


@router.callback_query(TimeCb.filter())
async def pick_time(callback: CallbackQuery, callback_data: TimeCb, state: FSMContext) -> None:
    service = await _service_from_state(state)
    data = await state.get_data()
    if not service or "day" not in data:
        await _session_expired(callback, state)
        return
    day = date.fromisoformat(data["day"])
    hh, mm = int(callback_data.value[:2]), int(callback_data.value[2:])
    start = datetime.combine(day, time(hh, mm), tzinfo=config.TZ)

    if not await is_free(start, service.duration):
        await callback.answer("Это время уже заняли, выберите другое", show_alert=True)
        slots = await free_slots(day, service.duration)
        if slots:
            await callback.message.edit_reply_markup(reply_markup=times_kb(slots))
        else:
            await _show_dates(callback, service)
        return

    await state.update_data(start_ts=int(start.timestamp()))
    await state.set_state(Booking.name)
    await callback.message.edit_text(f"<b>{service.title}</b>, {fmt_dt(start)}")
    await callback.message.answer("Как вас зовут?", reply_markup=ReplyKeyboardRemove())
    await callback.answer()


# ---------- Запись: имя, телефон, подтверждение ----------

@router.message(Booking.name, F.text)
async def enter_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if not 2 <= len(name) <= 50:
        await message.answer("Введите имя длиной от 2 до 50 символов.")
        return
    await state.update_data(client_name=name)
    await state.set_state(Booking.phone)
    await message.answer(
        "Оставьте номер телефона: нажмите кнопку ниже или введите вручную.",
        reply_markup=phone_kb(),
    )


@router.message(Booking.phone, F.contact | F.text)
async def enter_phone(message: Message, state: FSMContext) -> None:
    raw = message.contact.phone_number if message.contact else message.text
    digits = re.sub(r"\D", "", raw)
    if not 10 <= len(digits) <= 15:
        await message.answer("Похоже, номер некорректный. Пример: +7 900 123-45-67")
        return
    phone = raw.strip() if raw.strip().startswith("+") else f"+{digits}"
    await state.update_data(phone=phone)
    await state.set_state(Booking.confirm)

    data = await state.get_data()
    service = config.SERVICES_BY_ID[data["service_id"]]
    start = from_ts(data["start_ts"])
    await message.answer("Номер сохранён ✅", reply_markup=ReplyKeyboardRemove())
    await message.answer(
        "<b>Проверьте запись:</b>\n\n"
        f"💈 {service.title} — {service.price} ₽\n"
        f"🗓 {fmt_dt(start)}\n"
        f"👤 {html.escape(data['client_name'])}\n"
        f"📞 {html.escape(phone)}",
        reply_markup=confirm_kb(),
    )


@router.callback_query(ConfirmCb.filter(), Booking.confirm)
async def confirm_booking(
    callback: CallbackQuery, callback_data: ConfirmCb, state: FSMContext, bot: Bot,
) -> None:
    if callback_data.action != "yes":
        await state.clear()
        await callback.message.edit_text("Запись отменена.")
        await callback.message.answer("Главное меню:", reply_markup=main_menu())
        await callback.answer()
        return

    data = await state.get_data()
    service = config.SERVICES_BY_ID[data["service_id"]]
    start = from_ts(data["start_ts"])

    async with booking_lock:
        if not await is_free(start, service.duration):
            await state.clear()
            await callback.message.edit_text("😔 Увы, это время только что заняли. Начните запись заново.")
            await callback.message.answer("Главное меню:", reply_markup=main_menu())
            await callback.answer()
            return
        # если до визита меньше окна напоминания, отдельное напоминание не нужно
        too_soon = data["start_ts"] - time_mod.time() <= config.REMIND_BEFORE_MIN * 60
        booking_id = await db.create_booking(
            user_id=callback.from_user.id,
            client_name=data["client_name"],
            phone=data["phone"],
            service_id=service.id,
            start_ts=data["start_ts"],
            duration=service.duration,
            reminded=too_soon,
        )

    await state.clear()
    await callback.message.edit_text(
        f"✅ <b>Вы записаны!</b> (запись #{booking_id})\n\n"
        f"💈 {service.title}\n🗓 {fmt_dt(start)}\n📍 {config.ADDRESS}\n\n"
        "Напомню о визите заранее. Отменить можно в разделе «🗂 Мои записи»."
    )
    await callback.message.answer("Главное меню:", reply_markup=main_menu())
    await callback.answer("Готово!")
    await notify_admins(
        bot,
        f"🆕 <b>Новая запись #{booking_id}</b>\n"
        f"💈 {service.title}\n🗓 {fmt_dt(start)}\n"
        f"👤 {html.escape(data['client_name'])}, 📞 {html.escape(data['phone'])}",
    )


@router.callback_query(ConfirmCb.filter())
async def confirm_stale(callback: CallbackQuery, state: FSMContext) -> None:
    await _session_expired(callback, state)


# ---------- Мои записи и отмена ----------

@router.message(F.text == BTN_MY)
@router.message(Command("my"))
async def my_bookings(message: Message) -> None:
    text, kb = await render_user_list(message.from_user.id)
    await message.answer(text, reply_markup=kb)


@router.callback_query(CancelCb.filter())
async def cancel_booking(callback: CallbackQuery, callback_data: CancelCb, bot: Bot) -> None:
    booking = await db.get_booking(callback_data.id)
    user_id = callback.from_user.id
    is_owner = booking is not None and booking["user_id"] == user_id
    is_admin = user_id in config.ADMIN_IDS

    if booking is None or not (is_owner or is_admin):
        await callback.answer("Запись не найдена", show_alert=True)
        return
    if not await db.cancel_booking(booking["id"]):
        await callback.answer("Эта запись уже отменена", show_alert=True)
        return

    await callback.answer("Запись отменена")
    text, kb = await (render_user_list(user_id) if is_owner else render_admin_list())
    await callback.message.edit_text(text, reply_markup=kb)

    summary = booking_summary(booking)
    if is_owner:
        await notify_admins(
            bot,
            f"❌ <b>Клиент отменил запись</b>\n{summary}\n"
            f"👤 {html.escape(booking['client_name'])}, 📞 {html.escape(booking['phone'])}",
        )
    else:
        try:
            await bot.send_message(
                booking["user_id"],
                f"❌ Ваша запись отменена мастером:\n{summary}\n\n"
                f"Вопросы можно задать по телефону {config.PHONE}",
            )
        except Exception:
            pass  # клиент мог заблокировать бота


# ---------- Всё остальное ----------

@router.message()
async def fallback(message: Message) -> None:
    await message.answer("Не понял вас 🙂 Воспользуйтесь меню ниже.", reply_markup=main_menu())
