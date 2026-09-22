# -*- coding: utf-8 -*-
"""
Savollar ro‘yxati.

MUHIM: variant matnlari ("value") Google Formadagi bilan harfma-harf bir xil
bo‘lishi shart (‘ U+2018 va ’ U+2019 belgilari bilan). "icon" faqat tugmada
ko‘rinadi, Formaga yuborilmaydi.

Turlar:
  text      - oddiy matn (1..1000 belgi)
  fio       - F.I.Sh. (kamida 2 so‘z)
  longtext  - uzun matn (20..1000 belgi)
  members   - jamoa a’zolari (uzun matn, ichidagi raqamlar +998 XX XXX XX XX ko‘rinishiga keltiriladi)
  date      - sana (KK.OO.YYYY), yosh 17..30
  choice    - bitta variant
  phone     - telefon raqami
  username  - Telegram @username
  email     - e-mail
  link_or_file - havola(lar) va/yoki fayl(lar), 10 tagacha
  confirm   - checkbox (barcha bandlar belgilanishi shart)

"other": True  -> «Boshqa» varianti bor (foydalanuvchi o‘zi yozadi)
"when": (key, value) -> savol faqat shu shart bajarilsa beriladi
"stop": {value: xabar} -> shu variant tanlansa, ro‘yxatdan o‘tish to‘xtatiladi
"full": True -> xulosada javob qisqartirilmaydi
"""

OTHER = "Boshqa"

TEAM = "Jamoa shaklida"

QUESTIONS = [
    {
        "key": "fio", "entry": "208831017", "type": "fio", "required": True,
        "icon": "👤",
        "text": "Familiyangiz, ismingiz, otangizning ismi (F.I.Sh.)",
        "hint": "Masalan: <i>Karimov Jasur Anvar o‘g‘li</i>",
    },
    {
        "key": "birth", "entry": "1981586230", "type": "date", "required": True,
        "icon": "🎂",
        "text": "Tug‘ilgan sanangiz (KK.OO.YYYY, masalan 14.03.2005)",
    },
    {
        "key": "gender", "entry": "1156034120", "type": "choice", "required": True,
        "icon": "🧑",
        "text": "Jinsingiz",
        "options": [("👨", "Erkak"), ("👩", "Ayol")],
    },
    {
        "key": "citizenship", "entry": "1844246420", "type": "choice", "required": True,
        "icon": "🇺🇿",
        "text": "Fuqaroligingiz",
        "options": [
            ("🇺🇿", "O‘zbekiston Respublikasi fuqarosi"),
            ("🌍", "Boshqa davlat fuqarosi"),
        ],
        "stop": {
            "Boshqa davlat fuqarosi":
                "Tanlovda faqat O‘zbekiston Respublikasi fuqarolari ishtirok eta oladi.",
        },
    },
    {
        "key": "residence", "entry": "748676036", "type": "choice", "required": True,
        "icon": "🏠",
        "text": "Xatirchi tumanida ro‘yxatdan o‘tganlik holatingiz",
        "options": [
            ("🏡", "Doimiy ro‘yxatdan o‘tganman"),
            ("🕒", "Vaqtincha ro‘yxatdan o‘tganman"),
            # Formada yo‘q variant: tanlansa ro‘yxatdan o‘tish to‘xtatiladi, Formaga yuborilmaydi
            ("🚫", "Xatirchi tumanida yashamayman"),
        ],
        "stop": {
            "Xatirchi tumanida yashamayman":
                "Tanlovda faqat Xatirchi tumanida doimiy yoki vaqtincha ro‘yxatdan o‘tgan "
                "yoshlar ishtirok eta oladi.",
        },
    },
    {
        "key": "address", "entry": "1190945236", "type": "text", "required": True,
        "icon": "📍",
        "text": "Yashash manzilingiz (MFY, ko‘cha, uy raqami)",
        "hint": "Masalan: <i>Farovon MFY, Mustaqillik ko‘chasi, 12-uy</i>",
    },
    {
        "key": "phone", "entry": "1421806962", "type": "phone", "required": True,
        "icon": "📞",
        "text": "Telefon raqamingiz",
        "hint": "Pastdagi «📱 Raqamni yuborish» tugmasini bosing yoki istalgan "
                "ko‘rinishda yozing: <i>90 123 45 67</i>, <i>+998901234567</i>, "
                "<i>(90) 123-45-67</i>",
    },
    {
        "key": "username", "entry": "649957427", "type": "username", "required": True,
        "icon": "✈️",
        "text": "Telegram foydalanuvchi nomingiz",
        "hint": "Masalan: <i>@username</i>",
    },
    {
        "key": "email", "entry": "631494217", "type": "email", "required": True,
        "icon": "📧",
        "text": "Elektron pochta manzilingiz (e-mail)",
        "hint": "Masalan: <i>ism@gmail.com</i>",
    },
    {
        "key": "activity", "entry": "1392220754", "type": "choice", "required": True,
        "icon": "💼",
        "text": "Faoliyat turingiz",
        "options": [
            ("🏫", "Umumta’lim maktabi o‘quvchisi"),
            ("🛠", "Kollej / texnikum o‘quvchisi"),
            ("🎓", "Oliy ta’lim muassasasi talabasi"),
            ("👔", "Ishlayman"),
            ("🔎", "Vaqtincha ishsizman"),
        ],
        "other": True,
    },
    {
        "key": "workplace", "entry": "381741156", "type": "text", "required": True,
        "icon": "🏢",
        "text": "O‘qish yoki ish joyingiz (ta’lim muassasasi / tashkilot nomi)",
    },
    {
        "key": "participation", "entry": "1143291183", "type": "choice", "required": True,
        "icon": "🤝",
        "text": "Ishtirok shakli",
        "options": [("🙋", "Yakka tartibda"), ("👥", TEAM)],
    },
    {
        "key": "team_name", "entry": "1948699500", "type": "text", "required": True,
        "icon": "🏷",
        "text": "Jamoa nomi",
        "when": ("participation", TEAM),
    },
    {
        "key": "team_members", "entry": "336194601", "type": "members", "required": True,
        "icon": "👥",
        "text": "Jamoa a’zolari haqida ma’lumot (har bir a’zo uchun: F.I.Sh., yoshi, "
                "telefon raqami, jamoadagi vazifasi)",
        "hint": "Masalan:\n<i>1. Karimov Jasur, 20 yosh, +998 90 123 45 67, backend dasturchi\n"
                "2. Aliyeva Dilnoza, 19 yosh, +998 91 765 43 21, dizayner</i>",
        "when": ("participation", TEAM),
        "full": True,  # xulosada qisqartirilmaydi
    },
    {
        "key": "project_name", "entry": "489716322", "type": "text", "required": True,
        "icon": "💡",
        "text": "Loyiha nomi",
    },
    {
        "key": "sphere", "entry": "2056356162", "type": "choice", "required": True,
        "icon": "🎯",
        "text": "Loyiha qaysi sohaga yo‘naltirilgan?",
        "options": [
            ("📨", "Aholi murojaatlari bilan ishlash"),
            ("❤️", "Ijtimoiy soha"),
            ("🚰", "Kommunal soha"),
            ("🏛", "Davlat boshqaruvi"),
            ("⚡️", "Energiya samaradorligi"),
            ("🏭", "Ishlab chiqarish"),
            ("🛎", "Xizmat ko‘rsatish"),
        ],
        "other": True,
    },
    {
        "key": "problem", "entry": "774643636", "type": "longtext", "required": True,
        "icon": "❓",
        "text": "Loyiha qanday muammoni hal qiladi? (muammoning dolzarbligi va ko‘lami)",
    },
    {
        "key": "solution", "entry": "1380766093", "type": "longtext", "required": True,
        "icon": "🧩",
        "text": "Taklif etilayotgan yechim: loyiha qanday ishlaydi va qanday natija beradi?",
    },
    {
        "key": "readiness", "entry": "984380669", "type": "choice", "required": True,
        "icon": "📊",
        "text": "Loyihaning tayyorlik darajasi",
        "options": [
            ("✅", "Ishchi model (MVP prototipi) to‘liq tayyor"),
            ("⚙️", "MVP prototipi ishlab chiqilmoqda (tanlovgacha yakunlanadi)"),
        ],
    },
    {
        "key": "tech", "entry": "1318810278", "type": "text", "required": True,
        "icon": "🧑‍💻",
        "text": "Loyihada qo‘llanilgan texnologiyalar (dasturlash tillari, freymvorklar, "
                "platformalar)",
        "hint": "Masalan: <i>Python, Django, PostgreSQL, Flutter</i>",
    },
    {
        "key": "link", "entry": "672210720", "type": "link_or_file", "required": False,
        "icon": "🔗",
        "text": "Loyiha havolasi yoki fayllari (GitHub, demo-sayt, video, taqdimot)",
        "hint": "🔗 Havola yuboring (<i>https://...</i>) yoki\n"
                "📎 fayl yuklang: PDF, taqdimot, rasm, video, ZIP-arxiv.\n\n"
                "📁 Papka yubormoqchi bo‘lsangiz, uni ZIP-arxivga joylab yuboring.\n"
                "Bir nechta havola va fayl yuborish mumkin (10 tagacha).",
        "full": True,
    },
    {
        "key": "agreement", "entry": "361355329", "type": "confirm", "required": True,
        "icon": "📜",
        "text": "Loyiha talablariga muvofiqligini tasdiqlang",
        "options": [
            "Tasdiqlayman: loyiha yangi, ilgari boshqa tanlovlarda g‘olib bo‘lmagan "
            "va amaliyotga joriy etilmagan",
            "Shaxsiy ma’lumotlarimni tanlov maqsadlarida qayta ishlashga roziman",
        ],
        # Tugmalardagi qisqa yozuvlar (to‘liq matn xabarda ko‘rsatiladi)
        "short": [
            "Loyiha talablarga mos",
            "Shaxsiy ma’lumotlarga roziman",
        ],
    },
    {
        "key": "source", "entry": "231288651", "type": "choice", "required": False,
        "icon": "📣",
        "text": "Tanlov haqida qayerdan xabar topdingiz?",
        "options": [
            ("📢", "«Yangi Xatirchi» Telegram kanali"),
            ("🏙", "«IT-shaharcha» Xatirchi filiali"),
            ("🏛", "Tuman hokimligi rasmiy manbalari"),
            ("📱", "Ijtimoiy tarmoqlar"),
            ("🗣", "Do‘stlar yoki tanishlardan"),
        ],
        "other": True,
    },
]

KEYS = [q["key"] for q in QUESTIONS]


def is_applicable(q, answers):
    """Savol shu foydalanuvchiga beriladimi (shartli savollar uchun)."""
    cond = q.get("when")
    if not cond:
        return True
    key, value = cond
    return answers.get(key) == value
