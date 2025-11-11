# taxi_bot.py
import asyncio
import json
import time
from pathlib import Path
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ParseMode
from aiogram.utils import executor

# ================== SOZLAMALAR ==================
TOKEN = "8212255968:AAETRL91puhUESsCP7eFKm7pE51tKgm6SQo"   # <-- o'zingiz tokenni qo'ying
# Eski yagona GROUP_ID saqlanmoqda fallback uchun:
# GROUP_ID = -1002774668004       # <-- eski guruh/chat ID (masalan: -100xxxx)

# Yangi: haydovchi va yo'lovchi uchun alohida guruhlar
DRIVER_GROUP_ID = -1001499767213       # <-- haydovchilar e'lonlari uchun guruh ID (o'zgartiring)
PASSENGER_GROUP_ID = -1002774668004    # <-- yo'lovchilar e'lonlari uchun guruh ID (o'zgartiring)

DATA_FILE = Path("taxi_data.json")
# =================================================

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# In-memory data (saqlash taxi_data.json ga)
data = {
    "users": {},   # uid -> {role, phone, state, draft_ad, username}
    "ads": [],     # list of ads (haydovchi va yo'lovchi aralash)
    "next_ad_id": 1,
    "jobs": {}     # ad_id -> {task, stop_flag, user_id, interval}
}

# ======= yordamchi funksiya: yuklash/saqlash =======
def load_data():
    if DATA_FILE.exists():
        try:
            d = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            for k, v in d.items():
                data[k] = v
        except Exception:
            print("Data load error, continuing with empty data.")


def save_data():
    # jobs obyektni saqlamaymiz (task obyektlari jsonlanmaydi)
    to_save = {k: v for k, v in data.items() if k != "jobs"}
    DATA_FILE.write_text(json.dumps(to_save, ensure_ascii=False, indent=2), encoding="utf-8")


load_data()

# ======= statik ro'yhatlar =======
DIRECTIONS = [
    "🚗 Qo‘qon → Toshkent", "🚗 Toshkent → Qo‘qon",
    "🚗 Rishton → Toshkent", "🚗 Toshkent → Rishton",
    "🚗 Buvayda → Toshkent", "🚗 Toshkent → Buvayda",
    "🚗 Yangi Qo‘rg‘on → Toshkent", "🚗 Toshkent → Yangi Qo‘rg‘on",
    "🚗 Farg‘ona → Toshkent", "🚗 Toshkent → Farg‘ona",
    "🚗 Bag‘dod → Toshkent", "🚗 Toshkent → Bag‘dod",
]

CARS = ["Malibu 1", "Tracker 2", "BYD", "Kia k5", "Cobalt", "Gentra", "Nexia", "Malibu 1", "Onix", "Monza"]

# ======= keyboard makers =======
def start_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("🚘 Haydovchiman"), KeyboardButton("🧍 Yo'lovchiman"))
    return kb

def driver_main_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("📣 E'lon berish"), KeyboardButton("🗂 E'lonlar"))
    kb.row(KeyboardButton("🧾 Mening e'lonlarim"), KeyboardButton("◀️ Asosiy menyu"))
    return kb

def passenger_main_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("🚕 E'lon berish"), KeyboardButton("🗂 E'lonlar"))
    kb.add(KeyboardButton("◀️ Asosiy menyu"))
    return kb

def directions_kb(include_other=True):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    for d in DIRECTIONS:
        kb.add(KeyboardButton(d))
    if include_other:
        kb.add(KeyboardButton("🟢 Boshqa"))
    kb.add(KeyboardButton("◀️ Orqaga"))
    return kb

def cars_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    for c in CARS:
        kb.add(KeyboardButton(c))
    kb.add(KeyboardButton("🟢 Boshqa"))
    kb.add(KeyboardButton("◀️ Orqaga"))
    return kb

def contact_request_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("📱 Telefon raqamni yuborish", request_contact=True))
    kb.add(KeyboardButton("◀️ Orqaga"))
    return kb

def photo_or_skip_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("⛔ Tashlab ketish"))
    kb.add(KeyboardButton("📱 Telefon raqamni yuborish", request_contact=True))
    kb.add(KeyboardButton("◀️ Orqaga"))
    return kb

def confirm_clear_kb(additional=None):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("✅ Tasdiqlash"), KeyboardButton("🧹 Tozalash"))
    if additional:
        kb.row(*additional)
    kb.add(KeyboardButton("◀️ Asosiy menyu"))
    return kb

def post_control_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("⏸ Habarni to'xtatish"), KeyboardButton("➕ Yangi habar"))
    kb.add(KeyboardButton("◀️ Asosiy menyu"))
    return kb

# ======= util: formatlash =======
def format_passenger_ad(ad):
    t = (
        f"🚕 <b>Yangi buyurtma #{ad['id']}</b>\n\n"
        f"🛣 <b>Yo‘nalish:</b> {ad.get('direction','-')}\n\n"
        f"📞 <b>Telefon:</b> {ad.get('phone','-')}\n\n"
        f"👤 <b>Foydalanuvchi:</b> {ad.get('username','-')}\n\n"
        f"🚗 <b>Buyurtma turi:</b> {ad.get('count','-')}\n\n"
        f"🕒 <b>Kun:</b> {ad.get('date','-')}  |  <b>Soat:</b> {ad.get('time','-')}\n\n"
        f"🆔 <b>UserID:</b> {ad.get('user_id','-')}\n"
    )
    return t

def format_driver_ad(ad):
    t = (
        f"{ad.get('text','')}\n\n"
        f"🛣 <b>Yo‘nalish:</b> {ad.get('direction','-')}\n\n"
        f"📞 <b>Telefon:</b> {ad.get('phone','-')}\n\n"
        f"🚗 <b>Mashina:</b> {ad.get('car','-')}\n\n"
        f"🕒 <b>Kun:</b> {ad.get('date','-')}\n\n"
        f"🆔 <b>UserID:</b> {ad.get('user_id','-')}\n"
    )
    return t

# ======= sending task (haydovchi e'lonlarini cheksiz yuborish) =======
async def send_indefinitely(ad_id):
    """Ad_id ga mos adni tegishli guruhga interval bo'yicha yuboradi; to'xtatish flag tekshiriladi."""
    job = data['jobs'].get(ad_id)
    if not job:
        return
    interval = job.get('interval', 5)  # daqiqa
    ad = next((a for a in data['ads'] if a['id'] == ad_id), None)
    if not ad:
        return
    # qaysi guruhga yuborish kerakligini aniqlaymiz
    target = DRIVER_GROUP_ID if ad.get('role') == 'driver' else PASSENGER_GROUP_ID
    if not target:
        target = GROUP_ID

    while True:
        # check stop
        job = data['jobs'].get(ad_id)
        if not job or job.get('stop'):
            break
        # send message (photo bo'lsa photo bilan)
        try:
            text = format_driver_ad(ad) if ad.get('role') == 'driver' else format_passenger_ad(ad)
            if ad.get('photo'):
                try:
                    await bot.send_photo(target, ad['photo'], caption=text, parse_mode=ParseMode.HTML)
                except Exception as e:
                    print("Photo send error (indef):", e)
                    await bot.send_message(target, text, parse_mode=ParseMode.HTML)
            else:
                await bot.send_message(target, text, parse_mode=ParseMode.HTML)
        except Exception as e:
            print("Send error:", e)
        await asyncio.sleep(int(interval * 60))
    # cleanup job
    data['jobs'].pop(ad_id, None)
    save_data()

# ======= /start handler =======
@dp.message_handler(commands=['start', 'help'])
async def cmd_start(message: types.Message):
    uid = message.from_user.id
    data['users'].setdefault(uid, {
        "role": None, "phone": None, "state": None, "draft_ad": None, "username": message.from_user.username or ""
    })
    save_data()
    await message.answer(
        "👋 Assalomu alaykum!\n\nKimsiz? Iltimos tanlang:",
        reply_markup=start_kb()
    )

# ======= Role selection =======
@dp.message_handler(lambda m: m.text in ["🚘 Haydovchiman", "🧍 Yo'lovchiman"])
async def choose_role(message: types.Message):
    uid = message.from_user.id
    role = 'driver' if message.text == "🚘 Haydovchiman" else 'passenger'
    u = data['users'].setdefault(uid, {})
    u['role'] = role
    u['state'] = None
    u['draft_ad'] = {}
    u['username'] = message.from_user.username or message.from_user.full_name or ""
    save_data()
    if role == 'driver':
        await message.answer("🚘 Haydovchi bo‘limiga xush kelibsiz.", reply_markup=driver_main_kb())
    else:
        await message.answer("🧍 Yo‘lovchi bo‘limiga xush kelibsiz.", reply_markup=passenger_main_kb())

# ======= Driver main buttons =======
@dp.message_handler(lambda m: m.text == "📣 E'lon berish" and data['users'].get(m.from_user.id,{}).get('role') == 'driver')
async def driver_create_start(message: types.Message):
    """
    Endi birinchi bosqich: Matn kiriting.
    keyin yo'nalish -> mashina -> rasm -> contact -> interval -> tasdiqlash
    """
    uid = message.from_user.id
    u = data['users'].setdefault(uid, {})
    u['state'] = 'driver_wait_text'
    u['draft_ad'] = {"role": "driver", "user_id": uid, "username": u.get('username','-')}
    save_data()
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("◀️ Orqaga"))
    await message.answer("✍️ Iltimos e'lon matnini yozing (misol: “Faqat nechta odam va qachon yurishingizni yozing!”):", reply_markup=kb)

@dp.message_handler(lambda m: m.text == "🗂 E'lonlar")
async def show_all_ads(message: types.Message):
    if not data['ads']:
        await message.answer("Hozircha e'lonlar yo'q.", reply_markup=driver_main_kb())
        return
    for ad in reversed(data['ads']):
        text = format_driver_ad(ad) if ad.get('role') == 'driver' else format_passenger_ad(ad)
        # agar rasm bo'lsa, uni yuboramiz
        if ad.get('photo'):
            try:
                await message.answer_photo(ad['photo'], caption=text, parse_mode=ParseMode.HTML, reply_markup=driver_main_kb())
            except:
                await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=driver_main_kb())
        else:
            await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=driver_main_kb())

@dp.message_handler(lambda m: m.text == "🧾 Mening e'lonlarim" and data['users'].get(m.from_user.id,{}).get('role') == 'driver')
async def my_ads(message: types.Message):
    uid = message.from_user.id
    my = [ad for ad in data['ads'] if ad['user_id'] == uid]
    if not my:
        await message.answer("Sizda e'lonlar yo'q.", reply_markup=driver_main_kb())
        return
    for ad in my:
        text = format_driver_ad(ad)
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.row(KeyboardButton("⏸ Habarni to'xtatish"), KeyboardButton("➕ Yangi habar"))
        kb.add(KeyboardButton("◀️ Asosiy menyu"))
        if ad.get('photo'):
            try:
                await message.answer_photo(ad['photo'], caption=text, parse_mode=ParseMode.HTML, reply_markup=kb)
            except:
                await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=kb)
        else:
            await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=kb)

# ======= Passenger main: E'lon berish =======
@dp.message_handler(lambda m: m.text == "🚕 E'lon berish" and data['users'].get(m.from_user.id,{}).get('role') == 'passenger')
async def passenger_create_start(message: types.Message):
    uid = message.from_user.id
    u = data['users'].setdefault(uid, {})
    u['state'] = 'passenger_wait_direction'
    u['draft_ad'] = {"role": "passenger", "user_id": uid, "username": u.get('username','-')}
    save_data()
    await message.answer("🛣 Yo'nalishni tanlang:", reply_markup=directions_kb())

# ======= Directions handler (for both roles) =======
@dp.message_handler(lambda m: m.text in DIRECTIONS + ["🟢 Boshqa"] and data['users'].get(m.from_user.id,{}).get('state') in ['driver_wait_direction', 'passenger_wait_direction'])
async def direction_chosen(message: types.Message):
    uid = message.from_user.id
    u = data['users'][uid]
    if message.text == "🟢 Boshqa":
        u['state'] = 'wait_custom_direction'
        save_data()
        await message.answer("Iltimos, yo'nalishni yozib yuboring (misol: Rishton → Toshkent):", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("◀️ Orqaga")))
        return
    # regular direction
    u['draft_ad']['direction'] = message.text
    # if passenger -> ask date/time and count; if driver -> ask car (but driver may already have text)
    if u['role'] == 'passenger':
        u['state'] = 'passenger_wait_date'
        save_data()
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.row(KeyboardButton("📅 Bugun"), KeyboardButton("📅 Ertaga"))
        kb.add(KeyboardButton("◀️ Orqaga"))
        await message.answer("📅 Kun tanlang:", reply_markup=kb)
    else:
        u['state'] = 'driver_wait_car'
        save_data()
        await message.answer("🚗 Mashina turini tanlang:", reply_markup=cars_kb())

@dp.message_handler(lambda m: data['users'].get(m.from_user.id,{}).get('state') == 'wait_custom_direction')
async def custom_direction(message: types.Message):
    uid = message.from_user.id
    text = message.text.strip()
    if text == "◀️ Orqaga":
        data['users'][uid]['state'] = None
        data['users'][uid]['draft_ad'] = {}
        save_data()
        await message.answer("🔙 Orqaga qaytdingiz.", reply_markup=start_kb())
        return
    data['users'][uid]['draft_ad']['direction'] = text
    role = data['users'][uid]['role']
    if role == 'passenger':
        data['users'][uid]['state'] = 'passenger_wait_date'
        save_data()
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.row(KeyboardButton("📅 Bugun"), KeyboardButton("📅 Ertaga"))
        kb.add(KeyboardButton("◀️ Orqaga"))
        await message.answer("📅 Kun tanlang:", reply_markup=kb)
    else:
        data['users'][uid]['state'] = 'driver_wait_car'
        save_data()
        await message.answer("🚗 Mashina turini tanlang:", reply_markup=cars_kb())

# ======= Passenger date/time/count flow =======
@dp.message_handler(lambda m: m.text in ["📅 Bugun", "📅 Ertaga"] and data['users'].get(m.from_user.id,{}).get('state') == 'passenger_wait_date')
async def passenger_date(message: types.Message):
    uid = message.from_user.id
    date = datetime.now().strftime("%Y-%m-%d") if message.text == "📅 Bugun" else (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    data['users'][uid]['draft_ad']['date'] = date
    data['users'][uid]['state'] = 'passenger_wait_time'
    save_data()
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    for h in range(6, 24, 2):
        kb.add(KeyboardButton(f"{h:02d}:00"))
    kb.add(KeyboardButton("◀️ Orqaga"))
    await message.answer("⏰ Soatni tanlang (yoki yozing HH:MM):", reply_markup=kb)

@dp.message_handler(lambda m: data['users'].get(m.from_user.id,{}).get('state') == 'passenger_wait_time')
async def passenger_time(message: types.Message):
    uid = message.from_user.id
    text = message.text.strip()
    if text == "◀️ Orqaga":
        data['users'][uid]['state'] = 'passenger_wait_date'
        save_data()
        await message.answer("📅 Kun tanlang:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).row(KeyboardButton("📅 Bugun"), KeyboardButton("📅 Ertaga")).add(KeyboardButton("◀️ Orqaga")))
        return
    data['users'][uid]['draft_ad']['time'] = text
    data['users'][uid]['state'] = 'passenger_wait_count'
    save_data()
    await message.answer("🧍 Necha kishi bor? (misol: 1 kishi, 2 kishi, Pochta bor)", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).row(KeyboardButton("👤 1 kishi"), KeyboardButton("👥 2 kishi")).row(KeyboardButton("📦 Pochta bor"), KeyboardButton("◀️ Orqaga")))

@dp.message_handler(lambda m: data['users'].get(m.from_user.id,{}).get('state') == 'passenger_wait_count')
async def passenger_count(message: types.Message):
    uid = message.from_user.id
    text = message.text.strip()
    if text == "◀️ Orqaga":
        data['users'][uid]['state'] = 'passenger_wait_time'
        save_data()
        await message.answer("⏰ Soatni tanlang:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("◀️ Orqaga")))
        return
    data['users'][uid]['draft_ad']['count'] = text
    data['users'][uid]['state'] = 'passenger_wait_contact'
    save_data()
    await message.answer("📞 Telefon raqamingizni yuboring (tugma orqali yuborish tavsiya etiladi):", reply_markup=contact_request_kb())

# ======= Driver flow: WAIT TEXT handler =======
@dp.message_handler(lambda m: data['users'].get(m.from_user.id,{}).get('state') == 'driver_wait_text')
async def driver_receive_text(message: types.Message):
    uid = message.from_user.id
    text = message.text.strip()
    if text == "◀️ Orqaga":
        data['users'][uid]['state'] = None
        data['users'][uid]['draft_ad'] = {}
        save_data()
        await message.answer("🔙 Orqaga qaytdingiz.", reply_markup=driver_main_kb())
        return
    # store text and ask for direction
    data['users'][uid]['draft_ad']['text'] = text
    data['users'][uid]['state'] = 'driver_wait_direction'
    save_data()
    await message.answer("🛣 Yo'nalishni tanlang (e'lon uchun):", reply_markup=directions_kb())

# ======= Car selection for driver =======
@dp.message_handler(lambda m: m.text in CARS + ["🟢 Boshqa"] and data['users'].get(m.from_user.id,{}).get('state') == 'driver_wait_car')
async def driver_car(message: types.Message):
    uid = message.from_user.id
    if message.text == "◀️ Orqaga":
        data['users'][uid]['state'] = None
        data['users'][uid]['draft_ad'] = {}
        save_data()
        await message.answer("🔙 Orqaga qaytdingiz.", reply_markup=driver_main_kb())
        return
    if message.text == "🟢 Boshqa":
        data['users'][uid]['state'] = 'driver_wait_custom_car'
        save_data()
        await message.answer("Iltimos o'zingizning mashina modelini yozing (masalan: Labo 2020 yoki O'z mashinam):", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("◀️ Orqaga")))
        return
    # regular car selected
    data['users'][uid]['draft_ad']['car'] = message.text
    # end of car selection: request optional photo and contact (state allows both)
    data['users'][uid]['state'] = 'driver_wait_contact_or_photo'
    save_data()
    await message.answer("📷 Endi mashina rasmi yuboring (majburiy emas). Rasm yuborib keyin telefonni tugma orqali yuborishingiz mumkin yoki tashlab o'tishingiz mumkin.", reply_markup=photo_or_skip_kb())

@dp.message_handler(lambda m: data['users'].get(m.from_user.id,{}).get('state') == 'driver_wait_custom_car')
async def driver_custom_car(message: types.Message):
    uid = message.from_user.id
    text = message.text.strip()
    if text == "◀️ Orqaga":
        data['users'][uid]['state'] = None
        data['users'][uid]['draft_ad'] = {}
        save_data()
        await message.answer("🔙 Orqaga qaytdingiz.", reply_markup=driver_main_kb())
        return
    data['users'][uid]['draft_ad']['car'] = text
    data['users'][uid]['state'] = 'driver_wait_contact_or_photo'
    save_data()
    await message.answer("📷 Endi mashina rasmi yuboring (majburiy emas). Rasm yuborib keyin telefonni tugma orqali yuborishingiz mumkin yoki tashlab o'tishingiz mumkin.", reply_markup=photo_or_skip_kb())

# ======= Contact handler (both passenger and driver) =======
@dp.message_handler(content_types=types.ContentType.CONTACT)
async def contact_received(message: types.Message):
    uid = message.from_user.id
    if uid not in data['users']:
        data['users'][uid] = {"role": None, "phone": None, "state": None, "draft_ad": {}, "username": message.from_user.username or ""}
    u = data['users'][uid]
    phone = message.contact.phone_number
    u['phone'] = phone
    u['draft_ad']['phone'] = phone
    save_data()

    state = u.get('state')
    # Driver case: if waiting for contact_or_photo, move to interval step after contact
    if state == 'driver_wait_contact_or_photo':
        u['state'] = 'driver_wait_interval'
        save_data()
        await message.answer("⏱ Endi xabar qanchalik tez yuborilsin? (daqiqada) — raqam kiriting. Masalan: 5  (har 5 daqiqada yuborilsin)", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("◀️ Orqaga")))
        return

    # Passenger case: after contact, ask for optional photo then preview
    if state == 'passenger_wait_contact':
        u['state'] = 'passenger_wait_photo'
        save_data()
        await message.answer("📷 Hoziroq rasm qo'shmoqchimisiz? Rasm yuboring yoki '⛔ Tashlab ketish' tugmasini bosing.", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("⛔ Tashlab ketish")).add(KeyboardButton("◀️ Asosiy menyu")))
        return

    # fallback: if contact in other states, just acknowledge
    await message.answer("Telefon qabul qilindi.", reply_markup=start_kb())

# ======= Photo handler (for optional car/photo upload) =======
@dp.message_handler(content_types=types.ContentType.PHOTO)
async def photo_received(message: types.Message):
    uid = message.from_user.id
    if uid not in data['users']:
        await message.answer("Iltimos avval /start ni bosing.", reply_markup=start_kb())
        return
    u = data['users'][uid]
    state = u.get('state')

    # pick highest quality photo file_id
    file_id = message.photo[-1].file_id

    # Driver: if waiting for contact_or_photo, store photo and keep waiting for contact (or let them move on)
    if state == 'driver_wait_contact_or_photo':
        u['draft_ad']['photo'] = file_id
        save_data()
        await message.answer("✅ Rasm olindi. Endi telefon raqamingizni tugma orqali yuboring yoki intervalni kiritish uchun avval telefonni yuboring.", reply_markup=contact_request_kb())
        return

    # Passenger: if waiting for photo, attach and go to preview
    if state == 'passenger_wait_photo':
        u['draft_ad']['photo'] = file_id
        # prepare ad preview and go to confirm
        u['state'] = 'passenger_confirm'
        save_data()
        d = u['draft_ad']
        ad_preview = {
            "id": data['next_ad_id'],
            "user_id": uid,
            "username": f"@{u.get('username')}" if u.get('username') else "",
            "phone": d.get('phone','-'),
            "direction": d.get('direction','-'),
            "count": d.get('count','-'),
            "date": d.get('date','-'),
            "time": d.get('time','-'),
            "created_at": int(time.time()),
            "role": "passenger",
            "photo": d.get('photo')
        }
        text = format_passenger_ad(ad_preview)
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.row(KeyboardButton("✅ Tasdiqlash"), KeyboardButton("🧹 Tozalash"))
        kb.add(KeyboardButton("◀️ Asosiy menyu"))
        try:
            await message.answer_photo(file_id, caption=text, parse_mode=ParseMode.HTML, reply_markup=kb)
        except:
            await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=kb)
        return

    # Other states: ignore or inform
    await message.answer("Hozir rasm qabul qilinmadi. Iltimos menyu orqali davom eting.", reply_markup=start_kb())

# ======= Interval input for driver (text numeric) =======
@dp.message_handler(lambda m: data['users'].get(m.from_user.id,{}).get('state') == 'driver_wait_interval')
async def driver_interval_input(message: types.Message):
    uid = message.from_user.id
    text = message.text.strip()
    if text == "◀️ Orqaga":
        data['users'][uid]['state'] = 'driver_wait_contact_or_photo'
        save_data()
        await message.answer("📞 Telefon raqamingizni yuboring (tugma orqali tavsiya etiladi) yoki rasm yuboring:", reply_markup=photo_or_skip_kb())
        return
    # expect a number (minutes)
    if not text.isdigit():
        await message.answer("Iltimos faqat raqam kiriting (daqiqada). Masalan: 5")
        return
    minutes = int(text)
    data['users'][uid]['draft_ad']['interval'] = minutes
    data['users'][uid]['state'] = 'driver_confirm'
    save_data()
    # show preview and confirm/clear
    d = data['users'][uid]['draft_ad']
    if 'date' not in d:
        d['date'] = datetime.now().strftime("%Y-%m-%d")
    preview = {
        "id": data['next_ad_id'],
        "user_id": uid,
        "username": f"@{data['users'][uid].get('username','')}",
        "phone": d.get('phone','-'),
        "direction": d.get('direction','-'),
        "car": d.get('car','-'),
        "date": d.get('date','-'),
        "time": d.get('time','-'),
        "text": d.get('text','-'),
        "created_at": int(time.time()),
        "role": "driver",
        "photo": d.get('photo')
    }
    text = format_driver_ad(preview) + f"\n\n<i>Interval: {minutes} daqiqa (to'xtamaguncha yuboriladi)</i>"
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("✅ Tasdiqlash"), KeyboardButton("🧹 Tozalash"))
    kb.add(KeyboardButton("◀️ Asosiy menyu"))
    # send preview with possible photo
    if preview.get('photo'):
        try:
            await message.answer_photo(preview['photo'], caption=text, parse_mode=ParseMode.HTML, reply_markup=kb)
        except:
            await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    else:
        await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=kb)

# ======= Confirmations =======
@dp.message_handler(lambda m: m.text == "✅ Tasdiqlash")
async def confirm_handler(message: types.Message):
    uid = message.from_user.id
    u = data['users'].get(uid, {})
    state = u.get('state')
    draft = u.get('draft_ad') or {}

    if state == 'passenger_confirm':
        # finalize passenger ad -> single send
        ad = {
            "id": data['next_ad_id'],
            "user_id": uid,
            "username": draft.get('username', f"@{u.get('username','')}"),
            "phone": draft.get('phone','-'),
            "direction": draft.get('direction','-'),
            "count": draft.get('count','-'),
            "date": draft.get('date','-'),
            "time": draft.get('time','-'),
            "created_at": int(time.time()),
            "role": "passenger",
            "photo": draft.get('photo')  # may be None
        }
        data['ads'].append(ad)
        data['next_ad_id'] += 1
        # send once to passenger group (fallback to GROUP_ID)
        target = PASSENGER_GROUP_ID or GROUP_ID
        try:
            if ad.get('photo'):
                await bot.send_photo(target, ad['photo'], caption=format_passenger_ad(ad), parse_mode=ParseMode.HTML)
            else:
                await bot.send_message(target, format_passenger_ad(ad), parse_mode=ParseMode.HTML)
        except Exception as e:
            print("Send error:", e)
        # clear
        u['draft_ad'] = {}
        u['state'] = None
        save_data()
        await message.answer("✅ E'lon yuborildi.", reply_markup=passenger_main_kb())
        return

    if state == 'driver_confirm':
        # finalize driver ad -> start indefinite sending
        ad = {
            "id": data['next_ad_id'],
            "user_id": uid,
            "username": draft.get('username', f"@{u.get('username','')}"),
            "phone": draft.get('phone','-'),
            "direction": draft.get('direction','-'),
            "car": draft.get('car','-'),
            "date": draft.get('date', datetime.now().strftime("%Y-%m-%d")),
            "time": draft.get('time','-'),
            "text": draft.get('text','-'),
            "created_at": int(time.time()),
            "role": "driver",
            "photo": draft.get('photo')
        }
        data['ads'].append(ad)
        data['next_ad_id'] += 1
        save_data()
        # schedule task
        ad_id = ad['id']
        interval = draft.get('interval', 5)
        data['jobs'][ad_id] = {"task": None, "stop": False, "interval": interval, "user_id": uid}
        # create task
        task = asyncio.create_task(send_indefinitely(ad_id))
        data['jobs'][ad_id]['task'] = task
        save_data()
        # reply with controls
        await message.answer("✅ E'lon yaratildi va yuborish boshlandi.", reply_markup=post_control_kb())
        # clear draft and state
        u['draft_ad'] = {}
        u['state'] = None
        save_data()
        return

    # generic fallback
    await message.answer("Hech qanday doimiy jarayon topilmadi yoki siz tasdiqlash uchun kerakli bosqichda emassiz.", reply_markup=start_kb())

@dp.message_handler(lambda m: m.text == "🧹 Tozalash")
async def clear_handler(message: types.Message):
    uid = message.from_user.id
    u = data['users'].setdefault(uid, {})
    u['draft_ad'] = {}
    u['state'] = None
    save_data()
    await message.answer("Ma'lumotlar tozalandi.", reply_markup=start_kb())

# ======= Post controls: stop or new ad =======
@dp.message_handler(lambda m: m.text == "⏸ Habarni to'xtatish")
async def stop_handler(message: types.Message):
    uid = message.from_user.id
    stopped = 0
    # stop all jobs started by this user
    for ad in list(data['ads']):
        if ad.get('user_id') == uid:
            job = data['jobs'].get(ad['id'])
            if job:
                job['stop'] = True
                t = job.get('task')
                try:
                    if t:
                        t.cancel()
                except:
                    pass
                data['jobs'].pop(ad['id'], None)
                stopped += 1
    save_data()
    await message.answer(f"{stopped} ta yuborish to'xtatildi.", reply_markup=start_kb())

@dp.message_handler(lambda m: m.text == "➕ Yangi habar")
async def new_ad_handler(message: types.Message):
    uid = message.from_user.id
    # start new ad flow (haydovchi uchun: boshlang'ich - MATN)
    data['users'].setdefault(uid, {})['state'] = 'driver_wait_text'
    data['users'][uid]['draft_ad'] = {"role": "driver", "user_id": uid, "username": data['users'][uid].get('username','-')}
    save_data()
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("◀️ Orqaga"))
    await message.answer("✍️ Iltimos e'lon matnini yozing:", reply_markup=kb)

# ======= Show all ads (global) =======
@dp.message_handler(lambda m: (m.text == "🗂 E'lonlar" and data['users'].get(m.from_user.id,{}).get('role') == 'passenger') or m.text == "🗂 E'lonlar'")
async def show_all_ads_button(message: types.Message):
    if not data['ads']:
        await message.answer("Hozircha e'lonlar yo'q.", reply_markup=start_kb())
        return
    for ad in reversed(data['ads']):
        text = format_driver_ad(ad) if ad.get('role') == 'driver' else format_passenger_ad(ad)
        if ad.get('photo'):
            try:
                await message.answer_photo(ad['photo'], caption=text, parse_mode=ParseMode.HTML, reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("◀️ Asosiy menyu")))
            except:
                await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("◀️ Asosiy menyu")))
        else:
            await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("◀️ Asosiy menyu")))

# ======= Catch-all text handler for misc states (time input, phone typed manually, driver text fallback, etc.) =======
@dp.message_handler()
async def fallback_handler(message: types.Message):
    uid = message.from_user.id
    u = data['users'].get(uid)
    text = message.text.strip()
    # if user typing while in passenger_wait_time (alternative path)
    if u:
        state = u.get('state')
        # passenger alternative time input
        if state == 'passenger_wait_time':
            # accept as time
            u['draft_ad']['time'] = text
            u['state'] = 'passenger_wait_count'
            save_data()
            await message.answer("🧍 Necha kishi bor? (misol: 1 kishi, 2 kishi, Pochta bor)", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).row(KeyboardButton("👤 1 kishi"), KeyboardButton("👥 2 kishi")).row(KeyboardButton("📦 Pochta bor"), KeyboardButton("◀️ Orqaga")))
            return
        if state == 'passenger_wait_count':
            # store count
            u['draft_ad']['count'] = text
            u['state'] = 'passenger_wait_contact'
            save_data()
            await message.answer("📞 Telefon raqamingizni yuboring (tugma orqali yuborish tavsiya etiladi):", reply_markup=contact_request_kb())
            return
        if state == 'driver_wait_contact':
            # user typed phone manually (not via contact) -> this case may be rare because we use contact button earlier
            u['draft_ad']['phone'] = text
            u['state'] = 'driver_wait_interval'
            save_data()
            await message.answer("⏱ Iltimos interval (daqiqada) kiriting. Misol: 5", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("◀️ Orqaga")))
            return
        if state == 'driver_wait_contact_or_photo':
            # user typed phone manually here (if not using contact button)
            if text == "⛔ Tashlab ketish":
                # user chooses to skip photo and should press contact button or type phone
                u['state'] = 'driver_wait_contact_or_photo'
                save_data()
                await message.answer("Rasm o'tkazib yuborildi. Iltimos telefon raqamingizni tugma orqali yuboring yoki yozing.", reply_markup=contact_request_kb())
                return
            # if they typed a phone number manually:
            if text.replace("+","").replace(" ","").isdigit():
                u['draft_ad']['phone'] = text
                u['state'] = 'driver_wait_interval'
                save_data()
                await message.answer("⏱ Iltimos interval (daqiqada) kiriting. Misol: 5", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("◀️ Orqaga")))
                return
            # otherwise prompt
            await message.answer("Iltimos telefon raqamni tugma orqali yuboring yoki rasm yuboring yoki '⛔ Tashlab ketish' bosing.", reply_markup=photo_or_skip_kb())
            return
        if state == 'driver_wait_interval':
            # typed interval (duplicate handling for fallback)
            if not text.isdigit():
                await message.answer("Iltimos faqat raqam kiriting (daqiqada). Masalan: 5")
                return
            minutes = int(text)
            u['draft_ad']['interval'] = minutes
            u['state'] = 'driver_confirm'
            save_data()
            # preview
            d = u['draft_ad']
            preview = {
                "id": data['next_ad_id'],
                "user_id": uid,
                "username": f"@{u.get('username','')}",
                "phone": d.get('phone','-'),
                "direction": d.get('direction','-'),
                "car": d.get('car','-'),
                "date": d.get('date', datetime.now().strftime("%Y-%m-%d")),
                "time": d.get('time','-'),
                "text": d.get('text','-'),
                "created_at": int(time.time()),
                "role": "driver",
                "photo": d.get('photo')
            }
            text_msg = format_driver_ad(preview) + f"\n\n<i>Interval: {minutes} daqiqa (to'xtamaguncha yuboriladi)</i>"
            kb = ReplyKeyboardMarkup(resize_keyboard=True)
            kb.row(KeyboardButton("✅ Tasdiqlash"), KeyboardButton("🧹 Tozalash"))
            kb.add(KeyboardButton("◀️ Asosiy menyu"))
            if preview.get('photo'):
                try:
                    await message.answer_photo(preview['photo'], caption=text_msg, parse_mode=ParseMode.HTML, reply_markup=kb)
                except:
                    await message.answer(text_msg, parse_mode=ParseMode.HTML, reply_markup=kb)
            else:
                await message.answer(text_msg, parse_mode=ParseMode.HTML, reply_markup=kb)
            return
        if state == 'driver_wait_text':
            # fallback: user typed text but didn't trigger handler? (redundant but safe)
            data['users'][uid]['draft_ad']['text'] = text
            data['users'][uid]['state'] = 'driver_wait_direction'
            save_data()
            await message.answer("🛣 Yo'nalishni tanlang:", reply_markup=directions_kb())
            return
        if state == 'wait_custom_direction':
            # handled above; redundant
            return
        if state == 'passenger_wait_photo':
            if text == "⛔ Tashlab ketish":
                # go to preview without photo
                u['state'] = 'passenger_confirm'
                save_data()
                d = u['draft_ad']
                ad_preview = {
                    "id": data['next_ad_id'],
                    "user_id": uid,
                    "username": f"@{u.get('username')}" if u.get('username') else "",
                    "phone": d.get('phone','-'),
                    "direction": d.get('direction','-'),
                    "count": d.get('count','-'),
                    "date": d.get('date','-'),
                    "time": d.get('time','-'),
                    "created_at": int(time.time()),
                    "role": "passenger"
                }
                text2 = format_passenger_ad(ad_preview)
                kb = ReplyKeyboardMarkup(resize_keyboard=True)
                kb.row(KeyboardButton("✅ Tasdiqlash"), KeyboardButton("🧹 Tozalash"))
                kb.add(KeyboardButton("◀️ Asosiy menyu"))
                await message.answer(text2, parse_mode=ParseMode.HTML, reply_markup=kb)
                return
            # otherwise remind
            await message.answer("Rasm yuboring yoki '⛔ Tashlab ketish' tugmasini bosing.", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("⛔ Tashlab ketish")))
            return
    # default fallback
    await message.answer("Iltimos menyudan tanlang yoki /start ni bosing.", reply_markup=start_kb())

# ======= Shutdown hook =======
async def on_shutdown(dp):
    save_data()
    # cancel running tasks
    for job in list(data.get('jobs', {}).values()):
        t = job.get('task')
        try:
            if t:
                t.cancel()
        except:
            pass
    await bot.close()

if __name__ == "__main__":
    print("🚕 Taxi bot ishga tushmoqda...")
    executor.start_polling(dp, skip_updates=True, on_shutdown=on_shutdown)
