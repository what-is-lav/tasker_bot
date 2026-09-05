from aiogram import Bot
import database as db

async def midnight_reset_job():
    """Функция запускается ночью и обновляет базу."""
    await db.reset_daily_tasks()
    await db.reset_weekly_tasks()  # <- Добавили эту строку
    print("Ежедневные и еженедельные задачи успешно сброшены!")

async def morning_summary_job(bot: Bot):
    """Функция запускается утром и рассылает пользователям их планы."""
    users = await db.get_all_users()
    
    for user in users:
        tasks = await db.get_active_tasks(user.telegram_id)
        
        if tasks:
            text = "🌅 <b>Доброе утро! Твой план на сегодня:</b>\n\n"
            for i, task in enumerate(tasks, start=1):
                icon = "🎯" if task.task_type == "one_time" else "🔄"
                text += f"{i}. {icon} {task.title}\n"
            
            try:
                # Отправляем сообщение без кнопок — чисто для ознакомления
                await bot.send_message(user.telegram_id, text, parse_mode="HTML")
            except Exception:
                # Если пользователь заблокировал бота, Telegram выдаст ошибку.
                # Глушим её, чтобы цикл не прервался для остальных юзеров.
                pass