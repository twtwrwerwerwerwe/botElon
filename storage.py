# -*- coding: utf-8 -*-
"""
storage.py — JSON asosidagi oddiy, xavfsiz ma'lumot saqlash qatlami.

Eski koddagi asosiy muammo: bir nechta turli joyларда load_json/save_json
qayta-qayta e'lon qilingan va bir-birini ustiga yozib, xatolarga sabab
bo'lgan edi. Endi butun loyihada FAQAT shu yerdagi bitta JSONStore
klassi ishlatiladi.
"""
import copy
import json
import asyncio
from pathlib import Path

from aiogram.contrib.fsm_storage.memory import BaseStorage


class JSONStore:
    """Diskga yoziladigan oddiy kalit-qiymat ombori (async-xavfsiz)."""

    def __init__(self, path: Path, default: dict):
        self.path = Path(path)
        self._lock = asyncio.Lock()
        self.data = self._load(default)

    def _load(self, default: dict) -> dict:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text(
                json.dumps(default, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            return json.loads(json.dumps(default))
        try:
            raw = self.path.read_text(encoding="utf-8")
            loaded = json.loads(raw)
            if not isinstance(loaded, dict):
                return json.loads(json.dumps(default))
            # yetishmayotgan kalitlarni to'ldirish (eski fayllar bilan moslik uchun)
            for k, v in default.items():
                loaded.setdefault(k, v)
            return loaded
        except Exception:
            return json.loads(json.dumps(default))

    async def save(self):
        async with self._lock:
            tmp_path = self.path.with_suffix(".tmp")
            tmp_path.write_text(
                json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            tmp_path.replace(self.path)


class FileStorage(BaseStorage):
    """
    Diskka yozadigan FSM (holat) ombori.

    MUHIM: aiogram'ning standart MemoryStorage'i bot qayta ishga tushganda
    (Railway qayta deploy qilganda, konteyner uxlab-uyg'onganda va h.k.)
    barcha foydalanuvchilarning "qaysi bosqichda turgani" ma'lumotini
    butunlay yo'qotadi — masalan, kimdir telefon raqamini kiritayotgan
    payt bot qayta ishga tushsa, u holat unutiladi va foydalanuvchi
    yuborgan xabarga bot HECH QANDAY javob bermay qoladi ("hech nima
    chiqmayabdi" degan muammoning aynan asosiy sababi shu edi).

    Shu klass har bir o'zgarishni darhol diskka (`storage_data/fsm.json`)
    yozib boradi, shuning uchun bot qayta ishga tushsa ham foydalanuvchi
    to'xtagan joyidan davom etaveradi.
    """

    def __init__(self, path):
        self.path = Path(path)
        self._lock = asyncio.Lock()
        self.data = self._load()

    def _load(self) -> dict:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text("{}", encoding="utf-8")
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_sync(self):
        tmp_path = self.path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")
        tmp_path.replace(self.path)

    async def _save(self):
        async with self._lock:
            self._save_sync()

    def resolve_address(self, chat, user):
        chat_id, user_id = map(str, self.check_address(chat=chat, user=user))
        if chat_id not in self.data:
            self.data[chat_id] = {}
        if user_id not in self.data[chat_id]:
            self.data[chat_id][user_id] = {"state": None, "data": {}, "bucket": {}}
        return chat_id, user_id

    async def get_state(self, *, chat=None, user=None, default=None):
        chat, user = self.resolve_address(chat=chat, user=user)
        return self.data[chat][user].get("state", self.resolve_state(default))

    async def get_data(self, *, chat=None, user=None, default=None):
        chat, user = self.resolve_address(chat=chat, user=user)
        return copy.deepcopy(self.data[chat][user]["data"])

    async def update_data(self, *, chat=None, user=None, data=None, **kwargs):
        if data is None:
            data = {}
        chat, user = self.resolve_address(chat=chat, user=user)
        self.data[chat][user]["data"].update(data, **kwargs)
        await self._save()

    async def set_state(self, *, chat=None, user=None, state=None):
        chat, user = self.resolve_address(chat=chat, user=user)
        self.data[chat][user]["state"] = self.resolve_state(state)
        await self._save()

    async def set_data(self, *, chat=None, user=None, data=None):
        chat, user = self.resolve_address(chat=chat, user=user)
        self.data[chat][user]["data"] = copy.deepcopy(data or {})
        await self._save()

    async def reset_state(self, *, chat=None, user=None, with_data=True):
        chat, user = self.resolve_address(chat=chat, user=user)
        self.data[chat][user]["state"] = None
        if with_data:
            self.data[chat][user]["data"] = {}
        await self._save()

    def has_bucket(self):
        return True

    async def get_bucket(self, *, chat=None, user=None, default=None):
        chat, user = self.resolve_address(chat=chat, user=user)
        return copy.deepcopy(self.data[chat][user]["bucket"])

    async def set_bucket(self, *, chat=None, user=None, bucket=None):
        chat, user = self.resolve_address(chat=chat, user=user)
        self.data[chat][user]["bucket"] = copy.deepcopy(bucket or {})
        await self._save()

    async def update_bucket(self, *, chat=None, user=None, bucket=None, **kwargs):
        if bucket is None:
            bucket = {}
        chat, user = self.resolve_address(chat=chat, user=user)
        self.data[chat][user]["bucket"].update(bucket, **kwargs)
        await self._save()

    async def close(self):
        self._save_sync()

    async def wait_closed(self):
        return True


# ==================== OMBORLAR ====================
from config import DATA_FILE, ADS_FILE, PAYMENTS_FILE  # noqa: E402

users_store = JSONStore(DATA_FILE, {"users": {}, "admin_notifs": {}, "ad_counter": 0})
ads_store = JSONStore(ADS_FILE, {"driver": {}, "passenger": {}})
payments_store = JSONStore(PAYMENTS_FILE, {"payments": {}, "payment_notifs": {}})


DEFAULT_USER = {
    "full_name": "",
    "username": "",
    "phone": None,
    "driver_status": "none",       # none | pending | approved | rejected
    "driver_paused": True,
    "subscription": {
        "tariff": None,
        "start": None,
        "end": None,               # None = umrbod yoki obuna yo'q
        "active": False,
        "reminded_3d": False,
        "reminded_expired": False,
    },
    "last_ad": {},                 # oxirgi e'lon matni/rasmi (qayta ishlatish uchun)
}


def get_user(uid: str) -> dict:
    """Foydalanuvchi yozuvini qaytaradi, yo'q bo'lsa yaratadi."""
    users = users_store.data["users"]
    if uid not in users:
        users[uid] = json.loads(json.dumps(DEFAULT_USER))
    else:
        # eski yozuvlarda yetishmayotgan maydonlarni to'ldirish
        _deep_fill(users[uid], DEFAULT_USER)
    return users[uid]


def _deep_fill(target: dict, defaults: dict):
    for k, v in defaults.items():
        if k not in target:
            target[k] = json.loads(json.dumps(v))
        elif isinstance(v, dict) and isinstance(target.get(k), dict):
            _deep_fill(target[k], v)


def touch_user_profile(uid: str, full_name: str, username: str):
    """Foydalanuvchining ism/username ma'lumotini yangilab boradi."""
    u = get_user(uid)
    u["full_name"] = full_name or u.get("full_name") or ""
    u["username"] = username or u.get("username") or ""


async def save_users():
    await users_store.save()


async def save_ads():
    await ads_store.save()


async def save_payments():
    await payments_store.save()


def next_ad_number() -> int:
    """Yo'lovchi e'lonlari uchun ketma-ket raqam (#01, #02, ...)."""
    users_store.data["ad_counter"] = users_store.data.get("ad_counter", 0) + 1
    return users_store.data["ad_counter"]
