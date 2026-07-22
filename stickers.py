# -*- coding: utf-8 -*-
"""stickers.py — jonli (animatsiyali) stikerlarni xavfsiz yuborish."""
import logging
from bot_instance import bot
from config import STICKERS

log = logging.getLogger(__name__)


async def send_sticker_safe(chat_id: int, key: str):
    """
    STICKERS[key] sozlangan bo'lsa shu stikerni yuboradi.
    Sozlanmagan yoki yuborishda xatolik chiqsa — jim o'tkazib yuboradi,
    botning asosiy funksiyasiga hech qanday ta'sir qilmaydi.
    """
    sticker_id = STICKERS.get(key)
    if not sticker_id:
        return
    try:
        await bot.send_sticker(chat_id, sticker_id)
    except Exception as e:
        log.warning("Stiker yuborilmadi (%s): %s", key, e)
