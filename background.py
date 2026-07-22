# -*- coding: utf-8 -*-
"""
background.py — fonda ishlaydigan vazifalar:
  1) Haydovchi e'lonlarini intervalga ko'ra kanalga qayta yuborish
  2) E'lon 12 soat bo'lganda eslatma, 24 soatda avtomatik to'xtatish
  3) Obuna muddati tugashiga 3 kun qolganda va tugagan kunda eslatma,
     muddat tugagach botdan foydalanish huquqini olib qo'yish

MUHIM: guruhga qayta yuborish endi handlers.driver._broadcast_driver_ad
funksiyasi orqali amalga oshiriladi — shu bilan xatolik sodir bo'lsa
(masalan bot guruhda admin emas) jimgina yutib yuborilmaydi, aksincha
log'ga yoziladi va zarur bo'lsa qayta urinadi.
"""
import asyncio
import time
import logging

from bot_instance import bot
from config import (
    AD_AUTO_STOP_HOURS, AD_REMINDER_HOURS,
    REMINDER_DAYS_BEFORE, BACKGROUND_LOOP_INTERVAL,
)
from storage import ads_store, users_store, save_ads, save_users, get_user
from utils import fmt_date
from keyboards import main_menu_kb, tariff_kb

log = logging.getLogger(__name__)


async def driver_ads_loop():
    """Haydovchi e'lonlarini davriy ravishda kanalga yuboradi."""
    from handlers.driver import _broadcast_driver_ad  # aylanma import'dan qochish uchun shu yerda

    while True:
        now = time.time()
        changed = False
        for ad_id, ad in list(ads_store.data["driver"].items()):
            try:
                if not ad.get("active", False):
                    continue

                elapsed = now - ad.get("start", now)

                # 24 soatdan keyin avtomatik to'xtatish
                if elapsed > AD_AUTO_STOP_HOURS * 3600:
                    ad["active"] = False
                    changed = True
                    uid = ad.get("user")
                    if uid:
                        get_user(uid)["driver_paused"] = True
                        try:
                            await bot.send_message(
                                int(uid),
                                f"⏹ E’loningiz {AD_AUTO_STOP_HOURS} soat o‘tgani sababli "
                                "avtomatik to‘xtatildi. Xohlasangiz qayta e’lon berishingiz mumkin.",
                                reply_markup=main_menu_kb(),
                            )
                        except Exception:
                            pass
                    continue

                # 12 soatlik eslatma (faqat bir marta)
                if elapsed > AD_REMINDER_HOURS * 3600 and not ad.get("reminded_12h"):
                    ad["reminded_12h"] = True
                    changed = True
                    uid = ad.get("user")
                    if uid:
                        try:
                            remaining_h = AD_AUTO_STOP_HOURS - AD_REMINDER_HOURS
                            await bot.send_message(
                                int(uid),
                                f"⏰ E’loningiz aylanayotganiga {AD_REMINDER_HOURS} soat bo‘ldi.\n"
                                "Agar esingizdan chiqqan bo‘lsa, to‘xtatib qo‘ying 🙏\n"
                                f"Aks holda yana {remaining_h} soatdan keyin avtomatik to‘xtatiladi.",
                            )
                        except Exception:
                            pass

                # foydalanuvchi pauza qilgan bo'lsa yubormaymiz
                uid = ad.get("user")
                if uid and users_store.data["users"].get(uid, {}).get("driver_paused", False):
                    continue

                interval_seconds = ad.get("interval", 5) * 60
                last = ad.get("last_sent", 0)
                if last == 0 or (now - last) >= interval_seconds:
                    ok, err = await _broadcast_driver_ad(ad_id)
                    if not ok:
                        log.error("E'lon %s guruhga yuborilmadi: %s", ad_id, err)
                    changed = True
                    await asyncio.sleep(0.4)
            except Exception:
                log.exception("driver_ads_loop ichida kutilmagan xatolik (ad_id=%s)", ad_id)

        if changed:
            await save_ads()
        await asyncio.sleep(BACKGROUND_LOOP_INTERVAL)


async def subscription_watch_loop():
    """Haydovchilar obunasi muddatini kuzatib boradi va eslatma yuboradi."""
    while True:
        now = time.time()
        changed = False
        for uid, u in list(users_store.data["users"].items()):
            try:
                sub = u.get("subscription") or {}
                if not sub.get("active") or sub.get("end") is None:
                    continue  # umrbod yoki faol emas

                remaining = sub["end"] - now

                if remaining <= 0:
                    sub["active"] = False
                    u["driver_paused"] = True
                    changed = True
                    for ad in ads_store.data["driver"].values():
                        if ad.get("user") == uid:
                            ad["active"] = False
                    try:
                        await bot.send_message(
                            int(uid),
                            "⛔️ Obunangiz muddati tugadi. Botdan haydovchi sifatida "
                            "foydalanish uchun obunani yangilang.",
                            reply_markup=tariff_kb(),
                        )
                    except Exception:
                        pass
                    continue

                if remaining <= 86400 and not sub.get("reminded_expired"):
                    sub["reminded_expired"] = True
                    changed = True
                    try:
                        await bot.send_message(
                            int(uid),
                            "⚠️ Obunangizning to‘lov kuni keldi! Vaqtingiz tugadi. "
                            "Iltimos, obunani yangilang, aks holda haydovchi bo‘limidan "
                            "foydalanish to‘xtatiladi.",
                            reply_markup=tariff_kb(),
                        )
                    except Exception:
                        pass
                elif remaining <= REMINDER_DAYS_BEFORE * 86400 and not sub.get("reminded_3d"):
                    sub["reminded_3d"] = True
                    changed = True
                    try:
                        await bot.send_message(
                            int(uid),
                            f"⏰ Obunangiz tugashiga {REMINDER_DAYS_BEFORE} kun qoldi "
                            f"({fmt_date(sub['end'])}). Vaqtida yangilashni unutmang!",
                        )
                    except Exception:
                        pass
            except Exception:
                log.exception("subscription_watch_loop ichida kutilmagan xatolik (uid=%s)", uid)

        if changed:
            await save_ads()
            await save_users()
        await asyncio.sleep(BACKGROUND_LOOP_INTERVAL)
