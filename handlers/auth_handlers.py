import os
import json
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from config import API_TELEGRAM, SCHOOL_AUTH_PSWD, PATH_TO_USERS_FILE, NON_DISPLAY_CHARACTER
from states import ActiveState
from utils import read_json_file, write_json_file
from keyboards import get_main_menu_kb
from services import get_user_data, update_user_data, save_user_consent

router = Router()

@router.message(F.chat.type == "private", Command(commands=['запуск','начало','от_винта','start']))
async def start(message: Message, state: FSMContext):
    user_id = str(message.from_user.id)
    
    from services import is_user_banned
    if await is_user_banned(user_id):
        await message.answer("❌ Вы были заблокированы администрацией бота ❌")
        return
    from utils import check_authorization
    if not await check_authorization(user_id):
        from utils import send_not_authorized
        await send_not_authorized(message, state)
        return   

    from utils import check_user_consent
    if not await check_user_consent(user_id):
        from utils import show_consent_agreement
        await show_consent_agreement(message=message, state=state)
        return
    
    await state.clear()
    await main_menu(message, state)


@router.message(ActiveState.auth_wait_pswd)
async def authorization(message: Message, state: FSMContext):
    user_id = str(message.from_user.id)
    from services import is_user_banned
    if await is_user_banned(user_id):
        await message.answer("❌ Вы были заблокированы администрацией бота ❌")
        return
    
    if message.text == str(SCHOOL_AUTH_PSWD):
        user_profile = {     #Создание нового ПУСТОГО пользователя 
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
        await message.answer(
                "✅ Код школы указан успешно ✅"
            )

        from utils import show_consent_agreement
        await show_consent_agreement(message=message, state=state)           
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
                "✅ Имя сохранено успешно ✅\nВведите Вашу фамилию:"
            )

    elif user_data.get("surname") == "Не указано":
        success = await update_user_data(user_id, "surname", new_value)
        if success:
            await message.answer(
                "✅ Фамилия сохранена успешно ✅\nВведите ваш номер телефона:"
            )
    elif user_data.get("phone") == "Не указано":
        from utils import phone_number_validating
        valid_number = await phone_number_validating(new_value)
        if not valid_number:
            await message.answer("❌ Некорректный номер телефона.")
            await state.set_state(ActiveState.new_user_registration)
            return  
        else:
            success = await update_user_data(user_id, "phone", NON_DISPLAY_CHARACTER+valid_number)
            if success:
                await message.answer(
                    "✅ Телефон сохранен успешно ✅\nВведите Ваше ID <a href='https://id.pervye.ru/account/board'>cайта движения </a>:",
                    parse_mode="HTML"
                )
    elif user_data.get("IDfirst") == "Не указано":
        value_only_digits = ''.join(filter(lambda x: x.isdigit(), new_value))
        if len(value_only_digits) == len(new_value.strip()) == 8:
            success = await update_user_data(user_id, "IDfirst", value_only_digits)
            if success:
                await message.answer(
                    "✅ ID сохранен успешно ✅\nНе забудь подтвердить свой номер телефона в меню \'Мои данные\'\nРегистрация окончена!"
                )
            from config import GREETING_TEXT
            await message.answer(GREETING_TEXT)
            await main_menu(message, state)
            return
        else:
            await message.answer("❌ Некорректный ID первых. Он должен быть длинной 8.")
            return            
    else:
        return

async def main_menu(message: Message, state: FSMContext):
    from keyboards import get_main_menu_kb
    await state.set_state(ActiveState.main_menu)
    await message.answer(
        "Главное меню\nВыберите Раздел:",
        reply_markup=await get_main_menu_kb()
    )

@router.callback_query(F.data.startswith("CONSENT"))
async def consent_button_handler(callback: CallbackQuery, state: FSMContext):
    """Обработчик кнопок согласия пользователей"""
    action = callback.data.split(":::")[1]
    user_id = str(callback.from_user.id)

    if action == "ACCEPTED":
        #принята
        success = await save_user_consent(user_id)
        if success:
            from services import check_new_user
            if await check_new_user(user_id): # Новый пользователь

                await callback.message.edit_text(
                "✔️ Условия приняты",
                reply_markup = None
                )
                await state.set_state(ActiveState.new_user_registration)
                await callback.message.answer("Введите Ваше имя:")
                await callback.answer() 
            else:
                await callback.message.edit_text(
                "✔️ Условия приняты",
                reply_markup = None
                )
                await main_menu(message=callback.message, state=state)
                      
    else:
        from services import remove_user

        await remove_user(user_id)
        await callback.message.edit_text(
                "❌ Условия не приняты.\n\nРегистрация прервана. Введите код школы для повторной регистрации:",
                reply_markup = None
            )
        await state.set_state(ActiveState.auth_wait_pswd)
        await callback.answer()