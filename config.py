"""
تنظیمات قابل تغییر ربات «تریاکی»
همه‌ی قیمت‌ها / تایمرها / فرمول‌ها همینجاست
"""

import os

BOT_TOKEN = os.getenv("TERIAKY_TOKEN", "")
DATABASE_URL = os.getenv("TERIAKY_DB", "sqlite+aiosqlite:///teriaky.db")

# ───────── شروع بازی ─────────
START_CASH = 500                # پول نقد شروع
MAX_ENERGY = 100
ENERGY_REGEN_MINUTES = 3        # هر چند دقیقه ۱ انرژی برگرده

# ───────── لول و تجربه ─────────
XP_BASE = 100                   # xp لازم برای لول N برابر XP_BASE * N
LEVEL_CASH_REWARD = 250         # جایزه نقدی لول‌آپ = این عدد × لول جدید

# ───────── زمین (Plot) ─────────
PLOT_BASE_PRICE = 1000          # قیمت اولین زمین
PLOT_PRICE_GROWTH = 1.65        # هر زمین جدید = قیمت قبلی × این ضریب
MAX_PLOTS = 8
PLOT_MAX_LEVEL = 3
UPGRADE_BASE_PRICE = 800        # هزینه آپگرید از لول ۱ به ۲
UPGRADE_PRICE_GROWTH = 2.4      # ضریب تصاعدی هزینه آپگرید

# ضریب درآمد و سرعت هر لول زمین
PLOT_YIELD_MULT = {1: 1.0, 2: 1.8, 3: 2.8}
PLOT_SPEED_MULT = {1: 1.0, 2: 0.85, 3: 0.70}

# ───────── محصولات (به ترتیب باز شدن با لول) ─────────
# cost = هزینه کاشت | grow_min = دقیقه آماده‌سازی | sell = قیمت فروش پایه | xp = تجربه برداشت
CROPS = {
    "teriak":    {"name": "تریاک",      "min_level": 1,  "cost": 150,  "grow_min": 5,  "sell": 420,   "xp": 10},
    "marijuana": {"name": "ماری‌جوانا",  "min_level": 3,  "cost": 400,  "grow_min": 8,  "sell": 1150,  "xp": 18},
    "koka":      {"name": "کوکا",        "min_level": 5,  "cost": 1000, "grow_min": 12, "sell": 3000,  "xp": 30},
    "ghat":      {"name": "قات",         "min_level": 7,  "cost": 2400, "grow_min": 18, "sell": 7500,  "xp": 45},
    "peyote":    {"name": "پیوته",       "min_level": 10, "cost": 6000, "grow_min": 25, "sell": 20000, "xp": 70},
}

# ───────── کنده‌کاری (درآمد روزانه) ─────────
MINE_COOLDOWN_HOURS = 24        # فاصله بین دو کنده‌کاری
MINE_MIN = 10                   # حداقل جایزه
MINE_MAX = 150                  # حداکثر جایزه
MINE_COMMON_MAX = 100           # تا این عدد «شانس بیشتر» داره
MINE_COMMON_WEIGHT = 0.75       # ۷۵٪ مواقع بین MINE_MIN تا MINE_COMMON_MAX میاد
MINE_XP = 3                     # یه ذره تجربه هم میده

# ───────── حمله (PvP) ─────────
ATTACK_COOLDOWN_MINUTES = 10    # کولدون بین حمله‌ها
ATTACK_ENERGY_COST = 12         # هزینه انرژی هر حمله
ATTACK_LOSE_ENERGY = 15         # جریمه انرژی در صورت باخت
ATTACK_TARGET_LEVEL_RANGE = 2   # هدف فقط در بازه ±۲ لول خودت
STEAL_MIN_PCT = 0.10            # حداقل درصد سرقت از پول قربانی
STEAL_MAX_PCT = 0.25            # حداکثر درصد سرقت
ATTACK_WIN_XP = 30
ATTACK_LOSE_XP = 8
ATK_BASE = 4                    # حمله پایه = ATK_BASE + لول × ATK_PER_LEVEL
ATK_PER_LEVEL = 2
DEF_BASE = 3                    # دفاع پایه = DEF_BASE + لول × DEF_PER_LEVEL
DEF_PER_LEVEL = 2

# ───────── فروشگاه ─────────
# type: weapon (افزایش حمله) | armor (افزایش دفاع)
SHOP_ITEMS = {
    "knife":   {"name": "چاقوی دسته‌چوبی",  "type": "weapon", "attack": 6,   "price": 400},
    "pipe":    {"name": "میله آهنی",        "type": "weapon", "attack": 14,  "price": 1200},
    "shocker": {"name": "شوکر دست‌ساز",      "type": "weapon", "attack": 30,  "price": 3500},
    "deagle":  {"name": "کلت نقره‌ای",       "type": "weapon", "attack": 60,  "price": 10000},
    "plasma":  {"name": "شلیک‌کن پلاسما",    "type": "weapon", "attack": 130, "price": 30000},
    "jacket":  {"name": "کت چرمی",          "type": "armor",  "defense": 4,  "price": 350},
    "vest":    {"name": "جلیقه سنگین",      "type": "armor",  "defense": 12, "price": 1500},
    "steel":   {"name": "زره فولادی",       "type": "armor",  "defense": 28, "price": 4500},
    "nano":    {"name": "زره نانو",         "type": "armor",  "defense": 70, "price": 20000},
}

# ───────── رتبه‌بندی ─────────
RANK_LIMIT = 10
