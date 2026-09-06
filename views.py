import datetime
import pytz
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
    waiting_for_time = State() # Новое состояние для времени

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
    # Вместо сохранения в базу, запоминаем тип и просим время
    task_type = "one_time" if callback.data == "type_one_time" else "daily"
    await state.update_data(task_type=task_type)
    
    user_data = await state.get_data()
    title = user_data.get("title")
    
    await ask_for_time(callback, state, title)

@router.callback_query(F.data == "type_weekly", TaskFSM.waiting_for_type)
async def ask_for_days(callback: CallbackQuery, state: FSMContext):
    await state.update_data(task_type="weekly")
    await state.set_state(TaskFSM.waiting_for_days)
    await callback.message.edit_text(
        "Напиши дни недели цифрами через пробел (1 - Пн, 2 - Вт... 7 - Вс).\n"
        "Например, для понедельника, среды и пятницы напиши: <b>1 3 5</b>",
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(TaskFSM.waiting_for_days)
async def process_weekly_days(message: Message, state: FSMContext):
    # Запоминаем дни и просим время
    await state.update_data(week_days=message.text)
    user_data = await state.get_data()
    title = user_data.get("title")
    
    await ask_for_time(message, state, title)

# Общая функция для запроса времени
async def ask_for_time(message_or_callback, state: FSMContext, title: str):
    await state.set_state(TaskFSM.waiting_for_time)
    text = (
        f"Задача <b>«{title}»</b> почти готова.\n\n"
        "Во сколько напомнить? (Напиши время в формате ЧЧ:ММ, например 14:30).\n"
        "Если напоминание не нужно, напиши <b>0</b>."
    )
    if isinstance(message_or_callback, CallbackQuery):
        await message_or_callback.message.edit_text(text, parse_mode="HTML")
        await message_or_callback.answer()
    else:
        await message_or_callback.answer(text, parse_mode="HTML")

# Финальный шаг: получение времени и сохранение в базу
@router.message(TaskFSM.waiting_for_time)
async def finish_task_creation(message: Message, state: FSMContext):
    user_data = await state.get_data()
    title = user_data.get("title")
    task_type = user_data.get("task_type")
    week_days = user_data.get("week_days")
    
    reminder_time = None
    if message.text != "0":
        reminder_time = message.text # Ожидаем формат 14:30
        
    await db.add_task(
        telegram_id=message.from_user.id,
        title=title,
        task_type=task_type,
        week_days=week_days,
        reminder_time=reminder_time
    )
    
    await message.answer(f"✅ Задача <b>«{title}»</b> успешно создана!", parse_mode="HTML")
    await state.clear()

# Вспомогательная функция с динамической сортировкой по дням
async def get_tasks_presentation(telegram_id: int):
    tasks = await db.get_all_user_tasks(telegram_id)
    
    if not tasks:
        return "Твой список дел пуст! Можно отдыхать 🎉", None
        
    # Определяем текущий и завтрашний день недели по времени Бишкека
    tz = pytz.timezone("Asia/Bishkek")
    now = datetime.datetime.now(tz)
    today_iso = now.isoweekday()
    
    today_str = str(today_iso)
    tomorrow_str = str((today_iso % 7) + 1)
    
    tasks_today = []
    tasks_tomorrow = []
    tasks_other = []
    
    # Сортируем задачи
    for task in tasks:
        if task.task_type in ("one_time", "daily"):
            tasks_today.append(task)
        elif task.task_type == "weekly" and task.week_days:
            days = task.week_days.split()
            if today_str in days:
                tasks_today.append(task)
            elif tomorrow_str in days:
                tasks_tomorrow.append(task)
            else:
                tasks_other.append(task)

    text = "<b>📅 Твой список задач:</b>\n"
    builder = InlineKeyboardBuilder()
    counter = 1
    
    def render_group(group_tasks, group_title):
        nonlocal text, counter
        if not group_tasks:
            return
            
        text += f"\n{group_title}\n"
        for task in group_tasks:
            status = "✅" if task.is_done else "⬜️"
            icon = "🎯" if task.task_type == "one_time" else "🔄"
            
            # Выводим время, если оно есть (обрабатываем через getattr для совместимости, если колонка еще пустая)
            time_val = getattr(task, 'reminder_time', None)
            time_str = f" <i>({time_val})</i>" if time_val else ""
            
            days_str = f" <i>(дни: {task.week_days})</i>" if task.task_type == "weekly" and group_tasks == tasks_other else ""
            
            text += f"{counter}. {status} {icon} {task.title}{time_str}{days_str}\n"
            
            if not task.is_done:
                builder.button(text=f"✓ {counter}", callback_data=f"done_{task.id}")
            counter += 1

    render_group(tasks_today, "📌 <b>На сегодня:</b>")
    render_group(tasks_tomorrow, "🗓 <b>На завтра:</b>")
    render_group(tasks_other, "📅 <b>Еженедельные (другие дни):</b>")
            
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