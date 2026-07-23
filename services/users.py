"""سرویس کاربر: ثبت‌نام | انرژی | آیتم | لول‌آپ"""

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import config
from models import InventoryItem, Plot, User
from services.economy import xp_need
from utils import fa_num, money, now_utc


async def get_or_create(session: AsyncSession, tg_user) -> tuple[User, bool]:
    """ثبت‌نام خودکار با اولین تعامل، یه زمین رایگان هم بهت میرسه"""
    user = await get_by_tg(session, tg_user.id)
    if user:
        # اسم/یوزرنیم ممکنه عوض شده باشه
        user.username = tg_user.username
        user.first_name = tg_user.first_name
        user.last_seen_at = now_utc()
        return user, False

    user = User(
        telegram_id=tg_user.id,
        username=tg_user.username,
        first_name=tg_user.first_name,
    )
    session.add(user)
    await session.flush()  # گرفتن id بدون کامیت
    user.last_seen_at = now_utc()
    session.add(Plot(user_id=user.id))  # زمین اول هدیه خونه‌بختگی 🎁
    return user, True


async def get_by_tg(session: AsyncSession, telegram_id: int) -> User | None:
    q = select(User).where(User.telegram_id == telegram_id)
    return (await session.execute(q)).scalar_one_or_none()


async def search_users(session: AsyncSession, query: str) -> list[User]:
    """
    جستجوی کاربر برای /user ادمین
    آیدی عددی → دقیق | @یوزرنیم → اول مچ دقیق بعد جزئی | بخشی از اسم/یوزرنیم → جزئی
    """
    q = (query or "").strip()
    if not q:
        return []
    if q.lstrip("-").isdigit():
        u = await get_by_tg(session, int(q))
        return [u] if u else []

    norm = q.lstrip("@").lower()
    if not norm:
        return []

    exact = list((await session.execute(
        select(User).where(func.lower(User.username) == norm).limit(1)
    )).scalars())
    if exact:
        return exact

    qy = (
        select(User)
        .where(
            (func.lower(User.username).contains(norm))
            | (func.lower(User.first_name).contains(norm))
        )
        .limit(8)
    )
    return list((await session.execute(qy)).scalars())


def display_name(user: User) -> str:
    return user.first_name or user.username or "رفیق"


def apply_energy_regen(user: User) -> None:
    """ریجن تنبلی انرژی، فقط موقع دیدن کاربر حساب میشه"""
    now = now_utc()
    if user.energy_updated_at is None:
        user.energy_updated_at = now

    if user.energy >= config.MAX_ENERGY:
        user.energy = min(user.energy, config.MAX_ENERGY)
        user.energy_updated_at = now
        return

    step = config.ENERGY_REGEN_MINUTES * 60
    elapsed = (now - user.energy_updated_at).total_seconds()
    gained = int(elapsed // step)
    if gained > 0:
        user.energy = min(config.MAX_ENERGY, user.energy + gained)
        user.energy_updated_at += timedelta(seconds=gained * step)
        if user.energy >= config.MAX_ENERGY:
            user.energy_updated_at = now


async def get_item_keys(session: AsyncSession, user_id: int) -> list[str]:
    q = select(InventoryItem.item_key).where(InventoryItem.user_id == user_id)
    return list((await session.execute(q)).scalars())


def add_xp(user: User, amount: int) -> list[str]:
    """
    اضافه کردن xp + مدیریت لول‌آپ، خروجی: لیست پیام‌های تبریک لول‌آپ
    جایزه هر لول: اسکناس + شارژ کامل انرژی + لیست چیزایی که باز میشن
    """
    notes: list[str] = []
    user.xp += amount

    while user.xp >= xp_need(user.level):
        user.xp -= xp_need(user.level)
        user.level += 1

        reward = config.LEVEL_CASH_REWARD * user.level
        user.cash += reward
        user.energy = config.MAX_ENERGY
        user.energy_updated_at = now_utc()

        note = (
            f"🎉 <b>تبریک، لول {fa_num(user.level)} شدی</b>\n\n"
            f"💰 {money(reward)} جایزه\n"
            f"⚡ انرژی کاملا شارژ شد"
        )

        # چیزایی که با این لول باز میشن
        unlocks: list[str] = []
        unlocks += [f"🌾 {c['name']}" for c in config.SEEDS.values() if c["min_level"] == user.level]
        unlocks += [f"🔪 {w['name']}" for w in config.WEAPONS.values() if w["min_level"] == user.level]
        unlocks += [f"🛡 {a['name']}" for a in config.ARMORS.values() if a["min_level"] == user.level]
        unlocks += [f"🐕 {d['name']}" for d in config.DOGS.values() if d["min_level"] == user.level]
        unlocks += [
            f"🗺 زمین شماره {fa_num(n)}"
            for n, p in config.PLOT_CATALOG.items() if p["min_level"] == user.level and n > 1
        ]
        if user.level == config.TEAM_JOIN_MIN_LEVEL:
            unlocks.append("🏴 عضویت تو تیم")
        if user.level == config.TEAM_CREATE_MIN_LEVEL:
            unlocks.append("🏴 ساخت تیم")
        if unlocks:
            note += "\n\n🔓 آیتم های جدید باز شدن\n\n" + "\n".join(unlocks)

        notes.append(note)

    return notes
