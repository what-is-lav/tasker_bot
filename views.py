from aiogram import Router, F
from aiogram.types import Message
from aiogram.types import CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
import database as db

import keyboards as kb

# Роутер заменяет диспетчер (dp) внутри отдельных файлов
router = Router()

# Описываем шаги машины состояний
class TaskFSM(StatesGroup):
    waiting_for_title = State()
    waiting_for_type = State()
    waiting_for_days = State()  # Понадобится только для еженедельных задач

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    # Сбрасываем состояние на случай, если юзер нажал /start посреди создания задачи
    await state.clear() 
    await message.answer(
        "Главное меню. Что будем планировать?",
        reply_markup=kb.main_menu
    )

# Обработка нажатия на текстовую кнопку из Reply-клавиатуры
@router.message(F.text == "➕ Новая задача")
async def start_adding_task(message: Message, state: FSMContext):
    await message.answer("Напиши текст задачи:")
    await state.set_state(TaskFSM.waiting_for_title)

# Перехватываем любой текст, если бот находится в состоянии waiting_for_title
@router.message(TaskFSM.waiting_for_title)
async def process_task_title(message: Message, state: FSMContext):
    # Сохраняем введенный текст в хранилище FSM
    await state.update_data(title=message.text)
    
    await message.answer(
        f"Текст сохранен: <b>{message.text}</b>\n\nТеперь выбери тип задачи:",
        reply_markup=kb.task_type_menu,
        parse_mode="HTML"
    )
    await state.set_state(TaskFSM.waiting_for_type)

# Обработка выбора: Разовая или Ежедневная задача
@router.callback_query(F.data.in_(["type_one_time", "type_daily"]), TaskFSM.waiting_for_type)
async def save_simple_task(callback: CallbackQuery, state: FSMContext):
    # Достаем текст задачи из памяти FSM
    user_data = await state.get_data()
    title = user_data.get("title")
    
    # Определяем тип для базы и для красивого вывода
    task_type = "one_time" if callback.data == "type_one_time" else "daily"
    type_name = "Разовая" if task_type == "one_time" else "Ежедневная"
    
    # Сохраняем в базу данных
    await db.add_task(telegram_id=callback.from_user.id, title=title, task_type=task_type)
    
    # edit_text меняет текущее сообщение (убирает кнопки и выводит текст успеха)
    await callback.message.edit_text(
        f"✅ Задача <b>«{title}»</b> добавлена!\nТип: {type_name}",
        parse_mode="HTML"
    )
    
    # Очищаем машину состояний
    await state.clear()
    
    # Обязательно отвечаем на callback, чтобы "часики" на кнопке перестали крутиться
    await callback.answer()


# Обработка выбора: Еженедельная задача
@router.callback_query(F.data == "type_weekly", TaskFSM.waiting_for_type)
async def ask_for_days(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TaskFSM.waiting_for_days)
    
    await callback.message.edit_text(
        "Напиши дни недели цифрами через пробел (1 - Пн, 2 - Вт... 7 - Вс).\n"
        "Например, для понедельника, среды и пятницы напиши: <b>1 3 5</b>",
        parse_mode="HTML"
    )
    await callback.answer()


# Перехватываем текст с днями недели
@router.message(TaskFSM.waiting_for_days)
async def save_weekly_task(message: Message, state: FSMContext):
    user_data = await state.get_data()
    title = user_data.get("title")
    week_days = message.text  # Забираем дни (например, "1 3 5")
    
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
# Обработчик кнопки "Список дел"
@router.message(F.text == "📅 Список дел")
async def show_tasks(message: Message):
    # Достаем все невыполненные задачи пользователя
    tasks = await db.get_active_tasks(message.from_user.id)
    
    if not tasks:
        await message.answer("Твой список дел пуст! Можно отдыхать 🎉")
        return
        
    text = "<b>📅 Твои активные задачи:</b>\n\n"
    builder = InlineKeyboardBuilder()
    
    for i, task in enumerate(tasks, start=1):
        # Добавляем эмодзи в зависимости от типа задачи
        icon = "🎯" if task.task_type == "one_time" else "🔄"
        
        # Формируем текст сообщения
        text += f"{i}. {icon} {task.title}\n"
        
        # Создаем кнопку для каждой задачи.
        # В callback_data зашиваем ID задачи, например: "done_15"
        builder.button(text=f"⬜️ {i}", callback_data=f"done_{task.id}")
        
    # Группируем кнопки по 4 в ряд, чтобы они не выстраивались в огромную вертикальную колонну
    builder.adjust(4) 
    
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")


# Обработка нажатия на кнопку выполнения задачи
@router.callback_query(F.data.startswith("done_"))
async def process_task_done(callback: CallbackQuery):
    # Разделяем строку "done_15" и забираем ID (15)
    task_id = int(callback.data.split("_")[1])
    
    # Отмечаем задачу в базе как выполненную
    completed_task = await db.complete_task(task_id)
    
    if not completed_task:
        await callback.answer("Эта задача уже выполнена или удалена!", show_alert=True)
        return

    # Показываем красивое всплывающее уведомление поверх экрана
    await callback.answer(f"✅ Выполнено: {completed_task.title}", show_alert=False)
    
    # Обновляем список задач
    # Заново запрашиваем актуальные задачи и перерисовываем сообщение
    remaining_tasks = await db.get_active_tasks(callback.from_user.id)
    
    if not remaining_tasks:
        await callback.message.edit_text("Все задачи выполнены! Отличная работа 🎉")
        return

    new_text = "<b>📅 Твои активные задачи:</b>\n\n"
    builder = InlineKeyboardBuilder()
    
    for i, task in enumerate(remaining_tasks, start=1):
        icon = "🎯" if task.task_type == "one_time" else "🔄"
        new_text += f"{i}. {icon} {task.title}\n"
        builder.button(text=f"⬜️ {i}", callback_data=f"done_{task.id}")
        
    builder.adjust(4)
    
    # Редактируем сообщение (выполненная задача просто исчезнет из списка)
    await callback.message.edit_text(new_text, reply_markup=builder.as_markup(), parse_mode="HTML")