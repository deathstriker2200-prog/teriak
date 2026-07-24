"""
حمله پی‌وی کلاسیک ⚔️، سیستم قدیمی بدون HP

قدرت حمله مهاجم با دفاع حریف مقایسه میشه و شانس برد درصدی درمیاد
هدف‌ها فقط حوالی لول خودتن (±۲ لول) | بعد هر حمله قربانی 12 ساعت مصونیت می‌گیره
و از لیست حمله‌های پی‌وی خارج میشه
ماژولاره: همه ضرایب توی config بخش «حمله پی‌وی کلاسیک» قابل تغییره
"""

import random
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import config
from models import User
from services import combat
from services import dogs as dog_svc
from services import users as user_svc
from utils import now_utc


# ───────── مصونیت قربانی 🛡 ─────────

def shield_left(user: User) -> int:
    """ثانیه مونده از مصونیت پی‌وی، صفر یعنی دوباره تو لیست حمله‌ست"""
    if not user.shield_until:
        return 0
    left = (user.shield_until - now_utc()).total_seconds()
    return max(0, int(left))


# ───────── کولدون مهاجم ⏳ ─────────

def cooldown_left(user: User) -> int:
    """ثانیه مونده از کولدون حمله پی‌وی، صفر یعنی آماده حمله‌ست"""
    if not user.pv_attack_at:
        return 0
    end = user.pv_attack_at + timedelta(seconds=config.PV_ATTACK_COOLDOWN_SECONDS)
    return max(0, int((end - now_utc()).total_seconds()))


# ───────── هزینه «هدف دیگه» 🎲 ─────────

def reroll_cost(level: int) -> int:
    """هزینه دکمه هدف دیگه، خطی با لول جست‌وجوگر بین حداقل و حداکثر کانفیگ"""
    lo, hi = config.PV_REROLL_MIN_COST, config.PV_REROLL_MAX_COST
    lv = max(1, min(config.MAX_LEVEL, level))
    span = max(1, config.MAX_LEVEL - 1)
    return int(lo + (hi - lo) * (lv - 1) / span)


# ───────── قدرت و شانس 🎲 ─────────

async def powers(session: AsyncSession, user: User) -> tuple[int, int]:
    """(حمله, دفاع) کاربر با آیتم‌ها و سگ‌هاش، مبنای مقایسه کلاسیک"""
    items = await user_svc.get_item_keys(session, user.id)
    dogs = await dog_svc.get_user_dogs(session, user.id)
    return combat.combat_stats(user, items, dogs)


def win_chance(a_atk: int, t_dfn: int) -> float:
    """شانس برد مهاجم، پایه ۵۰ درصد و هر واحد اختلاف قدرت جابه‌جاش می‌کنه (با کف و سقف)"""
    raw = config.PV_BASE_CHANCE + (a_atk - t_dfn) * config.PV_ATTACK_CHANCE_SCALE
    return max(config.PV_ATTACK_MIN_CHANCE, min(config.PV_ATTACK_MAX_CHANCE, raw))


# ───────── هدف شانسی 🎯 ─────────

async def pick_random_target(session: AsyncSession, user: User, exclude_id: int | None = None) -> User | None:
    """
    یه هدف شانسی حوالی لول کاربر (±۲)، خودش و کسایی که مصونیت دارن حذف میشن
    exclude_id آیدی هدف فعلی پیش‌نمایشه که دکمه «هدف دیگه» باید ردش کنه
    هدفی نبود None برمی‌گرده
    """
    rng = config.PV_ATTACK_LEVEL_RANGE
    conds = [
        User.id != user.id,
        User.level >= user.level - rng,
        User.level <= user.level + rng,
        (User.shield_until.is_(None)) | (User.shield_until <= now_utc()),
    ]
    if exclude_id:
        conds.append(User.id != exclude_id)
    q = select(User).where(*conds).order_by(func.random()).limit(1)
    return (await session.execute(q)).scalar_one_or_none()


# ───────── اجرای حمله ⚔️ ─────────

async def execute(session: AsyncSession, attacker: User, victim: User) -> dict:
    """
    همه چک‌ها + رول شانس + تغییرات دیتابیس یه حمله پی‌وی (بدون کامیت)
    reason: self | level | shield | energy | cooldown
    هر حمله، برد یا باخت، قربانی رو 12 ساعت مصون می‌کنه
    کولدون مهاجم ثبت میشه و به قربانی هم یه تجربه ناچیز میرسه
    """
    if victim.id == attacker.id:
        return {"ok": False, "reason": "self"}

    rng = config.PV_ATTACK_LEVEL_RANGE
    if abs(victim.level - attacker.level) > rng:
        return {"ok": False, "reason": "level"}

    sl = shield_left(victim)
    if sl:
        return {"ok": False, "reason": "shield", "left": sl}

    if attacker.energy < config.PV_ATTACK_ENERGY_COST:
        return {"ok": False, "reason": "energy"}

    cd = cooldown_left(attacker)
    if cd:
        return {"ok": False, "reason": "cooldown", "left": cd}

    attacker.energy -= config.PV_ATTACK_ENERGY_COST
    attacker.pv_attack_at = now_utc()

    a_atk, _ = await powers(session, attacker)
    _, t_dfn = await powers(session, victim)
    chance = win_chance(a_atk, t_dfn)
    won = random.random() < chance

    # مصونیت قربانی بعد از حمله، تو برد و باخت هر دو
    victim.shield_until = now_utc() + timedelta(seconds=config.PV_ATTACK_SHIELD_SECONDS)

    steal = 0
    penalty = 0
    if won:
        attacker.wins += 1
        victim.losses += 1
        pct = random.uniform(config.PV_ATTACK_STEAL_MIN_PCT, config.PV_ATTACK_STEAL_MAX_PCT)
        steal = max(0, int(victim.cash * pct))
        if steal:
            victim.cash -= steal
            attacker.cash += steal
        xp = config.PV_ATTACK_WIN_XP
    else:
        victim.wins += 1
        attacker.losses += 1
        penalty = max(0, int(attacker.cash * config.PV_ATTACK_LOSE_PENALTY_PCT))
        if penalty:
            attacker.cash -= penalty
            victim.cash += penalty
        xp = config.PV_ATTACK_LOSE_XP

    notes = user_svc.add_xp(attacker, xp)
    # قربانی هم یه تجربه ناچیز می‌گیره، حمله نکرده ولی خورده
    victim_xp = config.PV_ATTACK_VICTIM_XP
    if victim_xp:
        user_svc.add_xp(victim, victim_xp)
    return {
        "ok": True,
        "won": won,
        "chance": chance,
        "steal": steal,
        "penalty": penalty,
        "xp": xp,
        "victim_xp": victim_xp,
        "notes": notes,
        "a_pow": a_atk,
        "d_pow": t_dfn,
    }
