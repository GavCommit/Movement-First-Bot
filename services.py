import os
import random
from typing import Any, Optional
from config import PATH_TO_USERS_FILE, PATH_TO_PROJECTS_FILE, NON_DISPLAY_CHARACTER
from utils import read_json_file, write_json_file, invalidate_cache

# Сервисы для работы с пользователями
async def get_user_data(user_id: str):
    """Получить данные пользователя"""
    return read_json_file(PATH_TO_USERS_FILE).get(str(user_id))

async def update_user_data(user_id: str, parm: str, new_value: Any) -> bool:
    """Обновить данные пользователя"""
    data = read_json_file(PATH_TO_USERS_FILE)
    user_id = str(user_id)
    if user_id in data:
        data[user_id][parm] = new_value
        success = write_json_file(PATH_TO_USERS_FILE, data)
        if success:
            invalidate_cache(PATH_TO_USERS_FILE)
        return success
    return False

async def remove_user(user_id: str) -> bool:
    """Удалить пользователя из системы"""
    users_data = read_json_file(PATH_TO_USERS_FILE)
    projects_data = read_json_file(PATH_TO_PROJECTS_FILE)
    
    user_id = str(user_id)
    if user_id not in users_data:
        return False
    
    # Удаляем пользователя из всех проектов
    user_active_projects = users_data[user_id].get("active_projects", [])
    for project_value in user_active_projects:
        try:
            category, project_id = project_value.split(":::")
            if category in projects_data and project_id in projects_data[category]:
                projects_data[category][project_id]["members"].pop(user_id, None)
        except:
            continue
    
    # Удаляем пользователя
    del users_data[user_id]
    
    # Сохраняем изменения
    success1 = write_json_file(PATH_TO_USERS_FILE, users_data)
    success2 = write_json_file(PATH_TO_PROJECTS_FILE, projects_data)
    
    if success1 and success2:
        invalidate_cache(PATH_TO_USERS_FILE)
        invalidate_cache(PATH_TO_PROJECTS_FILE)
    
    return success1 and success2

# Сервисы для работы с проектами
async def get_project_data(category: str, project_id: str):
    """Получить данные проекта"""
    return read_json_file(PATH_TO_PROJECTS_FILE).get(category, {}).get(project_id)

async def get_all_projects():
    """Получить все проекты"""
    return read_json_file(PATH_TO_PROJECTS_FILE)

async def free_id(category: str) -> str:
    """Сгенерировать свободный ID проекта"""
    data = read_json_file(PATH_TO_PROJECTS_FILE)
    category_data = data.get(category, {})
    while True:
        new_id = str(random.randint(1, 1000))
        if new_id not in category_data:
            return new_id

async def create_project(category: str, project_name: str) -> Optional[str]:
    """Создать новый проект"""
    data = read_json_file(PATH_TO_PROJECTS_FILE)
    project_id = await free_id(category)
    
    if category not in data:
        data[category] = {}
    
    # ✅ Добавил поле approval_required (по умолчанию 0 - не требуется одобрение)
    data[category][project_id] = {
        "name": NON_DISPLAY_CHARACTER + project_name,
        "description": "Без описания",
        "url": None,
        "date": "00.01.2000",
        "prize": 0,
        "unleaveable": 0,
        "approval_required": 0,  # ✅ Новый флаг
        "preview_photo": None,
        "max_members": 100,
        "members": {}
    }
    
    success = write_json_file(PATH_TO_PROJECTS_FILE, data)
    if success:
        invalidate_cache(PATH_TO_PROJECTS_FILE)
        return project_id
    return None

async def update_project_data(category: str, project_id: str, parm: str, value: Any) -> bool:
    """Обновить данные проекта"""
    data = read_json_file(PATH_TO_PROJECTS_FILE)
    
    if category not in data or project_id not in data[category]:
        return False
    
    data[category][project_id][parm] = value
    success = write_json_file(PATH_TO_PROJECTS_FILE, data)
    
    if success:
        invalidate_cache(PATH_TO_PROJECTS_FILE)
    return success

async def delete_project(category: str, project_id: str) -> bool:
    """Удалить проект"""
    data_pr = read_json_file(PATH_TO_PROJECTS_FILE)
    data_us = read_json_file(PATH_TO_USERS_FILE)
    
    if category not in data_pr or project_id not in data_pr[category]:
        return False
    
    # Удаляем проект из активных проектов пользователей
    project_members = data_pr[category][project_id].get("members", {})
    for user_id in project_members:
        if user_id in data_us:
            project_value = f"{category}:::{project_id}"
            if project_value in data_us[user_id].get("active_projects", []):
                data_us[user_id]["active_projects"].remove(project_value)
    
    # Удаляем фото проекта если есть
    photo_path = data_pr[category][project_id].get("preview_photo")
    if photo_path and os.path.exists(photo_path):
        try:
            os.remove(photo_path)
        except:
            pass
    
    # Удаляем проект
    del data_pr[category][project_id]
    
    # Сохраняем изменения
    success1 = write_json_file(PATH_TO_PROJECTS_FILE, data_pr)
    success2 = write_json_file(PATH_TO_USERS_FILE, data_us)
    
    if success1 and success2:
        invalidate_cache(PATH_TO_PROJECTS_FILE)
        invalidate_cache(PATH_TO_USERS_FILE)
    
    return success1 and success2

# Сервисы для работы с участниками проектов
async def add_member_to_project(user_id: str, category: str, project_id: str):
    """Добавить участника в проект"""
    users_data = read_json_file(PATH_TO_USERS_FILE)
    projects_data = read_json_file(PATH_TO_PROJECTS_FILE)
    
    if (category not in projects_data or 
        project_id not in projects_data[category] or
        user_id not in users_data):
        return {"status": False, "error": "Project or user not found"}
    
    project = projects_data[category][project_id]
    max_members = project.get("max_members", 1000000000)
    current_members = len(project.get("members", {}))
    
    if current_members >= max_members:
        return {"status": False, "error": "No free places"}
    
    if user_id in project.get("members", {}):
        return {"status": False, "error": "User already member"}
    
    # Добавляем в проект
    projects_data[category][project_id]["members"][user_id] = {"role": "участник"}
    
    # Добавляем в активные проекты пользователя
    project_value = f"{category}:::{project_id}"
    if project_value not in users_data[user_id].get("active_projects", []):
        users_data[user_id]["active_projects"].append(project_value)
    
    # Сохраняем изменения
    success1 = write_json_file(PATH_TO_PROJECTS_FILE, projects_data)
    success2 = write_json_file(PATH_TO_USERS_FILE, users_data)
    
    if success1 and success2:
        invalidate_cache(PATH_TO_PROJECTS_FILE)
        invalidate_cache(PATH_TO_USERS_FILE)
        return {"status": True, "error": "success"}
    return {"status": False, "error": "Failed to save"}

async def remove_member_from_project(user_id: str, category: str, project_id: str):
    """Удалить участника из проекта"""
    users_data = read_json_file(PATH_TO_USERS_FILE)
    projects_data = read_json_file(PATH_TO_PROJECTS_FILE)
    
    if (category not in projects_data or 
        project_id not in projects_data[category] or
        user_id not in users_data):
        return {"status": False, "error": "Project or user not found"}
    
    project = projects_data[category][project_id]
    if user_id not in project.get("members", {}):
        return {"status": False, "error": "User not member of project"}
    
    # Удаляем из проекта
    del projects_data[category][project_id]["members"][user_id]
    
    # Удаляем из активных проектов пользователя
    project_value = f"{category}:::{project_id}"
    if project_value in users_data[user_id].get("active_projects", []):
        users_data[user_id]["active_projects"].remove(project_value)
    
    # Сохраняем изменения
    success1 = write_json_file(PATH_TO_PROJECTS_FILE, projects_data)
    success2 = write_json_file(PATH_TO_USERS_FILE, users_data)
    
    if success1 and success2:
        invalidate_cache(PATH_TO_PROJECTS_FILE)
        invalidate_cache(PATH_TO_USERS_FILE)
        return {"status": True, "error": "success"}
    return {"status": False, "error": "Failed to save"}

# Сервисы для работы с баллами
async def add_points_to_member(user_id: str, points: int):
    """Добавить баллы пользователю"""
    users_data = read_json_file(PATH_TO_USERS_FILE)
    user_id = str(user_id)
    
    if user_id not in users_data:
        return {"status": False, "error": "User not found"}
    
    current_score = users_data[user_id].get("score", 0)
    users_data[user_id]["score"] = current_score + int(points)
    
    success = write_json_file(PATH_TO_USERS_FILE, users_data)
    if success:
        invalidate_cache(PATH_TO_USERS_FILE)
        return {"status": True, "error": "success"}
    
    return {"status": False, "error": "Failed to save"}

async def give_reward_to_project_members(category: str, project_id: str):
    """Наградить всех участников проекта"""
    projects_data = read_json_file(PATH_TO_PROJECTS_FILE)
    
    if category not in projects_data or project_id not in projects_data[category]:
        return {"status": False, "members": 0, "error": "Project not found"}
    
    project = projects_data[category][project_id]
    prize = project.get("prize", 0)
    members = project.get("members", {})
    
    if not members:
        return {"status": True, "members": 0, "error": "No members"}
    
    rewarded = 0
    for member_id in members:
        result = await add_points_to_member(member_id, prize)
        if result["status"]:
            rewarded += 1
    
    return {"status": True, "members": rewarded, "error": None}

# Проверка регистрации для проектов
async def check_project_registration(user_id: str):
    """Проверить готовность пользователя к участию в проектах"""
    user_data = await get_user_data(user_id)
    if not user_data:
        return {"status": False, "error": "User not found"}
    
    required_fields = ["name", "surname", "IDfirst", "phone"]
    for field in required_fields:
        if user_data.get(field, "Не указано") == "Не указано":
            return {"status": False, "error": f"{field} not specified"}
    
    return {"status": True, "error": "access"}

# Сервисы для рейтинга
async def get_leaderboard_data(user_id: str = None, top_n: int = None):
    """Получить данные рейтинга"""
    users_data = read_json_file(PATH_TO_USERS_FILE)
    
    leaderboard = []
    for uid, user_data in users_data.items():
        name = f'{user_data.get("name", "")} {user_data.get("surname", "")}'.strip()
        if not name:
            name = user_data.get("username", "Unknown")
        
        leaderboard.append({
            "user_id": uid,
            "user_name": name,
            "score": int(user_data.get("score", 0))
        })
    
    leaderboard.sort(key=lambda x: x["score"], reverse=True)
    
    user_rank = None
    if user_id:
        for rank, user in enumerate(leaderboard, 1):
            if user["user_id"] == user_id:
                user_rank = rank
                break
    
    if top_n:
        leaderboard = leaderboard[:top_n]
    
    return leaderboard, user_rank

# ✅ НовЫЕ ФУНКЦИИ ДЛЯ РАБОТЫ С БАНОМ
async def ban_user(user_id: str) -> bool:
    """Забанить пользователя"""
    users_data = read_json_file(PATH_TO_USERS_FILE)
    projects_data = read_json_file(PATH_TO_PROJECTS_FILE)
    
    user_id = str(user_id)
    if user_id not in users_data:
        return False
    
    # Удаляем пользователя из всех проектов
    user_active_projects = users_data[user_id].get("active_projects", [])
    for project_value in user_active_projects:
        try:
            category, project_id = project_value.split(":::")
            if category in projects_data and project_id in projects_data[category]:
                projects_data[category][project_id]["members"].pop(user_id, None)
        except:
            continue
    
    # Устанавливаем флаг бана
    users_data[user_id]["ban"] = 1
    
    # Сохраняем изменения
    success1 = write_json_file(PATH_TO_USERS_FILE, users_data)
    success2 = write_json_file(PATH_TO_PROJECTS_FILE, projects_data)
    
    if success1 and success2:
        invalidate_cache(PATH_TO_USERS_FILE)
        invalidate_cache(PATH_TO_PROJECTS_FILE)
    
    return success1 and success2

async def unban_user(user_id: str) -> bool:
    """Разбанить пользователя"""
    users_data = read_json_file(PATH_TO_USERS_FILE)
    user_id = str(user_id)
    
    if user_id not in users_data:
        return False
    
    # Убираем флаг бана
    users_data[user_id]["ban"] = 0
    
    success = write_json_file(PATH_TO_USERS_FILE, users_data)
    if success:
        invalidate_cache(PATH_TO_USERS_FILE)
    
    return success

async def is_user_banned(user_id: str) -> bool:
    """Проверить забанен ли пользователь"""
    user_data = await get_user_data(user_id)
    if not user_data:
        return False
    
    return bool(user_data.get("ban", 0))