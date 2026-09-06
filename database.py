import datetime
from sqlalchemy import select, update
from models import async_session, Task, User

async def add_task(telegram_id: int, title: str, task_type: str, week_days: str = None, reminder_time: str = None):
    """Добавляет новую задачу в базу данных."""
    async with async_session() as session:
        new_task = Task(
            user_id=telegram_id,
            title=title,
            task_type=task_type,
            week_days=week_days,
            reminder_time=reminder_time # Сохраняем время
        )
        session.add(new_task)
        await session.commit()

async def get_active_tasks(telegram_id: int):
    """Возвращает список невыполненных задач пользователя."""
    async with async_session() as session:
        stmt = select(Task).where(
            Task.user_id == telegram_id,
            Task.is_done == False
        )
        result = await session.execute(stmt)
        return result.scalars().all()

async def get_all_user_tasks(telegram_id: int):
    """Возвращает вообще все задачи пользователя (и выполненные, и активные)."""
    async with async_session() as session:
        stmt = select(Task).where(Task.user_id == telegram_id)
        result = await session.execute(stmt)
        return result.scalars().all()

async def complete_task(task_id: int):
    """Отмечает задачу как выполненную."""
    async with async_session() as session:
        task = await session.scalar(select(Task).where(Task.id == task_id))
        
        if task:
            task.is_done = True
            await session.commit()
            return task
        return None

async def get_all_users():
    """Возвращает список всех пользователей из базы."""
    async with async_session() as session:
        result = await session.execute(select(User))
        return result.scalars().all()

async def reset_daily_tasks():
    """Сбрасывает статус is_done = False для всех ежедневных задач."""
    async with async_session() as session:
        stmt = update(Task).where(Task.task_type == "daily").values(is_done=False)
        await session.execute(stmt)
        await session.commit()

async def reset_weekly_tasks():
    """Сбрасывает статус еженедельных задач, если сегодня их день."""
    today_weekday = str(datetime.datetime.today().isoweekday())
    
    async with async_session() as session:
        result = await session.execute(select(Task).where(Task.task_type == "weekly"))
        weekly_tasks = result.scalars().all()
        
        for task in weekly_tasks:
            if task.week_days and today_weekday in task.week_days.split():
                task.is_done = False
                
        await session.commit()

async def get_tasks_by_reminder(time_str: str):
    """Ищет невыполненные задачи на конкретное время (формат HH:MM)."""
    async with async_session() as session:
        stmt = select(Task).where(
            Task.reminder_time == time_str, 
            Task.is_done == False
        )
        result = await session.execute(stmt)
        return result.scalars().all()