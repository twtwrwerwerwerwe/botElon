# taxi_bot_updated.py
"""
Kengaytirilgan Taxi bot
- Kontakt yuborilganda foydalanuvchi avtomatik yo'lovchi (passenger) bo'lib belgilanadi.
- "E'lon berish" jarayonida oxirida "necha marta yuborish" tugmalari (1,2,4,5,6)
  va interval 2 daqiqa bilan bir nechta yuborish amalga oshiriladi.
- Haydovchi bo'limi: 2 tugma — "E'lon berish" (haydovchi sifatida elon berish oqimi)
  va "Odam olish" (yo'nalish bo'yicha mavjud e'lonlarni ko'rish / olish).
- Haydovchi tomonidan elon berishda: yo'nalish -> soat (24) -> mashina tanlash -> telefon
  -> necha marta yuborish (1..20 + Cheksiz) -> interval (2 min yoki 2.5 min)
  -> tasdiqlash / tozalash / to'xtatish / habarni almashtirish
- Yuborishlar bot ichida asyncio vazifalari orqali amalga oshiriladi va to'xtatilishi mumkin.

Eslatma: ushbu faylni ishga tushirishdan oldin TOKEN va GROUP_ID larni tekshiring.
"""

import json
import time
import asyncio
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
ADMIN_ID = 6302873072

DATA_FILE = Path("taxi_data.json")
# ========================

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# In-memory cache
data = {
    "users": {},   # user_id: {phone, role, approved(bool), username, draft_*}
    "ads": [],     # list of active ads
    "next_ad_id": 1,
    "jobs": {}     # ad_id -> {task, stop_flag}
}

# ====== DATA LOAD / SAVE ======

def load_data():
    if DATA_FILE.exists():
        try:
            d = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            # merge safely
            for k, v in d.items():
                data[k] = v
        except Exception:
            pass


def save_data():
    # don't attempt to serialize tasks; only persist simple fields
    to_save = {k: v for k, v in data.items() if k != "jobs"}
    DATA_FILE.write_text(json.dumps(to_save, ensure_ascii=False, indent=2), encoding="utf-8")

# ====== CLEANUP OLD ADS ======

def cleanup_old_ads(days=1):
    cutoff = int(time.time()) - days * 24 * 60 * 60
    old_count = len(data["ads"])
    data["ads"] = [ad for ad in data["ads"] if ad.get("created_at", 0) >= cutoff]
    if len(data["ads"]) != old_count:
        save_data()

load_data()
cleanup_old_ads(days=1)

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


def back_kb(label="◀️ Orqaga"):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton(label))
    return kb


def directions_kb():
    # dynamic: include all known directions + some defaults
    rows = []
    default_rows = [
        "🚗 Qo‘qon → Toshkent", "🚗 Toshkent → Qo‘qon",
        "🚗 Rishton → Toshkent", "🚗 Toshkent → Rishton",
        "🚗 Buvayda → Toshkent", "🚗 Toshkent → Buvayda",
        "🚗 Yangi Qo‘rg‘on → Toshkent", "🚗 Toshkent → Yangi Qo‘rg‘on",
        "🚗 Farg‘ona → Toshkent", "🚗 Toshkent → Farg‘ona",
        "🚗 Bag‘dod → Toshkent", "🚗 Toshkent → Bag‘dod",
    ]
    # include directions from existing ads first
    dyn_dirs = sorted(set(ad["direction"] for ad in data.get("ads", [])))
    choices = dyn_dirs + default_rows
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    added = set()
    for d in choices:
        if d and d not in added:
            kb.add(KeyboardButton(d))
            added.add(d)
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


def send_count_kb_small():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("1 marta"), KeyboardButton("2 marta"), KeyboardButton("4 marta"))
    kb.row(KeyboardButton("5 marta"), KeyboardButton("6 marta"))
    kb.add(KeyboardButton("◀️ Orqaga"))
    return kb


def send_count_kb_large():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    # 1..20 + Cheksiz
    row = []
    for i in range(1, 21):
        row.append(KeyboardButton(str(i)))
        if len(row) == 5:
            kb.row(*row)
            row = []
    if row:
        kb.row(*row)
    kb.row(KeyboardButton("Cheksiz"), KeyboardButton("◀️ Orqaga"))
    return kb


def interval_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("2 minut"), KeyboardButton("2.5 minut"))
    kb.add(KeyboardButton("◀️ Orqaga"))
    return kb


def driver_main_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("📣 E'lon berish"), KeyboardButton("🧍 Odam olish"))
    kb.add(KeyboardButton("◀️ Orqaga"))
    return kb


def car_kb():
    cars = ["Trezor", "Malibu", "Kia k5", "Gentra", "Cobalt", "Nexia", "BYD"]
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    for c in cars:
        kb.add(KeyboardButton(c))
    kb.add(KeyboardButton("◀️ Orqaga"))
    return kb

# ====== UTIL ======

def format_ad(ad):
    t = (
        f"🚕 <b>Yangi buyurtma #{ad['id']}</b>\n\n"
        f"🛣 <b>Yo‘nalish:</b> {ad['direction']}\n\n"
        f"📞 <b>Telefon:</b> {ad['phone']}\n\n"
        f"👤 <b>Foydalanuvchi:</b> {ad.get('username','-')}\n\n"
        f"🚗 <b>Buyurtma turi:</b> {ad.get('count','-')}\n\n"
        f"🕒 <b>Kun:</b> {ad.get('date','-')}  |  <b>Soat:</b> {ad.get('time','-')}\n\n"
        f"🆔 <b>UserID:</b> {ad['user_id']}\n\n"
        f"📣 <i>Takrorlanadi:</i> {ad.get('send_times','1')} marta, Interval: {ad.get('interval','2')} min"
    )
    return t


def is_admin(user: types.User):
    if ADMIN_ID and user.id == ADMIN_ID:
        return True
    if user.username and user.username.lower() == ADMIN_USERNAME.lower():
        return True
    return False

# ====== SENDING TASKS ======

async def send_repeated(ad, send_times, interval_min):
    """Asinxron ravishda guruhga bir nechta marta e'lon yuboradi.
    Agar send_times is 'Cheksiz', davom etadi, to'xtatish flag tekshiriladi.
    """
    ad_id = ad['id']
    sent = 0
    # stop flag
    stop_flag = data['jobs'].setdefault(ad_id, {}).get('stop_flag')
    while True:
        # check stop flag
        if data['jobs'].get(ad_id, {}).get('stop'):
            break
        try:
            await bot.send_message(GROUP_ID, format_ad(ad), parse_mode=ParseMode.HTML)
            sent += 1
        except Exception as e:
            # log, but continue
            print('send error', e)
        if send_times == 'Cheksiz':
            # sleep then continue until stopped
            await asyncio.sleep(int(interval_min * 60))
            continue
        if sent >= int(send_times):
            break
        await asyncio.sleep(int(interval_min * 60))
    # task finished
    data['jobs'].pop(ad_id, None)

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

# E'lon berish bosilganda - avval telefon so'raymiz
@dp.message_handler(lambda m: m.text == "🚕 E'lon berish")
async def ask_phone(message: types.Message):
    uid = message.from_user.id
    data["users"].setdefault(uid, {"phone": None, "role": None, "approved": False, "username": message.from_user.username or ""})
    save_data()
    # IMPORTANT CHANGE: don't ask driver/passenger — auto assign passenger after contact
    await message.answer("📞 Iltimos, telefon raqamingizni yuboring (tugma orqali yuborsangiz qulay):", reply_markup=contact_request_kb())

@dp.message_handler(content_types=types.ContentType.CONTACT)
async def handle_contact(message: types.Message):
    uid = message.from_user.id
    phone = message.contact.phone_number
    data["users"].setdefault(uid, {})
    data["users"][uid]["phone"] = phone
    data["users"][uid]["username"] = message.from_user.username or ""
    # AUTO: make passenger
    data["users"][uid]["role"] = "passenger"
    save_data()
    # Continue flow: show directions
    await message.answer("✅ Raqamingiz qabul qilindi. Siz avtomatik ravishda <b>Yo'lovchi</b> sifatida belgilanding.\n\n🛣 Yo'nalishni tanlang:", parse_mode=ParseMode.HTML, reply_markup=directions_kb())

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
    # create draft ad
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
    # NEW: show how many times to send (small set)
    await message.answer(preview, parse_mode=ParseMode.HTML)
    await message.answer("Necha marta yuborilsin?", reply_markup=send_count_kb_small())

# small send count for passengers
@dp.message_handler(lambda m: m.text in ["1 marta","2 marta","4 marta","5 marta","6 marta"])
async def passenger_send_count(message: types.Message):
    uid = message.from_user.id
    d = data["users"].get(uid, {})
    draft = d.get("draft_ad")
    if not draft:
        await message.answer("Hech qanday e'lon topilmadi.", reply_markup=main_menu())
        return
    times = message.text.split()[0]
    draft["send_times"] = times
    draft["interval"] = 2  # fixed 2 minutes as requested
    # finalize: add to ads and schedule sends
    data["ads"].append(draft)
    data["next_ad_id"] += 1
    data["users"][uid].pop("draft_ad", None)
    save_data()
    # schedule as async task
    ad_copy = draft.copy()
    ad_id = ad_copy['id']
    task = asyncio.create_task(send_repeated(ad_copy, times, ad_copy['interval']))
    data['jobs'][ad_id] = {'task': task, 'stop': False}
    await message.answer("✅ E’loningiz yuborish uchun rejalashtirildi! (har 2 daqiqada)", reply_markup=main_menu())

# Final confirm from previous simple flow (if user pressed confirm instead of choosing send_count)
@dp.message_handler(lambda m: m.text=="✅ Tasdiqlash")
async def send_to_group(message: types.Message):
    cleanup_old_ads(days=1)
    uid = message.from_user.id
    draft = data["users"].get(uid,{}).get("draft_ad")
    if not draft:
        await message.answer("Hech qanday e'lon topilmadi.", reply_markup=main_menu())
        return
    # default single send
    draft["send_times"] = 1
    draft["interval"] = 2
    data["ads"].append(draft)
    data["next_ad_id"] += 1
    data["users"][uid].pop("draft_ad", None)
    save_data()
    # schedule
    ad_copy = draft.copy()
    ad_id = ad_copy['id']
    task = asyncio.create_task(send_repeated(ad_copy, ad_copy['send_times'], ad_copy['interval']))
    data['jobs'][ad_id] = {'task': task, 'stop': False}
    try:
        await bot.send_message(GROUP_ID, format_ad(ad_copy), parse_mode=ParseMode.HTML)
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
@dp.message_handler(lambda m: m.text=="🚘 Haydovchi bo‘limi" or m.text=="🔎 Yonalsihlar (filtr)" or m.text=="📣 Hammasi" or m.text=="ℹ️ To‘lov va admin bilan bog‘lanish")
async def driver_section(message: types.Message):
    uid = message.from_user.id
    u = data["users"].get(uid,{})
    approved = u.get("approved",False)
    # new: show driver main keyboard
    await message.answer("🚘 Haydovchi bo‘limi", reply_markup=driver_main_kb())

# Driver main choices
@dp.message_handler(lambda m: m.text in ["📣 E'lon berish", "🧍 Odam olish"])
async def driver_choices(message: types.Message):
    uid = message.from_user.id
    if message.text == "🧍 Odam olish":
        # show directions based on ads
        directions = sorted(list({ad["direction"] for ad in data["ads"]}))
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        if directions:
            for d in directions:
                kb.add(KeyboardButton(d))
        else:
            kb.add(KeyboardButton("Hech yo‘nalish yo‘q"))
        kb.add(KeyboardButton("◀️ Orqaga"))
        await message.answer("🧭 Yo‘nalishlardan birini tanlang:", reply_markup=kb)
        return
    # if E'lon berish by driver: follow driver-specific flow
    await message.answer("🛣 Yo‘nalishni tanlang:", reply_markup=directions_kb())
    # mark that this user is in driver_ad_flow
    data['users'].setdefault(uid, {})['driver_flow'] = True
    save_data()

# Show ads for chosen direction when driver pressed Odam olish or selected
@dp.message_handler(lambda m: any(m.text == ad["direction"] for ad in data["ads"]) if data["ads"] else False)
async def driver_view_filtered(message: types.Message):
    uid = message.from_user.id
    text = message.text
    # if user in driver_flow or pressed Odam olish, show special options
    u = data['users'].get(uid, {})
    # if driver_flow True -> this is driver creating an ad
    if u.get('driver_flow'):
        # driver creating ad: selected direction
        u['direction'] = text
        save_data()
        await message.answer("🕒 Iltimos, vaqtni tanlang:", reply_markup=hours_kb())
        return
    # else, treat as driver looking for ads
    found = [ad for ad in data['ads'] if ad['direction'] == text]
    if not found:
        await message.answer("Ushbu yo‘nalishda e'lonlar topilmadi.", reply_markup=driver_main_kb())
        return
    # show options: "Ortga shu yonalishdagi elonlar"
    for ad in reversed(found):
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add(KeyboardButton("◀️ Orqaga"))
        await message.answer(format_ad(ad), parse_mode=ParseMode.HTML, reply_markup=kb)

# Driver ad flow: after time chosen -> car
@dp.message_handler(lambda m: m.text and m.text.endswith(":00") and data['users'].get(m.from_user.id, {}).get('driver_flow'))
async def driver_time_chosen(message: types.Message):
    uid = message.from_user.id
    u = data['users'].setdefault(uid, {})
    u['time'] = message.text
    save_data()
    await message.answer("🚗 Mashina tanlang:", reply_markup=car_kb())

# Driver car chosen -> ask for contact
@dp.message_handler(lambda m: m.text in ["Trezor","Malibu","Kia k5","Gentra","Cobalt","Nexia","BYD"] and data['users'].get(m.from_user.id, {}).get('driver_flow'))
async def driver_car_chosen(message: types.Message):
    uid = message.from_user.id
    u = data['users'].setdefault(uid, {})
    u['car'] = message.text
    save_data()
    await message.answer("📞 Iltimos telefon raqamingizni yuboring:", reply_markup=contact_request_kb())

# Driver contact handler (for driver_flow)
@dp.message_handler(content_types=types.ContentType.CONTACT)
async def driver_contact_handler(message: types.Message):
    uid = message.from_user.id
    u = data['users'].setdefault(uid, {})
    # if in driver_flow and contact provided
    if u.get('driver_flow'):
        u['phone'] = message.contact.phone_number
        u['username'] = message.from_user.username or ''
        save_data()
        await message.answer("Necha marta yuborilsin? (1..20 yoki Cheksiz)", reply_markup=send_count_kb_large())
        return
    # else handled earlier passenger contact

# Driver send count large
@dp.message_handler(lambda m: (m.text and (m.text.isdigit() and 1 <= int(m.text) <= 20 or m.text == 'Cheksiz')) and data['users'].get(m.from_user.id, {}).get('driver_flow'))
async def driver_send_count_selected(message: types.Message):
    uid = message.from_user.id
    u = data['users'].get(uid, {})
    u['send_times'] = message.text
    save_data()
    await message.answer("Intervalni tanlang:", reply_markup=interval_kb())

# Interval chosen
@dp.message_handler(lambda m: m.text in ["2 minut", "2.5 minut"] and data['users'].get(m.from_user.id, {}).get('driver_flow'))
async def driver_interval_chosen(message: types.Message):
    uid = message.from_user.id
    u = data['users'].get(uid, {})
    u['interval'] = 2.0 if message.text == '2 minut' else 2.5
    save_data()
    # show confirm / tozalash
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("✅ Tasdiqlash"), KeyboardButton("🧹 Tozalash"))
    kb.row(KeyboardButton("⏸ To'xtatish"), KeyboardButton("✏️ Habarni almashtirish"))
    kb.add(KeyboardButton("◀️ Orqaga"))
    await message.answer("Ma'lumotlarni tekshiring va tasdiqlang:", reply_markup=kb)

# Driver confirm
@dp.message_handler(lambda m: m.text=="✅ Tasdiqlash" and data['users'].get(m.from_user.id, {}).get('driver_flow'))
async def driver_confirm(message: types.Message):
    uid = message.from_user.id
    u = data['users'].get(uid, {})
    # build ad
    ad = {
        'id': data['next_ad_id'],
        'user_id': uid,
        'username': u.get('username','-'),
        'phone': u.get('phone','-'),
        'direction': u.get('direction','-'),
        'count': u.get('car','-'),
        'date': u.get('date', datetime.now().strftime('%Y-%m-%d')),
        'time': u.get('time','-'),
        'created_at': int(time.time()),
        'send_times': u.get('send_times',1),
        'interval': u.get('interval',2.0)
    }
    data['ads'].append(ad)
    data['next_ad_id'] += 1
    # clear driver_flow data
    for k in ['driver_flow','direction','time','car','phone','send_times','interval']:
        u.pop(k, None)
    save_data()
    # schedule sending
    ad_copy = ad.copy()
    ad_id = ad_copy['id']
    task = asyncio.create_task(send_repeated(ad_copy, ad_copy['send_times'], ad_copy['interval']))
    data['jobs'][ad_id] = {'task': task, 'stop': False}
    await message.answer("✅ E'lon yaratilidi va yuborish boshlandi.", reply_markup=main_menu())

# Tozalash
@dp.message_handler(lambda m: m.text=="🧹 Tozalash" and data['users'].get(m.from_user.id, {}).get('driver_flow'))
async def driver_clear(message: types.Message):
    uid = message.from_user.id
    u = data['users'].get(uid, {})
    for k in ['driver_flow','direction','time','car','phone','send_times','interval']:
        u.pop(k, None)
    save_data()
    await message.answer("Ma'lumotlar tozalandi.", reply_markup=main_menu())

# To'xtatish
@dp.message_handler(lambda m: m.text=="⏸ To'xtatish")
async def stop_job(message: types.Message):
    # allow stopping by ad id? We'll try to stop all jobs started by this user
    uid = message.from_user.id
    stopped = 0
    for ad in list(data['ads']):
        if ad.get('user_id') == uid:
            job = data['jobs'].get(ad['id'])
            if job:
                job['stop'] = True
                # cancel task if exists
                t = job.get('task')
                try:
                    t.cancel()
                except:
                    pass
                data['jobs'].pop(ad['id'], None)
                stopped += 1
    await message.answer(f"{stopped} ta yuborish to'xtatildi.", reply_markup=main_menu())

# Habarni almashtirish -> simply set driver_flow True again and start over
@dp.message_handler(lambda m: m.text=="✏️ Habarni almashtirish" and data['users'].get(m.from_user.id, {}).get('driver_flow') is not None)
async def edit_message_flow(message: types.Message):
    uid = message.from_user.id
    data['users'].setdefault(uid, {})['driver_flow'] = True
    save_data()
    await message.answer("Yangidan boshlash: Yo'nalishni tanlang:", reply_markup=directions_kb())

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
        await bot.send_message(uid,"🎉 Sizga admin tomonidan haydovchi sifatida ruxsat berildi!", reply_markup=driver_main_kb())
    except:
        pass

# Shutdown
async def on_shutdown(dp):
    save_data()
    # cancel running tasks
    for job in list(data.get('jobs', {}).values()):
        t = job.get('task')
        try:
            t.cancel()
        except:
            pass
    await bot.close()

if __name__=="__main__":
    print("🚕 Taxi bot yangilandi — ishga tushmoqda...")
    executor.start_polling(dp, skip_updates=True, on_shutdown=on_shutdown)
