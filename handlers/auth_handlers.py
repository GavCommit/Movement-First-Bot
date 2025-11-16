import os
import json
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from config import API_TELEGRAM, SCHOOL_AUTH_PSWD, PATH_TO_USERS_FILE
from states import ActiveState
from utils import read_json_file, write_json_file, check_authorization, send_not_authorized
from keyboards import get_main_menu_kb
from services import get_user_data, update_user_data

router = Router()

@router.message(F.chat.type == "private", Command(commands=['запуск','начало','от_винта','start']))
async def start(message: Message, state: FSMContext):
    user_id = str(message.from_user.id)
    
    # ✅ Проверяем не забанен ли пользователь
    from services import is_user_banned
    if await is_user_banned(user_id):
        await message.answer("❌ Вы были заблокированы администрацией бота ❌")
        return
    
    if await check_authorization(user_id):
        await state.clear()
        await main_menu(message, state)
    else:
        await send_not_authorized(message, state)

@router.message(ActiveState.auth_wait_pswd)
async def authorization(message: Message, state: FSMContext):
    # ✅ Проверяем не забанен ли пользователь
    user_id = str(message.from_user.id)
    from services import is_user_banned
    if await is_user_banned(user_id):
        await message.answer("❌ Вы были заблокированы администрацией бота ❌")
        return
    
    if message.text == str(SCHOOL_AUTH_PSWD):
        user_profile = {
            "username": message.from_user.username or "Не указано",
            "name": "Не указано", 
            "surname": "Не указано",
            "IDfirst": "Не указано",
            "score": 0,
            "completed_projects": 0,
            "active_projects": [],
            "phone": "Не указано"
        }
        
        data = read_json_file(PATH_TO_USERS_FILE)
        data[str(message.from_user.id)] = user_profile
        write_json_file(PATH_TO_USERS_FILE, data)

        await state.clear()
        await state.set_state(ActiveState.new_user_registration)
        await message.answer(
                "✅ Код школы указан успешно ✅\nВведите ваше имя:"
            )
        return
    else:
        await message.answer("Неверный пароль школы. Попробуйте снова.")
        await state.set_state(ActiveState.auth_wait_pswd)

@router.message(ActiveState.new_user_registration)
async def new_user_registration(message: Message, state: FSMContext):
    user_id = str(message.from_user.id)
    
    from services import is_user_banned
    if await is_user_banned(user_id):
        await message.answer("❌ Вы были заблокированы администрацией бота ❌")
        return
    
    user_data = await get_user_data(user_id)

    new_value = message.text.capitalize().strip()

    if user_data.get("name") == "Не указано":
        success = await update_user_data(user_id, "name", new_value)
        if success:
            await message.answer(
                "✅ Имя сохранено успешно ✅\nВведите вашу фамилию:"
            )

    elif user_data.get("surname") == "Не указано":
        success = await update_user_data(user_id, "surname", new_value)
        if success:
            await message.answer(
                "✅ Фамилия сохранена успешно ✅\nРегистрация окончена!"
            )
            await message.answer(
            "Привет, Первый!\n"
            "Этот бот создан для того, чтобы помочь тебе стать самым активным в школе 🤗\n"
            "Бот поможет найти интересующие тебя мероприятия и сообщит о массовых событиях 👍\n"
            "Также здесь есть система рейтинга: чем в большем количестве проектов ты участвуешь и чем они сложнее, тем больше у тебя баллов ⭐️\n"
            "В конце учебного года три самых активных получат мерч Движения Первых. И ты можешь быть среди них! Но чтобы ты был в списках, нужно вести корректные данные во вкладке \"Мои данные\" 📝\n"
            "И не забывай про фото 📷! Помни, что они должны быть горизонтальными, и ты должен быть хотя бы на одном из них. Отправить их можно во вкладке \"Обратная связь\". Также здесь можно задавать вопросы.\n\n"
            "Помни, что всё в твоих руках! Удачи🍀"
            )
            await main_menu(message, state)
    else:
        return


async def main_menu(message: Message, state: FSMContext):
    from keyboards import get_main_menu_kb
    await state.set_state(ActiveState.main_menu)
    await message.answer(
        "Главное меню\nВыберите Раздел:",
        reply_markup=await get_main_menu_kb()
    )