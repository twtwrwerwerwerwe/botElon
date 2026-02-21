# taxi_bot_final_fixed.py
import asyncio
import json
import time
from pathlib import Path
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
import time
import json
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
import sqlite3
from aiogram.types import CallbackQuery
from datetime import datetime, timedelta

# 🔗 DATABASE ULANISH
conn = sqlite3.connect("bot.db")
cursor = conn.cursor()

def is_user_premium(user_id):
    cursor.execute("SELECT is_premium, premium_until FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()

    if user:
        is_premium, premium_until = user
        if is_premium == 1:
            return True

    return False

# 👤 USERS TABLE
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    is_premium INTEGER DEFAULT 0,
    premium_until TEXT
)
""")

conn.commit()

# ---------------- CONFIG ----------------
TOKEN = "8212255968:AAETRL91puhUESsCP7eFKm7pE51tKgm6SQo"
ADMINS = [6302873072, 6731395876]
BOT_USERNAME = "@RishtonBuvaydaBogdod_bot"

class PremiumStates(StatesGroup):
    waiting_for_month = State()

# Bu yerga 1 yoki undan ortiq kanal id larini qo'yishingiz mumkin.
DRIVER_CHANNELS = [-1003292352387, -1002558743974, -1002258300973, -1001168970257, -1002401105872, -1002071453667, -1002336638025, -1002280167812, -1001742021244, -1002671120549, -1002349130903,-1001845354641, -1002196478283, -1002454716537]
PASSENGER_CHANNELS = [-1003443552869, -1003706847533]

DATA_FILE = Path("data.json")
ADS_FILE = Path("ads.json")

# ---------------- JSON HELPERS ----------------
def load_json(path, default):
    if not path.exists():
        return default
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(d, dict):
            return default
        # ensure structure for compatibility
        if 'users' not in d:
            d['users'] = {}
        if 'admin_notifs' not in d:
            d['admin_notifs'] = {}  # uid -> list of {"admin": id, "msg_id": id}
        return d
    except:
        return default

def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

# ---------------- INIT FILES ----------------
if not DATA_FILE.exists():
    save_json(DATA_FILE, {"users":{}, "admin_notifs": {}})
if not ADS_FILE.exists():
    save_json(ADS_FILE, {"driver":{}, "passenger":{}})

# ---------------- BOT ----------------
bot = Bot(TOKEN, parse_mode="HTML")
dp = Dispatcher(bot)
data = load_json(DATA_FILE, {"users":{}, "admin_notifs": {}})
ads = load_json(ADS_FILE, {"driver":{}, "passenger":{}})


ADS_FILE = "ads.json"

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

ads = load_json(ADS_FILE)


# ---------------- KEYBOARDS ----------------
def main_menu(is_admin=False):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("🚘 Haydovchi"), KeyboardButton("🧍 Yo‘lovchi"))
    if is_admin:
        kb.add(KeyboardButton("👥 Haydovchilar"))
    return kb

def back_btn():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("◀️ Orqaga")
    return kb

def driver_main_kb():
    # after approval show minimal options (no "Davom etish")
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📣 E’lon berish", "⏸ To‘xtatish")
    kb.add("🆕 Yangi e’lon", "◀️ Orqaga")
    return kb

# ---------------- START ----------------
@dp.message_handler(commands=['start'])
async def start_cmd(message: types.Message):
    uid = str(message.from_user.id)
    if uid not in data['users']:
        data['users'][uid] = {
            "role": None,
            "driver_status": "none",
            "driver_paused": False,
            "state": None,
            "driver_temp": {},
            "pass_temp": {},
            "full_name": message.from_user.full_name or "",
            "username": message.from_user.username or ""
        }
        save_json(DATA_FILE, data)
    else:
        # update stored display info on each /start to keep names up-to-date
        data['users'][uid].setdefault("full_name", message.from_user.full_name or "")
        data['users'][uid].setdefault("username", message.from_user.username or "")
        # also refresh with latest values
        data['users'][uid]['full_name'] = message.from_user.full_name or data['users'][uid].get('full_name', '')
        data['users'][uid]['username'] = message.from_user.username or data['users'][uid].get('username', '')
        save_json(DATA_FILE, data)

    is_admin = int(message.from_user.id) in ADMINS
    await message.answer("<b>Salom!</b> Siz kimsiz? Tanlang:", reply_markup=main_menu(is_admin=is_admin))

# ---------------- HAYDOVCHI SECTION ----------------
@dp.message_handler(lambda m: m.text == "🚘 Haydovchi")
async def driver_section(message: types.Message):
    uid = str(message.from_user.id)

    # Agar foydalanuvchi ma'lumotlari yo'q bo'lsa yarating (xavfsizlik uchun)
    if uid not in data['users']:
        data['users'][uid] = {
            "role": None,
            "driver_status": "none",
            "driver_paused": False,
            "state": None,
            "driver_temp": {},
            "pass_temp": {},
            "full_name": message.from_user.full_name or "",
            "username": message.from_user.username or ""
        }
        save_json(DATA_FILE, data)

    # Agar user admin bo'lsa — avtomatik tasdiqlangan haydovchi qilib qo'yamiz
    if int(uid) in ADMINS or int(message.from_user.id) in ADMINS:
        # agar hali approved bo'lmasa — approved qilamiz
        if data['users'][uid].get('driver_status') != "approved":
            data['users'][uid]['driver_status'] = "approved"
            # default: pauza o'chirilgan bo'lsin
            data['users'][uid]['driver_paused'] = False
            save_json(DATA_FILE, data)
        # bevosita haydovchi bo'limiga kirishi uchun xabar
        return await message.answer("Haydovchi bo‘limi (admin):", reply_markup=driver_main_kb())

    u = data['users'].get(uid, {"driver_status": "none"})
    if u['driver_status'] == "none":
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add("📨 Haydovchi bo‘lish uchun ariza yuborish", "◀️ Orqaga")
        return await message.answer("Siz hali haydovchi emassiz. Ariza yuboring.", reply_markup=kb)
    if u['driver_status'] == "pending":
        return await message.answer("⏳ Arizangiz admin tomonidan ko‘rib chiqilmoqda…", reply_markup=back_btn())
    if u['driver_status'] == "rejected":
        kb = ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add("📨 Haydovchi bo‘lish uchun ariza yuborish", "◀️ Orqaga")
        return await message.answer("❌ Admin arizani rad etgan. Yana ariza yuborishingiz mumkin.", reply_markup=kb)
    # Tasdiqlangan haydovchi
    await message.answer("Haydovchi bo‘limi:", reply_markup=driver_main_kb())

# ---------------- YOLOVCHI SECTION ----------------
@dp.message_handler(lambda m: m.text == "🧍 Yo‘lovchi")
async def passenger_section(message: types.Message):
    uid = str(message.from_user.id)
    if uid not in data['users']:
        data['users'][uid] = {
            "role": None,
            "driver_status": "none",
            "driver_paused": False,
            "state": None,
            "driver_temp": {},
            "pass_temp": {},
            "full_name": message.from_user.full_name or "",
            "username": message.from_user.username or ""
        }
        save_json(DATA_FILE, data)
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📝 E’lon berish", "◀️ Orqaga")
    await message.answer("Yo‘lovchi bo‘limi:", reply_markup=kb)

# ---------------- HAYDOVCHI ARIZA ----------------
@dp.message_handler(lambda m: m.text == "📨 Haydovchi bo‘lish uchun ariza yuborish")
async def driver_apply(message: types.Message):
    uid = str(message.from_user.id)
    u = data['users'].get(uid)

    if u and u.get('driver_status') == "pending":
        return await message.answer("Siz allaqachon ariza yuborgansiz. Iltimos kuting.")
    if u and u.get('driver_status') == "approved":
        return await message.answer("Siz allaqachon tasdiqlangan haydovchisiz.")

    if uid not in data['users']:
        data['users'][uid] = {
            "role": None,
            "driver_status": "none",
            "driver_paused": False,
            "state": None,
            "driver_temp": {},
            "pass_temp": {},
            "full_name": message.from_user.full_name or "",
            "username": message.from_user.username or "",
            "is_premium": 0,
            "premium_until": None
        }

    data['users'][uid]['driver_status'] = "pending"
    data['users'][uid]['driver_temp']['name'] = data['users'][uid]['full_name'] or data['users'][uid]['username'] or f"ID:{uid}"

    data['admin_notifs'][uid] = []
    save_json(DATA_FILE, data)

    kb = InlineKeyboardMarkup(row_width=2)
    for admin in ADMINS:
        try:
            msg = await bot.send_message(
                admin,
                f"🚘 Haydovchilik uchun ariza:\n👤 <b>{message.from_user.full_name}</b>\n🆔 <code>{uid}</code>",
                reply_markup=InlineKeyboardMarkup().add(
                    InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve_{uid}"),
                    InlineKeyboardButton("⭐ Premium", callback_data=f"premium_{uid}"),
                    InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_{uid}")
                )
            )
            data['admin_notifs'].setdefault(uid, []).append({"admin": admin, "msg_id": msg.message_id})
        except: pass

    save_json(DATA_FILE, data)
    await message.answer("Arizangiz adminga yuborildi! ⏳ Kuting.")

@dp.message_handler(lambda m: m.text == "👥 Foydalanuvchilarni ko‘rish")
async def show_users(message: types.Message):
    kb = InlineKeyboardMarkup(row_width=1)
    for uid, u in data['users'].items():
        if u.get('driver_status') == "approved":
            name = u.get('full_name') or u.get('username') or f"ID:{uid}"
            kb.add(InlineKeyboardButton(f"{name}", callback_data=f"userinfo_{uid}"))
    await message.answer("Tasdiqlangan foydalanuvchilar:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("userinfo_"))
async def user_info(call: types.CallbackQuery):
    uid = call.data.split("_")[1]
    u = data['users'].get(uid)
    if not u:
        return await call.answer("Foydalanuvchi topilmadi!", show_alert=True)

    text = f"👤 <b>{u.get('full_name') or u.get('username')}</b>\n🆔 <code>{uid}</code>\n"
    text += f"📌 Status: {u.get('driver_status')}\n"
    if u.get('is_premium'):
        try:
            premium_until = datetime.fromisoformat(u.get('premium_until'))
            days_left = (premium_until - datetime.now()).days
            remaining = f"{days_left} kun qoldi" if days_left > 0 else "Muddati tugagan"
        except: remaining = "Noma'lum"
        text += f"⭐ Premium: Ha, {remaining}\n"
    else:
        text += f"⭐ Premium: Yo‘q\n"

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"approve_{uid}"),
        InlineKeyboardButton("⭐ Premium berish", callback_data=f"premium_{uid}"),
        InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_{uid}")
    )
    await call.message.edit_text(text, reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith(("approve_", "reject_", "premium_")))
async def manage_user(call: types.CallbackQuery):
    action, uid = call.data.split("_")
    u = data['users'].get(uid)
    if not u:
        return await call.answer("Foydalanuvchi topilmadi!", show_alert=True)

    if action == "approve":
        u['driver_status'] = "approved"
        await call.answer("Foydalanuvchi tasdiqlandi ✅", show_alert=True)
        try:
            await bot.send_message(uid, "Siz haydovchi sifatida tasdiqlandingiz! ✅")
        except: pass

    elif action == "reject":
        u['driver_status'] = "rejected"
        await call.answer("Foydalanuvchi rad etildi ❌", show_alert=True)
        try:
            await bot.send_message(uid, "Sizning arizangiz rad etildi ❌")
        except: pass

    elif action == "premium":
        await call.message.answer("Necha oyga premium berasiz? (son bilan kiriting)")
        await PremiumStates.waiting_for_month.set()
        state_data = dp.current_state(user=call.from_user.id)
        await state_data.update_data(uid=uid)

    save_json(DATA_FILE, data)

@dp.message_handler(state=PremiumStates.waiting_for_month)
async def set_premium_duration(message: types.Message, state: FSMContext):
    try:
        months = int(message.text)
    except:
        return await message.answer("Iltimos faqat son kiriting!")

    data_state = await state.get_data()
    uid = data_state['uid']
    u = data['users'].get(uid)
    if not u:
        await message.answer("Foydalanuvchi topilmadi!")
        await state.finish()
        return

    premium_until = datetime.now() + timedelta(days=30*months)
    u['is_premium'] = 1
    u['premium_until'] = premium_until.isoformat()

    await message.answer(f"{u.get('full_name')} foydalanuvchiga ⭐ Premium berildi {months} oyga!")
    try:
        await bot.send_message(uid, f"Sizga {months} oyga Premium berildi! ⭐\nMuddat: {premium_until.date()}")
    except: pass

    save_json(DATA_FILE, data)
    await state.finish()
    
# ---------------- ADMIN HAYDOVCHI TASDIQLASH ----------------
@dp.callback_query_handler(lambda c: c.data and (c.data.startswith("drv_ok:") or c.data.startswith("drv_no:") or c.data.startswith("drv_view:") or c.data.startswith("drv_remove:") or c.data.startswith("drv_keep:")))
async def admin_driver_action(call: types.CallbackQuery):
    # umumiy callback handling
    data_parts = call.data.split(":")
    action = data_parts[0]
    uid = data_parts[1] if len(data_parts) > 1 else None

    # faqat adminlar
    if int(call.from_user.id) not in ADMINS:
        await call.answer("Faqat adminlar uchun.", show_alert=True)
        return

    if action == "drv_ok":
        # tasdiqlash
        if uid not in data['users']:
            await call.answer("Foydalanuvchi topilmadi.")
            return
        data['users'][uid]['driver_status'] = "approved"
        data['users'][uid]['driver_paused'] = False
        save_json(DATA_FILE, data)

        # update: barcha adminlarga yuborilgan xabarlarni yangilash
        notifs = data.get('admin_notifs', {}).get(uid, [])
        for item in notifs:
            try:
                await bot.edit_message_text("✅ Amal bajarildi (tasdiqlandi)", item['admin'], item['msg_id'])
            except:
                pass

        # foydalanuvchiga xabar
        try:
            await bot.send_message(uid, "🎉 Admin sizni tasdiqladi! Endi haydovchi bo‘limiga kira olasiz.", reply_markup=driver_main_kb())
        except:
            pass

        # darhol bir marotaba har bir e'lonni kanallarga yuborish (faollashtirilgan e'lonlar uchun)
        # (eski ishlashni saqlab qolyapmiz)
        for ad_id, ad in list(ads['driver'].items()):
            if ad.get('user') == uid and ad.get('active', False):
                for ch in DRIVER_CHANNELS:
                    try:
                        kb = InlineKeyboardMarkup()
                        bot_username_for_url = BOT_USERNAME.lstrip('@')
                        kb.add(InlineKeyboardButton("📩 Zakaz berish", url=f"https://t.me/{bot_username_for_url}?start=zakaz"))
                        if ad.get('photo'):
                            await bot.send_photo(ch, ad['photo'], caption=ad.get('text', ''), reply_markup=kb)
                        else:
                            await bot.send_message(ch, ad.get('text', ''), reply_markup=kb)
                        ad['last_sent'] = time.time()
                    except:
                        pass
        save_json(ADS_FILE, ads)
        save_json(DATA_FILE, data)

    elif action == "drv_no":
        # rad etish
        if uid not in data['users']:
            await call.answer("Foydalanuvchi topilmadi.")
            return
        data['users'][uid]['driver_status'] = "rejected"
        data['users'][uid]['driver_paused'] = False
        save_json(DATA_FILE, data)

        # update admin notifs
        notifs = data.get('admin_notifs', {}).get(uid, [])
        for item in notifs:
            try:
                await bot.edit_message_text("❌ Amal bajarildi (rad etildi)", item['admin'], item['msg_id'])
            except:
                pass

        try:
            await bot.send_message(uid, "❌ Admin arizani rad etdi. Agar xohlasangiz qayta ariza yuborishingiz mumkin.", reply_markup=main_menu())
        except:
            pass

    elif action == "drv_view":
        # Admin haydovchilar ro'yxatidan -> bitta haydovchini ko'rish
        if uid not in data['users']:
            await call.answer("Foydalanuvchi topilmadi.")
            return
        u = data['users'][uid]
        # Topilgan haydovchining ma'lumotlari
        display_name = u.get('full_name') or u.get('driver_temp', {}).get('name') or (("@" + u['username']) if u.get('username') else f"ID:{uid}")
        txt = (
            f"🚘 <b>Haydovchi ma'lumotlari:</b>\n\n"
            f"👤 <b>Ism:</b> {display_name}\n"
            f"🆔 <code>{uid}</code>\n\n"
            f"📋 <i>Status:</i> {u.get('driver_status', '—')}\n"
        )
        # Tugmalar: chiqarib tashlash va qoldirish
        kb = InlineKeyboardMarkup()
        kb.add(
            InlineKeyboardButton("❌ Chiqarib tashlash", callback_data=f"drv_remove:{uid}"),
            InlineKeyboardButton("✅ Qoldirish", callback_data=f"drv_keep:{uid}")
        )
        # Javobni adminga yuboramiz (call.message ga edit emas, yangi xabar)
        try:
            await bot.send_message(call.from_user.id, txt, reply_markup=kb, parse_mode="HTML")
        except:
            pass

    elif action == "drv_remove":
        # admin tomonidan chiqarib tashlash (haydovchilik huquqini olib tashlash)
        if uid not in data['users']:
            await call.answer("Foydalanuvchi topilmadi.")
            return
        data['users'][uid]['driver_status'] = "rejected"
        data['users'][uid]['driver_paused'] = False
        save_json(DATA_FILE, data)
        await call.answer("Foydalanuvchi chiqarib tashlandi.")
        try:
            await bot.send_message(uid, "❌ Siz haydovchi sifatida chiqarib tashlandingiz.", reply_markup=main_menu())
        except:
            pass

    elif action == "drv_keep":
        # admin tomonidan saqlash (hech narsa o'zgarmaydi, lekin xabar beramiz)
        if uid not in data['users']:
            await call.answer("Foydalanuvchi topilmadi.")
            return
        data['users'][uid]['driver_status'] = "approved"
        save_json(DATA_FILE, data)
        await call.answer("Foydalanuvchi haydovchi sifatida qoldirildi.")
        try:
            await bot.send_message(uid, "✅ Siz haydovchi sifatida qoldirildingiz.", reply_markup=driver_main_kb())
        except:
            pass

    # tugmani bosgan admin xabarini tahrirlash (mahalliy)
    try:
        await call.message.edit_text("✅ Amal bajarildi")
    except:
        pass
    await call.answer()

# ---------------- HAYDOVCHI E’LON BERISH ----------------
@dp.message_handler(lambda m: m.text == "📣 E’lon berish")
async def driver_new_ad(message: types.Message):
    uid = str(message.from_user.id)
    if data['users'].get(uid, {}).get('driver_status') != "approved":
        return await message.answer("❌ Siz hali haydovchi emassiz yoki admin arizani tasdiqlamagan.", reply_markup=back_btn())
    data['users'][uid]['state'] = "driver_text"
    data['users'][uid]['driver_temp'] = {}
    # e'lon yaratishda avtomatik pauza o'chirilgan bo'lsin
    data['users'][uid]['driver_paused'] = False
    save_json(DATA_FILE, data)
    await message.answer("✍️ E’lon matnini yuboring:", reply_markup=back_btn())

# ---------------- DRIVER HANDLERS ----------------
@dp.message_handler(lambda m: data['users'].get(str(m.from_user.id), {}).get('state') == "driver_text")
async def driver_get_text(message: types.Message):
    uid = str(message.from_user.id)
    data['users'][uid]['driver_temp']['text'] = message.text
    data['users'][uid]['state'] = "driver_photo"
    save_json(DATA_FILE, data)
    await message.answer("📸 Mashina rasmini yuboring (majburiy):", reply_markup=back_btn())

@dp.message_handler(content_types=['photo'])
async def driver_get_photo(message: types.Message):
    uid = str(message.from_user.id)
    if data.get('users', {}).get(uid, {}).get('state') != "driver_photo":
        # foydalanuvchi hali yo'q bo'lsa, default holat
        data.setdefault('users', {})[uid] = {'state': None}
        return
    file_id = message.photo[-1].file_id
    data['users'][uid]['driver_temp']['photo'] = file_id
    data['users'][uid]['state'] = "driver_interval"
    save_json(DATA_FILE, data)
    await message.answer("⏱ Necha daqiqada qayta yuborilsin? (masalan: 1)", reply_markup=back_btn())

@dp.message_handler(lambda m: data['users'].get(str(m.from_user.id), {}).get('state') == "driver_interval")
async def driver_get_interval(message: types.Message):
    uid = str(message.from_user.id)
    try:
        interval = int(message.text)
    except:
        return await message.answer("Faqat son kiriting!", reply_markup=back_btn())
    data['users'][uid]['driver_temp']['interval'] = interval
    data['users'][uid]['state'] = "driver_confirm"
    save_json(DATA_FILE, data)
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    # Tasdiqlash/Tozalash va Orqaga — lekin "Davom etish" olib tashlandi
    kb.add("✅ Tasdiqlash", "🗑 Tozalash")
    kb.add("◀️ Orqaga")
    await message.answer("Hammasi tayyor. Tasdiqlaysizmi?", reply_markup=kb)

@dp.message_handler(lambda m: m.text == "🗑 Tozalash")
async def driver_clear(message: types.Message):
    uid = str(message.from_user.id)
    data['users'][uid]['driver_temp'] = {}
    data['users'][uid]['state'] = None
    save_json(DATA_FILE, data)
    await message.answer("Tozalandi!", reply_markup=main_menu())

@dp.message_handler(lambda m: m.text == "✅ Tasdiqlash")
async def driver_confirm(message: types.Message):
    uid = str(message.from_user.id)
    u = data['users'][uid]['driver_temp']
    # ad yaratish
    ad_id = str(time.time()).replace('.', '')
    ads['passenger'][ad_id] = {
        "user": str(message.from_user.id),
        "route": t['route'],
        "people": t['people'],
        "time": t['time'],
        "phone": t['phone'],
        "created": time.time(),
        "taken_by": None  # hali haydovchi olmagan
    }
    save_json(ADS_FILE, ads)

    data['users'][uid]['driver_temp'] = {}
    data['users'][uid]['state'] = None
    # e'lon yaratishda pauza false bo'lsin
    data['users'][uid]['driver_paused'] = False
    save_json(DATA_FILE, data)

    # xabar: e'lon yuborish boshlandi va minimal tugmalar (To'xtatish, Yangi e'lon, Orqaga)
    await message.answer("🚀 E’lon yuborish boshlandi!", reply_markup=ReplyKeyboardMarkup(resize_keyboard=True).add("⏸ To‘xtatish", "🆕 Yangi e’lon").add("◀️ Orqaga"))

# ---------------- DRIVER LOOP ----------------
async def driver_loop():
    """
    Har bir ad uchun last_sent soatiga qarab yuborishni boshqaradi.
    Bu usul tufayli bir ad yuborilgach, boshqa adlar bloklanib qolmaydi.
    Qo'shimcha: foydalanuvchi pauza qilgan bo'lsa (driver_paused) ad yuborilmaydi darhol.
    """
    while True:
        now = time.time()
        changed = False
        for ad_id, ad in list(ads['driver'].items()):
            try:
                if not ad.get('active', False):
                    continue
                # agar e'lon 1 kundan ortiq bo'lsa uni avtomatik oʻchir
                if now - ad.get('start', now) > 86400:
                    ads['driver'][ad_id]['active'] = False
                    changed = True
                    continue

                # agar foydalanuvchi pauza holatida bo'lsa — yubormaymiz
                user_uid = ad.get('user')
                if user_uid and data['users'].get(user_uid, {}).get('driver_paused', False):
                    continue

                interval_seconds = ad.get('interval', 1) * 60
                last = ad.get('last_sent', 0)
                # agar hech qachon yuborilmagan yoki interval o'tgan bo'lsa — yuborish
                if last == 0 or (now - last) >= interval_seconds:
                    for ch in DRIVER_CHANNELS:
                        try:
                            kb = InlineKeyboardMarkup()
                            bot_username_for_url = BOT_USERNAME.lstrip('@')
                            kb.add(InlineKeyboardButton("📩 Zakaz berish", url=f"https://t.me/{bot_username_for_url}?start=zakaz"))
                            if ad.get('photo'):
                                await bot.send_photo(ch, ad['photo'], caption=ad.get('text', ''), reply_markup=kb)
                            else:
                                await bot.send_message(ch, ad.get('text', ''), reply_markup=kb)
                            # belgila yuborilgan vaqtni
                            ads['driver'][ad_id]['last_sent'] = time.time()
                            changed = True
                        except:
                            pass
                    # kichik kutish — keyingi adga o'tish uchun
                    await asyncio.sleep(0.5)
            except:
                pass
        if changed:
            save_json(ADS_FILE, ads)
        await asyncio.sleep(2)

# ---------------- PAUSE / NEW AD ----------------
@dp.message_handler(lambda m: m.text == "⏸ To‘xtatish")
async def pause_driver(message: types.Message):
    uid = str(message.from_user.id)
    any_changed = False

    # 1) Mark user as paused in data (immediate effect in loop)
    if uid in data['users']:
        data['users'][uid]['driver_paused'] = True
        save_json(DATA_FILE, data)

    # 2) Also mark any active ads of this user as inactive (defensive)
    for ad in ads['driver'].values():
        if ad.get('user') == uid and ad.get('active', False):
            ad['active'] = False
            any_changed = True
    if any_changed:
        save_json(ADS_FILE, ads)

    await message.answer("⏸ Pauza qilindi.", reply_markup=main_menu())

@dp.message_handler(lambda m: m.text == "🆕 Yangi e’lon")
async def new_driver_ad(message: types.Message):
    # yangi e'lon bosilganda pauzani avtomatik o'chirish (foydalanuvchi e'lonni yana boshlamoqchi)
    uid = str(message.from_user.id)
    if uid in data['users']:
        data['users'][uid]['driver_paused'] = False
        save_json(DATA_FILE, data)
    return await driver_new_ad(message)

# ---------------- YOLOVCHI SECTION ----------------
PASS_ROUTES = [
    "🚗 Qo‘qon → Toshkent", "🚗 Toshkent → Qo‘qon",
    "🚗 Rishton → Toshkent", "🚗 Toshkent → Rishton",
    "🚗 Buvayda → Toshkent", "🚗 Toshkent → Buvayda",
    "🚗 Yangi Qo‘rg‘on → Toshkent", "🚗 Toshkent → Yangi Qo‘rg‘on",
    "🚗 Farg‘ona → Toshkent", "🚗 Toshkent → Farg‘ona",
    "🚗 Bag‘dod → Toshkent", "🚗 Toshkent → Bag‘dod"
]

@dp.message_handler(lambda m: m.text == "📝 E’lon berish")
async def passenger_ad(message: types.Message):
    uid = str(message.from_user.id)
    if uid not in data['users']:
        data['users'][uid] = {
            "role": None,
            "driver_status": "none",
            "driver_paused": False,
            "state": None,
            "driver_temp": {},
            "pass_temp": {},
            "full_name": message.from_user.full_name or "",
            "username": message.from_user.username or ""
        }
        save_json(DATA_FILE, data)
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    for r in PASS_ROUTES:
        kb.add(r)
    kb.add("🔤 Boshqa", "◀️ Orqaga")
    data['users'][uid]['state'] = "pass_route"
    save_json(DATA_FILE, data)
    await message.answer("Yo‘nalishni tanlang:", reply_markup=kb)

# ---------------- YOLOVCHI HANDLERS ----------------
@dp.message_handler(lambda m: data['users'].get(str(m.from_user.id), {}).get('state') == "pass_route")
async def pass_get_route(message: types.Message):
    uid = str(message.from_user.id)
    if message.text == "🔤 Boshqa":
        data['users'][uid]['state'] = "pass_route_custom"
        save_json(DATA_FILE, data)
        return await message.answer("Yo‘nalishni yozing:")
    if message.text not in PASS_ROUTES:
        return await message.answer("Ro‘yxatdan tanlang yoki Boshqani bosing.")
    data['users'][uid]['pass_temp'] = {"route": message.text}
    data['users'][uid]['state'] = "pass_people"
    save_json(DATA_FILE, data)
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("1 kishi","2 kishi","3 kishi","4 kishi","📦 Pochta","◀️ Orqaga")
    await message.answer("Necha kishisiz?", reply_markup=kb)

@dp.message_handler(lambda m: data['users'].get(str(m.from_user.id), {}).get('state') == "pass_route_custom")
async def pass_custom(message: types.Message):
    uid = str(message.from_user.id)
    data['users'][uid]['pass_temp'] = {"route": message.text}
    data['users'][uid]['state'] = "pass_people"
    save_json(DATA_FILE, data)
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("1 kishi","2 kishi","3 kishi","4 kishi","📦 Pochta","◀️ Orqaga")
    await message.answer("Necha kishisiz?", reply_markup=kb)

@dp.message_handler(lambda m: data['users'].get(str(m.from_user.id), {}).get('state') == "pass_people")
async def pass_people(message: types.Message):
    uid = str(message.from_user.id)
    data['users'][uid]['pass_temp']['people'] = message.text
    data['users'][uid]['state'] = "pass_date"
    save_json(DATA_FILE, data)

    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    for h in range(24):
        kb.add(f"{h:02d}:00")
    kb.add("◀️ Orqaga")
    await message.answer("Qachonga?", reply_markup=kb)

@dp.message_handler(lambda m: data['users'].get(str(m.from_user.id), {}).get('state') == "pass_date")
async def pass_date(message: types.Message):
    uid = str(message.from_user.id)
    data['users'][uid]['pass_temp']['time'] = message.text
    data['users'][uid]['state'] = "pass_phone"
    save_json(DATA_FILE, data)
    await message.answer("📞 Telefon raqamingizni kiriting (+998901234567):", reply_markup=back_btn())

@dp.message_handler(lambda m: data['users'].get(str(m.from_user.id), {}).get('state') == "pass_phone")
async def pass_phone(message: types.Message):
    uid = str(message.from_user.id)
    t = data['users'][uid]['pass_temp']
    if not message.text.startswith("+"):
        return await message.answer("Raqam + bilan boshlansin!", reply_markup=back_btn())
    t['phone'] = message.text

    # E'lon matni
    ad_text = (
        f"🚖 <b>Yo‘lovchi e’loni:</b>\n\n"
        f"📍 <b>Yo‘nalish:</b> {t['route']}\n\n"
        f"👥 <b>Odamlar soni:</b> {t['people']}\n\n"
        f"🕒 <b>Vaqt:</b> {t['time']}\n\n"
        f"📞 <b>Telefon:</b> {t['phone']}\n\n"
    )

    # submit_passenger_ad funksiyasini chaqiramiz
    await submit_passenger_ad(uid, ad_text)

    # foydalanuvchining vaqtinchalik ma'lumotini tozalaymiz
    data['users'][uid]['pass_temp'] = {}
    data['users'][uid]['state'] = None
    save_json(DATA_FILE, data)

async def submit_passenger_ad(user_id, ad_text):
    ad_id = str(int(time.time()*1000))  # unique id
    ads['passenger'][ad_id] = {
        "user": str(user_id),
        "text": ad_text,
        "created": time.time(),
        "taken_by": None
    }
    save_json(ADS_FILE, ads)

    # Foydalanuvchiga xabar
    await bot.send_message(user_id, "✅ Eloningiz shofirlarga yuborildi. Iltimos, shofir javobini kuting.")

    kb = InlineKeyboardMarkup()
    # Guruhdagi xabarda tugma callback ishlatadi (botga kirish uchun)
    kb.add(InlineKeyboardButton("📥 Ko‘rish", callback_data=f"view_pass:{ad_id}"))

    for ch in PASSENGER_CHANNELS:
        msg = await bot.send_message(ch, f"\n{ad_text[:100]} ...", reply_markup=kb)
        ads['passenger'][ad_id]['group_msg_id'] = msg.message_id

    save_json(ADS_FILE, ads)


from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- Guruhdagi korish tugmasi (faqat botga) ---
@dp.callback_query_handler(lambda c: c.data.startswith("view_pass:"))
async def view_passenger(call: types.CallbackQuery):
    user_id = call.from_user.id

    cursor.execute("SELECT is_premium, premium_until FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()

    from datetime import datetime

    if not user:
        return

    is_premium, premium_until = user

    if not is_premium or datetime.strptime(premium_until, "%Y-%m-%d %H:%M:%S") < datetime.now():
        await call.answer("❌ Premium kerak!", show_alert=True)
        return
    ad_id = call.data.split(":")[1]
    ad = ads['passenger'].get(ad_id)
    if not ad:
        return await call.answer("Topilmadi", show_alert=True)

    # Foydalanuvchiga bot orqali e’lonni yuborish
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Qabul qilish", callback_data=f"take_pass:{ad_id}"))

    await bot.send_message(call.from_user.id, ad['text'], reply_markup=kb)
    await call.answer("E’lon botga ochildi ✅", show_alert=True)


@dp.callback_query_handler(lambda c: c.data.startswith("view_pass:"))
async def view_single_pass(call: types.CallbackQuery):
    ad_id = call.data.split(":")[1]
    ad = ads['passenger'].get(ad_id)
    if not ad:
        return await call.answer("Topilmadi", show_alert=True)

    # Guruhdagi xabarni o‘zgartirmaymiz, faqat bot ichida foydalanuvchiga ko‘rsatamiz
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Qabul qilish", callback_data=f"take_pass:{ad_id}"))

    await call.message.answer(ad['text'], reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("take_pass:"))
async def take_pass(call: types.CallbackQuery):
    uid = str(call.from_user.id)
    ad_id = call.data.split(":")[1]
    ad = ads['passenger'].get(ad_id)
    if not ad:
        return await call.answer("Topilmadi", show_alert=True)

    if ad.get('taken_by'):
        return await call.answer("❌ Boshqa foydalanuvchi allaqachon qabul qilgan.", show_alert=True)

    # Shu foydalanuvchi qabul qildi
    ad['taken_by'] = uid
    save_json(ADS_FILE, ads)

    # Guruhdagi eslatma tugmasini o'zgartirish
    for ch in PASSENGER_CHANNELS:
        try:
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("✅ Qabul qilindi", callback_data="none"))
            await bot.edit_message_reply_markup(chat_id=ch, message_id=ad.get('group_msg_id'), reply_markup=kb)
        except:
            pass

    await call.message.edit_reply_markup(reply_markup=None)  # o'zida tugmani olib tashlaymiz
    await call.message.answer("✅ Siz e’lonni qabul qildingiz.")


# ---------------- YOLOVCHI CALLBACKS ----------------
@dp.callback_query_handler(lambda c: c.data.startswith("view_pass:"))
async def view_passenger(call: types.CallbackQuery):
    ad_id = call.data.split(":")[1]
    ad = ads['passenger'].get(ad_id)
    if not ad:
        return await call.answer("Topilmadi", show_alert=True)

    # Agar e'lon boshqa foydalanuvchi tomonidan qabul qilingan bo'lsa
    if ad.get('taken_by'):
        return await call.answer("❌ Ushbu e'lon allaqachon qabul qilingan.", show_alert=True)

    # Botga shaxsiy chatda faqat shu foydalanuvchi uchun
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Qabul qilish", callback_data=f"take_pass:{ad_id}"))

    await call.from_user.send_message(ad['text'], reply_markup=kb)
    await call.answer("E’lon botga ochildi ✅", show_alert=True)

# --- Qabul qilish tugmasi ---
@dp.callback_query_handler(lambda c: c.data.startswith("take_pass:"))
async def take_passenger(call: types.CallbackQuery):
    uid = str(call.from_user.id)
    ad_id = call.data.split(":")[1]
    ad = ads['passenger'].get(ad_id)
    if not ad:
        return await call.answer("Topilmadi", show_alert=True)

    if ad.get('taken_by'):
        return await call.answer("❌ Boshqa foydalanuvchi allaqachon qabul qilgan.", show_alert=True)

    # Shu foydalanuvchi qabul qildi
    ad['taken_by'] = uid
    save_json(ADS_FILE, ads)

    # Guruhdagi eslatmani "Qabul qilindi" ga o'zgartirish
    for ch in PASSENGER_CHANNELS:
        try:
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("✅ Qabul qilindi", callback_data="none"))
            await bot.edit_message_reply_markup(chat_id=ch, message_id=ad.get('group_msg_id'), reply_markup=kb)
        except:
            pass

    # Faqat shu foydalanuvchiga xabar
    await call.message.edit_reply_markup(reply_markup=None)
    await call.message.answer("✅ Siz e’lonni qabul qildingiz.")

@dp.message_handler(lambda m: m.text == "📥 Yo‘lovchi e’lonlari")
async def passenger_ads_menu(message: types.Message):
    uid = str(message.from_user.id)
    if data['users'].get(uid, {}).get('driver_status') != "approved" and int(uid) not in ADMINS:
        return await message.answer("❌ Sizga ruxsat yo‘q")

    kb = InlineKeyboardMarkup()
    for ad_id, ad in ads.get('passenger', {}).items():
        # faqat faol e'lonlar (24 soat ichida)
        if time.time() - ad['created'] > 86400:
            continue
        kb.add(InlineKeyboardButton("📥 Ko‘rish", callback_data=f"view_pass:{ad_id}"))

    if not kb.inline_keyboard:
        await message.answer("❌ Faol yo‘lovchi e’lonlari yo‘q.")
    else:
        await message.answer("📥 Yo‘lovchi e’lonlari:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith("view_pass:"))
async def view_pass(call: types.CallbackQuery):
    ad_id = call.data.split(":")[1]
    ad = ads['passenger'].get(ad_id)
    if not ad:
        await call.answer("E’lon topilmadi", show_alert=True)
        return

    # Agar e’lon allaqachon boshqa haydovchi tomonidan olingan bo‘lsa
    if ad.get('taken_by') and ad['taken_by'] != str(call.from_user.id):
        await call.answer("❌ Bu e’lon boshqa haydovchi tomonidan olingan.", show_alert=True)
        return

    # E’lonni hozirgi haydovchiga ko‘rsatish
    text = (
        f"🚖 Yo‘lovchi e’loni:\n\n"
        f"📍 Yo‘nalish: {ad['route']}\n"
        f"👥 Odamlar soni: {ad['people']}\n"
        f"🕒 Vaqt: {ad['time']}\n"
        f"📞 Telefon: {ad['phone']}\n"
    )
    await bot.send_message(call.from_user.id, text)

    # E’lonni shu foydalanuvchi olgan deb belgilaymiz
    ad['taken_by'] = str(call.from_user.id)
    save_json(ADS_FILE, ads)

    await call.answer("✅ E’lon sizga berildi", show_alert=True)

@dp.message_handler(lambda m: m.text == "📥 Yo‘lovchi e’lonlari")
async def my_passenger_ads(message: types.Message):
    uid = str(message.from_user.id)
    text = "📥 Yo‘lovchi e’lonlari:\n\n"
    for ad_id, ad in ads['passenger'].items():
        if ad.get('taken_by') is None:  # hali hech kim olmagan e’lonlar
            text += f"• {ad['route']} - {ad['people']} kishi\n"
    if text == "📥 Yo‘lovchi e’lonlari:\n\n":
        text = "Yo‘lovchi e’lonlari yo‘q."
    await message.answer(text)

@dp.callback_query_handler(lambda c: c.data.startswith("premium_"))
async def premium_choose(call: types.CallbackQuery):
    user_id = call.data.split("_")[1]

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("1 oy", callback_data=f"premtime_1_{user_id}"),
        InlineKeyboardButton("3 oy", callback_data=f"premtime_3_{user_id}"),
        InlineKeyboardButton("1 yil", callback_data=f"premtime_12_{user_id}"),
        InlineKeyboardButton("Boshqa", callback_data=f"premtime_custom_{user_id}")
    )

    await call.message.edit_text("⏳ Necha oyga premium qilinsin?", reply_markup=kb)

from datetime import datetime, timedelta

@dp.callback_query_handler(lambda c: c.data.startswith("premtime_"))
async def set_premium(call: CallbackQuery):
    parts = call.data.split("_")
    months = int(parts[1])
    user_id = int(parts[2])

    until = datetime.now() + timedelta(days=30*months)

    cursor.execute(
        "UPDATE users SET is_premium=1, premium_until=? WHERE user_id=?",
        (until.strftime("%Y-%m-%d %H:%M:%S"), user_id)
    )
    conn.commit()

    await call.message.edit_text(f"⭐ {months} oyga premium qilindi!")

@dp.callback_query_handler(lambda c: c.data == "premium_users")
async def show_premium(call: CallbackQuery):
    cursor.execute("SELECT user_id FROM users WHERE is_premium=1")
    users = cursor.fetchall()

    text = "⭐ Premium foydalanuvchilar:\n\n"

    for u in users:
        text += f"👤 {u[0]}\n"

    await call.message.edit_text(text)

@dp.callback_query_handler(lambda c: c.data.startswith("removeprem_"))
async def remove_premium(call: CallbackQuery):
    user_id = int(call.data.split("_")[1])

    cursor.execute(
        "UPDATE users SET is_premium=0, premium_until=NULL WHERE user_id=?",
        (user_id,)
    )
    conn.commit()

    await call.message.edit_text("✅ Oddiyga tushirildi")

@dp.message_handler(commands=['start'])
async def start_handler(message: types.Message):
    user_id = str(message.from_user.id)

    if user_id not in data['users']:
        data['users'][user_id] = {
            "role": None,
            "driver_status": "none",
            "driver_paused": False,
            "state": None,
            "driver_temp": {},
            "pass_temp": {},
            "full_name": message.from_user.full_name or "",
            "username": message.from_user.username or "",
            "is_premium": 0,
            "premium_until": None
        }
        save_json(DATA_FILE, data)

    await message.answer("Botga xush kelibsiz!")

# ---------------- UNIVERSAL "ORQAGA" HANDLER ----------------
@dp.message_handler(lambda m: m.text == "◀️ Orqaga")
async def go_back(message: types.Message):
    uid = str(message.from_user.id)
    # reset any temporary state
    if uid in data['users']:
        data['users'][uid]['state'] = None
        data['users'][uid]['driver_temp'] = {}
        data['users'][uid]['pass_temp'] = {}
        save_json(DATA_FILE, data)
    is_admin = int(message.from_user.id) in ADMINS
    await message.answer("Asosiy menyuga qaytdingiz:", reply_markup=main_menu(is_admin=is_admin))

# ---------------- ADMINS: HAYDOVCHILAR RO'YXATI ----------------
@dp.message_handler(lambda m: m.text == "👥 Haydovchilar")
async def admin_drivers_list(message: types.Message):
    if int(message.from_user.id) not in ADMINS:
        return await message.answer("Faqat adminlar uchun.")
    # barcha tasdiqlangan haydovchilarni topamiz
    inline = InlineKeyboardMarkup()
    found = False
    for uid, u in data['users'].items():
        if u.get('driver_status') == "approved":
            # display name logic: prefer stored full_name, then username, then driver_temp.name, then ID
            display = u.get('full_name') or (("@" + u['username']) if u.get('username') else u.get('driver_temp', {}).get('name') or f"ID:{uid}")
            inline.add(InlineKeyboardButton(display, callback_data=f"drv_view:{uid}"))
            found = True
    if not found:
        return await message.answer("Hozircha tasdiqlangan haydovchilar yo'q.")
    await message.answer("Tasdiqlangan haydovchilar:", reply_markup=None)
    await bot.send_message(message.from_user.id, "Ro'yxat:", reply_markup=inline)

# ---------------- START BOT ----------------
if __name__ == "__main__":
    import asyncio
    loop = asyncio.get_event_loop()
    loop.create_task(driver_loop())
    executor.start_polling(dp, skip_updates=True)