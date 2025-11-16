import os
import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import API_TELEGRAM
from handlers.auth_handlers import router as auth_router
from handlers.common_handlers import router as common_router
from handlers.user_handlers import router as user_router
from handlers.project_handlers import router as project_router
from handlers.report_handlers import router as report_router
from handlers.moderation_handlers import router as moderation_router
from scheduler import timer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    bot = Bot(token=API_TELEGRAM)
    dp = Dispatcher(storage=MemoryStorage())
    
    # Include routers
    dp.include_router(auth_router)
    dp.include_router(common_router)
    dp.include_router(user_router)
    dp.include_router(project_router)
    dp.include_router(report_router)
    dp.include_router(moderation_router)
    
    # Start scheduler
    asyncio.create_task(timer())
    
    #logger.info("Bot started successfully")
    
    # Start polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())