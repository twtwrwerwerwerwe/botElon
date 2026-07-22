# -*- coding: utf-8 -*-
"""
bot_instance.py — Bot va Dispatcher ning YAGONA nusxasi.

Eski koddagi muammolardan biri: bot/dp turli joylarda qayta-qayta
yaratilishi mumkin edi. Endi butun loyihada faqat shu yerdagi bitta
`bot` va `dp` obyekti ishlatiladi — barcha handler fayllari shu yerdan
import qiladi.

MUHIM: FSM holatlari uchun oddiy MemoryStorage EMAS, balki diskka
yozadigan FileStorage ishlatiladi — shunda Railway konteyner qayta
ishga tushganda ham (redeploy, uyqudan uyg'onish va h.k.) foydalanuvchi
to'xtagan joyidan (masalan, telefon raqam kiritish bosqichi) davom
etaveradi, bot "jim" qolib ketmaydi.
"""
from aiogram import Bot, Dispatcher

from config import TOKEN, FSM_FILE
from storage import FileStorage

bot = Bot(token=TOKEN, parse_mode="HTML")
dp = Dispatcher(bot, storage=FileStorage(FSM_FILE))
