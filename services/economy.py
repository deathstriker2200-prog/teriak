"""منطق اقتصادی: قیمت زمین | آپگرید | بذر | کنده‌کاری | منحنی تجربه"""

import random

import config


# ───────── منحنی تجربه (Idle/RPG، پایین سریع | بالا سنگین‌تر) ─────────

def xp_need(level: int) -> int:
    """xp لازم برای رفتن از این لول به لول بعد"""
    return int(config.XP_CURVE_BASE * (level ** config.XP_CURVE_EXP))


# ───────── زمین ─────────

def plot_info(plot_number: int) -> dict:
    """مشخصات زمین شماره n (۱ تا MAX)، قیمت/زمان ساخت/لول لازم"""
    n = min(max(plot_number, 1), config.MAX_PLOTS)
    return config.PLOT_CATALOG[n]


def plot_price(plots_count: int) -> int:
    """قیمت زمین بعدی بر اساس تعداد زمین‌های فعلی، هرکی خیلی گرون‌تر"""
    return plot_info(plots_count + 1)["price"]


def plot_required_level(plots_count: int) -> int:
    """گیت لول برای خرید زمین بعدی"""
    return plot_info(plots_count + 1)["min_level"]


def plot_build_seconds(plots_count: int) -> int:
    """زمان ساخت زمین بعدی به ثانیه"""
    return plot_info(plots_count + 1)["build_sec"]


def upgrade_price(plot_level: int) -> int:
    """هزینه آپگرید از لول فعلی به لول بعد، جدول رند قیمت"""
    lv = min(max(plot_level, 1), config.PLOT_MAX_LEVEL)
    return config.PLOT_UPGRADE_PRICES[lv - 1]


# ───────── بذر و محصول ─────────

def plot_yield_mult(plot_level: int) -> float:
    """ضریب درآمد زمین تو لولش، هر لول ۲۵% بیشتر (×۱٫۲۵)"""
    return config.PLOT_YIELD_PER_LEVEL ** max(0, plot_level - 1)


def plot_speed_mult(plot_level: int) -> float:
    """ضریب سرعت رشد زمین تو لولش، هر لول ۴۰% سرعت بیشتر (زمان ÷۱٫۴۰)"""
    return config.PLOT_SPEED_PER_LEVEL ** max(0, plot_level - 1)


def crop_yield(seed_key: str, plot_level: int = 1, user_level: int = 1) -> int:
    """درآمد برداشت با ضریب لول زمین و بونس لول کاربر"""
    base = config.SEEDS[seed_key]["sell"]
    user_mult = 1 + config.LEVEL_YIELD_BONUS * max(0, user_level - 1)
    return int(base * plot_yield_mult(plot_level) * user_mult)


def crop_grow_seconds(seed_key: str, plot_level: int = 1) -> int:
    """مدت آماده شدن با ضریب سرعت لول زمین، هر لول آپ ۴۰% سرعت بیشتر"""
    minutes = config.SEEDS[seed_key]["grow_min"]
    return max(30, int(minutes * 60 / plot_speed_mult(plot_level)))


def is_seed_unlocked(seed_key: str, user_level: int) -> bool:
    return user_level >= config.SEEDS[seed_key]["min_level"]


# ───────── کنده‌کاری ─────────

def mine_roll() -> int:
    """قرعه روزانه، بازه پایین با وزن بیشتر (۱۰ تا ۱۰۰ پرتکرارتر از ۱۰۰ تا ۱۵۰)"""
    if random.random() < config.MINE_COMMON_WEIGHT:
        return random.randint(config.MINE_MIN, config.MINE_COMMON_MAX)
    return random.randint(config.MINE_COMMON_MAX + 1, config.MINE_MAX)
