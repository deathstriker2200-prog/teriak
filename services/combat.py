"""منطق حمله: استت‌ها | کولدون | هدف | نتیجه نبرد با مادیفایر سگ و زره افسانه‌ای"""

import random

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import config
from models import User
from services import dogs as dog_svc
from services import users as user_svc
from utils import now_utc


# ───────── سپر محافظ 🛡 ─────────

def shield_left(user: User) -> int:
    """ثانیه مونده از سپر محافظ، صفر یعنی سپری نیس"""
    if not user.shield_until:
        return 0
    left = (user.shield_until - now_utc()).total_seconds()
    return max(0, int(left))


def give_shield(user: User) -> None:
    """به هدف حمله سپر بده، ۱۵ دقیقه کسی نمی‌تونه بزنتش"""
    from datetime import timedelta
    user.shield_until = now_utc() + timedelta(minutes=config.ATTACK_SHIELD_MINUTES)


# ───────── استت‌ها ─────────

def _effective_bonus(base: int, user_level: int) -> int:
    """قدرت آیتم با بونس لول کاربر"""
    return int(base * (1 + config.LEVEL_ITEM_BONUS * max(0, user_level - 1)))


def weapon_power(item_keys: list[str], user_level: int) -> int:
    """قدرت موثر بهترین سلاح، مبنای دمیج نمایشی نبرد"""
    base = max(
        (config.WEAPONS[k]["attack"] for k in item_keys if k in config.WEAPONS), default=0
    )
    return _effective_bonus(base, user_level)


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
    """آیا زره افسانه‌ای داره؟، سکه دزدیده‌شده ازش نصف میشه"""
    return any(config.ARMORS.get(k, {}).get("legendary") for k in item_keys)


# ───────── کولدون و هدف ─────────

def cooldown_left(user: User) -> int:
    """ثانیه مونده از کولدون حمله، هر ۱ دقیقه یه حمله"""
    if not user.last_attack_at:
        return 0
    cd = config.ATTACK_COOLDOWN_MINUTES * 60
    left = cd - (now_utc() - user.last_attack_at).total_seconds()
    return max(0, int(left))


async def find_target(session: AsyncSession, user: User) -> User | None:
    """یه هدف رندوم هم‌لول، برای جستجوی منوی حمله، سپردارها کنار گذاشته میشن"""
    lo = max(1, user.level - config.ATTACK_TARGET_LEVEL_RANGE)
    hi = user.level + config.ATTACK_TARGET_LEVEL_RANGE
    q = (
        select(User)
        .where(
            User.id != user.id, User.level >= lo, User.level <= hi,
            (User.shield_until.is_(None)) | (User.shield_until <= now_utc()),
        )
        .order_by(func.random())
        .limit(1)
    )
    return (await session.execute(q)).scalar_one_or_none()


# ───────── فرمول نبرد و سرقت ─────────

def win_chance(attacker_atk: int, defender_def: int) -> float:
    """
    شانس برد مهاجم بر اساس اختلاف قدرت دو طرف
    قدرت مساوی، ۵۰/۵۰ | اختلاف زیاد، قوی‌تر شانسش بیشتره ولی هیچ‌وقت ۱۰۰% تضمینی نیس
    """
    total = attacker_atk + defender_def
    if total <= 0:
        return 0.5
    x = (attacker_atk - defender_def) / total
    chance = 0.5 + x * config.ATTACK_CHANCE_SCALE
    return min(config.ATTACK_WIN_MAX_CHANCE, max(config.ATTACK_WIN_MIN_CHANCE, chance))


def display_damage(weapon_eff: int) -> int:
    """دمیج نمایشی بر اساس قدرت سلاح، دست خالی هم مشتشو داره"""
    base = max(5, weapon_eff)
    return int(base * random.uniform(1.0, 1.6))


def steal_amount(
    victim_cash: int,
    attacker_dogs: list,
    victim_has_legend: bool,
    victim_dogs: list | None = None,
) -> tuple[int, float, bool]:
    """
    مبلغ سرقت با مادیفایرها (گرگ + شخصیت سگ‌ها و زره افسانه‌ای)
    خروجی: (مبلغ نهایی, درصد بونس غرامت مهاجم, آیا زره افسانه‌ای نصف کرد)
    """
    pct = random.uniform(config.STEAL_MIN_PCT, config.STEAL_MAX_PCT)
    amount = victim_cash * pct

    bonus = dog_svc.rare_steal_bonus(attacker_dogs) + dog_svc.personality_steal_bonus(attacker_dogs)
    if bonus:
        amount *= 1 + bonus

    if victim_dogs:
        cut = dog_svc.personality_steal_cut(victim_dogs)
        if cut:
            amount *= 1 - cut

    if victim_has_legend and amount:
        amount *= 0.5

    return int(amount), bonus, bool(victim_has_legend and amount)


def cash_bucket(cash: int) -> str:
    """نمایش تقریبی دارایی هدف، عدد دقیق لو نمیره"""
    if cash < 1000:
        return "جیبش خالیه 🕳"
    if cash < 10000:
        return "یه پول معمولی داره 💵"
    if cash < 50000:
        return "وضعش خوبه 💰"
    return "صندوقش پره 🤑"


# ───────── اجرای کامل حمله (مشترک بین منو و ریپلای گروه) ─────────

async def execute_attack(
    session: AsyncSession, user: User, target: User, break_shield: bool = False
) -> dict:
    """
    همه چک‌ها + محاسبات + تغییرات دیتابیس
    خروجی: دیکشنری نتیجه برای ساخت پیام، اگه ok نباشه reason داره
    reason: cooldown | energy | self | shield_target | shield_self
    break_shield=True یعنی مهاجم آگاهانه سپر خودشو شکسته و حمله کرده
    """
    left = cooldown_left(user)
    if left:
        return {"ok": False, "reason": "cooldown", "left": left}

    if user.energy < config.ATTACK_ENERGY_COST:
        return {"ok": False, "reason": "energy"}

    if target.id == user.id:
        return {"ok": False, "reason": "self"}

    t_shield = shield_left(target)
    if t_shield:
        return {"ok": False, "reason": "shield_target", "left": t_shield}

    self_shield = shield_left(user)
    if self_shield and not break_shield:
        return {"ok": False, "reason": "shield_self", "left": self_shield}
    if self_shield:
        user.shield_until = None  # تایید کرده بود، سپرش الان می‌شکنه

    user_items = await user_svc.get_item_keys(session, user.id)
    target_items = await user_svc.get_item_keys(session, target.id)
    user_dogs = await dog_svc.get_user_dogs(session, user.id)
    target_dogs = await dog_svc.get_user_dogs(session, target.id)

    atk, _ = combat_stats(user, user_items, user_dogs)
    _, dfn = combat_stats(target, target_items, target_dogs)

    # بونس ساختمان‌های تیم، حمله مهاجم و دفاع مدافع
    from services import teams as team_svc
    user_team = await team_svc.get_team_of(session, user.id)
    target_team = await team_svc.get_team_of(session, target.id)
    tbuff = team_svc.atk_bonus(user_team)
    tbuff_def = team_svc.def_bonus(target_team)
    if tbuff:
        atk = int(atk * (1 + tbuff))
    if tbuff_def:
        dfn = int(dfn * (1 + tbuff_def))

    # افکت آب و هوا روی نبرد (طوفان −۱۰% حمله | مه +۲۰% دفاع)
    from services import world as world_svc
    wkey, _ = await world_svc.current_weather(session)
    watk, wdef = world_svc.weather_combat_mods(wkey)
    if watk:
        atk = max(1, int(atk * (1 + watk)))
    if wdef:
        dfn = max(1, int(dfn * (1 + wdef)))

    # گرگ سیاه دفاع حریف رو خرد می‌کنه، تا ۳۰% بسته به لولش
    def_cut = dog_svc.rare_defense_cut(user_dogs)
    if def_cut:
        dfn = max(1, int(dfn * (1 - def_cut)))

    # هزینه حمله
    user.energy -= config.ATTACK_ENERGY_COST
    user.last_attack_at = now_utc()

    # نتیجه بر اساس شانس قدرت‌محور + دمیج نمایشی از قدرت سلاح + احتمال بحرانی
    chance = win_chance(atk, dfn)
    win = random.random() < chance
    crit = random.random() < config.ATTACK_CRIT_CHANCE
    if win:
        dmg = display_damage(weapon_power(user_items, user.level))
    else:
        dmg = display_damage(weapon_power(target_items, target.level))
    if crit:
        dmg = int(dmg * config.ATTACK_CRIT_DMG_MULT)

    result: dict = {
        "ok": True,
        "win": win,
        "a_pow": atk,
        "d_pow": dfn,
        "chance": chance,
        "dmg": dmg,
        "crit": crit,
        "amount": 0,
        "bonus": 0.0,
        "halved": False,
        "defcut": def_cut,
        "tbuff": tbuff,
        "weather": wkey,
        "xp": config.ATTACK_WIN_XP if win else config.ATTACK_LOSE_XP,
        "penalty": 0 if win else config.ATTACK_LOSE_ENERGY,
        "notes": [],
    }

    # هدف هر حمله (برد یا باخت) برای مدتی سپر محافظ می‌گیره
    give_shield(target)

    if win:
        amount, bonus, halved = steal_amount(
            target.cash, user_dogs, has_legend_armor(target_items), target_dogs
        )
        if crit and amount:
            amount = int(amount * config.ATTACK_CRIT_STEAL_MULT)
        target.cash -= amount
        user.cash += amount
        user.wins += 1
        target.losses += 1
        result["notes"] = user_svc.add_xp(user, config.ATTACK_WIN_XP)

        # قلاب کوئست تیم، هر برد تو دعوا حساب میشه
        quest_msg = await team_svc.record_kill(session, user)
        if quest_msg:
            result["notes"].append(quest_msg)
        result.update(amount=amount, bonus=bonus, halved=halved)
    else:
        user.losses += 1
        target.wins += 1
        user.energy = max(0, user.energy - config.ATTACK_LOSE_ENERGY)
        result["notes"] = user_svc.add_xp(user, config.ATTACK_LOSE_XP)

    return result
