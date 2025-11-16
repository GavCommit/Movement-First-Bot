import difflib

def find_top_matches(input_name, name_list, max_matches=10, cutoff=0.3):
    """Находит топ-N наиболее похожих имен"""
    matches = difflib.get_close_matches(input_name, name_list, cutoff=cutoff)
    return matches[:max_matches]

# Пример использования
names = ['Максим', 'михаела', 'Лада', 'Данила', 'Владислава', 'Евгений', 'Анатолий', 'Михаил', 'Енокентий']
user_input = "Ана"

top = find_top_matches(user_input, names, max_matches=10, cutoff=0)

for i, match in enumerate(top, 1):
    print(f"{i}. {match}")





#@router.message(F.chat.type == "private", Command(commands=["уведомление","оповещение","notification"]))
#async def notification(message: Message, state: FSMContext):
#    user_id = str(message.from_user.id)
#    if not await check_authorization(user_id):
#        await send_not_authorized(message, state)
#        return
#        
#    if not await is_moderator(user_id):
#        await send_not_moderator(message)
#        return
#
#    await state.set_state(ActiveState.waiting_for_notification)
#    await state.update_data(notification_type = "all_users")
#    await message.answer(
#        "Введите сообщение для всех:",
#        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Отмена', callback_data="back_to_main")]])
#    )
#
#@router.message(ActiveState.waiting_for_notification, F.text)
#async def handle_photos(message: Message, state: FSMContext):
#    notification_message = message.text
#    await state.update_data(notification_message=notification_message)
#    await message.answer(
#        f"Ваше сообщение:\n{notification_message}\n\nСообщение будет отправлено всем, продолжить?",
#        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
#            [InlineKeyboardButton(text='Продолжить', callback_data="notification_send_continue")],
#            [InlineKeyboardButton(text='Отмена', callback_data="back_to_main")]
#        ]),
#        parse_mode="HTML"
#    )
#
#@router.callback_query(F.data == "notification_send_continue")
#async def send_notification(callback: CallbackQuery, state: FSMContext, bot: Bot):
#    state_data = await state.get_data()
#    notification = state_data.get('notification_message')
#    await state.clear()
#    
#    data = read_json_file(PATH_TO_USERS_FILE)
#    sent_to_users = 0
#    for user_id in data.keys():
#
#        if data[user_id].get("ban", 0) == 1:
#            continue
#            
#        try:
#            await bot.send_message(
#                chat_id=user_id,
#                text=notification,
#                reply_markup=await get_back_to_main_menu_kb(),
#                parse_mode="HTML"
#            )
#            sent_to_users += 1
#        except:
#            continue
#
#    await callback.message.answer(
#        f"✔️ Сообщение отправлено {sent_to_users} пользователям.",
#        reply_markup=await get_back_to_main_menu_kb()
#    )