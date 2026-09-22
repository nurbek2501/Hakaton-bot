# -*- coding: utf-8 -*-
"""
Webhookni o‘rnatish uchun bir martalik skript.
Ishga tushirish (PythonAnywhere Bash konsolida):
    cd ~/xakaton_bot && python3.10 set_webhook.py
"""
import os
import re
import sys

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

# Konsolda emoji va ‘ ’ belgilari xato bermasligi uchun
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

import telebot  # noqa: E402
from telebot import apihelper, types  # noqa: E402

TOKEN = os.getenv("BOT_TOKEN", "").strip()
HOST = os.getenv("WEBHOOK_HOST", "").strip().rstrip("/")
PATH = os.getenv("WEBHOOK_SECRET_PATH", "").strip("/ ")
SECRET = os.getenv("WEBHOOK_SECRET_TOKEN", "").strip()
ADMIN_IDS = [int(x) for x in re.findall(r"\d+", os.getenv("ADMIN_IDS", ""))]

if os.getenv("USE_PROXY", "0") == "1":
    apihelper.proxy = {"https": "http://proxy.server:3128"}


def main():
    if not TOKEN or not HOST or not PATH:
        raise SystemExit("❌ .env faylda BOT_TOKEN, WEBHOOK_HOST va WEBHOOK_SECRET_PATH to‘ldirilishi kerak.")

    bot = telebot.TeleBot(TOKEN, threaded=False)
    me = bot.get_me()
    print(f"🤖 Bot: @{me.username}")

    url = f"{HOST}/{PATH}"
    bot.remove_webhook()
    ok = bot.set_webhook(
        url=url,
        secret_token=SECRET or None,
        allowed_updates=["message", "callback_query", "my_chat_member"],
        drop_pending_updates=True,
        # Bepul tarifda bitta worker: Telegram bir vaqtda ko‘pi bilan 10 ta so‘rov yuborsin,
        # qolganlarini o‘zida navbatda ushlab tursin (PythonAnywhere navbati to‘lib 502 bermasin)
        max_connections=10,
    )
    print("✅ Webhook o‘rnatildi" if ok else "❌ Webhook o‘rnatilmadi")

    setup_commands(bot)

    # Bot profilidagi tavsiflar (foydalanuvchi /start bosishdan oldin ko‘radi)
    try:
        bot.set_my_description(
            "🚀 «Xatirchi raqamli yoshlari xakatoni – 2026» tanloviga ro‘yxatdan o‘tish boti.\n\n"
            "🏆 Mukofot jamg‘armasi: 150 mln so‘m\n"
            "👥 17–30 yoshli yoshlar uchun\n\n"
            "Boshlash uchun «Start» tugmasini bosing 👇"
        )
        bot.set_my_short_description("🚀 «Xatirchi raqamli yoshlari xakatoni – 2026» — ro‘yxatdan o‘tish")
    except Exception as e:  # eski kutubxona versiyasida bo‘lmasligi mumkin
        print("ℹ️ Tavsif o‘rnatilmadi:", type(e).__name__)

    info = bot.get_webhook_info()
    print("\n--- getWebhookInfo ---")
    print("url:                 ", info.url.replace(PATH, "<WEBHOOK_SECRET_PATH>"))
    print("pending_update_count:", info.pending_update_count)
    print("last_error_message:  ", info.last_error_message or "yo‘q ✅")

    # Google Forma bot savollariga mosmi - joylashda bir marta tekshiramiz
    from form_check import check_form, report_text
    print("\n" + report_text(check_form(), html_mode=False))


USER_COMMANDS = [
    ("start", "🏠 Bosh sahifa"),
    ("restart", "🔄 Boshidan to‘ldirish"),
    ("cancel", "❌ Bekor qilish"),
    ("help", "ℹ️ Yordam"),
]
ADMIN_COMMANDS = [
    ("stats", "📊 Statistika"),
    ("export", "📥 Barcha anketalar (Excel)"),
    ("checkform", "🔍 Google Formani tekshirish"),
    ("resend", "🔁 Yuborilmaganlarni qayta yuborish"),
]


def setup_commands(bot):
    """Menyu: hamma uchun oddiy buyruqlar, adminlarga esa qo‘shimcha admin buyruqlari.
    Admin buyruqlari boshqa foydalanuvchilar menyusida ko‘rinmaydi."""
    user = [types.BotCommand(c, d) for c, d in USER_COMMANDS]
    admin = user + [types.BotCommand(c, d) for c, d in ADMIN_COMMANDS]
    bot.set_my_commands(user)
    for admin_id in ADMIN_IDS:
        try:
            bot.set_my_commands(admin, scope=types.BotCommandScopeChat(admin_id))
            print(f"👑 Admin menyusi o‘rnatildi: {admin_id}")
        except Exception as e:  # admin botga hali /start bosmagan bo‘lishi mumkin
            print(f"⚠️ Admin {admin_id} uchun menyu o‘rnatilmadi ({type(e).__name__}). "
                  "Admin botga /start bosgach, skriptni qayta ishga tushiring.")


if __name__ == "__main__":
    main()
