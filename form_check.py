# -*- coding: utf-8 -*-
"""
Google Forma bot savollariga mosligini tekshirish.

Kimdir Formani tahrirlasa (variant matnini o‘zgartirsa, savolni o‘chirsa, yangi majburiy
savol qo‘shsa va h.k.), Google anketalarni HTTP 400 bilan rad eta boshlaydi. Bu tekshiruv
shunday o‘zgarishlarni oldindan topadi.

Ishlatilishi:  /checkform (admin), set_webhook.py, Formaga yuborishda HTTP 400 bo‘lganda.
"""
import json
import re

import requests

from form_submit import VIEW_URL, _proxies
from questions import QUESTIONS

# FB_PUBLIC_LOAD_DATA_ ichidagi savol turlari
T_SHORT, T_PARAGRAPH, T_RADIO, T_DROPDOWN, T_CHECKBOX, T_SECTION, T_DATE = 0, 1, 2, 3, 4, 8, 9
TEXTUAL = {T_SHORT, T_PARAGRAPH}
EXPECTED_TYPES = {
    "fio": TEXTUAL, "text": TEXTUAL, "longtext": TEXTUAL, "members": TEXTUAL,
    "phone": TEXTUAL, "username": TEXTUAL, "email": TEXTUAL, "link_or_file": TEXTUAL,
    "choice": {T_RADIO, T_DROPDOWN}, "confirm": {T_CHECKBOX}, "date": {T_DATE},
}
# Bot telefonni doim shu ko‘rinishda yuboradi - formadagi regex uni qabul qilishi kerak
SAMPLE_PHONE = "+998 90 123 45 67"


def _fetch():
    r = requests.get(VIEW_URL, proxies=_proxies(), timeout=(10, 30),
                     headers={"User-Agent": "Mozilla/5.0 (XakatonBot)"})
    return r.url, r.status_code, r.text


def _parse_entries(items):
    """Formadagi savollar: {entry_id: {...}}"""
    entries = {}
    for it in items:
        if len(it) < 5 or not it[4]:
            continue
        for e in it[4]:
            raw = e[1] or []
            entries[str(e[0])] = {
                "title": it[1] or "",
                "type": it[3],
                "required": bool(e[2]),
                "options": [o[0] for o in raw if not (len(o) > 4 and o[4])],
                "other": any(len(o) > 4 and o[4] for o in raw),
                "validation": e[4] if len(e) > 4 else None,
                "date_flags": e[7] if len(e) > 7 else None,
            }
    return entries


def _phone_regex_ok(validation):
    """Formadagi regex tekshiruvi bot yuboradigan raqamni qabul qiladimi."""
    for rule in validation or []:
        if rule and rule[0] == 4 and rule[2]:
            try:
                if not re.search(rule[2][0], SAMPLE_PHONE):
                    return False
            except re.error:
                pass
    return True


def check_form(html=None, url=None, status=200):
    """Qaytaradi: {"errors": [...], "warnings": [...], "ok": int}.
    errors   - anketalar Formaga tushmaydi, darhol tuzatish kerak;
    warnings - ishlaydi, lekin e’tibor bering."""
    errors, warnings = [], []
    if html is None:
        try:
            url, status, html = _fetch()
        except requests.RequestException as e:
            return {"errors": [f"Google Formani ochib bo‘lmadi ({type(e).__name__}). "
                               "Internet yoki PythonAnywhere proxy’sini tekshiring."],
                    "warnings": [], "ok": 0}

    if url and "accounts.google.com" in url:
        errors.append("Forma Google akkauntga kirishni talab qiladi — bot javob yubora olmaydi. "
                      "Sozlamalar → Javoblar: «1 ta javob bilan cheklash» va «Tashkilot "
                      "foydalanuvchilari bilan cheklash» ni o‘chiring.")
        return {"errors": errors, "warnings": warnings, "ok": 0}
    if url and "closedform" in url:
        errors.append("Forma javob qabul qilmayapti (yopilgan). Javoblar bo‘limida "
                      "«Javoblarni qabul qilish» ni yoqing.")
        return {"errors": errors, "warnings": warnings, "ok": 0}
    m = re.search(r"FB_PUBLIC_LOAD_DATA_ = (.*?);</script>", html, re.S)
    if status != 200 or not m:
        errors.append(f"Forma sahifasini o‘qib bo‘lmadi (HTTP {status}). Havola to‘g‘rimi?")
        return {"errors": errors, "warnings": warnings, "ok": 0}

    items = json.loads(m.group(1))[1][1] or []
    if 'name="emailAddress"' in html:
        errors.append("Formada «E-mail manzillarni yig‘ish» yoqilgan — bot bu maydonni "
                      "to‘ldirmaydi. Sozlamalar → Javoblar → «Yig‘ilmasin» qiling.")
    sections = sum(1 for it in items if len(it) > 3 and it[3] == T_SECTION)
    if sections:
        errors.append(f"Forma {sections + 1} ta bo‘limga (sahifaga) bo‘lingan — bot faqat "
                      "bitta sahifali formaga yuboradi. Bo‘lim ajratgichlarini olib tashlang.")

    form = _parse_entries(items)
    ok = 0
    for n, q in enumerate(QUESTIONS, 1):
        label = f"{n}-savol «{q['text'].split(' (')[0]}»"
        f = form.get(q["entry"])
        if f is None:
            errors.append(f"{label}: formada topilmadi (entry.{q['entry']}) — savol o‘chirilgan "
                          "yoki qaytadan yaratilgan. questions.py ni yangilash kerak.")
            continue
        problems = []
        if f["type"] not in EXPECTED_TYPES.get(q["type"], {f["type"]}):
            problems.append("savol turi o‘zgartirilgan")

        if q["type"] == "choice":
            stops = set(q.get("stop", {}))
            bot_values = [v for _, v in q["options"] if v not in stops]
            missing = [v for v in bot_values if v not in f["options"]]
            if missing:
                problems.append("formada bu variant(lar) yo‘q yoki matni o‘zgargan: "
                                + ", ".join(f"«{v}»" for v in missing))
            extra = [v for v in f["options"] if v not in bot_values and v not in stops]
            if extra:
                warnings.append(f"{label}: formada botda yo‘q variant bor: "
                                + ", ".join(f"«{v}»" for v in extra))
            if q.get("other") and not f["other"]:
                problems.append("formada «Boshqa» varianti o‘chirilgan")

        if q["type"] == "confirm":
            missing = [v for v in q["options"] if v not in f["options"]]
            if missing:
                problems.append("tasdiqlash bandi matni o‘zgargan: "
                                + ", ".join(f"«{v[:50]}…»" for v in missing))
            if len(f["options"]) > len(q["options"]):
                warnings.append(f"{label}: formaga yangi band qo‘shilgan — agar u majburiy "
                                "bo‘lsa, anketalar rad etiladi")

        if q["type"] == "date" and f["date_flags"]:
            with_time, with_year = (list(f["date_flags"]) + [0, 1])[:2]
            if with_time or not with_year:
                problems.append("sana formati o‘zgargan (vaqt qo‘shilgan yoki yil olib tashlangan)")

        if q["type"] == "phone" and not _phone_regex_ok(f["validation"]):
            problems.append(f"formadagi telefon tekshiruvi «{SAMPLE_PHONE}» ko‘rinishini qabul qilmaydi")

        if f["required"] and (not q["required"] or q.get("when")):
            problems.append("formada majburiy, botda esa ixtiyoriy yoki shartli — o‘tkazib "
                            "yuborilganda anketa rad etiladi")

        if problems:
            errors.append(f"{label}: " + "; ".join(problems))
        else:
            ok += 1

    known = {q["entry"] for q in QUESTIONS}
    for eid, f in form.items():
        if eid in known:
            continue
        title = f["title"][:60]
        if f["required"]:
            errors.append(f"Formaga yangi MAJBURIY savol qo‘shilgan: «{title}» — bot uni "
                          "to‘ldirmaydi, barcha anketalar rad etiladi")
        else:
            warnings.append(f"Formada botda yo‘q savol bor: «{title}» (ixtiyoriy, bo‘sh qoladi)")

    return {"errors": errors, "warnings": warnings, "ok": ok}


def report_text(result, html_mode=True):
    """Natijani o‘qish uchun qulay matnga aylantiradi (Telegram HTML yoki konsol)."""
    def b(s):
        return f"<b>{s}</b>" if html_mode else s

    def esc(s):
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") if html_mode else s

    lines = [b("🔍 Google Forma tekshiruvi"), ""]
    total = len(QUESTIONS)
    lines.append(f"✅ Mos savollar: {result['ok']}/{total}")
    if result["errors"]:
        lines += ["", b(f"❌ Xatolar ({len(result['errors'])}) — anketalar jadvalga tushmaydi:")]
        lines += [f"• {esc(e)}" for e in result["errors"]]
    if result["warnings"]:
        lines += ["", b(f"⚠️ Ogohlantirishlar ({len(result['warnings'])}):")]
        lines += [f"• {esc(w)}" for w in result["warnings"]]
    if not result["errors"]:
        lines += ["", "🎉 Hammasi joyida — anketalar Google Sheets jadvaliga to‘g‘ri tushadi."]
    return "\n".join(lines)
