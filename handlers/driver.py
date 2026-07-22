# -*- coding: utf-8 -*-
"""
handlers/driver.py — haydovchi telefon raqami, e'lon yaratish
(matn -> rasm -> interval -> tasdiqlash), to'xtatish va obuna holati.
"""
import time
import logging
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.utils.exceptions import TelegramAPIError

from bot_instance import bot, dp
from config import ADMINS, DRIVER_CHANNELS
from storage import get_user, save_users, save_ads, ads_store
from states import DriverStates
from stickers import send_sticker_safe
from utils import normalize_phone, new_id, fmt_date, seconds_to_human
from keyboards import (
    main_menu_kb, driver_main_kb, phone_request_kb, REMOVE_KB,
    interval_inline_kb, ad_confirm_kb, driver_channel_ad_kb, cancel_inline_kb,
)

log = logging.getLogger(__name__)


# ==================== TELEFON RAQAMNI QABUL QILISH ====================
@dp.message_handler(content_types=["contact", "text"], state=DriverStates.waiting_phone)
async def driver_get_phone(message: types.Message, state: FSMContext):
    uid = str(message.from_user.id)

    raw = message.contact.phone_number if message.contact else message.text
    phone = normalize_phone(raw)
    if not phone:
        return await message.answer(
            "❌ Raqam noto‘g‘ri formatda. Iltimos qayta yuboring "
            "(masalan: 901234567 yoki +998901234567).",
            reply_markup=phone_request_kb(),
        )

    u = get_user(uid)
    u["phone"] = phone
    await save_users()
    await state.finish()

    await message.answer(f"✅ Raqamingiz saqlandi: <code>{phone}</code>", reply_markup=REMOVE_KB)

    if not u["subscription"].get("active"):
        from handlers.payment import show_tariffs
        await show_tariffs(message.chat.id)
    else:
        await message.answer("Haydovchi bo‘limi:", reply_markup=driver_main_kb())


# ==================== E'LON BERISH (oxirgi e'londan davom etish) ====================
def _driver_ready(u: dict, uid: str = None) -> bool:
    is_admin = uid is not None and int(uid) in ADMINS
    if u.get("driver_status") != "approved":
        return False
    if not u["subscription"].get("active"):
        return False
    if not is_admin and not u.get("phone"):
        return False
    return True


@dp.callback_query_handler(lambda c: c.data == "drv_post_ad", state="*")
async def driver_new_ad_continue(call: types.CallbackQuery, state: FSMContext):
    uid = str(call.from_user.id)
    u = get_user(uid)
    if not _driver_ready(u, uid):
        return await call.answer("❌ Bu funksiyadan foydalanish uchun avval ro‘yxatdan o‘ting.", show_alert=True)

    u["driver_paused"] = False
    await save_users()

    last_ad = u.get("last_ad") or {}
    if last_ad.get("text") and last_ad.get("photo"):
        await state.update_data(ad_text=last_ad["text"], ad_photo=last_ad["photo"])
        await state.set_state(DriverStates.waiting_ad_photo)  # interval callback shu state'ni kutadi
        await call.message.answer(
            "♻️ Oxirgi e’loningiz asosida davom etyapmiz (matn va rasm qayta so‘ralmaydi).\n\n"
            "⏱ E’lon necha daqiqada bir marta yuborilsin?",
            reply_markup=interval_inline_kb(),
        )
        return await call.answer()

    await state.update_data(ad_text=None, ad_photo=None)
    await state.set_state(DriverStates.waiting_ad_text)
    await call.message.answer("✍️ E’lon matnini yuboring:", reply_markup=cancel_inline_kb())
    await call.answer()


@dp.callback_query_handler(lambda c: c.data == "drv_new_ad", state="*")
async def driver_new_ad_fresh(call: types.CallbackQuery, state: FSMContext):
    uid = str(call.from_user.id)
    u = get_user(uid)
    if not _driver_ready(u, uid):
        return await call.answer("❌ Bu funksiyadan foydalanish uchun avval ro‘yxatdan o‘ting.", show_alert=True)

    u["driver_paused"] = False
    await save_users()

    await state.update_data(ad_text=None, ad_photo=None)
    await state.set_state(DriverStates.waiting_ad_text)
    await call.message.answer("✍️ Yangi e’lon matnini yuboring:", reply_markup=cancel_inline_kb())
    await call.answer()


@dp.message_handler(state=DriverStates.waiting_ad_text, content_types=["text"])
async def driver_get_text(message: types.Message, state: FSMContext):
    await state.update_data(ad_text=message.text)
    await state.set_state(DriverStates.waiting_ad_photo)
    await message.answer("📸 Mashina rasmini yuboring (majburiy):", reply_markup=cancel_inline_kb())


@dp.message_handler(state=DriverStates.waiting_ad_photo, content_types=["photo"])
async def driver_get_photo(message: types.Message, state: FSMContext):
    await state.update_data(ad_photo=message.photo[-1].file_id)
    data = await state.get_data()
    await message.answer(
        f"⏱ E’lon necha daqiqada bir marta yuborilsin?\n\n✍️ Matn: {data.get('ad_text', '')[:200]}",
        reply_markup=interval_inline_kb(),
    )


@dp.message_handler(state=DriverStates.waiting_ad_photo, content_types=["text"])
async def driver_get_photo_wrong_type(message: types.Message, state: FSMContext):
    await message.answer("📸 Iltimos, mashina RASMINI yuboring (matn emas).", reply_markup=cancel_inline_kb())


@dp.callback_query_handler(lambda c: c.data.startswith("ad_interval:"), state=DriverStates.waiting_ad_photo)
async def driver_pick_interval(call: types.CallbackQuery, state: FSMContext):
    minutes = int(call.data.split(":")[1])
    await state.update_data(ad_interval=minutes)
    data = await state.get_data()

    text_preview = (data.get("ad_text") or "")[:300]
    summary = (
        f"📋 <b>E’lon xulosasi</b>\n\n"
        f"✍️ Matn: {text_preview}\n"
        f"⏱ Interval: {minutes} daqiqa\n\n"
        f"Tasdiqlaysizmi? Tasdiqlasangiz e’lon <b>darhol</b> guruhga yuboriladi, "
        f"so‘ng har {minutes} daqiqada avtomatik qayta yuborilib turadi."
    )
    try:
        await call.message.edit_reply_markup()
    except Exception:
        pass
    await call.message.answer(summary, reply_markup=ad_confirm_kb())
    await call.answer()


@dp.callback_query_handler(lambda c: c.data == "ad_cancel", state="*")
async def driver_cancel_ad(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    try:
        await call.message.edit_reply_markup()
    except Exception:
        pass
    await call.message.answer("🗑 Bekor qilindi.", reply_markup=driver_main_kb())
    await call.answer()


@dp.callback_query_handler(lambda c: c.data == "ad_confirm", state="*")
async def driver_confirm_ad(call: types.CallbackQuery, state: FSMContext):
    uid = str(call.from_user.id)
    data = await state.get_data()
    text = data.get("ad_text")
    photo = data.get("ad_photo")
    interval = data.get("ad_interval", 5)

    if not text or not photo:
        await state.finish()
        return await call.answer("Xatolik: e’lon ma’lumotlari topilmadi. Qaytadan boshlang.", show_alert=True)

    u = get_user(uid)
    ad_id = new_id()
    ads_store.data["driver"][ad_id] = {
        "user": uid,
        "text": text,
        "photo": photo,
        "interval": interval,
        "start": time.time(),
        "active": True,
        "last_sent": 0,
        "reminded_12h": False,
    }
    u["last_ad"] = {"text": text, "photo": photo, "interval": interval}
    u["driver_paused"] = False
    await save_ads()
    await save_users()
    await state.finish()

    ok, err = await _broadcast_driver_ad(ad_id)

    try:
        await call.message.edit_reply_markup()
    except Exception:
        pass

    if ok:
        await call.message.answer(
            f"🚀 E’lon guruhga yuborildi va faol holatda! Har {interval} daqiqada avtomatik takrorlanadi.",
            reply_markup=driver_main_kb(),
        )
        await send_sticker_safe(int(uid), "ad_posted")
    else:
        await call.message.answer(
            "⚠️ E’lon guruhga yuborilmadi!\n\n"
            f"Sabab: <code>{err}</code>\n\n"
            "Iltimos adminga xabar bering — botning kanal/guruhda administrator "
            "ekanligini va kanal ID (config.py dagi DRIVER_CHANNELS) to‘g‘riligini tekshiring.",
            reply_markup=driver_main_kb(),
        )
    await call.answer()


async def _broadcast_driver_ad(ad_id: str):
    """
    E'lonni DRIVER_CHANNELS ro'yxatidagi barcha guruh/kanallarga yuboradi.
    MUHIM: xatolik sodir bo'lsa (masalan, bot guruhda admin emas) endi
    bu jimgina yutib yuborilmaydi — aniq xato matni qaytariladi, shunda
    muammoni darhol tushunib tuzatish mumkin.
    """
    ad = ads_store.data["driver"].get(ad_id)
    if not ad:
        return False, "E'lon topilmadi"
    user = get_user(ad["user"])
    kb = driver_channel_ad_kb(ad_id, ad["user"], user.get("username"))

    any_success = False
    last_error = None

    for ch in DRIVER_CHANNELS:
        try:
            await bot.send_photo(ch, ad["photo"], caption=ad["text"], reply_markup=kb)
            any_success = True
        except TelegramAPIError as e:
            last_error = str(e)
            log.error("Kanal %s ga yuborib bo'lmadi: %s", ch, e)
        except Exception as e:
            last_error = str(e)
            log.error("Kanal %s ga yuborishda kutilmagan xatolik: %s", ch, e)

    ad["last_sent"] = time.time()
    await save_ads()
    return any_success, last_error


# ==================== HAYDOVCHI PROFILI ====================
@dp.callback_query_handler(lambda c: c.data.startswith("profile_drv:"))
async def profile_driver(call: types.CallbackQuery):
    ad_id = call.data.split(":")[1]
    ad = ads_store.data["driver"].get(ad_id)
    if not ad:
        return await call.answer("❌ Bu e’lon topilmadi yoki eskirgan.", show_alert=True)

    driver = get_user(ad["user"])
    phone = driver.get("phone")

    from utils import display_name
    from keyboards import driver_profile_kb
    name = display_name(driver, ad["user"])

    text = (
        f"👤 <b>Haydovchi profili</b>\n\n"
        f"🚕 Ism: <b>{name}</b>\n"
        f"✅ Status: Tasdiqlangan haydovchi\n\n"
    )
    if phone:
        # Telegram bunday raqamlarni matn ichida o'zi aniqlab, bosiladigan
        # havolaga aylantiradi — ustiga bosilsa terish (dialer) ilovasi
        # o'sha raqam bilan ochiladi.
        text += f"📞 Telefon: {phone}\n<i>(raqamning ustiga bosib qo‘ng‘iroq qilishingiz mumkin)</i>"
    else:
        text += "📞 Telefon: —"

    try:
        await bot.send_message(call.from_user.id, text, reply_markup=driver_profile_kb(driver.get("username")))
        await call.answer("👤 Profil botga yuborildi — xabarlarni oching!", show_alert=True)
    except Exception:
        await call.answer(
            f"👤 {name}\n📞 {phone or '—'}",
            show_alert=True,
        )


# ==================== TO'XTATISH ====================
@dp.callback_query_handler(lambda c: c.data == "drv_pause", state="*")
async def pause_driver(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    uid = str(call.from_user.id)
    u = get_user(uid)
    u["driver_paused"] = True

    changed = False
    for ad in ads_store.data["driver"].values():
        if ad.get("user") == uid and ad.get("active", False):
            ad["active"] = False
            changed = True
    if changed:
        await save_ads()
    await save_users()

    try:
        await call.message.edit_reply_markup()
    except Exception:
        pass
    await call.message.answer(
        "⏸ E’loningiz muvaffaqiyatli to‘xtatildi.",
        reply_markup=main_menu_kb(is_admin=call.from_user.id in ADMINS),
    )
    await call.answer()


# ==================== MENING OBUNAM ====================
@dp.callback_query_handler(lambda c: c.data == "drv_sub", state="*")
async def my_subscription(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    uid = str(call.from_user.id)
    u = get_user(uid)
    sub = u.get("subscription", {})

    if not sub.get("active"):
        from handlers.payment import show_tariffs
        await call.answer()
        return await show_tariffs(call.message.chat.id)

    tariff = sub.get("tariff")
    end = sub.get("end")
    if end is None:
        expiry_text = "♾ Umrbod (muddatsiz)"
    else:
        remaining = end - time.time()
        expiry_text = f"{fmt_date(end)} ({seconds_to_human(remaining)} qoldi)" if remaining > 0 else "muddati tugagan"

    await call.message.answer(
        f"💳 <b>Sizning obunangiz</b>\n\n"
        f"📦 Tarif: {tariff or '—'}\n"
        f"📅 Tugash sanasi: {expiry_text}",
        reply_markup=driver_main_kb(),
    )
    await call.answer()