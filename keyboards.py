# -*- coding: utf-8 -*-
"""keyboards.py — barcha klaviaturalar shu yerda, bitta joyda.

Iloji boricha barcha tugmalar endi INLINE (xabar ostida) qilib
chiqariladi — yozish maydonini to'smaydi. Faqat Telegram texnik
sabablarga ko'ra MAJBURIY qiladigan ikkita joy bundan mustasno:
telefon raqamni "tugma orqali yuborish" (request_contact) va
lokatsiyani "tugma orqali yuborish" (request_location) — булар faqat
oddiy (reply) klaviaturada ishlaydi, Telegram shunday talab qiladi.
"""
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from config import TARIFFS, AD_INTERVALS, PASSENGER_ROUTES, BOT_USERNAME, ADMIN_USERNAME

REMOVE_KB = ReplyKeyboardRemove()


# ==================== ASOSIY MENYU (inline) ====================
def main_menu_kb(is_admin: bool = False) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🚘 Haydovchi", callback_data="menu:driver"),
        InlineKeyboardButton("🧍 Yo‘lovchi", callback_data="menu:passenger"),
    )
    if is_admin:
        kb.add(
            InlineKeyboardButton("👥 Haydovchilar", callback_data="menu:admin_drivers"),
            InlineKeyboardButton("💳 To‘lovlar", callback_data="menu:admin_payments"),
        )
    return kb


def home_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🏠 Bosh menyu", callback_data="menu:home"))
    return kb


def cancel_inline_kb() -> InlineKeyboardMarkup:
    """Matn/rasm kutilayotgan bosqichlarda xabar ostida chiqadigan bekor qilish tugmasi."""
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_flow"))
    return kb


# ==================== HAYDOVCHI ====================
def driver_apply_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("📨 Ariza yuborish", callback_data="drv_apply"))
    kb.add(InlineKeyboardButton("🏠 Bosh menyu", callback_data="menu:home"))
    return kb


def phone_request_kb() -> ReplyKeyboardMarkup:
    """Telegram talabiga ko'ra, telefon raqamni tugma orqali yuborish
    FAQAT oddiy (reply) klaviaturada ishlaydi — shuning uchun bu yerda
    istisno qilinadi."""
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(KeyboardButton("📱 Raqamni yuborish", request_contact=True))
    kb.add(KeyboardButton("❌ Bekor qilish"))
    return kb


def driver_main_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📣 E’lon berish", callback_data="drv_post_ad"),
        InlineKeyboardButton("⏸ To‘xtatish", callback_data="drv_pause"),
    )
    kb.add(
        InlineKeyboardButton("🆕 Yangi e’lon", callback_data="drv_new_ad"),
        InlineKeyboardButton("💳 Mening obunam", callback_data="drv_sub"),
    )
    kb.add(InlineKeyboardButton("🏠 Bosh menyu", callback_data="menu:home"))
    return kb


def interval_inline_kb() -> InlineKeyboardMarkup:
    """E'lon necha daqiqada yuborilishini tanlash — xabar ostida inline tugma."""
    kb = InlineKeyboardMarkup(row_width=3)
    kb.add(*[
        InlineKeyboardButton(f"{m} daqiqa", callback_data=f"ad_interval:{m}")
        for m in AD_INTERVALS
    ])
    kb.add(InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel_flow"))
    return kb


def ad_confirm_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✅ Tasdiqlash va yuborish", callback_data="ad_confirm"),
        InlineKeyboardButton("🗑 Bekor qilish", callback_data="ad_cancel"),
    )
    return kb


def driver_channel_ad_kb(ad_id: str, uid: str, username: str) -> InlineKeyboardMarkup:
    """
    "Qo'ng'iroq" o'rniga endi "Haydovchi profili" tugmasi turadi.
    Agar haydovchida ochiq username bo'lsa — tugma to'g'ridan-to'g'ri
    o'sha profilga o'tadi (bitta bosishda, eng ishonchli usul). Agar
    username bo'lmasa (ba'zi foydalanuvchilar buni yashiradi), profilni
    ID orqali ochish har doim ham ishlayvermaydi — shu holatda tugma
    bot orqali profil ma'lumotini (ism, telefon) ko'rsatadi.
    """
    kb = InlineKeyboardMarkup(row_width=1)
    if username:
        kb.add(InlineKeyboardButton("👤 Haydovchi profili", url=f"https://t.me/{username}"))
    else:
        kb.add(InlineKeyboardButton("👤 Haydovchi profili", callback_data=f"profile_drv:{ad_id}"))
    kb.add(InlineKeyboardButton(
        "📩 Zakaz berish", url=f"https://t.me/{BOT_USERNAME}?start=zakaz"
    ))
    return kb


# ==================== ADMIN — HAYDOVCHI TASDIQLASH ====================
def admin_driver_decision_kb(uid: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"drv_ok:{uid}"),
        InlineKeyboardButton("❌ Rad etish", callback_data=f"drv_no:{uid}"),
    )
    return kb


def admin_driver_manage_kb(uid: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("❌ Chiqarib tashlash", callback_data=f"drv_remove:{uid}"),
        InlineKeyboardButton("✅ Qoldirish", callback_data=f"drv_keep:{uid}"),
    )
    return kb


# ==================== TO'LOV / TARIFLAR ====================
def tariff_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    for key, t in TARIFFS.items():
        price = f"{t['price']:,}".replace(",", " ")
        kb.add(InlineKeyboardButton(
            f"{t['label']} — {price} so‘m", callback_data=f"tariff:{key}"
        ))
    return kb


def payment_method_kb(tariff_key: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("👨‍💼 Admin orqali murojaat", callback_data=f"pm:admin:{tariff_key}"))
    kb.add(InlineKeyboardButton("💳 Click / Payme", callback_data=f"pm:click:{tariff_key}"))
    kb.add(InlineKeyboardButton("🧾 Chek orqali to‘lov", callback_data=f"pm:receipt:{tariff_key}"))
    kb.add(InlineKeyboardButton("⬅️ Orqaga (tarif tanlash)", callback_data="pm:back"))
    return kb


def admin_payment_decision_kb(payment_id: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"pay_ok:{payment_id}"),
        InlineKeyboardButton("❌ Rad etish", callback_data=f"pay_no:{payment_id}"),
    )
    return kb


def contact_admin_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton(f"✍️ {ADMIN_USERNAME} bilan yozishish", url=f"https://t.me/{ADMIN_USERNAME.lstrip('@')}"))
    return kb


# ==================== YO'LOVCHI ====================
def passenger_entry_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🚖 Haydovchi chaqirish", callback_data="pass_order"))
    kb.add(InlineKeyboardButton("🏠 Bosh menyu", callback_data="menu:home"))
    return kb


def route_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    for i, r in enumerate(PASSENGER_ROUTES):
        kb.add(InlineKeyboardButton(f"🚗 {r}", callback_data=f"route:idx:{i}"))
    kb.add(InlineKeyboardButton("✍️ O‘zim yozaman", callback_data="route:custom"))
    return kb


def location_choice_kb() -> ReplyKeyboardMarkup:
    """Lokatsiyani tugma orqali yuborish FAQAT reply klaviaturada
    ishlaydi — Telegram shunday talab qiladi."""
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(KeyboardButton("📍 Lokatsiyani yuborish", request_location=True))
    kb.add(KeyboardButton("➡️ Lokatsiyasiz davom etish"))
    kb.add(KeyboardButton("❌ Bekor qilish"))
    return kb


def passenger_channel_kb(ad_id: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("👁 E’lonni ko‘rish", callback_data=f"view_pass:{ad_id}"))
    return kb


def passenger_channel_taken_kb() -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("✅ Qabul qilindi", callback_data="taken"))
    return kb


def passenger_ad_full_kb(ad_id: str, has_location: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("✅ Qabul qilish", callback_data=f"take_pass:{ad_id}"))
    if has_location:
        kb.add(InlineKeyboardButton("📍 Lokatsiyani ochish", callback_data=f"open_loc:{ad_id}"))
    return kb


def map_choice_kb(ad_id: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🗺 Google Maps", callback_data=f"maplink:google:{ad_id}"))
    kb.add(InlineKeyboardButton("🗺 Yandex Maps", callback_data=f"maplink:yandex:{ad_id}"))
    kb.add(InlineKeyboardButton("🗺 2GIS", callback_data=f"maplink:2gis:{ad_id}"))
    return kb


def open_map_link_kb(url: str, label: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton(f"📍 {label}da ochish", url=url))
    return kb


def driver_profile_kb(username: str) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    if username:
        kb.add(InlineKeyboardButton("👤 Haydovchi profili", url=f"https://t.me/{username}"))
    return kb


def open_in_bot_kb(payload: str = "zakaz") -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🤖 Botga o‘tish", url=f"https://t.me/{BOT_USERNAME}?start={payload}"))
    return kb