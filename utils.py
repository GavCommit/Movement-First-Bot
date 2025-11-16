import os
import json
import re
import datetime
import time
from typing import Any, Dict, Optional
from config import PATH_TO_USERS_FILE, PATH_TO_PROJECTS_FILE

# Кэш для уменьшения чтения файлов
_file_cache = {}
_cache_timestamps = {}
CACHE_DURATION = 30  # секунд

def read_json_file(file_path: str) -> Dict[str, Any]:
    """Чтение JSON файла с кэшированием"""
    current_time = time.time()
    
    # Проверяем актуальность кэша
    if (file_path in _file_cache and 
        file_path in _cache_timestamps and
        current_time - _cache_timestamps[file_path] < CACHE_DURATION):
        return _file_cache[file_path]
    
    # Чтение из файла
    if not os.path.exists(file_path):
        _file_cache[file_path] = {}
        _cache_timestamps[file_path] = current_time
        return {}
    
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            data = json.load(file)
            _file_cache[file_path] = data
            _cache_timestamps[file_path] = current_time
            return data
    except (json.JSONDecodeError, Exception):
        _file_cache[file_path] = {}
        _cache_timestamps[file_path] = current_time
        return {}

def write_json_file(file_path: str, data: Dict[str, Any]) -> bool:
    """Запись в JSON файл с обновлением кэша"""
    try:
        # Создаем директорию если не существует
        os.makedirs(os.path.dirname(file_path) if os.path.dirname(file_path) else '.', exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
        
        # Обновляем кэш
        _file_cache[file_path] = data
        _cache_timestamps[file_path] = time.time()
        return True
    except Exception:
        return False

def invalidate_cache(file_path: str = None):
    """Сброс кэша"""
    if file_path:
        _file_cache.pop(file_path, None)
        _cache_timestamps.pop(file_path, None)
    else:
        _file_cache.clear()
        _cache_timestamps.clear()

# Функции проверки доступа
async def check_authorization(user_id: str) -> bool:
    """Проверка авторизации пользователя"""
    data = read_json_file(PATH_TO_USERS_FILE)
    user_data = data.get(str(user_id), {})
    
    # ✅ Проверяем не забанен ли пользователь
    if user_data.get("ban", 0) == 1:
        return False
    
    return str(user_id) in data

async def is_moderator(user_id: str) -> bool:
    """Проверка является ли пользователь модератором"""
    data = read_json_file(PATH_TO_USERS_FILE)
    user_data = data.get(str(user_id), {})
    
    # ✅ Забаненные пользователи не могут быть модераторами
    if user_data.get("ban", 0) == 1:
        return False
    
    return bool(user_data.get("moderator", False))

# Функции для отправки сообщений об ошибках
async def send_not_authorized(message, state=None):
    """Отправка сообщения о неавторизации"""
    from config import NOT_AUTHORIZED_MESSAGE
    from states import ActiveState
    
    user_id = str(message.from_user.id)
    data = read_json_file(PATH_TO_USERS_FILE)
    user_data = data.get(user_id, {})
    
    # ✅ Проверяем бан
    if user_data.get("ban", 0) == 1:
        await message.answer("❌ Вы были заблокированы администрацией бота ❌")
        return
    
    if state:
        await state.set_state(ActiveState.auth_wait_pswd)
    await message.answer(NOT_AUTHORIZED_MESSAGE)

async def send_not_moderator(message, reply_markup=None):
    """Отправка сообщения о недостатке прав модератора"""
    from config import NOT_MODERATOR_MESSAGE
    from keyboards import get_back_to_main_menu_kb
    
    if reply_markup is None:
        reply_markup = await get_back_to_main_menu_kb()
    
    await message.answer(NOT_MODERATOR_MESSAGE, reply_markup=reply_markup)

# Валидация данных
async def phone_number_validating(number: str) -> Optional[str]:
    """Валидация номера телефона"""
    n = ''.join(filter(lambda x: x.isdigit(), number))
    if len(n) == 11:
        if n.startswith("7"):
            return f"+{n[0]}-{n[1:4]}-{n[4:7]}-{n[7:9]}-{n[9:]}"
        if n.startswith('8'):
            return f"+7-{n[1:4]}-{n[4:7]}-{n[7:9]}-{n[9:]}"
    if len(n) == 10:
        return f"+7-{n[:3]}-{n[3:6]}-{n[6:8]}-{n[8:]}"
    return None

async def date_validation(date: str) -> bool:
    """Валидация даты"""
    pattern = r'^(\d{2}).(\d{2}).(\d{4})$'
    match = re.search(pattern, date)
    if not match:
        return False
    try:
        day, month, year = map(int, match.groups())
        datetime.datetime(year, month, day)
        return True
    except ValueError:
        return False

# Форматирование
async def format_points(points: int) -> str:
    """Форматирование баллов с правильными окончаниями"""
    points_str = str(points)
    if points_str.endswith(('5','6','7','8','9','0','11','12','13','14')):
        return f"{points} баллов"
    elif points_str.endswith(('2','3','4')):
        return f"{points} балла"
    else:
        return f"{points} балл"

async def format_member_count(count: int) -> str:
    """Форматирование количества участников"""
    count_str = str(count)
    if count_str.endswith(('5','6','7','8','9','0','11','12','13','14')):
        return f"{count} участников"
    elif count_str.endswith(('2','3','4')):
        return f"{count} участника"
    else:
        return f"{count} участник"

# Таблица лидеров

async def get_leaderboard(user_id:str, top_n=None):
    data = read_json_file(PATH_TO_USERS_FILE)
    leaderboard_data = []
    for user in data:
        user = str(user)
        name = f'{data[user].get("name") if data[user].get("name", "Не указано") != "Не указано" else ""} {data[user].get("surname", "Не указано") if data[user].get("surname", "Не указано") != "Не указано" else ""}'.strip()
        if not name or name.isspace(): 
            name = data[user].get("username", "Неизвестный пользователь")
        leaderboard_data.append({
            "user_id": user,
            "user_name" : name,
            "score" : int(data[user]["score"])
            })    
    leaderboard_data.sort(key=lambda x: x["score"], reverse=True)
    user_rank = None
    if user_id:
        for rank, user in enumerate(leaderboard_data, 1):
            if user["user_id"] == user_id:
                user_rank = rank
                break
    if top_n:
        leaderboard_data = leaderboard_data[:top_n]
    result = []
    current_group = []
    current_score = None
    group_start_rank = 1
    for i, user in enumerate(leaderboard_data):
        if user["score"] != current_score:
            if current_group:
                result.extend(await format_group(current_group, group_start_rank, i))
            current_group = [user]
            current_score = user["score"]
            group_start_rank = i + 1
        else:
            current_group.append(user)
    if current_group:
        result.extend(await format_group(current_group, group_start_rank, len(leaderboard_data)))
    return result, user_rank

async def get_medal(start_rank):
    if start_rank == 1:
        return "🥇"
    elif start_rank == 2:
        return "🥈"
    elif start_rank == 3:
        return "🥉"
    else:
        return ""

async def format_group(users_group, start_rank, end_rank):
    medal = await get_medal(start_rank)
    if len(users_group) == 1:
        user = users_group[0]
        if medal:
            return [f"{medal} {user['user_name']} - {await format_points(user['score'])} ⭐️"]
        else:
            return [f"{start_rank}. {user['user_name']} - {await format_points(user['score'])} ⭐️"] #1 Участник - 80 баллов
    else:
        formatted_lines = []
        if medal:
            prefix = f"{medal} {start_rank}-{end_rank}"
        else:
            prefix = f"{start_rank}-{end_rank}"
        for user in users_group:
            formatted_lines.append(f"{prefix} {user['user_name']} - {await format_points(user['score'])} ⭐️") #2-4 Участник - 40 баллов
        return formatted_lines