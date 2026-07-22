# -*- coding: utf-8 -*-
"""
handlers/driver_admin.py — haydovchilik arizalarini admin tomonidan
tasdiqlash/rad etish va tasdiqlangan haydovchilar ro'yxati.
"""
from aiogram import types
from aiogram.dispatcher import FSMContext

from bot_instance import bot, dp
from config import ADMINS
from storage import get_user, save_users, users_store
from states import DriverStates
from utils import display_name
from stickers import send_sticker_safe
from keyboards import (
    driver_apply_kb, main_menu_kb, driver_main_kb,
    admin_driver_decision_kb, admin_driver_manage_kb, phone_request_kb,
)


async def notify_admins_new_application(uid: str, full_name: str, username: str):
    kb = admin_driver_decision_kb(uid)
    username_display = f"@{username}" if username else "—"
    notifs = []
    for admin in ADMINS:
        try:
            msg = await bot.send_message(
                admin,
                f"🚘 <b>Yangi haydovchilik arizasi</b>\n\n"
                f"👤 Ism: <b>{full_name}</b>\n"
                f"🔗 Username: {username_display}\n"
                f"🆔 ID: <code>{uid}</code>",
                reply_markup=kb,
            )
            notifs.append({"admin": admin, "msg_id": msg.message_id})
        except Exception:
            pass
    users_store.data["admin_notifs"][uid] = notifs
    await save_users()


async def render_driver_section(chat_id: int, uid: int, state: FSMContext):
    uid_s = str(uid)
    u = get_user(uid_s)

    if uid in ADMINS:
        if u["driver_status"] != "approved":
            u["driver_status"] = "approved"
            u["driver_paused"] = False
            u["subscription"]["active"] = True
            await save_users()
        return await bot.send_message(chat_id, "Haydovchi bo‘limi (admin):", reply_markup=driver_main_kb())

    status = u["driver_status"]
    if status in ("none", "rejected"):
        text = "Siz hali haydovchi emassiz. Ariza yuboring." if status == "none" \
            else "❌ Admin arizangizni rad etgan edi. Xohlasangiz qayta ariza yuborishingiz mumkin."
        return await bot.send_message(chat_id, text, reply_markup=driver_apply_kb())

    if status == "pending":
        return await bot.send_message(chat_id, "⏳ Arizangiz admin tomonidan ko‘rib chiqilmoqda…", reply_markup=main_menu_kb())

    # status == approved
    if not u.get("phone"):
        await state.set_state(DriverStates.waiting_phone)
        return await bot.send_message(
            chat_id,
            "📱 Iltimos, telefon raqamingizni yuboring.\n"
            "Tugma orqali yoki qo‘lda kiritishingiz mumkin (masalan: 901234567).",
            reply_markup=phone_request_kb(),
        )

    if not u["subscription"].get("active"):
        from handlers.payment import show_tariffs
        return await show_tariffs(chat_id)

    await bot.send_message(chat_id, "Haydovchi bo‘limi:", reply_markup=driver_main_kb())


@dp.callback_query_handler(lambda c: c.data == "menu:driver", state="*")
async def driver_section_cb(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    try:
        await call.message.edit_reply_markup()
    except Exception:
        pass
    await render_driver_section(call.message.chat.id, call.from_user.id, state)
    await call.answer()


@dp.callback_query_handler(lambda c: c.data == "drv_apply")
async def driver_apply(call: types.CallbackQuery):
    uid = str(call.from_user.id)
    u = get_user(uid)

    if u["driver_status"] == "pending":
        return await call.answer("Siz allaqachon ariza yuborgansiz. Iltimos kuting.", show_alert=True)
    if u["driver_status"] == "approved":
        return await call.answer("Siz allaqachon tasdiqlangan haydovchisiz.", show_alert=True)

    u["driver_status"] = "pending"
    u["driver_paused"] = True
    u["full_name"] = call.from_user.full_name or u.get("full_name", "")
    u["username"] = call.from_user.username or u.get("username", "")
    await save_users()

    await notify_admins_new_application(uid, u["full_name"], u["username"])
    try:
        await call.message.edit_text("✅ Arizangiz adminga yuborildi! ⏳ Iltimos, javobini kuting.")
    except Exception:
        await call.message.answer("✅ Arizangiz adminga yuborildi! ⏳ Iltimos, javobini kuting.")
    await call.answer()


@dp.callback_query_handler(lambda c: c.data and c.data.split(":")[0] in
                            ("drv_ok", "drv_no", "drv_view", "drv_remove", "drv_keep"))
async def admin_driver_action(call: types.CallbackQuery):
    if call.from_user.id not in ADMINS:
        return await call.answer("Faqat adminlar uchun.", show_alert=True)

    action, _, uid = call.data.partition(":")
    if not uid:
        return await call.answer("Xatolik.", show_alert=True)

    u = get_user(uid)

    if action == "drv_ok":
        u["driver_status"] = "approved"
        u["driver_paused"] = True
        await save_users()
        await _update_admin_notifs(uid, "✅ Amal bajarildi (tasdiqlandi)")

        try:
            state = dp.current_state(chat=int(uid), user=int(uid))
            await state.set_state(DriverStates.waiting_phone)
            await bot.send_message(
                int(uid),
                "🎉 Admin sizni haydovchi sifatida tasdiqladi!\n\n"
                "📱 Endi telefon raqamingizni yuboring — tugma orqali yoki qo‘lda "
                "(masalan: 901234567).",
                reply_markup=phone_request_kb(),
            )
            await send_sticker_safe(int(uid), "driver_approved")
        except Exception:
            pass
        await call.answer("Tasdiqlandi ✅")

    elif action == "drv_no":
        u["driver_status"] = "rejected"
        u["driver_paused"] = True
        await save_users()
        await _update_admin_notifs(uid, "❌ Amal bajarildi (rad etildi)")
        try:
            await bot.send_message(
                int(uid),
                "❌ Admin arizangizni rad etdi. Xohlasangiz qayta ariza yuborishingiz mumkin.",
                reply_markup=main_menu_kb(),
            )
        except Exception:
            pass
        await call.answer("Rad etildi ❌")

    elif action == "drv_view":
        name = display_name(u, uid)
        sub = u.get("subscription", {})
        sub_text = "faol ✅" if sub.get("active") else "faol emas ❌"
        txt = (
            f"🚘 <b>Haydovchi ma'lumotlari</b>\n\n"
            f"👤 Ism: <b>{name}</b>\n"
            f"🆔 ID: <code>{uid}</code>\n"
            f"📞 Telefon: {u.get('phone') or '—'}\n"
            f"📋 Status: {u.get('driver_status', '—')}\n"
            f"💳 Obuna: {sub_text}"
        )
        await bot.send_message(call.from_user.id, txt, reply_markup=admin_driver_manage_kb(uid))
        await call.answer()

    elif action == "drv_remove":
        u["driver_status"] = "rejected"
        u["driver_paused"] = True
        u["subscription"]["active"] = False

        from storage import ads_store, save_ads
        ads_stopped = False
        for ad in ads_store.data["driver"].values():
            if ad.get("user") == uid and ad.get("active", False):
                ad["active"] = False
                ads_stopped = True
        if ads_stopped:
            await save_ads()

        await save_users()
        await call.answer("Foydalanuvchi chiqarib tashlandi, e’lonlari to‘xtatildi.")
        try:
            await bot.send_message(
                int(uid),
                "❌ Siz haydovchilar ro‘yxatidan chiqarib tashlandingiz. "
                "Faol e’loningiz ham to‘xtatildi va botdan haydovchi sifatida "
                "foydalana olmaysiz.",
                reply_markup=main_menu_kb(),
            )
        except Exception:
            pass

    elif action == "drv_keep":
        u["driver_status"] = "approved"
        await save_users()
        await call.answer("Foydalanuvchi haydovchi sifatida qoldirildi.")
        try:
            await bot.send_message(int(uid), "✅ Siz haydovchi sifatida qoldirildingiz.", reply_markup=driver_main_kb())
        except Exception:
            pass


async def _update_admin_notifs(uid: str, new_text: str):
    notifs = users_store.data.get("admin_notifs", {}).get(uid, [])
    for item in notifs:
        try:
            await bot.edit_message_text(new_text, item["admin"], item["msg_id"])
        except Exception:
            pass


@dp.callback_query_handler(lambda c: c.data == "menu:admin_drivers", state="*")
async def admin_drivers_list(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.id not in ADMINS:
        return await call.answer("Faqat adminlar uchun.", show_alert=True)
    await state.finish()

    kb = types.InlineKeyboardMarkup()
    found = False
    for uid, u in users_store.data["users"].items():
        if u.get("driver_status") == "approved":
            kb.add(types.InlineKeyboardButton(display_name(u, uid), callback_data=f"drv_view:{uid}"))
            found = True
    kb.add(types.InlineKeyboardButton("🏠 Bosh menyu", callback_data="menu:home"))

    if not found:
        try:
            await call.message.edit_text("Hozircha tasdiqlangan haydovchilar yo‘q.", reply_markup=kb)
        except Exception:
            await call.message.answer("Hozircha tasdiqlangan haydovchilar yo‘q.", reply_markup=kb)
        return await call.answer()

    try:
        await call.message.edit_text("📋 Tasdiqlangan haydovchilar ro‘yxati:", reply_markup=kb)
    except Exception:
        await call.message.answer("📋 Tasdiqlangan haydovchilar ro‘yxati:", reply_markup=kb)
    await call.answer()
