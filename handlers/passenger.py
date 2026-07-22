# -*- coding: utf-8 -*-
"""
handlers/passenger.py — yo'lovchi bo'limi (to'liq yangilangan):
  telefon -> yo'nalish -> matn -> (ixtiyoriy) lokatsiya -> guruhga yuborish
  -> haydovchi qabul qilishi -> yo'lovchiga bildirishnoma.
"""
import time
from urllib.parse import quote

from aiogram import types
from aiogram.dispatcher import FSMContext

from bot_instance import bot, dp
from config import ADMINS, PASSENGER_CHANNELS, PASSENGER_ROUTES
from storage import get_user, save_users, ads_store, save_ads, next_ad_number
from states import PassengerStates
from stickers import send_sticker_safe
from utils import normalize_phone, new_id, display_name
from keyboards import (
    main_menu_kb, passenger_entry_kb, phone_request_kb, REMOVE_KB,
    route_kb, location_choice_kb, passenger_channel_kb, passenger_channel_taken_kb,
    passenger_ad_full_kb, map_choice_kb, open_map_link_kb, driver_profile_kb,
    cancel_inline_kb,
)


# ==================== KIRISH ====================
@dp.callback_query_handler(lambda c: c.data == "menu:passenger", state="*")
async def passenger_section(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    get_user(str(call.from_user.id))
    try:
        await call.message.edit_text(
            "🧍 <b>Yo‘lovchi bo‘limi</b>\n\nHaydovchi chaqirish uchun quyidagi tugmani bosing:",
            reply_markup=passenger_entry_kb(),
        )
    except Exception:
        await call.message.answer(
            "🧍 <b>Yo‘lovchi bo‘limi</b>\n\nHaydovchi chaqirish uchun quyidagi tugmani bosing:",
            reply_markup=passenger_entry_kb(),
        )
    await call.answer()


@dp.callback_query_handler(lambda c: c.data == "pass_order", state="*")
async def passenger_order_start(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    uid = str(call.from_user.id)
    u = get_user(uid)

    if u.get("phone"):
        await state.update_data(passenger_phone=u["phone"])
        try:
            await call.message.edit_text("📍 Yo‘nalishni tanlang:", reply_markup=route_kb())
        except Exception:
            await call.message.answer("📍 Yo‘nalishni tanlang:", reply_markup=route_kb())
        return await call.answer()

    await state.set_state(PassengerStates.waiting_phone)
    await call.message.answer(
        "📱 Iltimos, telefon raqamingizni yuboring.\n"
        "Tugma orqali yoki qo‘lda kiritishingiz mumkin (masalan: 901234567).",
        reply_markup=phone_request_kb(),
    )
    await call.answer()


@dp.message_handler(content_types=["contact", "text"], state=PassengerStates.waiting_phone)
async def passenger_get_phone(message: types.Message, state: FSMContext):
    raw = message.contact.phone_number if message.contact else message.text
    phone = normalize_phone(raw)
    if not phone:
        return await message.answer(
            "❌ Raqam noto‘g‘ri formatda. Qaytadan yuboring (masalan: 901234567).",
            reply_markup=phone_request_kb(),
        )

    uid = str(message.from_user.id)
    u = get_user(uid)
    u["phone"] = phone
    await save_users()

    await state.finish()
    await message.answer(f"✅ Raqamingiz saqlandi: <code>{phone}</code>", reply_markup=REMOVE_KB)
    await message.answer("📍 Yo‘nalishni tanlang:", reply_markup=route_kb())


# ==================== YO'NALISH ====================
@dp.callback_query_handler(lambda c: c.data == "route:custom", state="*")
async def passenger_custom_route(call: types.CallbackQuery, state: FSMContext):
    await state.set_state(PassengerStates.waiting_route_custom)
    try:
        await call.message.edit_text(
            "✍️ Yo‘nalishni o‘zingiz yozing (masalan: Rishton → Toshkent):",
            reply_markup=cancel_inline_kb(),
        )
    except Exception:
        await call.message.answer(
            "✍️ Yo‘nalishni o‘zingiz yozing (masalan: Rishton → Toshkent):",
            reply_markup=cancel_inline_kb(),
        )
    await call.answer()


@dp.message_handler(state=PassengerStates.waiting_route_custom, content_types=["text"])
async def passenger_route_custom_got(message: types.Message, state: FSMContext):
    await state.update_data(passenger_route=message.text.strip())
    await state.set_state(PassengerStates.waiting_order_text)
    await _ask_order_text(message.chat.id)


@dp.callback_query_handler(lambda c: c.data.startswith("route:idx:"), state="*")
async def passenger_route_pick(call: types.CallbackQuery, state: FSMContext):
    idx = int(call.data.split(":")[2])
    if idx < 0 or idx >= len(PASSENGER_ROUTES):
        return await call.answer("❌ Yo‘nalish topilmadi.", show_alert=True)
    route = PASSENGER_ROUTES[idx]
    await state.update_data(passenger_route=route)
    await state.set_state(PassengerStates.waiting_order_text)
    try:
        await call.message.edit_reply_markup()
    except Exception:
        pass
    await _ask_order_text(call.message.chat.id)
    await call.answer()


async def _ask_order_text(chat_id: int):
    await bot.send_message(
        chat_id,
        "✍️ Endi buyurtmangizni yozing.\n\n"
        "<i>Masalan: Rishtondan Toshkentga 2 ta odam bor</i>",
        reply_markup=cancel_inline_kb(),
    )


# ==================== MATN ====================
@dp.message_handler(state=PassengerStates.waiting_order_text, content_types=["text"])
async def passenger_order_text_got(message: types.Message, state: FSMContext):
    await state.update_data(passenger_text=message.text.strip())
    await state.set_state(PassengerStates.waiting_location)
    await message.answer(
        "📍 Lokatsiyangizni yubormoqchimisiz? Bu shofirimizga qulay bo‘ladi.\n"
        "(Majburiy emas)",
        reply_markup=location_choice_kb(),
    )


# ==================== LOKATSIYA ====================
@dp.message_handler(state=PassengerStates.waiting_location, content_types=["location"])
async def passenger_location_got(message: types.Message, state: FSMContext):
    data = await state.get_data()
    loc = {"lat": message.location.latitude, "lon": message.location.longitude}
    await _submit_passenger_ad(message.from_user.id, data, loc)
    await state.finish()
    await message.answer(
        "✅ Zakaz qabul qilindi! Shofir qabul qilishi kutilmoqda.",
        reply_markup=REMOVE_KB,
    )
    await message.answer("🏠 Asosiy menyu:", reply_markup=main_menu_kb(is_admin=message.from_user.id in ADMINS))


@dp.message_handler(lambda m: m.text == "➡️ Lokatsiyasiz davom etish", state=PassengerStates.waiting_location)
async def passenger_location_skip(message: types.Message, state: FSMContext):
    data = await state.get_data()
    await _submit_passenger_ad(message.from_user.id, data, None)
    await state.finish()
    await message.answer(
        "✅ E’lonimiz shofirlar guruhimizga yuborildi. Qabul qilinishi kutilmoqda.",
        reply_markup=REMOVE_KB,
    )
    await message.answer("🏠 Asosiy menyu:", reply_markup=main_menu_kb(is_admin=message.from_user.id in ADMINS))


# ==================== E'LONNI SAQLASH VA GURUHGA YUBORISH ====================
async def _submit_passenger_ad(from_uid: int, data: dict, location):
    uid = str(from_uid)
    ad_id = new_id()
    number = next_ad_number()

    ads_store.data["passenger"][ad_id] = {
        "user": uid,
        "route": data.get("passenger_route", "—"),
        "text": data.get("passenger_text", ""),
        "phone": data.get("passenger_phone") or get_user(uid).get("phone"),
        "location": location,
        "created": time.time(),
        "taken_by": None,
        "taken_by_name": None,
        "taken_by_username": None,
        "number": number,
        "group_msg_id": None,
    }
    await save_ads()
    await save_users()

    ad = ads_store.data["passenger"][ad_id]
    group_text = (
        f"🧍 <b>Yo‘lovchi e’loni</b>   <code>#{number:02d}</code>\n\n"
        f"📍 <b>{ad['route']}</b>\n\n"
        f"<blockquote>{ad['text']}</blockquote>"
    )
    kb = passenger_channel_kb(ad_id)
    for ch in PASSENGER_CHANNELS:
        try:
            msg = await bot.send_message(ch, group_text, reply_markup=kb)
            ad["group_msg_id"] = msg.message_id
            ad["group_chat_id"] = ch
        except Exception:
            pass
    await save_ads()


# ==================== HAYDOVCHI: E'LONNI KO'RISH ====================
@dp.callback_query_handler(lambda c: c.data.startswith("view_pass:"))
async def view_passenger_ad(call: types.CallbackQuery):
    ad_id = call.data.split(":")[1]
    ad = ads_store.data["passenger"].get(ad_id)
    if not ad:
        return await call.answer("❌ E’lon topilmadi yoki muddati o‘tgan.", show_alert=True)

    if ad.get("taken_by"):
        return await call.answer("❌ Ushbu e’lon allaqachon qabul qilingan.", show_alert=True)

    text = (
        f"🧍 <b>Yo‘lovchi e’loni</b>  <code>#{ad['number']:02d}</code>\n\n"
        f"📍 <b>Yo‘nalish:</b> {ad['route']}\n\n"
        f"<blockquote>{ad['text']}</blockquote>\n\n"
        f"📞 <b>Telefon:</b> {ad.get('phone') or '—'}"
    )
    kb = passenger_ad_full_kb(ad_id, has_location=bool(ad.get("location")))
    try:
        await bot.send_message(call.from_user.id, text, reply_markup=kb)
        await call.answer("📩 To‘liq e’lon botga yuborildi. Botni oching! ✅", show_alert=True)
    except Exception:
        await call.answer(
            "❌ Botga xabar yubora olmadik. Iltimos, avval botni /start bilan ishga tushiring.",
            show_alert=True,
        )


# ==================== HAYDOVCHI: QABUL QILISH ====================
@dp.callback_query_handler(lambda c: c.data.startswith("take_pass:"))
async def take_passenger_ad(call: types.CallbackQuery):
    uid = str(call.from_user.id)
    ad_id = call.data.split(":")[1]
    ad = ads_store.data["passenger"].get(ad_id)
    if not ad:
        return await call.answer("❌ E’lon topilmadi.", show_alert=True)

    if ad.get("taken_by"):
        return await call.answer(
            "Hurmatli shafyor, bu buyurtmani hamkasbingiz allaqachon qabul qildi. "
            "Iltimos, mijozni bezovta qilmang, ishingizda davom eting. 🙏",
            show_alert=True,
        )

    driver = get_user(uid)
    driver_name = display_name(driver, uid)

    ad["taken_by"] = uid
    ad["taken_by_name"] = driver_name
    ad["taken_by_username"] = driver.get("username") or ""
    await save_ads()

    # guruhdagi xabarni yangilash
    if ad.get("group_msg_id"):
        for ch in (ad.get("group_chat_id"),) if ad.get("group_chat_id") else PASSENGER_CHANNELS:
            try:
                new_text = (
                    f"🧍 <b>Yo‘lovchi e’loni</b>   <code>#{ad['number']:02d}</code>\n\n"
                    f"📍 <b>{ad['route']}</b>\n\n"
                    f"<blockquote>{ad['text']}</blockquote>\n\n"
                    f"✅ Qabul qilindi: <b>{driver_name}</b>"
                )
                await bot.edit_message_text(
                    new_text, ch, ad["group_msg_id"], reply_markup=passenger_channel_taken_kb()
                )
            except Exception:
                pass

    try:
        await call.message.edit_reply_markup()
    except Exception:
        pass
    await call.message.answer("✅ Siz ushbu zakazni qabul qildingiz. Yo‘lovchi bilan bog‘laning!")
    await call.answer()
    await send_sticker_safe(int(uid), "order_taken")

    # yo'lovchiga xabar
    passenger_uid = ad["user"]
    try:
        await bot.send_message(
            int(passenger_uid),
            f"✅ Sizni <b>{driver_name}</b> ismli shofirimiz qabul qildi. Oq yo‘l bo‘lsin! 🚕",
            reply_markup=driver_profile_kb(ad.get("taken_by_username")),
        )
        await bot.send_message(int(passenger_uid), "🙏 Keyingi safar ham bizni tanlang!")
    except Exception:
        pass


# ==================== LOKATSIYANI OCHISH ====================
@dp.callback_query_handler(lambda c: c.data.startswith("open_loc:"))
async def open_location(call: types.CallbackQuery):
    ad_id = call.data.split(":")[1]
    ad = ads_store.data["passenger"].get(ad_id)
    if not ad or not ad.get("location"):
        return await call.answer("❌ Lokatsiya topilmadi.", show_alert=True)
    await call.message.answer("🗺 Qaysi ilovada ochmoqchisiz?", reply_markup=map_choice_kb(ad_id))
    await call.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("maplink:"))
async def open_map_link(call: types.CallbackQuery):
    _, provider, ad_id = call.data.split(":")
    ad = ads_store.data["passenger"].get(ad_id)
    if not ad or not ad.get("location"):
        return await call.answer("❌ Lokatsiya topilmadi.", show_alert=True)

    lat, lon = ad["location"]["lat"], ad["location"]["lon"]
    if provider == "google":
        url, label = f"https://www.google.com/maps?q={lat},{lon}", "Google Maps"
    elif provider == "yandex":
        url, label = f"https://yandex.com/maps/?pt={quote(str(lon))},{quote(str(lat))}&z=16&l=map", "Yandex Maps"
    else:
        url, label = f"https://2gis.uz/geo/{lon},{lat}", "2GIS"

    await call.message.answer(f"📍 {label}:", reply_markup=open_map_link_kb(url, label))
    await call.answer()
