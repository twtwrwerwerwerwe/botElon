# -*- coding: utf-8 -*-
"""
handlers/fallback.py — "qo'riqchi" handlerlar.

MUHIM: bu fayl handlerlar ro'yxatida ENG OXIRIDA ro'yxatdan o'tishi kerak
(main.py da eng oxirida import qilinadi). Agar biror sabab bilan (masalan,
kutilmagan matn, eskirgan tugma bosilishi va h.k.) boshqa hech qanday
handler mos kelmasa, bot foydalanuvchiga "jim" javob bermaydi — balki
tushunarli xabar bilan asosiy menyuga yo'naltiradi.
"""
from aiogram import types
from aiogram.dispatcher import FSMContext

from bot_instance import dp
from config import ADMINS
from storage import get_user
from keyboards import main_menu_kb


@dp.message_handler(content_types=["sticker"], state="*")
async def capture_sticker_id(message: types.Message, state: FSMContext):
    """Admin botga stiker yuborsa — uning file_id'sini qaytarib beradi.
    Shu ID'ni config.py dagi STICKERS lug'atiga qo'yish orqali bot
    o'sha stikerni muhim daqiqalarda avtomatik yuboradi."""
    if message.chat.type != "private":
        return
    if message.from_user.id not in ADMINS:
        return await fallback_message(message, state)
    await message.answer(
        "🎟 Bu stikerning file_id'si:\n\n"
        f"<code>{message.sticker.file_id}</code>\n\n"
        "Shu qatorni nusxalab, <code>config.py</code> ichidagi "
        "<code>STICKERS</code> lug‘atiga qo‘ying.",
    )


@dp.message_handler(content_types=types.ContentTypes.ANY, state="*")
async def fallback_message(message: types.Message, state: FSMContext):
    # MUHIM: bot faqat shaxsiy chatda "tushunmadim" deb javob berishi kerak.
    # Guruh/kanallarda (e'lonlar tushadigan joylarda) botga tegishli bo'lmagan
    # xabarlarga hech qachon javob YOZMASLIGI kerak — shu yerda aynan shu
    # cheklov qo'yiladi.
    if message.chat.type != "private":
        return
    uid = str(message.from_user.id)
    get_user(uid)
    await state.finish()
    await message.answer(
        "🤔 Buni tushunmadim. Quyidagi menyudan kerakli bo‘limni tanlang:",
        reply_markup=main_menu_kb(is_admin=message.from_user.id in ADMINS),
    )


@dp.callback_query_handler(lambda c: True, state="*")
async def fallback_callback(call: types.CallbackQuery):
    await call.answer(
        "⏳ Bu zakazni hamkasbingiz qabul qildi. Iltimos ishlashda to'xtamang, yangi zakazlarni kuting ....",
        show_alert=True,
    )