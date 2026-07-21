"""منطق اقتصادی: قیمت زمین | آپگرید | بذر | کنده‌کاری | منحنی تجربه"""

import random

import config


# ───────── منحنی تجربه (Idle/RPG — پایین سریع | بالا سنگین‌تر) ─────────

def xp_need(level: int) -> int:
    """xp لازم برای رفتن از این لول به لول بعد"""
    return int(config.XP_CURVE_BASE * (level ** config.XP_CURVE_EXP))


# ───────── زمین ─────────

def plot_price(plots_count: int) -> int:
    """قیمت زمین بعدی — افزایشی برای هر زمین جدید"""
    return int(config.PLOT_BASE_PRICE * (config.PLOT_PRICE_GROWTH ** plots_count))


def plot_required_level(plots_count: int) -> int:
    """گیت لول برای خرید زمین بعدی — زمین شماره n لول n می‌خواد"""
    return plots_count + 1


def upgrade_price(plot_level: int) -> int:
    """هزینه آپگرید از لول فعلی به لول بعد — تصاعدی"""
    return int(config.UPGRADE_BASE_PRICE * (config.UPGRADE_PRICE_GROWTH ** (plot_level - 1)))


# ───────── بذر و محصول ─────────

def crop_yield(seed_key: str, plot_level: int = 1, user_level: int = 1) -> int:
    """درآمد برداشت با ضریب لول زمین و بونس لول کاربر"""
    base = config.SEEDS[seed_key]["sell"]
    mult = config.PLOT_YIELD_MULT.get(plot_level, config.PLOT_YIELD_MULT[1])
    user_mult = 1 + config.LEVEL_YIELD_BONUS * max(0, user_level - 1)
    return int(base * mult * user_mult)


def crop_grow_seconds(seed_key: str, plot_level: int = 1) -> int:
    """مدت آماده شدن با ضریب سرعت لول زمین"""
    minutes = config.SEEDS[seed_key]["grow_min"]
    mult = config.PLOT_SPEED_MULT.get(plot_level, config.PLOT_SPEED_MULT[1])
    return max(30, int(minutes * 60 * mult))


def is_seed_unlocked(seed_key: str, user_level: int) -> bool:
    return user_level >= config.SEEDS[seed_key]["min_level"]


# ───────── کنده‌کاری ─────────

def mine_roll() -> int:
    """قرعه روزانه — بازه پایین با وزن بیشتر (۱۰ تا ۱۰۰ پرتکرارتر از ۱۰۰ تا ۱۵۰)"""
    if random.random() < config.MINE_COMMON_WEIGHT:
        return random.randint(config.MINE_MIN, config.MINE_COMMON_MAX)
    return random.randint(config.MINE_COMMON_MAX + 1, config.MINE_MAX)
