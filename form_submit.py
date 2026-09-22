# -*- coding: utf-8 -*-
"""Javoblarni Google Formaga yuborish."""
import logging
import os
import time

import requests

from questions import OTHER, QUESTIONS, is_applicable

log = logging.getLogger(__name__)

FORM_BASE = ("https://docs.google.com/forms/d/e/"
             "1FAIpQLScPFxOzw3y4qCiPZ4hezU3gq-IRZawzxDfGugXqJhVbP0rzBw")
FORM_URL = FORM_BASE + "/formResponse"
VIEW_URL = FORM_BASE + "/viewform"

PROXY_URL = "http://proxy.server:3128"


def _proxies():
    # PythonAnywhere bepul tarifida tashqi internetga faqat proxy orqali chiqiladi
    if os.getenv("USE_PROXY", "0") == "1":
        return {"http": PROXY_URL, "https": PROXY_URL}
    return None


def items_to_text(items):
    """Loyiha havolalari/fayllari ro‘yxatini bitta satrga aylantiradi (Forma va CSV uchun).
    Masalan: "https://github.com/x | https://t.me/c/123/45 (taqdimot.pdf)" """
    if isinstance(items, str):
        return items
    parts = []
    for it in items or []:
        if it.get("t") == "file":
            parts.append(f"{it['link']} ({it['name']})" if it.get("link")
                         else f"Telegram fayl: {it['name']}")
        else:
            parts.append(it["v"])
    return " | ".join(parts)


def build_payload(answers):
    """Javoblardan Forma uchun (kalit, qiymat) kortejlar ro‘yxatini tuzadi."""
    data = []
    for q in QUESTIONS:
        if not is_applicable(q, answers):
            continue  # shartli savol berilmagan - yuborilmaydi
        value = answers.get(q["key"])
        if value in (None, "", []):
            continue  # ixtiyoriy savol o‘tkazib yuborilgan - yuborilmaydi
        name = "entry." + q["entry"]

        if q["type"] == "date":
            day, month, year = value.split(".")
            data += [(name + "_year", str(int(year))),
                     (name + "_month", str(int(month))),
                     (name + "_day", str(int(day)))]
        elif q["type"] == "confirm":
            # checkbox: bir xil kalit takrorlanadi
            data += [(name, v) for v in value]
        elif q["type"] == "link_or_file":
            data.append((name, items_to_text(value)))
        elif q.get("other") and value == OTHER:
            data += [(name, "__other_option__"),
                     (name + ".other_option_response", answers.get(q["key"] + "__other", ""))]
        else:
            data.append((name, value))

    data += [("fvv", "1"), ("pageHistory", "0")]
    return data


# Vaqtinchalik xatolar: Google javobni yozmagan, qayta urinish xavfsiz
RETRY_STATUSES = {429, 500, 502, 503, 504}
RETRY_PAUSES = (0, 2, 5)  # 3 ta urinish: darhol, 2 s va 5 s dan keyin


def submit(answers):
    """Formaga yuboradi. Qaytaradi: (muvaffaqiyatli_mi, izoh).

    Google javobni qabul qilsa HTTP 200, rad etsa (majburiy maydon yo‘q, variant matni
    formadagiga mos emas va h.k.) HTTP 400 qaytaradi - 400 da qayta urinilmaydi.
    Ulanib bo‘lmasa yoki Google vaqtincha ishlamasa (5xx/429) - avtomatik qayta urinadi.
    """
    data = build_payload(answers)
    reason = ""
    for pause in RETRY_PAUSES:
        if pause:
            time.sleep(pause)
        try:
            resp = requests.post(FORM_URL, data=data, proxies=_proxies(), timeout=(10, 30),
                                 headers={"User-Agent": "Mozilla/5.0 (XakatonBot)"})
        except requests.ReadTimeout:
            # So‘rov Google’ga yetib borgan bo‘lishi mumkin - qayta yuborsak jadvalda
            # dublikat paydo bo‘ladi. Shuning uchun avtomatik takrorlamaymiz.
            log.error("Google Forma javob bermadi (ReadTimeout)")
            return False, "ReadTimeout"
        except requests.ConnectionError as e:
            # Ulanishning o‘zi bo‘lmadi - so‘rov yetib bormagan, qayta urinish xavfsiz
            reason = type(e).__name__
            log.warning("Google Formaga ulanib bo‘lmadi: %s", reason)
            continue
        except requests.RequestException as e:
            # Faqat xatolik turi yoziladi, shaxsiy ma’lumotlar emas
            log.error("Google Formaga yuborishda xatolik: %s", type(e).__name__)
            return False, type(e).__name__
        if resp.status_code == 200:
            if "closedform" in resp.url:
                log.error("Google Forma yopilgan (javob qabul qilmayapti)")
                return False, "Forma yopilgan"
            return True, "200"
        reason = "HTTP %s" % resp.status_code
        if resp.status_code not in RETRY_STATUSES:
            break
        log.warning("Google Forma vaqtincha javob bermadi: %s", reason)
    log.error("Google Forma javobi: %s", reason)
    return False, reason
