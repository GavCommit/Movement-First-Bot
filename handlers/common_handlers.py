import os
import json
import re
import datetime
import time
from typing import Any, Dict, Optional
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.fsm.context import FSMContext

from states import ActiveState
from keyboards import get_main_menu_kb, get_projects_menu_kb
from utils import check_authorization  

router = Router()

@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.set_state(ActiveState.main_menu)
    await callback.message.edit_text(
        "Главное меню\nВыберите Раздел:",
        reply_markup=await get_main_menu_kb()
    )
    await callback.answer()  

@router.callback_query(F.data == "menu_projects_editing")
async def project_categories_menu(callback: CallbackQuery, state: FSMContext):
    if not await check_authorization(callback.from_user.id):
        return
    
    await callback.message.edit_text(
        "👤 <b>Выберите категорию:</b>",
        reply_markup=await get_projects_menu_kb(),
        parse_mode="HTML"
    )
    await callback.answer() 