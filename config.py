"""
تنظیمات قابل تغییر ربات «تریاکی» — فاز ۲
همه‌ی قیمت‌ها / تایمرها / فرمول‌ها / کاتالوگ آیتم‌ها همینجاست
برای اضافه کردن آیتم | سلاح | سگ | بذر جدید فقط یه خط به کاتالوگ مربوطه اضافه کن
"""

import os

BOT_TOKEN = os.getenv("TERIAKY_TOKEN", "")


def _default_db() -> str:
    """
    اولویت با TERIAKY_DB — اگه ست نشده باشه و ولوم ریلوی سوار باشه
    خودش اتوماتیک از ولوم استفاده می‌کنه تا دیتابیس با ری‌دیپلوی نپره
    ولوم هم از متغیر RAILWAY_VOLUME_MOUNT_PATH تشخیص داده میشه هم از مسیر /data
    """
    env = os.getenv("TERIAKY_DB")
    if env:
        return env
    vol = os.getenv("RAILWAY_VOLUME_MOUNT_PATH") or ("/data" if os.path.isdir("/data") else "")
    if vol:
        return f"sqlite+aiosqlite:///{vol.rstrip('/')}/teriaky.db"
    return "sqlite+aiosqlite:///teriaky.db"


DATABASE_URL = _default_db()


def sqlite_path() -> str | None:
    """مسیر فایل SQLite از روی URL — اگه SQLite نباشه None (برای بک‌آپ)"""
    for pre in ("sqlite+aiosqlite:///", "sqlite:///"):
        if DATABASE_URL.startswith(pre):
            return DATABASE_URL[len(pre):]
    return None


def ensure_sqlite_dir() -> None:
    """پوشه فایل SQLite رو اگه نیس بساز (مثلا ولوم ریلوی تازه سوار شده)"""
    path = sqlite_path()
    if not path:
        return
    d = os.path.dirname(os.path.abspath(path))
    try:
        os.makedirs(d, exist_ok=True)
    except OSError as e:
        raise SystemExit(
            f"❌ پوشه دیتابیس ساخته نشد: {d}\n"
            "اگه روی Railway ای چک کن Volume ساخته شده و Mount Path با مسیر TERIAKY_DB یکی باشه\n"
            f"جزئیات: {e}"
        )

# لیست ادمین‌ها — تلگرام آیدی‌ها با کاما: TERIAKY_ADMIN_IDS="111,222"
ADMIN_IDS = {
    int(x) for x in os.getenv("TERIAKY_ADMIN_IDS", "").replace(" ", "").split(",") if x
}

# ───────── شروع بازی ─────────
START_CASH = 500                # تی‌پوینت شروع
MAX_ENERGY = 100
ENERGY_REGEN_MINUTES = 3        # هر چند دقیقه ۱ انرژی برگرده

# ───────── لول و تجربه بازیکن ─────────
# منحنی Idle/RPG: لول‌های پایین سریع | لول‌های بالا سنگین‌تر ولی قابل پیشرفت
# xp لازم برای لول N = XP_CURVE_BASE × N^XP_CURVE_EXP
# نمونه: لول۱→۵۰ | لول۵→۷۲۴ | لول۱۰→۲۵۱۵ | لول۲۰→۷۲۰۰
XP_CURVE_BASE = 50
XP_CURVE_EXP = 1.6
LEVEL_CASH_REWARD = 250         # جایزه نقدی لول‌آپ = این عدد × لول جدید

# ───────── اثر لول روی اقتصاد و تجهیزات ─────────
LEVEL_YIELD_BONUS = 0.02        # هر لول +۲٪ درآمد برداشت
LEVEL_ITEM_BONUS = 0.02         # هر لول +۲٪ قدرت سلاح و زره

# ───────── زمین (Plot) ─────────
# سقف ۵ زمین — اولی رایگانه (موقع ثبت‌نام داده میشه)
# هر زمین بعدی قیمت و زمان ساخت و لول خودشو داره و خیلی گرون‌تره
MAX_PLOTS = 5
PLOT_CATALOG = {
    1: {"price": 0,     "build_sec": 0,          "min_level": 1},   # رایگان شروع
    2: {"price": 1000,  "build_sec": 30,         "min_level": 2},   # 30 ثانیه ساخت
    3: {"price": 10000, "build_sec": 900,        "min_level": 4},   # 15 دقیقه
    4: {"price": 20000, "build_sec": 3600,       "min_level": 6},   # 1 ساعت
    5: {"price": 50000, "build_sec": 43200,      "min_level": 10},  # 12 ساعت
}
PLOT_MAX_LEVEL = 3
UPGRADE_BASE_PRICE = 800
UPGRADE_PRICE_GROWTH = 2.4
PLOT_YIELD_MULT = {1: 1.0, 2: 1.8, 3: 2.8}
PLOT_SPEED_MULT = {1: 1.0, 2: 0.85, 3: 0.70}

# ───────── بذرها (فروشگاه 🌱) ─────────
# price = قیمت بذر | grow_min = دقیقه رشد | sell = فروش | xp = تجربه برداشت | min_level = لول لازم
SEEDS = {
    "teriak":    {"name": "تریاک",      "price": 120,  "grow_min": 5,  "sell": 420,   "xp": 10, "min_level": 1,  "desc": "محصول شروع هر دلال"},
    "marijuana": {"name": "ماری‌جوانا",  "price": 320,  "grow_min": 8,  "sell": 1150,  "xp": 18, "min_level": 3,  "desc": "سبزه و پرطرفدار"},
    "koka":      {"name": "کوکا",        "price": 850,  "grow_min": 12, "sell": 3000,  "xp": 30, "min_level": 5,  "desc": "پودر سفید قیمتی"},
    "ghat":      {"name": "قات",         "price": 2000, "grow_min": 18, "sell": 7500,  "xp": 45, "min_level": 7,  "desc": "برگ تلخ و گرون"},
    "peyote":    {"name": "پیوته",       "price": 5200, "grow_min": 25, "sell": 20000, "xp": 70, "min_level": 10, "desc": "کاکتوس جادویی صحرا"},
}

# ───────── کنده‌کاری ─────────
MINE_COOLDOWN_SECONDS = 30      # هر ۳۰ ثانیه یه بار
MINE_MIN = 10
MINE_MAX = 150
MINE_COMMON_MAX = 100
MINE_COMMON_WEIGHT = 0.75       # ۷۵٪ مواقع بین ۱۰ تا ۱۰۰ میاد
MINE_XP = 3

# ───────── برداشت ─────────
HARVEST_COOLDOWN_SECONDS = 120  # هر ۲ دقیقه فقط یه بار برداشت — زمان‌بندی برای هر کاربر جداست

# ───────── حمله (PvP) ─────────
ATTACK_COOLDOWN_MINUTES = 1     # هر ۱ دقیقه فقط یه حمله
ATTACK_ENERGY_COST = 12
ATTACK_LOSE_ENERGY = 15
ATTACK_TARGET_LEVEL_RANGE = 2   # جستجوی رندوم از منو — حمله ریپلای بدون محدودیت لوله
STEAL_MIN_PCT = 0.10            # حداقل درصد سرقت
STEAL_MAX_PCT = 0.25            # حداکثر درصد سرقت
ATTACK_WIN_XP = 30
ATTACK_LOSE_XP = 8
ATK_BASE = 4
ATK_PER_LEVEL = 2
DEF_BASE = 3
DEF_PER_LEVEL = 2

# ───────── سلاح‌ها (فروشگاه 🔪) ─────────
# چاقو و قمه و میله سردن — بقیه اسلحه‌ن (🔫)
WEAPONS = {
    "knife":   {"name": "چاقو",              "price": 400,   "attack": 6,   "min_level": 1,  "desc": "سلاح کلاسیک محله", "gun": False},
    "shank":   {"name": "قمه",               "price": 850,   "attack": 11,  "min_level": 2,  "desc": "بلند و ترسناک", "gun": False},
    "pipe":    {"name": "میله آهنی",          "price": 1200,  "attack": 14,  "min_level": 3,  "desc": "سنگین و زخمی", "gun": False},
    "colt":    {"name": "کلت کمری 🔫",        "price": 2200,  "attack": 22,  "min_level": 4,  "desc": "اولین اسلحه هر تازه‌کار", "gun": True},
    "shocker": {"name": "شوکر دست‌ساز",        "price": 3500,  "attack": 30,  "min_level": 5,  "desc": "برق می‌گیرهت", "gun": False},
    "uzi":     {"name": "اوزی 🔫",            "price": 5500,  "attack": 42,  "min_level": 6,  "desc": "رگباری و پرسرعت", "gun": True},
    "shotgun": {"name": "شات‌گان 🔫",         "price": 7500,  "attack": 52,  "min_level": 7,  "desc": "از نزدیک ویرانه", "gun": True},
    "deagle":  {"name": "کلت نقره‌ای 🔫",      "price": 10000, "attack": 60,  "min_level": 8,  "desc": "خشن و پرسرعت", "gun": True},
    "ak47":    {"name": "AK-47 🔫",           "price": 16000, "attack": 85,  "min_level": 10, "desc": "کلاش افسانه‌ای محله", "gun": True},
    "svd":     {"name": "دراگونوف 🔫",        "price": 22000, "attack": 105, "min_level": 11, "desc": "تک‌تیرانداز از پشت بوم", "gun": True},
    "plasma":  {"name": "شلیک‌کن پلاسما",     "price": 30000, "attack": 130, "min_level": 12, "desc": "آینده‌گرایانه و کشنده", "gun": True},
    "minigun": {"name": "گاتلینگ 🔫",         "price": 45000, "attack": 175, "min_level": 14, "desc": "رگبار تموم‌نشدنی", "gun": True},
    "rpg":     {"name": "آرپی‌جی 🔫",          "price": 60000, "attack": 230, "min_level": 16, "desc": "باهاش نصف محله دود میشه", "gun": True},
}

# ───────── زره‌ها (فروشگاه 🛡) ─────────
# legendary=True یعنی سکه دزدیده‌شده از صاحبش نصف میشه
ARMORS = {
    "jacket": {"name": "کت چرمی",        "price": 350,   "defense": 4,   "min_level": 1,  "desc": "سبک و شیک"},
    "vest":   {"name": "جلیقه سنگین",    "price": 1500,  "defense": 12,  "min_level": 3,  "desc": "ضربه رو جذب می‌کنه"},
    "kevlar": {"name": "جلیقه کِولار",   "price": 2800,  "defense": 20,  "min_level": 5,  "desc": "استاندارد پلیس‌ها"},
    "steel":  {"name": "زره فولادی",     "price": 4500,  "defense": 28,  "min_level": 6,  "desc": "محکم مثل در بانک"},
    "swat":   {"name": "جلیقه تاکتیکی",  "price": 9000,  "defense": 42,  "min_level": 8,  "desc": "مخصوص یگه‌های ویژه"},
    "nano":   {"name": "زره نانو",       "price": 20000, "defense": 65,  "min_level": 10, "desc": "تکنولوژی فضایی"},
    "titan":  {"name": "زره تیتانیومی",  "price": 40000, "defense": 82,  "min_level": 12, "desc": "سبک ولی شکست‌ناپذیر"},
    "legend": {
        "name": "زره افسانه‌ای 👑", "price": 75000, "defense": 100, "min_level": 14,
        "legendary": True,
        "desc": "این زره افسانه‌ای باعث می‌شود نصف مقدار سکه‌ای که دشمن از شما دریافت می‌کند از بین برود.",
    },
}

# ───────── سگ‌ها (فروشگاه 🐕) ─────────
MAX_DOGS = 4                    # حداکثر سگ برای هر بازیکن
DOG_MAX_LEVEL = 10
DOG_FEED_PER_DAY = 5            # هر بازیکن روزی فقط ۵ بار غذا میده
DOG_XP_BASE = 40                # xp لازم سگ برای لول N = DOG_XP_BASE × N^DOG_XP_EXP
DOG_XP_EXP = 1.35
RARE_DOG_STEAL_MAX = 0.15       # حداکثر بونس سرقت سگ کمیاب (۱۵٪ با لول مکس)
# قدرت سگ = attack + atk_per_level × (لول-۱)
DOGS = {
    "pitbull": {
        "name": "پیتبول رکس", "breed": "پیتبول", "price": 2000, "attack": 8, "atk_per_level": 2,
        "min_level": 1, "rare": False, "ability": "وفادار و همیشه آماده‌ی دعوا",
        "desc": "سگ اول هر گانگستر",
    },
    "doberman": {
        "name": "دوبرمن اصغر", "breed": "دوبرمن", "price": 6000, "attack": 15, "atk_per_level": 3,
        "min_level": 3, "rare": False, "ability": "تند و تیز — سرعت حمله بالا",
        "desc": "بادیگارد قدیمی محله",
    },
    "shepherd": {
        "name": "ژرمن شپرد راکی", "breed": "ژرمن شپرد", "price": 15000, "attack": 26, "atk_per_level": 4,
        "min_level": 6, "rare": False, "ability": "بویایی قوی — قربانی رو بو می‌کشه",
        "desc": "چیزی ازش پنهون نمیمونه",
    },
    "kangal": {
        "name": "کانگال رستم", "breed": "کانگال", "price": 40000, "attack": 45, "atk_per_level": 6,
        "min_level": 10, "rare": False, "ability": "فک افسانه‌ای که ول نمی‌کنه",
        "desc": "هیولاي آسیايی",
    },
    "blackwolf": {
        "name": "گرگ سیاه شبح", "breed": "گرگ سیاه", "price": 150000, "attack": 70, "atk_per_level": 9,
        "min_level": 15, "rare": True,
        "ability": "بسته به لولش تا 15٪ سکه دزدیده‌شده از حریف رو زیاد می‌کنه 👑",
        "desc": "کمیاب‌ترین و بهترین سگ بازی",
    },
}

# ───────── غذای سگ ─────────
DOG_FOODS = {
    "bone": {"name": "استخون",      "price": 200,  "xp": 15, "desc": "میان‌وعده ساده"},
    "meat": {"name": "گوشت تازه",   "price": 450,  "xp": 35, "desc": "پروتئین خالص"},
    "gold": {"name": "غذای طلایی",  "price": 1000, "xp": 80, "desc": "رژیم قهرمانا"},
}

# ───────── تیم 🏴 ─────────
TEAM_CREATE_MIN_LEVEL = 10      # ساخت تیم از لول ۱۰
TEAM_JOIN_MIN_LEVEL = 5         # عضو شدن تو تیم از لول ۵
TEAM_CREATE_COST = 5000         # هزینه ساخت تیم
TEAM_MAX_MEMBERS = 20
TEAM_NAME_MAX = 24
TEAM_BIO_MAX = 120

# کوئست‌های روزانه تیم — پیشرفتش جمع همه اعضاست و جایزه به همه میرسه
TEAM_QUESTS = [
    {"key": "kills",    "emoji": "⚔️", "title": "کشتن 25 نفر",    "target": 25, "reward": 300, "desc": "برد هر عضو تو دعوا حساب میشه"},
    {"key": "harvest",  "emoji": "🌾", "title": "برداشت 10 محصول", "target": 10, "reward": 200, "desc": "برداشت هر عضو حساب میشه"},
]

# کنده‌کاری تیمی — با پیوستن ۷۰٪ اعضا پول میره تو خزانه تیم
TEAM_MINE_JOIN_PCT = 0.70
TEAM_MINE_WINDOW_SECONDS = 300  # ۵ دقیقه فرصت برای جمع شدن
TEAM_MINE_COOLDOWN_MINUTES = 60
TEAM_MINE_PER_MIN = 150         # سهم هر پیوسته (حداقل)
TEAM_MINE_PER_MAX = 400         # سهم هر پیوسته (حداکثر)

# ───────── رتبه‌بندی ─────────
RANK_LIMIT = 10
