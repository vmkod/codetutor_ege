from aiogram import Router, types
from aiogram.filters import CommandStart

user_router = Router()


@user_router.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        f"Привет, {message.from_user.first_name}!\n\n"
        f"Я твой ИИ-помощник CodeTutor.\n"
        f"Помогу тебе разобраться с кодом на Python для задач ЕГЭ."
    )