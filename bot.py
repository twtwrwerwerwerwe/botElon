# taxi_bot_driver_only_updated.py
"""
Driver-focused Taxi bot
- When user presses "E'lon berish" (passenger) -> original passenger flow unchanged.
- Driver section now ONLY has "E'lon berish" (no "Odam olish").
- Driver's "E'lon berish" flow is distinct:
    1. Select direction (dynamic list from existing ads + defaults + "Boshqa" for manual entry)
    2. Select time (24-hour buttons only; no "Today/Ertaga")
    3. Select car model (Nexia, Malibu, Cobalt, Gentra, BYD, Kia k5, Tracker)
    4. Share contact (request_contact button)
    5. Enter number of sends (free text integer, e.g. 10)
    6. Choose interval (2 yoki 3 minut)
    7. Start sending. During sending the bot shows an inline "⏹️ To'xtatish" button which stops the repetition.
- "Boshqa" direction lets driver type a custom direction string which the bot accepts.

Eslatma: TOKEN, GROUP_ID va ADMIN_* o'zgartirilishi mumkin.
"""

import json
import time
import asyncio
from pathlib import Path
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, ParseMode
)
from aiogram.utils import executor

# ====== CONFIG ======
TOKEN = "8212255968:AAETRL91puhUESsCP7eFKm7pE51tKgm6SQo"
GROUP_ID = -1002589715287
ADMIN_USERNAME = "akramjonovPY"
ADMIN_ID = 6302873072
DATA_FILE = Path("taxi_data.json")

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# ====== STATE ======
# Keep only serializable parts in DATA_FILE; runtime tasks stored in jobs
state = {
    "users": {},   # user_id -> dict
    "ads": [],     # active ads
    "next_ad_id": 1,
}
jobs = {}  # ad_id -> {task, stop_flag, owner}

# ====== STORAGE ======

def load_state():
    if DATA_FILE.exists():
        try:
            d = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            state.update(d)
        except Exception:
            pass


def save_state():
    to_save = {k: v for k, v in state.items()}
    DATA_FILE.write_text(json.dumps(to_save, ensure_ascii=False, indent=2), encoding="utf-8")

load_state()

# remove old ads older than X days
def cleanup_old_ads(days=1):
    cutoff = int(time.time()) - days * 24 * 60 * 60
    before = len(state["ads"])
    state["ads"] = [ad for ad in state["ads"] if ad.get("created_at",0) >= cutoff]
    if len(state["ads"]) != before:
        save_state()

cleanup_old_ads()

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


def directions_kb(include_other=True):
    # dynamic directions from existing ads (passenger-provided) + defaults
    defaults = [
        "🚗 Qo‘qon → Toshkent", "🚗 Toshkent → Qo‘qon",
        "🚗 Rishton → Toshkent", "🚗 Toshkent → Rishton",
        "🚗 Buvayda → Toshkent", "🚗 Toshkent → Buvayda",
    ]
    dyn = sorted({ad["direction"] for ad in state.get("ads", []) if ad.get("direction")})
    choices = dyn + defaults
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    added = set()
    for c in choices:
        if not c or c in added:
            continue
        kb.add(KeyboardButton(c))
        added.add(c)
    if include_other:
        kb.add(KeyboardButton("Boshqa"))
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


def car_kb():
    cars = ["Nexia", "Malibu", "Cobalt", "Gentra", "BYD", "Kia k5", "Tracker"]
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    for c in cars:
        kb.add(KeyboardButton(c))
    kb.add(KeyboardButton("◀️ Orqaga"))
    return kb


def interval_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("2 minut"), KeyboardButton("3 minut"))
    kb.add(KeyboardButton("◀️ Orqaga"))
    return kb

# ====== HELPERS ======

def is_admin(user: types.User):
    if ADMIN_ID and user.id == ADMIN_ID:
        return True
    if user.username and user.username.lower() == ADMIN_USERNAME.lower():
        return True
    return False


def format_ad(ad):
    return (
        f"🚕 <b>Buyurtma #{ad['id']}</b>\n\n"
        f"🛣 <b>Yo‘nalish:</b> {ad['direction']}\n"
        f"📞 <b>Telefon:</b> {ad['phone']}\n"
        f"🚗 <b>Mashina:</b> {ad.get('car','-')}\n"
        f"🕒 <b>Soat:</b> {ad.get('time','-')}\n"
        f"📣 <i>Takrorlanadi:</i> {ad.get('send_times','1')} marta, Interval: {ad.get('interval','2')} min\n"
        f"👤 <b>User:</b> {ad.get('username','-')}\n"
    )

# ====== SENDING TASK ======
async def send_repeated(ad, send_times, interval_min):
    ad_id = ad['id']
    sent = 0
    # ensure job exists
    jobs.setdefault(ad_id, {})
    while True:
        if jobs.get(ad_id, {}).get('stop'):
            break
        try:
            await bot.send_message(GROUP_ID, format_ad(ad), parse_mode=ParseMode.HTML)
            sent += 1
        except Exception as e:
            print('send error', e)
        if send_times == 'Cheksiz':
            await asyncio.sleep(int(interval_min * 60))
            continue
        if sent >= int(send_times):
            break
        await asyncio.sleep(int(interval_min * 60))
    # cleanup job
    jobs.pop(ad_id, None)

# ====== HANDLERS ======
@dp.message_handler(commands=['start','help'])
async def cmd_start(m: types.Message):
    uid = m.from_user.id
    state['users'].setdefault(str(uid), {'username': m.from_user.username or ''})
    save_state()
    await m.answer("👋 Assalomu alaykum!\nTaxi botga xush kelibsiz.", reply_markup=main_menu())

# ----- Passenger (original) flow: E'lon berish starts by asking contact -----
@dp.message_handler(lambda m: m.text == "🚕 E'lon berish")
async def passenger_start(m: types.Message):
    uid = m.from_user.id
    # mark flow
    state['users'].setdefault(str(uid), {})['flow'] = 'passenger'
    save_state()
    await m.answer("📞 Iltimos telefon raqamingizni yuboring:", reply_markup=contact_request_kb())

# Contact handler for both passenger and driver flows
@dp.message_handler(content_types=types.ContentType.CONTACT)
async def handle_contact(m: types.Message):
    uid = m.from_user.id
    u = state['users'].setdefault(str(uid), {})
    phone = m.contact.phone_number
    u['phone'] = phone
    u['username'] = m.from_user.username or m.from_user.full_name
    flow = u.get('flow')
    save_state()
    if flow == 'driver_creating':
        # continue driver flow: after phone ask number of sends
        await m.answer("📣 Necha marta yuborilsin? Iltimos butun son kiriting (masalan: 10)")
        return
    # default passenger behavior: auto set passenger and continue passenger flow
    u['role'] = 'passenger'
    save_state()
    await m.answer("✅ Raqamingiz qabul qilindi. Yo'nalishni tanlang:", reply_markup=directions_kb())

# Passenger direction selection (-> date -> time -> count etc) keep as before
@dp.message_handler(lambda m: '→' in (m.text or '') and state['users'].get(str(m.from_user.id), {}).get('flow') == 'passenger')
async def passenger_direction(m: types.Message):
    uid = str(m.from_user.id)
    state['users'].setdefault(uid, {})['direction'] = m.text
    save_state()
    await m.answer("📅 Kunni tanlang:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).row(KeyboardButton('📅 Bugun'), KeyboardButton('📅 Ertaga')).add(KeyboardButton('◀️ Orqaga')))

@dp.message_handler(lambda m: m.text in ['📅 Bugun','📅 Ertaga'] and state['users'].get(str(m.from_user.id), {}).get('flow') == 'passenger')
async def passenger_date(m: types.Message):
    uid = str(m.from_user.id)
    date = datetime.now().strftime('%Y-%m-%d') if m.text == '📅 Bugun' else (datetime.now()+timedelta(days=1)).strftime('%Y-%m-%d')
    state['users'][uid]['date'] = date
    save_state()
    await m.answer('🕒 Soatni tanlang:', reply_markup=hours_kb())

@dp.message_handler(lambda m: m.text and m.text.endswith(':00') and state['users'].get(str(m.from_user.id), {}).get('flow') == 'passenger')
async def passenger_time(m: types.Message):
    uid = str(m.from_user.id)
    state['users'][uid]['time'] = m.text
    save_state()
    await m.answer('Necha kishi bor? (tugmalardan tanlang)', reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).row(KeyboardButton('👤 1 kishi'), KeyboardButton('👥 2 kishi')).row(KeyboardButton('👪 3 kishi'), KeyboardButton('👨‍👩‍👧‍👦 4 kishi')).add(KeyboardButton('📦 Pochta bor')).add(KeyboardButton('◀️ Orqaga')))

@dp.message_handler(lambda m: any(x in (m.text or '') for x in ['kishi','Pochta','pochta','Pochta bor']) and state['users'].get(str(m.from_user.id), {}).get('flow') == 'passenger')
async def passenger_finalize(m: types.Message):
    uid = str(m.from_user.id)
    u = state['users'][uid]
    # build ad
    ad = {
        'id': state['next_ad_id'],
        'user_id': int(uid),
        'username': u.get('username','-'),
        'phone': u.get('phone','-'),
        'direction': u.get('direction','-'),
        'car': '-',
        'date': u.get('date','-'),
        'time': u.get('time','-'),
        'created_at': int(time.time()),
        'send_times': 1,
        'interval': 2
    }
    state['ads'].append(ad)
    state['next_ad_id'] += 1
    # clear flow state
    for k in ['flow','direction','date','time','phone']:
        u.pop(k, None)
    save_state()
    await m.answer('✅ E\'lon qabul qilindi va guruhga yuboriladi.', reply_markup=main_menu())
    # send once immediately
    try:
        await bot.send_message(GROUP_ID, format_ad(ad), parse_mode=ParseMode.HTML)
    except:
        pass

# ----- Driver section: now only "E'lon berish" -----
@dp.message_handler(lambda m: m.text == '🚘 Haydovchi bo‘limi')
async def driver_section(m: types.Message):
    uid = str(m.from_user.id)
    state['users'].setdefault(uid, {})
    # Only show E'lon berish for drivers
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("📣 E'lon berish"))
    kb.add(KeyboardButton('◀️ Orqaga'))
    await m.answer("🚘 Haydovchi bo'limi:", reply_markup=kb)

# Driver starts creating ad
@dp.message_handler(lambda m: m.text == "📣 E'lon berish")
async def driver_start(m: types.Message):
    uid = str(m.from_user.id)
    state['users'].setdefault(uid, {})['flow'] = 'driver_creating'
    save_state()
    await m.answer("🛣 Yo'nalishni tanlang:", reply_markup=directions_kb())

# When driver selects a direction or "Boshqa"
@dp.message_handler(lambda m: True)
async def catch_all(m: types.Message):
    uid = str(m.from_user.id)
    u = state['users'].get(uid, {})
    text = m.text or ''

    # Back to main
    if text == '◀️ Orqaga':
        # clear flow and go to main menu
        if 'flow' in u:
            for k in ['flow','direction','time','car','phone','send_times','interval']:
                u.pop(k, None)
            save_state()
        await m.answer('🔙 Bosh menyuga qaytdingiz.', reply_markup=main_menu())
        return

    # Driver manual direction entry after pressing Boshqa
    if u.get('flow') == 'driver_creating' and u.get('expecting') == 'manual_direction':
        u['direction'] = text
        u.pop('expecting', None)
        save_state()
        await m.answer("🕒 Soatni tanlang (faqat 24 soat format):", reply_markup=hours_kb())
        return

    # If driver in creating flow and selected a direction from keyboard (or default)
    if u.get('flow') == 'driver_creating' and ('direction' not in u):
        if text == 'Boshqa':
            u['expecting'] = 'manual_direction'
            save_state()
            await m.answer('Iltimos yo\'nalishni matn ko\'rinishida kiriting:')
            return
        # otherwise set direction and ask time
        # accept any text (including arrows) as direction
        u['direction'] = text
        save_state()
        await m.answer("🕒 Soatni tanlang (faqat 24 soat):", reply_markup=hours_kb())
        return

    # Driver: after time selected
    if u.get('flow') == 'driver_creating' and text.endswith(':00') and 'time' not in u:
        u['time'] = text
        save_state()
        await m.answer('🚗 Mashina rusumini tanlang:', reply_markup=car_kb())
        return

    # Driver: after car selected
    if u.get('flow') == 'driver_creating' and text in ["Nexia","Malibu","Cobalt","Gentra","BYD","Kia k5","Tracker"] and 'car' not in u:
        u['car'] = text
        save_state()
        await m.answer('📞 Iltimos telefon raqamingizni yuboring (tugma orqali):', reply_markup=contact_request_kb())
        return

    # Driver: after contact (contact handler directs here to ask send number), we now expect free-text integer
    if u.get('flow') == 'driver_creating' and 'phone' in u and 'send_times' not in u and text.isdigit():
        # user typed number of sends
        n = int(text)
        if n <= 0:
            await m.answer('Iltimos musbat butun son kiriting.')
            return
        u['send_times'] = n
        save_state()
        await m.answer('Intervalni tanlang:', reply_markup=interval_kb())
        return

    # Driver: choose interval
    if u.get('flow') == 'driver_creating' and text in ['2 minut','3 minut'] and 'interval' not in u:
        u['interval'] = 2 if text == '2 minut' else 3
        save_state()
        # finalize and start sending
        # Validate required fields
        missing = [k for k in ['direction','time','car','phone','send_times','interval'] if k not in u]
        if missing:
            await m.answer(f"Quyidagi maydonlar to'ldirilmagan: {', '.join(missing)}. Iltimos qaytadan to'ldiring.")
            return
        # Build ad
        ad = {
            'id': state['next_ad_id'],
            'user_id': int(uid),
            'username': u.get('username','-'),
            'phone': u.get('phone'),
            'direction': u.get('direction'),
            'car': u.get('car'),
            'time': u.get('time'),
            'created_at': int(time.time()),
            'send_times': u.get('send_times'),
            'interval': u.get('interval')
        }
        state['ads'].append(ad)
        state['next_ad_id'] += 1
        save_state()
        # start background task
        ad_copy = ad.copy()
        ad_id = ad_copy['id']
        jobs[ad_id] = {'stop': False, 'owner': int(uid)}
        task = asyncio.create_task(send_repeated(ad_copy, ad_copy['send_times'], ad_copy['interval']))
        jobs[ad_id]['task'] = task
        # show inline stop button to the driver
        ik = InlineKeyboardMarkup().add(InlineKeyboardButton("⏹️ To'xtatish", callback_data=f"stop:{ad_id}"))
        await m.answer(f"✅ E'lon yaratildi va yuborish boshlandi. ID: {ad_id}\nAd: \n{format_ad(ad_copy)}", parse_mode=ParseMode.HTML, reply_markup=ik)
        # clear flow data for user
        for k in ['flow','direction','time','car','phone','send_times','interval','expecting']:
            u.pop(k, None)
        save_state()
        return

    # If nothing matched, fallback
    # (Avoid interfering with other users) 
    await m.answer("😊 Men tushunmadim. Bosh menyu uchun /start yoki tugmalardan birini tanlang.", reply_markup=main_menu())

# Callback to stop a sending job
@dp.callback_query_handler(lambda c: c.data and c.data.startswith('stop:'))
async def callback_stop(call: types.CallbackQuery):
    await call.answer()
    parts = call.data.split(':')
    if len(parts) < 2:
        return
    ad_id = int(parts[1])
    job = jobs.get(ad_id)
    if not job:
        await call.message.edit_text('Bu yuborish topilmadi yoki allaqachon tugagan.')
        return
    # Only owner or admin can stop
    owner = job.get('owner')
    if call.from_user.id != owner and not is_admin(call.from_user):
        await call.message.answer('Siz bu yuborishni to' + "xtata olmaysiz.")
        return
    job['stop'] = True
    t = job.get('task')
    try:
        t.cancel()
    except:
        pass
    jobs.pop(ad_id, None)
    await call.message.edit_text('✅ Yuborish to' + "xtatildi.")

# Admin command to approve (unchanged)
@dp.message_handler(commands=['approved'])
async def cmd_approved(m: types.Message):
    if not is_admin(m.from_user):
        await m.reply('Siz admin emassiz.')
        return
    parts = m.text.split()
    if len(parts) < 2:
        await m.reply("Foydalanish: /approved <user_id>")
        return
    try:
        uid = int(parts[1])
    except:
        await m.reply("Noto'g'ri user_id.")
        return
    state['users'].setdefault(str(uid), {})['approved'] = True
    save_state()
    await m.reply(f"✅ {uid} ruxsatlandi.")

# Shutdown: cancel running tasks
async def on_shutdown(dp):
    # set stop flags
    for jid, job in list(jobs.items()):
        job['stop'] = True
        t = job.get('task')
        try:
            t.cancel()
        except:
            pass
    save_state()
    await bot.close()

if __name__ == '__main__':
    print('Taxi bot (driver-only update) ishga tushmoqda...')
    executor.start_polling(dp, skip_updates=True, on_shutdown=on_shutdown)
# taxi_bot_driver_only_updated.py
"""
Driver-focused Taxi bot
- When user presses "E'lon berish" (passenger) -> original passenger flow unchanged.
- Driver section now ONLY has "E'lon berish" (no "Odam olish").
- Driver's "E'lon berish" flow is distinct:
    1. Select direction (dynamic list from existing ads + defaults + "Boshqa" for manual entry)
    2. Select time (24-hour buttons only; no "Today/Ertaga")
    3. Select car model (Nexia, Malibu, Cobalt, Gentra, BYD, Kia k5, Tracker)
    4. Share contact (request_contact button)
    5. Enter number of sends (free text integer, e.g. 10)
    6. Choose interval (2 yoki 3 minut)
    7. Start sending. During sending the bot shows an inline "⏹️ To'xtatish" button which stops the repetition.
- "Boshqa" direction lets driver type a custom direction string which the bot accepts.

Eslatma: TOKEN, GROUP_ID va ADMIN_* o'zgartirilishi mumkin.
"""

import json
import time
import asyncio
from pathlib import Path
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, ParseMode
)
from aiogram.utils import executor

# ====== CONFIG ======
TOKEN = "8212255968:AAETRL91puhUESsCP7eFKm7pE51tKgm6SQo"
GROUP_ID = -1002589715287
ADMIN_USERNAME = "akramjonovPY"
ADMIN_ID = 6302873072
DATA_FILE = Path("taxi_data.json")

bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# ====== STATE ======
# Keep only serializable parts in DATA_FILE; runtime tasks stored in jobs
state = {
    "users": {},   # user_id -> dict
    "ads": [],     # active ads
    "next_ad_id": 1,
}
jobs = {}  # ad_id -> {task, stop_flag, owner}

# ====== STORAGE ======

def load_state():
    if DATA_FILE.exists():
        try:
            d = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            state.update(d)
        except Exception:
            pass


def save_state():
    to_save = {k: v for k, v in state.items()}
    DATA_FILE.write_text(json.dumps(to_save, ensure_ascii=False, indent=2), encoding="utf-8")

load_state()

# remove old ads older than X days
def cleanup_old_ads(days=1):
    cutoff = int(time.time()) - days * 24 * 60 * 60
    before = len(state["ads"])
    state["ads"] = [ad for ad in state["ads"] if ad.get("created_at",0) >= cutoff]
    if len(state["ads"]) != before:
        save_state()

cleanup_old_ads()

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


def directions_kb(include_other=True):
    # dynamic directions from existing ads (passenger-provided) + defaults
    defaults = [
        "🚗 Qo‘qon → Toshkent", "🚗 Toshkent → Qo‘qon",
        "🚗 Rishton → Toshkent", "🚗 Toshkent → Rishton",
        "🚗 Buvayda → Toshkent", "🚗 Toshkent → Buvayda",
    ]
    dyn = sorted({ad["direction"] for ad in state.get("ads", []) if ad.get("direction")})
    choices = dyn + defaults
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    added = set()
    for c in choices:
        if not c or c in added:
            continue
        kb.add(KeyboardButton(c))
        added.add(c)
    if include_other:
        kb.add(KeyboardButton("Boshqa"))
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


def car_kb():
    cars = ["Nexia", "Malibu", "Cobalt", "Gentra", "BYD", "Kia k5", "Tracker"]
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    for c in cars:
        kb.add(KeyboardButton(c))
    kb.add(KeyboardButton("◀️ Orqaga"))
    return kb


def interval_kb():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("2 minut"), KeyboardButton("3 minut"))
    kb.add(KeyboardButton("◀️ Orqaga"))
    return kb

# ====== HELPERS ======

def is_admin(user: types.User):
    if ADMIN_ID and user.id == ADMIN_ID:
        return True
    if user.username and user.username.lower() == ADMIN_USERNAME.lower():
        return True
    return False


def format_ad(ad):
    return (
        f"🚕 <b>Buyurtma #{ad['id']}</b>\n\n"
        f"🛣 <b>Yo‘nalish:</b> {ad['direction']}\n"
        f"📞 <b>Telefon:</b> {ad['phone']}\n"
        f"🚗 <b>Mashina:</b> {ad.get('car','-')}\n"
        f"🕒 <b>Soat:</b> {ad.get('time','-')}\n"
        f"📣 <i>Takrorlanadi:</i> {ad.get('send_times','1')} marta, Interval: {ad.get('interval','2')} min\n"
        f"👤 <b>User:</b> {ad.get('username','-')}\n"
    )

# ====== SENDING TASK ======
async def send_repeated(ad, send_times, interval_min):
    ad_id = ad['id']
    sent = 0
    # ensure job exists
    jobs.setdefault(ad_id, {})
    while True:
        if jobs.get(ad_id, {}).get('stop'):
            break
        try:
            await bot.send_message(GROUP_ID, format_ad(ad), parse_mode=ParseMode.HTML)
            sent += 1
        except Exception as e:
            print('send error', e)
        if send_times == 'Cheksiz':
            await asyncio.sleep(int(interval_min * 60))
            continue
        if sent >= int(send_times):
            break
        await asyncio.sleep(int(interval_min * 60))
    # cleanup job
    jobs.pop(ad_id, None)

# ====== HANDLERS ======
@dp.message_handler(commands=['start','help'])
async def cmd_start(m: types.Message):
    uid = m.from_user.id
    state['users'].setdefault(str(uid), {'username': m.from_user.username or ''})
    save_state()
    await m.answer("👋 Assalomu alaykum!\nTaxi botga xush kelibsiz.", reply_markup=main_menu())

# ----- Passenger (original) flow: E'lon berish starts by asking contact -----
@dp.message_handler(lambda m: m.text == "🚕 E'lon berish")
async def passenger_start(m: types.Message):
    uid = m.from_user.id
    # mark flow
    state['users'].setdefault(str(uid), {})['flow'] = 'passenger'
    save_state()
    await m.answer("📞 Iltimos telefon raqamingizni yuboring:", reply_markup=contact_request_kb())

# Contact handler for both passenger and driver flows
@dp.message_handler(content_types=types.ContentType.CONTACT)
async def handle_contact(m: types.Message):
    uid = m.from_user.id
    u = state['users'].setdefault(str(uid), {})
    phone = m.contact.phone_number
    u['phone'] = phone
    u['username'] = m.from_user.username or m.from_user.full_name
    flow = u.get('flow')
    save_state()
    if flow == 'driver_creating':
        # continue driver flow: after phone ask number of sends
        await m.answer("📣 Necha marta yuborilsin? Iltimos butun son kiriting (masalan: 10)")
        return
    # default passenger behavior: auto set passenger and continue passenger flow
    u['role'] = 'passenger'
    save_state()
    await m.answer("✅ Raqamingiz qabul qilindi. Yo'nalishni tanlang:", reply_markup=directions_kb())

# Passenger direction selection (-> date -> time -> count etc) keep as before
@dp.message_handler(lambda m: '→' in (m.text or '') and state['users'].get(str(m.from_user.id), {}).get('flow') == 'passenger')
async def passenger_direction(m: types.Message):
    uid = str(m.from_user.id)
    state['users'].setdefault(uid, {})['direction'] = m.text
    save_state()
    await m.answer("📅 Kunni tanlang:", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).row(KeyboardButton('📅 Bugun'), KeyboardButton('📅 Ertaga')).add(KeyboardButton('◀️ Orqaga')))

@dp.message_handler(lambda m: m.text in ['📅 Bugun','📅 Ertaga'] and state['users'].get(str(m.from_user.id), {}).get('flow') == 'passenger')
async def passenger_date(m: types.Message):
    uid = str(m.from_user.id)
    date = datetime.now().strftime('%Y-%m-%d') if m.text == '📅 Bugun' else (datetime.now()+timedelta(days=1)).strftime('%Y-%m-%d')
    state['users'][uid]['date'] = date
    save_state()
    await m.answer('🕒 Soatni tanlang:', reply_markup=hours_kb())

@dp.message_handler(lambda m: m.text and m.text.endswith(':00') and state['users'].get(str(m.from_user.id), {}).get('flow') == 'passenger')
async def passenger_time(m: types.Message):
    uid = str(m.from_user.id)
    state['users'][uid]['time'] = m.text
    save_state()
    await m.answer('Necha kishi bor? (tugmalardan tanlang)', reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).row(KeyboardButton('👤 1 kishi'), KeyboardButton('👥 2 kishi')).row(KeyboardButton('👪 3 kishi'), KeyboardButton('👨‍👩‍👧‍👦 4 kishi')).add(KeyboardButton('📦 Pochta bor')).add(KeyboardButton('◀️ Orqaga')))

@dp.message_handler(lambda m: any(x in (m.text or '') for x in ['kishi','Pochta','pochta','Pochta bor']) and state['users'].get(str(m.from_user.id), {}).get('flow') == 'passenger')
async def passenger_finalize(m: types.Message):
    uid = str(m.from_user.id)
    u = state['users'][uid]
    # build ad
    ad = {
        'id': state['next_ad_id'],
        'user_id': int(uid),
        'username': u.get('username','-'),
        'phone': u.get('phone','-'),
        'direction': u.get('direction','-'),
        'car': '-',
        'date': u.get('date','-'),
        'time': u.get('time','-'),
        'created_at': int(time.time()),
        'send_times': 1,
        'interval': 2
    }
    state['ads'].append(ad)
    state['next_ad_id'] += 1
    # clear flow state
    for k in ['flow','direction','date','time','phone']:
        u.pop(k, None)
    save_state()
    await m.answer('✅ E\'lon qabul qilindi va guruhga yuboriladi.', reply_markup=main_menu())
    # send once immediately
    try:
        await bot.send_message(GROUP_ID, format_ad(ad), parse_mode=ParseMode.HTML)
    except:
        pass

# ----- Driver section: now only "E'lon berish" -----
@dp.message_handler(lambda m: m.text == '🚘 Haydovchi bo‘limi')
async def driver_section(m: types.Message):
    uid = str(m.from_user.id)
    state['users'].setdefault(uid, {})
    # Only show E'lon berish for drivers
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("📣 E'lon berish"))
    kb.add(KeyboardButton('◀️ Orqaga'))
    await m.answer("🚘 Haydovchi bo'limi:", reply_markup=kb)

# Driver starts creating ad
@dp.message_handler(lambda m: m.text == "📣 E'lon berish")
async def driver_start(m: types.Message):
    uid = str(m.from_user.id)
    state['users'].setdefault(uid, {})['flow'] = 'driver_creating'
    save_state()
    await m.answer("🛣 Yo'nalishni tanlang:", reply_markup=directions_kb())

# When driver selects a direction or "Boshqa"
@dp.message_handler(lambda m: True)
async def catch_all(m: types.Message):
    uid = str(m.from_user.id)
    u = state['users'].get(uid, {})
    text = m.text or ''

    # Back to main
    if text == '◀️ Orqaga':
        # clear flow and go to main menu
        if 'flow' in u:
            for k in ['flow','direction','time','car','phone','send_times','interval']:
                u.pop(k, None)
            save_state()
        await m.answer('🔙 Bosh menyuga qaytdingiz.', reply_markup=main_menu())
        return

    # Driver manual direction entry after pressing Boshqa
    if u.get('flow') == 'driver_creating' and u.get('expecting') == 'manual_direction':
        u['direction'] = text
        u.pop('expecting', None)
        save_state()
        await m.answer("🕒 Soatni tanlang (faqat 24 soat format):", reply_markup=hours_kb())
        return

    # If driver in creating flow and selected a direction from keyboard (or default)
    if u.get('flow') == 'driver_creating' and ('direction' not in u):
        if text == 'Boshqa':
            u['expecting'] = 'manual_direction'
            save_state()
            await m.answer('Iltimos yo\'nalishni matn ko\'rinishida kiriting:')
            return
        # otherwise set direction and ask time
        # accept any text (including arrows) as direction
        u['direction'] = text
        save_state()
        await m.answer("🕒 Soatni tanlang (faqat 24 soat):", reply_markup=hours_kb())
        return

    # Driver: after time selected
    if u.get('flow') == 'driver_creating' and text.endswith(':00') and 'time' not in u:
        u['time'] = text
        save_state()
        await m.answer('🚗 Mashina rusumini tanlang:', reply_markup=car_kb())
        return

    # Driver: after car selected
    if u.get('flow') == 'driver_creating' and text in ["Nexia","Malibu","Cobalt","Gentra","BYD","Kia k5","Tracker"] and 'car' not in u:
        u['car'] = text
        save_state()
        await m.answer('📞 Iltimos telefon raqamingizni yuboring (tugma orqali):', reply_markup=contact_request_kb())
        return

    # Driver: after contact (contact handler directs here to ask send number), we now expect free-text integer
    if u.get('flow') == 'driver_creating' and 'phone' in u and 'send_times' not in u and text.isdigit():
        # user typed number of sends
        n = int(text)
        if n <= 0:
            await m.answer('Iltimos musbat butun son kiriting.')
            return
        u['send_times'] = n
        save_state()
        await m.answer('Intervalni tanlang:', reply_markup=interval_kb())
        return

    # Driver: choose interval
    if u.get('flow') == 'driver_creating' and text in ['2 minut','3 minut'] and 'interval' not in u:
        u['interval'] = 2 if text == '2 minut' else 3
        save_state()
        # finalize and start sending
        # Validate required fields
        missing = [k for k in ['direction','time','car','phone','send_times','interval'] if k not in u]
        if missing:
            await m.answer(f"Quyidagi maydonlar to'ldirilmagan: {', '.join(missing)}. Iltimos qaytadan to'ldiring.")
            return
        # Build ad
        ad = {
            'id': state['next_ad_id'],
            'user_id': int(uid),
            'username': u.get('username','-'),
            'phone': u.get('phone'),
            'direction': u.get('direction'),
            'car': u.get('car'),
            'time': u.get('time'),
            'created_at': int(time.time()),
            'send_times': u.get('send_times'),
            'interval': u.get('interval')
        }
        state['ads'].append(ad)
        state['next_ad_id'] += 1
        save_state()
        # start background task
        ad_copy = ad.copy()
        ad_id = ad_copy['id']
        jobs[ad_id] = {'stop': False, 'owner': int(uid)}
        task = asyncio.create_task(send_repeated(ad_copy, ad_copy['send_times'], ad_copy['interval']))
        jobs[ad_id]['task'] = task
        # show inline stop button to the driver
        ik = InlineKeyboardMarkup().add(InlineKeyboardButton("⏹️ To'xtatish", callback_data=f"stop:{ad_id}"))
        await m.answer(f"✅ E'lon yaratildi va yuborish boshlandi. ID: {ad_id}\nAd: \n{format_ad(ad_copy)}", parse_mode=ParseMode.HTML, reply_markup=ik)
        # clear flow data for user
        for k in ['flow','direction','time','car','phone','send_times','interval','expecting']:
            u.pop(k, None)
        save_state()
        return

    # If nothing matched, fallback
    # (Avoid interfering with other users) 
    await m.answer("😊 Men tushunmadim. Bosh menyu uchun /start yoki tugmalardan birini tanlang.", reply_markup=main_menu())

# Callback to stop a sending job
@dp.callback_query_handler(lambda c: c.data and c.data.startswith('stop:'))
async def callback_stop(call: types.CallbackQuery):
    await call.answer()
    parts = call.data.split(':')
    if len(parts) < 2:
        return
    ad_id = int(parts[1])
    job = jobs.get(ad_id)
    if not job:
        await call.message.edit_text('Bu yuborish topilmadi yoki allaqachon tugagan.')
        return
    # Only owner or admin can stop
    owner = job.get('owner')
    if call.from_user.id != owner and not is_admin(call.from_user):
        await call.message.answer('Siz bu yuborishni to' + "xtata olmaysiz.")
        return
    job['stop'] = True
    t = job.get('task')
    try:
        t.cancel()
    except:
        pass
    jobs.pop(ad_id, None)
    await call.message.edit_text('✅ Yuborish to' + "xtatildi.")

# Admin command to approve (unchanged)
@dp.message_handler(commands=['approved'])
async def cmd_approved(m: types.Message):
    if not is_admin(m.from_user):
        await m.reply('Siz admin emassiz.')
        return
    parts = m.text.split()
    if len(parts) < 2:
        await m.reply("Foydalanish: /approved <user_id>")
        return
    try:
        uid = int(parts[1])
    except:
        await m.reply("Noto'g'ri user_id.")
        return
    state['users'].setdefault(str(uid), {})['approved'] = True
    save_state()
    await m.reply(f"✅ {uid} ruxsatlandi.")

# Shutdown: cancel running tasks
async def on_shutdown(dp):
    # set stop flags
    for jid, job in list(jobs.items()):
        job['stop'] = True
        t = job.get('task')
        try:
            t.cancel()
        except:
            pass
    save_state()
    await bot.close()

if __name__ == '__main__':
    print('Taxi bot (driver-only update) ishga tushmoqda...')
    executor.start_polling(dp, skip_updates=True, on_shutdown=on_shutdown)
