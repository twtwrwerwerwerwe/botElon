# -*- coding: utf-8 -*-
"""handlers/payment_admin.py — admin to'lovlarni tasdiqlash/rad etish."""
import time
from aiogram import types
from aiogram.dispatcher import FSMContext

from bot_instance import bot, dp
from config import ADMINS, TARIFFS, ADMIN_PHONE, ADMIN_USERNAME
from storage import get_user, save_users, payments_store, save_payments
from stickers import send_sticker_safe
from utils import fmt_date, display_name, fmt_money
from keyboards import driver_main_kb, contact_admin_kb, admin_payment_decision_kb


async def _update_payment_notifs(payment_id: str, new_text: str):
    notifs = payments_store.data.get("payment_notifs", {}).get(payment_id, [])
    for item in notifs:
        try:
            await bot.edit_message_caption(item["admin"], item["msg_id"], caption=new_text)
        except Exception:
            try:
                await bot.edit_message_text(new_text, item["admin"], item["msg_id"])
            except Exception:
                pass


@dp.callback_query_handler(lambda c: c.data.startswith("pay_ok:") or c.data.startswith("pay_no:"))
async def admin_payment_action(call: types.CallbackQuery):
    if call.from_user.id not in ADMINS:
        return await call.answer("Faqat adminlar uchun.", show_alert=True)

    action, _, payment_id = call.data.partition(":")
    p = payments_store.data["payments"].get(payment_id)
    if not p:
        return await call.answer("To‘lov topilmadi.", show_alert=True)
    if p["status"] != "pending":
        return await call.answer("Bu so‘rov allaqachon ko‘rib chiqilgan.", show_alert=True)

    uid = p["uid"]
    tariff = TARIFFS[p["tariff"]]

    if action == "pay_ok":
        p["status"] = "approved"
        u = get_user(uid)
        start = time.time()
        end = None if tariff["days"] is None else start + tariff["days"] * 86400
        u["subscription"] = {
            "tariff": tariff["label"],
            "start": start,
            "end": end,
            "active": True,
            "reminded_3d": False,
            "reminded_expired": False,
        }
        u["driver_status"] = "approved"
        await save_users()
        await save_payments()
        await _update_payment_notifs(payment_id, "✅ To‘lov tasdiqlandi")

        expiry_text = "♾ umrbod" if end is None else f"{fmt_date(end)} sanagacha"
        try:
            await bot.send_message(
                int(uid),
                f"🎉 To‘lovingiz tasdiqlandi!\n\n"
                f"📦 Tarif: <b>{tariff['label']}</b>\n"
                f"📅 Amal qilish muddati: {expiry_text}\n\n"
                f"Endi haydovchi bo‘limidan to‘liq foydalanishingiz mumkin! 🚕",
                reply_markup=driver_main_kb(),
            )
            await send_sticker_safe(int(uid), "payment_approved")
        except Exception:
            pass
        await call.answer("Tasdiqlandi ✅")

    else:
        p["status"] = "rejected"
        await save_payments()
        await _update_payment_notifs(payment_id, "❌ To‘lov rad etildi")
        try:
            await bot.send_message(
                int(uid),
                "❌ To‘lovingiz rad etildi.\n\n"
                "Iltimos, ma’lumotlarni tekshirib qayta urinib ko‘ring yoki quyidagi "
                f"admin bilan bog‘laning:\n👤 {ADMIN_USERNAME}\n📞 {ADMIN_PHONE}",
                reply_markup=contact_admin_kb(),
            )
        except Exception:
            pass
        await call.answer("Rad etildi ❌")


@dp.callback_query_handler(lambda c: c.data == "menu:admin_payments", state="*")
async def admin_payments_list(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMINS:
        return await call.answer("Faqat adminlar uchun.", show_alert=True)
    await state.finish()

    pending = [
        (pid, p) for pid, p in payments_store.data["payments"].items()
        if p["status"] == "pending"
    ]
    if not pending:
        try:
            await call.message.edit_text("✅ Hozircha kutilayotgan to‘lovlar yo‘q.")
        except Exception:
            await call.message.answer("✅ Hozircha kutilayotgan to‘lovlar yo‘q.")
        return await call.answer()

    await call.answer(f"{len(pending)} ta kutilayotgan to‘lov topildi")
    for pid, p in pending:
        u = get_user(p["uid"])
        tariff = TARIFFS[p["tariff"]]
        caption = (
            f"💳 <b>To‘lov so‘rovi</b>\n\n"
            f"👤 {display_name(u, p['uid'])}\n"
            f"🆔 <code>{p['uid']}</code>\n"
            f"📦 {tariff['label']} — {fmt_money(p['price'])}"
        )
        kb = admin_payment_decision_kb(pid)
        if p.get("receipt_photo"):
            await bot.send_photo(call.from_user.id, p["receipt_photo"], caption=caption, reply_markup=kb)
        else:
            await bot.send_message(call.from_user.id, caption, reply_markup=kb)
