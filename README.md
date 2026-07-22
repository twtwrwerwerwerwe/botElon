# 🚕 Taxi Bot — Yangilangan versiya (Upgrade #1)

Bu versiyada butun bot **qaytadan, toza va modul-modul qilib** yozildi.
Eski `bot.py` faylida bo'lgan takrorlangan/qarama-qarshi kodlar
(load_json ikki marta e'lon qilingani, `view_pass`/`take_pass`
handlerlari bir necha marta takrorlangani va h.k.) butunlay olib
tashlandi.

## 🛠️ Upgrade #1.1 — kritik xatolik tuzatildi (holat saqlanmasligi)

**Muammo:** `to'lov joylari hech nima chiqmayabdi` deb xabar berdingiz.
Chuqur tekshiruv natijasida sabab topildi: aiogram'ning standart
`MemoryStorage`si foydalanuvchi "qaysi bosqichda turgani"ni
(masalan, "telefon raqam kutilmoqda") faqat operativ xotirada saqlaydi.
Railway konteyner har safar qayta ishga tushganda (redeploy, uyqudan
uyg'onish, xatolik bo'lsa qayta ishga tushirish va h.k.) bu ma'lumot
**butunlay yo'qolar edi**. Agar shu payt foydalanuvchi aynan telefon
raqam yoki chek rasmi kutilayotgan bosqichda bo'lsa, bot uning
xabariga umuman javob bermay qolardi — aynan siz ko'rgan "hech nima
chiqmayabdi" holati shu edi.

**Yechim:**
1. Endi FSM holatlar `FileStorage` orqali **diskka** (`storage_data/fsm.json`)
   yoziladi — bot qayta ishga tushsa ham, foydalanuvchi to'xtagan
   joyidan (masalan, telefon so'ralayotgan bosqichdan) davom etaveradi.
2. Qo'shimcha xavfsizlik chorasi sifatida `handlers/fallback.py`
   qo'shildi — agar biror sabab bilan hech qanday handler mos kelmasa,
   bot **hech qachon jim qolmaydi**, balki "Buni tushunmadim, menyudan
   tanlang" deb asosiy menyuga qaytaradi.

Bu tuzatish men tomondan haqiqiy Telegram oqimini simulyatsiya qiluvchi
avtomatlashtirilgan test bilan tasdiqlandi: ariza → tasdiqlash →
telefon → tarif → to'lov usuli → chek → admin tasdiqlashi — hammasi
oxirigacha muvaffaqiyatli ishladi, shu jumladan **jarayon o'rtasida
botni qayta ishga tushirib** ko'rilganda ham.

⚠️ **Muhim:** Railway'da konteyner **doim ham bir xil diskda
ishlamasligi** mumkin (agar Persistent Volume ulanmagan bo'lsa).
Eng ishonchli natija uchun Railway loyihangizga **Volume** qo'shib,
uni `/app/storage_data` yo'liga ulashni tavsiya qilaman — shunda
ma'lumotlar (foydalanuvchilar, e'lonlar, to'lovlar, FSM holatlar)
konteyner butunlay qayta yaratilganda ham yo'qolmaydi.

---

## 🎨 Upgrade #1.2 — dizayn, e'lon yuborilmaslik xatosi, stikerlar

**1) "E'lon yuborildi deydi, lekin guruhga kelmaydi" — tuzatildi.**
Sabab topildi: guruhga yuborishda xatolik chiqsa (masalan, bot
guruhda administrator emas, yoki callback tugmasidagi `tel:` havolasi
Telegram tomonidan rad etilsa), avvalgi kodda bu xatolik **jimgina
yutib yuborilar edi** — bot "yuborildi" deb yozardi-yu, aslida hech
narsa bormasdi. Endi:
- Avval qo‘ng‘iroq tugmasi bilan yuboriladi;
- Agar shu sabab xato chiqsa, qo‘ng‘iroq tugmasisiz qayta uriniladi;
- Baribir muvaffaqiyatsiz bo‘lsa, **sizga aniq xato matni bilan xabar
  beriladi** ("guruhga yuborilmadi, sababi: ...") — shunda muammoni
  darhol tushunib, tuzatasiz (odatda sabab: bot kanal/guruhda admin
  emas, yoki `config.py`dagi `DRIVER_CHANNELS` ID noto‘g‘ri).

**2) Interval mantig'i aniqlashtirildi.** Interval tanlab
"Tasdiqlash"ni bosgan zahoti e'lon **darhol** guruhga yuboriladi,
so‘ng har tanlangan daqiqada (masalan 10 daqiqa) avtomatik qayta
yuborilib turadi — boshqacha (kutib turib keyin yuborish) endi yo‘q.

**3) Deyarli barcha tugmalar endi INLINE (xabar ostida).** Yozish
maydonini to'sadigan katta reply-klaviaturalar olib tashlandi — asosiy
menyu, haydovchi bo‘limi, yo‘lovchi bo‘limi, yo‘nalish tanlash va h.k.
endi xabar ostida chiroyli tugmalar sifatida chiqadi. Faqat ikkita
joy — telefon raqamni tugma orqali yuborish va lokatsiyani tugma
orqali yuborish — Telegram’ning o‘zi talab qilgani sababli oddiy
klaviatura bo‘lib qoladi (buni o'zgartirib bo'lmaydi).

**4) Jonli (animatsiyali) stikerlar qo‘shildi.** Haydovchi
tasdiqlanganda, e'lon guruhga yuborilganda, to‘lov tasdiqlanganda va
zakaz qabul qilinganda bot endi (agar sozlangan bo‘lsa) stiker ham
yuboradi. Stiker ID'sini olish JUDA OSON:
1. Botga istalgan animatsiyali stikerni yuboring (o‘zingiz — admin
   sifatida).
2. Bot sizga o‘sha stikerning `file_id`'sini yozib beradi.
3. Shu ID'ni `config.py` dagi `STICKERS` lug‘atiga qo‘ying (masalan
   `"driver_approved": "CAACAgIA..."`).
Sozlanmagan holatda ("") bot shunchaki stiker yubormaydi — hech
qanday xatolikka olib kelmaydi.

---

## ☎️ Upgrade #1.3 — qo'ng'iroq tugmasi va haydovchini chiqarishda e'lon to'xtashi

**1) "📞 Haydovchiga qo‘ng‘iroq" tugmasi yo‘qolib qolayotgan edi —
sababi topildi.** Telegram Bot API "tel:" havolali tugmalarni ASLIDA
qabul qilmaydi (faqat http/https/tg:// ruxsat etiladi) — bot buni
serverdan "xato" deb qaytarib olar, avvalgi kodda esa shu sabab shu
tugmasiz qayta yuborib yuborar edi (shuning uchun faqat "Zakaz
berish" tugmasi qolardi). Endi bu tugma **kontakt karta** orqali
ishlaydi: bosilganda bot haydovchining raqamini sizga shaxsiy
xabarda "kontakt" shaklida yuboradi — uni bosib, bir zumda
qo‘ng‘iroq qilishingiz mumkin (Telegram'ning o‘zi shunday imkoniyat
beradi).

**2) Admin haydovchini "❌ Chiqarib tashlash" qilsa, uning e'loni ham
darhol to‘xtaydi.** Avval faqat "pauza" belgisi qo‘yilardi, ammo
e'lonning o'zi "faol" holatda qolib ketardi. Endi e'lon ham darhol
"nofaol" qilinadi va haydovchiga ham xabar boradi.

---

## 📁 Loyiha tuzilishi

```
taxi_bot/
├── main.py              # botni ishga tushirish nuqtasi
├── bot_instance.py       # yagona Bot/Dispatcher obyekti
├── config.py             # BARCHA sozlamalar shu yerda (token, adminlar, narxlar...)
├── storage.py             # JSON ma'lumotlarni saqlash (xavfsiz, bitta joyda)
├── states.py              # FSM holatlar (aiogram)
├── keyboards.py            # barcha klaviaturalar
├── utils.py                # yordamchi funksiyalar (telefon formatlash va h.k.)
├── background.py            # fon jarayonlari (e'lon yuborish, eslatmalar, obuna nazorati)
└── handlers/
    ├── start.py             # /start, "Orqaga"
    ├── driver_admin.py        # haydovchilik arizasini tasdiqlash/rad etish, ro'yxat
    ├── driver.py               # telefon, e'lon berish/to'xtatish, obuna holati
    ├── payment.py               # tarif tanlash, to'lov usullari
    ├── payment_admin.py          # admin to'lovlarni tasdiqlash/rad etish
    ├── passenger.py               # yo'lovchi bo'limi (to'liq yangi dizayn)
    └── fallback.py                  # hech narsa mos kelmasa - oxirgi himoya
```

## ⚙️ Sozlash — FAQAT `config.py` faylini tahrirlang

- `TOKEN`, `ADMINS`, `DRIVER_CHANNELS`, `PASSENGER_CHANNELS` — eskisidek saqlanib qoldi.
- `ADMIN_PHONE`, `ADMIN_USERNAME` — admin bilan bog'lanish uchun.
- `PAYMENT_CARD` — "chek orqali to'lov"da ko'rsatiladigan karta ma'lumotlari.
- `TARIFFS` — 1 oylik / 2 oylik / 5 oylik / umrbod narxlari. **Narxlarni
  o'zingiz kiritgan emassiz, shuning uchun men taxminiy narxlar qo'ydim —
  albatta o'zingizga moslab o'zgartiring.**
- `CLICK_MERCHANT_ID` / `PAYME_MERCHANT_ID` — hozircha `None` (bo'sh).
  Shu sababli bot "Click/Payme" tugmasini bossa avtomatik ravishda
  **"Bu to'lov usuli hozircha vaqtinchalik mavjud emas"** deb javob beradi
  — aynan siz so'ragandek. Merchant ID'laringiz tayyor bo'lganda shu
  yerga kiritsangiz bo'ldi.

## 🆕 Nima qo'shildi / o'zgardi

### 1) To'lov tizimi (butunlay yangi)
- Haydovchi tasdiqlangach, avval **telefon raqami** so'raladi (tugma
  yoki qo'lda, `+998`siz kiritsa bot o'zi qo'shib qo'yadi).
- Keyin **4 ta tarif** taklif qilinadi: 1 oylik, 2 oylik, 5 oylik, umrbod.
- Tarif tanlangach, **3 ta to'lov usuli**:
  1. 👨‍💼 Admin orqali murojaat
  2. 💳 Click/Payme (merchant sozlanmagan bo'lsa — vaqtincha mavjud emas)
  3. 🧾 Chek orqali (karta ko'rsatiladi, chek rasmi qabul qilinadi)
- Har ikkala holatda ham (admin orqali / chek orqali) so'rov **adminga
  to'liq ma'lumot bilan** (kim, qaysi tarif, narxi, telefon) ✅/❌
  tugmalari bilan boradi.
- Admin tasdiqlagan kundan boshlab obuna muddati hisoblanadi.
- **3 kun qolganda** va **muddat tugagan kuni** avtomatik eslatma boradi.
- Muddat tugagach, haydovchi avtomatik ravishda bloklanadi (e'lonlari
  to'xtaydi) va obunani yangilashga taklif qilinadi.

### 2) Haydovchi bo'limi
- E'lon interval tanlash endi **inline tugmalar** (xabar ostida) orqali
  — yozish maydonini endi to'smaydi.
- Kanaldagi e'londa **2 ta tugma**: 📞 haydovchiga qo'ng'iroq (to'g'ridan
  to'g'ri raqamga) va 📩 botga zakaz berish.
- E'lon **12 soatdan keyin** eslatma beradi, **24 soatdan keyin**
  o'zi avtomatik to'xtaydi.
- "📣 E'lon berish" tugmasi endi **oxirgi e'lonni eslab qoladi** — matn
  va rasmni qayta so'ramaydi, faqat intervalni so'raydi. "🆕 Yangi
  e'lon" bosilsa — hammasi qaytadan so'raladi.

### 3) Yo'lovchi bo'limi (to'liq qayta dizayn qilindi)
- "🚖 Haydovchi chaqirish" → telefon → yo'nalish (tugma yoki qo'lda) →
  buyurtma matni (misol bilan) → ixtiyoriy lokatsiya.
- Guruhdagi e'lon endi chiroyli: sarlavha, tartib raqami (`#01`, `#02`...),
  yo'nalish va matn **quote (blockquote)** shaklida, telefon **yashirin**.
- "👁 E'lonni ko'rish" tugmasi bosilsa, to'liq ma'lumot (telefon +
  lokatsiya tugmasi bilan) **botning shaxsiy chatida** ochiladi.
- Birinchi qabul qilgan haydovchi g'olib — qolganlar bossa "hamkasbingiz
  qabul qildi" degan ogohlantirish oladi.
- Qabul qilingach, guruhdagi xabarda **kim qabul qilgani** ko'rinadi,
  yo'lovchiga esa haydovchi profili (username bo'lsa — tugma orqali)
  va "Oq yo'l!" xabari yuboriladi.
- Lokatsiya yuborilgan bo'lsa, "📍 Lokatsiyani ochish" tugmasi orqali
  Google Maps / Yandex Maps / 2GIS dan birini tanlab ochish mumkin.

## ▶️ Ishga tushirish

```bash
pip install -r requirements.txt
python main.py
```

yoki Docker orqali:

```bash
docker build -t taxi-bot .
docker run -d --name taxi-bot taxi-bot
```

Ma'lumotlar `storage_data/` papkasida saqlanadi (birinchi ishga
tushganda avtomatik yaratiladi).

## 📌 Keyingi yangilanishlar uchun eslatma

Kodning har bir qismi alohida faylda bo'lgani uchun endi keyingi
yangilanishlarni kiritish ancha oson va xavfsiz bo'ladi — masalan,
faqat `handlers/passenger.py` yoki faqat `keyboards.py` faylini
o'zgartirish orqali, boshqa qismlarga tegmasdan yangi funksiya
qo'shish mumkin.
