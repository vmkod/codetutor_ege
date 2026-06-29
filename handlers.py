from aiogram import Router, F, types
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.chat_action import ChatActionSender
import re

from database import get_random_task, add_user, add_task_to_db, get_bot_statistics, save_user_solution, get_user_statistics
from ai import analyze_code_with_gemini
from config import config

user_router = Router()

ADMIN_ID = int(config.admin_id.get_secret_value())


class TaskStates(StatesGroup):
    waiting_for_code = State()


class AdminStates(StatesGroup):
    waiting_for_task_number = State()
    waiting_for_condition = State()


def get_tasks_keyboard(user_id):
    builder = InlineKeyboardBuilder()
    task_numbers = [5, 8, 16, 23]

    for num in task_numbers:
        builder.button(text=f"Задание №{num}", callback_data=f"task_{num}")
    builder.adjust(2)

    builder.row(types.InlineKeyboardButton(text="Моя статистика", callback_data="user_stats"))

    if user_id == ADMIN_ID:
        builder.row(types.InlineKeyboardButton(text="Админ-панель", callback_data="admin_menu"))

    return builder.as_markup()


def get_back_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад в меню", callback_data="back_to_menu")
    return builder.as_markup()


def is_python_code(text):
    keywords = ["def", "print", "for", "while", "import", "if", "=", "range"]
    found_keywords = [word for word in keywords if word in text]
    return len(found_keywords) >= 2


def format_ai_response_to_html(text):
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r'```python\s*(.*?)\s*```', r'<pre><code class="language-python">\1</code></pre>', text,
                  flags=re.DOTALL)
    text = re.sub(r'```\s*(.*?)\s*```', r'<pre><code>\1</code></pre>', text, flags=re.DOTALL)
    text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
    text = re.sub(r'\*(.*?)\*', r'<b>\1</b>', text)

    return text


def get_admin_main_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="Добавить задание", callback_data="admin_add_task")
    builder.button(text="Статистика бота", callback_data="admin_stats")
    builder.button(text="⬅️ Выйти в меню", callback_data="back_to_menu")
    builder.adjust(1)
    return builder.as_markup()


def get_admin_back_keyboard():
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад в админку", callback_data="admin_menu")
    return builder.as_markup()


@user_router.callback_query(F.data == "admin_menu")
async def show_admin_menu(callback: types.CallbackQuery, state: FSMContext):
    try:
        admin_id = int(config.admin_id.get_secret_value())
    except (ValueError, TypeError):
        return

    if callback.from_user.id != admin_id:
        await callback.answer("У вас нет прав доступа.", show_alert=True)
        return

    await state.clear()
    await state.update_data(task_message_id=callback.message.message_id)

    await callback.answer()
    await callback.message.edit_text(
        "<b>Панель администратора</b>\n\nВыбери необходимое действие ниже:",
        parse_mode="HTML",
        reply_markup=get_admin_main_keyboard()
    )


@user_router.callback_query(F.data == "admin_add_task")
async def admin_add_task_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AdminStates.waiting_for_task_number)

    await callback.message.edit_text(
        "<b>Добавление задания</b>\n\n"
        "Введи номер задания ЕГЭ (например: 5, 8, 16, 23):",
        parse_mode="HTML",
        reply_markup=get_admin_back_keyboard()
    )


@user_router.callback_query(F.data == "admin_stats")
async def admin_show_stats(callback: types.CallbackQuery):
    await callback.answer()

    stats = get_bot_statistics()

    dist_text = ""
    if stats["distribution"]:
        for task_num, count in stats["distribution"]:
            dist_text += f"   • Задание №{task_num}: <b>{count} шт.</b>\n"
    else:
        dist_text = "   • Задач в базе пока нет.\n"

    stats_message = (
        "<b>Статистика бота</b>\n\n"
        f"Всего учеников в базе: <b>{stats['total_users']}</b>\n"
        f"Всего задач загружено: <b>{stats['total_tasks']}</b>\n\n"
        f"<b>Распределение по номерам ЕГЭ:</b>\n{dist_text}"
    )

    await callback.message.edit_text(
        stats_message,
        parse_mode="HTML",
        reply_markup=get_admin_back_keyboard()
    )


@user_router.message(AdminStates.waiting_for_task_number)
async def process_admin_task_number(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    task_message_id = user_data.get("task_message_id")

    try:
        await message.delete()
    except Exception:
        pass

    if not message.text.isdigit():
        error_text = "Номер задачи должен быть числом!\n\nВведи номер задания ЕГЭ (например: 5, 8, 16, 23):"
        if task_message_id:
            try:
                await message.bot.edit_message_text(
                    chat_id=message.chat.id, message_id=task_message_id,
                    text=error_text, reply_markup=get_admin_back_keyboard()
                )
                return
            except Exception:
                pass
        new_msg = await message.answer(error_text, reply_markup=get_admin_back_keyboard())
        await state.update_data(task_message_id=new_msg.message_id)
        return

    await state.update_data(admin_task_number=int(message.text))
    await state.set_state(AdminStates.waiting_for_condition)

    next_text = "Теперь отправь текст условия для этого задания:"

    if task_message_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id, message_id=task_message_id,
                text=next_text, parse_mode="HTML", reply_markup=get_admin_back_keyboard()
            )
            return
        except Exception:
            pass

    new_msg = await message.answer(next_text, parse_mode="HTML", reply_markup=get_admin_back_keyboard())
    await state.update_data(task_message_id=new_msg.message_id)


@user_router.message(AdminStates.waiting_for_condition)
async def process_admin_condition(message: types.Message, state: FSMContext):
    condition_text = message.text
    user_data = await state.get_data()
    task_number = user_data.get("admin_task_number")
    task_message_id = user_data.get("task_message_id")

    try:
        await message.delete()
    except Exception:
        pass

    add_task_to_db(task_number, condition_text)
    await state.clear()

    success_text = (
        f"<b>Задание успешно добавлено в базу.</b>\n\n"
        f"• <b>Номер задачи:</b> №{task_number}\n"
        f"• <b>Текст задачи:</b> {condition_text}"
    )

    if task_message_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id, message_id=task_message_id,
                text=success_text, parse_mode="HTML", reply_markup=get_admin_back_keyboard()
            )
            await state.update_data(task_message_id=task_message_id)
            return
        except Exception:
            pass

    new_msg = await message.answer(success_text, parse_mode="HTML", reply_markup=get_admin_back_keyboard())
    await state.update_data(task_message_id=new_msg.message_id)


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
        reply_markup=get_tasks_keyboard(user_id=message.from_user.id)
    )

    await state.update_data(task_message_id=start_msg.message_id)


@user_router.callback_query(F.data.startswith("task_"))
async def handle_task_selection(callback: types.CallbackQuery, state: FSMContext):
    task_number = int(callback.data.split("_")[1])
    task_condition = get_random_task(task_number)

    if task_condition:
        await callback.answer()
        await state.set_state(TaskStates.waiting_for_code)
        await state.update_data(current_task=task_number, current_task_condition=task_condition,
                                task_message_id=callback.message.message_id)

        await callback.message.edit_text(
            f"<b>Задание №{task_number}</b>\n\n"
            f"{task_condition}\n\n"
            f"<b>Отправь мне свой вариант кода на Python для этой задачи.</b>",
            parse_mode="HTML",
            reply_markup=get_back_keyboard()
        )
    else:
        await callback.answer("Произошла ошибка: задача не найдена.", show_alert=True)


@user_router.callback_query(F.data == "back_to_menu")
async def handle_back_to_menu(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()

    await callback.message.edit_text(
        f"Привет, {callback.from_user.first_name}!\n\n"
        f"Я твой ИИ-помощник CodeTutor.\n"
        f"Помогу тебе разобраться с кодом на Python для задач ЕГЭ.",
        reply_markup=get_tasks_keyboard(user_id=callback.from_user.id)
    )

    await state.update_data(task_message_id=callback.message.message_id)


@user_router.message(TaskStates.waiting_for_code)
async def handle_user_code(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    task_number = user_data.get("current_task")
    task_condition = user_data.get("current_task_condition")
    task_message_id = user_data.get("task_message_id")
    error_count = user_data.get("error_count", 0)

    user_code = message.text

    if not is_python_code(user_code):
        error_count += 1
        await state.update_data(error_count=error_count)

        if task_message_id:
            try:
                await message.bot.delete_message(chat_id=message.chat.id, message_id=task_message_id)
            except Exception:
                pass

        if error_count == 1:
            error_text = (
                f"<b>Это не похоже на код на Python!</b>\n\n"
                f"В твоем сообщении должны быть базовые конструкции языка (например: <code>def</code>, <code>print</code>, <code>for</code>).\n\n"
                f"<b>Отправь рабочее решение для Задания №{task_number}:</b>"
            )
        else:
            error_text = (
                f"<b>Все еще не вижу код на Python (Попытка {error_count})</b>\n\n"
                f"В твоем сообщении должны быть базовые конструкции языка (например: <code>def</code>, <code>print</code>, <code>for</code>).\n\n"
                f"<b>Отправь рабочее решение для Задания №{task_number}:</b>"
            )

        new_msg = await message.answer(
            error_text,
            parse_mode="HTML",
            reply_markup=get_back_keyboard()
        )

        await state.update_data(task_message_id=new_msg.message_id)
        return

    if task_message_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=task_message_id)
        except Exception:
            pass

    waiting_msg = await message.answer("<b>ИИ анализирует твой код... Пожалуйста, подожди несколько секунд.</b>", parse_mode="HTML")

    try:
        await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    except Exception:
        pass

    ai_response = await analyze_code_with_gemini(task_number, task_condition, user_code)
    save_user_solution(user_id=message.from_user.id, task_number=task_number)

    await state.clear()

    try:
        await waiting_msg.delete()
    except Exception:
        pass

    html_response = format_ai_response_to_html(ai_response)
    result_message = await message.answer(
        f"<b>Разбор Задания №{task_number}</b>\n\n"
        f"{html_response}",
        parse_mode="HTML",
        reply_markup=get_back_keyboard()
    )

    await state.update_data(task_message_id=result_message.message_id)


@user_router.callback_query(F.data == "user_stats")
async def show_user_stats(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()

    user_id = callback.from_user.id

    stats = get_user_statistics(user_id)

    dist_text = ""
    if stats["distribution"]:
        for task_num, count in stats["distribution"]:
            dist_text += f"   • Задание №{task_num}: отправлено <b>{count} раз(а)</b>\n"
    else:
        dist_text = "   • Ты пока не отправлял код на проверку.\n"

    stats_message = (
        f"<b>Твои достижения, {callback.from_user.first_name}.</b>\n\n"
        f"Всего проверено решений: <b>{stats['total_attempts']}</b>\n\n"
        f"<b>Активность по заданиям ЕГЭ:</b>\n{dist_text}\n"
        f"<i>Продолжай в том же духе, подготовка - залог успеха!</i>"
    )

    await callback.message.edit_text(
        stats_message,
        parse_mode="HTML",
        reply_markup=get_back_keyboard()
    )