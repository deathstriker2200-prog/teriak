"""منطق حمله: استت‌ها | کولدون | هدف | نتیجه نبرد با مادیفایر سگ و زره افسانه‌ای"""

import random

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import config
from models import User
from services import dogs as dog_svc
from services import users as user_svc
from utils import now_utc


# ───────── استت‌ها ─────────

def _effective_bonus(base: int, user_level: int) -> int:
    """قدرت آیتم با بونس لول کاربر"""
    return int(base * (1 + config.LEVEL_ITEM_BONUS * max(0, user_level - 1)))


def combat_stats(user: User, item_keys: list[str], dogs: list) -> tuple[int, int]:
    """
    (حمله, دفاع) = پایه بر اساس لول + بهترین سلاح + سگ‌ها / بهترین زره
    فرمول نبرد: حمله بازیکن + سگ + سلاح  مقابل  دفاع بازیکن + زره
    """
    atk = config.ATK_BASE + config.ATK_PER_LEVEL * user.level
    dfn = config.DEF_BASE + config.DEF_PER_LEVEL * user.level

    weapon_bonus = max(
        (config.WEAPONS[k]["attack"] for k in item_keys if k in config.WEAPONS), default=0
    )
    armor_bonus = max(
        (config.ARMORS[k]["defense"] for k in item_keys if k in config.ARMORS), default=0
    )

    atk += _effective_bonus(weapon_bonus, user.level)
    dfn += _effective_bonus(armor_bonus, user.level)

    atk += sum(dog_svc.dog_attack(d) for d in dogs)
    return atk, dfn


def best_weapon_name(item_keys: list[str]) -> str | None:
    owned = [k for k in item_keys if k in config.WEAPONS]
    if not owned:
        return None
    best = max(owned, key=lambda k: config.WEAPONS[k]["attack"])
    return config.WEAPONS[best]["name"]


def best_armor_name(item_keys: list[str]) -> str | None:
    owned = [k for k in item_keys if k in config.ARMORS]
    if not owned:
        return None
    best = max(owned, key=lambda k: config.ARMORS[k]["defense"])
    return config.ARMORS[best]["name"]


def has_legend_armor(item_keys: list[str]) -> bool:
    """آیا زره افسانه‌ای داره؟ — سکه دزدیده‌شده ازش نصف میشه"""
    return any(config.ARMORS.get(k, {}).get("legendary") for k in item_keys)


# ───────── کولدون و هدف ─────────

def cooldown_left(user: User) -> int:
    """ثانیه مونده از کولدون حمله — هر ۱ دقیقه یه حمله"""
    if not user.last_attack_at:
        return 0
    cd = config.ATTACK_COOLDOWN_MINUTES * 60
    left = cd - (now_utc() - user.last_attack_at).total_seconds()
    return max(0, int(left))


async def find_target(session: AsyncSession, user: User) -> User | None:
    """یه هدف رندوم هم‌لول — برای جستجوی منوی حمله"""
    lo = max(1, user.level - config.ATTACK_TARGET_LEVEL_RANGE)
    hi = user.level + config.ATTACK_TARGET_LEVEL_RANGE
    q = (
        select(User)
        .where(User.id != user.id, User.level >= lo, User.level <= hi)
        .order_by(func.random())
        .limit(1)
    )
    return (await session.execute(q)).scalar_one_or_none()


# ───────── فرمول نبرد و سرقت ─────────

def battle_roll(attacker_atk: int, defender_def: int) -> tuple[bool, int, int]:
    """
    فرمول احتمالاتی: قدرت‌ها اول ضریب شانس می‌گیرن (۰٫۸۵ تا ۱٫۱۵)
    بعد شانس برد مهاجم = حمله / (حمله + دفاع)
    """
    a = attacker_atk * random.uniform(0.85, 1.15)
    d = defender_def * random.uniform(0.85, 1.15)
    win_chance = a / (a + d)
    return random.random() < win_chance, round(a), round(d)


def steal_amount(
    victim_cash: int,
    attacker_dogs: list,
    victim_has_legend: bool,
) -> tuple[int, float, bool]:
    """
    مبلغ سرقت با مادیفایرها
    خروجی: (مبلغ نهایی, درصد بونس سگ کمیاب, آیا زره افسانه‌ای نصف کرد)
    """
    pct = random.uniform(config.STEAL_MIN_PCT, config.STEAL_MAX_PCT)
    amount = victim_cash * pct

    bonus = dog_svc.rare_steal_bonus(attacker_dogs)
    if bonus:
        amount *= 1 + bonus

    if victim_has_legend and amount:
        amount *= 0.5

    return int(amount), bonus, bool(victim_has_legend and amount)


def cash_bucket(cash: int) -> str:
    """نمایش تقریبی دارایی هدف — عدد دقیق لو نمیره"""
    if cash < 1000:
        return "جیبش خالیه 🕳"
    if cash < 10000:
        return "یه پول معمولی داره 💵"
    if cash < 50000:
        return "وضعش خوبه 💰"
    return "صندوقش پره 🤑"


# ───────── اجرای کامل حمله (مشترک بین منو و ریپلای گروه) ─────────

async def execute_attack(session: AsyncSession, user: User, target: User) -> dict:
    """
    همه چک‌ها + محاسبات + تغییرات دیتابیس
    خروجی: دیکشنری نتیجه برای ساخت پیام — اگه ok نباشه reason داره
    """
    left = cooldown_left(user)
    if left:
        return {"ok": False, "reason": "cooldown", "left": left}

    if user.energy < config.ATTACK_ENERGY_COST:
        return {"ok": False, "reason": "energy"}

    if target.id == user.id:
        return {"ok": False, "reason": "self"}

    user_items = await user_svc.get_item_keys(session, user.id)
    target_items = await user_svc.get_item_keys(session, target.id)
    user_dogs = await dog_svc.get_user_dogs(session, user.id)

    atk, _ = combat_stats(user, user_items, user_dogs)
    _, dfn = combat_stats(target, target_items, [])

    # هزینه حمله
    user.energy -= config.ATTACK_ENERGY_COST
    user.last_attack_at = now_utc()

    win, a_roll, d_roll = battle_roll(atk, dfn)
    result: dict = {
        "ok": True,
        "win": win,
        "a_roll": a_roll,
        "d_roll": d_roll,
        "amount": 0,
        "bonus": 0.0,
        "halved": False,
        "xp": config.ATTACK_WIN_XP if win else config.ATTACK_LOSE_XP,
        "penalty": 0 if win else config.ATTACK_LOSE_ENERGY,
        "notes": [],
    }

    if win:
        amount, bonus, halved = steal_amount(
            target.cash, user_dogs, has_legend_armor(target_items)
        )
        target.cash -= amount
        user.cash += amount
        user.wins += 1
        target.losses += 1
        result["notes"] = user_svc.add_xp(user, config.ATTACK_WIN_XP)
        result.update(amount=amount, bonus=bonus, halved=halved)
    else:
        user.losses += 1
        target.wins += 1
        user.energy = max(0, user.energy - config.ATTACK_LOSE_ENERGY)
        result["notes"] = user_svc.add_xp(user, config.ATTACK_LOSE_XP)

    return result
