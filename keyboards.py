from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

# Нижняя клавиатура (главное меню)
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Новая задача")],
        [KeyboardButton(text="📅 Список дел")]
    ],
    resize_keyboard=True,
    input_field_placeholder="Управляй своими задачами..."
)

# Inline-клавиатура для выбора типа задачи
task_type_menu = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Разовая ", callback_data="type_one_time")],
        [InlineKeyboardButton(text="Ежедневная ", callback_data="type_daily")],
        [InlineKeyboardButton(text="Еженедельная ", callback_data="type_weekly")]
    ]
)