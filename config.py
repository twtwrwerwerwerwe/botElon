# -*- coding: utf-8 -*-
"""
config.py — Botning barcha sozlamalari shu yerda joylashgan.
Faqat shu faylni tahrirlab, botning token, admin, guruh va narxlarini
o'zgartirishingiz mumkin — boshqa fayllarga tegishning hojati yo'q.
"""
from pathlib import Path

# ==================== BOT ====================
TOKEN = "8212255968:AAETRL91puhUESsCP7eFKm7pE51tKgm6SQo"
BOT_USERNAME = "RishtonBuvaydaBogdod_bot"  # @ belgisiz

# ==================== ADMIN ====================
ADMINS = [6731395876, 6302873072]                # admin(lar) telegram ID si
ADMIN_PHONE = "+998940081100"         # admin telefon raqami (foydalanuvchiga ko'rsatiladi)
ADMIN_USERNAME = "@Taksi_2300"     # admin telegram username (foydalanuvchiga ko'rsatiladi)

# ==================== GURUH / KANALLAR ====================
DRIVER_CHANNELS = [-1003292352387, -1002558743974, -1002258300973, -1001168970257, -1002401105872, -1002071453667, -1002336638025, -1002280167812, -1001742021244, -1002671120549, -1002349130903,-1001845354641, -1002196478283, -1002454716537]     # haydovchilar e'lonlari shu yerga tushadi
PASSENGER_CHANNELS = [-1003871778653]  # yo'lovchilar e'lonlari shu yerga tushadi

# ==================== FAYLLAR ====================
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "storage_data"
DATA_FILE = DATA_DIR / "data.json"
ADS_FILE = DATA_DIR / "ads.json"
PAYMENTS_FILE = DATA_DIR / "payments.json"
FSM_FILE = DATA_DIR / "fsm.json"

# ==================== TO'LOV — CHEK ORQALI ====================
# "Chek orqali to'lov" tanlanganda foydalanuvchiga shu karta ko'rsatiladi.
PAYMENT_CARD = {
    "number": "5614681015871225",
    "owner": "Abdullayev Imomiazam",
    "phone": "+998940081100",
}

# ==================== TO'LOV — CLICK / PAYME ====================
# Agar quyidagi merchant ID'lar kiritilmagan (None) bo'lsa, bot foydalanuvchiga
# "Bu to'lov usuli hozircha vaqtinchalik mavjud emas" deb avtomatik xabar beradi.
# Merchant ID'larni sozlagandan so'ng shu yerga kiritsangiz, avto-to'lov ishga tushadi.
CLICK_MERCHANT_ID = None
PAYME_MERCHANT_ID = None

# ==================== TARIFLAR ====================
# key -> {label: ko'rinadigan nom, days: necha kunlik obuna (None = umrbod), price: narxi so'mda}
TARIFFS = {
    "1m": {"label": "1 oylik", "days": 31, "price": 100_000},
    "2m": {"label": "2 oylik", "days": 62, "price": 200_000},
    "5m": {"label": "5 oylik", "days": 153, "price": 500_000},
    "lifetime": {"label": "♾ Umrbod", "days": None, "price": 2_000_000},
}

# ==================== ESLATMALAR / VAQT SOZLAMALARI ====================
REMINDER_DAYS_BEFORE = 3          # obuna tugashiga necha kun qolganda eslatma yuboriladi
BACKGROUND_LOOP_INTERVAL = 30     # fon jarayoni necha soniyada bir tekshiradi (soniya)

AD_AUTO_STOP_HOURS = 24           # haydovchi e'loni necha soatdan keyin avtomatik to'xtaydi
AD_REMINDER_HOURS = 12            # necha soatdan keyin eslatma yuboriladi (to'xtatilmagan bo'lsa)

# Yo'lovchi yo'nalishlari (eskisi saqlab qolindi)
PASSENGER_ROUTES = [
    "Qo‘qon → Toshkent", "Toshkent → Qo‘qon",
    "Rishton → Toshkent", "Toshkent → Rishton",
    "Buvayda → Toshkent", "Toshkent → Buvayda",
    "Yangi Qo‘rg‘on → Toshkent", "Toshkent → Yangi Qo‘rg‘on",
    "Farg‘ona → Toshkent", "Toshkent → Farg‘ona",
    "Bag‘dod → Toshkent", "Toshkent → Bag‘dod",
]

# Haydovchi e'loni necha daqiqada bir qayta yuborilishi mumkin bo'lgan variantlar
AD_INTERVALS = [5, 10, 15, 20, 30]

# ==================== JONLI (ANIMATSIYALI) STIKERLAR ====================
# Bu yerga animatsiyali stikerning file_id'sini kiriting — shunda bot
# muhim daqiqalarda (haydovchi tasdiqlandi, e'lon yuborildi, to'lov
# tasdiqlandi va h.k.) shu stikerni yuboradi. Bo'sh ("") qoldirilsa,
# bot shunchaki stiker yubormaydi — hech qanday xatolik chiqmaydi.
#
# STIKER FILE_ID QANDAY OLINADI (juda oson):
#   1) Botga istalgan animatsiyali stikerni yuboring (shaxsiy chatda).
#   2) Agar siz ADMINS ro'yxatida bo'lsangiz, bot sizga o'sha
#      stikerning file_id'sini avtomatik yozib beradi.
#   3) Shu ID'ni pastdagi mos qatorga qo'yib qo'ying.
STICKERS = {
    "success": "",            # umumiy muvaffaqiyat (masalan ✅ tasdiqlandi)
    "driver_approved": "",    # haydovchi tasdiqlanganda
    "ad_posted": "",          # e'lon guruhga yuborilganda
    "payment_approved": "",   # to'lov tasdiqlanganda
    "order_taken": "",        # yo'lovchi zakazi qabul qilinganda
}

