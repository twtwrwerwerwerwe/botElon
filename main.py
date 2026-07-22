# -*- coding: utf-8 -*-
"""
main.py — botni ishga tushirish nuqtasi.

Ishga tushirish:
    python main.py
"""
import logging
import asyncio

from aiogram.utils import executor
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats

from bot_instance import bot, dp
import background

# Barcha handlerlarni ro'yxatdan o'tkazamiz (import qilish orqali,
# chunki har bir modul dp.message_handler / dp.callback_query_handler
# dekoratorlari yordamida o'zini o'zi ro'yxatdan o'tkazadi).
from handlers import start          # noqa: F401  /start, Orqaga
from handlers import driver_admin   # noqa: F401  ariza tasdiqlash, haydovchilar ro'yxati
from handlers import driver         # noqa: F401  telefon, e'lon berish, to'xtatish
from handlers import payment        # noqa: F401  tariflar, to'lov usullari
from handlers import payment_admin  # noqa: F401  admin to'lov tasdiqlash
from handlers import passenger      # noqa: F401  yo'lovchi bo'limi
from handlers import fallback       # noqa: F401  hech narsa mos kelmasa - oxirgi himoya

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")


async def on_startup(dispatcher):
    # MUHIM: bot buyruqlari ("/" bosilganda chiqadigan menyu) FAQAT
    # shaxsiy chatda ko'rinishi kerak. Guruh/kanallarda bu menyu
    # chiqmasligi uchun guruh doirasidagi buyruqlar ro'yxati bo'sh
    # qilib qo'yiladi.
    try:
        await bot.set_my_commands(
            [BotCommand("start", "Botni ishga tushirish")],
            scope=BotCommandScopeAllPrivateChats(),
        )
        await bot.set_my_commands([], scope=BotCommandScopeAllGroupChats())
    except Exception as e:
        logging.warning("Bot buyruqlarini sozlashda xatolik: %s", e)

    asyncio.create_task(background.driver_ads_loop())
    asyncio.create_task(background.subscription_watch_loop())
    logging.info("Bot ishga tushdi ✅")


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)