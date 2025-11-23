from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import NON_DISPLAY_CHARACTER

async def get_main_menu_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='1️⃣ Активности', callback_data="menu_projects")],
            [InlineKeyboardButton(text='👤 Мои данные', callback_data="menu_my_data")],
            [InlineKeyboardButton(text='🏆 Топ Первых', callback_data="menu_leaderboard")],
            [InlineKeyboardButton(text='💬 Обратная связь', callback_data="menu_report")]
        ]
    )

async def get_back_to_main_menu_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='🔙 В главное меню.', callback_data="back_to_main")]
        ]
    )

async def get_my_data_menu_kb(user_id: str = None):
    from utils import read_json_file
    from config import PATH_TO_USERS_FILE

    
    kb = []
    if user_id:
        users_data = read_json_file(PATH_TO_USERS_FILE)
        user_data = users_data.get(str(user_id), {})
        phone = user_data.get("phone", "Не указано")
        
        if phone.startswith(NON_DISPLAY_CHARACTER):
            kb.append([InlineKeyboardButton(text='✅ Подтвердить телефон', callback_data="confirm_phone_main")])
    kb.extend([
        [InlineKeyboardButton(text='✏️ Редактировать', callback_data="menu_my_data_edit")],
        [InlineKeyboardButton(text='🔙 Назад', callback_data="back_to_main")]
    ])

    return InlineKeyboardMarkup(inline_keyboard=kb)

async def get_projects_menu_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='🎓 Образование и знания', callback_data="menu_project_category_education")],
            [InlineKeyboardButton(text='🔬 Наука и технологии', callback_data="menu_project_category_science")],
            [InlineKeyboardButton(text='🧑‍🏫 Труд, профессия и своё дело', callback_data="menu_project_category_profession")],
            [InlineKeyboardButton(text='🎺 Культура и искусство', callback_data="menu_project_category_culture")],
            [InlineKeyboardButton(text='🌍 Волонтёрство и добровольчество', callback_data="menu_project_category_volunteering")],
            [InlineKeyboardButton(text='🇷🇺 Патриотизм и историческая память', callback_data="menu_project_category_patriotism")],
            [InlineKeyboardButton(text='🏃 Спорт и здоровый образ жизни', callback_data="menu_project_category_sport")],
            [InlineKeyboardButton(text='🧩 Другое', callback_data="menu_project_category_other")],
            [InlineKeyboardButton(text='🔙 Назад', callback_data="back_to_main")]
        ]
    )

async def generate_projects_category_menu_kb(projects_preview, projects_id, category, is_editing_mode=False):
    kb = []
    if not is_editing_mode:
        for preview, project_id in zip(projects_preview, projects_id):
            if preview.startswith(NON_DISPLAY_CHARACTER):
                pass
            else:
                button = InlineKeyboardButton(
                    text=preview,
                    callback_data=f"PROJECT:::{category}:::{project_id}"
                )
                kb.append([button])
        kb.append([InlineKeyboardButton(text='🔙 Назад', callback_data="menu_projects")])
    else:
        for preview, project_id in zip(projects_preview, projects_id):
            button = InlineKeyboardButton(
                text=preview,
                callback_data=f"PROJECT_FOR_EDITING:::{category}:::{project_id}"
            )
            kb.append([button])
        kb.append([InlineKeyboardButton(text='🔙 Назад', callback_data="menu_projects_editing")])

    return InlineKeyboardMarkup(inline_keyboard=kb)

async def get_report_menu_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='📷 Отправить фото о проекте', callback_data="send_report_progress")],
            [InlineKeyboardButton(text='✏️ Написать модераторам', callback_data="send_message_to_moderators")],
            [InlineKeyboardButton(text='🔙 Назад', callback_data="back_to_main")]
        ]
    )

async def get_back_to_report_menu_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='🔙 Назад', callback_data="menu_report")]
        ]
    )

async def get_adding_projects_md_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='🎓 Образование и знания', callback_data="adding_project_category_education")],
            [InlineKeyboardButton(text='🔬 Наука и технологии', callback_data="adding_project_category_science")],
            [InlineKeyboardButton(text='🧑‍🏫 Труд, профессия и своё дело', callback_data="adding_project_category_profession")],
            [InlineKeyboardButton(text='🎺 Культура и искусство', callback_data="adding_project_category_culture")],
            [InlineKeyboardButton(text='🌍 Волонтёрство и добровольчество', callback_data="adding_project_category_volunteering")],
            [InlineKeyboardButton(text='🇷🇺 Патриотизм и историческая память', callback_data="adding_project_category_patriotism")],
            [InlineKeyboardButton(text='🏃 Спорт и здоровый образ жизни', callback_data="adding_project_category_sport")],
            [InlineKeyboardButton(text='🧩 Другое', callback_data="adding_project_category_other")],
            [InlineKeyboardButton(text='Отмена', callback_data="back_to_main")]
        ]
    )

async def get_back_to_project_editing_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='В меню редактирования', callback_data="back_to_project_editing")]
        ]
    )

async def get_approval_request_kb(user_id: str, category: str, project_id: str):
    """Клавиатура для запроса одобрения участия в проекте"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text='✅ Добавить', 
                    callback_data=f"APPROVE_USER_PROJECT:::{user_id}:::{category}:::{project_id}"
                ),
                InlineKeyboardButton(
                    text='❌ Отклонить', 
                    callback_data=f"DECLINE_USER_PROJECT:::{user_id}:::{category}:::{project_id}"
                )
            ]
        ]
    )

async def get_consent_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text='✅ Принять условия', 
                    callback_data=f"CONSENT:::ACCEPTED"
                ),
                InlineKeyboardButton(
                    text='❌ Отклонить', 
                    callback_data=f"CONSENT:::REJECTED"
                )
            ]
        ]
    )