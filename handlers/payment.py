# -*- coding: utf-8 -*-
"""
handlers/payment.py — tarif tanlash va to'lov usullari:
  1) Admin orqali murojaat
  2) Click / Payme (agar sozlanmagan bo'lsa — vaqtincha mavjud emas)
  3) Chek orqali to'lov
"""
import time
from aiogram import types
from aiogram.dispatcher import FSMContext

from bot_instance import bot, dp
from config import (
    TARIFFS, ADMINS, ADMIN_PHONE, ADMIN_USERNAME,
    PAYMENT_CARD, CLICK_MERCHANT_ID, PAYME_MERCHANT_ID,
)
from storage import get_user, save_users, payments_store, save_payments
from states import DriverStates
from utils import new_id, display_name, fmt_money
from keyboards import (
    tariff_kb, payment_method_kb, contact_admin_kb,
    admin_payment_decision_kb, cancel_inline_kb,
)


async def show_tariffs(chat_id: int):
    await bot.send_message(
        chat_id,
        "💳 <b>Obuna tariflari</b>\n\n"
        "Botdan haydovchi sifatida to‘liq foydalanish uchun quyidagi "
        "tariflardan birini tanlang:",
        reply_markup=tariff_kb(),
    )


@dp.callback_query_handler(lambda c: c.data.startswith("tariff:"))
async def choose_tariff(call: types.CallbackQuery):
    tariff_key = call.data.split(":")[1]
    tariff = TARIFFS.get(tariff_key)
    if not tariff:
        return await call.answer("Tarif topilmadi.", show_alert=True)

    try:
        await call.message.edit_text(
            f"📦 Tanlangan tarif: <b>{tariff['label']}</b>\n"
            f"💰 Narxi: <b>{fmt_money(tariff['price'])}</b>\n\n"
            f"To‘lov usulini tanlang:",
            reply_markup=payment_method_kb(tariff_key),
        )
    except Exception:
        await call.message.answer(
            f"📦 Tanlangan tarif: <b>{tariff['label']}</b>\n"
            f"💰 Narxi: <b>{fmt_money(tariff['price'])}</b>\n\n"
            f"To‘lov usulini tanlang:",
            reply_markup=payment_method_kb(tariff_key),
        )
    await call.answer()


@dp.callback_query_handler(lambda c: c.data == "pm:back")
async def payment_method_back(call: types.CallbackQuery):
    try:
        await call.message.edit_text("💳 <b>Obuna tariflari</b>\n\nTarifni tanlang:", reply_markup=tariff_kb())
    except Exception:
        pass
    await call.answer()


async def _create_payment_record(uid: str, tariff_key: str, method: str, receipt_photo: str = None) -> str:
    tariff = TARIFFS[tariff_key]
    payment_id = new_id()
    payments_store.data["payments"][payment_id] = {
        "uid": uid,
        "tariff": tariff_key,
        "price": tariff["price"],
        "method": method,
        "status": "pending",
        "created": time.time(),
        "receipt_photo": receipt_photo,
    }
    await save_payments()
    return payment_id


async def _notify_admins_payment(payment_id: str):
    p = payments_store.data["payments"][payment_id]
    tariff = TARIFFS[p["tariff"]]
    u = get_user(p["uid"])
    name = display_name(u, p["uid"])
    method_label = {"admin": "👨‍💼 Admin orqali murojaat", "receipt": "🧾 Chek orqali"}.get(p["method"], p["method"])

    caption = (
        f"💳 <b>Yangi to‘lov so‘rovi</b>\n\n"
        f"👤 Foydalanuvchi: <b>{name}</b>\n\n"
        f"🆔 ID: <code>{p['uid']}</code>\n\n"
        f"📞 Telefon: {u.get('phone') or '—'}\n\n"
        f"📦 Tarif: <b>{tariff['label']}</b>\n\n"
        f"💰 Narxi: <b>{fmt_money(p['price'])}</b>\n\n"
        f"🔧 Usul: {method_label}"
    )
    kb = admin_payment_decision_kb(payment_id)
    notifs = []
    for admin in ADMINS:
        try:
            if p.get("receipt_photo"):
                msg = await bot.send_photo(admin, p["receipt_photo"], caption=caption, reply_markup=kb)
            else:
                msg = await bot.send_message(admin, caption, reply_markup=kb)
            notifs.append({"admin": admin, "msg_id": msg.message_id})
        except Exception:
            pass
    payments_store.data["payment_notifs"][payment_id] = notifs
    await save_payments()


# ---------- 1) ADMIN ORQALI MUROJAAT ----------
@dp.callback_query_handler(lambda c: c.data.startswith("pm:admin:"))
async def payment_via_admin(call: types.CallbackQuery):
    tariff_key = call.data.split(":")[2]
    uid = str(call.from_user.id)

    payment_id = await _create_payment_record(uid, tariff_key, "admin")
    await _notify_admins_payment(payment_id)

    try:
        await call.message.edit_text(
            "📨 So‘rovingiz adminga yuborildi. Iltimos, admin javobini kuting.\n\n"
            f"Zarur bo‘lsa, adminga bevosita murojaat qilishingiz ham mumkin:\n"
            f"👤 {ADMIN_USERNAME}\n📞 {ADMIN_PHONE}",
            reply_markup=contact_admin_kb(),
        )
    except Exception:
        pass
    await call.answer("So‘rov yuborildi ✅")


# ---------- 2) CLICK / PAYME ----------
@dp.callback_query_handler(lambda c: c.data.startswith("pm:click:"))
async def payment_via_click(call: types.CallbackQuery):
    if not CLICK_MERCHANT_ID and not PAYME_MERCHANT_ID:
        return await call.answer(
            "⏳ Bu to‘lov usuli hozircha vaqtinchalik mavjud emas.",
            show_alert=True,
        )
    # Merchant ID sozlangan bo'lsa — shu yerga real to'lov havolasi yaratish logikasi qo'shiladi.
    await call.answer("To‘lov havolasi tayyorlanmoqda…", show_alert=True)


# ---------- 3) CHEK ORQALI ----------
@dp.callback_query_handler(lambda c: c.data.startswith("pm:receipt:"))
async def payment_via_receipt(call: types.CallbackQuery, state: FSMContext):
    tariff_key = call.data.split(":")[2]
    await state.update_data(receipt_tariff=tariff_key)
    await state.set_state(DriverStates.waiting_receipt_photo)

    card = PAYMENT_CARD
    text = (
        "🧾 <b>Chek orqali to‘lov</b>\n\n"
        f"🏦 Karta raqami: <code>{card['number']}</code>\n"
        f"👍 {card['owner']}\n"
        f"📞 Ulangan raqam: <code>{card['phone']}</code>\n\n"
        "Yuqoridagi kartaga to‘lovni amalga oshirib, "
        "to‘lov chekining rasmini shu yerga yuboring. 📸"
    )
    try:
        await call.message.edit_text(text, reply_markup=cancel_inline_kb())
    except Exception:
        await call.message.answer(text, reply_markup=cancel_inline_kb())
    await call.answer()


@dp.message_handler(state=DriverStates.waiting_receipt_photo, content_types=["photo"])
async def receipt_photo_received(message: types.Message, state: FSMContext):
    uid = str(message.from_user.id)
    data = await state.get_data()
    tariff_key = data.get("receipt_tariff")
    await state.finish()

    if tariff_key not in TARIFFS:
        return await message.answer("❌ Xatolik yuz berdi. Iltimos, qaytadan tarif tanlang.", reply_markup=tariff_kb())

    photo_id = message.photo[-1].file_id
    payment_id = await _create_payment_record(uid, tariff_key, "receipt", receipt_photo=photo_id)
    await _notify_admins_payment(payment_id)

    await message.answer(
        "✅ Chek qabul qilindi!\n📨 So‘rov adminga yuborildi. Iltimos, admin javobini kuting.",
    )


@dp.message_handler(state=DriverStates.waiting_receipt_photo, content_types=["text"])
async def receipt_photo_wrong_type(message: types.Message, state: FSMContext):
    await message.answer("📸 Iltimos, to‘lov CHEKINING RASMINI yuboring.", reply_markup=cancel_inline_kb())
