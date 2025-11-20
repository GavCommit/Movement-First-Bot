import asyncio
import datetime
from config import POLLING_TIMEOUT
from services import get_all_projects, update_project_data

async def check_completed_projects():
    """Проверка и отметка проектов, которые заканчиваются сегодня"""
    date_today = datetime.datetime.now().strftime("%d.%m.%Y")
    projects_data = await get_all_projects()
    edited = False
    
    for category in projects_data:
        for project_id, project in projects_data[category].items():
            date = project.get("date", "")
            if date == date_today:
                desc_text = "🔚 Этот проект завершается сегодня, не забудьте отправить достаточно фотографий, для получения баллов! 🔚"
                name_text = "🔚 Завершён:"
                
                if (not project["description"].startswith(desc_text) and 
                    not project["name"].startswith(name_text)):
                    
                    name = f'{name_text} {project["name"]}'
                    description = f'{desc_text}\n\n{project["description"]}'
                    
                    await update_project_data(category, project_id, "name", name)
                    await update_project_data(category, project_id, "description", description)
                    await update_project_data(category, project_id, "unleaveable", 1)
                    await update_project_data(category, project_id, "completed", 1)
                    edited = True
    
    if edited:
        print("Отмечены завершенные проекты для сегодняшней даты")
    return edited

async def ask_for_removing_old_projects():
    """Отправка завершенных проектов модераторам для проверки"""
    from handlers.moderation_handlers import send_project_to_moderators
    from aiogram import Bot
    from config import API_TELEGRAM
    
    bot = Bot(token=API_TELEGRAM)
    projects_data = await get_all_projects()
    for category in projects_data:
        for project_id, project in projects_data[category].items():
            if project.get("completed", False):
                await send_project_to_moderators(category=category, project_id=project_id, bot=bot)
    await bot.session.close()

async def timer():
    """Основной таймер планировщика"""
    now = datetime.datetime.now()
    next_hour = (now + datetime.timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    wait_seconds = (next_hour - now).total_seconds()
    await asyncio.sleep(wait_seconds)
    
    while True:
        now = datetime.datetime.now()
        
        # Ежедневно в 12:00 - проверка завершенных проектов
        if now.hour == 12 and now.minute == 0 and now.second < 30:
            await check_completed_projects()
        
        # Ежедневно в 10:00 - запрос на удаление старых проектов
        if now.hour == 10 and now.minute == 0 and now.second < 30:
            await ask_for_removing_old_projects()
        
        await asyncio.sleep(POLLING_TIMEOUT)