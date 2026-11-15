"""Команды мастера/админа. Доступны только пользователям из ADMIN_IDS."""
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

import config
import views
from keyboards import cancel_list_kb

router = Router()
router.message.filter(F.from_user.id.in_(config.ADMIN_IDS))


@router.message(Command("admin"))
async def admin_panel(message: Message) -> None:
    text, items = await views.admin_list()
    await message.answer(text, reply_markup=cancel_list_kb(items))
