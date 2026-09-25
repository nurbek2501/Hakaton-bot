# -*- coding: utf-8 -*-
"""
«Xatirchi raqamli yoshlari xakatoni – 2026» ro‘yxatga olish boti.
Flask + webhook (PythonAnywhere bepul tarifi uchun).
"""
import html
import io
import logging
import os
import re
import time
from collections import Counter, deque
from datetime import date, datetime, timedelta

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

import requests  # noqa: E402
import telebot  # noqa: E402
from flask import Flask, abort, request  # noqa: E402
from telebot import apihelper, types  # noqa: E402
from telebot.apihelper import ApiTelegramException  # noqa: E402

import storage as st  # noqa: E402
from excel_export import build_xlsx  # noqa: E402
from form_check import check_form, report_text  # noqa: E402
from form_submit import submit  # noqa: E402
from questions import OTHER, QUESTIONS, REG_DEADLINE, TEAM, is_applicable  # noqa: E402

# ------------------------------------------------------------------
# Sozlamalar (.env dan)
# ------------------------------------------------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
WEBHOOK_SECRET_PATH = os.getenv("WEBHOOK_SECRET_PATH", "webhook").strip("/ ")
WEBHOOK_SECRET_TOKEN = os.getenv("WEBHOOK_SECRET_TOKEN", "").strip()
USE_PROXY = os.getenv("USE_PROXY", "0") == "1"
ADMIN_IDS = {int(x) for x in re.findall(r"\d+", os.getenv("ADMIN_IDS", ""))}
KEEP_LOCAL_COPY = os.getenv("KEEP_LOCAL_COPY", "0") == "1"
CHANNEL_URL = os.getenv("CHANNEL_URL", "").strip()
# Loyiha fayllari saqlanadigan yopiq kanal (-100... yoki @kanal). Bo‘sh bo‘lsa - adminlarga yuboriladi
STORAGE_CHAT_ID = os.getenv("STORAGE_CHAT_ID", "").strip()


# ------------------------------------------------------------------
# Log: token hech qachon log’ga tushmasligi uchun yashiriladi
# ------------------------------------------------------------------
class RedactingFormatter(logging.Formatter):
    def format(self, record):
        s = super().format(record)
        return s.replace(BOT_TOKEN, "***TOKEN***") if BOT_TOKEN else s


_handler = logging.StreamHandler()
_handler.setFormatter(RedactingFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
logging.basicConfig(level=logging.INFO, handlers=[_handler])
# telebot o‘z handleri bilan ham yozadi - xabarlar ikki marta chiqmasligi uchun olib tashlaymiz
telebot.logger.handlers.clear()
log = logging.getLogger("xakaton_bot")
if not ADMIN_IDS:
    log.warning("ADMIN_IDS bo‘sh — /export, /stats va boshqa admin buyruqlari hech kimga ishlamaydi")


# ------------------------------------------------------------------
# Ro‘yxatga olish muddati
# ------------------------------------------------------------------
UZ_MONTHS = ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust",
             "sentabr", "oktabr", "noyabr", "dekabr"]
# Foydalanuvchi «Yuborish» ni muddat ichida bossa-yu, server navbati tufayli sal kechroq
# ishlansa - rad etilmasligi uchun (tugma bosilgan vaqtni Telegram bermaydi)
SEND_LAG_GRACE = timedelta(minutes=2)


def _parse_deadline(raw):
    """«2026-09-30 23:59» yoki «30.09.2026 23:59» -> qabul yopiladigan payt (shu daqiqa oxiri).
    «off» - muddatsiz. Noto‘g‘ri yozilgan bo‘lsa - log’da xato va muddatsiz ishlaydi."""
    raw = (raw or "").strip()
    if raw.lower() in ("off", "none", "0"):
        return None
    for fmt in ("%Y-%m-%d %H:%M", "%d.%m.%Y %H:%M"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=st.TZ) + timedelta(minutes=1)
        except ValueError:
            pass
    log.error("REG_DEADLINE noto‘g‘ri: %r (kutilgan ko‘rinish: 2026-09-30 23:59) — muddat qo‘yilmadi", raw)
    return None


# .env dagi REG_DEADLINE ustun turadi, bo‘lmasa - questions.py dagi qiymat
DEADLINE_END = _parse_deadline(os.getenv("REG_DEADLINE") or REG_DEADLINE)


def _now():
    return datetime.now(st.TZ)


def deadline_label():
    """«30-sentabr, 23:59»"""
    d = DEADLINE_END - timedelta(minutes=1)
    return f"{d.day}-{UZ_MONTHS[d.month - 1]}, {d:%H:%M}"


def registration_open(at=None):
    """Ro‘yxatga olish ochiqmi. at - foydalanuvchi harakat qilgan payt
    (datetime yoki Telegram xabaridagi unix vaqt); None - hozir."""
    if DEADLINE_END is None:
        return True
    if at is None:
        at = _now()
    elif isinstance(at, (int, float)):
        at = datetime.fromtimestamp(at, st.TZ)
    return at < DEADLINE_END


def time_left():
    """Qolgan vaqt, masalan «4 kun 18 soat». Muddat yo‘q yoki tugagan bo‘lsa - None."""
    if DEADLINE_END is None:
        return None
    sec = (DEADLINE_END - _now()).total_seconds()
    if sec <= 0:
        return None
    days, rest = divmod(int(sec // 60), 1440)
    hours, mins = divmod(rest, 60)
    if days:
        return f"{days} kun {hours} soat" if hours else f"{days} kun"
    if hours:
        return f"{hours} soat {mins} daqiqa" if mins else f"{hours} soat"
    return f"{mins} daqiqa" if mins else "1 daqiqadan kam"


def countdown_line():
    """«⏳ Qabul tugashiga: 4 kun 18 soat» (oxirgi sutkada ⏰, oxirgi soatda 🔥)."""
    left = time_left()
    if not left:
        return ""
    sec = (DEADLINE_END - _now()).total_seconds()
    icon = "⏳" if sec >= 86400 else "⏰" if sec >= 3600 else "🔥"
    return f"{icon} Qabul tugashiga: <b>{left}</b>"


def closed_text():
    return ("⏰ <b>Ro‘yxatdan o‘tish yakunlandi.</b>\n\n"
            f"Oxirgi muddat {deadline_label()} edi — shundan keyin anketalar qabul qilinmaydi.\n\n"
            "Qiziqishingiz uchun rahmat! 📢 Natijalarni «Yangi Xatirchi» Telegram kanalida "
            "kuzatib boring.")

# PythonAnywhere bepul tarifida Telegram API ga faqat proxy orqali chiqiladi
if USE_PROXY:
    apihelper.proxy = {"https": "http://proxy.server:3128"}


# ------------------------------------------------------------------
# Telegram API: vaqtinchalik xatolarda qayta urinish.
# Katta oqimda Telegram «429 Too Many Requests» qaytarishi mumkin - telebot buni o‘zi
# qayta urinmaydi va keyingi savol foydalanuvchiga yetib bormay qolardi.
# ------------------------------------------------------------------
_raw_request = apihelper._make_request


def _request_with_retry(token, method_name, method="get", params=None, files=None, attempts=4):
    for attempt in range(attempts):
        last = attempt == attempts - 1
        try:
            # params nusxasi: telebot uni ichida o‘zgartiradi (timeout ni olib tashlaydi)
            return _raw_request(token, method_name, method=method,
                                params=dict(params) if params else params, files=files)
        except ApiTelegramException as e:
            wait = ((e.result_json or {}).get("parameters") or {}).get("retry_after", 1)
            if e.error_code != 429 or files or last or wait > 10:
                raise
            log.warning("Telegram cheklovi (429): %s s kutamiz (%s)", wait, method_name)
            time.sleep(wait)
        except requests.ConnectionError:
            # Ulanishning o‘zi bo‘lmadi - so‘rov Telegram’ga yetmagan, qayta urinish xavfsiz
            if files or last:
                raise
            time.sleep(1 + attempt)


apihelper._make_request = _request_with_retry

# Webhook rejimida threaded=False bo‘lishi shart
bot = telebot.TeleBot(BOT_TOKEN, threaded=False, parse_mode="HTML")
app = Flask(__name__)
st.init_db()

# ------------------------------------------------------------------
# Matnlar va tugmalar
# ------------------------------------------------------------------
BTN_BACK = "⬅️ Orqaga"
BTN_SKIP = "⏭ O‘tkazib yuborish"
BTN_CONTACT = "📱 Raqamni yuborish"
BTN_OTHER = "✍️ " + OTHER
USERNAME_SUFFIX = " — shuni ishlatish"
BTN_USERNAME_DONE = "✅ Username yaratdim"
NO_USERNAME_HINT = (
    "ℹ️ Sizda hali Telegram username yo‘q. Uni 1 daqiqada yaratish mumkin:\n"
    "<b>Sozlamalar (Settings) → Foydalanuvchi nomi (Username)</b> → nom o‘ylab toping → ✓\n\n"
    f"So‘ng pastdagi <b>{BTN_USERNAME_DONE}</b> tugmasini bosing."
)
BTN_NEXT = "➡️ Davom etish"
BTN_CLEAR = "🗑 Tozalash"

# Loyiha fayllari: qabul qilinadigan turlar va ularning ikonkalari
FILE_ICONS = {"document": "📄", "photo": "🖼", "video": "🎬", "audio": "🎵",
              "animation": "🎞", "voice": "🎤"}
MAX_ITEMS = 10

ANNOUNCE = (
    "🚀 <b>«Xatirchi raqamli yoshlari xakatoni – 2026»</b>\n"
    "\n"
    "💡 <b>Yo‘nalish:</b> «Eng yaxshi ijtimoiy va samarali innovatsion loyiha»\n"
    "\n"
    "👥 <b>Kimlar qatnasha oladi:</b> 17–30 yoshli O‘zbekiston fuqarolari, Xatirchi "
    "tumanida doimiy yoki vaqtincha ro‘yxatda turgan yoshlar (yakka yoki jamoa)\n"
    "\n"
    "📌 <b>Talab:</b> loyiha yangi, avval g‘olib bo‘lmagan, joriy etilmagan va "
    "MVP shaklida bo‘lishi kerak\n"
    "\n"
    "🏆 <b>G‘olib ishtirokchilarimiz uchun maxsus tayyorlangan qimmatbaho sovg‘alar va esdalik mukofotlari!</b>\n"
    "\n"
    "📍 Xatirchi tumani, «Farovon» MFY, «IT-shaharcha» binosi\n"
    "\n"
    "⏱ Ro‘yxatdan o‘tish 5–7 daqiqa vaqt oladi."
)

HELP = (
    "ℹ️ <b>Yordam</b>\n\n"
    "/start — bosh sahifa va ro‘yxatdan o‘tish\n"
    "/restart — anketani boshidan to‘ldirish\n"
    "/cancel — ro‘yxatdan o‘tishni bekor qilish\n"
    "/help — shu yordam\n\n"
    "Savollar bittadan beriladi. <b>⬅️ Orqaga</b> tugmasi oldingi savolga qaytaradi, "
    "<b>⏭ O‘tkazib yuborish</b> esa ixtiyoriy savollarda chiqadi."
)

SUCCESS = (
    "🎉 <b>Tabriklaymiz!</b> Siz «Xatirchi raqamli yoshlari xakatoni – 2026» tanloviga "
    "muvaffaqiyatli ro‘yxatdan o‘tdingiz.\n\n"
    "📢 Yangiliklarni «Yangi Xatirchi» Telegram kanalida kuzatib boring."
)

TECH_ERROR = (
    "⚠️ Texnik xatolik, birozdan so‘ng qayta urinib ko‘ring.\n\n"
    "💾 Javoblaringiz saqlab qo‘yildi — qaytadan to‘ldirish shart emas."
)

# Google Forma anketani rad etdi (forma o‘zgartirilgan/yopilgan) - foydalanuvchi qayta
# bossa ham foyda yo‘q, adminlar tuzatib /resend qiladi
FORM_ERROR = (
    "⚠️ Anketangizni hozircha qabul qilib bo‘lmadi — tashkilotchilarga xabar berildi.\n\n"
    "💾 Javoblaringiz saqlab qo‘yildi. Muammo hal qilingach, anketangiz avtomatik "
    "yuboriladi va sizga xabar keladi."
)
FORM_PROBLEMS = {"HTTP 400", "HTTP 401", "HTTP 403", "HTTP 404", "Forma yopilgan"}

ADMIN_HELP = (
    "\n\n👑 <b>Admin buyruqlari</b> (faqat sizga ko‘rinadi)\n"
    "/stats — statistika\n"
    "/export — barcha anketalar bitta Excel faylda\n"
    "/checkform — Google Forma bot bilan mosligini tekshirish\n"
    "/resend — yuborilmay qolgan anketalarni qayta yuborish"
)
ADMIN_COMMANDS = {"/stats", "/export", "/checkform", "/resend"}

AGE_STOP = "Afsuski, tanlovda 17 yoshdan 30 yoshgacha bo‘lgan yoshlar ishtirok eta oladi."


def announce_text():
    """E’lon + oxirgi muddat va qancha vaqt qolgani."""
    if DEADLINE_END is None:
        return ANNOUNCE
    if registration_open():
        return f"{ANNOUNCE}\n\n📅 <b>Oxirgi muddat:</b> {deadline_label()}\n{countdown_line()}"
    return f"{ANNOUNCE}\n\n⏰ <b>Ro‘yxatdan o‘tish yakunlandi</b> ({deadline_label()})."


def send_closed(chat_id):
    bot.send_message(chat_id, closed_text(), reply_markup=types.ReplyKeyboardRemove())


def esc(s):
    return html.escape(str(s), quote=False)


def ikb(*rows):
    """Inline klaviatura: ikb([("Matn", "callback"), ...], ...)"""
    kb = types.InlineKeyboardMarkup()
    for row in rows:
        kb.row(*[types.InlineKeyboardButton(t, url=d[4:]) if d.startswith("url:")
                 else types.InlineKeyboardButton(t, callback_data=d) for t, d in row])
    return kb


def norm(s):
    """Solishtirish uchun: apostroflarni bir xil qiladi, kichik harf, ortiqcha bo‘shliqsiz."""
    s = re.sub(r"[‘’ʻʼ`´']", "'", s or "")
    return re.sub(r"\s+", " ", s).strip().lower()


def clip(s, n):
    """Telegram limitlaridan (xabar 4096, izoh 1024 belgi) oshmasligi uchun qisqartiradi."""
    s = str(s)
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


# Bot tugmalarining yozuvlari. Ular hech qachon erkin matnli savolga javob bo‘la olmaydi:
# foydalanuvchi tugmani ikki marta bossa, ikkinchisi keyingi savolga (masalan, «Manzil»ga)
# javob bo‘lib tushib qolmasin
BUTTON_TEXTS = {norm(f"{icon} {v}") for q in QUESTIONS if q["type"] == "choice"
                for icon, v in q["options"]}
BUTTON_TEXTS |= {norm(b) for b in (BTN_BACK, BTN_SKIP, BTN_CONTACT, BTN_OTHER,
                                   BTN_USERNAME_DONE, BTN_NEXT, BTN_CLEAR)}
FREE_TEXT_TYPES = {"text", "fio", "longtext", "members", "phone", "username", "email"}


def is_button_text(text):
    return norm(text) in BUTTON_TEXTS or text.endswith(USERNAME_SUFFIX)


# ------------------------------------------------------------------
# Savollar bo‘yicha harakat
# ------------------------------------------------------------------
def next_index(i, answers):
    for j in range(i + 1, len(QUESTIONS)):
        if is_applicable(QUESTIONS[j], answers):
            return j
    return None


def prev_index(i, answers):
    for j in range(i - 1, -1, -1):
        if is_applicable(QUESTIONS[j], answers):
            return j
    return None


def progress(i, answers):
    """(joriy raqam, jami). Ishtirok shakli hali tanlanmagan bo‘lsa, jamoa savollari ham sanaladi."""
    idx = [j for j, q in enumerate(QUESTIONS)
           if not q.get("when") or answers.get(q["when"][0]) is None or is_applicable(q, answers)]
    pos = idx.index(i) + 1 if i in idx else i + 1
    return pos, len(idx)


def progress_bar(pos, total, width=10):
    filled = round(width * (pos - 1) / total)
    return "▰" * filled + "▱" * (width - filled)


def short_title(q):
    """Xulosa uchun savolning qisqa nomi."""
    return q["text"].split(" (")[0].split(":")[0]


def link_items(answers, key):
    """Loyiha havola/fayllari ro‘yxati (eski satr ko‘rinishidagi javob ham qo‘llab-quvvatlanadi)."""
    v = answers.get(key)
    if isinstance(v, str) and v:
        return [{"t": "url", "v": v}]
    return v if isinstance(v, list) else []


def item_label(it):
    if it.get("t") == "file":
        return f"{FILE_ICONS.get(it.get('kind'), '📎')} {clip(it['name'], 60)}"
    return f"🔗 {clip(it['v'], 80)}"


def question_keyboard(q, first, user, answers=None):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    t = q["type"]
    has_items = t == "link_or_file" and bool(link_items(answers or {}, q["key"]))
    if t == "link_or_file":
        kb.input_field_placeholder = "Havola yoki fayl yuboring 📎"
        if has_items:
            kb.row(BTN_NEXT)
            kb.row(BTN_CLEAR)
    elif t == "choice":
        kb.input_field_placeholder = "Variantni tanlang 👇"
        for icon, value in q["options"]:
            kb.row(f"{icon} {value}")
        if q.get("other"):
            kb.row(BTN_OTHER)
    elif t == "phone":
        kb.input_field_placeholder = "+998 90 123 45 67"
        kb.row(types.KeyboardButton(BTN_CONTACT, request_contact=True))
    elif t == "username" and user is not None:
        kb.input_field_placeholder = "@username"
        kb.row(f"@{user.username}{USERNAME_SUFFIX}" if user.username else BTN_USERNAME_DONE)
    else:
        kb.input_field_placeholder = "Javobingizni yozing…"

    nav = []
    if not first:
        nav.append(BTN_BACK)
    if not q["required"] and not has_items:
        nav.append(BTN_SKIP)
    if nav:
        kb.row(*nav)
    return kb if kb.keyboard else types.ReplyKeyboardRemove()


def confirm_keyboard(q, bits):
    rows = []
    for i, label in enumerate(q["short"]):
        mark = "✅" if bits[i] == "1" else "⬜️"
        rows.append([(f"{mark} {i + 1}. {label}", f"cf:{i}")])
    if "0" not in bits:
        rows.append([("➡️ Davom etish", "cf:go")])
    return ikb(*rows)


def ask(chat_id, s, user=None):
    """Joriy savolni yuboradi va u foydalanuvchiga yetib borganini belgilaydi."""
    msg = _send_question(chat_id, s, user)
    s["shown"], s["asked_id"] = s["step"], msg.message_id
    st.mark_shown(s["user_id"], s["step"], msg.message_id)


def _send_question(chat_id, s, user):
    i = s["step"]
    q = QUESTIONS[i]
    a = s["answers"]
    pos, total = progress(i, a)
    first = prev_index(i, a) is None

    cd = countdown_line()  # «⏳ Qabul tugashiga: 4 kun 18 soat»
    text = (f"📋 <b>Savol {pos}/{total}</b>   {progress_bar(pos, total)}\n"
            + (f"{cd}\n" if cd else "")
            + f"\n{q['icon']} <b>{esc(q['text'])}</b>")
    if not q["required"]:
        text += "\n<i>(ixtiyoriy savol)</i>"

    if q["type"] == "confirm":
        text += "\n\n" + "\n\n".join(f"<b>{n}.</b> {esc(o)}" for n, o in enumerate(q["options"], 1))
        text += "\n\nIkkala bandni ham belgilash shart."
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.row(BTN_BACK)
        bot.send_message(chat_id, text, reply_markup=kb)
        bits = s["sub"] if s["sub"] and len(s["sub"]) == len(q["options"]) else "0" * len(q["options"])
        return bot.send_message(chat_id, "👇 Belgilang:", reply_markup=confirm_keyboard(q, bits))

    if q.get("hint"):
        text += "\n\n" + q["hint"]
    if q["type"] == "username" and user is not None and not user.username:
        text += "\n\n" + NO_USERNAME_HINT
    items = link_items(a, q["key"]) if q["type"] == "link_or_file" else []
    if items:
        text += (f"\n\n📦 <b>Yuborilganlar ({len(items)} ta):</b>\n"
                 + "\n".join(esc(item_label(it)) for it in items))
    if s.get("sub") == "other":
        text = f"{q['icon']} <b>{esc(q['text'])}</b>\n\n✍️ Iltimos, o‘z variantingizni yozing."
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, input_field_placeholder="O‘z variantingiz…")
        kb.row(BTN_BACK)
        return bot.send_message(chat_id, text, reply_markup=kb)
    return bot.send_message(chat_id, text, reply_markup=question_keyboard(q, first, user, a),
                            disable_web_page_preview=True)


def start_filling(chat_id, user):
    if not registration_open():  # muddat tugagan - yangi anketa boshlanmaydi
        send_closed(chat_id)
        return
    s = {"user_id": user.id, "status": st.FILLING, "step": 0, "sub": None, "answers": {},
         "shown": -1, "asked_id": 0}
    st.save_session(s)
    cd = countdown_line()
    bot.send_message(
        chat_id,
        f"✨ Ajoyib, {esc(user.first_name or 'do‘stim')}! Boshladik.\n\n"
        "Savollarga birma-bir javob bering. Istalgan payt <b>⬅️ Orqaga</b> "
        "tugmasi bilan oldingi savolga qaytishingiz mumkin."
        + (f"\n\n{cd} (oxirgi muddat: {deadline_label()})" if cd else ""),
    )
    ask(chat_id, s, user)


def advance(chat_id, s, user):
    """Keyingi savolga o‘tadi yoki xulosani ko‘rsatadi."""
    s["sub"] = None
    n = next_index(s["step"], s["answers"])
    if n is None:
        s["status"] = st.REVIEW
        st.save_session(s)
        log.info("xulosa ko‘rsatildi: user=%s", s["user_id"])
        show_review(chat_id, s)
    else:
        s["step"] = n
        st.save_session(s)
        ask(chat_id, s, user)


def reject(chat_id, s, text, **kw):
    """Noto‘g‘ri javob: log’ga (javob matnisiz) yozadi va ogohlantirish yuboradi."""
    log.info("rad etildi: user=%s savol=%s", s["user_id"], QUESTIONS[s["step"]]["key"])
    bot.send_message(chat_id, text, **kw)


def stop_registration(chat_id, user_id, reason):
    log.info("to‘xtatildi: user=%s sabab=%s", user_id, reason)
    st.reset_session(user_id, st.STOPPED)
    bot.send_message(
        chat_id,
        f"😔 {esc(reason)}\n\nQiziqishingiz uchun rahmat! Agar ma’lumotni xato kiritgan "
        "bo‘lsangiz, /restart buyrug‘i bilan qaytadan boshlashingiz mumkin.",
        reply_markup=types.ReplyKeyboardRemove(),
    )


# ------------------------------------------------------------------
# Javoblarni tekshirish (validatsiya)
# Har bir funksiya (qiymat, xato_matni) qaytaradi
# ------------------------------------------------------------------
# O‘zbekiston operator va shahar kodlari (+998 dan keyingi 2 raqam).
# Google Formadagi tekshiruv faqat +998 raqamlarni qabul qiladi.
UZ_CODES = {
    # mobil operatorlar
    "20", "33", "50", "55", "77", "88", "90", "91", "93", "94", "95", "97", "98", "99",
    # shahar (statsionar) kodlari
    "61", "62", "65", "66", "67", "69", "70", "71", "72", "73", "74", "75", "76", "78", "79",
}
# Matn ichidan raqamni topadi: 901234567, 90 123 45 67, (90) 123-45-67, 90.123.45.67,
# +998901234567, 998 90 123 45 67, 8 90 123 45 67, "raqamim: 90 123 45 67" ...
_SEP = r"[\s\-.]{0,2}"
PHONE_FIND_RE = re.compile(
    r"(?<![\d+])(?:\+?\s?998" + _SEP + r"|8" + _SEP + r")?"
    r"\(?(\d{2})\)?" + _SEP + r"(\d{3})" + _SEP + r"(\d{2})" + _SEP + r"(\d{2})(?!\d)"
)
URL_RE = re.compile(r"https?://[^\s<>\"']+\.[^\s<>\"']+", re.I)
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
USERNAME_RE = re.compile(r"^@?([A-Za-z][A-Za-z0-9_]{3,31})$")
DATE_RE = re.compile(r"^(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})$")


def v_text(t, min_len=1):
    t = (t or "").strip()
    if not t:
        return None, "Javob bo‘sh bo‘lmasligi kerak."
    if len(t) > 1000:
        return None, f"Javob 1000 belgidan oshmasligi kerak (hozir {len(t)} ta). Qisqartirib yozing."
    if len(t) < min_len:
        return None, (f"Iltimos, batafsilroq yozing — kamida {min_len} ta belgi "
                      f"(hozir {len(t)} ta).")
    return t, None


def v_fio(t):
    t, err = v_text(t)
    if err:
        return None, err
    t = " ".join(t.split())
    if len(t.split()) < 2 or re.search(r"\d", t):
        return None, "F.I.Sh. kamida 2 ta so‘zdan iborat bo‘lishi kerak. Masalan: <i>Karimov Jasur</i>"
    return t, None


def find_uz_phone(text):
    """Matn ichidan birinchi haqiqiy O‘zbekiston raqamini topib, chiroyli ko‘rinishga keltiradi."""
    for mt in PHONE_FIND_RE.finditer(text or ""):
        code, a, b, c = mt.groups()
        if code in UZ_CODES:
            return f"+998 {code} {a} {b} {c}"
    return None


def beautify_phones(text):
    """Matndagi barcha O‘zbekiston raqamlarini +998 XX XXX XX XX ko‘rinishiga keltiradi."""
    def repl(mt):
        code, a, b, c = mt.groups()
        return f"+998 {code} {a} {b} {c}" if code in UZ_CODES else mt.group(0)
    return PHONE_FIND_RE.sub(repl, text)


def v_phone(t):
    phone = find_uz_phone(t)
    if phone:
        return phone, None
    digits = re.sub(r"\D", "", t or "")
    if len(digits) >= 10 and not digits.startswith(("998", "8")):
        err = "Faqat O‘zbekiston raqamlari (+998) qabul qilinadi."
    elif len(digits) >= 9:
        err = "Bunday operator kodi yo‘q. Raqamni tekshirib qayta yozing."
    else:
        err = "Telefon raqami topilmadi."
    return None, err + " Masalan: <i>+998 90 123 45 67</i> yoki <i>90 123 45 67</i>"


def v_members(t):
    """Jamoa a’zolari: uzun matn + ichidagi telefon raqamlari chiroyli ko‘rinishga keltiriladi."""
    t, err = v_text(t, 20)
    return (None, err) if err else (beautify_phones(t), None)


def v_username(t):
    t = (t or "").strip()
    if t.endswith(USERNAME_SUFFIX):
        t = t[: -len(USERNAME_SUFFIX)]
    t = re.sub(r"^(https?://)?(t\.me|telegram\.me)/", "", t)
    m = USERNAME_RE.match(t)
    if not m:
        return None, "Foydalanuvchi nomi noto‘g‘ri. Masalan: <i>@username</i>"
    return "@" + m.group(1), None


def v_email(t):
    t = (t or "").strip()
    if not EMAIL_RE.match(t) or len(t) > 254:
        return None, "E-mail manzil noto‘g‘ri. Masalan: <i>ism@gmail.com</i>"
    return t.lower(), None


def match_option(q, t):
    """Tugma yoki qo‘lda yozilgan matnni variantga moslaydi."""
    n = norm(t)
    for icon, value in q["options"]:
        if n in (norm(value), norm(f"{icon} {value}")):
            return value
    if q.get("other") and n in (norm(OTHER), norm(BTN_OTHER)):
        return OTHER
    return None


# ------------------------------------------------------------------
# Javobni qabul qilish
# ------------------------------------------------------------------
def handle_answer(m, s):
    chat_id, user = m.chat.id, m.from_user
    # 1) Joriy savol foydalanuvchiga yetib bormagan (masalan, Telegram xatosi tufayli) -
    #    xabarni javob deb olmaymiz, avval savolni ko‘rsatamiz
    if s.get("shown") != s["step"]:
        ask(chat_id, s, user)
        return
    # 2) Savol yuborilishidan OLDIN yozilgan xabar (tugmani ikki marta bosish, sekin internetda
    #    qayta yuborish) oldingi savolga tegishli - joriy savolga javob sifatida olinmaydi
    if m.message_id < s.get("asked_id", 0):
        log.info("eskirgan xabar e’tiborsiz qoldirildi: user=%s savol=%s", user.id, s["step"] + 1)
        return

    q = QUESTIONS[s["step"]]
    a = s["answers"]
    key = q["key"]
    text = m.text if m.content_type == "text" else None

    # ⬅️ Orqaga
    if text == BTN_BACK:
        if s.get("sub") == "other":
            s["sub"] = None
        else:
            p = prev_index(s["step"], a)
            if p is not None:
                s["step"], s["sub"] = p, None
        st.save_session(s)
        ask(chat_id, s, user)
        return

    # ⏭ O‘tkazib yuborish (faqat ixtiyoriy savollarda)
    if text == BTN_SKIP and not q["required"]:
        a[key] = None
        a.pop(key + "__other", None)
        advance(chat_id, s, user)
        return

    # Loyiha havolasi yoki fayllari
    if q["type"] == "link_or_file":
        handle_link_or_file(m, s, q, text)
        return

    # Telefon: kontakt tugmasi orqali
    if m.content_type == "contact":
        if q["type"] != "phone":
            bot.send_message(chat_id, "Iltimos, javobni matn ko‘rinishida yozing ✍️")
            return
        text = m.contact.phone_number

    if text is None:
        # Albom (bir nechta rasm) yuborilsa, har biriga emas - bir marta javob beramiz
        if not m.media_group_id or st.claim(f"mg:{m.media_group_id}"):
            bot.send_message(chat_id, "Iltimos, javobni matn ko‘rinishida yozing ✍️")
        return

    # «Boshqa» tanlangandan keyingi o‘z varianti
    if s.get("sub") == "other":
        if is_button_text(text):
            reject(chat_id, s, "✍️ Iltimos, o‘z variantingizni matn bilan yozing.")
            return
        val, err = v_text(text)
        if err:
            reject(chat_id, s, "⚠️ " + err)
            return
        a[key], a[key + "__other"] = OTHER, val
        advance(chat_id, s, user)
        return

    t = q["type"]
    if t == "confirm":
        bot.send_message(chat_id, "☝️ Iltimos, yuqoridagi tugmalar orqali ikkala bandni belgilang.")
        return

    # Tugma yozuvi erkin matnli savolga javob bo‘la olmaydi (masalan, «🏡 Doimiy
    # ro‘yxatdan o‘tganman» ikki marta bosilsa, ikkinchisi «Manzil»ga yozilib qolmasin)
    own_button = t == "username" and (text == BTN_USERNAME_DONE or text.endswith(USERNAME_SUFFIX))
    if t in FREE_TEXT_TYPES and is_button_text(text) and not own_button:
        reject(chat_id, s, "✍️ Bu savolga javobni matn bilan yozing 👇",
               reply_markup=question_keyboard(q, prev_index(s["step"], a) is None, user, a))
        return

    if t == "choice":
        val = match_option(q, text)
        if val is None:
            reject(chat_id, s, "⚠️ Iltimos, pastdagi variantlardan birini tanlang 👇",
                   reply_markup=question_keyboard(q, prev_index(s["step"], a) is None, user))
            return
        if val in q.get("stop", {}):
            stop_registration(chat_id, user.id, q["stop"][val])
            return
        if val == OTHER:
            s["sub"] = "other"
            st.save_session(s)
            ask(chat_id, s, user)
            return
        a[key] = val
        a.pop(key + "__other", None)
        advance(chat_id, s, user)
        return

    if t == "date":
        mt = DATE_RE.match(text.strip())
        if not mt:
            reject(chat_id, s, "⚠️ Sanani <b>KK.OO.YYYY</b> ko‘rinishida yozing. "
                               "Masalan: <i>14.03.2005</i>")
            return
        d, mo, y = map(int, mt.groups())
        try:
            born = date(y, mo, d)
        except ValueError:
            reject(chat_id, s, "⚠️ Bunday sana mavjud emas. Qaytadan tekshirib yozing.")
            return
        today = datetime.now(st.TZ).date()
        if born >= today:
            reject(chat_id, s, "⚠️ Tug‘ilgan sana kelajakda bo‘lishi mumkin emas.")
            return
        age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
        if not 17 <= age <= 30:
            stop_registration(chat_id, user.id, AGE_STOP)
            return
        a[key] = born.strftime("%d.%m.%Y")
        advance(chat_id, s, user)
        return

    # «Username yaratdim»: Telegram har xabarda joriy username’ni yuboradi - shuni olamiz
    if t == "username" and text == BTN_USERNAME_DONE:
        if not user.username:
            reject(chat_id, s, "⚠️ Username hali ko‘rinmayapti. Uni sozlamalarda saqlaganingizni "
                               "tekshiring yoki shu yerga qo‘lda yozing: <i>@username</i>")
            return
        a[key] = "@" + user.username
        advance(chat_id, s, user)
        return

    validators = {
        "text": v_text,
        "fio": v_fio,
        "longtext": lambda x: v_text(x, 20),
        "members": v_members,
        "phone": v_phone,
        "username": v_username,
        "email": v_email,
    }
    val, err = validators[t](text)
    if err:
        reject(chat_id, s, "⚠️ " + err)
        return
    # Uzun matn boshqa uzun javob bilan aynan bir xil bo‘lsa - bu qayta yuborilgan eski xabar
    # (masalan, «Muammo» matni «Yechim» savoliga tushib qolmasin)
    if t in ("longtext", "members") and any(
            a.get(q2["key"]) == val for q2 in QUESTIONS
            if q2["key"] != key and q2["type"] in ("longtext", "members")):
        reject(chat_id, s, "⚠️ Bu matnni oldingi savolga yuborgan edingiz. Iltimos, aynan shu "
                           "savolga mos javob yozing 👇")
        return
    a[key] = val
    advance(chat_id, s, user)


# ------------------------------------------------------------------
# Loyiha havolalari va fayllari
# ------------------------------------------------------------------
def message_link(chat_id, message_id):
    """Kanal xabariga havola (yopiq kanalda faqat a’zolar ocha oladi)."""
    cid = str(chat_id)
    if cid.startswith("@"):
        return f"https://t.me/{cid[1:]}/{message_id}"
    if cid.startswith("-100"):
        return f"https://t.me/c/{cid[4:]}/{message_id}"
    return None


def file_name(m):
    ct = m.content_type
    obj = getattr(m, ct, None)
    name = getattr(obj, "file_name", None) if ct != "photo" else None
    defaults = {"document": "fayl", "photo": "rasm.jpg", "video": "video.mp4",
                "audio": "audio.mp3", "animation": "animatsiya.mp4", "voice": "ovozli_xabar.ogg"}
    return name or defaults.get(ct, "fayl")


def store_file(m, s):
    """Faylni tashkilotchilar kanaliga (yoki adminlarga) nusxalaydi.
    Fayl yuklab olinmaydi - Telegram ichida nusxalanadi, shuning uchun hajm cheklovi yo‘q.
    Qaytaradi: element dict yoki None (saqlab bo‘lmasa)."""
    a = s["answers"]
    # Izoh 1024 belgidan oshmasligi kerak - uzun nomlar qisqartiriladi
    caption = (f"📎 <b>{esc(clip(a.get('project_name') or 'Loyiha fayli', 100))}</b>\n"
               f"👤 {esc(clip(a.get('fio') or '—', 100))}\n"
               f"📞 {esc(a.get('phone') or '—')}\n"
               f"🆔 <code>{m.from_user.id}</code>")
    item = {"t": "file", "kind": m.content_type, "name": file_name(m), "link": None}

    if STORAGE_CHAT_ID:
        try:
            res = bot.copy_message(STORAGE_CHAT_ID, m.chat.id, m.message_id,
                                   caption=caption, parse_mode="HTML")
            item["link"] = message_link(STORAGE_CHAT_ID, res.message_id)
            return item
        except Exception as e:
            log.error("Faylni kanalga saqlab bo‘lmadi (STORAGE_CHAT_ID ni tekshiring): %s", e)

    # Kanal sozlanmagan yoki xatolik: fayl adminlarga yuboriladi
    sent = False
    for admin_id in ADMIN_IDS:
        try:
            bot.copy_message(admin_id, m.chat.id, m.message_id, caption=caption, parse_mode="HTML")
            sent = True
        except Exception as e:
            log.error("Faylni adminga yuborib bo‘lmadi: admin=%s, %s", admin_id, e)
    return item if sent else None


def handle_link_or_file(m, s, q, text):
    chat_id, user, key = m.chat.id, m.from_user, q["key"]
    items = link_items(s["answers"], key)

    if text == BTN_NEXT:
        if not items and q["required"]:
            reject(chat_id, s, "⚠️ Avval havola yoki fayl yuboring.")
            return
        s["answers"][key] = items or None
        advance(chat_id, s, user)
        return

    if text == BTN_CLEAR:
        s["answers"][key] = []
        s["sub"] = None
        st.save_session(s)
        bot.send_message(chat_id, "🗑 Tozalandi. Havola yoki fayl yuboring 📎",
                         reply_markup=question_keyboard(q, prev_index(s["step"], s["answers"]) is None,
                                                        user, s["answers"]))
        return

    if len(items) >= MAX_ITEMS:
        reject(chat_id, s, f"⚠️ Ko‘pi bilan {MAX_ITEMS} ta havola yoki fayl yuborish mumkin. "
                           f"«{BTN_NEXT}» ni bosing.")
        return

    if m.content_type in FILE_ICONS:
        item = store_file(m, s)
        if item is None:
            reject(chat_id, s, "⚠️ Faylni saqlab bo‘lmadi. Birozdan so‘ng qayta yuboring "
                               "yoki uning o‘rniga havola yuboring.")
            return
        new_items = [item]
    elif text:
        urls = [u.rstrip(".,;:!?)»") for u in URL_RE.findall(text)]
        urls = [u for u in urls if len(u) <= 1000]
        if not urls:
            reject(chat_id, s, "⚠️ Havola <b>http://</b> yoki <b>https://</b> bilan boshlanishi "
                               "kerak. Yoki fayl yuklang 📎")
            return
        new_items = [{"t": "url", "v": u} for u in urls]
    else:
        bot.send_message(chat_id, "Iltimos, havola yoki fayl yuboring 📎")
        return

    total, first_in_album = None, True
    for it in new_items:
        cnt, first = st.append_item(user.id, key, it, group_id=m.media_group_id, limit=MAX_ITEMS)
        if cnt is None:
            break
        total, first_in_album = cnt, first
    if total is None:
        reject(chat_id, s, f"⚠️ Ko‘pi bilan {MAX_ITEMS} ta havola yoki fayl yuborish mumkin.")
        return
    log.info("loyiha materiali qo‘shildi: user=%s jami=%s", user.id, total)

    # Albom (bir nechta fayl birga) bo‘lsa, faqat birinchisiga javob beramiz
    if m.media_group_id and not first_in_album:
        return
    s = st.get_session(user.id)
    if m.media_group_id:
        ack = "✅ Fayllar qabul qilinmoqda…"
    else:
        ack = "✅ Qabul qilindi:\n" + "\n".join(esc(item_label(it)) for it in new_items)
        ack += f"\n\n📦 Jami: <b>{total} ta</b>"
    ack += f"\n\nYana havola yoki fayl yuborishingiz mumkin. Tayyor bo‘lsa — <b>{BTN_NEXT}</b> 👇"
    bot.send_message(chat_id, ack, disable_web_page_preview=True,
                     reply_markup=question_keyboard(q, prev_index(s["step"], s["answers"]) is None,
                                                    user, s["answers"]))


# ------------------------------------------------------------------
# Xulosa va yuborish
# ------------------------------------------------------------------
def display_value(q, answers, limit=None):
    v = answers.get(q["key"])
    if v in (None, "", []):
        return "—"
    if q["type"] == "confirm":
        return "✅ Tasdiqlangan"
    if q["type"] == "link_or_file":
        return "\n".join(item_label(it) for it in link_items(answers, q["key"])) or "—"
    if v == OTHER and q.get("other"):
        v = f"{OTHER}: {answers.get(q['key'] + '__other', '')}"
    v = str(v)
    if limit and len(v) > limit:
        v = v[:limit].rstrip() + "…"
    return v


def review_text(answers):
    parts = ["📋 <b>Javoblaringizni tekshiring</b>"]
    for q in QUESTIONS:
        if is_applicable(q, answers):
            parts.append(f"{q['icon']} <b>{esc(short_title(q))}</b>\n"
                         f"{esc(display_value(q, answers, limit=None if q.get('full') else 150))}")
    cd = countdown_line()
    parts.append((f"{cd} — shu vaqt ichida yuboring.\n" if cd else "") + "Hammasi to‘g‘rimi? 👇")
    return parts


def send_parts(chat_id, parts, reply_markup=None):
    """Uzun matnni Telegram limiti (4096) dan oshmaydigan bo‘laklarga bo‘lib yuboradi."""
    chunks, cur = [], ""
    for p in parts:
        p = clip(p, 3800)
        if cur and len(cur) + len(p) + 2 > 3800:
            chunks.append(cur)
            cur = p
        else:
            cur = f"{cur}\n\n{p}" if cur else p
    chunks.append(cur)
    msg = None
    for k, c in enumerate(chunks):
        msg = bot.send_message(chat_id, c, disable_web_page_preview=True,
                               reply_markup=reply_markup if k == len(chunks) - 1 else None)
    return msg


REVIEW_KB = (
    [("✅ Tasdiqlash va yuborish", "send")],
    [("✏️ Qaytadan to‘ldirish", "refill")],
)


def show_review(chat_id, s):
    bot.send_message(chat_id, "✨ Barcha savollarga javob berdingiz!",
                     reply_markup=types.ReplyKeyboardRemove())
    msg = send_parts(chat_id, review_text(s["answers"]), reply_markup=ikb(*REVIEW_KB))
    # Xulosadan oldin yozilgan (eskirgan) xabarlarga javob bermaslik uchun
    st.mark_shown(s["user_id"], s["step"], msg.message_id)


def first_missing(answers):
    """Javob berilmagan birinchi majburiy savol raqami (hammasi bo‘lsa - None)."""
    for i, q in enumerate(QUESTIONS):
        if q["required"] and is_applicable(q, answers) and answers.get(q["key"]) in (None, "", []):
            return i
    return None


def send_to_form(user_id, allowed=(st.REVIEW, st.FAILED)):
    """Anketani Formaga yuboradi va holatni yangilaydi.
    Qaytaradi: (True/False, sabab) yoki (None, "band") - boshqa so‘rov allaqachon yubormoqda."""
    # Holat atomar almashtiriladi - tugmani ikki marta bosish ikki marta yubormaydi
    if not st.set_status_if(user_id, allowed, st.SENDING):
        return None, "band"
    s = st.get_session(user_id)
    ok, reason = submit(s["answers"])
    if ok:
        st.mark_submitted(user_id, s["answers"] if KEEP_LOCAL_COPY else None)
        log.info("Ro‘yxatdan o‘tdi (Formaga yuborildi): user_id=%s", user_id)
    else:
        st.set_status_if(user_id, (st.SENDING,), st.FAILED)
        log.error("Formaga yuborilmadi: user_id=%s, sabab=%s", user_id, reason)
    return ok, reason


def success_keyboard():
    return ikb([("📢 «Yangi Xatirchi» kanali", "url:" + CHANNEL_URL)]) if CHANNEL_URL else None


def do_submit(chat_id, user):
    s = st.get_session(user.id)
    # Himoya: majburiy savol javobsiz qolgan bo‘lsa, Formaga yubormaymiz (Google rad etadi)
    idx = first_missing(s["answers"])
    if idx is not None:
        s.update(status=st.FILLING, step=idx, sub=None)
        st.save_session(s)
        bot.send_message(chat_id, "⚠️ Bu savolga javob berilmagan ekan — iltimos, to‘ldiring 👇")
        ask(chat_id, s, user)
        return
    try:
        bot.send_chat_action(chat_id, "typing")
    except Exception:
        pass
    ok, reason = send_to_form(user.id)
    if ok is None:
        return
    if ok:
        bot.send_message(chat_id, SUCCESS, reply_markup=success_keyboard())
        return
    form_problem = reason in FORM_PROBLEMS
    bot.send_message(chat_id, FORM_ERROR if form_problem else TECH_ERROR,
                     reply_markup=None if form_problem else ikb([("🔁 Qayta yuborish", "send")]))
    alert_failure(user.id, s["answers"], reason, form_problem)


# ------------------------------------------------------------------
# Adminlarga xabarlar
# ------------------------------------------------------------------
_last_alert = {}


def notify_admins(text, reply_markup=None):
    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(admin_id, text, reply_markup=reply_markup,
                             disable_web_page_preview=True)
        except Exception as e:
            log.error("Adminga xabar yuborib bo‘lmadi: admin=%s, %s", admin_id, e)


def alert_failure(user_id, answers, reason, form_problem):
    """Anketa Formaga tushmasa adminlarga darhol xabar beradi.
    Bir xil sababli xabar 10 daqiqada ko‘pi bilan 1 marta yuboriladi (spam bo‘lmasin)."""
    now = time.time()
    if not ADMIN_IDS or now - _last_alert.get(reason, 0) < 600:
        return
    _last_alert[reason] = now
    text = ("⚠️ <b>Anketa Google Formaga yuborilmadi</b>\n\n"
            f"👤 {esc(clip(answers.get('fio') or '—', 100))} (<code>{user_id}</code>)\n"
            f"💡 {esc(clip(answers.get('project_name') or '—', 100))}\n"
            f"❗ Sabab: <code>{esc(reason)}</code>\n"
            f"📦 Hozir yuborilmay turganlar: <b>{len(st.failed_user_ids())} ta</b>")
    if form_problem:
        # Google anketani rad etdi - ehtimol Forma tahrirlangan. Nima o‘zgarganini aniqlaymiz
        text += "\n\n" + report_text(check_form())[:2500]
    else:
        text += "\n\nFoydalanuvchi o‘zi ham «🔁 Qayta yuborish» ni bosishi mumkin."
    notify_admins(text, reply_markup=ikb([("🔁 Hammasini qayta yuborish", "adm:resend")],
                                         [("🔍 Formani tekshirish", "adm:check")]))


def resend_failed(chat_id, limit=10):
    """Yuborilmay qolgan anketalarni qayta yuboradi (admin uchun).
    Muvaffaqiyatli bo‘lsa, anketa egasiga ham xabar boradi.
    Bir martada 10 tagacha: bepul tarifda bitta worker bor - uzoq band qilib, boshqa
    foydalanuvchilarni kutdirib qo‘ymaslik uchun (qolganlari uchun /resend qayta bosiladi)."""
    ids = st.failed_user_ids()
    if not ids:
        bot.send_message(chat_id, "✅ Yuborilmay qolgan anketa yo‘q.")
        return
    batch = ids[:limit]
    bot.send_message(chat_id, f"⏳ {len(batch)} ta anketa qayta yuborilmoqda…")
    sent, reasons = 0, Counter()
    for uid in batch:
        ok, reason = send_to_form(uid, allowed=(st.FAILED,))
        if ok:
            sent += 1
            try:
                bot.send_message(uid, SUCCESS, reply_markup=success_keyboard())
            except Exception as e:
                log.warning("Foydalanuvchiga xabar yuborib bo‘lmadi: user=%s, %s", uid, e)
        elif ok is False:
            reasons[reason] += 1
    text = f"🔁 <b>Qayta yuborish natijasi</b>\n\n✅ Yuborildi: <b>{sent} ta</b>"
    if reasons:
        text += f"\n❌ Yana yuborilmadi: <b>{sum(reasons.values())} ta</b> (" + ", ".join(
            f"{esc(r)}: {n}" for r, n in reasons.items()) + ")"
        if FORM_PROBLEMS & set(reasons):
            text += "\n\nForma bilan muammo bor — /checkform bilan tekshiring."
    left = len(ids) - len(batch)
    if left:
        text += f"\n\n📦 Yana {left} ta qoldi — /resend ni yana bosing."
    bot.send_message(chat_id, text)
    log.info("/resend: yuborildi=%s, xato=%s, qoldi=%s", sent, sum(reasons.values()), left)


# ------------------------------------------------------------------
# Buyruqlar
# ------------------------------------------------------------------
def private_only(m):
    return m.chat.type == "private"


@bot.message_handler(commands=["start"], func=private_only)
def cmd_start(m):
    s = st.get_session(m.from_user.id)
    status = s["status"]
    log.info("/start: user=%s holat=%s", m.from_user.id, status)
    if status == st.FAILED:
        # Muddat ichida yuborilgan, lekin texnik sabab bilan qolib ketgan - muddatdan keyin ham
        # qayta yuborish mumkin
        kb = ikb([("🔁 Qayta yuborish", "send")])
        note = "\n\n⚠️ Anketangiz hali yuborilmagan. Qayta urinib ko‘ring."
    elif status == st.SENDING:
        # Aynan hozir yuborilmoqda - «qayta yuborish» tugmasi dublikat qator yaratardi
        kb = None
        note = "\n\n⏳ Anketangiz hozir yuborilmoqda — natija haqida xabar keladi."
    elif not registration_open():
        kb = None  # muddat tugagan - ro‘yxatdan o‘tish tugmasi yo‘q
        note = "\n\n✅ Siz ro‘yxatdan o‘tgansiz." if st.has_submitted(m.from_user.id) else ""
    elif status == st.FILLING and (s["step"] > 0 or s["answers"]):
        kb = ikb([("▶️ Davom ettirish", "resume")], [("🔄 Boshidan boshlash", "restart")])
        note = "\n\n📝 Sizda to‘ldirilmagan anketa bor. Davom ettirasizmi?"
    elif status == st.REVIEW:
        kb = ikb([("▶️ Anketani ko‘rish", "resume")], [("🔄 Boshidan boshlash", "restart")])
        note = "\n\n📝 Anketangiz tayyor, faqat tasdiqlash qoldi."
    else:
        kb = ikb([("📝 Ro‘yxatdan o‘tish", "reg")])
        note = ""
    bot.send_message(m.chat.id, announce_text() + note, reply_markup=kb)


@bot.message_handler(commands=["help"], func=private_only)
def cmd_help(m):
    bot.send_message(m.chat.id, HELP + (ADMIN_HELP if m.from_user.id in ADMIN_IDS else ""))


@bot.message_handler(commands=["cancel"], func=private_only)
def cmd_cancel(m):
    log.info("/cancel: user=%s", m.from_user.id)
    st.reset_session(m.from_user.id)
    bot.send_message(m.chat.id, "❌ Ro‘yxatdan o‘tish bekor qilindi.\n\nQayta boshlash uchun /start",
                     reply_markup=types.ReplyKeyboardRemove())


@bot.message_handler(commands=["restart"], func=private_only)
def cmd_restart(m):
    log.info("/restart: user=%s", m.from_user.id)
    begin_registration(m.chat.id, m.from_user)


def begin_registration(chat_id, user):
    if not registration_open():
        send_closed(chat_id)
        return
    if st.has_submitted(user.id):
        st.reset_session(user.id)
        bot.send_message(
            chat_id,
            "ℹ️ Siz allaqachon ro‘yxatdan o‘tgansiz. Yana bir loyiha yubormoqchimisiz?",
            reply_markup=ikb([("✅ Ha", "again:yes"), ("❌ Yo‘q", "again:no")]),
        )
        return
    start_filling(chat_id, user)


# ---- Admin buyruqlari ----
def is_admin(m):
    return private_only(m) and m.from_user.id in ADMIN_IDS


@bot.message_handler(commands=["stats"], func=is_admin)
def cmd_stats(m):
    log.info("/stats: admin=%s", m.from_user.id)
    x = st.stats()
    rows = [[("📥 Excel yuklab olish", "adm:export")], [("🔍 Formani tekshirish", "adm:check")]]
    if x["failed"]:
        rows.append([(f"🔁 Qayta yuborish ({x['failed']} ta)", "adm:resend")])
    deadline = ""
    if DEADLINE_END is not None:
        left = time_left()
        deadline = f"\n\n📅 Muddat: {deadline_label()} — " + (
            f"<b>{left}</b> qoldi" if left else "<b>yakunlangan</b>")
    bot.send_message(
        m.chat.id,
        "📊 <b>Statistika</b>\n\n"
        f"✅ Yuborilgan anketalar: <b>{x['total']}</b>\n"
        f"👤 Noyob ishtirokchilar: <b>{x['users']}</b>\n"
        f"✍️ Hozir to‘ldirayotganlar: <b>{x['filling']}</b>\n"
        f"⚠️ Yuborilmay qolganlar: <b>{x['failed']}</b>" + deadline,
        reply_markup=ikb(*rows),
    )


@bot.message_handler(commands=["checkform"], func=is_admin)
def cmd_checkform(m):
    log.info("/checkform: admin=%s", m.from_user.id)
    run_form_check(m.chat.id)


def run_form_check(chat_id):
    bot.send_chat_action(chat_id, "typing")
    # Xatolar ko‘p bo‘lsa hisobot uzun bo‘ladi - 4096 belgilik bo‘laklarga bo‘lib yuboriladi
    send_parts(chat_id, report_text(check_form()).split("\n\n"))


@bot.message_handler(commands=["resend"], func=is_admin)
def cmd_resend(m):
    log.info("/resend: admin=%s", m.from_user.id)
    resend_failed(m.chat.id)


@bot.message_handler(commands=["export"], func=is_admin)
def cmd_export(m):
    send_export(m.chat.id, m.from_user.id)


def send_export(chat_id, admin_id):
    rows = st.export_rows()
    if not rows:
        note = "" if KEEP_LOCAL_COPY else "\n\n(Nusxa saqlash o‘chiq: .env da KEEP_LOCAL_COPY=1 qiling.)"
        bot.send_message(chat_id, "📭 Eksport uchun ma’lumot yo‘q." + note)
        return
    bot.send_chat_action(chat_id, "upload_document")
    now = datetime.now(st.TZ)
    data = io.BytesIO(build_xlsx(rows))
    name = f"xakaton_royxat_{now:%Y-%m-%d_%H-%M}.xlsx"
    data.name = name

    team = sum(1 for r in rows if r[3].get("participation") == TEAM)
    failed = sum(1 for r in rows if not r[2].startswith("Formaga"))
    caption = (f"📊 <b>Ishtirokchilar ro‘yxati</b>\n\n"
               f"👥 Jami: <b>{len(rows)} ta</b> anketa\n"
               f"🙋 Yakka: {len(rows) - team}   ·   👥 Jamoa: {team}\n")
    if failed:
        caption += f"⚠️ Formaga yuborilmagan: {failed} ta (jadvalda qizil)\n"
    caption += f"🕒 {now:%d.%m.%Y %H:%M}\n\n🔒 Shaxsiy ma’lumotlar — faqat tashkilotchilar uchun."
    bot.send_document(chat_id, data, visible_file_name=name, caption=caption)
    log.info("/export: admin=%s, %s ta anketa", admin_id, len(rows))


# ------------------------------------------------------------------
# Inline tugmalar
# ------------------------------------------------------------------
def drop_markup(c):
    try:
        bot.edit_message_reply_markup(c.message.chat.id, c.message.message_id, reply_markup=None)
    except Exception:
        pass


def handle_admin_callback(c, data):
    # Tugmani kim bosganini qayta tekshiramiz: faqat ADMIN_IDS va faqat shaxsiy chat
    if c.from_user.id not in ADMIN_IDS or c.message.chat.type != "private":
        log.warning("Ruxsatsiz admin tugmasi: user=%s data=%s", c.from_user.id, data)
        bot.answer_callback_query(c.id, "⛔ Ruxsat yo‘q", show_alert=True)
        return
    bot.answer_callback_query(c.id)
    chat_id = c.message.chat.id
    if data == "adm:export":
        send_export(chat_id, c.from_user.id)
    elif data == "adm:check":
        run_form_check(chat_id)
    elif data == "adm:resend":
        drop_markup(c)
        resend_failed(chat_id)


@bot.callback_query_handler(func=lambda c: True)
def on_callback(c):
    uid, chat_id, data = c.from_user.id, c.message.chat.id, c.data or ""
    s = st.get_session(uid)
    log.info("tugma: user=%s data=%s holat=%s savol=%s", uid, data, s["status"], s["step"] + 1)

    # Tugmani tez-tez ikki marta bosish (sekin internetda ko‘p uchraydi): ikkinchisi e’tiborsiz.
    # Aks holda, masalan, ✅ belgisi qo‘yilib-olib tashlanib qolardi
    if not st.debounce(uid, data):
        bot.answer_callback_query(c.id)
        return

    if data.startswith("adm:"):
        handle_admin_callback(c, data)
        return

    # Muddat tugagan: anketa boshlash va to‘ldirish yopiq («Yuborish» pastda alohida tekshiriladi)
    if data not in ("send", "again:no") and not registration_open():
        bot.answer_callback_query(c.id, "⏰ Ro‘yxatdan o‘tish yakunlandi", show_alert=True)
        drop_markup(c)
        send_closed(chat_id)
        return

    if data == "reg":
        bot.answer_callback_query(c.id)
        if s["status"] in (st.FILLING, st.REVIEW) and (s["step"] > 0 or s["answers"]):
            resume(chat_id, s, c.from_user)
        else:
            drop_markup(c)
            begin_registration(chat_id, c.from_user)

    elif data == "resume":
        bot.answer_callback_query(c.id)
        drop_markup(c)
        if s["status"] in (st.FILLING, st.REVIEW):
            resume(chat_id, s, c.from_user)
        else:
            begin_registration(chat_id, c.from_user)

    elif data in ("restart", "refill"):
        bot.answer_callback_query(c.id, "🔄 Boshidan boshlaymiz")
        drop_markup(c)
        if s["status"] in (st.SENDING,):
            return
        start_filling(chat_id, c.from_user)

    elif data.startswith("again:"):
        bot.answer_callback_query(c.id)
        drop_markup(c)
        if data == "again:yes":
            if s["status"] in (st.FILLING, st.REVIEW) and (s["step"] > 0 or s["answers"]):
                resume(chat_id, s, c.from_user)  # allaqachon to‘ldirishni boshlagan
            else:
                start_filling(chat_id, c.from_user)
        else:
            bot.send_message(chat_id, "👌 Yaxshi! Ishtirokingiz uchun rahmat. Omad tilaymiz! 🍀")

    elif data == "send":
        if s["status"] not in (st.REVIEW, st.FAILED):
            bot.answer_callback_query(c.id, "Bu tugma endi faol emas.")
            drop_markup(c)
            return
        # Yangi anketa muddatdan keyin yuborilmaydi. FAILED - muddat ichida yuborilgan, lekin
        # texnik sabab bilan qolib ketgan: uni qayta yuborishga ruxsat beriladi
        if s["status"] == st.REVIEW and not registration_open(_now() - SEND_LAG_GRACE):
            bot.answer_callback_query(c.id, "⏰ Ro‘yxatdan o‘tish yakunlandi", show_alert=True)
            drop_markup(c)
            send_closed(chat_id)
            return
        bot.answer_callback_query(c.id, "⏳ Yuborilmoqda…")
        drop_markup(c)
        do_submit(chat_id, c.from_user)

    elif data.startswith("cf:"):
        q = QUESTIONS[s["step"]]
        if s["status"] != st.FILLING or q["type"] != "confirm":
            bot.answer_callback_query(c.id, "Bu tugma endi faol emas.")
            drop_markup(c)
            if s["status"] == st.FILLING and s["shown"] != s["step"]:
                ask(chat_id, s, c.from_user)  # joriy savol yetib bormagan - qayta ko‘rsatamiz
            return
        n = len(q["options"])
        bits = s["sub"] if s["sub"] and len(s["sub"]) == n else "0" * n
        if data == "cf:go":
            if "0" in bits:
                bot.answer_callback_query(c.id, "Ikkala bandni ham belgilang.", show_alert=True)
                return
            bot.answer_callback_query(c.id, "✅ Tasdiqlandi")
            drop_markup(c)
            s["answers"][q["key"]] = list(q["options"])
            advance(chat_id, s, c.from_user)
            return
        k = int(data[3:])
        bits = bits[:k] + ("0" if bits[k] == "1" else "1") + bits[k + 1:]
        s["sub"] = bits
        st.save_session(s)
        bot.answer_callback_query(c.id, "✅ Belgilandi" if bits[k] == "1" else "Belgi olib tashlandi")
        try:
            bot.edit_message_reply_markup(chat_id, c.message.message_id,
                                          reply_markup=confirm_keyboard(q, bits))
        except Exception:
            pass
    else:
        bot.answer_callback_query(c.id)


def resume(chat_id, s, user):
    if s["status"] == st.REVIEW:
        show_review(chat_id, s)
    else:
        ask(chat_id, s, user)


# ------------------------------------------------------------------
# Oddiy xabarlar
# ------------------------------------------------------------------
@bot.message_handler(func=private_only,
                     content_types=["text", "contact", "photo", "video", "document", "audio",
                                    "voice", "sticker", "video_note", "animation", "location",
                                    "venue", "poll"])
def on_message(m):
    # Noma’lum yoki ruxsatsiz buyruq hech qachon anketaga javob sifatida qabul qilinmaydi.
    # Admin buyrug‘ini oddiy foydalanuvchi yozsa - «bunday buyruq yo‘q» (borligi ham oshkor qilinmaydi)
    if m.content_type == "text" and m.text.startswith("/"):
        cmd = m.text.split()[0].split("@")[0].lower()
        if cmd in ADMIN_COMMANDS:
            log.warning("Ruxsatsiz admin buyrug‘i: user=%s buyruq=%s", m.from_user.id, cmd)
        bot.send_message(m.chat.id, "🤷 Bunday buyruq yo‘q. Mavjud buyruqlar: /help")
        return

    s = st.get_session(m.from_user.id)
    # Javob matni log’ga yozilmaydi (shaxsiy ma’lumot) - faqat qaysi savolga kelgani
    log.info("xabar: user=%s holat=%s savol=%s turi=%s", m.from_user.id, s["status"],
             s["step"] + 1, m.content_type)
    if s["status"] in (st.FILLING, st.REVIEW) and not registration_open(m.date):
        # Xabar muddat tugagandan keyin yozilgan (vaqt - Telegram’dagi yozilgan payti,
        # server navbatidagi kechikish hisobga olinmaydi). Javoblar o‘chirilmaydi:
        # muddat uzaytirilsa, foydalanuvchi davom ettira oladi
        send_closed(m.chat.id)
    elif s["status"] == st.FILLING:
        handle_answer(m, s)
    elif s["status"] == st.REVIEW:
        if m.message_id < s["asked_id"]:
            return  # xulosa chiqishidan oldin yozilgan eskirgan xabar
        bot.send_message(m.chat.id, "☝️ Iltimos, anketani tasdiqlang yoki qaytadan to‘ldiring.",
                         reply_markup=ikb(*REVIEW_KB))
    elif s["status"] == st.SENDING:
        bot.send_message(m.chat.id, "⏳ Anketangiz yuborilmoqda — natija haqida xabar keladi.")
    elif s["status"] == st.FAILED:
        bot.send_message(m.chat.id, "⚠️ Anketangiz hali yuborilmagan.",
                         reply_markup=ikb([("🔁 Qayta yuborish", "send")]))
    elif st.has_submitted(m.from_user.id):
        bot.send_message(m.chat.id, "✅ Siz tanlovga ro‘yxatdan o‘tgansiz. Yangiliklarni «Yangi "
                                    "Xatirchi» Telegram kanalida kuzatib boring."
                         + ("\n\nYana bir loyiha yubormoqchi bo‘lsangiz — /restart"
                            if registration_open() else ""),
                         reply_markup=success_keyboard())
    elif not registration_open():
        send_closed(m.chat.id)
    else:
        cd = countdown_line()
        bot.send_message(m.chat.id, "👋 Tanlovda ishtirok etish uchun ro‘yxatdan o‘ting 👇"
                         + (f"\n\n{cd}" if cd else ""),
                         reply_markup=ikb([("📝 Ro‘yxatdan o‘tish", "reg")]))


@bot.my_chat_member_handler()
def on_bot_added(u):
    """Admin botni kanalga admin qilib qo‘shsa - STORAGE_CHAT_ID ni aytib beradi."""
    if (u.new_chat_member.status == "administrator"
            and u.chat.type in ("channel", "supergroup")
            and u.from_user.id in ADMIN_IDS):
        log.info("Bot kanalga admin qilindi: chat_id=%s", u.chat.id)
        bot.send_message(
            u.from_user.id,
            f"📁 Bot «{esc(u.chat.title)}» ga admin qilindi.\n\n"
            "Loyiha fayllari shu yerga saqlanishi uchun <code>.env</code> faylga yozing:\n"
            f"<code>STORAGE_CHAT_ID={u.chat.id}</code>\n\n"
            "So‘ng botni qayta ishga tushiring (PythonAnywhere’da — <b>Reload</b>).",
        )


# ------------------------------------------------------------------
# Flask: webhook
# ------------------------------------------------------------------
@app.route("/")
def index():
    if DEADLINE_END is None:
        return "Xakaton bot ishlayapti ✅"
    left = time_left()
    state = f"qabul ochiq, {left} qoldi" if left else "qabul yakunlangan"
    return f"Xakaton bot ishlayapti ✅ · Ro‘yxatga olish: {deadline_label()} gacha ({state})"


_recent = {}


def flooding(user_id, limit=30, window=10.0):
    """Bir foydalanuvchi 10 soniyada 30 tadan ko‘p xabar/tugma yuborsa (spam) - vaqtincha
    e’tiborsiz. Bepul tarifda bitta worker bor: bitta spamchi hammani kutdirib qo‘ymasin.
    (10 ta fayllik albom bu chegaraga yetmaydi.)"""
    if user_id in ADMIN_IDS:
        return False
    now = time.time()
    q = _recent.get(user_id)
    if q is None:
        if len(_recent) > 10000:  # xotira to‘lib ketmasin
            for u in [u for u, d in _recent.items() if not d or d[-1] < now - window]:
                del _recent[u]
        q = _recent[user_id] = deque()
    while q and q[0] < now - window:
        q.popleft()
    q.append(now)
    if len(q) == limit + 1:
        log.warning("Spam: user=%s 10 soniyada %s+ xabar - vaqtincha e’tiborsiz", user_id, limit)
    return len(q) > limit


def update_user_id(update):
    for obj in (update.message, update.callback_query, update.my_chat_member):
        if obj is not None and getattr(obj, "from_user", None):
            return obj.from_user.id
    return None


@app.route(f"/{WEBHOOK_SECRET_PATH}", methods=["POST"])
def webhook():
    # Faqat Telegram yuborgan so‘rovlar qabul qilinadi
    if WEBHOOK_SECRET_TOKEN and \
            request.headers.get("X-Telegram-Bot-Api-Secret-Token") != WEBHOOK_SECRET_TOKEN:
        abort(403)
    try:
        update = types.Update.de_json(request.get_data(as_text=True))
        # Server sekin javob bersa, Telegram o‘sha update’ni qayta yuboradi - ikki marta ishlamaymiz
        if not st.claim(f"u:{update.update_id}"):
            log.info("takroriy update e’tiborsiz: %s", update.update_id)
            return "OK", 200
        uid = update_user_id(update)
        if uid and flooding(uid):
            return "OK", 200
        bot.process_new_updates([update])
    except Exception:
        # Xatoda ham 200 qaytaramiz, aks holda Telegram shu xabarni qayta-qayta yuboradi
        log.exception("Update’ni qayta ishlashda xatolik")
    return "OK", 200
