import json
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from config import PATH_TO_USERS_FILE, PATH_TO_PROJECTS_FILE, MEMBERS_IN_MEMBERSLIST, USER_IN_LEADERBOARD
from states import ActiveState
from utils import read_json_file, check_authorization, is_moderator, phone_number_validating, send_not_moderator, get_leaderboard
from services import get_user_data, update_user_data, get_leaderboard_data
from keyboards import get_main_menu_kb, get_my_data_menu_kb, get_back_to_main_menu_kb

router = Router()

@router.callback_query(F.data == "menu_my_data")
async def my_data_menu(callback: CallbackQuery, state: FSMContext):
    if not await check_authorization(callback.from_user.id):
        return
    
    from utils import check_user_consent
    if not await check_user_consent(callback.from_user.id):
        from utils import show_consent_agreement
        await show_consent_agreement(message=message, state=state)
        return

    await state.clear()
    data = read_json_file(PATH_TO_USERS_FILE)
    user_id = callback.from_user.id
    user_data = data[str(user_id)]
    
    await state.set_state(ActiveState.my_data_menu)
    
    # Форматирование активных проектов
    if not user_data['active_projects']:
        active_projects = "Нет"
    else:
        active_projects = "\n"
        data_pr = read_json_file(PATH_TO_PROJECTS_FILE)
        for index, project in enumerate(user_data["active_projects"], 1):
            category, project_id = project.split(":::")
            project_name = f'{index}. {data_pr.get(category, {}).get(project_id, {}).get("name", "Не найден")}\n'
            active_projects += project_name

    await callback.message.edit_text(
        f"👤 <b>Ваши данные:</b>\n\n"
        f"📝 Имя пользователя: @{user_data['username']}\n"
        f"😎 Имя: {user_data['name']}\n"
        f"😄 Фамилия: {user_data['surname']}\n"
        f"📝ID Первых: {user_data['IDfirst']}\n"
        f"📞 Телефон: {user_data['phone']}\n"
        f"⭐ Баллы: {user_data['score']}\n"
        f"🔄 Активные проекты: {active_projects}\n"
        f"✅ Завершенные проекты: {user_data['completed_projects']}\n",
        reply_markup=await get_my_data_menu_kb(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "menu_my_data_edit")
async def menu_my_data_edit(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ActiveState.my_data_edit)
    data = read_json_file(PATH_TO_USERS_FILE)
    user_id = str(callback.from_user.id)
    user_data = data[user_id]

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"😎 Имя: {user_data['name']}", callback_data=f"user_edit_parm:::name:::{user_id}")],
            [InlineKeyboardButton(text=f"😄 Фамилия: {user_data['surname']}", callback_data=f"user_edit_parm:::surname:::{user_id}")],
            [InlineKeyboardButton(text=f"⭐ID Первых: {user_data['IDfirst']}", callback_data=f"user_edit_parm:::IDfirst:::{user_id}")],
            [InlineKeyboardButton(text=f"📞Телефон: {user_data['phone']}", callback_data=f"user_edit_parm:::phone:::{user_id}")],
            [InlineKeyboardButton(text='🔙 Назад', callback_data="menu_my_data")]
        ]
    )
    await callback.message.edit_text(
        "Выберите данные для редактирования:",
        reply_markup=markup
    )
    callback.answer()

@router.callback_query(F.data.startswith("user_edit_parm:::"))
async def my_data_edit_parms(callback: CallbackQuery, state: FSMContext):
    _, parm, user_id = callback.data.split(":::")
    
    if parm.startswith("moderator_"):
        from services import update_user_data
        await update_user_data(user_id, "moderator", int(parm[-1]))
        await editing_user_parms(message=callback.message, user_id=user_id)
        return

    parms_translate = {
        "name": "имя пользователя",
        "surname": "фамилию пользователя", 
        "IDfirst": "ID с сайта движения первых пользователя",
        "phone": "номер телефона пользователя",
        "score": "количество баллов пользователя",
        "username": "username пользователя",
        "completed_projects": "количество завершённых проектов пользователя"
    }
    
    if str(callback.from_user.id) == user_id:
        markup = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text='🔙 Вернуться в меню', callback_data="menu_my_data")]]
        )
    else:
        markup = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text='🔙 Вернуться в меню', callback_data=f"editing_user:::{user_id}")]]
        )

    await callback.message.edit_text(
        f"Введите {parms_translate[parm]}:",
        reply_markup=markup
    )
   
    await state.set_state(ActiveState.editing_parm_user_data)
    await state.update_data(editing_parm=parm, user_id=user_id)
    callback.answer()

@router.message(ActiveState.editing_parm_user_data)
async def my_data_parm_editing(message: Message, state: FSMContext):
    data = await state.get_data()
    parm = data.get("editing_parm")
    user_id = data.get("user_id")
    new_value = message.text

    if str(message.from_user.id) == user_id:
        markup = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text='🔙 Вернуться в меню', callback_data="menu_my_data")]]
        )
    else:
        markup = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text='🔙 Вернуться в меню', callback_data=f"editing_user:::{user_id}")]]
        )

    if new_value:
        if parm == "phone":
            valid_number = await phone_number_validating(new_value)
            if valid_number:
                new_value = valid_number
            else:
                await message.answer("❌ Некорректный номер телефона.", reply_markup=markup)
                return
  
        if parm in ["name", "surname"]:
            new_value = new_value.capitalize().strip()

        if parm == "IDfirst":
            value_only_digits = ''.join(filter(lambda x: x.isdigit(), new_value))
            if len(value_only_digits) == len(new_value.strip()) == 8:
                new_value = value_only_digits
            else:
                await message.answer("❌ Некорректный ID первых.", reply_markup=markup)
                return

        if parm == "username":
            new_value = new_value.replace("@", "")
        
        if parm == "score":
            if not new_value.isdigit():
                await message.answer("❌ Количеством баллов могут быть только целые числа", reply_markup=markup)
                return
            new_value = int(new_value)

        if parm == "completed_projects":
            if not new_value.isdigit():
                await message.answer("❌ Количеством завершённых проектов могут быть только целые числа", reply_markup=markup)
                return
            new_value = int(new_value)

        from services import update_user_data
        success = await update_user_data(user_id, parm, new_value)
        
        if success:
            await state.clear()
            await message.answer("✔️ Изменения сохранены успешно!", reply_markup=markup)
        else:
            await message.answer("❌ Не получилось изменить данные, попробуйте позже.", reply_markup=markup)

@router.callback_query(F.data == "menu_leaderboard")
async def leaderboard_menu(callback: CallbackQuery, state: FSMContext):
    user_id =  str(callback.from_user.id)
    leaderboard_data, user_rank = await get_leaderboard(user_id= user_id, top_n= USER_IN_LEADERBOARD) 
    
    if user_rank:
        your_place = f"Ваше место в списке - {user_rank}\n\n"
    else:
        your_place =""
    leaderboard = '\n'.join(leaderboard_data)
    text =  (
        "🏆 <b>Таблица лидеров по баллам ⭐️</b>\n\n"
        f"{your_place}"
        f"{leaderboard}"
    )
    await callback.message.edit_text(
        text,
        reply_markup = await get_back_to_main_menu_kb(),
        parse_mode = "HTML"
    )

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

@router.callback_query(F.data.startswith("editing_user:::"))
async def my_data_edit_parms(callback: CallbackQuery, state: FSMContext):
    _, user_id = callback.data.split(":::")
    await state.clear()
    await editing_user_parms(message=callback.message, user_id=user_id)

async def editing_user_parms(message, user_id: str, update_message: bool = None):
    user_data = read_json_file(PATH_TO_USERS_FILE).get(str(user_id), False)
    if not user_data:
        await message.answer("❌ Пользователь с таким ID не найден❌", reply_markup=await get_back_to_main_menu_kb())
        return

    is_moder = bool(user_data.get("moderator", 0))
    moder_btn = [InlineKeyboardButton(text="Сделать участником", callback_data=f"user_edit_parm:::moderator_0:::{user_id}")] if is_moder else [InlineKeyboardButton(text="Сделать модератором", callback_data=f"user_edit_parm:::moderator_1:::{user_id}")]

    markup = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"📝 Имя пользователя: @{user_data['username']}", callback_data=f"user_edit_parm:::username:::{user_id}")],
            [InlineKeyboardButton(text=f"😎 Имя: {user_data['name']}", callback_data=f"user_edit_parm:::name:::{user_id}")],
            [InlineKeyboardButton(text=f"😄 Фамилия: {user_data['surname']}", callback_data=f"user_edit_parm:::surname:::{user_id}")],
            [InlineKeyboardButton(text=f"⭐ ID Первых: {user_data['IDfirst']}", callback_data=f"user_edit_parm:::IDfirst:::{user_id}")],
            [InlineKeyboardButton(text=f"📞 Телефон: {user_data['phone']}", callback_data=f"user_edit_parm:::phone:::{user_id}")],
            [InlineKeyboardButton(text=f"⭐️ Баллы: {user_data['score']}", callback_data=f"user_edit_parm:::score:::{user_id}")],
            [InlineKeyboardButton(text="❌ Удалить из проекта", callback_data=f"REMOVE_FROM_PROJECT:::{user_id}")],
            [InlineKeyboardButton(text=f"✅ Завершенные проекты: {user_data['completed_projects']}", callback_data=f"user_edit_parm:::completed_projects:::{user_id}")],
            moder_btn,
            [InlineKeyboardButton(text='🔙 Назад', callback_data="back_to_main")]
        ]
    )

    # Форматирование активных проектов
    if not user_data['active_projects']:
        active_projects = "Нет"
    else:
        active_projects = "\n"
        data_pr = read_json_file(PATH_TO_PROJECTS_FILE)
        for index, project in enumerate(user_data["active_projects"], 1):
            category, project_id = project.split(":::")
            project_name = f'{index}. {data_pr.get(category, {}).get(project_id, {}).get("name", "Не найден")}\n'
            active_projects += project_name

    text = (
        f"👤 <b>Данные пользователя:</b>\n\n"
        f"📝 Имя пользователя: @{user_data['username']}\n"
        f"😎 Имя: {user_data['name']}\n"
        f"😄 Фамилия: {user_data['surname']}\n"
        f"📝ID Первых: {user_data['IDfirst']}\n"
        f"📞 Телефон: {user_data['phone']}\n"
        f"⭐ Баллы: {user_data['score']}\n"
        f"🔄 Активные проекты: {active_projects}\n"
        f"✅ Завершенные проекты: {user_data['completed_projects']}\n"
        "\nВыберите данные для редактирования:"
    )

    if update_message:
        await message.answer(text, reply_markup=markup, parse_mode="HTML")
    else:
        try:
            await message.edit_text(text, reply_markup=markup, parse_mode="HTML")
        except:
            await message.answer(text, reply_markup=markup, parse_mode="HTML")