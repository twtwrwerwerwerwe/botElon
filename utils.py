# -*- coding: utf-8 -*-
"""utils.py — yordamchi funksiyalar."""
import time
import uuid


def normalize_phone(raw: str):
    """
    Telefon raqamni +998XXXXXXXXX formatiga keltiradi.
    Agar raqam noto'g'ri bo'lsa None qaytaradi.

    Qo'llab-quvvatlaydi:
      +998901234567
      998901234567
      901234567        -> +998901234567 (avtomatik +998 qo'shiladi)
      +7 / boshqa davlat kodlari ham qabul qilinadi
    """
    if not raw:
        return None
    raw = raw.strip()
    digits = "".join(ch for ch in raw if ch.isdigit())

    if not digits:
        return None

    if raw.startswith("+998") and len(digits) == 12:
        return "+" + digits
    if digits.startswith("998") and len(digits) == 12:
        return "+" + digits
    if len(digits) == 9:  # masalan 901234567 -> +998 qo'shiladi
        return "+998" + digits
    if raw.startswith("+") and len(digits) >= 9:
        return "+" + digits
    # boshqa holatlarda ham, agar 9-15 raqamdan iborat bo'lsa qabul qilamiz
    if 9 <= len(digits) <= 15:
        return "+998" + digits[-9:] if len(digits) == 9 else "+" + digits
    return None


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def now_ts() -> float:
    return time.time()


def fmt_date(ts: float) -> str:
    if not ts:
        return "—"
    return time.strftime("%d.%m.%Y %H:%M", time.localtime(ts))


def fmt_money(amount: int) -> str:
    return f"{amount:,.0f}".replace(",", " ") + " so‘m"


def seconds_to_human(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    if hours > 0:
        return f"{hours} soat {minutes} daqiqa"
    return f"{minutes} daqiqa"


def display_name(user: dict, uid: str) -> str:
    if user.get("full_name"):
        return user["full_name"]
    if user.get("username"):
        return "@" + user["username"]
    return f"ID:{uid}"
