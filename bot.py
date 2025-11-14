# taxi_bot_final.py
# Aiogram 2.x taxi bot — haydovchi va yo‘lovchi e’lonlari bilan
import asyncio
import json
import time
from pathlib import Path
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

# ---------------- CONFIG ----------------
TOKEN = "8212255968:AAETRL91puhUESsCP7eFKm7pE51tKgm6SQo"
ADMIN_ID = 6302873072
BOT_USERNAME = "https://t.me/RishtonBuvaydaBogdod_bot"

DRIVER_CHANNELS = [-1003292352387]
PASSENGER_CHANNELS = [-1003443552869]

DATA_FILE = Path("data.json")
ADS_FILE  = Path("ads.json")

# ---------------- JSON HELPERS ----------------
def load_json(path, default):
    if not path.exists():
        return default
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(d, dict):
            return default
        if 'users' not in d:
            d['users'] = {}
        return d
    except:
        return default

def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

# ---------------- INIT FILES ----------------
if not DATA_FILE.exists(): save_json(DATA_FILE, {"users":{}})
if not ADS_FILE.exists():  save_json(ADS_FILE, {"driver":{}, "passenger":{}})

# ---------------- BOT ----------------
bot = Bot(TOKEN, parse_mode="HTML")
dp  = Dispatcher(bot)

data = load_json(DATA_FILE, {"users":{}})
ads  = load_json(ADS_FILE, {"driver":{}, "passenger":{}})

# ---------------- KEYBOARDS ----------------
def main_menu():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("🚘 Haydovchi"), KeyboardButton("🧍 Yo‘lovchi"))
    return kb

def back_btn():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("◀️ Orqaga")
    return kb

# ---------------- START ----------------
@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    uid = str(message.from_user.id)
    if uid not in data['users']:
        data['users'][uid] = {"role":None, "driver_status":"none", "state":None, "driver_temp":{}, "pass_temp":{}}
        save_json(DATA_FILE, data)
    await message.answer("<b>Salom!</b> Siz kimsiz? Tanlang:", reply_markup=main_menu())

# ---------------- HAYDOVCHI SECTION ----------------
@dp.message_handler(lambda m: m.text == "🚘 Haydovchi")
async def driver_section(message: types.Message):
    uid = str(message.from_user.id)
    u  = data['users'].get(uid, {"driver_status":"none"})
    if u['driver_status'] == "none":
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add("📨 Haydovchi bo‘lish uchun ariza yuborish", "◀️ Orqaga")
        return await message.answer("Siz hali haydovchi emassiz. Ariza yuboring.", reply_markup=kb)
    if u['driver_status'] == "pending":
        return await message.answer("⏳ Arizangiz admin tomonidan ko‘rib chiqilmoqda…", reply_markup=back_btn())
    if u['driver_status'] == "rejected":
        return await message.answer("❌ Admin arizani rad etgan.", reply_markup=back_btn())
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📣 E’lon berish", "⏸ To‘xtatish", "▶ Davom etish", "🆕 Yangi e’lon", "◀️ Orqaga")
    await message.answer("Haydovchi bo‘limi:", reply_markup=kb)

# ---------------- YOLOVCHI SECTION ----------------
@dp.message_handler(lambda m: m.text == "🧍 Yo‘lovchi")
async def passenger_section(message: types.Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📝 E’lon berish", "◀️ Orqaga")
    await message.answer("Yo‘lovchi bo‘limi:", reply_markup=kb)

# ---------------- HAYDOVCHI ARIZA ----------------
@dp.message_handler(lambda m: m.text == "📨 Haydovchi bo‘lish uchun ariza yuborish")
async def driver_apply(message: types.Message):
    uid = str(message.from_user.id)
    u = data['users'].get(uid)
    if not u or u['driver_status'] != "none":
        return await message.answer("Siz allaqachon ariza yuborgansiz.")
    data['users'][uid]['driver_status'] = "pending"
    save_json(DATA_FILE, data)
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"drv_ok:{uid}"),
        InlineKeyboardButton("❌ Rad etish", callback_data=f"drv_no:{uid}")
    )
    await bot.send_message(
        ADMIN_ID,
        f"🚘 Haydovchilik uchun ariza:\n👤 <b>{message.from_user.full_name}</b>\n🆔 <code>{uid}</code>",
        reply_markup=kb
    )
    await message.answer("Arizangiz adminga yuborildi! ⏳ Kuting.")

# ---------------- ADMIN HAYDOVCHI TASDIQLASH ----------------
@dp.callback_query_handler(lambda c: c.data.startswith("drv_"))
async def admin_driver_action(call: types.CallbackQuery):
    action, uid = call.data.split(":")
    if action == "drv_ok":
        data['users'][uid]['driver_status'] = "approved"
        save_json(DATA_FILE, data)
        await bot.send_message(uid, "🎉 Admin sizni tasdiqladi! Endi haydovchi bo‘limiga kira olasiz.")
    else:
        data['users'][uid]['driver_status'] = "rejected"
        save_json(DATA_FILE, data)
        await bot.send_message(uid, "❌ Admin arizani rad etdi.")
    # Har doim asosiy menyuga qaytadi
    await bot.send_message(uid, "Asosiy menyuga qayting:", reply_markup=main_menu())
    await call.message.edit_text("✅ Amal bajarildi")

# ---------------- HAYDOVCHI E’LON BERISH ----------------
@dp.message_handler(lambda m: m.text == "📣 E’lon berish")
async def driver_new_ad(message: types.Message):
    uid = str(message.from_user.id)
    data['users'][uid]['state'] = "driver_text"
    data['users'][uid]['driver_temp'] = {}
    save_json(DATA_FILE, data)
    await message.answer("✍️ E’lon matnini yuboring:", reply_markup=back_btn())

@dp.message_handler(lambda m: data['users'].get(str(m.from_user.id), {}).get('state')=="driver_text")
async def driver_get_text(message: types.Message):
    uid = str(message.from_user.id)
    data['users'][uid]['driver_temp']['text'] = message.text
    data['users'][uid]['state'] = "driver_photo"
    save_json(DATA_FILE, data)
    await message.answer("📸 Mashina rasmini yuboring (majburiy):")

@dp.message_handler(content_types=['photo'])
async def driver_get_photo(message: types.Message):
    uid = str(message.from_user.id)
    if data['users'][uid].get('state') != "driver_photo":
        return
    file_id = message.photo[-1].file_id
    data['users'][uid]['driver_temp']['photo'] = file_id
    data['users'][uid]['state'] = "driver_interval"
    save_json(DATA_FILE, data)
    await message.answer("⏱ Necha daqiqada qayta yuborilsin? (masalan: 1)")

@dp.message_handler(lambda m: data['users'].get(str(m.from_user.id), {}).get('state')=="driver_interval")
async def driver_get_interval(message: types.Message):
    uid = str(message.from_user.id)
    try: interval = int(message.text)
    except: return await message.answer("Faqat son kiriting!")
    data['users'][uid]['driver_temp']['interval'] = interval
    data['users'][uid]['state'] = "driver_confirm"
    save_json(DATA_FILE, data)
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("✅ Tasdiqlash", "🗑 Tozalash", "◀️ Orqaga")
    await message.answer("Hammasi tayyor. Tasdiqlaysizmi?", reply_markup=kb)

@dp.message_handler(lambda m: m.text=="🗑 Tozalash")
async def driver_clear(message: types.Message):
    uid = str(message.from_user.id)
    data['users'][uid]['driver_temp'] = {}
    data['users'][uid]['state'] = None
    save_json(DATA_FILE, data)
    await message.answer("Tozalandi!", reply_markup=main_menu())

@dp.message_handler(lambda m: m.text=="✅ Tasdiqlash")
async def driver_confirm(message: types.Message):
    uid = str(message.from_user.id)
    u = data['users'][uid]['driver_temp']
    ad_id = str(time.time()).replace('.', '')
    ads['driver'][ad_id] = {
        "user": uid,
        "text": u['text'],
        "photo": u['photo'],
        "interval": max(0.1, u['interval']),  # minimal tezlik
        "start": time.time(),
        "active": True
    }
    save_json(ADS_FILE, ads)
    data['users'][uid]['driver_temp'] = {}
    data['users'][uid]['state'] = None
    save_json(DATA_FILE, data)
    await message.answer("🚀 E’lon yuborish boshlandi!", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("⏸ To‘xtatish", "▶ Davom etish", "🆕 Yangi e’lon", "◀️ Orqaga"))

# ---------------- DRIVER LOOP ----------------
async def driver_loop():
    while True:
        now = time.time()
        for ad_id, ad in list(ads['driver'].items()):
            if not ad.get('active', False): continue
            if now - ad['start'] > 86400:
                ads['driver'][ad_id]['active'] = False
                save_json(ADS_FILE, ads)
                continue
            for ch in DRIVER_CHANNELS:
                try:
                    kb = InlineKeyboardMarkup()
                    kb.add(InlineKeyboardButton("📩 Zakaz berish", url=f"https://t.me/{BOT_USERNAME}"))
                    await bot.send_photo(ch, ad['photo'], caption=ad['text'], reply_markup=kb)
                except: pass
            await asyncio.sleep(ad['interval']*60)
        await asyncio.sleep(2)

# ---------------- PAUSE / RESUME ----------------
@dp.message_handler(lambda m: m.text=="⏸ To‘xtatish")
async def pause_driver(message: types.Message):
    uid = str(message.from_user.id)
    for ad in ads['driver'].values():
        if ad['user']==uid: ad['active']=False
    save_json(ADS_FILE, ads)
    await message.answer("⏸ Pauza qilindi.", reply_markup=main_menu())

@dp.message_handler(lambda m: m.text=="▶ Davom etish")
async def resume_driver(message: types.Message):
    uid = str(message.from_user.id)
    for ad in ads['driver'].values():
        if ad['user']==uid:
            ad['active']=True
            ad['start']=time.time()
    save_json(ADS_FILE, ads)
    await message.answer("▶ Davom ettirildi.", reply_markup=main_menu())

@dp.message_handler(lambda m: m.text=="🆕 Yangi e’lon")
async def new_driver_ad(message: types.Message):
    return await driver_new_ad(message)

# ---------------- YOLOVCHI ----------------
PASS_ROUTES = [
    "🚗 Qo‘qon → Toshkent", "🚗 Toshkent → Qo‘qon",
    "🚗 Rishton → Toshkent", "🚗 Toshkent → Rishton",
    "🚗 Buvayda → Toshkent", "🚗 Toshkent → Buvayda",
    "🚗 Yangi Qo‘rg‘on → Toshkent", "🚗 Toshkent → Yangi Qo‘rg‘on",
    "🚗 Farg‘ona → Toshkent", "🚗 Toshkent → Farg‘ona",
    "🚗 Bag‘dod → Toshkent", "🚗 Toshkent → Bag‘dod"
]

@dp.message_handler(lambda m: m.text=="📝 E’lon berish")
async def passenger_ad(message: types.Message):
    uid = str(message.from_user.id)
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    for r in PASS_ROUTES: kb.add(r)
    kb.add("🔤 Boshqa")
    kb.add("◀️ Orqaga")
    data['users'][uid]['state']="pass_route"
    save_json(DATA_FILE, data)
    await message.answer("Yo‘nalishni tanlang:", reply_markup=kb)

# ---------------- YOLOVCHI HANDLERS ----------------
@dp.message_handler(lambda m: data['users'].get(str(m.from_user.id),{}).get('state')=="pass_route")
async def pass_get_route(message):
    uid=str(message.from_user.id)
    if message.text=="🔤 Boshqa":
        data['users'][uid]['state']="pass_route_custom"
        save_json(DATA_FILE, data)
        return await message.answer("Yo‘nalishni yozing:")
    if message.text not in PASS_ROUTES:
        return await message.answer("Ro‘yxatdan tanlang yoki Boshqani bosing.")
    data['users'][uid]['pass_temp']={"route":message.text}
    data['users'][uid]['state']="pass_people"
    save_json(DATA_FILE, data)
    kb=ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("1 kishi","2 kishi","3 kishi","4 kishi","📦 Pochta","◀️ Orqaga")
    await message.answer("Necha kishisiz?", reply_markup=kb)

@dp.message_handler(lambda m: data['users'].get(str(m.from_user.id),{}).get('state')=="pass_route_custom")
async def pass_custom(message):
    uid=str(message.from_user.id)
    data['users'][uid]['pass_temp']={"route":message.text}
    data['users'][uid]['state']="pass_people"
    save_json(DATA_FILE, data)
    kb=ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("1 kishi","2 kishi","3 kishi","4 kishi","📦 Pochta","◀️ Orqaga")
    await message.answer("Necha kishisiz?", reply_markup=kb)

@dp.message_handler(lambda m: data['users'].get(str(m.from_user.id),{}).get('state')=="pass_people")
async def pass_people(message: types.Message):
    uid = str(message.from_user.id)
    data['users'][uid]['pass_temp']['people'] = message.text
    data['users'][uid]['state'] = "pass_date"
    save_json(DATA_FILE, data)

    # 24 soatlik klaviatura
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    for h in range(24):
        kb.add(f"{h:02d}:00")
    kb.add("◀️ Orqaga")  # orqaga tugma

    await message.answer("Qachonga?", reply_markup=kb)


@dp.message_handler(lambda m: data['users'].get(str(m.from_user.id),{}).get('state')=="pass_date")
async def pass_date(message):
    uid=str(message.from_user.id)
    data['users'][uid]['pass_temp']['time']=message.text
    data['users'][uid]['state']="pass_phone"
    save_json(DATA_FILE, data)
    await message.answer("📞 Telefon raqamingizni kiriting (+998901234567):", reply_markup=back_btn())

@dp.message_handler(lambda m: data['users'].get(str(m.from_user.id),{}).get('state')=="pass_phone")
async def pass_phone(message):
    uid=str(message.from_user.id)
    t=data['users'][uid]['pass_temp']
    if not message.text.startswith("+"): return await message.answer("Raqam + bilan boshlansin!")
    t['phone']=message.text
    ad_id=str(time.time()).replace('.','')
    ads['passenger'][ad_id]=t
    save_json(ADS_FILE, ads)
    data['users'][uid]['pass_temp']={}
    data['users'][uid]['state']=None
    save_json(DATA_FILE, data)
    text = (
    f"🚖 <b>Yo‘lovchi e’loni:</b>\n\n"
    f"📍 <b>Yo‘nalish:</b> {t['route']}\n\n"
    f"👥 <b>Odamlar soni:</b> {t['people']}\n\n"
    f"🕒 <b>Vaqt:</b> {t['time']}\n\n"
    f"📞 <b>Telefon:</b> {t['phone']}\n"
)
    for ch in PASSENGER_CHANNELS:
        try: await bot.send_message(ch,text, parse_mode="HTML")
        except: pass
    await message.answer("E’lon yuborildi!", reply_markup=main_menu())

# ---------------- START BOT ----------------
if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.create_task(driver_loop())
    executor.start_polling(dp, skip_updates=True)
