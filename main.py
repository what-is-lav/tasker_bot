import os
import asyncio
from dotenv import load_dotenv
from aiohttp import web

from aiogram import Bot, Dispatcher

from models import init_db
import views
from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Импортируем все 4 функции из твоего файла planner
from planner import midnight_reset_job, morning_summary_job, evening_summary_job, check_reminders_job

# 1. Загрузка токена
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("Переменная BOT_TOKEN не найдена в файле .env!")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# 2. Подключение роутера (views)
dp.include_router(views.router)

# 3. Крошечный хэндлер для веб-страницы
async def ping_handler(request):
    return web.Response(text="Бот работает!")

async def main():
    await init_db()
    
    # 4. Настраиваем планировщик 
    scheduler = AsyncIOScheduler(timezone="Asia/Bishkek")
    
    # Сброс задач ночью
    scheduler.add_job(midnight_reset_job, trigger='cron', hour=0, minute=0)
    # Утренняя сводка в 09:00
    scheduler.add_job(morning_summary_job, trigger='cron', hour=9, minute=0, kwargs={'bot': bot})
    
    # НОВОЕ: Вечерний итог в 21:00
    scheduler.add_job(evening_summary_job, trigger='cron', hour=21, minute=0, kwargs={'bot': bot})
    # НОВОЕ: Ежеминутная проверка точечных напоминаний
    scheduler.add_job(check_reminders_job, trigger='cron', minute='*', kwargs={'bot': bot})
    
    scheduler.start()
    
    # 5. Настраиваем веб-сервер для Render
    app = web.Application()
    app.router.add_get('/', ping_handler)
    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    print(f"Веб-заглушка запущена на порту {port}")
    print("Бот и планировщик запущены!")
    
    # 6. Запускаем поллинг бота
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())