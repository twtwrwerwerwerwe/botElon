# taxi_bot.py
import json
import time
from pathlib import Path
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, ParseMode
)
from aiogram.utils import executor

# ====== SOZLAMALAR ======
TOKEN = "8212255968:AAETRL91puhUESsCP7eFKm7pE51tKgm6SQo"
GROUP_ID = -1002589715287
ADMIN_USERNAME = "akramjonovPY"
ADMIN_ID = None

DATA_FILE = Path("taxi_data.json")
# ========================

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# In-memory cache
data = {
    "users": {},   # user_id: {phone, role, approved(bool), username}
    "ads": [],     # list of ads
    "next_ad_id": 1
}

# ====== DATA LOAD / SAVE ======
def load_data():
    if DATA_FILE.exists():
        try:
            d = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            data.update(d)
        except Exception:
            pass

def save_data():
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

# ====== CLEANUP OLD ADS ======
def cleanup_old_ads(days=1):
    """Old ads cleanup"""
    cutoff = int(time.time()) - days * 24 * 60 * 60
    old_count = len(data["ads"])
    data["ads"] = [ad for ad in data["ads"] if ad.get("created_at", 0) >= cutoff]
    if len(data["ads"]) != old_count:
        save_data()

load_data()
cleanup_old_ads(days=1)  # bot ishga tushganda ham eski arizalarni o'chiradi

# ====== KEYBOARDS ======
def main_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("🚕 E'lon berish"))
    kb.add(KeyboardButton("🚘 Haydovchi bo‘limi"), KeyboardButton("🧭 Yo‘lovchi e'lonlari"))
    return kb

def contact_request_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("📱 Telefon raqamni yuborish", request_contact=True))
    kb.add(KeyboardButton("◀️ Orqaga"))
    return kb

def back_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("◀️ Orqaga"))
    return kb

def directions_kb():
    rows = [
        ["🚗 Qo‘qon → Toshkent", "🚗 Toshkent → Qo‘qon"],
        ["🚗 Rishton → Toshkent", "🚗 Toshkent → Rishton"],
        ["🚗 Buvayda → Toshkent", "🚗 Toshkent → Buvayda"],
        ["🚗 Yangi Qo‘rg‘on → Toshkent", "🚗 Toshkent → Yangi Qo‘rg‘on"],
        ["🚗 Farg‘ona → Toshkent", "🚗 Toshkent → Farg‘ona"],
        ["🚗 Bag‘dod → Toshkent", "🚗 Toshkent → Bag‘dod"],
    ]
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    for r in rows:
        kb.row(*[KeyboardButton(t) for t in r])
    kb.add(KeyboardButton("◀️ Orqaga"))
    return kb

def count_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("👤 1 kishi"), KeyboardButton("👥 2 kishi"))
    kb.row(KeyboardButton("👪 3 kishi"), KeyboardButton("👨‍👩‍👧‍👦 4 kishi"))
    kb.row(KeyboardButton("📦 Pochta bor"))
    kb.add(KeyboardButton("◀️ Orqaga"))
    return kb

def date_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    today = "📅 Bugun"
    tomorrow = "📅 Ertaga"
    kb.row(KeyboardButton(today), KeyboardButton(tomorrow))
    kb.add(KeyboardButton("◀️ Orqaga"))
    return kb

def hours_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    row = []
    for h in range(24):
        label = f"{h:02d}:00"
        row.append(KeyboardButton(label))
        if len(row) == 4:
            kb.row(*row)
            row = []
    if row:
        kb.row(*row)
    kb.add(KeyboardButton("◀️ Orqaga"))
    return kb

def driver_main_kb(approved=False):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    if approved:
        kb.add(KeyboardButton("🔎 Yonalsihlar (filtr)"), KeyboardButton("📣 Hammasi"))
    else:
        kb.add(KeyboardButton("ℹ️ To‘lov va admin bilan bog‘lanish"))
    kb.add(KeyboardButton("◀️ Orqaga"))
    return kb

# ====== UTIL ======
def format_ad(ad):
    t = (
        f"🚕 <b>Yangi buyurtma #{ad['id']}</b>\n\n"
        f"🛣 <b>Yo‘nalish:</b> {ad['direction']}\n\n"
        f"📞 <b>Telefon:</b> {ad['phone']}\n\n"
        f"👤 <b>Foydalanuvchi:</b> {ad.get('username','no')}\n\n"
        f"🚗 <b>Buyurtma turi:</b> {ad['count']}\n\n"
        f"🕒 <b>Kun:</b> {ad.get('date','-')}  |  <b>Soat:</b> {ad.get('time','-')}\n\n"
        f"🆔 <b>UserID:</b> {ad['user_id']}"
    )
    return t

def is_admin(user: types.User):
    if ADMIN_ID and user.id == ADMIN_ID:
        return True
    if user.username and user.username.lower() == ADMIN_USERNAME.lower():
        return True
    return False

# ====== HANDLERS ======
@dp.message_handler(commands=["start", "help"])
async def cmd_start(message: types.Message):
    uid = message.from_user.id
    if uid not in data["users"]:
        data["users"][uid] = {"phone": None, "role": None, "approved": False, "username": message.from_user.username or ""}
        save_data()
    await message.answer(
        "👋 <b>Assalomu alaykum!</b>\n\n"
        "🚖 <i>Rishton — Toshkent Taxi</i> botiga xush kelibsiz.\n\n"
        "Quyidagilardan birini tanlang:",
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu()
    )

# E'lon berish
@dp.message_handler(lambda m: m.text == "🚕 E'lon berish")
async def ask_phone(message: types.Message):
    uid = message.from_user.id
    data["users"].setdefault(uid, {"phone": None, "role": None, "approved": False, "username": message.from_user.username or ""})
    save_data()
    await message.answer("📞 Iltimos, telefon raqamingizni yuboring (tugma orqali yuborsangiz qulay):", reply_markup=contact_request_kb())

@dp.message_handler(content_types=types.ContentType.CONTACT)
async def handle_contact(message: types.Message):
    uid = message.from_user.id
    phone = message.contact.phone_number
    data["users"].setdefault(uid, {})
    data["users"][uid]["phone"] = phone
    data["users"][uid]["username"] = message.from_user.username or ""
    save_data()
    await message.answer("✅ Raqamingiz qabul qilindi.\nEndi siz haydovchi yoki yo‘lovchi ekanligingizni tanlang:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).row(KeyboardButton("🚘 Haydovchi"), KeyboardButton("🧍 Yo‘lovchi")).add(KeyboardButton("◀️ Orqaga")))

# Role tanlash
@dp.message_handler(lambda m: m.text in ["🚘 Haydovchi", "🧍 Yo‘lovchi"])
async def choose_role(message: types.Message):
    uid = message.from_user.id
    role = "driver" if message.text == "🚘 Haydovchi" else "passenger"
    data["users"].setdefault(uid, {})
    data["users"][uid]["role"] = role
    data["users"][uid]["username"] = message.from_user.username or ""
    save_data()
    if role == "driver":
        approve_kb = InlineKeyboardMarkup().add(
            InlineKeyboardButton("✅ Ruxsat berish (driver ga aylantirish)", callback_data=f"approve:{uid}")
        )
        admin_text = f"🟡 <b>Ruxsat so‘rovi</b>\n\nUser: @{message.from_user.username or message.from_user.full_name}\nUserID: {uid}\nTelefon: {data['users'][uid].get('phone','-')}\n\nAgar ushbu foydalanuvchini haydovchi sifatida ruxsat bermoqchi bo‘lsangiz, tugmaga bosing."
        try:
            if ADMIN_ID:
                await bot.send_message(ADMIN_ID, admin_text, parse_mode=ParseMode.HTML, reply_markup=approve_kb)
            await bot.send_message(f"@{ADMIN_USERNAME}", admin_text, parse_mode=ParseMode.HTML, reply_markup=approve_kb)
        except:
            kb = ReplyKeyboardMarkup(resize_keyboard=True)
            kb.add(KeyboardButton("📞 Admin bilan bog‘lanish", url=f"https://t.me/{ADMIN_USERNAME}"))
            kb.add(KeyboardButton("◀️ Orqaga"))
            await message.answer("⚠️ Haydovchi uchun admin bilan bog‘laning.", reply_markup=kb)
    else:
        await message.answer("🛣 Yo‘nalishni tanlang:", reply_markup=directions_kb())

# Admin approves driver
@dp.callback_query_handler(lambda c: c.data and c.data.startswith("approve:"))
async def process_approve(call: types.CallbackQuery):
    await call.answer()
    if not is_admin(call.from_user):
        await call.message.edit_text("❌ Sizda ruxsat yo‘q.")
        return
    _, sid = call.data.split(":")
    sid = int(sid)
    data["users"].setdefault(sid, {})
    data["users"][sid]["approved"] = True
    save_data()
    await call.message.edit_text(f"✅ User {sid} ruxsatlandi.")
    try:
        await bot.send_message(sid, "🎉 Sizga admin tomonidan haydovchi sifatida ruxsat berildi!", reply_markup=driver_main_kb(approved=True))
    except:
        pass

# Direction selection
@dp.message_handler(lambda m: "→" in (m.text or ""))
async def choose_direction(message: types.Message):
    uid = message.from_user.id
    data["users"].setdefault(uid, {})
    data["users"][uid]["direction"] = message.text
    save_data()
    await message.answer("📅 Iltimos, kunni tanlang:", reply_markup=date_kb())

# Date selection
@dp.message_handler(lambda m: m.text in ["📅 Bugun", "📅 Ertaga"])
async def choose_date(message: types.Message):
    uid = message.from_user.id
    if uid not in data["users"] or "direction" not in data["users"][uid]:
        await message.answer("Avval yo‘nalishni tanlang.", reply_markup=main_menu())
        return
    date = datetime.now().strftime("%Y-%m-%d") if message.text=="📅 Bugun" else (datetime.now()+timedelta(days=1)).strftime("%Y-%m-%d")
    data["users"][uid]["date"] = date
    save_data()
    await message.answer("🕒 Iltimos, vaqtni tanlang:", reply_markup=hours_kb())

# Time selection
@dp.message_handler(lambda m: m.text and m.text.endswith(":00"))
async def choose_time(message: types.Message):
    uid = message.from_user.id
    u = data["users"].get(uid, {})
    if "direction" not in u or "date" not in u:
        await message.answer("Avval yo‘nalish va kunni tanlang.", reply_markup=main_menu())
        return
    u["time"] = message.text
    save_data()
    await message.answer("🧍 Necha kishi bor?", reply_markup=count_kb())

# Count selection
@dp.message_handler(lambda m: any(x in (m.text or "") for x in ["kishi","Pochta","pochta","Pochta bor"]))
async def confirm_order(message: types.Message):
    uid = message.from_user.id
    u = data["users"].get(uid,{})
    if not u or "direction" not in u or "date" not in u or "time" not in u or "phone" not in u:
        await message.answer("Iltimos, barcha ma'lumotlarni to‘ldiring.", reply_markup=main_menu())
        return
    u["count"] = message.text
    ad = {
        "id": data["next_ad_id"],
        "user_id": uid,
        "username": f"@{message.from_user.username}" if message.from_user.username else message.from_user.full_name,
        "phone": u["phone"],
        "direction": u["direction"],
        "count": u["count"],
        "date": u["date"],
        "time": u["time"],
        "created_at": int(time.time())
    }
    data["users"][uid]["draft_ad"] = ad
    save_data()
    preview = format_ad(ad)
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("✅ Tasdiqlash"), KeyboardButton("❌ Rad etish"))
    kb.add(KeyboardButton("◀️ Orqaga"))
    await message.answer(preview, parse_mode=ParseMode.HTML, reply_markup=kb)

# Final confirm
@dp.message_handler(lambda m: m.text=="✅ Tasdiqlash")
async def send_to_group(message: types.Message):
    cleanup_old_ads(days=1)  # <--- shu yerda eski arizalarni o'chiramiz
    uid = message.from_user.id
    draft = data["users"].get(uid,{}).get("draft_ad")
    if not draft:
        await message.answer("Hech qanday e'lon topilmadi.", reply_markup=main_menu())
        return
    data["ads"].append(draft)
    data["next_ad_id"] += 1
    data["users"][uid].pop("draft_ad", None)
    save_data()
    try:
        await bot.send_message(GROUP_ID, format_ad(draft), parse_mode=ParseMode.HTML)
    except:
        pass
    await message.answer("✅ E’loningiz muvaffaqiyatli yuborildi!", reply_markup=main_menu())

# Cancel order
@dp.message_handler(lambda m: m.text=="❌ Rad etish")
async def cancel(message: types.Message):
    uid = message.from_user.id
    if uid in data["users"]:
        data["users"][uid].pop("draft_ad", None)
        save_data()
    await message.answer("❌ E’lon bekor qilindi.", reply_markup=main_menu())

# Go back
@dp.message_handler(lambda m: m.text=="◀️ Orqaga")
async def go_back(message: types.Message):
    await message.answer("🔙 Bosh menyuga qaytdingiz.", reply_markup=main_menu())

# Haydovchi bo'limi
@dp.message_handler(lambda m: m.text in ["🚘 Haydovchi bo‘limi","🔎 Yonalsihlar (filtr)","📣 Hammasi","ℹ️ To‘lov va admin bilan bog‘lanish"])
async def driver_section(message: types.Message):
    uid = message.from_user.id
    u = data["users"].get(uid,{})
    approved = u.get("approved",False)
    if message.text=="ℹ️ To‘lov va admin bilan bog‘lanish":
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add(KeyboardButton("📞 Admin bilan bog‘lanish", url=f"https://t.me/{ADMIN_USERNAME}"))
        kb.add(KeyboardButton("◀️ Orqaga"))
        await message.answer("To‘lov va admin bilan bog‘lanish uchun pastdagi tugmani bosing.", reply_markup=kb)
        return
    if not approved:
        await message.answer("⚠️ Siz hali haydovchi sifatida ruxsatlanmagansiz.", reply_markup=driver_main_kb(False))
        return
    if message.text=="📣 Hammasi":
        if not data["ads"]:
            await message.answer("Hozircha e'lonlar yo'q.", reply_markup=driver_main_kb(True))
            return
        for ad in reversed(data["ads"]):
            kb = ReplyKeyboardMarkup(resize_keyboard=True)
            kb.add(KeyboardButton("◀️ Orqaga"))
            await message.answer(format_ad(ad), parse_mode=ParseMode.HTML, reply_markup=kb)
        return
    if message.text in ["🔎 Yonalsihlar (filtr)","🚘 Haydovchi bo‘limi"]:
        directions = sorted(list({ad["direction"] for ad in data["ads"]}))
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        if directions:
            for d in directions:
                kb.add(KeyboardButton(d))
        else:
            kb.add(KeyboardButton("Hech yo‘nalish yo‘q"))
        kb.add(KeyboardButton("📣 Hammasi"))
        kb.add(KeyboardButton("◀️ Orqaga"))
        await message.answer("🧭 Yo‘nalishlardan birini tanlang (yoki Hammasi):", reply_markup=kb)
        return

# Driver view filtered ads
@dp.message_handler(lambda m: any(m.text == ad["direction"] for ad in data["ads"]) if data["ads"] else False)
async def driver_view_filtered(message: types.Message):
    uid = message.from_user.id
    u = data["users"].get(uid,{})
    if not u.get("approved",False):
        await message.answer("Siz ruxsatlanmagansiz.", reply_markup=main_menu())
        return
    chosen = message.text
    found = [ad for ad in data["ads"] if ad["direction"]==chosen]
    if not found:
        await message.answer("Ushbu yo‘nalishda e'lonlar topilmadi.", reply_markup=driver_main_kb(True))
        return
    for ad in reversed(found):
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add(KeyboardButton("◀️ Orqaga"))
        await message.answer(format_ad(ad), parse_mode=ParseMode.HTML, reply_markup=kb)

# Passenger ads
@dp.message_handler(lambda m: m.text=="🧭 Yo‘lovchi e'lonlari")
async def passenger_ads(message: types.Message):
    if not data["ads"]:
        await message.answer("Hozircha e'lonlar yo'q.", reply_markup=main_menu())
        return
    for ad in reversed(data["ads"]):
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add(KeyboardButton("◀️ Orqaga"))
        await message.answer(format_ad(ad), parse_mode=ParseMode.HTML, reply_markup=kb)

# Fallback
@dp.message_handler()
async def fallback(message: types.Message):
    await message.answer("😊 Men tushunmadim. Bosh menyu uchun /start yoki tugmalardan birini tanlang.", reply_markup=main_menu())

# Admin command
@dp.message_handler(commands=["approved"])
async def cmd_approved(message: types.Message):
    if not is_admin(message.from_user):
        await message.reply("Siz admin emassiz.")
        return
    parts = message.text.split()
    if len(parts)<2:
        await message.reply("Foydalanish: /approved <user_id>")
        return
    try:
        uid = int(parts[1])
    except:
        await message.reply("Noto'g'ri user_id.")
        return
    data["users"].setdefault(uid,{})
    data["users"][uid]["approved"]=True
    save_data()
    await message.reply(f"✅ {uid} ruxsatlandi.")
    try:
        await bot.send_message(uid,"🎉 Sizga admin tomonidan haydovchi sifatida ruxsat berildi!", reply_markup=driver_main_kb(True))
    except:
        pass

# Shutdown
async def on_shutdown(dp):
    save_data()
    await bot.close()

if __name__=="__main__":
    print("🚕 Taxi bot ishga tushdi...")
    executor.start_polling(dp, skip_updates=True, on_shutdown=on_shutdown)
