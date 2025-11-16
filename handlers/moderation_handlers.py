import os
import json
import random
import difflib
import re
import datetime
import asyncio
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from config import PATH_TO_USERS_FILE, PATH_TO_PROJECTS_FILE, MODERATORS_CHAT_ID, NON_DISPLAY_CHARACTER
from states import ActiveState
from utils import read_json_file, write_json_file, check_authorization, is_moderator, date_validation, send_not_authorized, send_not_moderator
from services import get_user_data, get_project_data, get_all_projects, update_user_data, delete_project, give_reward_to_project_members, add_points_to_member, ban_user, unban_user, is_user_banned
from keyboards import get_adding_projects_md_kb, get_projects_menu_kb, generate_projects_category_menu_kb, get_back_to_main_menu_kb, get_back_to_project_editing_kb

router = Router()

@router.message(F.chat.type == "private", Command(commands=['все_пользователи','все_активисты','all_users','all_members']))
async def all_users(message: Message):
    if not await is_moderator(str(message.from_user.id)):
        await send_not_moderator(message)
        return

    data_us = read_json_file(PATH_TO_USERS_FILE)
    text = f'Всего пользователей: {len(data_us)}\n\n'
    for index, user in enumerate(data_us, 1):
        name = f'{index} {data_us[user].get("name")} {data_us[user].get("surname")} ID: <code>{user}</code>\n'
        text += name

    await message.answer(text, reply_markup=await get_back_to_main_menu_kb(), parse_mode="HTML")

@router.message(F.chat.type == "private", Command(commands=['поиск', 'search', 'find']))
async def search_users(message: Message):
    if not await is_moderator(str(message.from_user.id)):
        await send_not_moderator(message)
        return
    
    # /поиск запрос /5
    command_parts = message.text.split()
    if len(command_parts) < 2:
        await message.answer(
            "❌ Использование: /поиск запрос [/N]\n\n",
            reply_markup=await get_back_to_main_menu_kb()
        )
        return

    search_query = ""
    max_results = 5  
    
    for part in command_parts[1:]:
        if part.startswith('/') and part[1:].isdigit():
            max_results = int(part[1:])
        else:
            search_query += part + " "
    
    search_query = search_query.strip()
    
    if not search_query:
        await message.answer("❌ Введите поисковый запрос", reply_markup=await get_back_to_main_menu_kb())
        return
    
    await perform_user_search(message, search_query, max_results)

async def perform_user_search(message: Message, search_query: str, max_results: int = 5):
    """Выполняет поиск пользователей по всем полям"""
    users_data = read_json_file(PATH_TO_USERS_FILE)
    
    if not users_data:
        await message.answer("❌ База пользователей пуста", reply_markup=await get_back_to_main_menu_kb())
        return
    
    search_results = []
    exact_matches = []
    fuzzy_matches = []
    
    normalized_query = search_query.lower().strip()
    
    for user_id, user_data in users_data.items():
        fields = {
            'user_id': user_id,
            'username': user_data.get('username', '').lower(),
            'name': user_data.get('name', '').lower(), 
            'surname': user_data.get('surname', '').lower(),
            'IDfirst': user_data.get('IDfirst', '').lower(),
            'phone': user_data.get('phone', '').lower()
        }
        
        exact_match = False
        score = 0
        
        if (normalized_query == fields['user_id'] or 
            normalized_query == fields['username'].replace('@', '') or
            normalized_query == fields['IDfirst'] or
            normalized_query == fields['phone'].replace('-', '').replace('+', '') or
            search_query == user_data.get('username') or 
            search_query == user_data.get('IDfirst') or
            search_query == user_data.get('phone')):
            
            exact_match = True
            score = 100
        
        elif (normalized_query in fields['user_id'] or
              normalized_query in fields['username'] or
              normalized_query in fields['IDfirst'] or
              normalized_query in fields['phone'].replace('-', '').replace('+', '')):
            
            score = 80  
        
        else:
            full_name = f"{fields['name']} {fields['surname']}".strip()
            if full_name:
                name_ratio = difflib.SequenceMatcher(
                    None, normalized_query, full_name
                ).ratio()
                
                # имя и фамилию
                name_only_ratio = difflib.SequenceMatcher(
                    None, normalized_query, fields['name']
                ).ratio() if fields['name'] else 0
                
                surname_only_ratio = difflib.SequenceMatcher(
                    None, normalized_query, fields['surname'] 
                ).ratio() if fields['surname'] else 0
                
                max_name_ratio = max(name_ratio, name_only_ratio, surname_only_ratio)
                
                if max_name_ratio > 0.3:  #match_ratio
                    score = int(max_name_ratio * 100)
        
        if score > 0:
            user_result = {
                'user_id': user_id,
                'user_data': user_data,
                'score': score,
                'exact_match': exact_match
            }
            
            if exact_match:
                exact_matches.append(user_result)
            else:
                fuzzy_matches.append(user_result)
    
    exact_matches.sort(key=lambda x: x['score'], reverse=True)
    fuzzy_matches.sort(key=lambda x: x['score'], reverse=True)
    
    search_results = exact_matches + fuzzy_matches
    
    if not search_results:
        await message.answer(
            f"❌ По запросу '{search_query}' ничего не найдено",
            reply_markup=await get_back_to_main_menu_kb()
        )
        return
    
    top_results = search_results[:max_results]
    
    response_text = f"🔍 <b>Результаты поиска</b> \"{search_query}\":\n\n"
    
    for i, result in enumerate(top_results, 1):
        user_data = result['user_data']
        
        name = f"{user_data.get('name', '')} {user_data.get('surname', '')}".strip()
        username = f"@{user_data.get('username', '')}" if user_data.get('username') else "Не указан"
        phone = user_data.get('phone', 'Не указан')
        id_first = user_data.get('IDfirst', 'Не указано')
        id_first = id_first if id_first == 'Не указано' else "<code>"+str(id_first)+"</code>"
        user_id = result['user_id']
        
        match_type = "🎯" if result['exact_match'] else "🔍"
        
        response_text += (
            f"{match_type} <b>Результат {i}</b> (сходство: {result['score']}%)\n"
            f"👤 {name}\n"
            f"📱 {username}\n" 
            f"📞 {phone}\n"
            f"🆔 {id_first}\n"
            f"🔗 TG ID: <code>{user_id}</code>\n"
            f"────────────────────\n\n"
        )
    
    total_found = len(search_results)
    if total_found > max_results:
        response_text += f"<i>Показано {max_results} из {total_found} найденных результатов</i>\n"
    
    await message.answer(
        response_text,
        reply_markup=await get_back_to_main_menu_kb(),
        parse_mode="HTML"
    )

@router.message(F.chat.type == "private", Command(commands=['редактировать_пользователя','edit_member','edit_user']))
async def all_users(message: Message, state: FSMContext):
    await state.clear()
    if not await is_moderator(str(message.from_user.id)):
        await send_not_moderator(message)
        return
    
    if len(message.text.split()) == 1:
        await message.answer("❌ Телеграм ID не указан ❌", reply_markup=await get_back_to_main_menu_kb())
        return
    
    user_id = message.text.split()[1]
    if not user_id.isdigit():
        await message.answer("❌ Неверный телеграм ID ❌", reply_markup=await get_back_to_main_menu_kb())
        return
    
    from handlers.user_handlers import editing_user_parms
    await editing_user_parms(message=message, user_id=user_id)

@router.message(F.chat.type == "private", Command(commands=['удалить_пользователя','remove_user','delete_user']))
async def all_users(message: Message, state: FSMContext):
    await state.clear()
    if not await is_moderator(str(message.from_user.id)):
        await send_not_moderator(message)
        return
    
    if len(message.text.split()) == 1:
        await message.answer("❌ Телеграм ID не указан ❌", reply_markup=await get_back_to_main_menu_kb())
        return
    
    user_id = message.text.split()[1]
    if not user_id.isdigit():
        await message.answer("❌ Неверный телеграм ID ❌", reply_markup=await get_back_to_main_menu_kb())
        return
    
    from services import remove_user
    success = await remove_user(user_id=user_id)
    if success:
        await message.answer(f"✔️ Пользователь: {user_id}. Успешно удалён ✔️", reply_markup=await get_back_to_main_menu_kb())
    else:
        await message.answer(f"❌ Пользователь: {user_id} не найден ❌", reply_markup=await get_back_to_main_menu_kb())

@router.callback_query(F.data.startswith("REMOVE_FROM_PROJECT:::"))
async def remove_user_from_project_menu(callback: CallbackQuery, state: FSMContext):
    """Меню выбора проекта для удаления пользователя"""
    data_parts = callback.data.split(":::")
    user_id = data_parts[1]
    
    users_data = read_json_file(PATH_TO_USERS_FILE)
    projects_data = read_json_file(PATH_TO_PROJECTS_FILE)
    
    user_data = users_data.get(user_id, {})
    active_projects = user_data.get("active_projects", [])
    
    if not active_projects:
        await callback.message.edit_text(
            f"❌ У пользователя нет активных проектов",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text='🔙 Назад', callback_data=f"editing_user:::{user_id}")]
            ])
        )
        return
    
    kb = []
    for project_value in active_projects:
        try:
            category, project_id = project_value.split(":::")
            project = projects_data.get(category, {}).get(project_id, {})
            project_name = project.get("name", "Неизвестный проект")
            display_name = project_name[len(NON_DISPLAY_CHARACTER):] if project_name.startswith(NON_DISPLAY_CHARACTER) else project_name
            
            button_text = f"{display_name}"
            if len(button_text) > 50:
                button_text = button_text[:47] + "..."
                
            kb.append([InlineKeyboardButton(
                text=button_text,
                callback_data=f"CONFIRM_REMOVE_PROJECT:::{user_id}:::{category}:::{project_id}"
            )])
        except:
            continue
    
    kb.append([InlineKeyboardButton(text='🔙 Отмена', callback_data=f"editing_user:::{user_id}")])
    
    user_name = f"{user_data.get('name', '')} {user_data.get('surname', '')}".strip()
    if not user_name:
        user_name = user_id
    
    await callback.message.edit_text(
        f"🗑️ <b>Удаление пользователя из проекта</b>\n\n"
        f"👤 Пользователь: {user_name}\n"
        f"📋 Выберите проект для удаления:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("CONFIRM_REMOVE_PROJECT:::"))
async def confirm_remove_from_project(callback: CallbackQuery, state: FSMContext):
    """Подтверждение удаления из проекта"""
    data_parts = callback.data.split(":::")
    user_id = data_parts[1]
    category = data_parts[2]
    project_id = data_parts[3]
    
    projects_data = read_json_file(PATH_TO_PROJECTS_FILE)
    users_data = read_json_file(PATH_TO_USERS_FILE)
    
    project = projects_data.get(category, {}).get(project_id, {})
    user_data = users_data.get(user_id, {})
    
    project_name = project.get("name", "Неизвестный проект")
    display_name = project_name[len(NON_DISPLAY_CHARACTER):] if project_name.startswith(NON_DISPLAY_CHARACTER) else project_name
    user_name = f"{user_data.get('name', '')} {user_data.get('surname', '')}".strip()
    if not user_name:
        user_name = user_id
    
    await callback.message.edit_text(
        f"⚠️ <b>Подтверждение удаления</b>\n\n"
        f"👤 Пользователь: {user_name}\n"
        f"📋 Проект: {display_name}\n"
        f"📁 Категория: {category}\n\n"
        f"Вы уверены, что хотите удалить пользователя из проекта?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text='✅ Да, удалить', callback_data=f"EXECUTE_REMOVE_PROJECT:::{user_id}:::{category}:::{project_id}"),
                InlineKeyboardButton(text='❌ Отмена', callback_data=f"editing_user:::{user_id}") 
            ]
        ]),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("EXECUTE_REMOVE_PROJECT:::"))
async def execute_remove_from_project(callback: CallbackQuery, state: FSMContext, bot: Bot):
    """Выполнение удаления из проекта"""
    data_parts = callback.data.split(":::")
    user_id = data_parts[1]
    category = data_parts[2]
    project_id = data_parts[3]
    
    from services import remove_member_from_project
    result = await remove_member_from_project(user_id, category, project_id)
    
    projects_data = read_json_file(PATH_TO_PROJECTS_FILE)
    users_data = read_json_file(PATH_TO_USERS_FILE)
    
    project = projects_data.get(category, {}).get(project_id, {})
    user_data = users_data.get(user_id, {})
    
    project_name = project.get("name", "Неизвестный проект")
    display_name = project_name[len(NON_DISPLAY_CHARACTER):] if project_name.startswith(NON_DISPLAY_CHARACTER) else project_name
    user_name = f"{user_data.get('name', '')} {user_data.get('surname', '')}".strip()
    if not user_name:
        user_name = user_id
    
    if result["status"]:
        try:
            await bot.send_message(
                chat_id=user_id,
                text=f"❌ Вас удалили из проекта <b>{display_name}</b> администрацией",
                parse_mode="HTML"
            )
        except:
            pass  
        
        from handlers.user_handlers import editing_user_parms
        await editing_user_parms(message=callback.message, user_id=user_id)
    else:
        from handlers.user_handlers import editing_user_parms
        await editing_user_parms(message=callback.message, user_id=user_id)

@router.message(F.chat.type == "private", Command(commands=['ban', 'бан']))
async def ban_user_command(message: Message):
    if not await is_moderator(str(message.from_user.id)):
        await send_not_moderator(message)
        return
    
    if len(message.text.split()) < 2:
        await message.answer("❌ Использование: /ban user_id", reply_markup=await get_back_to_main_menu_kb())
        return
    
    user_id = message.text.split()[1]
    if not user_id.isdigit():
        await message.answer("❌ Неверный ID пользователя", reply_markup=await get_back_to_main_menu_kb())
        return
    
    users_data = read_json_file(PATH_TO_USERS_FILE)
    if user_id not in users_data:
        await message.answer("❌ Пользователь не найден", reply_markup=await get_back_to_main_menu_kb())
        return
    
    success = await ban_user(user_id)
    if success:
        try:
            await message.bot.send_message(
                chat_id=user_id,
                text="❌ Вы были заблокированы администрацией бота ❌"
            )
        except:
            pass 
        
        await message.answer(f"✅ Пользователь {user_id} заблокирован", reply_markup=await get_back_to_main_menu_kb())
    else:
        await message.answer("❌ Ошибка при блокировке пользователя", reply_markup=await get_back_to_main_menu_kb())

@router.message(F.chat.type == "private", Command(commands=['unban', 'разбан']))
async def unban_user_command(message: Message):
    if not await is_moderator(str(message.from_user.id)):
        await send_not_moderator(message)
        return
    
    if len(message.text.split()) < 2:
        await message.answer("❌ Использование: /unban user_id", reply_markup=await get_back_to_main_menu_kb())
        return
    
    user_id = message.text.split()[1]
    if not user_id.isdigit():
        await message.answer("❌ Неверный ID пользователя", reply_markup=await get_back_to_main_menu_kb())
        return
    
    success = await unban_user(user_id)
    if success:
        await message.answer(f"✅ Пользователь {user_id} разблокирован", reply_markup=await get_back_to_main_menu_kb())
    else:
        await message.answer("❌ Ошибка при разблокировке пользователя", reply_markup=await get_back_to_main_menu_kb())

@router.callback_query(F.data.startswith("editing_user:::"))
async def my_data_edit_parms(callback: CallbackQuery, state: FSMContext):
    data_parts = callback.data.split(":::")
    user_id = data_parts[1]
    await state.clear()
    from handlers.user_handlers import editing_user_parms
    await editing_user_parms(message=callback.message, user_id=user_id)

@router.message(F.chat.type == "private", Command(commands=["новый_проект","создание_проекта","new_project"]))
async def new_project(message: Message, state: FSMContext):
    user_id = str(message.from_user.id)
    if not await check_authorization(user_id):
        await send_not_authorized(message, state)
        return
        
    if not await is_moderator(user_id):
        await send_not_moderator(message)
        return

    await state.set_state(ActiveState.waiting_for_name_of_the_project)
    await message.answer(
        "Введите название проекта:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Отмена', callback_data="back_to_main")]])
    )

@router.message(ActiveState.waiting_for_name_of_the_project, F.text)
async def handle_photos(message: Message, state: FSMContext):
    name_project = message.text
    valid_project_name = name_project
    await state.update_data(project_name=valid_project_name)

    await message.answer(
        "Выберите категорию проекта:",
        reply_markup=await get_adding_projects_md_kb()
    )

@router.callback_query(F.data.startswith("adding_project_category_"))
async def new_project(callback: CallbackQuery, state: FSMContext):
    category = callback.data.replace("adding_project_category_", "")
    state_data = await state.get_data()
    project_name = state_data.get('project_name')
    
    from services import free_id, create_project
    project_id = await create_project(category, project_name)

    if not project_id:
        await callback.message.answer("❌ Ошибка при создании проекта", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Отмена', callback_data="back_to_main")]]))
        await state.clear()
        return

    await callback.message.edit_text(
        "✔️ Проект успешно создан!\nВыберите параметр для редактирования.",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=await get_project_editing_kb(category=category, project_id=project_id))
    )

async def get_project_editing_kb(category: str, project_id: str):
    data = read_json_file(PATH_TO_PROJECTS_FILE)
    project_data = data[category].get(project_id, {})
    if not project_data:
        return []

    name = project_data.get("name", "").strip()
    project_mode = None
    if name.startswith(NON_DISPLAY_CHARACTER):
        project_mode = [InlineKeyboardButton(text="Опубликовать проект", callback_data=f"PROJECT-EDITING:::{category}:::{project_id}:::display_on")]
        name = f'Название: {name[len(NON_DISPLAY_CHARACTER):]}'
    else:
        project_mode = [InlineKeyboardButton(text="Спрятать проект", callback_data=f"PROJECT-EDITING:::{category}:::{project_id}:::display_off")]
        name = f'Название: {name}'
    
    description = f'Описание: {project_data.get("description", "")}'
    url = f'Ссылка на проект: {project_data.get("url", "")}'
    date = f'Дата окончания: {project_data.get("date", "")}'
    prize = f'Награда: {project_data.get("prize", 0)}'
    max_members = f'Максимальное кол-во участников: {project_data.get("max_members", 0)}'

    unleaveable = bool(project_data.get("unleaveable", 0))
    if unleaveable:
        unleave_btn = [InlineKeyboardButton(text="Разрешить выход из проекта", callback_data=f"PROJECT-EDITING:::{category}:::{project_id}:::unleaveable_off")]
    else:
        unleave_btn = [InlineKeyboardButton(text="Запретить выход из проекта", callback_data=f"PROJECT-EDITING:::{category}:::{project_id}:::unleaveable_on")]

    approval_required = bool(project_data.get("approval_required", 0))
    if approval_required:
        approval_btn = [InlineKeyboardButton(text="Отключить одобрение заявок", callback_data=f"PROJECT-EDITING:::{category}:::{project_id}:::approval_off")]
    else:
        approval_btn = [InlineKeyboardButton(text="Включить одобрение заявок", callback_data=f"PROJECT-EDITING:::{category}:::{project_id}:::approval_on")]

    kb = [
        [InlineKeyboardButton(text=name, callback_data=f"PROJECT-EDITING:::{category}:::{project_id}:::name")],
        [InlineKeyboardButton(text=description, callback_data=f"PROJECT-EDITING:::{category}:::{project_id}:::description")],
        [InlineKeyboardButton(text=date, callback_data=f"PROJECT-EDITING:::{category}:::{project_id}:::date")],
        [InlineKeyboardButton(text=prize, callback_data=f"PROJECT-EDITING:::{category}:::{project_id}:::prize")],
        [InlineKeyboardButton(text=url, callback_data=f"PROJECT-EDITING:::{category}:::{project_id}:::url")],
        [InlineKeyboardButton(text=max_members, callback_data=f"PROJECT-EDITING:::{category}:::{project_id}:::max_members")],
        [InlineKeyboardButton(text="Установить фотографию.", callback_data=f"PROJECT-EDITING:::{category}:::{project_id}:::preview_photo")],
        unleave_btn,
        approval_btn,  
        project_mode,
        [InlineKeyboardButton(text="Предпросмотр проекта", callback_data=f"PROJECT-PREVIEW:::{category}:::{project_id}")],
        [InlineKeyboardButton(text="Удалить проект", callback_data=f"PROJECT_REMOVE:::{category}:::{project_id}:::0")],
        [InlineKeyboardButton(text='🔙 В главное меню.', callback_data="back_to_main")]
    ]
    
    return kb

@router.callback_query(F.data.startswith("PROJECT-PREVIEW:::"))
async def new_project(callback: CallbackQuery, state: FSMContext):
    data_parts = callback.data.split(":::")
    category = data_parts[1]
    project_id = data_parts[2]
    await state.update_data(category=category, project_id=project_id)

    data = read_json_file(PATH_TO_PROJECTS_FILE)
    data_project = data[category].get(project_id, {})
    if not data_project:
        await callback.message.edit_text("❌ Проект не найден", reply_markup=await get_back_to_main_menu_kb())
        return
    
    name = data_project.get("name", "Без названия")
    description = data_project.get("description", "Без описания")
    date = data_project.get("date", "Не указана")
    prize = data_project.get("prize", "0")
    from utils import format_points
    prize_points = await format_points(int(prize))
    current_mem = len(data_project.get("members", {}))
    max_mem = data_project.get("max_members", "Нет ограничения")
    url = data_project.get("url")
    photo_path = data_project.get('preview_photo')
    
    users_data = read_json_file(PATH_TO_USERS_FILE)
    member_list = []
    for index, member_id in enumerate(data_project.get("members", {}), 1):
        try:
            member_list.append(f"{index}. {users_data.get(member_id, {}).get('name')} {users_data.get(member_id, {}).get('surname')}")
        except:
            member_list.append(f"{index}. Участник не найден")
    members = "\n".join(member_list)

    project_info = (
        f"<b>{name}</b>\n\n"
        f"{description}\n\n"
        f"🗓️ <b>Сроки: до {date}</b>\t"
        f"⭐️ <b>Награда: {prize_points}</b>\n" 
        f"👤 <b>Участники: {current_mem}/{max_mem}</b>\n"
        f"{members}"
    )
    
    if url:
        project_info += f"\n\n<a href='{url}'>Перейти к проекту</a>"
    
    kb = await get_back_to_project_editing_kb()
    
    if photo_path:
        try:
            with open(photo_path, 'rb') as file:
                photo_bytes = file.read()
            input_file = BufferedInputFile(photo_bytes, filename=os.path.basename(photo_path))
            await callback.message.answer_photo(
                photo=input_file,
                caption=project_info,
                reply_markup=kb,
                parse_mode="HTML"
            )
            await callback.message.delete()
        except:
            await callback.message.edit_text(project_info, reply_markup=kb, parse_mode="HTML")
    else:
        await callback.message.edit_text(project_info, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "back_to_project_editing")
async def back_to_project_editing(callback: CallbackQuery, state: FSMContext):
    state_data = await state.get_data()
    category = state_data.get('category', False)
    project_id = state_data.get('project_id', False)
    
    if project_id and category:
        await state.clear()
        if callback.message.photo:
            await callback.message.delete()
            await callback.message.answer(
                "Выберите параметр для редактирования.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=await get_project_editing_kb(category=category, project_id=project_id))
            )
        else:
            await callback.message.edit_text(
                "Выберите параметр для редактирования.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=await get_project_editing_kb(category=category, project_id=project_id))
            )
    else:
        return

@router.callback_query(F.data.startswith("PROJECT-EDITING:::"))
async def new_project(callback: CallbackQuery, state: FSMContext):
    data_parts = callback.data.split(":::")
    category = data_parts[1]
    project_id = data_parts[2]
    parm = data_parts[3]
    
    data = read_json_file(PATH_TO_PROJECTS_FILE)
    project_data = data[category].get(project_id, {})
    
    if not project_data:
        await callback.message.edit_text("❌ Проект не найден", reply_markup=await get_back_to_main_menu_kb())
        return
       
    if parm.startswith("unleaveable_"):
        parm_state = 1 if parm.replace("unleaveable_", "") == "on" else 0
        data[category][project_id]["unleaveable"] = int(parm_state)
        write_json_file(PATH_TO_PROJECTS_FILE, data)
        await state.clear()
        try:
            await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=await get_project_editing_kb(category=category, project_id=project_id)))
        except:
            await asyncio.sleep(0.5)
            await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=await get_project_editing_kb(category=category, project_id=project_id)))
        return

    if parm.startswith("approval_"):
        parm_state = 1 if parm.replace("approval_", "") == "on" else 0
        data[category][project_id]["approval_required"] = int(parm_state)
        write_json_file(PATH_TO_PROJECTS_FILE, data)
        await state.clear()
        try:
            await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=await get_project_editing_kb(category=category, project_id=project_id)))
        except:
            await asyncio.sleep(0.5)
            await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=await get_project_editing_kb(category=category, project_id=project_id)))
        return

    if parm.startswith("display_"):
        name = project_data.get("name", "")
        if name:
            if name.startswith(NON_DISPLAY_CHARACTER):
                name = name[len(NON_DISPLAY_CHARACTER):]
            else:
                name = f"{NON_DISPLAY_CHARACTER}{name}"
            data[category][project_id]["name"] = name
            write_json_file(PATH_TO_PROJECTS_FILE, data)
        await state.clear()
        try:
            await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=await get_project_editing_kb(category=category, project_id=project_id)))
        except:
            await asyncio.sleep(0.5)
            await callback.message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=await get_project_editing_kb(category=category, project_id=project_id)))
        return

    if parm == "preview_photo":
        await callback.message.edit_text(
            "Отправьте фото для проекта.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Отмена', callback_data="back_to_project_editing")]])
        )
        await state.set_state(ActiveState.editing_project_photo)
        await state.update_data(category=category, project_id=project_id)
        return
    
    await state.set_state(ActiveState.editing_project_parm)
    await state.update_data(category=category, project_id=project_id, parm=parm)

    value_tips = {
        "name": "Введите новое название проекта:",
        "description": "Введите новое описание проекта:",
        "url": "Введите ссылку на проект:",
        "date": "Введите новую дату окончания проекта:",
        "prize": "Введите новую награду за проект(баллы):",
        "max_members": "Введите максимальное количество участников проекта:"
    }
    
    await callback.message.edit_text(
        value_tips[parm],
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Отмена', callback_data="back_to_project_editing")]])
    )

@router.message(ActiveState.editing_project_photo, F.photo)
async def handle_photos(message: Message, state: FSMContext, bot: Bot):
    photo = message.photo[-1]
    file_id = photo.file_id
    file = await bot.get_file(file_id)
    file_path = file.file_path

    file_extension = os.path.splitext(file_path)[1] if file_path else '.jpg'
    state_data = await state.get_data()
    category = state_data.get('category', "")
    project_id = state_data.get('project_id',"")
    filename = f"project:::{category}:::{project_id}{file_extension}"
    save_path = os.path.join("media", filename)

    data = read_json_file(PATH_TO_PROJECTS_FILE)
    project_data = data[category].get(project_id, {})
    if not project_data:
        await callback.message.edit_text("❌ Проект не найден", reply_markup=await get_back_to_main_menu_kb())
        return

    data[category][project_id]["preview_photo"] = save_path
    write_json_file(PATH_TO_PROJECTS_FILE, data)

    await bot.download_file(file_path, save_path)

    await state.set_state(ActiveState.editing_menu_project)
    await state.update_data(category=category, project_id=project_id)
    await message.answer("✔️ Фото успешно сохранено!", reply_markup=await get_back_to_project_editing_kb())

@router.message(ActiveState.editing_project_parm, F.text)
async def handle_photos(message: Message, state: FSMContext):
    text = message.text
    state_data = await state.get_data()
    category = state_data.get('category')
    project_id = state_data.get('project_id')
    project_parm = state_data.get('parm')

    data = read_json_file(PATH_TO_PROJECTS_FILE)
    if not data[category].get(project_id):
        await message.answer("❌ Проект не найден", reply_markup=await get_back_to_main_menu_kb())
        return

    if project_parm == "date":
        if not await date_validation(text.strip()):
            await message.answer("❌ Введите корректную дату в формате дд.мм.гггг", reply_markup=await get_back_to_project_editing_kb())
            return

    if project_parm in ("prize", "max_members"):
        if not text.strip().isdigit():
            await message.answer("❌ Введите только число.", reply_markup=await get_back_to_project_editing_kb())
            return
        text = int(text.strip())

    if project_parm == "url":
        if not text.startswith(("https://", "http://")):
            await message.answer("❌ Введите корректную ссылку.", reply_markup=await get_back_to_project_editing_kb())
            return

    if project_parm == "description":
        len_of_message = len(text)
        if len_of_message > 850:
            await message.answer(f"❌ В описании не может быть больше 850 символов\n\nУ Вас - {len_of_message}", reply_markup=await get_back_to_project_editing_kb())
            return

    data[category][project_id][project_parm] = text
    write_json_file(PATH_TO_PROJECTS_FILE, data)
    
    await message.answer("✔️ Параметр изменен успешно", reply_markup=await get_back_to_project_editing_kb())

@router.message(F.chat.type == "private", Command(commands=["изменение_проекта","редактирование_проекта","edit_project"]))
async def edit_project(message: Message, state: FSMContext):
    user_id = str(message.from_user.id)
    if not await check_authorization(user_id):
        await send_not_authorized(message, state)
        return
        
    if not await is_moderator(user_id):
        await send_not_moderator(message)
        return
    
    await state.set_state(ActiveState.editing_menu_project)
    await state.update_data(editing_mode=True)
    await message.answer("👤 <b>Выберите категорию:</b>", reply_markup=await get_projects_menu_kb(), parse_mode="HTML")

@router.callback_query(F.data.startswith("PROJECT_FOR_EDITING:::"))
async def back_to_project_editing(callback: CallbackQuery, state: FSMContext):
    data_parts = callback.data.split(":::")
    category = data_parts[1]
    project_id = data_parts[2]

    if callback.message.photo:
        await callback.message.delete()
        await callback.message.answer(
            "Выберите параметр для редактирования.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=await get_project_editing_kb(category=category, project_id=project_id))
        )
    else:
        await callback.message.edit_text(
            "Выберите параметр для редактирования.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=await get_project_editing_kb(category=category, project_id=project_id))
        )

@router.message(F.chat.type == "private", Command(commands=["уведомление","оповещение","notification"]))
async def notification(message: Message, state: FSMContext):
    user_id = str(message.from_user.id)
    if not await check_authorization(user_id):
        await send_not_authorized(message, state)
        return
        
    if not await is_moderator(user_id):
        await send_not_moderator(message)
        return

    await state.set_state(ActiveState.waiting_for_notification)
    await state.update_data(notification_type="all_users")  # ✅ По умолчанию для всех
    await message.answer(
        "Введите сообщение для всех пользователей:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Отмена', callback_data="back_to_main")]])
    )

@router.callback_query(F.data.startswith("NOTIFY_PROJECT_MEMBERS:::"))
async def notify_project_members(callback: CallbackQuery, state: FSMContext):
    """Начало процесса оповещения участников проекта"""
    data_parts = callback.data.split(":::")
    category = data_parts[1]
    project_id = data_parts[2]
    
    await state.set_state(ActiveState.waiting_for_notification)
    await state.update_data(
        notification_type="project_members",
        project_category=category,
        project_id=project_id
    )
    
    await callback.message.delete()
    await callback.message.answer(
        f"Введите сообщение для участников проекта:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='🔙 К проекту', callback_data=f"PROJECT:::{category}:::{project_id}")]
        ]),
        parse_mode="HTML"
    )

@router.message(ActiveState.waiting_for_notification, F.text)
async def handle_notification_message(message: Message, state: FSMContext):
    state_data = await state.get_data()
    notification_type = state_data.get('notification_type', 'all_users')
    notification_message = message.text
    
    if notification_type == "project_members":
        category = state_data.get('project_category')
        project_id = state_data.get('project_id')
        
        await state.update_data(notification_message=notification_message)
        
        projects_data = read_json_file(PATH_TO_PROJECTS_FILE)
        project_data = projects_data.get(category, {}).get(project_id, {})
        project_name = project_data.get("name", "Неизвестный проект")
        display_name = project_name[len(NON_DISPLAY_CHARACTER):] if project_name.startswith(NON_DISPLAY_CHARACTER) else project_name
        members_count = len(project_data.get("members", {}))
        
        await message.answer(
            f"📢 <b>Оповещение участников проекта</b>\n\n"
            f"📋 Проект: {display_name}\n"
            f"👤 Участников: {members_count}\n\n"
            f"<b>Ваше сообщение:</b>\n{notification_message}\n\n"
            f"Сообщение будет отправлено {members_count} участникам, продолжить?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text='✅ Продолжить', callback_data="notification_send_continue")],
                [InlineKeyboardButton(text='❌ Отмена', callback_data=f"PROJECT:::{category}:::{project_id}")]
            ]),
            parse_mode="HTML"
        )
    else:
        await state.update_data(notification_message=notification_message)
        await message.answer(
            f"<b>Ваше сообщение для всех пользователей:</b>\n{notification_message}\n\n"
            f"Сообщение будет отправлено всем, продолжить?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text='✅ Продолжить', callback_data="notification_send_continue")],
                [InlineKeyboardButton(text='❌ Отмена', callback_data="back_to_main")]
            ]),
            parse_mode="HTML"
        )

@router.callback_query(F.data == "notification_send_continue")
async def send_notification(callback: CallbackQuery, state: FSMContext, bot: Bot):
    state_data = await state.get_data()
    notification = state_data.get('notification_message')
    notification_type = state_data.get('notification_type', 'all_users')
    
    await state.clear()
    
    if notification_type == "project_members":
        category = state_data.get('project_category')
        project_id = state_data.get('project_id')
        
        projects_data = read_json_file(PATH_TO_PROJECTS_FILE)
        project_data = projects_data.get(category, {}).get(project_id, {})
        project_name = project_data.get("name", "Неизвестный проект")
        display_name = project_name[len(NON_DISPLAY_CHARACTER):] if project_name.startswith(NON_DISPLAY_CHARACTER) else project_name
        members = project_data.get("members", {})
        
        sent_to_users = 0
        for member_id in members:
            from services import is_user_banned
            if await is_user_banned(member_id):
                continue
                
            try:
                await bot.send_message(
                    chat_id=member_id,
                    text=f"📢 <b>Оповещение от проекта:</b> {display_name}\n\n{notification}",reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text='🔙 К проекту', callback_data=f"PROJECT:::{category}:::{project_id}")],
                        [InlineKeyboardButton(text='🔙 В главное меню.', callback_data="back_to_main")]
                    ]),
                    parse_mode="HTML"
                )
                sent_to_users += 1
            except:
                continue
        
        await callback.message.edit_text(
            f"✅ Сообщение отправлено {sent_to_users} участникам проекта <b>{display_name}</b>",
            
            parse_mode="HTML"
        )
    else:
        data = read_json_file(PATH_TO_USERS_FILE)
        sent_to_users = 0
        for user_id in data.keys():
            if data[user_id].get("ban", 0) == 1:
                continue
                
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=notification,
                    reply_markup=await get_back_to_main_menu_kb(),
                    parse_mode="HTML"
                )
                sent_to_users += 1
            except:
                continue

        await callback.message.edit_text(
            f"✅ Сообщение отправлено {sent_to_users} пользователям.",
            reply_markup=await get_back_to_main_menu_kb()
        )

@router.message(F.chat.type == "private", Command(commands=["написать","write_to_user","write", "написать_пользователю"]))
async def notification(message: Message, state: FSMContext):
    user_id = str(message.from_user.id)
    if not await check_authorization(user_id):
        await send_not_authorized(message, state)
        return
        
    if not await is_moderator(user_id):
        await send_not_moderator(message)
        return
    if len(message.text.split()) == 1:
        await message.answer(
        "❌ id пользователя не указан",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Отмена', callback_data="back_to_main")]])
        )
        return

    user_dest_id = message.text.split()[1]
    if not user_dest_id.isdigit():
        await message.answer(
        "❌ id пользователя не найдено",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Отмена', callback_data="back_to_main")]])
        )
        return

    if not await check_authorization(user_dest_id):
        await message.answer(
        "❌ Пользователь с таким id не найден",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Отмена', callback_data="back_to_main")]])
        )
        return

    await state.set_state(ActiveState.waiting_for_message_to_user)
    await state.update_data(user_dest_id=user_dest_id)
    await message.answer(
        "Введите сообщение для пользователя",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Отмена', callback_data="back_to_main")]])
    )

@router.message(ActiveState.waiting_for_message_to_user, F.text)
async def handle_message(message: Message, state: FSMContext, bot: Bot):
    state_data = await state.get_data()
    user_dest_id = state_data.get('user_dest_id')
    if not await check_authorization(user_dest_id):
        await message.answer(
        "❌ Пользователь с таким id не найден",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Отмена', callback_data="back_to_main")]])
        )
        return

    text = f"Сообщение от администрации: {message.text}"
    try:
        await bot.send_message(
            chat_id=user_dest_id,
            text=text,
            reply_markup=await get_back_to_main_menu_kb(),
            parse_mode="HTML"
        )
        await message.answer(
        "✔️ Сообщение успешно отправлено",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Отмена', callback_data="back_to_main")]])
        )
        return
    except:
        await message.answer(
        "❌ Сообщение не удалось отправить",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Отмена', callback_data="back_to_main")]])
        )
        return

@router.message(Command("завершенные_проекты"))
async def test(message: Message):
    user_id = str(message.from_user.id)
    if not await check_authorization(user_id):
        await send_not_authorized(message)
        return        
    if not await is_moderator(user_id):
        await send_not_moderator(message)
        return
    from scheduler import ask_for_removing_old_projects
    await ask_for_removing_old_projects()

@router.message(Command("проверить_проекты_на_окончание"))
async def test(message: Message):
    user_id = str(message.from_user.id)
    if not await check_authorization(user_id):
        await send_not_authorized(message)
        return        
    if not await is_moderator(user_id):
        await send_not_moderator(message)
        return
    from scheduler import check_completed_projects
    await check_completed_projects()


@router.callback_query(F.data.startswith("APPROVE_USER_PROJECT:::"))
async def approve_user_project(callback: CallbackQuery, bot: Bot):
    data_parts = callback.data.split(":::")
    user_id = data_parts[1]
    category = data_parts[2]
    project_id = data_parts[3]
    
    from services import add_member_to_project
    result = await add_member_to_project(user_id, category, project_id)
    
    if result["status"]:
        await callback.message.edit_text(
            f"{callback.message.text}\n\n✅ <b>Добавлен(а) администрацией</b>",
            parse_mode="HTML"
        )
        
        projects_data = read_json_file(PATH_TO_PROJECTS_FILE)
        project_data = projects_data.get(category, {}).get(project_id, {})
        project_name = project_data.get("name", "Без названия")
        display_name = project_name[len(NON_DISPLAY_CHARACTER):] if project_name.startswith(NON_DISPLAY_CHARACTER) else project_name
        
        try:
            await bot.send_message(
                chat_id=user_id,
                text=f"✅ Вы были добавлены в проект <b>{display_name}</b> администрацией",
                parse_mode="HTML"
            )
        except:
            pass  
    else:
        await callback.message.edit_text(
            f"{callback.message.text}\n\n❌ <b>Ошибка при добавлении: {result['error']}</b>",
            parse_mode="HTML"
        )
    
    await callback.answer()

@router.callback_query(F.data.startswith("DECLINE_USER_PROJECT:::"))
async def decline_user_project(callback: CallbackQuery, bot: Bot):
    data_parts = callback.data.split(":::")
    user_id = data_parts[1]
    category = data_parts[2]
    project_id = data_parts[3]
    
    await callback.message.edit_text(
        f"{callback.message.text}\n\n❌ <b>Не добавлен(а) администрацией</b>",
        parse_mode="HTML"
    )
    
    projects_data = read_json_file(PATH_TO_PROJECTS_FILE)
    project_data = projects_data.get(category, {}).get(project_id, {})
    project_name = project_data.get("name", "Без названия")
    display_name = project_name[len(NON_DISPLAY_CHARACTER):] if project_name.startswith(NON_DISPLAY_CHARACTER) else project_name
    
    try:
        await bot.send_message(
            chat_id=user_id,
            text=f"❌ Ваша заявка на участие в проекте <b>{display_name}</b> отклонена администрацией",
            parse_mode="HTML"
        )
    except:
        pass  
    
    await callback.answer()

async def deleting_project(category: str, project_id: str):
    try:
        data_pr = read_json_file(PATH_TO_PROJECTS_FILE)
        if category not in data_pr or project_id not in data_pr[category]:
            return {"status": False, "error": "category or project not found"}
        
        if data_pr[category][project_id].get("members", {}):
            for member in data_pr[category][project_id]["members"]:
                await removing_project_from_members(user_id=member, category=category, project_id=project_id)
        
        photo_path = data_pr[category][project_id].get("preview_photo")
        if photo_path and os.path.exists(photo_path):
            os.remove(photo_path)
        
        del data_pr[category][project_id]
        write_json_file(PATH_TO_PROJECTS_FILE, data_pr)
        return {"status": True, "error": "success"}
    except:
        return {"status": False, "error": "ValueError send correct values"}

async def removing_project_from_members(user_id: str, category: str, project_id: str):
    try:
        data_us = read_json_file(PATH_TO_USERS_FILE)
        if user_id not in data_us:
            return {"status": False, "error": "user not found"}
        
        active_projects = data_us[user_id].get("active_projects", [])
        project_value = f'{category}:::{project_id}'
        if project_value in active_projects:
            data_us[user_id]["active_projects"].remove(project_value)
            data_us[user_id]["completed_projects"] = int(data_us[user_id]["completed_projects"]) + 1
            write_json_file(PATH_TO_USERS_FILE, data_us)
        return {"status": True, "error": "success"}
    except:
        return {"status": False, "error": "ValueError send correct values"}

@router.callback_query(F.data.startswith("PROJECT_REMOVE:::"))
async def button_handler(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    data_parts = callback.data.split(":::")
    category = data_parts[1]
    project_id = data_parts[2]
    rewarding = data_parts[3]
    
    await state.set_state(ActiveState.confirmation_project_ending)
    rewarding = bool(int(rewarding)) if rewarding.isdigit() else False
    await state.update_data(category=category, project_id=project_id, rewarding=bool(rewarding))
    
    confirm_word = "Награда" if bool(rewarding) else "Удаление"
    await callback.message.answer(f"Введите '{confirm_word}' для подтверждения.")

@router.message(ActiveState.confirmation_project_ending, F.text)
async def handle_photos(message: Message, state: FSMContext):
    data = await state.get_data()
    category = data.get("category", False)
    project_id = data.get("project_id", False)
    is_rewarding = data.get("rewarding", False)
    
    if not category or not project_id:
        return
    
    text = message.text
    data_pr = read_json_file(PATH_TO_PROJECTS_FILE)

    if is_rewarding:
        if text.strip() == "Награда":
            status = await give_reward_to_project_members(category=category, project_id=project_id)
            if not status["status"]:
                await message.answer("❌ Удаление прервано, не получилось наградить всех участников.")
                if message.chat.type == "private":
                    return
                else:
                    await send_project_to_moderators(category=category, project_id=project_id, bot=message.bot)
            
            name_text = "🔚 Завершён:"
            name = data_pr[category][project_id]["name"][len(name_text):].strip() if data_pr[category][project_id]["name"].startswith(name_text) else data_pr[category][project_id]["name"]
            await deleting_project(category=category, project_id=project_id)
            await message.answer(f"✔️ Проект: {name} - Успешно завершён модератором @{message.from_user.username}\nНаграду получило: {status['members']} участников.")
        else:
            await message.answer("❌ Удаление прервано")
            if message.chat.type == "private":
                return
            else:
                await send_project_to_moderators(category=category, project_id=project_id, bot=message.bot)
    else:
        if text.strip() == "Удаление":
            name_text = "🔚 Завершён:"
            name = data_pr[category][project_id]["name"][len(name_text):].strip() if data_pr[category][project_id]["name"].startswith(name_text) else data_pr[category][project_id]["name"]
            await deleting_project(category=category, project_id=project_id)
            await message.answer(f"✔️ Проект: {name} - Успешно удалён модератором @{message.from_user.username}")
        else:
            await message.answer("❌ Удаление прервано")
            if message.chat.type == "private":
                return
            else:
                await send_project_to_moderators(category=category, project_id=project_id, bot=message.bot)
    
    await state.clear()

async def send_project_to_moderators(category: str, project_id: str, bot: Bot):
    data_pr = read_json_file(PATH_TO_PROJECTS_FILE)
    name_text = "🔚 Завершён:"
    prize = data_pr[category][project_id].get("prize", 0)
    from utils import format_points
    prize_for_project = await format_points(int(prize))
    
    name = data_pr[category][project_id]["name"][len(name_text):].strip() if data_pr[category][project_id]["name"].startswith(name_text) else data_pr[category][project_id]["name"]
    
    users_data = read_json_file(PATH_TO_USERS_FILE)
    member_list = []
    for index, member_id in enumerate(data_pr[category][project_id].get("members", {}), 1):
        try:
            member_list.append(f"{index}. {users_data.get(member_id, {}).get('name')} {users_data.get(member_id, {}).get('surname')}")
        except:
            member_list.append(f"{index}. Участник не найден")
    members = "\n".join(member_list)

    caption = f"Проект: <b>{name}</b> - завершён.\n\nНаграда: {prize_for_project}.\nНаградить участников:{len(member_list)}\n{members}"
    
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='Наградить всех участников', callback_data=f"PROJECT_REMOVE:::{category}:::{project_id}:::1")],
            [InlineKeyboardButton(text='Удалить проект', callback_data=f"PROJECT_REMOVE:::{category}:::{project_id}:::0")]
        ])
    
    photo_path = data_pr[category][project_id].get('preview_photo')
    if not photo_path:
        await bot.send_message(
            chat_id=MODERATORS_CHAT_ID,
            text=caption,
            reply_markup=kb,
            parse_mode="HTML"
        )
    else:
        try:
            with open(photo_path, 'rb') as file:
                photo_bytes = file.read()
            input_file = BufferedInputFile(photo_bytes, filename=os.path.basename(photo_path))
            await bot.send_photo(
                chat_id=MODERATORS_CHAT_ID,
                photo=input_file,
                caption=caption,
                reply_markup=kb,
                parse_mode="HTML"
            )
        except:
            await bot.send_message(
                chat_id=MODERATORS_CHAT_ID,
                text=caption,
                reply_markup=kb,
                parse_mode="HTML"
            )

@router.message(Command("команды"))
async def notification(message: Message):
    if not await is_moderator(str(message.from_user.id)):
        await send_not_moderator(message)
        return

    text = (
        "Список всех команд бота\n"
        "Команда - Описание\n"
        "***         Основные         ***\n"
        "/start - Вызов главного меню\n\n"
        "/notification - Уведомление для всех пользователей бота\n\n"
        "/report - Обратная связь, написать администрации бота\n\n"
        "\n"
        "***   Управление проектами   ***\n"
        "/new_project - Создание нового проекта\n\n"
        "/edit_project - Режим редактирования проектов\n\n"
        "\n"   
        "***   Управление пользователями   ***\n" 
        "/all_members - Список всех пользователей\n\n"
        "/search - Поиск пользователей по имени/телефону/id первых\n"
        "/write - Написать пользователю\n\n"
        "/edit_user - Изменение параметров пользователей\n\n"
        "/remove_user - Полное удаление пользователя\n\n"
        "/ban - Заблокировать пользователя\n\n"
        "/unban - Разблокировать пользователя\n\n"
        "\n"   
    )
    await message.answer(text, reply_markup=await get_back_to_main_menu_kb())

