"""منطق مزرعه: خرید زمین | کاشت با بذر | برداشت با کولدون | آپگرید"""

from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import config
from models import Plot, SeedStock, User
from services import economy, users
from utils import fa_dur, fa_num, money, now_utc


# ───────── ابزار ─────────

async def get_user_plots(session: AsyncSession, user_id: int) -> list[Plot]:
    q = select(Plot).where(Plot.user_id == user_id).order_by(Plot.id)
    return list((await session.execute(q)).scalars())


async def get_plot(session: AsyncSession, user_id: int, plot_id: int) -> Plot | None:
    q = select(Plot).where(Plot.id == plot_id, Plot.user_id == user_id)
    return (await session.execute(q)).scalar_one_or_none()


async def plots_count(session: AsyncSession, user_id: int) -> int:
    q = select(func.count(Plot.id)).where(Plot.user_id == user_id)
    return (await session.execute(q)).scalar_one()


async def get_stock(session: AsyncSession, user_id: int) -> dict[str, int]:
    """انبار بذر کاربر به شکل دیکشنری: seed_key → تعداد"""
    q = select(SeedStock).where(SeedStock.user_id == user_id)
    return {row.seed_key: row.count for row in (await session.execute(q)).scalars()}


async def add_seed_stock(session: AsyncSession, user_id: int, seed_key: str, amount: int = 1) -> None:
    q = select(SeedStock).where(SeedStock.user_id == user_id, SeedStock.seed_key == seed_key)
    row = (await session.execute(q)).scalar_one_or_none()
    if row:
        row.count += amount
    else:
        session.add(SeedStock(user_id=user_id, seed_key=seed_key, count=amount))


# ───────── خرید زمین (قیمت/زمان ساخت متفاوت برای هرکی + گیت لول) ─────────

async def buy_plot(session: AsyncSession, user: User) -> tuple[bool, str]:
    count = await plots_count(session, user.id)
    if count >= config.MAX_PLOTS:
        return False, "🏡 به سقف 5 زمین رسیدی رفیق"

    n = count + 1
    req_level = economy.plot_required_level(count)
    if user.level < req_level:
        return False, f"🔒 زمین شماره {fa_num(n)} لول {fa_num(req_level)} می‌خواد"

    price = economy.plot_price(count)
    if user.cash < price:
        return False, "❌ تی‌پوینتت کافی نیس رفیق"

    build_sec = economy.plot_build_seconds(count)
    user.cash -= price

    built_at = None if build_sec <= 0 else now_utc() + timedelta(seconds=build_sec)
    session.add(Plot(user_id=user.id, built_at=built_at))

    if build_sec > 0:
        return True, f"🔨 زمین شماره {fa_num(n)} رفت تو کار ساخت — {fa_dur(build_sec)} دیگه تحویلت میشه"
    return True, f"🎉 زمین شماره {fa_num(n)} مالت شد"


# ───────── کاشت (مصرف بذر) ─────────

async def plant(session: AsyncSession, user: User, plot: Plot, seed_key: str) -> tuple[bool, str]:
    seed = config.SEEDS.get(seed_key)
    if not seed:
        return False, "❌ همچین بذری نیس"
    if plot.user_id != user.id:
        return False, "❌ این زمین مال تو نیس"
    state, left = plot.current_status()
    if state == "building":
        return False, f"🔨 زمینت هنوز داره ساخته میشه — {fa_dur(left)} مونده"
    if state != "empty":
        return False, "❌ این زمین الان خالی نیس"
    if not economy.is_seed_unlocked(seed_key, user.level):
        return False, "🔒 این محصول هنوز برات باز نشده"

    stock = await get_stock(session, user.id)
    if stock.get(seed_key, 0) <= 0:
        return False, f"🌾 بذر {seed['name']} نداری — از بخش بذرهای شاپ بخرش"

    await add_seed_stock(session, user.id, seed_key, -1)

    seconds = economy.crop_grow_seconds(seed_key, plot.level)
    plot.status = "growing"
    plot.crop = seed_key
    plot.planted_at = now_utc()
    plot.ready_at = now_utc() + timedelta(seconds=seconds)
    return True, f"🌱 {seed['name']} کاشته شد | {fa_dur(seconds)} دیگه آمادست"


# ───────── برداشت (همه آماده‌ها — هر ۲ دقیقه یه بار) ─────────

def harvest_cooldown_left(user: User) -> int:
    """ثانیه مونده از کولدون برداشت — زمان‌بندی برای هر کاربر جدا ذخیره میشه"""
    if not user.last_harvest_at:
        return 0
    left = config.HARVEST_COOLDOWN_SECONDS - (now_utc() - user.last_harvest_at).total_seconds()
    return max(0, int(left))


async def harvest_all(session: AsyncSession, user: User) -> tuple[bool, str, str | None]:
    """
    برداشت همه زمین‌های آماده
    خروجی: (موفق, پیام کوتاه برای alert, متن اضافه برای نمایش توی مزرعه)
    """
    left = harvest_cooldown_left(user)
    if left:
        return False, f"⏳ هر 2 دقیقه یه بار میشه برداشت کرد | {fa_dur(left)} مونده", None

    plots = await get_user_plots(session, user.id)
    ready = [p for p in plots if p.current_status()[0] == "ready"]
    if not ready:
        return False, "▫️ چیزی آماده برداشت نیس رفیق", None

    total_gain = 0
    total_xp = 0
    names: list[str] = []
    for p in ready:
        if p.crop not in config.SEEDS:
            # بذر قدیمی (از کاتالوگ حذف شده) — زمین خالی میشه بدون درآمد
            p.status = "empty"
            p.crop = None
            p.planted_at = None
            p.ready_at = None
            continue
        gain = economy.crop_yield(p.crop, p.level, user.level)
        total_gain += gain
        total_xp += config.SEEDS[p.crop]["xp"]
        names.append(config.SEEDS[p.crop]["name"])
        p.status = "empty"
        p.crop = None
        p.planted_at = None
        p.ready_at = None

    user.cash += total_gain
    user.last_harvest_at = now_utc()
    notes = users.add_xp(user, total_xp)

    # قلاب کوئست تیم — برداشت هر عضو حساب میشه
    from services import teams as team_svc
    quest_msg = await team_svc.record_harvest(session, user, len(ready))

    extra = (
        f"📦 {' و '.join(names)} برداشت شد و {money(total_gain)} خالص گیرت اومد"
        + (f"\n✨ {fa_num(total_xp)} تجربه" if total_xp else "")
    )
    if quest_msg:
        extra += "\n\n" + quest_msg
    if notes:
        extra += "\n" + "\n".join(notes)
    return True, f"💰 {money(total_gain)}", extra


# ───────── آپگرید ─────────

async def upgrade_plot(session: AsyncSession, user: User, plot: Plot) -> tuple[bool, str]:
    if plot.user_id != user.id:
        return False, "❌ این زمین مال تو نیس"
    if plot.level >= config.PLOT_MAX_LEVEL:
        return False, "⭐ این زمین مکس لوله"

    price = economy.upgrade_price(plot.level)
    if user.cash < price:
        return False, "❌ تی‌پوینتت کافی نیس رفیق"

    user.cash -= price
    plot.level += 1
    return True, f"⬆️ زمین رفت رو لول {fa_num(plot.level)}"
