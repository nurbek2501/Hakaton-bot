# -*- coding: utf-8 -*-
"""
PythonAnywhere’ga bitta buyruq bilan joylash (va keyinchalik yangilash).

1) Bir marta, brauzerda: Web → Add a new web app → Next → Manual configuration → Python 3.10 → Next
2) Bash konsolida:
       git clone https://github.com/nurbek2501/Hakaton-bot.git ~/xakaton_bot
       python3.10 ~/xakaton_bot/deploy_pa.py

Skript nima qiladi:
  - kutubxonalarni o‘rnatadi (requirements.txt)
  - .env yaratadi: bot tokeni so‘raladi (yozganda ekranda ko‘rinmaydi) va Telegram’da
    tekshiriladi; maxfiy kalitlar avtomatik yaratiladi. .env bor bo‘lsa - saqlanadi
  - WSGI faylini yozadi - PythonAnywhere buni ko‘rib web-ilovani o‘zi qayta ishga tushiradi
  - sayt ishlayotganini tekshiradi, Telegram webhook’ni o‘rnatadi va Google Formani tekshiradi

Kod yangilanganda:  cd ~/xakaton_bot && git pull && python3.10 deploy_pa.py
"""
import getpass
import glob
import os
import re
import secrets
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(HERE, ".env")
WSGI_DIR = os.environ.get("PA_WSGI_DIR", "/var/www")
PROXY = {"https": "http://proxy.server:3128", "http": "http://proxy.server:3128"}
TOKEN_RE = re.compile(r"^\d{5,}:[A-Za-z0-9_-]{30,}$")
ENV_KEYS = [
    ("BOT_TOKEN", "@BotFather bergan token"),
    ("WEBHOOK_SECRET_PATH", "webhook manzilining maxfiy qismi (avtomatik)"),
    ("WEBHOOK_SECRET_TOKEN", "Telegram so‘rovlarini tekshirish kaliti (avtomatik)"),
    ("WEBHOOK_HOST", "web-ilova manzili (avtomatik)"),
    ("USE_PROXY", "bepul tarifda 1 (avtomatik aniqlanadi)"),
    ("ADMIN_IDS", "adminlar Telegram ID’lari, vergul bilan"),
    ("KEEP_LOCAL_COPY", "1 - /export uchun anketalar nusxasi saqlanadi"),
    ("STORAGE_CHAT_ID", "loyiha fayllari kanali (ixtiyoriy)"),
    ("CHANNEL_URL", "«Yangi Xatirchi» kanali havolasi (ixtiyoriy)"),
]
WSGI_TEMPLATE = '''# Xakaton bot - deploy_pa.py tomonidan yozilgan
import os
import sys

project_home = {home!r}
if project_home not in sys.path:
    sys.path.insert(0, project_home)

from dotenv import load_dotenv
load_dotenv(os.path.join(project_home, ".env"))

from app import app as application  # noqa
'''

# Konsolda emoji va ‘ ’ belgilari xato bermasligi uchun
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass


def say(msg=""):
    print(msg, flush=True)


def fail(msg):
    say("❌ " + msg)
    sys.exit(1)


def find_wsgi():
    """Web-ilovaning WSGI fayli: /var/www/<login>_pythonanywhere_com_wsgi.py"""
    files = sorted(glob.glob(os.path.join(WSGI_DIR, "*_wsgi.py")))
    user = (os.environ.get("USER") or getpass.getuser()).lower()
    mine = [f for f in files if os.path.basename(f).lower().startswith(user + "_")]
    return (mine or files or [None])[0]


def domain_of(wsgi_path):
    # nurbek_pythonanywhere_com_wsgi.py -> nurbek.pythonanywhere.com
    return os.path.basename(wsgi_path)[: -len("_wsgi.py")].replace("_", ".")


def need_proxy(requests):
    """Bepul tarifda tashqi internetga faqat proxy orqali chiqiladi - to‘g‘ridan-to‘g‘ri urinib ko‘ramiz."""
    s = requests.Session()
    s.trust_env = False  # muhitdagi proxy sozlamalarini hisobga olmay tekshiramiz
    try:
        s.get("https://api.telegram.org", timeout=6)
        return False
    except requests.RequestException:
        return True


def read_env():
    env = {}
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env


def write_env(env):
    lines = ["# deploy_pa.py tomonidan yozilgan. Bu faylni hech kimga bermang!", ""]
    for key, comment in ENV_KEYS:
        lines += [f"# {comment}", f"{key}={env.get(key, '')}", ""]
    # Qo‘lda qo‘shilgan boshqa sozlamalar (masalan REG_DEADLINE) ham saqlanadi
    known = {k for k, _ in ENV_KEYS}
    extra = [k for k in env if k not in known]
    if extra:
        lines += ["# Qo‘shimcha sozlamalar"] + [f"{k}={env[k]}" for k in extra] + [""]
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    try:
        os.chmod(ENV_PATH, 0o600)  # faqat siz o‘qiy olasiz
    except OSError:
        pass


def check_token(requests, token, proxies):
    """Tokenni Telegram’da tekshiradi. Qaytaradi: bot username yoki None."""
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getMe", proxies=proxies, timeout=20)
        data = r.json()
        return data["result"]["username"] if data.get("ok") else None
    except (requests.RequestException, ValueError, KeyError):
        return None


def ask_token(requests, proxies, first=None):
    for _ in range(5):
        token = first or getpass.getpass("   🔑 Bot tokeni (yozganda ko‘rinmaydi, keyin Enter): ").strip()
        first = None
        if not TOKEN_RE.match(token):
            say("   ⚠️ Token ko‘rinishi noto‘g‘ri (masalan: 1234567890:AAH...). Qayta kiriting.")
            continue
        username = check_token(requests, token, proxies)
        if username:
            say(f"   ✅ Token to‘g‘ri — bot: @{username}")
            return token, username
        say("   ⚠️ Telegram bu tokenni qabul qilmadi (eskirgan yoki xato). Qayta kiriting.")
    fail("Token 5 marta noto‘g‘ri kiritildi.")


def ask_admins():
    while True:
        v = input("   👑 Admin Telegram ID (bir nechta bo‘lsa vergul bilan; @userinfobot dan bilasiz): ").strip()
        ids = re.findall(r"\d{5,}", v)
        if ids:
            return ",".join(ids)
        say("   ⚠️ Kamida bitta raqamli ID kiriting.")


def main():
    say("🚀 Xakaton botni PythonAnywhere’ga joylash\n")

    wsgi = find_wsgi()
    if not wsgi:
        fail("Web-ilova topilmadi. Avval brauzerda: Web → Add a new web app → Next → "
             "Manual configuration → Python 3.10 → Next. Keyin skriptni qayta ishga tushiring.")
    domain = domain_of(wsgi)
    say(f"🌐 Web-ilova: https://{domain}")

    say("\n📦 1/5 Kutubxonalar o‘rnatilmoqda (1–2 daqiqa)…")
    r = subprocess.run([sys.executable, "-m", "pip", "install", "--user", "-q",
                        "-r", os.path.join(HERE, "requirements.txt")])
    if r.returncode:
        fail("Kutubxonalarni o‘rnatib bo‘lmadi — yuqoridagi xabarni o‘qing.")
    import requests  # o‘rnatilgandan keyin

    say("\n🔌 2/5 Internet sozlamasi tekshirilmoqda…")
    use_proxy = need_proxy(requests)
    proxies = PROXY if use_proxy else None
    say("   " + ("Bepul tarif — proxy orqali (USE_PROXY=1)" if use_proxy else "To‘g‘ridan-to‘g‘ri ulanish (USE_PROXY=0)"))

    say("\n🔑 3/5 Sozlamalar (.env)…")
    env = read_env()
    if env.get("BOT_TOKEN"):
        say("   .env mavjud — sozlamalar saqlanadi.")
        new = getpass.getpass("   Yangi bot tokeni (Enter — eskisini qoldirish): ").strip()
        env["BOT_TOKEN"], bot_username = ask_token(requests, proxies, first=new or env["BOT_TOKEN"])
        if not env.get("ADMIN_IDS"):
            env["ADMIN_IDS"] = ask_admins()
    else:
        env["BOT_TOKEN"], bot_username = ask_token(requests, proxies)
        env["ADMIN_IDS"] = ask_admins()
    # Bo‘sh yoki yo‘q bo‘lsa - avtomatik yaratiladi (mavjudlari o‘zgarmaydi)
    if not env.get("WEBHOOK_SECRET_PATH"):
        env["WEBHOOK_SECRET_PATH"] = secrets.token_urlsafe(24)
    if not env.get("WEBHOOK_SECRET_TOKEN"):
        env["WEBHOOK_SECRET_TOKEN"] = secrets.token_urlsafe(32)
    if not env.get("KEEP_LOCAL_COPY"):
        env["KEEP_LOCAL_COPY"] = "1"
    env["WEBHOOK_HOST"] = f"https://{domain}"
    env["USE_PROXY"] = "1" if use_proxy else "0"
    write_env(env)
    say("   ✅ .env saqlandi (faqat sizga ochiq)")

    say("\n♻️ 4/5 Web-ilova sozlanmoqda va qayta ishga tushirilmoqda…")
    with open(wsgi, "w", encoding="utf-8") as f:
        f.write(WSGI_TEMPLATE.format(home=HERE))
    ok, status = False, None
    for _ in range(8):  # WSGI fayl o‘zgargach PythonAnywhere ilovani bir necha soniyada qayta yuklaydi
        time.sleep(5)
        try:
            resp = requests.get(f"https://{domain}/", proxies=proxies, timeout=15)
            status = resp.status_code
            if status == 200 and "ishlayapti" in resp.text:
                ok = True
                break
        except requests.RequestException:
            pass
    if ok:
        say(f"   ✅ Sayt ishlayapti: https://{domain}")
    elif status is None:
        say(f"   ℹ️ Konsoldan tekshirib bo‘lmadi. Brauzerda oching: https://{domain} — "
            "«Xakaton bot ishlayapti ✅» chiqishi kerak.")
    else:
        say(f"   ⚠️ Sayt javobi: HTTP {status}. Web sahifasida «Reload» ni bosing va Error log’ni ko‘ring.")

    say("\n🔗 5/5 Telegram webhook o‘rnatilmoqda…\n")
    r = subprocess.run([sys.executable, os.path.join(HERE, "set_webhook.py")])
    if r.returncode:
        fail("Webhook o‘rnatilmadi — yuqoridagi xabarni o‘qing.")

    say("\n" + "=" * 50)
    say(f"🎉 Tayyor! Botni sinab ko‘ring: https://t.me/{bot_username}")
    say("=" * 50)
    say("• Har oy: Web sahifasida «Run until 1 month from today» "
        "(«Bugundan boshlab 1 oygacha amal qiladi») ni bosing.")
    say("• Kod yangilansa: cd ~/xakaton_bot && git pull && python3.10 deploy_pa.py")


if __name__ == "__main__":
    main()
