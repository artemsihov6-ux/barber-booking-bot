"""Бот в MAX: меню, запись (услуга → день → время → имя → телефон → подтверждение),
просмотр и отмена своих записей, /admin для мастера.

Вся навигация идёт через inline-кнопки: нажатие перерисовывает то же сообщение.
"""
from datetime import date, datetime, time

from maxapi import F, Router
from maxapi.context import MemoryContext, State, StatesGroup
from maxapi.enums.attachment import AttachmentType
from maxapi.enums.chat_type import ChatType
from maxapi.filters.command import Command, CommandStart
from maxapi.types import BotStarted, MessageCallback, MessageCreated
from maxapi.types.attachments.buttons.attachment_button import AttachmentButton

import booking
import config
import views
from slots import free_slots, is_free, working_dates
from utils import fmt_dt, normalize_phone

from .keyboards import (
    BackCb, CancelCb, ConfirmCb, DateCb, MenuCb, ServiceCb, TimeCb,
    abort_kb, cancel_list_kb, confirm_kb, dates_kb, home_kb, main_menu, phone_kb,
    services_kb, times_kb,
)

router = Router()

MENU_TEXT = f"<b>{config.BUSINESS_NAME}</b>\n\nВыберите действие:"
PICK_SERVICE = "Выберите услугу:"


class Booking(StatesGroup):
    name = State()
    phone = State()
    confirm = State()


# ---------- Отправка ----------

async def _send(
    event: MessageCreated | MessageCallback | BotStarted,
    text: str, kb: AttachmentButton | None = None,
) -> None:
    """Новое сообщение в тот же чат, откуда пришло событие."""
    chat_id, user_id = event.get_ids()
    await event.bot.send_message(
        chat_id=chat_id,
        user_id=None if chat_id else user_id,
        text=text,
        attachments=[kb] if kb else None,
    )


async def _screen(
    event: MessageCallback, text: str, kb: AttachmentButton | None = None,
    notification: str | None = None,
) -> None:
    """Ответ на нажатие кнопки: перерисовывает сообщение, в котором она была.

    notification — короткая всплывающая подсказка поверх чата.
    """
    await event.edit(text, attachments=[kb] if kb else [], notification=notification)


# ---------- Главное меню и команды ----------

@router.bot_started()
async def bot_started(event: BotStarted, context: MemoryContext) -> None:
    """Пользователь впервые открыл бота и нажал «Начать»."""
    await context.clear()
    await _send(event, views.welcome(event.user.first_name), main_menu())


@router.message_created(CommandStart())
async def cmd_start(event: MessageCreated, context: MemoryContext) -> None:
    await context.clear()
    await _send(event, views.welcome(event.message.sender.first_name), main_menu())


@router.message_created(Command("id"))
async def cmd_id(event: MessageCreated) -> None:
    await _send(event, f"Ваш MAX ID: <code>{event.message.sender.user_id}</code>")


@router.message_created(Command("book"))
async def cmd_book(event: MessageCreated, context: MemoryContext) -> None:
    await context.clear()
    await _send(event, PICK_SERVICE, services_kb())


@router.message_created(Command("my"))
async def cmd_my(event: MessageCreated) -> None:
    text, items = await views.user_list(config.MAX, event.message.sender.user_id)
    await _send(event, text, cancel_list_kb(items, with_home=True))


@router.message_created(
    Command("admin"), F.message.sender.user_id.in_(config.MAX_ADMIN_IDS),
)
async def cmd_admin(event: MessageCreated) -> None:
    text, items = await views.admin_list()
    await _send(event, text, cancel_list_kb(items, with_home=False))


@router.message_callback(MenuCb.filter())
async def menu(event: MessageCallback, payload: MenuCb, context: MemoryContext) -> None:
    await context.clear()  # любая кнопка меню прерывает начатую запись
    if payload.action == "book":
        await _screen(event, PICK_SERVICE, services_kb())
    elif payload.action == "my":
        text, items = await views.user_list(config.MAX, event.callback.user.user_id)
        await _screen(event, text, cancel_list_kb(items, with_home=True))
    elif payload.action == "prices":
        await _screen(event, views.prices(), home_kb())
    elif payload.action == "contacts":
        await _screen(event, views.contacts(), home_kb())
    else:
        await _screen(event, MENU_TEXT, main_menu())


# ---------- Запись: выбор услуги, дня и времени ----------

async def _service_from_state(context: MemoryContext) -> config.Service | None:
    data = await context.get_data()
    return config.SERVICES_BY_ID.get(data.get("service_id", ""))


async def _session_expired(event: MessageCallback, context: MemoryContext) -> None:
    await context.clear()
    await _screen(event, "Сессия устарела, начните запись заново.", home_kb())


async def _show_dates(
    event: MessageCallback, service: config.Service, notification: str | None = None,
) -> None:
    dates = [d for d in working_dates() if await free_slots(d, service.duration)]
    if not dates:
        await _screen(event, views.NO_FREE_DAYS, home_kb(), notification)
        return
    await _screen(event, views.pick_day(service), dates_kb(dates), notification)


@router.message_callback(ServiceCb.filter())
async def pick_service(event: MessageCallback, payload: ServiceCb, context: MemoryContext) -> None:
    service = config.SERVICES_BY_ID.get(payload.id)
    if not service:
        await _screen(event, PICK_SERVICE, services_kb(), "Услуга не найдена")
        return
    await context.clear()
    await context.update_data(service_id=service.id)
    await _show_dates(event, service)


@router.message_callback(BackCb.filter())
async def go_back(event: MessageCallback, payload: BackCb, context: MemoryContext) -> None:
    if payload.to == "services":
        await _screen(event, PICK_SERVICE, services_kb())
        return
    service = await _service_from_state(context)
    if not service:
        await _session_expired(event, context)
        return
    await _show_dates(event, service)


@router.message_callback(DateCb.filter())
async def pick_date(event: MessageCallback, payload: DateCb, context: MemoryContext) -> None:
    service = await _service_from_state(context)
    if not service:
        await _session_expired(event, context)
        return
    day = date.fromisoformat(payload.value)
    slots = await free_slots(day, service.duration)
    if not slots:
        await _show_dates(event, service, "На этот день окна уже закончились")
        return
    await context.update_data(day=day.isoformat())
    await _screen(event, views.pick_time(service, day), times_kb(slots))


@router.message_callback(TimeCb.filter())
async def pick_time(event: MessageCallback, payload: TimeCb, context: MemoryContext) -> None:
    service = await _service_from_state(context)
    data = await context.get_data()
    if not service or "day" not in data:
        await _session_expired(event, context)
        return
    day = date.fromisoformat(data["day"])
    hh, mm = int(payload.value[:2]), int(payload.value[2:])
    start = datetime.combine(day, time(hh, mm), tzinfo=config.TZ)

    if not await is_free(start, service.duration):
        taken = "Это время уже заняли, выберите другое"
        slots = await free_slots(day, service.duration)
        if slots:
            await _screen(event, views.pick_time(service, day), times_kb(slots), taken)
        else:
            await _show_dates(event, service, taken)
        return

    await context.update_data(start_ts=int(start.timestamp()))
    await context.set_state(Booking.name)
    await _screen(
        event, f"<b>{service.title}</b>, {fmt_dt(start)}\n\nКак вас зовут?", abort_kb(),
    )


# ---------- Запись: имя, телефон, подтверждение ----------

@router.message_created(Booking.name, F.message.body.text)
async def enter_name(event: MessageCreated, context: MemoryContext) -> None:
    name = event.message.body.text.strip()
    if not 2 <= len(name) <= 50:
        await _send(event, "Введите имя длиной от 2 до 50 символов.", abort_kb())
        return
    await context.update_data(client_name=name)
    await context.set_state(Booking.phone)
    await _send(
        event, "Оставьте номер телефона: нажмите кнопку ниже или введите вручную.", phone_kb(),
    )


def _contact_phone(event: MessageCreated) -> str | None:
    """Телефон из контакта, которым пользователь поделился по кнопке."""
    for att in event.message.body.attachments or []:
        if getattr(att, "type", None) == AttachmentType.CONTACT:
            vcf = getattr(getattr(att, "payload", None), "vcf", None)
            if vcf and vcf.phone:
                return vcf.phone
    return None


@router.message_created(Booking.phone)
async def enter_phone(event: MessageCreated, context: MemoryContext) -> None:
    phone = normalize_phone(_contact_phone(event) or event.message.body.text or "")
    if not phone:
        await _send(event, "Похоже, номер некорректный. Пример: +7 900 123-45-67", phone_kb())
        return
    data = await context.update_data(phone=phone)
    await context.set_state(Booking.confirm)
    await _send(event, views.check(data), confirm_kb())


@router.message_callback(ConfirmCb.filter(F.action == "no"))
async def abort_booking(event: MessageCallback, context: MemoryContext) -> None:
    # кнопка «Отмена» остаётся и в старых сообщениях: тогда просто показываем меню
    in_progress = await context.get_state() is not None
    await context.clear()
    await _screen(event, "Запись не оформлена." if in_progress else MENU_TEXT, main_menu())


@router.message_callback(ConfirmCb.filter(), Booking.confirm)
async def confirm_booking(event: MessageCallback, context: MemoryContext) -> None:
    data = await context.get_data()
    await context.clear()
    created = await booking.create(
        platform=config.MAX,
        user_id=event.callback.user.user_id,
        client_name=data["client_name"],
        phone=data["phone"],
        service=config.SERVICES_BY_ID[data["service_id"]],
        start_ts=data["start_ts"],
    )
    if not created:
        await _screen(event, views.SLOT_TAKEN, main_menu())
        return
    await _screen(event, views.booked(created), notification="Готово!")
    await _send(event, MENU_TEXT, main_menu())


@router.message_callback(ConfirmCb.filter())
async def confirm_stale(event: MessageCallback, context: MemoryContext) -> None:
    await _session_expired(event, context)


# ---------- Отмена записи ----------

@router.message_callback(CancelCb.filter())
async def cancel_booking(event: MessageCallback, payload: CancelCb) -> None:
    user_id = event.callback.user.user_id
    result = await booking.cancel(payload.id, config.MAX, user_id)
    if result is booking.Cancel.NOT_FOUND:
        await event.ack("Запись не найдена")
    elif result is booking.Cancel.ALREADY:
        await event.ack("Эта запись уже отменена")
    elif result is booking.Cancel.BY_OWNER:
        text, items = await views.user_list(config.MAX, user_id)
        await _screen(event, text, cancel_list_kb(items, with_home=True), "Запись отменена")
    else:
        text, items = await views.admin_list()
        await _screen(event, text, cancel_list_kb(items, with_home=False), "Запись отменена")


# ---------- Всё остальное ----------

@router.message_created(F.message.recipient.chat_type == ChatType.DIALOG)
async def fallback(event: MessageCreated) -> None:
    await _send(event, "Не понял вас 🙂 Воспользуйтесь меню ниже.", main_menu())
