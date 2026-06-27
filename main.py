import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import config
from handlers import user_router
from database import init_db

logging.basicConfig(level=logging.INFO)

bot = Bot(token=config.telegram_bot_token.get_secret_value())
dp = Dispatcher()

dp.include_router(user_router)


async def main():
    init_db()
    logging.info("Бот запущен.")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())