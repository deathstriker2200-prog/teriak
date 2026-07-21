"""منطق حمله: استت‌ها | کولدون | پیدا کردن هدف | نتیجه نبرد"""

import random

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import config
from models import User
from utils import now_utc


def combat_stats(user: User, item_keys: list[str]) -> tuple[int, int]:
    """(حمله, دفاع) = پایه بر اساس لول + بهترین سلاح + بهترین زره"""
    atk = config.ATK_BASE + config.ATK_PER_LEVEL * user.level
    dfn = config.DEF_BASE + config.DEF_PER_LEVEL * user.level

    for key in item_keys:
        item = config.SHOP_ITEMS.get(key)
        if not item:
            continue
        if item["type"] == "weapon":
            atk += item["attack"]
        elif item["type"] == "armor":
            dfn += item["defense"]
    return atk, dfn


def cooldown_left(user: User) -> int:
    """ثانیه مونده از کولدون حمله — صفر یعنی آزاده"""
    if not user.last_attack_at:
        return 0
    cd = config.ATTACK_COOLDOWN_MINUTES * 60
    left = cd - (now_utc() - user.last_attack_at).total_seconds()
    return max(0, int(left))


async def find_target(session: AsyncSession, user: User) -> User | None:
    """یه هدف رندوم هم‌لول — خودت انتخاب نمیشی"""
    lo = max(1, user.level - config.ATTACK_TARGET_LEVEL_RANGE)
    hi = user.level + config.ATTACK_TARGET_LEVEL_RANGE
    q = (
        select(User)
        .where(User.id != user.id, User.level >= lo, User.level <= hi)
        .order_by(func.random())
        .limit(1)
    )
    return (await session.execute(q)).scalar_one_or_none()


def battle_roll(attacker_atk: int, defender_def: int) -> tuple[bool, int, int]:
    """
    فرمول احتمالاتی: قدرت‌ها اول ضریب شانس می‌گیرن (۰٫۸۵ تا ۱٫۱۵)
    بعد شانس برد مهاجم = حمله / (حمله + دفاع)
    اینطوری ضعیف‌تر هم همیشه یه شانسی داره و قوی‌تر صد در صد نمی‌بره
    """
    a = attacker_atk * random.uniform(0.85, 1.15)
    d = defender_def * random.uniform(0.85, 1.15)
    win_chance = a / (a + d)
    return random.random() < win_chance, round(a), round(d)


def steal_amount(victim_cash: int) -> int:
    """مبلغ سرقت: درصدی رندوم از پول قربانی"""
    pct = random.uniform(config.STEAL_MIN_PCT, config.STEAL_MAX_PCT)
    return int(victim_cash * pct)


def cash_bucket(cash: int) -> str:
    """نمایش تقریبی دارایی هدف — عدد دقیق لو نمیره"""
    if cash < 1000:
        return "جیبش خالیه 🕳"
    if cash < 10000:
        return "یه پول معمولی داره 💵"
    if cash < 50000:
        return "وضعش خوبه 💰"
    return "صندوقش پره 🤑"
