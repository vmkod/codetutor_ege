from aiogram import Router, types
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

from database import get_random_task, add_user

user_router = Router()


class TaskStates(StatesGroup):
    waiting_for_code = State()


def get_tasks_keyboard():
    builder = InlineKeyboardBuilder()
    task_numbers = [5, 8, 16, 23]
    for num in task_numbers:
        builder.button(text=f"Задание №{num}", callback_data=f"task_{num}")
    builder.adjust(2)
    return builder.as_markup()


def get_back_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад в меню", callback_data="back_to_menu")
    return builder.as_markup()


def is_python_code(text):
    keywords = ["def", "print", "for", "while", "import", "if", "=", "range"]
    found_keywords = [word for word in keywords if word in text]
    return len(found_keywords) >= 2


@user_router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    task_message_id = user_data.get("task_message_id")

    if task_message_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=task_message_id)
        except Exception:
            pass

    await state.clear()

    add_user(
        user_id=message.from_user.id,
        username=message.from_user.username,
        first_name=message.from_user.first_name
    )

    start_msg = await message.answer(
        f"Привет, {message.from_user.first_name}!\n\n"
        f"Я твой ИИ-помощник CodeTutor.\n"
        f"Помогу тебе разобраться с кодом на Python для задач ЕГЭ.",
        reply_markup=get_tasks_keyboard()
    )

    await state.update_data(task_message_id=start_msg.message_id)


@user_router.callback_query(lambda c: c.data.startswith("task_"))
async def handle_task_selection(callback: types.CallbackQuery, state: FSMContext):
    task_number = int(callback.data.split("_")[1])
    task_condition = get_random_task(task_number)

    if task_condition:
        await callback.answer()
        await state.set_state(TaskStates.waiting_for_code)

        await state.update_data(current_task=task_number, task_message_id=callback.message.message_id)

        await callback.message.edit_text(
            f"📋 <b>Задание №{task_number}</b>\n\n"
            f"{task_condition}\n\n"
            f"<b>Отправь мне свой вариант кода на Python для этой задачи.</b>",
            parse_mode="HTML",
            reply_markup=get_back_keyboard()
        )
    else:
        await callback.answer("Произошла ошибка: задача не найдена.", show_alert=True)


@user_router.callback_query(lambda c: c.data == "back_to_menu")
async def handle_back_to_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()

    await callback.message.edit_text(
        f"Привет, {callback.from_user.first_name}!\n\n"
        f"Я твой ИИ-помощник CodeTutor.\n"
        f"Помогу тебе разобраться с кодом на Python для задач ЕГЭ.",
        reply_markup=get_tasks_keyboard()
    )

    await state.update_data(task_message_id=callback.message.message_id)


@user_router.message(TaskStates.waiting_for_code)
async def handle_user_code(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    task_number = user_data.get("current_task")
    task_message_id = user_data.get("task_message_id")

    error_count = user_data.get("error_count", 0)

    user_code = message.text

    if not is_python_code(user_code):
        error_count += 1
        await state.update_data(error_count=error_count)

        if error_count == 1:
            error_text = (
                f"❌ <b>Это не похоже на код на Python!</b>\n\n"
                f"В твоем сообщении должны быть базовые конструкции языка (например: <code>def</code>, <code>print</code>, <code>for</code>).\n\n"
                f"<b>Отправь рабочее решение для Задания №{task_number} или вернись в меню:</b>"
            )
        else:
            error_text = (
                f"⚠️ <b>Все еще не вижу код на Python (Попытка {error_count})</b>\n\n"
                f"В твоем сообщении должны быть базовые конструкции языка (например: <code>def</code>, <code>print</code>, <code>for</code>).\n\n"
                f"<b>Отправь рабочее решение для Задания №{task_number} или вернись в меню:</b>"
            )

        if task_message_id:
            try:
                await message.bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=task_message_id,
                    text=error_text,
                    parse_mode="HTML",
                    reply_markup=get_back_keyboard()
                )
            except Exception:
                new_msg = await message.answer(error_text, parse_mode="HTML", reply_markup=get_back_keyboard())
                await state.update_data(task_message_id=new_msg.message_id)

        return

    if task_message_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=task_message_id)
        except Exception:
            pass

    await state.clear()

    await message.answer(
        f"✅ Код для задания №{task_number} успешно принят на проверку!\n\n"
        f"Твой код: {user_code}.\n\n"
        f"Здесь будет ИИ-анализ, который разберет решение.",
        reply_markup=get_back_keyboard()
    )
