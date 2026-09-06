from aiogram import Router, F
from aiogram.types import Message
from aiogram.types import CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
import database as db

import keyboards as kb

router = Router()

class TaskFSM(StatesGroup):
    waiting_for_title = State()
    waiting_for_type = State()
    waiting_for_days = State()

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear() 
    await message.answer(
        "Главное меню. Что будем планировать?",
        reply_markup=kb.main_menu
    )

@router.message(F.text == "➕ Новая задача")
async def start_adding_task(message: Message, state: FSMContext):
    await message.answer("Напиши текст задачи:")
    await state.set_state(TaskFSM.waiting_for_title)

@router.message(TaskFSM.waiting_for_title)
async def process_task_title(message: Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer(
        f"Текст сохранен: <b>{message.text}</b>\n\nТеперь выбери тип задачи:",
        reply_markup=kb.task_type_menu,
        parse_mode="HTML"
    )
    await state.set_state(TaskFSM.waiting_for_type)

@router.callback_query(F.data.in_(["type_one_time", "type_daily"]), TaskFSM.waiting_for_type)
async def save_simple_task(callback: CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    title = user_data.get("title")
    
    task_type = "one_time" if callback.data == "type_one_time" else "daily"
    type_name = "Разовая" if task_type == "one_time" else "Ежедневная"
    
    await db.add_task(telegram_id=callback.from_user.id, title=title, task_type=task_type)
    
    await callback.message.edit_text(
        f"✅ Задача <b>«{title}»</b> добавлена!\nТип: {type_name}",
        parse_mode="HTML"
    )
    await state.clear()
    await callback.answer()

@router.callback_query(F.data == "type_weekly", TaskFSM.waiting_for_type)
async def ask_for_days(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TaskFSM.waiting_for_days)
    await callback.message.edit_text(
        "Напиши дни недели цифрами через пробел (1 - Пн, 2 - Вт... 7 - Вс).\n"
        "Например, для понедельника, среды и пятницы напиши: <b>1 3 5</b>",
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(TaskFSM.waiting_for_days)
async def save_weekly_task(message: Message, state: FSMContext):
    user_data = await state.get_data()
    title = user_data.get("title")
    week_days = message.text
    
    await db.add_task(
        telegram_id=message.from_user.id, 
        title=title, 
        task_type="weekly", 
        week_days=week_days
    )
    
    await message.answer(
        f"✅ Еженедельная задача <b>«{title}»</b> добавлена на дни: {week_days}", 
        parse_mode="HTML"
    )
    await state.clear()

# Вспомогательная функция для генерации текста и клавиатуры списка задач
async def get_tasks_presentation(telegram_id: int):
    tasks = await db.get_all_user_tasks(telegram_id)
    
    if not tasks:
        return "Твой список дел пуст! Можно отдыхать 🎉", None
        
    text = "<b>📅 Твой список задач:</b>\n"
    builder = InlineKeyboardBuilder()
    
    simple_tasks = [t for t in tasks if t.task_type in ("one_time", "daily")]
    weekly_tasks = [t for t in tasks if t.task_type == "weekly"]
    
    counter = 1
    
    if simple_tasks:
        text += "\n📌 <b>Основные (разовые и ежедневные):</b>\n"
        for task in simple_tasks:
            status = "✅" if task.is_done else "⬜️"
            icon = "🎯" if task.task_type == "one_time" else "🔄"
            text += f"{counter}. {status} {icon} {task.title}\n"
            
            if not task.is_done:
                builder.button(text=f"✓ {counter}", callback_data=f"done_{task.id}")
            counter += 1

    if weekly_tasks:
        text += "\n🗓 <b>Еженедельные задачи:</b>\n"
        for task in weekly_tasks:
            status = "✅" if task.is_done else "⬜️"
            text += f"{counter}. {status} 🔄 {task.title} <i>(дни: {task.week_days})</i>\n"
            
            if not task.is_done:
                builder.button(text=f"✓ {counter}", callback_data=f"done_{task.id}")
            counter += 1
            
    builder.adjust(4)
    return text, builder.as_markup()

# Обработчик кнопки "Список дел"
@router.message(F.text == "📅 Список дел")
async def show_tasks(message: Message):
    text, markup = await get_tasks_presentation(message.from_user.id)
    if markup:
        await message.answer(text, reply_markup=markup, parse_mode="HTML")
    else:
        await message.answer(text)

# Обработка нажатия на кнопку выполнения задачи
@router.callback_query(F.data.startswith("done_"))
async def process_task_done(callback: CallbackQuery):
    task_id = int(callback.data.split("_")[1])
    completed_task = await db.complete_task(task_id)
    
    if not completed_task:
        await callback.answer("Эта задача уже выполнена!", show_alert=True)
        return

    await callback.answer(f"✅ Готово: {completed_task.title}", show_alert=False)
    
    text, markup = await get_tasks_presentation(callback.from_user.id)
    
    if markup:
        await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    else:
        await callback.message.edit_text(text)