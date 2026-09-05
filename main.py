import asyncio
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message
import dotenv
from models import init_db, async_session, User
from sqlalchemy import select


BOT_TOKEN = dotenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

@dp.message(CommandStart())
async def cmd_start(message: Message):
    async with async_session() as session:
        user = await session.scalar(select(User).where(User.telegram_id == message.from_user.id))
        
        if not user:
            session.add(User(telegram_id=message.from_user.id))
            await session.commit()
            
    await message.answer(
        "Привет! Я твой планировщик задач.\n\n"
        "Здесь ты можешь создавать разовые, ежедневные и еженедельные задачи."
    )

async def main():
    await init_db()
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())