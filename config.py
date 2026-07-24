"""
تنظیمات قابل تغییر ربات «تریاکی»، فاز ۲
همه‌ی قیمت‌ها / تایمرها / فرمول‌ها / کاتالوگ آیتم‌ها همینجاست
برای اضافه کردن آیتم | سلاح | سگ | بذر جدید فقط یه خط به کاتالوگ مربوطه اضافه کن
"""

import os

BOT_TOKEN = os.getenv("TERIAKY_TOKEN", "")


def _default_db() -> str:
    """
    اولویت با TERIAKY_DB، اگه ست نشده باشه و ولوم ریلوی سوار باشه
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
    """مسیر فایل SQLite از روی URL، اگه SQLite نباشه None (برای بک‌آپ)"""
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

# لیست ادمین‌ها، تلگرام آیدی‌ها با کاما: TERIAKY_ADMIN_IDS="111,222"
ADMIN_IDS = {
    int(x) for x in os.getenv("TERIAKY_ADMIN_IDS", "").replace(" ", "").split(",") if x
}

# ───────── شروع بازی ─────────
START_CASH = 500                # تی‌پوینت شروع
MAX_ENERGY = 100
# ریجن انرژی دسته‌جمعی: هر ۵ دقیقه ۲۰ انرژی به همه کاربرا میرسه (یه کوئری، بدون حلقه تک‌تک)
ENERGY_PULSE_SECONDS = 300      # فاصله نبض انرژی
ENERGY_PULSE_AMOUNT = 20        # مقدار هر نبض

# ───────── لول و تجربه بازیکن ─────────
# منحنی Idle/RPG: لول‌های پایین سریع | لول‌های بالا سنگین‌تر ولی قابل پیشرفت
# xp لازم برای لول N = XP_CURVE_BASE × N^XP_CURVE_EXP
# نمونه: لول۱→۵۰ | لول۵→۷۲۴ | لول۱۰→۲۵۱۵ | لول۲۰→۷۲۰۰
XP_CURVE_BASE = 50
XP_CURVE_EXP = 1.6
LEVEL_CASH_REWARD = 400         # جایزه نقدی لول‌آپ = این عدد × لول جدید

# ───────── اثر لول روی اقتصاد و تجهیزات ─────────
LEVEL_YIELD_BONUS = 0.02        # هر لول +۲% درآمد برداشت
LEVEL_ITEM_BONUS = 0.02         # هر لول +۲% قدرت سلاح و زره

# ───────── زمین (Plot) ─────────
# سقف ۵ زمین، اولی رایگانه (موقع ثبت‌نام داده میشه)
# هر زمین بعدی قیمت و زمان ساخت و لول خودشو داره و خیلی گرون‌تره
MAX_PLOTS = 5
# گیت لول خرید زمین: زمین دوم لول ۵، بعدی ۱۰، بعدی ۱۵ و آخری ۲۰ باز میشه
PLOT_CATALOG = {
    1: {"price": 0,     "build_sec": 0,          "min_level": 1},   # رایگان شروع
    2: {"price": 1000,  "build_sec": 30,         "min_level": 5},   # 30 ثانیه ساخت
    3: {"price": 10000, "build_sec": 900,        "min_level": 10},  # 15 دقیقه
    4: {"price": 20000, "build_sec": 3600,       "min_level": 15},  # 1 ساعت
    5: {"price": 50000, "build_sec": 43200,      "min_level": 20},  # 12 ساعت
}
# ───────── لول‌آپ زمین ─────────
# هر لول آپ: ۲۵% درآمد بیشتر + ۴۰% سرعت رشد بیشتر، تا لول ۶ قابل آپگریده
PLOT_MAX_LEVEL = 6
PLOT_YIELD_PER_LEVEL = 1.25     # ×۱٫۲۵ درآمد به ازای هر لول
PLOT_SPEED_PER_LEVEL = 1.40     # زمان رشد ÷۱٫۴۰ به ازای هر لول
# هزینه لول‌آپ زمین از لول n به n+1 (اندیس 0 = از لول ۱ به ۲)، آخری آپگرید به لول مکس
PLOT_UPGRADE_PRICES = [5000, 10000, 30000, 100000, 200000]
# لول کاربر که هر آپگرید رو باز می‌کنه (اندیس 0 = آپگرید ۱ به ۲ تو لول ۳ باز میشه)
PLOT_UPGRADE_LEVELS = [3, 5, 10, 15, 20]

# ───────── بذرها (فروشگاه 🌱) ─────────
# ترتیب پیشرفت: ماری‌جوانا → قارچ → پیوت → تریاک → کوکائین
# price = قیمت بذر | grow_min = دقیقه رشد | sell = فروش | xp = تجربه برداشت | min_level = لول لازم
SEEDS = {
    "marijuana": {"name": "ماری‌جوانا",  "emoji": "🌿", "price": 120,  "grow_min": 5,  "sell": 420,   "xp": 10, "min_level": 1,  "desc": "محصول شروع هر دلال"},
    "gharch":    {"name": "قارچ",         "emoji": "🍄", "price": 320,  "grow_min": 8,  "sell": 1150,  "xp": 18, "min_level": 3,  "desc": "کپک سحرآمیز و پرطرفدار"},
    "peyote":    {"name": "پیوت",         "emoji": "🌵", "price": 850,  "grow_min": 12, "sell": 3000,  "xp": 30, "min_level": 5,  "desc": "کاکتوس جادویی صحرا"},
    "teriak":    {"name": "تریاک",        "emoji": "🌱", "price": 2000, "grow_min": 18, "sell": 7500,  "xp": 45, "min_level": 7,  "desc": "طلای سیاه محله"},
    "cocaine":   {"name": "کوکائین",      "emoji": "⚪", "price": 5200, "grow_min": 25, "sell": 20000, "xp": 70, "min_level": 10, "desc": "پودر سفید قیمتی"},
    # ── بذرهای افسانه‌ای، قابل خرید نیستن (فقط جستجو/کاروان/ایونت) و تو بازار سیاه دیده نمیشن ──
    "jahannam": {
        "name": "بذر جهنم 🔥", "price": 0, "grow_min": 60, "sell": 120000, "xp": 150,
        "min_level": 12, "legendary": True, "desc": "از عمق جهنم رسیده",
    },
    "eblis": {
        "name": "بذر ابلیس 😈", "price": 0, "grow_min": 120, "sell": 400000, "xp": 300,
        "min_level": 18, "legendary": True, "desc": "نایاب‌ترین بذر محله",
    },
}

# ───────── کنده‌کاری ─────────
MINE_COOLDOWN_SECONDS = 30      # هر ۳۰ ثانیه یه بار
MINE_MIN = 10
MINE_MAX = 150
MINE_COMMON_MAX = 100
MINE_COMMON_WEIGHT = 0.75       # ۷۵% مواقع بین ۱۰ تا ۱۰۰ میاد
MINE_XP_MIN = 1                 # تجربه هر کنده‌کاری رندوم بین ۱ تا ۵
MINE_XP_MAX = 5

# ───────── برداشت ─────────
HARVEST_COOLDOWN_SECONDS = 120  # هر ۲ دقیقه فقط یه بار برداشت، زمان‌بندی برای هر کاربر جداست

# ───────── نبرد HP گروهی ⚔️ ─────────
# نبرد فقط تو گروه با ریپلای یا آیدی انجام میشه
# HP دائمیه و تو دیتابیس میمونه، تجربه و غارت همون لحظه هر ضربه پرداخت میشه
MAX_LEVEL = 20                # بعد از این لول کاراکتر مکسه و فقط تجربه‌اش جمع میشه
# جدول HP هر لول (۲۰ تا)، لول ۱ شروع با ۲۰۰ و هر لول ۲۰ تا بیشتر
HP_TABLE = [200, 220, 240, 260, 280, 300, 320, 340, 360, 380,
            400, 420, 440, 460, 480, 500, 520, 540, 560, 580]
BATTLE_COOLDOWN_SECONDS = 30  # بعد هر حمله فقط مهاجم اینقدر کولدان می‌گیره
ATTACK_ENERGY_COST = 12       # هزینه انرژی هر ضربه
# فرمول دمیج: (پایه + حمله×ضریب) × (۱ - دفاع/(دفاع + K))
# نمونه حمله ۱۵۰ دفاع ۱۳۰ ≈ ۲۶ دمیج | حمله ۸۸۰ دفاع ۲۳۵ ≈ ۹۳ دمیج
BATTLE_DMG_BASE = 10
BATTLE_DMG_ATK_FACTOR = 0.30
BATTLE_MITIGATION_K = 120     # هرچی بزرگ‌تر، اثر دفاع کمتر
BATTLE_DMG_VARIANCE = 0.30    # دمیج نهایی تا ۳۰% بیشتر یا کمتر رندوم میشه
BATTLE_MIN_DAMAGE = 6         # دمیج خام کمتر از این یعنی هیچ آسیبی نمی‌رسه
BATTLE_NO_DAMAGE_DEF_RATIO = 1.8  # دفاع ≥ این مقدار برابر حمله یعنی حریف زیادی قویه
# غارت هر ضربه: درصد از جیب حریف = سقف × (دمیج ÷ HP کامل حریف)، بعد مادیفایرها و سقف سخت
BATTLE_STEAL_MAX_PCT = 0.05   # هر ضربه حداکثر ۵% دارایی حریف
BATTLE_HIT_XP_BASE = 3        # تجربه هر ضربه = پایه + دمیج × ضریب
BATTLE_HIT_XP_PER_DMG = 0.07
BATTLE_DEAD_SECONDS = 600     # بعد شکست ۱۰ دقیقه بیهوشه، بعد خودکار با HP فول زنده میشه
# ضربه کریتیکال، فقط وقتی ضربه اصلا دمیج داره رول میشه و دمیج نهایی چند برابر میشه
BATTLE_CRIT_CHANCE = 0.02     # شانس ۲ درصدی کریتیکال
BATTLE_CRIT_MULT = 2.0        # دمیج نهایی ×۲

# ───────── حمله پی‌وی کلاسیک ⚔️ ─────────
# سیستم قدیمی بدون HP: قدرت حمله مهاجم با دفاع حریف مقایسه میشه و شانس برد درصدی درمیاد
# بعد هر حمله قربانی ۱۲ ساعت مصونیت می‌گیره و از لیست حمله‌های پی‌وی خارج میشه
PV_ATTACK_ENERGY_COST = 15        # هزینه انرژی هر حمله پی‌وی
PV_ATTACK_LEVEL_RANGE = 2         # هدف فقط بین ۲ لول بالاتر تا ۲ لول پایین‌تر
PV_ATTACK_MIN_CHANCE = 0.15       # کف شانس برد
PV_ATTACK_MAX_CHANCE = 0.85       # سقف شانس برد
PV_ATTACK_CHANCE_SCALE = 0.02     # هر واحد اختلاف (حمله − دفاع) شانس رو اینقدر جابه‌جا می‌کنه
PV_BASE_CHANCE = 0.50             # شانس پایه وقتی قدرت‌ها برابرن
PV_ATTACK_SHIELD_SECONDS = 43200  # مصونیت قربانی بعد حمله، ۱۲ ساعت
PV_ATTACK_STEAL_MIN_PCT = 0.08    # غارت برد = رندوم بین این دو درصد از جیب قربانی
PV_ATTACK_STEAL_MAX_PCT = 0.20
PV_ATTACK_LOSE_PENALTY_PCT = 0.05  # جریمه باخت، این درصد از جیب مهاجم به قربانی میرسه
PV_ATTACK_WIN_XP = 25             # تجربه برد
PV_ATTACK_LOSE_XP = 6             # تجربه باخت
PV_ATTACK_VICTIM_XP = 3           # تجربه کمی که قربانی تو پی‌ویش می‌گیره (حمله نکرده، فقط خورده)
PV_ATTACK_COOLDOWN_SECONDS = 60   # کولدون هر حمله پی‌وی
PV_REROLL_MIN_COST = 25           # هزینه «هدف دیگه» تو لول ۱
PV_REROLL_MAX_COST = 1000         # هزینه «هدف دیگه» تو مکس لول، بین اینا خطی با لول جست‌وجوگر
PV_ATTACK_SHIELD_BREAK_COST = 1500  # هزینه شکستن سپر ۱۲ ساعته قربانی (اختیاری مهاجمه)

# قدرت پایه نبرد (حمله و دفاع) که با لول رشد می‌کنه
ATK_BASE = 4
ATK_PER_LEVEL = 2
DEF_BASE = 3
DEF_PER_LEVEL = 2

# ───────── درمان ❤️ ─────────
# مثل غذای سگ: کلیک یعنی خرید و استفاده همون لحظه، تو انبار ذخیره نمیشه
# heal = مقدار HP برگردونده‌شده | None یعنی فول
HEAL_ITEMS = {
    "band": {"name": "🩹 باند کوچک",          "heal": 75,   "price": 400,  "desc": "بخشی از HP رو برمی‌گردونه"},
    "kit":  {"name": "💉 کیت درمان",           "heal": 150,  "price": 900,  "desc": "مقدار بیشتری HP برمی‌گردونه"},
    "box":  {"name": "🏥 جعبه کمک‌های اولیه",   "heal": None, "price": 1800, "desc": "HP رو کامل می‌کنه"},
}

# ───────── سلاح‌ها (فروشگاه 🔪) ─────────
# چاقو و قمه و میله سردن، بقیه اسلحه‌ن (🔫)
WEAPONS = {
    "knife":   {"name": "چاقو",              "price": 400,   "attack": 6,   "min_level": 1,  "desc": "سلاح کلاسیک محله", "gun": False},
    "shank":   {"name": "قمه",               "price": 850,   "attack": 11,  "min_level": 2,  "desc": "بلند و ترسناک", "gun": False},
    "pipe":    {"name": "میله آهنی",          "price": 1200,  "attack": 14,  "min_level": 3,  "desc": "سنگین و زخمی", "gun": False},
    "shocker": {"name": "شوکر دست‌ساز",        "price": 1800,  "attack": 18,  "min_level": 4,  "desc": "برق می‌گیرهت ولی اسلحه نیس", "gun": False},
    "colt":    {"name": "کلت کمری 🔫",        "price": 2600,  "attack": 24,  "min_level": 5,  "desc": "اولین اسلحه هر تازه‌کار", "gun": True},
    "uzi":     {"name": "اوزی 🔫",            "price": 5500,  "attack": 42,  "min_level": 6,  "desc": "رگباری و پرسرعت", "gun": True},
    "shotgun": {"name": "شات‌گان 🔫",         "price": 7500,  "attack": 52,  "min_level": 7,  "desc": "از نزدیک ویرانه", "gun": True},
    "deagle":  {"name": "کلت نقره‌ای 🔫",      "price": 10000, "attack": 60,  "min_level": 8,  "desc": "خشن و پرسرعت", "gun": True},
    "ak47":    {"name": "کلاشنیکف 🔫",           "price": 16000, "attack": 85,  "min_level": 10, "desc": "کلاش افسانه‌ای محله", "gun": True},
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
        "desc": "این زره افسانه‌ای باعث می‌شود نصف مقدار سکه‌ای که دشمن از شما دریافت می‌کند از بین برود",
    },
}

# ───────── سگ‌ها (فروشگاه 🐕) ─────────
MAX_DOGS = 2                    # حداکثر سگ برای هر بازیکن
DOG_MAX_LEVEL = 10
DOG_FEED_PER_DAY = 5            # هر بازیکن روزی فقط ۵ بار غذا میده
DOG_XP_BASE = 40                # xp لازم سگ برای لول N = DOG_XP_BASE × N^DOG_XP_EXP
DOG_XP_EXP = 1.35
RARE_DOG_STEAL_MAX = 0.10       # حداکثر غرامت بیشتر گرگ سیاه (۱۰% با لول مکس)
RARE_DOG_DEF_CUT_MAX = 0.30     # حداکثر کاهش دفاع حریف توسط گرگ سیاه (۳۰% با لول مکس)
# قدرت سگ = attack + atk_per_level × (لول-۱) | اسم آیتم فقط نژاده، اسمشو خودت بعد خرید می‌ذاری
DOGS = {
    "pitbull": {
        "name": "پیتبول", "breed": "پیتبول", "price": 2000, "attack": 8, "atk_per_level": 2,
        "min_level": 1, "rare": False, "ability": "وفادار و همیشه آماده‌ی دعوا",
        "desc": "سگ اول هر گانگستر",
    },
    "doberman": {
        "name": "دوبرمن", "breed": "دوبرمن", "price": 6000, "attack": 15, "atk_per_level": 3,
        "min_level": 3, "rare": False, "ability": "تند و تیز، سرعت حمله بالا",
        "desc": "بادیگارد قدیمی محله",
    },
    "shepherd": {
        "name": "ژرمن شپرد", "breed": "ژرمن شپرد", "price": 15000, "attack": 26, "atk_per_level": 4,
        "min_level": 6, "rare": False, "ability": "بویایی قوی، قربانی رو بو می‌کشه",
        "desc": "چیزی ازش پنهون نمیمونه",
    },
    "kangal": {
        "name": "کانگال", "breed": "کانگال", "price": 40000, "attack": 45, "atk_per_level": 6,
        "min_level": 10, "rare": False, "ability": "فک افسانه‌ای که ول نمی‌کنه",
        "desc": "هیولاي آسیايی",
    },
    "blackwolf": {
        "name": "گرگ سیاه", "breed": "گرگ سیاه", "price": 150000, "attack": 70, "atk_per_level": 9,
        "min_level": 15, "rare": True,
        "ability": "با لول‌آپ تا 30% دفاع حریف رو خرد می‌کنه و تا 10% غرامت بیشتری از حریف می‌گیره 👑",
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
TEAM_MAX_MEMBERS = 10
TEAM_NAME_MAX = 24
TEAM_BIO_MAX = 120

# کوئست‌های روزانه تیم، پیشرفتش جمع همه اعضاست و جایزه به همه میرسه
# reward = جایزه نقدی هر عضو | bank_reward = جایزه به بانک تیم
TEAM_QUESTS = [
    {"key": "kills",    "emoji": "⚔️", "title": "کشتن 25 نفر",    "target": 25, "reward": 200, "bank_reward": 2000, "desc": "برد هر عضو تو دعوا حساب میشه"},
    {"key": "harvest",  "emoji": "🌾", "title": "برداشت 10 محصول", "target": 10, "reward": 100, "bank_reward": 1000, "desc": "برداشت هر عضو حساب میشه"},
]

# کنده‌کاری تیمی، با پیوستن ۷۰% اعضا پول میره تو خزانه تیم
TEAM_MINE_JOIN_PCT = 0.70
TEAM_MINE_WINDOW_SECONDS = 300  # ۵ دقیقه فرصت برای جمع شدن
TEAM_MINE_COOLDOWN_MINUTES = 60
TEAM_MINE_PER_MIN = 150         # سهم هر پیوسته (حداقل)
TEAM_MINE_PER_MAX = 400         # سهم هر پیوسته (حداکثر)

# ───────── بانک شخصی 🏦 ─────────
# پول بانک موقع حمله دزدیده نمیشه، ظرفیت با لول بانک رشد می‌کنه
# لول بانک نمی‌تونه از لول خود بازیکن جلوتر بره
BANK_MAX_LEVEL = 10
BANK_CAP_BASE = 25000         # ظرفیت بانک = این عدد × لول بانک
# هزینه ارتقای بانک از لول n به n+1 (اندیس 0 = از لول ۱ به ۲)
BANK_UPGRADE_PRICES = [4000, 9000, 18000, 32000, 55000, 85000, 130000, 190000, 260000]

# ───────── امتیاز و رقابت هفتگی تیم 🏆 ─────────
# امتیاز تیم با برد تو حمله و برداشت محصول جمع میشه، آخر هفته ۳ تیم اول جایزه می‌گیرن
TEAM_POINT_KILL = 10          # امتیاز هر برد تو حمله
TEAM_POINT_HARVEST = 2        # امتیاز هر محصول برداشت‌شده
TEAM_WEEKLY_PRIZES = {1: 50000, 2: 30000, 3: 15000}   # جایزه هفتگی، میره تو بانک تیم

# ───────── ساختمان‌های تیم 🏗 ─────────
# رهبر با پول بانک تیم آپگریدشون می‌کنه و بونسش به همه اعضا میرسه
TEAM_BUILDING_MAX_LEVEL = 10
# هزینه ارتقای ساختمان به لول ۱..۱۰، گرونه چون همه تیم باهم جمعش می‌کنن، اعداد رند
TEAM_BUILDING_PRICES = [25000, 45000, 75000, 120000, 180000, 260000, 360000, 480000, 620000, 800000]
TEAM_ATK_BONUS_PER_LEVEL = 0.03   # هر لول ساختمان حمله: +۳% قدرت حمله همه اعضا
TEAM_DEF_BONUS_PER_LEVEL = 0.03   # هر لول ساختمان دفاع: +۳% دفاع همه اعضا

# ───────── شخصیت سگ‌ها 🧬 ─────────
# گرگ سیاه 👑 شخصیت نمی‌گیره، قابلیت‌های خودشو داره و ثابت می‌مونه
DOG_PERSONALITIES = {
    "loyal":   {"emoji": "🦴", "name": "وفادار",   "desc": "+5% قدرت سگ",           "atk_mult": 0.05},
    "warrior": {"emoji": "⚔", "name": "جنگجو",   "desc": "+10% قدرت سگ",          "atk_mult": 0.10},
    "guard":   {"emoji": "🛡", "name": "نگهبان",  "desc": "دزدی از جیبت 10% کمتر",     "def_steal_cut": 0.10},
    "hunter":  {"emoji": "💰", "name": "شکارچی",  "desc": "+8% غرامت جنگی",        "steal_bonus": 0.08},
    "lucky":   {"emoji": "🍀", "name": "خوش‌شانس", "desc": "شانس جایزه‌های جستجو بیشتر", "luck": 1.5},
}

# ───────── کیفیت محصول ⭐ ─────────
# هر برداشت یه کیفیت داره و کیفیت بالاتر قیمت فروش رو می‌بره بالا
QUALITY_TIERS = [
    {"key": "normal", "stars": 1, "label": "معمولی",   "chance": 0.45, "mult": 1.00},
    {"key": "good",   "stars": 2, "label": "خوب",      "chance": 0.30, "mult": 1.25},
    {"key": "great",  "stars": 3, "label": "عالی",     "chance": 0.17, "mult": 1.60},
    {"key": "rare",   "stars": 4, "label": "کمیاب",    "chance": 0.07, "mult": 2.00},
    {"key": "epic",   "stars": 5, "label": "افسانه‌ای", "chance": 0.01, "mult": 3.00},
]

# ───────── جستجو 🔍 ─────────
SEARCH_COOLDOWN_MINUTES = 10      # هر ۱۰ دقیقه یه جستجو
# هر نتیجه شانس خودشو داره، جمع شانس‌ها باید ۱ باشه
SEARCH_OUTCOMES = [
    {"key": "money",       "chance": 0.28, "emoji": "💰", "text": "مقداری پول پیدا کردی",        "min": 100, "max": 700},
    {"key": "seed_common", "chance": 0.25, "emoji": "🌱", "text": "بذر معمولی پیدا کردی",        "pool": ["marijuana", "gharch"]},
    {"key": "seed_rare",   "chance": 0.20, "emoji": "🌿", "text": "بذر کمیاب پیدا کردی",         "pool": ["peyote", "teriak", "cocaine"]},
    {"key": "seed_hell",   "chance": 0.07, "emoji": "🔥", "text": "بذر جهنم پیدا کردی",          "pool": ["jahannam"]},
    {"key": "seed_devil",  "chance": 0.05, "emoji": "😈", "text": "بذر ابلیس پیدا کردی",         "pool": ["eblis"]},
    {"key": "thief",       "chance": 0.15, "emoji": "☠️", "text": "دزد مقداری پولت را دزدید",   "pct_min": 0.05, "pct_max": 0.12},
]

# ───────── آب و هوا 🌦 ─────────
WEATHER_ROLL_SECONDS = 7200       # هر ۲ ساعت عوض میشه
WEATHER_NORMAL_CHANCE = 0.60      # ۶۰% عادی | ۴۰% یکی از ویژه‌ها
WEATHER_GROUP_ACTIVE_HOURS = 1    # اعلان فقط به گروه‌های فعال ۱ ساعت اخیر
# speed = ضریب سرعت رشد | def_mod/atk_mod = اصلاح نبرد | sell_mod = اصلاح قیمت فروش | q5 = شانس اضافه محصول ۵ ستاره
# announce = متن کامل اعلان گروهی | effects = خط کوتاه افکت توی صفحه «وضعیت آب و هوا»
WEATHERS = {
    "normal": {"emoji": "🌤", "name": "هوای عادی", "announce": [], "effects": []},
    "rain": {
        "emoji": "🌧", "name": "باران", "speed": 1.30,
        "announce": ["سرعت رشد گیاه ها 30% افزایش پیدا کرد"],
        "effects": ["سرعت رشد مثبت 30%"],
    },
    "heat": {
        "emoji": "☀️", "name": "گرمای شدید", "speed": 0.80,
        "announce": ["سرعت رشد گیاه ها 20% کاهش پیدا کرد"],
        "effects": ["سرعت رشد منفی 20%"],
    },
    "fog": {
        "emoji": "🌫", "name": "مه", "def_mod": 0.20,
        "announce": ["دفاع همه بازیکن ها 20% افزایش پیدا کرد"],
        "effects": ["دفاع مثبت 20%"],
    },
    "storm": {
        "emoji": "🌪", "name": "طوفان", "atk_mod": -0.10,
        "announce": ["قدرت حمله همه 10% کاهش پیدا کرد"],
        "effects": ["حمله منفی 10%"],
    },
    "fest": {
        "emoji": "🌈", "name": "جشن برداشت", "sell_mod": 0.50,
        "announce": ["قیمت فروش محصولات 50% افزایش پیدا کرد"],
        "effects": ["قیمت فروش مثبت 50%"],
    },
    "moon": {
        "emoji": "🌕", "name": "شب مهتابی", "q5": 0.10,
        "announce": ["شانس محصول ⭐⭐⭐⭐⭐ به مقدار 10% افزایش پیدا کرد"],
        "effects": ["شانس ⭐⭐⭐⭐⭐ مثبت 10%"],
    },
    "frost": {
        "emoji": "❄️", "name": "سرمای شدید", "speed": 1 / 1.15,
        "announce": ["زمان رشد گیاه ها 15% بیشتر شد"],
        "effects": ["زمان رشد بیشتر 15%"],
    },
}

# ───────── بازار سیاه 📈 ─────────
MARKET_ROLL_SECONDS = 4 * 3600     # هر ۴ ساعت قیمت‌ها عوض میشن
MARKET_MIN_PCT = -30               # کف درصد تغییر (حداکثر 30% ضرر)
MARKET_MAX_PCT = 50                # سقف درصد تغییر (حداکثر 50% سود)
MARKET_COMMON_WEIGHT = 0.75        # اغلب‌ها تو بازه کم‌نوسانن (75% مواقع)
MARKET_UP_COMMON = 20              # اغلب‌ها: سود 0 تا 20% | گاهی تا سقف 50%
MARKET_DOWN_COMMON = 10            # اغلب‌ها: ضرر 0 تا 10% | گاهی تا کف 30%
# جهت سود/ضرر 50/50، نیمی مثبت نیمی منفی

# ───────── قمارخانه 🎰 ─────────
CASINO_MIN_LEVEL = 7
CASINO_COOLDOWN_HOURS = 12         # هر ۱۲ ساعت یه دست
CASINO_WIN_CHANCE = 0.40           # ۴۰% برد، ۶۰% باخت
CASINO_WIN_MULT = 1.8              # برد: ۱٫۸ برابر شرط (تو بلندمدت سودده نیس)
CASINO_BETS = [1000, 5000, 25000]  # میزهای شرط

# ───────── پناهگاه 🏚 ─────────
SHELTER_MAX_LEVEL = 10
# هزینه ارتقا به لول ۱..۱۰، اعداد رند
SHELTER_PRICES = [3000, 7500, 16000, 30000, 52000, 85000, 130000, 190000, 265000, 360000]
SHELTER_RAID_CUT_PER_LEVEL = 0.05  # هر لول ۵% از خسارت یورش کم می‌کنه
SHELTER_DODGE_PER_LEVEL = 0.04     # هر لول ۴% شانس فرار کامل از یورش
SHELTER_SEED_CAP_BASE = 15         # ظرفیت انبار هر بذر بدون پناهگاه
SHELTER_SEED_CAP_PER_LEVEL = 10    # هر لول پناهگاه +۱۰ ظرفیت هر بذر

# ───────── یورش پلیس 🚔 ─────────
POLICE_ROLL_SECONDS = 7200         # هر ۲ ساعت یه موج احتمالی
POLICE_RAID_CHANCE = 0.08          # شانس یورش برای هر نفر فعال (هر موج)
POLICE_ACTIVITY_HOURS = 24         # هدف: کسایی که ۲۴ ساعت اخیر فعال بودن
POLICE_DESTROY_PCT = 0.30          # ۳۰% محصولات انبار نابود میشه

# ───────── کاروان 🚛 ─────────
CARAVAN_TICK_SECONDS = 60          # هر دقیقه چک اسپون/انقضا
CARAVAN_BOARD_REFRESH_SECONDS = 120  # برد کاروان با این تایمر ادیت میشه نه بعد هر ضربه
CARAVAN_TOP_REWARDS = 5            # فقط ۵ نفر برتر دمیج جایزه نهایی می‌گیرن
CARAVAN_DMG_VARIANCE = 0.20        # دمیج کاروان تا اینقدر بیشتر یا کمتر از قدرت حمله می‌چرخه
CARAVAN_SPAWN_CHANCE = 0.35        # شانس اسپون برای هر گروه فعال در هر ساعت
CARAVAN_GROUP_COOLDOWN_HOURS = 3   # فاصله بین دو کاروان تو یه گروه
CARAVAN_GROUP_ACTIVE_HOURS = 24    # فقط گروه‌های فعال ۱ روز اخیر
CARAVAN_HP_TIERS = [500, 1000, 2000, 5000]
CARAVAN_LIFETIME_MINUTES = 10      # اگه نمرد می‌ره
CARAVAN_HIT_COOLDOWN_SECONDS = 60  # هر بازیکن هر ۱ دقیقه یه ضربه
CARAVAN_MONEY_PER_DMG = 2          # جایزه هر ضربه = دمیج × این
CARAVAN_HIT_XP = 5                 # XP هر ضربه
# جایزه نهایی کشته شدن، بذر بر اساس سهم دمیج + جایزه مخصوص نفر اول
CARAVAN_LOOT = [
    {"key": "common", "chance": 0.60, "pool": ["marijuana", "gharch"]},
    {"key": "rare",   "chance": 0.30, "pool": ["peyote", "teriak", "cocaine"]},
    {"key": "hell",   "chance": 0.07, "pool": ["jahannam"]},
    {"key": "devil",  "chance": 0.03, "pool": ["eblis"]},
]

# ───────── عضویت اجباری 🔒 ─────────
# کانال از پنل ادمین ست میشه و توی game_meta ذخیره می‌مونه (با ری‌استارت حفظه)
FORCE_JOIN_STALE_SECONDS = 120   # پیام گیت برای هر نفر پشت سر هم اسپم نمیشه

# ───────── رتبه‌بندی ─────────
RANK_LIMIT = 10

# ───────── کوئست‌های روزانه 📅 ─────────
# هر روز برای هر بازیکن ۲ تا ۳ ماموریت رندوم از این لیست ورداشته میشه
# هر شب ساعت ۱۲ (به‌وقت ایران) ریست میشن، جایزه بر اساس سختی: تی‌پوینت | تجربه | بذر
# title با {n} پر میشه | target = هدف | tp/xp = مبنای جایزه نقدی یا تجربه
DAILY_QUESTS = {
    "attack":  {"emoji": "⚔️", "title": "انجام {n} حمله",        "target": 5,  "tp": 900, "xp": 60},
    "harvest": {"emoji": "🌾", "title": "برداشت {n} محصول",      "target": 10, "tp": 700, "xp": 70},
    "mine":    {"emoji": "⛏", "title": "{n} بار کنده‌کاری",      "target": 20, "tp": 450, "xp": 45},
    "plant":   {"emoji": "🌱", "title": "کاشت {n} بذر",          "target": 5,  "tp": 550, "xp": 50},
    "search":  {"emoji": "🔍", "title": "{n} بار جستجو",         "target": 1,  "tp": 280, "xp": 22},
    "feed":    {"emoji": "🍖", "title": "{n} بار غذا دادن به سگ", "target": 3,  "tp": 350, "xp": 28},
}
# شانس نوع جایزه هر کوئست: مابقی بذر رندوم معمولیه
DAILY_QUEST_TP_WEIGHT = 0.55     # ۵۵% جایزه تی‌پوینت
DAILY_QUEST_XP_WEIGHT = 0.30     # ۳۰% جایزه تجربه
DAILY_QUEST_COUNT_MIN = 2        # حداقل ماموریت روزانه
DAILY_QUEST_COUNT_MAX = 3        # حداکثر ماموریت روزانه
