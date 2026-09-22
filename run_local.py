# -*- coding: utf-8 -*-
"""
Faqat LOKAL kompyuterda sinash uchun (polling rejimi).
PythonAnywhere’da bu fayl ISHLATILMAYDI — u yerda webhook ishlaydi.

    .env da USE_PROXY=0 qiling va:  python run_local.py

Diqqat: bu skript webhookni o‘chiradi. Sinab bo‘lgach, serverda
set_webhook.py ni qayta ishga tushiring.
"""
import sys

# Windows konsolida emoji va ‘ ’ belgilari xato bermasligi uchun
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

from app import BOT_TOKEN, bot  # noqa: E402

if __name__ == "__main__":
    if not BOT_TOKEN or ":" not in BOT_TOKEN:
        sys.exit("❌ .env faylda BOT_TOKEN to‘ldirilmagan. @BotFather bergan tokenni yozing.")
    me = bot.get_me()
    bot.remove_webhook()
    print(f"🤖 @{me.username} lokal rejimda ishga tushdi. To‘xtatish: Ctrl+C")
    bot.infinity_polling(skip_pending=True)
