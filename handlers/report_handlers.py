import os
import re
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from config import PATH_TO_USERS_FILE, PATH_TO_PROJECTS_FILE, MODERATORS_CHAT_ID, REWARD_COEFFICIENT_FOR_THE_PHOTO
from states import ActiveState
from utils import read_json_file, check_authorization
from services import check_project_registration, get_user_data, get_project_data, add_points_to_member
from keyboards import get_report_menu_kb, get_back_to_report_menu_kb, get_back_to_main_menu_kb

router = Router()

@router.callback_query(F.data == "menu_report")
async def report_menu(callback: CallbackQuery, state: FSMContext):
    if not await check_authorization(callback.from_user.id):
        return
    
    await state.clear()
    await callback.message.edit_text(
        "👤 <b>Выберите действие:</b>",
        reply_markup=await get_report_menu_kb(),
        parse_mode="HTML"
    )

@router.callback_query(F.data == "send_report_progress")
async def report_progress(callback: CallbackQuery, state: FSMContext):
    user_id = str(callback.from_user.id)
    access = await check_project_registration(user_id)
    
    if not access["status"]:
        await callback.message.edit_text(
            "Для отправки отчета укажите все необходимые данные(Имя, фамилию, ID первых, Номер телефона)",
            reply_markup=await get_back_to_report_menu_kb()
        )        
        return 
    
    users_data = read_json_file(PATH_TO_USERS_FILE)
    user_data = users_data.get(user_id, {})
    projects_data = read_json_file(PATH_TO_PROJECTS_FILE)
    
    if not user_data:
        return
      
    if user_data.get("active_projects", []):
        kb = []
        for project in user_data["active_projects"]:
            category, project_id = project.split(":::")
            project_name = projects_data.get(category, {}).get(project_id, {}).get("name", "Не найден")
            button = InlineKeyboardButton(
                text=project_name,
                callback_data=f"REPORT:::{category}:::{project_id}"
            )
            kb.append([button])  
              
        kb.append([InlineKeyboardButton(text='Без проекта', callback_data="REPORT:::noproject")])
        kb.append([InlineKeyboardButton(text='🔙 Назад', callback_data="menu_report")])

        await callback.message.edit_text(
            "Выберите проект по которому хотите отправить отчёт",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=kb)
        )
    else:
        await state.set_state(ActiveState.waiting_for_photos)
        await callback.message.edit_text(
            "📷 Отправьте одно или несколько <b>фото</b> для отчета(можно с подписью)",
            reply_markup=await get_back_to_report_menu_kb(),
            parse_mode="HTML"
        )

@router.callback_query(F.data.startswith("REPORT:::"))
async def report_progress(callback: CallbackQuery, state: FSMContext):
    if callback.data == "REPORT:::noproject":
        await state.update_data(reporting_project=False)
    else:
        data_parts = callback.data.split(":::")
        category = data_parts[1]
        project_id = data_parts[2]
        projects_data = read_json_file(PATH_TO_PROJECTS_FILE)
        data_project = projects_data.get(category, {}).get(project_id)
        if not data_project:
            return
        await state.update_data(
            reporting_project=data_project.get("name", False),
            reporting_project_prize=data_project.get('prize', False)
        )

    await state.set_state(ActiveState.waiting_for_photos)
    if callback.message.photo:
        await callback.message.delete()
        await callback.message.answer(
            "📷 Отправьте одно или несколько <b>фото</b> для отчета(можно с подписью)",
            reply_markup=await get_back_to_report_menu_kb(),
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            "📷 Отправьте одно или несколько <b>фото</b> для отчета(можно с подписью)",
            reply_markup=await get_back_to_report_menu_kb(),
            parse_mode="HTML"
        )

@router.message(ActiveState.waiting_for_photos, F.photo)
async def handle_photos(message: Message, state: FSMContext, bot: Bot):
    user = message.from_user
    data = await state.get_data()
    project_name = data.get("reporting_project", False)
    project_prize = data.get("reporting_project_prize", False)

    users_data = read_json_file(PATH_TO_USERS_FILE)
    user_data = users_data.get(str(user.id), {})
    
    if not user_data:
        return
    
    if not project_name:
        project_name = "Без проекта"
    
    full_name = "имя не указано" if user_data.get('name') == "Не указано" else user_data.get("name", "") + ("" if user_data.get("surname") == "Не указано" else " " + user_data.get("surname", ""))

    caption = (
        f"📷 Отчет от @{user.username} или {full_name}\n"
        f"Проект: {project_name}\n"
        f"Телефон: {user_data.get('phone', '')}\n|{user.id}|"
    )
    
    if message.caption:
        caption += f"\n\nСообщение от пользователя: {message.caption}"
    
    if project_prize:
        project_prize = str(round(float(project_prize) * REWARD_COEFFICIENT_FOR_THE_PHOTO))
        from utils import format_points
        prize_points = await format_points(int(project_prize))
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=f'Наградить: {prize_points}', callback_data=f"ADD_SCORE:::{str(user.id)}:::{project_prize}")]
            ]
        )
        await bot.send_photo(
            chat_id=MODERATORS_CHAT_ID,
            photo=message.photo[-1].file_id,
            caption=caption[:1024],
            reply_markup=kb
        )
    else:
        await bot.send_photo(
            chat_id=MODERATORS_CHAT_ID,
            photo=message.photo[-1].file_id,
            caption=caption[:1024]
        )
    
    await state.clear()
    await message.answer(
        "✔️ <b>Отчет отправлен!</b>",
        reply_markup=await get_back_to_report_menu_kb(),
        parse_mode="HTML"
    )

@router.message(ActiveState.waiting_for_photos)
async def handle_not_photos(message: Message):
    await message.answer(
        "❌ Нужно отправить хотя-бы одно <b>фото</b>!",
        reply_markup=await get_back_to_report_menu_kb(),
        parse_mode="HTML"
    )

@router.callback_query(F.data.startswith("ADD_SCORE:::"))
async def reward_member(callback: CallbackQuery):
    data_parts = callback.data.split(":::")
    user_id = data_parts[1]
    points = data_parts[2]
    await callback.message.edit_reply_markup(reply_markup=None)
    await add_points_to_member(user_id=user_id, points=points)

@router.callback_query(F.data == "send_message_to_moderators")
async def report_progress(callback: CallbackQuery, state: FSMContext):
    user_id = str(callback.from_user.id)
    access = await check_project_registration(user_id)
    
    if not access["status"]:
        await callback.message.edit_text(
            "Для отправки отчета укажите все необходимые данные(Имя, фамилию, ID первых, Номер телефона)",
            reply_markup=await get_back_to_report_menu_kb()
        )
        return

    await state.set_state(ActiveState.waiting_for_message_to_mods)
    await callback.message.edit_text(
        "Отправьте сообщение для модераторов.",
        reply_markup=await get_back_to_report_menu_kb(),
        parse_mode="HTML"
    )

@router.message(F.chat.type == "private", Command(commands=["обратная_связь","report"]))
async def report(message: Message, state: FSMContext):
    user_id = str(message.from_user.id)
    if not await check_authorization(user_id):
        from utils import send_not_authorized
        await send_not_authorized(message, state)
        return
    
    access = await check_project_registration(user_id)
    if not access["status"]:
        await message.answer(
            "Для отправки отчета укажите все необходимые данные(Имя, фамилию, ID первых, Номер телефона)",
            reply_markup=await get_back_to_report_menu_kb()
        )
        return

    await state.set_state(ActiveState.waiting_for_message_to_mods)
    await message.answer(
        "Отправьте сообщение для модераторов.",
        reply_markup=await get_back_to_report_menu_kb(),
        parse_mode="HTML"
    )

@router.message(ActiveState.waiting_for_message_to_mods, F.text)
async def handle_photos(message: Message, state: FSMContext, bot: Bot):
    user = message.from_user
    users_data = read_json_file(PATH_TO_USERS_FILE)
    user_data = users_data.get(str(user.id), {})

    if not user_data:
        return
    
    full_name = "имя не указано" if user_data.get('name') == "Не указано" else user_data.get("name", "") + ("" if user_data.get("surname") == "Не указано" else " " + user_data.get("surname", ""))
    
    caption = (
        f"<b>Сообщение от @{user.username} или {full_name}</b>\n"
        f"<b>Телефон: {user_data.get('phone', '')}</b>\n|{user.id}|\n\n"
        f"<b>Сообщение:</b> {message.text}"
    )
    
    await bot.send_message(
        chat_id=MODERATORS_CHAT_ID,
        text=caption,
        parse_mode="HTML"
    )

    await state.clear()
    await message.answer(
        "✔️ <b>Сообщение модератору отправлено!</b>",
        reply_markup=await get_back_to_report_menu_kb(),
        parse_mode="HTML"
    )

@router.message(F.chat.type == "supergroup", F.reply_to_message)
async def report_answer(message: Message, bot: Bot):
    reply_text = message.text
    if not reply_text or not reply_text.strip().startswith("Ответ."):
        return

    reply_text = reply_text[6:]
    replyed_message = message.reply_to_message.text or message.reply_to_message.caption
    if not replyed_message:
        return

    pattern = r'Телефон:[^|]*\|\s*(\d{9,10})\s*\|'
    match = re.search(pattern, replyed_message)
    if not match:
        await message.answer("❌ Id пользователя для ответа не найдено, попробуйете ответить вручную.")
        return

    ID_user = match.group(1)

    pattern = r'@([a-zA-Z0-9_](?:[a-zA-Z0-9_]{4,31}|[a-zA-Z0-9_]{0,30}[a-zA-Z0-9]))'
    match = re.search(pattern, replyed_message)
    replyed_message_user = f"@{match.group(1)}" if match else "Не найден"

    user_message = "".join(replyed_message.split("Сообщение:")[1:]).strip()
    if len(user_message) > 40:
        user_message = f"{user_message[:40]}..."

    text = f"<b>Ответ администрации на сообщение: \"{user_message}\"</b>\nОтвет: {reply_text}"
    
    if "📷 Отчет" in replyed_message and "Проект:" in replyed_message:
        pattern = r"Проект:\s*(.*?)\s*Телефон:"
        match = re.search(pattern, replyed_message, re.IGNORECASE | re.DOTALL)
        project_name = match.group(1).strip() if match else "Без проекта"
        
        if project_name == "Без проекта":
            text = f"<b>Ответ администрации на отчёт.</b>\nОтвет: {reply_text}"
        else:
            text = f"<b>Ответ администрации на отчёт о проекте: {project_name}</b>\nОтвет: {reply_text}"

    await bot.send_message(
        chat_id=ID_user,
        text=text,
        reply_markup=await get_back_to_main_menu_kb(),
        parse_mode="HTML"
    )
    await message.answer(f"✔️ Ответ пользователю: {replyed_message_user} - Отправлен!")