# -*- coding: utf-8 -*-
"""handlers/start.py — /start buyrug'i va umumiy 'Bosh menyu' navigatsiyasi."""
from aiogram import types
from aiogram.dispatcher import FSMContext

from bot_instance import dp
from config import ADMINS
from storage import get_user, touch_user_profile, save_users
from keyboards import main_menu_kb, REMOVE_KB


@dp.message_handler(commands=["start"], state="*")
async def start_cmd(message: types.Message, state: FSMContext):
    # MUHIM: bot faqat shaxsiy chatda /start ga javob berishi kerak.
    # Bot admin qilib qo'yilgan guruh/kanallarda kimdir /start yozsa,
    # bot u yerda HECH QANDAY javob bermasligi kerak.
    if message.chat.type != "private":
        return

    await state.finish()
    uid = str(message.from_user.id)
    touch_user_profile(uid, message.from_user.full_name or "", message.from_user.username or "")
    await save_users()

    is_admin = message.from_user.id in ADMINS
    args = message.get_args()

    if args == "zakaz":
        await message.answer(
            "🚕 Marhamat! Agar yo‘lovchi bo‘lsangiz, "
            "quyidagi <b>🧍 Yo‘lovchi</b> bo‘limidan buyurtma berishingiz mumkin.",
            reply_markup=main_menu_kb(is_admin=is_admin),
        )
        return

    await message.answer(
        "<b>Assalomu alaykum! 👋</b>\n\nSiz kimsiz? Tanlang:",
        reply_markup=main_menu_kb(is_admin=is_admin),
    )


async def do_back(chat_id: int, uid: int, state: FSMContext):
    """Har qanday holatdan asosiy menyuga qaytarish (boshqa modullardan ham chaqiriladi)."""
    await state.finish()
    get_user(str(uid))
    is_admin = uid in ADMINS
    from bot_instance import bot
    await bot.send_message(chat_id, "🏠 Asosiy menyu:", reply_markup=main_menu_kb(is_admin=is_admin))


@dp.callback_query_handler(lambda c: c.data == "menu:home", state="*")
async def go_home(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    is_admin = call.from_user.id in ADMINS
    try:
        await call.message.edit_text("🏠 Asosiy menyu:", reply_markup=main_menu_kb(is_admin=is_admin))
    except Exception:
        await call.message.answer("🏠 Asosiy menyu:", reply_markup=main_menu_kb(is_admin=is_admin))
    await call.answer()


@dp.callback_query_handler(lambda c: c.data == "cancel_flow", state="*")
async def cancel_flow(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    is_admin = call.from_user.id in ADMINS
    try:
        await call.message.edit_reply_markup()
    except Exception:
        pass
    await call.message.answer("❌ Bekor qilindi.", reply_markup=main_menu_kb(is_admin=is_admin))
    await call.answer()


# "❌ Bekor qilish" reply-tugmasi (telefon/lokatsiya so'ralayotgan bosqichlarda)
@dp.message_handler(lambda m: m.text == "❌ Bekor qilish", state="*")
async def cancel_reply_button(message: types.Message, state: FSMContext):
    if message.chat.type != "private":
        return
    await state.finish()
    is_admin = message.from_user.id in ADMINS
    await message.answer("❌ Bekor qilindi.", reply_markup=REMOVE_KB)
    await message.answer("🏠 Asosiy menyu:", reply_markup=main_menu_kb(is_admin=is_admin))