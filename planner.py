import datetime
import pytz
from aiogram import Bot
import database as db

async def midnight_reset_job():
    """Сбрасывает ежедневные и еженедельные задачи в полночь."""
    await db.reset_daily_tasks()
    await db.reset_weekly_tasks()

async def morning_summary_job(bot: Bot):
    """Рассылает утреннюю сводку задач на сегодня."""
    users = await db.get_all_users()
    
    # Определяем сегодняшний день недели
    tz = pytz.timezone("Asia/Bishkek")
    today_str = str(datetime.datetime.now(tz).isoweekday())
    
    for user in users:
        tasks = await db.get_active_tasks(user.telegram_id)
        if not tasks:
            continue
            
        # Отбираем только задачи, актуальные на сегодня
        tasks_today = []
        for task in tasks:
            if task.task_type in ("one_time", "daily"):
                tasks_today.append(task)
            elif task.task_type == "weekly" and task.week_days and (today_str in task.week_days.split()):
                tasks_today.append(task)
                
        if tasks_today:
            text = f"🌅 Доброе утро! Твой план на сегодня — {len(tasks_today)} задач:\n\n"
            for i, t in enumerate(tasks_today, start=1):
                time_str = f" <i>({t.reminder_time})</i>" if getattr(t, 'reminder_time', None) else ""
                text += f"{i}. {t.title}{time_str}\n"
            
            try:
                await bot.send_message(user.telegram_id, text, parse_mode="HTML")
            except Exception:
                pass # Юзер заблокировал бота

async def evening_summary_job(bot: Bot):
    """Подводит итоги дня вечером."""
    users = await db.get_all_users()
    
    tz = pytz.timezone("Asia/Bishkek")
    today_str = str(datetime.datetime.now(tz).isoweekday())
    
    for user in users:
        # Запрашиваем активные (невыполненные) задачи
        active_tasks = await db.get_active_tasks(user.telegram_id)
        
        # Считаем, сколько задач НА СЕГОДНЯ осталось невыполненными
        pending_today = 0
        for task in active_tasks:
            if task.task_type in ("one_time", "daily"):
                pending_today += 1
            elif task.task_type == "weekly" and task.week_days and (today_str in task.week_days.split()):
                pending_today += 1
                
        if pending_today == 0:
            text = "🌙 Итоги дня: Отличная работа! Все задачи на сегодня закрыты. 🎉"
        else:
            text = f"🌙 Итоги дня. Осталось невыполненным задач на сегодня: {pending_today}.\nПостарайся закрыть их завтра!"
            
        try:
            await bot.send_message(user.telegram_id, text)
        except Exception:
            pass

async def check_reminders_job(bot: Bot):
    """Ежеминутно проверяет, есть ли задачи, о которых нужно напомнить прямо сейчас."""
    tz = pytz.timezone("Asia/Bishkek")
    now = datetime.datetime.now(tz)
    current_time_str = now.strftime("%H:%M")
    
    # Достаем все активные задачи, у которых время напоминания = текущая минута
    tasks = await db.get_tasks_by_reminder(current_time_str)
    
    for task in tasks:
        try:
            await bot.send_message(
                task.user_id, 
                f"🔔 <b>Напоминание:</b>\n{task.title}", 
                parse_mode="HTML"
            )
        except Exception:
            pass