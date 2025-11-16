import json
import os
import random
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, BufferedInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command, CommandObject

from config import PATH_TO_PROJECTS_FILE, PATH_TO_USERS_FILE, NON_DISPLAY_CHARACTER, MEMBERS_IN_MEMBERSLIST, MODERATORS_CHAT_ID
from states import ActiveState
from utils import read_json_file, check_authorization, is_moderator
from services import add_member_to_project, remove_member_from_project, get_project_data, get_all_projects, check_project_registration
from keyboards import get_projects_menu_kb, generate_projects_category_menu_kb, get_back_to_main_menu_kb, get_approval_request_kb

router = Router()

@router.callback_query(F.data == "menu_projects")
async def project_categories_menu(callback: CallbackQuery, state: FSMContext):
    if not await check_authorization(callback.from_user.id):
        return
    
    await state.clear()
    await state.set_state(ActiveState.projects_menu)
    await callback.message.edit_text(
        "👤 <b>Выберите категорию:</b>",
        reply_markup=await get_projects_menu_kb(),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("menu_project_category_"))
async def project_menu(callback: CallbackQuery, state: FSMContext):
    category = callback.data.replace("menu_project_category_", "")
    await state.update_data(selected_project_category=category)

    state_data = await state.get_data()
    is_editing_mode = bool(state_data.get('editing_mode', False))
        
    data = read_json_file(PATH_TO_PROJECTS_FILE).get(category, {})

    category_names = {
        "education": "🎓 Образование и знания",
        "science": "🔬 Наука и технологии", 
        "profession": "🧑‍🏫 Труд, профессия и своё дело",
        "culture": "🎺 Культура и искусство",
        "volunteering": "🌍 Волонтёрство и добровольчество",
        "patriotism": "🇷🇺 Патриотизм и историческая память",
        "sport": "🏃 Спорт и здоровый образ жизни",
        "other": "🧩 Другое"
    }    

    if not data:
        await callback.message.edit_text(
            f"❗ В категории <b>{category_names[category]}</b> нет доступных проектов\n\n"
            f"👤 <b>Выберите категорию:</b>",
            reply_markup=await get_projects_menu_kb(),
            parse_mode="HTML"
        )
        return

    data_projects = data.values()
    projects_id = list(data.keys())
    projects_name = [project["name"] for project in data_projects]

    if NON_DISPLAY_CHARACTER and not is_editing_mode:
        user_id = str(callback.from_user.id)
        filtered_projects_name = []
        filtered_projects_id = []
        filtered_projects_max_members = []
        filtered_projects_current_members = []
        
        for name, project_id, project in zip(projects_name, projects_id, data_projects):
            # показывать проект если:
            # - Он не скрыт 
            # - Пользователь участник проекта 
            # - Режим редактирования
            show_project = (
                not name.startswith(NON_DISPLAY_CHARACTER) or
                user_id in project.get("members", {}) or
                is_editing_mode
            )
            
            if show_project:
                display_name = name[len(NON_DISPLAY_CHARACTER):] if name.startswith(NON_DISPLAY_CHARACTER) else name
                filtered_projects_name.append(display_name)
                filtered_projects_id.append(project_id)
                filtered_projects_max_members.append(project.get("max_members", 100))
                filtered_projects_current_members.append(len(project.get("members", {})))
        
        projects_name = filtered_projects_name
        projects_id = filtered_projects_id
        projects_max_members = filtered_projects_max_members
        projects_current_members = filtered_projects_current_members
    else:
        projects_max_members = [project["max_members"] for project in data_projects]
        projects_current_members = [len(project["members"]) for project in data_projects]
        
    projects_members = [f"{c}/{m}" if m is not None else "" for c, m in zip(projects_current_members, projects_max_members)]
    projects_preview = [name + " " + members for name, members in zip(projects_name, projects_members)]
    
    if callback.message.photo:
        await callback.message.delete()
        await callback.message.answer(
            f"Категория: <b>{category_names[category]}</b>\n\n"
            f"👤 <b>Выберите проект:</b>",
            reply_markup=await generate_projects_category_menu_kb(projects_preview, projects_id, category, is_editing_mode=is_editing_mode),
            parse_mode="HTML"
        ) 
    else:
        await callback.message.edit_text(
            f"Категория: <b>{category_names[category]}</b>\n\n"
            f"👤 <b>Выберите проект:</b>",
            reply_markup=await generate_projects_category_menu_kb(projects_preview, projects_id, category, is_editing_mode=is_editing_mode),
            parse_mode="HTML"
        )

@router.callback_query(F.data.startswith("PROJECT:::"))
async def project_info(callback: CallbackQuery, state: FSMContext):
    from utils import format_points, format_member_count
    
    data_parts = callback.data.split(":::")
    category = data_parts[1]
    project_id = data_parts[2]
    user_id = str(callback.from_user.id)

    data = read_json_file(PATH_TO_PROJECTS_FILE)
    data_project = data.get(category, {}).get(project_id)

    back_btn = [InlineKeyboardButton(text='🔙 Назад', callback_data=f"menu_project_category_{category}")]

    if not data_project:
        await callback.message.edit_text(
            "❗ <b>Проект не найден</b> ❗",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[back_btn]),
            parse_mode="HTML"
        )
        return
    
    not_unleaveable = not bool(data_project.get("unleaveable", 0))
    name = data_project.get("name", "Без названия")
    display_name = name[len(NON_DISPLAY_CHARACTER):] if name.startswith(NON_DISPLAY_CHARACTER) else name
    description = data_project.get("description", "Без описания")
    date = data_project.get("date", "Не указана")
    prize = data_project.get("prize", "0")
    
    prize_points = await format_points(int(prize))
    
    current_mem = len(data_project.get("members", {}))
    max_mem = data_project.get("max_members", 1000)
    url = data_project.get("url")
    photo_path = data_project.get('preview_photo')

    is_member = user_id in data_project.get("members", {})

    data_users = read_json_file(PATH_TO_USERS_FILE)
    member_list = []
    if is_member:
        member_list.append(f"1. {data_users.get(user_id, {}).get('name')} {data_users.get(user_id, {}).get('surname')}")
    
    for member_id in data_project.get("members", {}):
        if user_id != member_id:
            try:
                member_data = data_users.get(member_id, {})
                member_list.append(f"{len(member_list)+1}. {member_data.get('name')} {member_data.get('surname')}")
            except:
                member_list.append(f"{len(member_list)+1}. Участник не найден")

    many_members = len(member_list) > MEMBERS_IN_MEMBERSLIST
    if many_members:
        len_mem_list = len(member_list) - MEMBERS_IN_MEMBERSLIST
        member_list = member_list[:MEMBERS_IN_MEMBERSLIST]
        more_members = await format_member_count(len_mem_list)
        member_list.append(f"\n... и еще {more_members} ...")
    
    members = "\n".join(member_list)

    project_info = (
        f"<b>{display_name}</b>\n\n"
        f"{description}\n\n"
        f"🗓️ <b>Сроки: до {date}</b>\n"
        f"⭐️ <b>Награда: {prize_points}</b>\n" 
        f"👤 <b>Участники: {current_mem}/{max_mem}</b>\n"
        f"{members}"
    )
    
    if url:
        project_info += f"\n\n<a href='{url}'>Перейти к проекту</a>"

    kb = []

    access = await check_project_registration(user_id)
    
    is_moderator_bool = await is_moderator(user_id)
    completed = bool(data_project.get("completed", False))
    
    if many_members:
        members_btn = [InlineKeyboardButton(text="👤 Список всех участников", callback_data=f"MEMBERS_LIST:::{category}:::{project_id}:::{int(is_moderator_bool)}")]
        kb.append(members_btn)

    if is_member:
        report_btn = [InlineKeyboardButton(text="📷 Отправить отчет о проекте", callback_data=f"REPORT:::{category}:::{project_id}")]
        kb.append(report_btn)

    if not access["status"]:
        project_info += "\n\n<b>❗ Для участия в проектах укажите все необходимые данные ❗</b>"
    
    free_places = True if current_mem < max_mem else False

    approval_required = bool(data_project.get("approval_required", 0))
    
    if access["status"] and not is_member and free_places and not completed:
        if approval_required:
            join_project_btn = [InlineKeyboardButton(
                text='📨 Подать заявку', 
                callback_data=f"REQUEST_JOIN_PROJECT:::{user_id}:::{category}:::{project_id}"
            )]
        else:
            request = "JOIN_PROJECT" if not_unleaveable else "JOIN_UL_PROJECT"
            join_project_btn = [InlineKeyboardButton(
                text='✔️ Участвовать', 
                callback_data=f"{request}:::{user_id}:::{category}:::{project_id}"
            )]
        kb.append(join_project_btn)

    if access["status"] and is_member and not_unleaveable:
        leave_project_btn = [InlineKeyboardButton(text='❌ Покинуть', callback_data=f"LEAVE_PROJECT:::{user_id}:::{category}:::{project_id}")] 
        kb.append(leave_project_btn)
    
    kb.append(back_btn)

    if is_moderator_bool:
        kb.append([InlineKeyboardButton(text='✏️ Редактировать', callback_data=f"PROJECT_FOR_EDITING:::{category}:::{project_id}")])
        if free_places:
            kb.append([InlineKeyboardButton(text='🎲 Добавить участников', callback_data=f"ADD_RANDOM_MEMBERS:::{category}:::{project_id}")])
        kb.append([InlineKeyboardButton(text='📢 Оповестить всех участников', callback_data=f"NOTIFY_PROJECT_MEMBERS:::{category}:::{project_id}")])
        kb.append([InlineKeyboardButton(text='🏆 Наградить всех участников', callback_data=f"PROJECT_REMOVE:::{category}:::{project_id}:::1")])
        kb.append([InlineKeyboardButton(text='🗑️ Удалить проект', callback_data=f"PROJECT_REMOVE:::{category}:::{project_id}:::0")])
        
    kb_end = InlineKeyboardMarkup(inline_keyboard=kb)
    
    if photo_path:
        try:
            with open(photo_path, 'rb') as file:
                photo_bytes = file.read()
            input_file = BufferedInputFile(photo_bytes, filename=photo_path)
            await callback.message.answer_photo(
                photo=input_file,
                caption=project_info,
                reply_markup=kb_end,
                parse_mode="HTML"
            )
            await callback.message.delete()
        except:
            await callback.message.edit_text(
                project_info,
                reply_markup=kb_end,
                parse_mode="HTML"
            )
    else:
        await callback.message.edit_text(
            project_info,
            reply_markup=kb_end,
            parse_mode="HTML"
        )

@router.callback_query(F.data.startswith("REQUEST_JOIN_PROJECT:::"))
async def request_join_project(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data_parts = callback.data.split(":::")
    user_id = data_parts[1]
    category = data_parts[2]
    project_id = data_parts[3]
    
    projects_data = read_json_file(PATH_TO_PROJECTS_FILE)
    users_data = read_json_file(PATH_TO_USERS_FILE)
    
    project_data = projects_data.get(category, {}).get(project_id, {})
    user_data = users_data.get(user_id, {})
    
    if not project_data or not user_data:
        await callback.answer("❌ Ошибка: проект или пользователь не найден")
        return
    
    project_name = project_data.get("name", "Без названия")
    display_project_name = project_name[len(NON_DISPLAY_CHARACTER):] if project_name.startswith(NON_DISPLAY_CHARACTER) else project_name
    cur_m = len(project_data.get("members", 0))
    max_m = project_data.get("max_members", 0)

    user_name = f"{user_data.get('name', '')} {user_data.get('surname', '')}".strip()
    if not user_name:
        user_name = user_data.get('username', 'Неизвестный пользователь')

    category_names = {
        "education": "🎓 Образование и знания",
        "science": "🔬 Наука и технологии", 
        "profession": "🧑‍🏫 Труд, профессия и своё дело",
        "culture": "🎺 Культура и искусство",
        "volunteering": "🌍 Волонтёрство и добровольчество",
        "patriotism": "🇷🇺 Патриотизм и историческая память",
        "sport": "🏃 Спорт и здоровый образ жизни",
        "other": "🧩 Другое"
    }    

    request_text = (
        f"📨 <b>Запрос на участие в проекте</b>\n\n"
        f"👤 <b>Пользователь:</b> {user_name} (ID: {user_id})\n"
        f"📋 <b>Проект:</b> {display_project_name}\n"
        f"📁 <b>Категория:</b> {category_names[category]}\n"
        f"👤 <b>Участники:</b> {cur_m}/{max_m}"
    )
    
    try:
        await bot.send_message(
            chat_id=MODERATORS_CHAT_ID,
            text=request_text,
            reply_markup=await get_approval_request_kb(user_id, category, project_id),
            parse_mode="HTML"
        )
        await callback.answer("✅ Заявка отправлена на рассмотрение администрации")
    except Exception as e:
        await callback.answer("❌ Ошибка при отправке заявки")
        print(f"Error sending approval request: {e}")

@router.callback_query(F.data.startswith("MEMBERS_LIST:::"))
async def project_full_members_list(callback: CallbackQuery, state: FSMContext):
    data_parts = callback.data.split(":::")
    category = data_parts[1]
    project_id = data_parts[2]
    user_id = str(callback.from_user.id)

    data = read_json_file(PATH_TO_PROJECTS_FILE)
    data_project = data.get(category,{}).get(project_id)
    if not data_project:
        await callback.message.delete()
        await callback.answer(
            "❗ <b>Проект не найден</b> ❗",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='🔙 Назад', callback_data=f"menu_project_category_{category}")]]),
            parse_mode="HTML"
        )
        return
      
    current_mem = len(data_project.get("members", {})) 
    max_mem = data_project.get("max_members", "Нет ограничения")
    is_member = user_id in data_project.get("members", {})
    data_users = read_json_file(PATH_TO_USERS_FILE)
    member_list = []
    if is_member:
        member_list.append(f"1. {data_users.get(user_id, {}).get('name')} {data_users.get(user_id, {}).get('surname')}")
    for member_id in data_project.get("members", {}):
        if user_id != member_id:
            try:
                member_data = data_users.get(member_id, {})
                member_list.append(f"{len(member_list)+1}. {member_data.get('name')} {member_data.get('surname')}")
            except:
                member_list.append(f"{len(member_list)+1}. Участник не найден")
    members = "\n".join(member_list)
    text = f"👤 <b>Все участники проекта: {current_mem}/{max_mem}</b>\n{members}"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='🔙 Назад', callback_data=f"PROJECT:::{category}:::{project_id}")]])  
    if callback.message.photo:
        await callback.message.delete()
        await callback.message.answer(
            text=text,
            reply_markup=kb,
            parse_mode="HTML"
        )
        return 
    else:        
        await callback.message.edit_text(
            text=text,
            reply_markup=kb,
            parse_mode="HTML"
        )
        return

@router.callback_query(F.data.startswith("JOIN_UL_PROJECT:::"))
async def join_ul_project(callback: CallbackQuery, state: FSMContext):
    data_parts = callback.data.split(":::")
    user_id = data_parts[1]
    category = data_parts[2]
    project_id = data_parts[3]

    await callback.message.answer(
        "Из этого проекта <b>нельзя будет выйти</b>.\nПродолжить?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='✔️ Подтвердить участие', callback_data=f"JOIN_PROJECT:::{user_id}:::{category}:::{project_id}")],
            [InlineKeyboardButton(text='🔙 Отмена', callback_data=f"PROJECT:::{category}:::{project_id}")]
        ]),
        parse_mode="HTML"
    )
    await callback.message.delete()
    await callback.answer()
    return

@router.callback_query(F.data.startswith("JOIN_PROJECT:::"))
async def join_project(callback: CallbackQuery, state: FSMContext):
    data_parts = callback.data.split(":::")
    user_id = data_parts[1]
    category = data_parts[2]
    project_id = data_parts[3]

    success = await add_member_to_project(user_id, category, project_id)

    back_btn = [InlineKeyboardButton(text='🔙 К проекту', callback_data=f"PROJECT:::{category}:::{project_id}")]

    if success["status"]:
        await callback.message.answer(
            "✔️ Вы были добавлены в проект!\nТеперь не забудь подать заявку на сайте Движения Первых",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[back_btn])
        )
        await callback.message.delete()
        await callback.answer()
    elif success["error"] == "no free places":
        await callback.message.answer(
            "❌ В проекте нет свободного места",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[back_btn])
        )
        await callback.message.delete()
        await callback.answer()
    else:
        await callback.message.answer(
            "❌ Возникла ошибка при добавлении в проект, попробуйте еще раз или обратитесь к медераторам",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[back_btn])
        )
        await callback.message.delete()
        await callback.answer()

@router.callback_query(F.data.startswith("LEAVE_PROJECT:::"))
async def project_info(callback: CallbackQuery, state: FSMContext):
    data_parts = callback.data.split(":::")
    user_id = data_parts[1]
    category = data_parts[2]
    project_id = data_parts[3]

    success = await remove_member_from_project(user_id, category, project_id)

    back_btn = [InlineKeyboardButton(text='🔙 К проекту', callback_data=f"PROJECT:::{category}:::{project_id}")]

    if success["status"]:
        await callback.message.answer(
            "✔️ Вы покинули в проект!\nТеперь не забудь выйти из проекта на сайте Движения Первых",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[back_btn])
        )
        await callback.message.delete()
        await callback.answer()
    else:
        await callback.message.answer(
            "❌ Возникла ошибка при выходе из проекта, попробуйте еще раз или обратитесь к медераторам",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[back_btn])
        )
        await callback.message.delete()
        await callback.answer()
        
###
@router.callback_query(F.data.startswith("ADD_RANDOM_MEMBERS:::"))
async def add_random_members_start(callback: CallbackQuery, state: FSMContext):
    data_parts = callback.data.split(":::")
    category = data_parts[1]
    project_id = data_parts[2]
    
    projects_data = read_json_file(PATH_TO_PROJECTS_FILE)
    project_data = projects_data.get(category, {}).get(project_id, {})
    
    if not project_data:
        await callback.answer("❌ Проект не найден")
        return
    
    current_members = len(project_data.get("members", {}))
    max_members = project_data.get("max_members", 100)
    free_places = max_members - current_members
    
    if free_places <= 0:
        await callback.answer("❌ В проекте нет свободных мест")
        return
    
    project_name = project_data.get("name", "Неизвестный проект")
    display_name = project_name[len(NON_DISPLAY_CHARACTER):] if project_name.startswith(NON_DISPLAY_CHARACTER) else project_name
    
    await state.set_state(ActiveState.waiting_random_members_count)
    await state.update_data(
        category=category,
        project_id=project_id,
        project_name=display_name,
        free_places=free_places
    )
    
    await callback.message.delete()
    await callback.message.answer(
        f"🎲 <b>Добавление случайных участников</b>\n\n"
        f"📋 Проект: {display_name}\n"
        f"🆓 Свободных мест: {free_places}\n\n"
        f"Введите количество пользователей для добавления (1-{free_places}):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='🔙 К проекту', callback_data=f"PROJECT:::{category}:::{project_id}")]
        ]),
        parse_mode="HTML"
    )

@router.message(ActiveState.waiting_random_members_count, F.text)
async def handle_random_members_count(message: Message, state: FSMContext):
    state_data = await state.get_data()
    category = state_data.get('category')
    project_id = state_data.get('project_id')
    project_name = state_data.get('project_name')
    free_places = state_data.get('free_places')
    
    try:
        count = int(message.text.strip())
        if count < 1 or count > free_places:
            await message.answer(
                f"❌ Введите число от 1 до {free_places}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text='🔙 К проекту', callback_data=f"PROJECT:::{category}:::{project_id}")]
                ])
            )
            return
    except ValueError:
        await message.answer(
            "❌ Введите целое число",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text='🔙 К проекту', callback_data=f"PROJECT:::{category}:::{project_id}")]
            ])
        )
        return
    
    candidates = await generate_random_candidates(category, project_id, count)
    
    if not candidates:
        await message.answer(
            "❌ Не найдено подходящих пользователей для добавления",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text='🔙 К проекту', callback_data=f"PROJECT:::{category}:::{project_id}")]
            ])
        )
        return
    
    await state.update_data(
        random_candidates=candidates,
        random_count=count
    )
    
    candidates_text = await format_candidates_list(candidates)
    await message.answer(
        f"🎲 <b>Список пользователей для добавления</b> ({len(candidates)}):\n\n"
        f"{candidates_text}\n\n"
        f"Добавить этих пользователей в проект?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text='✅ Да, добавить', callback_data="CONFIRM_ADD_RANDOM"),
                InlineKeyboardButton(text='🔄 Перегенерировать', callback_data="REGENERATE_RANDOM")
            ],
            [InlineKeyboardButton(text='❌ Нет, отмена', callback_data=f"PROJECT:::{category}:::{project_id}")]
        ]),
        parse_mode="HTML"
    )

async def generate_random_candidates(category: str, project_id: str, count: int):
    users_data = read_json_file(PATH_TO_USERS_FILE)
    projects_data = read_json_file(PATH_TO_PROJECTS_FILE)
    
    project_members = projects_data.get(category, {}).get(project_id, {}).get("members", {})
    
    eligible_users = []
    
    for user_id, user_data in users_data.items():
        if (user_id not in project_members and
            user_data.get("ban", 0) == 0 and
            await check_user_registration(user_data) and
            user_data.get("score", 0) >= 0):
            
            eligible_users.append({
                'user_id': user_id,
                'name': user_data.get('name', ''),
                'surname': user_data.get('surname', ''),
                'username': user_data.get('username', ''),
                'score': user_data.get('score', 0)
            })
    
    if not eligible_users:
        return []
    
    if len(eligible_users) <= count:
        return eligible_users
    
    random.shuffle(eligible_users)
    return eligible_users[:count]

async def check_user_registration(user_data: dict) -> bool:
    required_fields = ["name", "surname", "IDfirst", "phone"]
    for field in required_fields:
        if user_data.get(field, "Не указано") == "Не указано":
            return False
    return True

async def format_candidates_list(candidates: list) -> str:
    text = ""
    for i, candidate in enumerate(candidates, 1):
        name = f"{candidate['name']} {candidate['surname']}".strip()
        username = f"@{candidate['username']}" if candidate['username'] else "нет username"
        score = candidate['score']
        
        text += f"{i}. {name} ({username}) - {score} баллов\n"
    
    return text

@router.callback_query(F.data == "REGENERATE_RANDOM")
async def regenerate_random_candidates(callback: CallbackQuery, state: FSMContext):
    state_data = await state.get_data()
    category = state_data.get('category')
    project_id = state_data.get('project_id')
    count = state_data.get('random_count')
    
    candidates = await generate_random_candidates(category, project_id, count)
    
    if not candidates:
        await callback.message.edit_text(
            "❌ Не найдено подходящих пользователей для добавления",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text='🔙 К проекту', callback_data=f"PROJECT:::{category}:::{project_id}")]
            ])
        )
        return
    
    await state.update_data(random_candidates=candidates)
    
    candidates_text = await format_candidates_list(candidates)
    try:
        await callback.message.edit_text(
            f"🎲 <b>Новый список пользователей для добавления</b> ({len(candidates)}):\n\n"
            f"{candidates_text}\n\n"
            f"Добавить этих пользователей в проект?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text='✅ Да, добавить', callback_data="CONFIRM_ADD_RANDOM"),
                    InlineKeyboardButton(text='🔄 Перегенерировать', callback_data="REGENERATE_RANDOM")
                ],
                [InlineKeyboardButton(text='❌ Нет, отмена', callback_data=f"PROJECT:::{category}:::{project_id}")]
            ]),
            parse_mode="HTML"
        )
    except:
        return

@router.callback_query(F.data == "CONFIRM_ADD_RANDOM")
async def confirm_add_random_members(callback: CallbackQuery, state: FSMContext, bot: Bot):
    state_data = await state.get_data()
    category = state_data.get('category')
    project_id = state_data.get('project_id')
    project_name = state_data.get('project_name')
    candidates = state_data.get('random_candidates', [])
    
    if not candidates:
        await callback.answer("❌ Список кандидатов пуст")
        return
    
    from services import add_member_to_project
    added_count = 0
    failed_count = 0
    
    for candidate in candidates:
        result = await add_member_to_project(
            candidate['user_id'], 
            category, 
            project_id
        )
        
        if result["status"]:
            added_count += 1
            try:
                await bot.send_message(
                    chat_id=candidate['user_id'],
                    text=f"🎉 Вас добавили в проект <b>{project_name}</b>!",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text='🔙 К проекту', callback_data=f"PROJECT:::{category}:::{project_id}")]
                    ]),
                    parse_mode="HTML"
                )
            except:
                pass
        else:
            failed_count += 1
    
    await state.clear()
    
    report_text = (
        f"✅ <b>Результат добавления участников</b>\n\n"
        f"📋 Проект: {project_name}\n"
        f"✅ Успешно добавлено: {added_count}\n"
        f"❌ Не удалось добавить: {failed_count}"
    )
    
    if added_count > 0:
        report_text += f"\n\n🎉 Новые участники уведомлены о добавлении!"
    
    await callback.message.edit_text(
        report_text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text='🔙 К проекту', callback_data=f"PROJECT:::{category}:::{project_id}")]
        ]),
        parse_mode="HTML"
    )