# taxi_bot.py
import asyncio
import json
import time
from pathlib import Path
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton, ParseMode,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.utils import executor

# ================== SOZLAMALAR ==================
TOKEN = "8212255968:AAETRL91puhUESsCP7eFKm7pE51tKgm6SQo"  # <-- bot tokenni shu yerga qo'ying

# ADMINLAR (admin user_id lar)
ADMINS = [6731395876, 6302873072]

# Guruh / kanal ID lar (o'zgartiring)
DRIVER_GROUP_ID = -1001499767213       # haydovchi e'lonlari joylanadigan guruh/channel
PASSENGER_GROUP_ID = -1002774668004    # yo'lovchi e'lonlari joylanadigan guruh/channel

DATA_FILE = Path("taxi_data.json")
# =================================================

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# in-memory data (saqlanadi faylga)
data = {
    "users": {},            # uid -> {role, phone, state, draft_ad, username}
    "ads": [],              # list of ads
    "next_ad_id": 1,
    "jobs": {},             # ad_id -> {task, stop_flag, user_id, interval}
    "approved_drivers": []  # list of user_id larga haydovchi huquqi berilgan
}

BOT_LINK = "https://t.me/RishtonBuvaydaBogdod_bot"  # ishga tushganda to'ldiriladi (https://t.me/<bot_username>)

# ======= yuklash/saqlash =======
def load_data():
    if DATA_FILE.exists():
        try:
            d = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            # merge keys safely
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
        f"🚘 <b>Haydovchi e'lon #{ad['id']}</b>\n\n"
        f"{ad.get('text','')}\n\n"
        f"🛣 <b>Yo‘nalish:</b> {ad.get('direction','-')}\n\n"
        f"📞 <b>Telefon:</b> {ad.get('phone','-')}\n\n"
        f"🚗 <b>Mashina:</b> {ad.get('car','-')}\n\n"
        f"🕒 <b>Kun:</b> {ad.get('date','-')}\n\n"
        f"🆔 <b>UserID:</b> {ad.get('user_id','-')}\n"
    )
    return t

# ======= helper: build "Zakaz berish" inline KB =======
def zakaz_kb():
    kb = InlineKeyboardMarkup()
    if BOT_LINK:
        kb.add(InlineKeyboardButton("📝 Zakaz berish", url=BOT_LINK))
    return kb

# ======= sending task (haydovchi e'lonlarini cheksiz yuborish) =======
async def send_indefinitely(ad_id):
    """Adni interval bo'yicha yuboradi; to'xtatish flag tekshiriladi."""
    job = data['jobs'].get(str(ad_id))
    if not job:
        return
    interval = int(job.get('interval', 5))  # daqiqa
    # find ad
    ad = next((a for a in data['ads'] if a['id'] == ad_id), None)
    if not ad:
        return
    target = DRIVER_GROUP_ID if ad.get('role') == 'driver' else PASSENGER_GROUP_ID
    # prepare kb
    kb = zakaz_kb()
    while True:
        job = data['jobs'].get(str(ad_id))
        if not job or job.get('stop'):
            break
        try:
            text = format_driver_ad(ad) if ad.get('role') == 'driver' else format_passenger_ad(ad)
            if ad.get('photo'):
                try:
                    await bot.send_photo(target, ad['photo'], caption=text, parse_mode=ParseMode.HTML, reply_markup=kb)
                except Exception:
                    await bot.send_message(target, text, parse_mode=ParseMode.HTML, reply_markup=kb)
            else:
                await bot.send_message(target, text, parse_mode=ParseMode.HTML, reply_markup=kb)
        except Exception as e:
            print("Send error:", e)
        await asyncio.sleep(interval * 60)
    # cleanup
    data['jobs'].pop(str(ad_id), None)
    save_data()

# ======= startup hook =======
async def on_startup(dp):
    global BOT_LINK
    me = await bot.get_me()
    BOT_LINK = f"https://t.me/{me.username}"
    print("Bot username:", me.username)
    # restore tasks for running jobs (if bot restarted)
    for adid, job in list(data.get('jobs', {}).items()):
        # create tasks again if not present
        if not job.get('task'):
            task = asyncio.create_task(send_indefinitely(int(adid)))
            data['jobs'][adid]['task'] = task

# ======= /start handler =======
@dp.message_handler(commands=['start', 'help'])
async def cmd_start(message: types.Message):
    uid = message.from_user.id
    data['users'].setdefault(str(uid), {
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
    u = data['users'].setdefault(str(uid), {})
    u['role'] = role
    u['state'] = None
    u['draft_ad'] = {}
    u['username'] = message.from_user.username or message.from_user.full_name or ""
    save_data()

    # If driver selected -> check if allowed (admin or approved)
    if role == 'driver':
        if uid in ADMINS or uid in data.get('approved_drivers', []):
            await message.answer("🚘 Haydovchi bo‘limiga xush kelibsiz.", reply_markup=driver_main_kb())
            return
        # else: not approved -> provide option to request ruxsat and contact admins
        kb = InlineKeyboardMarkup()
        # add contact buttons for admins (tg deep links)
        for a in ADMINS:
            kb.add(InlineKeyboardButton(f"Adminga yozish ({a})", url=f"tg://user?id={a}"))
        # add request button (user requests admin approval)
        kb.add(InlineKeyboardButton("Soʻrov yuborish — Haydovchi bo‘lish", callback_data=f"req_driver:{uid}"))
        await message.answer(
            "🔒 Haydovchi bo‘limi faqat admin tomonidan ruxsat olingan foydalanuvchilarga koʻrinadi.\n"
            "Agar siz haydovchi bo‘lishni xohlasangiz, adminlarga murojaat qiling yoki quyidagi tugma orqali so‘rov yuboring.",
            reply_markup=kb
        )
        return

    # passenger
    await message.answer("🧍 Yo‘lovchi bo‘limiga xush kelibsiz.", reply_markup=passenger_main_kb())

# ======= Callback: user requests driver role =======
@dp.callback_query_handler(lambda c: c.data and c.data.startswith("req_driver:"))
async def handle_request_driver(cb: types.CallbackQuery):
    await cb.answer()  # acknowledge
    data_user = cb.data.split(":", 1)[1]
    try:
        req_uid = int(data_user)
    except:
        await cb.message.answer("So'rov ID noto'g'ri.")
        return
    # notify admins with approve/reject inline buttons
    for admin in ADMINS:
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve:{req_uid}"),
               InlineKeyboardButton("❌ Rad etish", callback_data=f"reject:{req_uid}"))
        kb.add(InlineKeyboardButton("Profilni ochish", url=f"tg://user?id={req_uid}"))
        try:
            await bot.send_message(admin,
                f"📩 Foydalanuvchi @{(data['users'].get(str(req_uid),{}).get('username') or '')} ({req_uid}) haydovchi bo‘lishga so‘rov yubordi.\n"
                "Tasdiqlash yoki rad etish uchun tugmalardan foydalaning.",
                reply_markup=kb
            )
        except Exception as e:
            print("Admin notify error:", e)
    await cb.message.answer("✅ Soʻrovingiz adminlarga yuborildi. Iltimos kuting — adminlar sizni ko'rib chiqadi.")

# ======= Callback: admin approves/rejects request =======
@dp.callback_query_handler(lambda c: c.data and (c.data.startswith("approve:") or c.data.startswith("reject:")))
async def handle_approve_reject(cb: types.CallbackQuery):
    await cb.answer()  # ack
    actor = cb.from_user.id
    if actor not in ADMINS:
        await cb.message.answer("Siz admin emassiz.")
        return
    action, uidstr = cb.data.split(":", 1)
    try:
        uid = int(uidstr)
    except:
        await cb.message.answer("Noto'g'ri ID.")
        return

    if action == "approve":
        if uid not in data.get('approved_drivers', []):
            data.setdefault('approved_drivers', []).append(uid)
            save_data()
        # notify user
        try:
            await bot.send_message(uid, "✅ Sizga admin tomonidan haydovchi huquqi berildi. /start orqali tekshiring.")
        except Exception:
            pass
        await cb.message.answer(f"{uid} tasdiqlandi.")
    else:  # reject
        try:
            await bot.send_message(uid, "❌ Sizning haydovchi bo‘lish so‘rovingiz admin tomonidan rad etildi.")
        except Exception:
            pass
        await cb.message.answer(f"{uid} rad etildi.")

# ======= Admin command: /approve <id> yoki /reject <id> =======
@dp.message_handler(commands=['approve'])
async def admin_approve_cmd(message: types.Message):
    actor = message.from_user.id
    if actor not in ADMINS:
        await message.answer("Bu buyruq faqat adminlarga mo'ljallangan.")
        return
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("Foydalanish: /approve <user_id>")
        return
    uid = int(parts[1])
    if uid not in data.get('approved_drivers', []):
        data.setdefault('approved_drivers', []).append(uid)
        save_data()
    try:
        await bot.send_message(uid, "✅ Sizga admin tomonidan haydovchi huquqi berildi. /start orqali tekshiring.")
    except Exception:
        pass
    await message.answer(f"{uid} tasdiqlandi.")

@dp.message_handler(commands=['reject'])
async def admin_reject_cmd(message: types.Message):
    actor = message.from_user.id
    if actor not in ADMINS:
        await message.answer("Bu buyruq faqat adminlarga mo'ljallangan.")
        return
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("Foydalanish: /reject <user_id>")
        return
    uid = int(parts[1])
    try:
        await bot.send_message(uid, "❌ Sizning haydovchi bo‘lish so‘rovingiz admin tomonidan rad etildi.")
    except Exception:
        pass
    await message.answer(f"{uid} rad etildi.")

# ======= Driver main buttons =======
@dp.message_handler(lambda m: m.text == "📣 E'lon berish" and data['users'].get(str(m.from_user.id),{}).get('role') == 'driver')
async def driver_create_start(message: types.Message):
    uid = message.from_user.id
    # check permission
    if uid not in ADMINS and uid not in data.get('approved_drivers', []):
        # no access
        kb = InlineKeyboardMarkup()
        for a in ADMINS:
            kb.add(InlineKeyboardButton(f"Adminga yozish ({a})", url=f"tg://user?id={a}"))
        await message.answer("🔒 Sizda haydovchi bo‘limiga kirish huquqi yo‘q. Adminlarga murojaat qiling.", reply_markup=kb)
        return

    u = data['users'].setdefault(str(uid), {})
    u['state'] = 'driver_wait_text'
    u['draft_ad'] = {"role": "driver", "user_id": uid, "username": u.get('username','-')}
    save_data()
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("◀️ Orqaga"))
    await message.answer("✍️ Iltimos e'lon matnini yozing (misol: “Faqat nechta odam va qachon yurishingizni yozing!”):", reply_markup=kb)

@dp.message_handler(lambda m: m.text == "🗂 E'lonlar")
async def show_all_ads(message: types.Message):
    if not data['ads']:
        await message.answer("Hozircha e'lonlar yo'q.", reply_markup=start_kb())
        return
    for ad in reversed(data['ads']):
        text = format_driver_ad(ad) if ad.get('role') == 'driver' else format_passenger_ad(ad)
        # attach zakaz button only for driver ads
        kb = zakaz_kb() if ad.get('role') == 'driver' else None
        if ad.get('photo'):
            try:
                await message.answer_photo(ad['photo'], caption=text, parse_mode=ParseMode.HTML, reply_markup=kb)
            except:
                await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=kb)
        else:
            await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=kb)

@dp.message_handler(lambda m: m.text == "🧾 Mening e'lonlarim" and data['users'].get(str(m.from_user.id),{}).get('role') == 'driver')
async def my_ads(message: types.Message):
    uid = message.from_user.id
    my = [ad for ad in data['ads'] if ad['user_id'] == uid]
    if not my:
        await message.answer("Sizda e'lonlar yo'q.", reply_markup=driver_main_kb())
        return
    for ad in my:
        text = format_driver_ad(ad)
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("⏸ To'xtatish", callback_data=f"stop_ad:{ad['id']}"))
        kb.add(InlineKeyboardButton("📝 Zakaz berish", url=BOT_LINK if BOT_LINK else "https://t.me/"))
        if ad.get('photo'):
            try:
                await message.answer_photo(ad['photo'], caption=text, parse_mode=ParseMode.HTML, reply_markup=kb)
            except:
                await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=kb)
        else:
            await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=kb)

# ======= Passenger main: E'lon berish =======
@dp.message_handler(lambda m: m.text == "🚕 E'lon berish" and data['users'].get(str(m.from_user.id),{}).get('role') == 'passenger')
async def passenger_create_start(message: types.Message):
    uid = message.from_user.id
    u = data['users'].setdefault(str(uid), {})
    u['state'] = 'passenger_wait_direction'
    u['draft_ad'] = {"role": "passenger", "user_id": uid, "username": u.get('username','-')}
    save_data()
    await message.answer("🛣 Yo'nalishni tanlang:", reply_markup=directions_kb())

# ======= Directions handler (for both roles) =======
@dp.message_handler(lambda m: m.text in DIRECTIONS + ["🟢 Boshqa"] and data['users'].get(str(m.from_user.id),{}).get('state') in ['driver_wait_direction', 'passenger_wait_direction'])
async def direction_chosen(message: types.Message):
    uid = message.from_user.id
    u = data['users'][str(uid)]
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

@dp.message_handler(lambda m: data['users'].get(str(m.from_user.id),{}).get('state') == 'wait_custom_direction')
async def custom_direction(message: types.Message):
    uid = message.from_user.id
    text = message.text.strip()
    if text == "◀️ Orqaga":
        data['users'][str(uid)]['state'] = None
        data['users'][str(uid)]['draft_ad'] = {}
        save_data()
        await message.answer("🔙 Orqaga qaytdingiz.", reply_markup=start_kb())
        return
    data['users'][str(uid)]['draft_ad']['direction'] = text
    role = data['users'][str(uid)]['role']
    if role == 'passenger':
        data['users'][str(uid)]['state'] = 'passenger_wait_date'
        save_data()
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.row(KeyboardButton("📅 Bugun"), KeyboardButton("📅 Ertaga"))
        kb.add(KeyboardButton("◀️ Orqaga"))
        await message.answer("📅 Kun tanlang:", reply_markup=kb)
    else:
        data['users'][str(uid)]['state'] = 'driver_wait_car'
        save_data()
        await message.answer("🚗 Mashina turini tanlang:", reply_markup=cars_kb())

# ======= Passenger date/time/count flow (no photo requested) =======
@dp.message_handler(lambda m: m.text in ["📅 Bugun", "📅 Ertaga"] and data['users'].get(str(m.from_user.id),{}).get('state') == 'passenger_wait_date')
async def passenger_date(message: types.Message):
    uid = message.from_user.id
    date = datetime.now().strftime("%Y-%m-%d") if message.text == "📅 Bugun" else (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
    data['users'][str(uid)]['draft_ad']['date'] = date
    data['users'][str(uid)]['state'] = 'passenger_wait_time'
    save_data()
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    for h in range(6, 24, 2):
        kb.add(KeyboardButton(f"{h:02d}:00"))
    kb.add(KeyboardButton("◀️ Orqaga"))
    await message.answer("⏰ Soatni tanlang (yoki yozing HH:MM):", reply_markup=kb)

@dp.message_handler(lambda m: data['users'].get(str(m.from_user.id),{}).get('state') == 'passenger_wait_time')
async def passenger_time(message: types.Message):
    uid = message.from_user.id
    text = message.text.strip()
    if text == "◀️ Orqaga":
        data['users'][str(uid)]['state'] = 'passenger_wait_date'
        save_data()
        await message.answer("📅 Kun tanlang:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).row(KeyboardButton("📅 Bugun"), KeyboardButton("📅 Ertaga")).add(KeyboardButton("◀️ Orqaga")))
        return
    data['users'][str(uid)]['draft_ad']['time'] = text
    data['users'][str(uid)]['state'] = 'passenger_wait_count'
    save_data()
    await message.answer("🧍 Necha kishi bor? (misol: 1 kishi, 2 kishi, 3 kishi, 4 kishi, Pochta bor)", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).row(KeyboardButton("👤 1 kishi"), KeyboardButton("👥 2 kishi")).row(KeyboardButton("📦 Pochta bor"), KeyboardButton("◀️ Orqaga")))

@dp.message_handler(lambda m: data['users'].get(str(m.from_user.id),{}).get('state') == 'passenger_wait_count')
async def passenger_count(message: types.Message):
    uid = message.from_user.id
    text = message.text.strip()
    if text == "◀️ Orqaga":
        data['users'][str(uid)]['state'] = 'passenger_wait_time'
        save_data()
        await message.answer("⏰ Soatni tanlang:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("◀️ Orqaga")))
        return
    data['users'][str(uid)]['draft_ad']['count'] = text
    data['users'][str(uid)]['state'] = 'passenger_wait_contact'
    save_data()
    # now ask contact; after contact we will immediately show preview (no photo for passenger)
    await message.answer("📞 Telefon raqamingizni yuboring (tugma orqali yuborish tavsiya etiladi):", reply_markup=contact_request_kb())

# ======= Driver flow handlers (text, car, optional photo, interval) =======
@dp.message_handler(lambda m: data['users'].get(str(m.from_user.id),{}).get('state') == 'driver_wait_text')
async def driver_receive_text(message: types.Message):
    uid = message.from_user.id
    text = message.text.strip()
    if text == "◀️ Orqaga":
        data['users'][str(uid)]['state'] = None
        data['users'][str(uid)]['draft_ad'] = {}
        save_data()
        await message.answer("🔙 Orqaga qaytdingiz.", reply_markup=driver_main_kb())
        return
    data['users'][str(uid)]['draft_ad']['text'] = text
    data['users'][str(uid)]['state'] = 'driver_wait_direction'
    save_data()
    await message.answer("🛣 Yo'nalishni tanlang (e'lon uchun):", reply_markup=directions_kb())

@dp.message_handler(lambda m: m.text in CARS + ["🟢 Boshqa"] and data['users'].get(str(m.from_user.id),{}).get('state') == 'driver_wait_car')
async def driver_car(message: types.Message):
    uid = message.from_user.id
    if message.text == "◀️ Orqaga":
        data['users'][str(uid)]['state'] = None
        data['users'][str(uid)]['draft_ad'] = {}
        save_data()
        await message.answer("🔙 Orqaga qaytdingiz.", reply_markup=driver_main_kb())
        return
    if message.text == "🟢 Boshqa":
        data['users'][str(uid)]['state'] = 'driver_wait_custom_car'
        save_data()
        await message.answer("Iltimos o'zingizning mashina modelini yozing:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add(KeyboardButton("◀️ Orqaga")))
        return
    # regular car selected
    data['users'][str(uid)]['draft_ad']['car'] = message.text
    # request optional photo and contact (state allows both)
    data['users'][str(uid)]['state'] = 'driver_wait_contact_or_photo'
    save_data()
    await message.answer("📷 Endi mashina rasmi yuboring (majburiy emas). Rasm yuborib keyin telefonni tugma orqali yuborishingiz mumkin yoki tashlab o'tishingiz mumkin.", reply_markup=photo_or_skip_kb())

@dp.message_handler(lambda m: data['users'].get(str(m.from_user.id),{}).get('state') == 'driver_wait_custom_car')
async def driver_custom_car(message: types.Message):
    uid = message.from_user.id
    text = message.text.strip()
    if text == "◀️ Orqaga":
        data['users'][str(uid)]['state'] = None
        data['users'][str(uid)]['draft_ad'] = {}
        save_data()
        await message.answer("🔙 Orqaga qaytdingiz.", reply_markup=driver_main_kb())
        return
    data['users'][str(uid)]['draft_ad']['car'] = text
    data['users'][str(uid)]['state'] = 'driver_wait_contact_or_photo'
    save_data()
    await message.answer("📷 Endi mashina rasmi yuboring (majburiy emas).", reply_markup=photo_or_skip_kb())

# ======= Contact handler (both passenger and driver) =======
@dp.message_handler(content_types=types.ContentType.CONTACT)
async def contact_received(message: types.Message):
    uid = message.from_user.id
    if str(uid) not in data['users']:
        data['users'][str(uid)] = {"role": None, "phone": None, "state": None, "draft_ad": {}, "username": message.from_user.username or ""}
    u = data['users'][str(uid)]
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

    # Passenger case: after contact, directly preview (no photo asked for passenger)
    if state == 'passenger_wait_contact':
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
        text = format_passenger_ad(ad_preview)
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.row(KeyboardButton("✅ Tasdiqlash"), KeyboardButton("🧹 Tozalash"))
        kb.add(KeyboardButton("◀️ Asosiy menyu"))
        await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=kb)
        return

    # fallback
    await message.answer("Telefon qabul qilindi.", reply_markup=start_kb())

# ======= Photo handler (driver optional photo) =======
@dp.message_handler(content_types=types.ContentType.PHOTO)
async def photo_received(message: types.Message):
    uid = message.from_user.id
    if str(uid) not in data['users']:
        await message.answer("Iltimos avval /start ni bosing.", reply_markup=start_kb())
        return
    u = data['users'][str(uid)]
    state = u.get('state')

    # pick highest quality photo file_id
    file_id = message.photo[-1].file_id

    # Driver: if waiting for contact_or_photo, store photo and keep waiting for contact (or let them move on)
    if state == 'driver_wait_contact_or_photo':
        u['draft_ad']['photo'] = file_id
        save_data()
        await message.answer("✅ Rasm olindi. Endi telefon raqamingizni tugma orqali yuborishingiz yoki interval kiritishingiz mumkin.", reply_markup=contact_request_kb())
        return

    # Other states: ignore or inform
    await message.answer("Hozir rasm qabul qilinmadi. Iltimos menyu orqali davom eting.", reply_markup=start_kb())

# ======= Interval input for driver (text numeric) =======
@dp.message_handler(lambda m: data['users'].get(str(m.from_user.id),{}).get('state') == 'driver_wait_interval')
async def driver_interval_input(message: types.Message):
    uid = message.from_user.id
    text = message.text.strip()
    if text == "◀️ Orqaga":
        data['users'][str(uid)]['state'] = 'driver_wait_contact_or_photo'
        save_data()
        await message.answer("📞 Telefon raqamingizni yuboring (tugma orqali tavsiya etiladi) yoki rasm yuboring:", reply_markup=photo_or_skip_kb())
        return
    # expect a number (minutes)
    if not text.isdigit():
        await message.answer("Iltimos faqat raqam kiriting (daqiqada). Masalan: 5")
        return
    minutes = int(text)
    data['users'][str(uid)]['draft_ad']['interval'] = minutes
    data['users'][str(uid)]['state'] = 'driver_confirm'
    save_data()
    # show preview and confirm/clear
    d = data['users'][str(uid)]['draft_ad']
    if 'date' not in d:
        d['date'] = datetime.now().strftime("%Y-%m-%d")
    preview = {
        "id": data['next_ad_id'],
        "user_id": uid,
        "username": f"@{data['users'][str(uid)].get('username','')}",
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

# ======= Confirmations =======
@dp.message_handler(lambda m: m.text == "✅ Tasdiqlash")
async def confirm_handler(message: types.Message):
    uid = message.from_user.id
    u = data['users'].get(str(uid), {})
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
            "photo": None
        }
        data['ads'].append(ad)
        data['next_ad_id'] += 1
        save_data()
        # send once to passenger group
        target = PASSENGER_GROUP_ID
        try:
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
        # ensure only allowed users can publish
        if uid not in ADMINS and uid not in data.get('approved_drivers', []):
            await message.answer("Sizda e'lon yuborish huquqi yo'q.", reply_markup=start_kb())
            return
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
        interval = int(draft.get('interval', 5))
        data['jobs'][str(ad_id)] = {"task": None, "stop": False, "interval": interval, "user_id": uid}
        task = asyncio.create_task(send_indefinitely(ad_id))
        data['jobs'][str(ad_id)]['task'] = task
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
    u = data['users'].setdefault(str(uid), {})
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
            job = data['jobs'].get(str(ad['id']))
            if job:
                job['stop'] = True
                t = job.get('task')
                try:
                    if t:
                        t.cancel()
                except:
                    pass
                data['jobs'].pop(str(ad['id']), None)
                stopped += 1
    save_data()
    await message.answer(f"{stopped} ta yuborish to'xtatildi.", reply_markup=start_kb())

@dp.message_handler(lambda m: m.text == "➕ Yangi habar")
async def new_ad_handler(message: types.Message):
    uid = message.from_user.id
    # only allowed if approved
    if uid not in ADMINS and uid not in data.get('approved_drivers', []):
        kb = InlineKeyboardMarkup()
        for a in ADMINS:
            kb.add(InlineKeyboardButton(f"Adminga yozish ({a})", url=f"tg://user?id={a}"))
        await message.answer("Sizda haydovchi bo‘limiga kirish huquqi yo‘q. Adminlarga murojaat qiling.", reply_markup=kb)
        return
    # start new ad flow (haydovchi uchun: boshlang'ich - MATN)
    data['users'].setdefault(str(uid), {})['state'] = 'driver_wait_text'
    data['users'][str(uid)]['draft_ad'] = {"role": "driver", "user_id": uid, "username": data['users'][str(uid)].get('username','-')}
    save_data()
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("◀️ Orqaga"))
    await message.answer("✍️ Iltimos e'lon matnini yozing:", reply_markup=kb)

# ======= Show all ads (global) =======
@dp.message_handler(lambda m: (m.text == "🗂 E'lonlar" and data['users'].get(str(m.from_user.id),{}).get('role') == 'passenger') or m.text == "🗂 E'lonlar'")
async def show_all_ads_button(message: types.Message):
    if not data['ads']:
        await message.answer("Hozircha e'lonlar yo'q.", reply_markup=start_kb())
        return
    for ad in reversed(data['ads']):
        text = format_driver_ad(ad) if ad.get('role') == 'driver' else format_passenger_ad(ad)
        kb = zakaz_kb() if ad.get('role') == 'driver' else None
        if ad.get('photo'):
            try:
                await message.answer_photo(ad['photo'], caption=text, parse_mode=ParseMode.HTML, reply_markup=kb)
            except:
                await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=kb)
        else:
            await message.answer(text, parse_mode=ParseMode.HTML, reply_markup=kb)

# ======= Catch-all text handler for misc states =======
@dp.message_handler()
async def fallback_handler(message: types.Message):
    uid = message.from_user.id
    u = data['users'].get(str(uid))
    text = message.text.strip()
    # stateful handling
    if u:
        state = u.get('state')
        # passenger alternative time input
        if state == 'passenger_wait_time':
            u['draft_ad']['time'] = text
            u['state'] = 'passenger_wait_count'
            save_data()
            await message.answer("🧍 Necha kishi bor? (misol: 1 kishi, 2 kishi, Pochta bor)", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).row(KeyboardButton("👤 1 kishi"), KeyboardButton("👥 2 kishi")).row(KeyboardButton("📦 Pochta bor"), KeyboardButton("◀️ Orqaga")))
            return
        if state == 'passenger_wait_count':
            u['draft_ad']['count'] = text
            u['state'] = 'passenger_wait_contact'
            save_data()
            await message.answer("📞 Telefon raqamingizni yuboring (tugma orqali tavsiya etiladi):", reply_markup=contact_request_kb())
            return
        if state == 'driver_wait_contact_or_photo':
            if text == "⛔ Tashlab ketish":
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
            await message.answer("Iltimos telefon raqamni tugma orqali yuboring yoki rasm yuboring yoki '⛔ Tashlab ketish' bosing.", reply_markup=photo_or_skip_kb())
            return
        if state == 'driver_wait_interval':
            if not text.isdigit():
                await message.answer("Iltimos faqat raqam kiriting (daqiqada). Masalan: 5")
                return
            minutes = int(text)
            u['draft_ad']['interval'] = minutes
            u['state'] = 'driver_confirm'
            save_data()
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
            # fallback
            data['users'][str(uid)]['draft_ad']['text'] = text
            data['users'][str(uid)]['state'] = 'driver_wait_direction'
            save_data()
            await message.answer("🛣 Yo'nalishni tanlang:", reply_markup=directions_kb())
            return
        if state == 'wait_custom_direction':
            return
        if state == 'passenger_wait_contact':
            # if they typed phone manually
            if text.replace("+","").replace(" ","").isdigit():
                u['draft_ad']['phone'] = text
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
            await message.answer("Iltimos telefon raqamni tugma orqali yuboring.", reply_markup=contact_request_kb())
            return

    # default fallback
    await message.answer("Iltimos menyudan tanlang yoki /start ni bosing.", reply_markup=start_kb())

# ======= Callback: stop single ad =======
@dp.callback_query_handler(lambda c: c.data and c.data.startswith("stop_ad:"))
async def stop_ad_callback(cb: types.CallbackQuery):
    await cb.answer()
    actor = cb.from_user.id
    if actor is None:
        return
    adid_str = cb.data.split(":",1)[1]
    try:
        adid = int(adid_str)
    except:
        await cb.message.answer("Noto'g'ri ad id.")
        return
    job = data['jobs'].get(str(adid))
    if job and job.get('user_id') == actor:
        job['stop'] = True
        t = job.get('task')
        try:
            if t:
                t.cancel()
        except:
            pass
        data['jobs'].pop(str(adid), None)
        save_data()
        await cb.message.answer("E'lonni yuborish to'xtatildi.")
    else:
        await cb.message.answer("Bu e'lon sizga tegishli emas yoki allaqachon to'xtagan.")

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
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup, on_shutdown=on_shutdown)
