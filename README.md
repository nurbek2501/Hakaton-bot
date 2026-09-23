# 🚀 «Xatirchi raqamli yoshlari xakatoni – 2026» — ro‘yxatga olish boti

Bot ishtirokchilardan 23 ta savolni birma-bir so‘raydi va javoblarni **Google Formaga** yuboradi.
Javoblar forma ulangan **Google Sheets** jadvaliga o‘zi tushadi.

## 📁 Fayllar

| Fayl | Vazifasi |
|---|---|
| `app.py` | Flask + webhook + barcha handlerlar |
| `questions.py` | Savollar ro‘yxati (entry ID, variantlar, ikonkalar) |
| `storage.py` | SQLite (`bot.db`) — foydalanuvchi holati |
| `form_submit.py` | Google Formaga yuborish |
| `excel_export.py` | Barcha anketalarni bitta Excel faylga yig‘ish (`/export`) |
| `form_check.py` | Google Forma bot savollariga mosligini tekshirish (`/checkform`) |
| `set_webhook.py` | Webhookni o‘rnatish (bir marta ishga tushiriladi) |
| `deploy_pa.py` | PythonAnywhere’ga bitta buyruq bilan joylash va yangilash |
| `run_local.py` | Faqat lokal kompyuterda sinash uchun (polling) |
| `.env.example` | Sozlamalar namunasi |

## ✨ Imkoniyatlar

- Har bir savolda progress: `📋 Savol 5/23 ▰▰▱▱▱▱▱▱▱▱`
- Variantli savollarda ikonkali tugmalar, «✍️ Boshqa» — o‘z variantini yozish
- `⬅️ Orqaga`, `⏭ O‘tkazib yuborish` (ixtiyoriy savollarda), `📱 Raqamni yuborish`
- `@username` bitta tugma bilan to‘ldiriladi
- Telefon raqami istalgan ko‘rinishda tanib olinadi (`901234567`, `(90) 123-45-67`, `8 90 ...`,
  gap ichida ham), operator kodi tekshiriladi va hamma joyda `+998 90 123 45 67` ko‘rinishida saqlanadi.
  Jamoa a’zolari ro‘yxatidagi raqamlar ham shu ko‘rinishga keltiriladi
- Loyiha uchun havola **yoki fayl** (PDF, taqdimot, rasm, video, ZIP) — 10 tagacha; fayllar
  tashkilotchilar kanaliga saqlanadi, Formaga esa ularning havolasi yoziladi
- Yosh (17–30) va fuqarolik tekshiruvi, telefon/e-mail/havola validatsiyasi
- «Yakka tartibda» tanlansa, jamoa savollari umuman berilmaydi
- Tasdiqlash (22-savol) — ikkita ✅ belgi, ikkalasi bosilgach «➡️ Davom etish»
- Yakunda javoblar xulosasi → «✅ Tasdiqlash va yuborish» / «✏️ Qaytadan to‘ldirish»
- Xatolik bo‘lsa javoblar saqlanadi va «🔁 Qayta yuborish» tugmasi chiqadi
- Bot qayta ishga tushsa ham foydalanuvchi qolgan joyidan davom etadi (SQLite)
- Ro‘yxatga olish muddati: qolgan vaqt doim ko‘rinib turadi, muddatdan keyin qabul yopiladi
- Admin uchun (faqat ADMIN_IDS dagilar): `/stats` — statistika, `/export` — barcha anketalar
  bitta **Excel** faylda, `/checkform` — Google Forma tekshiruvi, `/resend` — yuborilmay
  qolganlarni qayta yuborish

Buyruqlar: `/start`, `/restart`, `/cancel`, `/help`. Admin buyruqlari faqat adminlar menyusida
ko‘rinadi; boshqalar yozsa, bot «Bunday buyruq yo‘q» deydi.

---

## ⚡ Tezkor joylash (3 qadam)

1. **@BotFather** dan bot tokenini oling va [pythonanywhere.com](https://www.pythonanywhere.com)’da
   bepul (Beginner) akkaunt oching.
2. Brauzerda: **Web → Add a new web app → Next → Manual configuration → Python 3.10 → Next**.
3. **Consoles → Bash** ni oching va yozing:
   ```bash
   git clone https://github.com/nurbek2501/Hakaton-bot.git ~/xakaton_bot
   python3.10 ~/xakaton_bot/deploy_pa.py
   ```
   Skript bot tokenini (yozganda ekranda ko‘rinmaydi) va admin Telegram ID’ni so‘raydi.
   Qolganini o‘zi qiladi: kutubxonalar, `.env`, WSGI, qayta ishga tushirish, webhook,
   Google Forma tekshiruvi.

Kod yangilansa: `cd ~/xakaton_bot && git pull && python3.10 deploy_pa.py` (sozlamalar saqlanadi).

Hammasini qo‘lda qilmoqchi bo‘lsangiz — quyidagi bosqichma-bosqich qo‘llanma.

---

## 🛠 PythonAnywhere’ga joylash (bosqichma-bosqich)

### 1. Bot yaratish va token olish
1. Telegramda **@BotFather** ni oching → `/newbot`.
2. Bot nomini (masalan, *Xatirchi Xakaton 2026*) va username’ini (masalan, `xatirchi_xakaton_bot`) yozing.
3. BotFather bergan **tokenni** saqlab qo‘ying (`1234567890:AA...` ko‘rinishida). Uni hech kimga bermang.
4. (Ixtiyoriy) `/setuserpic` bilan botga rasm qo‘ying.

### 2. PythonAnywhere’da akkaunt ochish
[pythonanywhere.com](https://www.pythonanywhere.com) → **Pricing & signup** → **Create a Beginner account** (bepul).
Tanlagan **login**ingiz (USERNAME) manzilda bo‘ladi: `https://USERNAME.pythonanywhere.com`.

### 3. Fayllarni yuklash

**A) GitHub’dan (eng oson).** **Consoles → Bash** ni oching:
```bash
git clone https://github.com/nurbek2501/Hakaton-bot.git xakaton_bot
```
Keyinchalik kod yangilansa: `cd ~/xakaton_bot && git pull`, so‘ng **Web → Reload**.
(`.env` va `bot.db` repoda yo‘q — ular serverda saqlanib qoladi, `git pull` ularga tegmaydi.)

**B) Qo‘lda.**
1. **Files** bo‘limiga kiring.
2. *Directories* maydoniga `xakaton_bot` deb yozib **New directory** ni bosing.
3. Shu papkaga kirib, **Upload a file** orqali quyidagilarni yuklang:
   `app.py`, `questions.py`, `storage.py`, `form_submit.py`, `form_check.py`, `excel_export.py`,
   `set_webhook.py`, `requirements.txt`, `.env.example`.

### 4. Kutubxonalarni o‘rnatish
**Consoles → Bash** ni oching va yozing:
```bash
cd ~/xakaton_bot
pip3.10 install --user -r requirements.txt
```

### 5. `.env` faylini yaratish
Bash konsolida:
```bash
cd ~/xakaton_bot
cp .env.example .env
```
So‘ng **Files** → `xakaton_bot/.env` ni oching va qiymatlarni to‘ldiring:

```
BOT_TOKEN=BotFather bergan token
WEBHOOK_SECRET_PATH=uzun-tasodifiy-satr
WEBHOOK_SECRET_TOKEN=boshqa_tasodifiy_satr
WEBHOOK_HOST=https://USERNAME.pythonanywhere.com
USE_PROXY=1
ADMIN_IDS=sizning_telegram_id
KEEP_LOCAL_COPY=1
STORAGE_CHAT_ID=-100...   (keyingi bo‘limga qarang)
CHANNEL_URL=https://t.me/kanal_nomi
```

💡 Tasodifiy satrlarni Bash’da shunday olish mumkin:
```bash
python3.10 -c "import secrets; print(secrets.token_urlsafe(24))"
```
💡 O‘z Telegram ID’ingizni bilish uchun **@userinfobot** ga yozing.

**Save** tugmasini bosing.

### 5.1. 📁 Loyiha fayllari uchun yopiq kanal
Ishtirokchilar yuklagan fayllar (PDF, taqdimot, ZIP, video) shu kanalga saqlanadi.
Google Sheets jadvalida esa har bir fayl uchun kanal xabariga havola bo‘ladi
(`https://t.me/c/.../45 (taqdimot.pdf)`), uni faqat kanal a’zolari ochadi.

1. Telegramda **yangi kanal** yarating → turi **Private (yopiq)**.
2. Kanal sozlamalari → **Administrators → Add Admin** → botingizni toping va
   **Post messages** huquqini bering.
3. Bot sizga (ADMIN_IDS dagi admin) avtomatik xabar yuboradi:
   `STORAGE_CHAT_ID=-100xxxxxxxxxx` — shu qatorni `.env` ga yozing va **Reload** bosing.
4. Tashkilotchilarni kanalga a’zo qiling — ular jadvaldagi havolalarni ocha oladi.

> `STORAGE_CHAT_ID` bo‘sh qolsa, fayllar ADMIN_IDS dagi adminlarga shaxsiy xabar bo‘lib keladi,
> jadvalga esa faqat fayl nomi yoziladi (`Telegram fayl: taqdimot.pdf`).

### 6. Web-ilova yaratish
**Web** bo‘limi → **Add a new web app** → **Next** → **Manual configuration** (Flask emas!) → **Python 3.10** → **Next**.

### 7. WSGI faylini sozlash
**Web** sahifasida *Code* qismidagi **WSGI configuration file** havolasini
(`/var/www/USERNAME_pythonanywhere_com_wsgi.py`) bosing. Ichidagi **hamma narsani o‘chirib**,
quyidagini yozing (`USERNAME` ni o‘z loginingizga almashtiring):

```python
import os
import sys

# Bot papkasini Python yo‘liga qo‘shamiz
project_home = "/home/USERNAME/xakaton_bot"
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# .env faylini yuklaymiz
from dotenv import load_dotenv
load_dotenv(os.path.join(project_home, ".env"))

# Flask ilovasi
from app import app as application  # noqa
```
**Save** ni bosing.

### 8. Reload
**Web** sahifasiga qayting va yashil **Reload USERNAME.pythonanywhere.com** tugmasini bosing.
Brauzerda `https://USERNAME.pythonanywhere.com` ni ochsangiz, **«Xakaton bot ishlayapti ✅»** yozuvi chiqishi kerak.

### 9. Webhookni o‘rnatish
Bash konsolida:
```bash
cd ~/xakaton_bot
python3.10 set_webhook.py
```
Natija taxminan shunday bo‘lishi kerak:
```
🤖 Bot: @xatirchi_xakaton_bot
✅ Webhook o‘rnatildi
--- getWebhookInfo ---
url:                  https://USERNAME.pythonanywhere.com/<WEBHOOK_SECRET_PATH>
pending_update_count: 0
last_error_message:   yo‘q ✅
```
Skript bot menyusidagi buyruqlar va tavsifni ham o‘rnatadi.

### 10. Sinab ko‘rish
1. Telegramda botingizni oching → **Start**.
2. Anketani oxirigacha to‘ldirib, **✅ Tasdiqlash va yuborish** ni bosing.
3. Google Formaga ulangan **Google Sheets** jadvalini oching — yangi qator paydo bo‘lishi kerak.
4. Sinov qatorini jadvaldan o‘chirib qo‘yishni unutmang.

### 11. ⚠️ Har oy muddatni uzaytirish
Bepul web-ilova **1 oydan keyin o‘chib qoladi**. Buning oldini olish uchun oyiga bir marta
**Web** bo‘limida **«Run until 1 month from today»** («Bugundan boshlab 1 oygacha amal qiladi»)
tugmasini bosing. PythonAnywhere o‘chirishdan bir hafta oldin e-mail orqali eslatadi.

### 12. Xatolarni qayerdan ko‘rish mumkin
**Web** bo‘limining pastida *Log files*:
- **Error log** — Python xatolari (masalan, «Google Forma javobi: HTTP 400»);
- **Server log** — web-server xabarlari;
- **Access log** — kelgan so‘rovlar (Telegram har xabarda `POST /<maxfiy-yo‘l>` yuboradi).

Kod yoki `.env` o‘zgartirilgandan keyin har doim **Reload** bosing.

---

## 📊 Barcha anketalarni bitta faylda olish

**1-usul — Google Sheets (asosiy, avtomatik).** Har bir anketa forma ulangan jadvalga o‘zi tushadi.
Google Forms → **Javoblar (Responses)** → **Sheets’da ko‘rish**. Excel kerak bo‘lsa:
*Fayl → Yuklab olish → Microsoft Excel (.xlsx)*. Jadvalni tashkilotchilar bilan ulashish mumkin.

#### ✅ Google Sheets’ni to‘g‘ri sozlash (bir martalik)

1. **Jadvalni ulash:** Google Forms → *Javoblar* → **«Sheets’ga ulash» (Link to Sheets)** →
   *Yangi jadval yaratish*. Shundan keyin har bir anketa yangi qator bo‘lib tushadi.
2. **Forma sozlamalari** (*Sozlamalar → Javoblar*) — shunday qolishi shart:
   - «E-mail manzillarni yig‘ish» → **Yig‘ilmasin**;
   - «1 ta javob bilan cheklash» → **o‘chiq** (yoqilsa Google login so‘raydi — bot yubora olmaydi);
   - «Javoblar xulosasini ko‘rsatish» → **o‘chiq** (aks holda har kim boshqalarning
     ma’lumotlarini ko‘radi). Hozir o‘chiq — tekshirildi ✅
3. **Ulashish:** jadvalni faqat tashkilotchilarning e-mail’lariga oching.
   **«Havolaga ega har kim»** qilmang — ichida shaxsiy ma’lumotlar bor.
4. **Formani tahrirlagandan keyin** botga `/checkform` yozing. Variant matnini o‘zgartirish,
   savolni o‘chirish yoki yangi majburiy savol qo‘shish anketalarni buzadi — tekshiruv
   aynan nima buzilganini aytadi. Savol **sarlavhasini** o‘zgartirish xavfsiz.
5. **Qulaylik uchun** (ixtiyoriy):
   - 1-qatorni qotirish: *Ko‘rinish → Qotirish → 1 qator*;
   - filtr: *Ma’lumotlar → Filtr yaratish*;
   - bir odam ikki marta yozilgan bo‘lsa, bo‘yash: telefon ustunini belgilang (odatda **H**) →
     *Format → Shartli formatlash → Maxsus formula*: `=COUNTIF($H:$H;$H1)>1`
     (xato bersa, `;` o‘rniga `,` yozing — bu Google hisobingiz tiliga bog‘liq).

#### 🛡 Bot anketani jadvalga yetkazishni qanday kafolatlaydi

- Google javobni qabul qilsa **HTTP 200**, rad etsa **HTTP 400** qaytaradi — bot buni aniq ajratadi
  va «yuborildi» deb faqat haqiqatan qabul qilinganda aytadi.
- Internet uzilsa yoki Google vaqtincha ishlamasa — **avtomatik 3 marta** qayta urinadi.
- Google javob bermay qolsa (timeout) — dublikat qator bo‘lmasligi uchun avtomatik takrorlamaydi,
  foydalanuvchiga «🔁 Qayta yuborish» tugmasi chiqadi.
- Majburiy savol javobsiz qolgan bo‘lsa — Formaga yubormaydi, foydalanuvchini o‘sha savolga qaytaradi.
- Anketa tushmasa — **adminlarga darhol xabar** keladi (sababi bilan). Forma rad etgan bo‘lsa,
  bot Formani o‘zi tekshirib, nima o‘zgarganini ham yozadi.
- Hech bir anketa yo‘qolmaydi: yuborilmaganlar bazada turadi. Muammo hal bo‘lgach admin
  `/resend` bosadi — hammasi yuboriladi va har bir ishtirokchiga «🎉 Tabriklaymiz!» xabari boradi.
- Serverga joylashda `set_webhook.py` Formani avtomatik tekshiradi.

**2-usul — botdan Excel (bir bosishda, Google’ga bog‘liq emas).** Admin botga `/export` yozadi va
tayyor `.xlsx` fayl oladi:
- **«Ro‘yxat»** varag‘i: har bir ishtirokchi bitta qatorda (28 ustun, yoshi avtomatik hisoblanadi),
  sarlavha va F.I.Sh. ustuni qotirilgan, har ustunda filtr, loyiha fayllari bosiladigan havola;
- **«Statistika»** varag‘i: jinsi, faoliyat turi, ishtirok shakli, soha, tayyorlik darajasi va
  «qayerdan bildi» bo‘yicha sonlar va foizlar.

`/export` ishlashi uchun `.env` da `KEEP_LOCAL_COPY=1` bo‘lishi kerak. U yoqilishidan oldin
yuborilgan anketalar faylga tushmaydi (ular faqat Google Sheets’da bo‘ladi).

---

## 📅 Ro‘yxatga olish muddati

Oxirgi muddat: **27-sentabr 2026, 23:59** (Toshkent vaqti) — `questions.py` dagi `REG_DEADLINE`.

- Bot e’londa, har bir savol tepasida va xulosada **qancha vaqt qolganini** ko‘rsatib turadi:
  `⏳ Qabul tugashiga: 2 kun 6 soat` (oxirgi sutkada ⏰, oxirgi soatda 🔥).
- **Muddatdan keyin:** yangi anketa boshlanmaydi, to‘ldirilayotgan anketalar yopiladi
  («⏰ Ro‘yxatdan o‘tish yakunlandi»). Javoblar o‘chirilmaydi — muddat uzaytirilsa, davom ettirish mumkin.
- Muddat ichida yuborilib, texnik sabab bilan qolib ketgan anketalar keyin ham qayta yuboriladi
  («🔁 Qayta yuborish», `/resend`). Admin buyruqlari (`/stats`, `/export`) ishlayveradi.
- Vaqt adolatli hisoblanadi: xabarning **yozilgan payti** (Telegram vaqti) olinadi, server
  navbatidagi kechikish emas. «Yuborish» tugmasiga kechikish uchun 2 daqiqa beriladi.

**Muddatni kodga tegmasdan o‘zgartirish** (PythonAnywhere Bash konsolida):
```bash
echo "REG_DEADLINE=2026-10-05 23:59" >> ~/xakaton_bot/.env
touch /var/www/nurbek2501_pythonanywhere_com_wsgi.py
```
Ikkinchi qator web-ilovani qayta yuklaydi. Muddatsiz ishlatish: `REG_DEADLINE=off`.
Tekshirish: `https://nurbek2501.pythonanywhere.com` sahifasida muddat va qolgan vaqt ko‘rinadi.

💡 Muddat tugaganda Google Formada ham **«Javoblarni qabul qilish»** ni o‘chiring — repo ochiq,
Forma manzilini ko‘rgan kishi botni chetlab yubora olmasin.

---

## 🚦 Ko‘p foydalanuvchi bir vaqtda kelganda

**Bepul tarif imkoniyati.** PythonAnywhere bepul tarifida bitta web-worker bor: xabarlar navbat
bilan, bittadan qayta ishlanadi. Bitta xabar taxminan 0,3–0,8 soniya oladi (baza + Telegram’ga
1–3 ta so‘rov). Bu daqiqasiga ~80–200 ta xabar degani: bir vaqtda **15–30 kishi** bemalol
to‘ldiradi. Undan ko‘p bo‘lsa, bot javoblari bir necha soniya kechikadi, lekin hech narsa
yo‘qolmaydi va ma’lumotlar aralashmaydi: Telegram xabarlarni o‘zida navbatda ushlab turadi.
«Kuniga 100 CPU-soniya» cheklovi web-ilovaga tegishli emas — kunlik anketalar soni cheklanmagan.

Birdaniga yuzlab kishi kutilsa (masalan, e’lon minglab obunachili kanalga tushsa), **Developer**
tarifi (10$/oy, 3 ta worker) botni ~3 barobar tezlashtiradi — kod o‘zgartirilmaydi.

**Chalkashlikdan himoya** (yuklama sinovida tekshirilgan):

| Vaziyat | Bot nima qiladi |
|---|---|
| Tugma ikki marta bosildi (sekin internet) | Ikkinchisi e’tiborsiz — keyingi savolga «javob» bo‘lib tushmaydi |
| Tugma yozuvi matnli savolga keldi (masalan, «🏡 Doimiy…» → «Manzil») | Qabul qilinmaydi, «javobni matn bilan yozing» deydi |
| Oldingi javob qayta yuborildi («Muammo» matni → «Yechim») | Qabul qilinmaydi |
| Telegram bir xabarni ikki marta yetkazdi | Faqat bir marta ishlanadi |
| Telegram «429 juda ko‘p so‘rov» dedi / ulanish uzildi | Kutib, qayta yuboradi |
| Savol foydalanuvchiga yetib bormadi | Keyingi xabarni javob deb olmaydi — savolni qayta ko‘rsatadi |
| «Yuborish» ikki marta bosildi | Formaga faqat bir marta ketadi |
| Kimdir 10 soniyada 30+ xabar yubordi (spam) | Vaqtincha e’tiborsiz — boshqalarni kutdirmaydi |
| Juda uzun javob/havola/nom | Telegram limitlariga (4096/1024) sig‘diriladi |

Telegram bir vaqtda ko‘pi bilan 10 ta so‘rov yuboradi (`max_connections=10`) — qolganlarini o‘zida
navbatda ushlaydi, shuning uchun PythonAnywhere navbati to‘lib ketmaydi.

---

## ❗ Muammolar va yechimlar

| Belgisi | Sabab va yechim |
|---|---|
| Bot javob bermayapti | `set_webhook.py` ni qayta ishga tushiring, `last_error_message` ni o‘qing. Reload qilinganini tekshiring. |
| `last_error_message: ...403 Forbidden` | `.env` dagi `WEBHOOK_SECRET_TOKEN` o‘zgargan — Reload qilib, `set_webhook.py` ni qayta ishga tushiring. |
| «Texnik xatolik» chiqyapti | Botga `/checkform` yozing — Forma o‘zgargan bo‘lsa, aynan nima buzilganini ko‘rsatadi. Tuzatgach `/resend` bosing. `ProxyError` — pastdagi zaxira variantga qarang. |
| «Faylni saqlab bo‘lmadi» | Bot kanalda admin emas yoki **Post messages** huquqi yo‘q. `STORAGE_CHAT_ID` to‘g‘riligini tekshiring. |
| Chet el raqami qabul qilinmayapti | Bu ataylab qilingan: Google Formadagi telefon maydoni faqat `+998` raqamlarini qabul qiladi (regex tekshiruvi). Shuning uchun bot ham faqat O‘zbekiston raqamlarini qabul qiladi. |
| Jadvalga tushmayapti | Formada **«Javoblarni qabul qilish»** yoqilganini va forma **login talab qilmasligini** tekshiring. |

### 🔁 Zaxira variant: agar Google Forma bloklansa

PythonAnywhere bepul tarifida tashqi saytlarga faqat **ruxsat etilgan ro‘yxatdagi** (whitelist)
manzillarga chiqish mumkin. `docs.google.com` odatda shu ro‘yxatda bor, lekin agar Error log’da
`ProxyError` yoki `403` ko‘rsangiz:

1. `.env` da `KEEP_LOCAL_COPY=1` ekanini tekshiring (bo‘lmasa qo‘ying va **Reload** bosing).
2. Har bir anketa `bot.db` bazada ham saqlanadi (yuborilmay qolganlari ham).
3. Botga (admin sifatida) `/export` yozing — barcha anketalar **Excel fayl** bo‘lib keladi,
   yuborilmay qolganlari qizil rangda.
4. `/stats` — nechta anketa yuborilgani, nechtasi yuborilmay qolgani.

Yuborilmay qolgan anketalar egalari «🔁 Qayta yuborish» tugmasini bosishi mumkin.

---

## 🔒 Xavfsizlik

- **Ma’lumotlarni faqat admin oladi.** `/export`, `/stats`, `/checkform`, `/resend` va ularning
  tugmalari har safar Telegram ID bo‘yicha tekshiriladi (`ADMIN_IDS`). Telegram ID’ni soxtalashtirib
  bo‘lmaydi, webhook esa faqat Telegram’dan kelgan so‘rovlarni qabul qiladi. Admin buyruqlari faqat
  shaxsiy chatda ishlaydi — guruhga tasodifan eksport qilinmaydi. Ruxsatsiz urinishlar log’ga yoziladi.
- Token va boshqa maxfiy qiymatlar faqat `.env` da. Token log’larda `***TOKEN***` bo‘lib yashiriladi.
- Webhook manzili maxfiy yo‘lda, har bir so‘rovda `X-Telegram-Bot-Api-Secret-Token` tekshiriladi.
- `KEEP_LOCAL_COPY=1` (standart) bo‘lsa, anketalar nusxasi `bot.db` da saqlanadi — `/export` shu
  uchun kerak. `KEEP_LOCAL_COPY=0` qilsangiz, Formaga yuborilgan anketaning shaxsiy ma’lumotlari
  bazadan o‘chiriladi, faqat `user_id` va vaqt qoladi.
- Excel faylda `=` bilan boshlangan javoblar formula bo‘lib ishlamaydi — oddiy matn sifatida saqlanadi.
- `.env` va `bot.db` fayllarini hech kimga bermang.

## 💻 Lokal kompyuterda sinash

```bash
pip install -r requirements.txt
cp .env.example .env      # BOT_TOKEN ni yozing, USE_PROXY=0
python run_local.py
```
⚠️ `run_local.py` webhookni o‘chiradi. Sinovdan so‘ng serverda `python3.10 set_webhook.py` ni qayta ishga tushiring.

ℹ️ Lokal rejimda (polling) takroriy update va spam himoyasi ishlamaydi — ular faqat serverdagi
webhook’da. Loyiha papkasi OneDrive/Dropbox ichida bo‘lsa, sinxronizatsiya `bot.db` ni vaqtincha
qulflab qo‘yishi mumkin; lokal sinov uchun bu muhim emas, serverda (PythonAnywhere) bunday muammo yo‘q.

## ✏️ Savollarni o‘zgartirish

Hammasi `questions.py` da. Variant matnlari Google Formadagi bilan **harfma-harf bir xil** bo‘lishi shart
(`‘` va `’` belgilari bilan), aks holda forma javobni qabul qilmaydi. Ikonkalarni (`icon`) bemalol almashtirish mumkin.
