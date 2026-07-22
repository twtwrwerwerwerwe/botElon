# -*- coding: utf-8 -*-
"""states.py — FSM holatlari (aiogram StatesGroup).

Eski koddagi eng katta muammolardan biri: har bir "state" oddiy matn
(string) sifatida qo'lda users['...']['state'] ichida saqlanardi va
tez-tez bir-biriga aralashib, xatolarga sabab bo'lardi. Endi aiogram'ning
o'zining FSM (Finite State Machine) mexanizmi ishlatiladi — bu ancha
barqaror va xatosiz ishlaydi.
"""
from aiogram.dispatcher.filters.state import State, StatesGroup


class DriverStates(StatesGroup):
    waiting_phone = State()
    waiting_ad_text = State()
    waiting_ad_photo = State()
    waiting_receipt_photo = State()


class PassengerStates(StatesGroup):
    waiting_phone = State()
    waiting_route_custom = State()
    waiting_order_text = State()
    waiting_location = State()
