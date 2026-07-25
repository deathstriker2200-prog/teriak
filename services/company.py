"""
🏭 شرکت: چوب‌بری و کارخانه آهن، تولید خودکار منابع چوب و آهن

تولید lazy حساب میشه: موقع باز کردن صفحه شرکت تیک‌های گذشته واریز میشن
همه اعداد تو config.py ن (FACTORIES | FACTORY_TICK_SECONDS | ...)
"""

from sqlalchemy.ext.asyncio import AsyncSession

import config
from models import User
from services.resources import add_res, take_res
from utils import fa_num, money, now_utc


def factory_level(user: User, fac_key: str) -> int:
    return user.lumber_level if fac_key == "lumber" else user.ironmill_level


def _set_level(user: User, fac_key: str, level: int) -> None:
    if fac_key == "lumber":
        user.lumber_level = level
    else:
        user.ironmill_level = level


def factory_production(fac_key: str, level: int) -> int:
    """تولید هر تیک (۱۰ دقیقه)"""
    return config.FACTORIES[fac_key]["per_tick"] * level


def build_cost(fac_key: str) -> tuple[int, int]:
    """(تی‌پوینت, چوب) ساخت از صفر"""
    return config.FACTORIES[fac_key]["build"]


def upgrade_cost(fac_key: str, to_level: int) -> tuple[int, int]:
    """(تی‌پوینت, چوب) ارتقا به لول to_level"""
    cfg = config.FACTORIES[fac_key]
    return cfg["up_tp"] * to_level, cfg["up_wood"] * to_level


# ───────── تسویه تولید ─────────

async def settle(session: AsyncSession, user: User) -> dict:
    """
    تیک‌های گذشته رو حساب و منابع رو واریز می‌کنه
    خروجی: {"wood":…, "iron":…, "ticks":…} و واریز واقعی با سقف انباره
    """
    now = now_utc()
    if user.company_at is None:
        user.company_at = now
        return {"wood": 0, "iron": 0, "ticks": 0}

    elapsed = int((now - user.company_at).total_seconds())
    ticks = min(elapsed // config.FACTORY_TICK_SECONDS, config.FACTORY_OFFLINE_TICKS)
    if ticks <= 0:
        return {"wood": 0, "iron": 0, "ticks": 0}

    got = {"wood": 0, "iron": 0, "ticks": ticks}
    if user.lumber_level > 0:
        got["wood"] = add_res(user, "wood", factory_production("lumber", user.lumber_level) * ticks)
    if user.ironmill_level > 0:
        got["iron"] = add_res(user, "iron", factory_production("ironmill", user.ironmill_level) * ticks)

    user.company_at = user.company_at + ticks_delta(ticks)
    return got


def ticks_delta(ticks: int):
    from datetime import timedelta
    return timedelta(seconds=ticks * config.FACTORY_TICK_SECONDS)


# ───────── ساخت و ارتقا ─────────

async def build(session: AsyncSession, user: User, fac_key: str) -> tuple[bool, str]:
    cfg = config.FACTORIES[fac_key]
    if factory_level(user, fac_key) > 0:
        return False, f"{cfg['emoji']} {cfg['name']} رو که ساختی"
    tp, wood = build_cost(fac_key)
    if user.cash < tp:
        return False, "❌ تی‌پوینتت کافی نیس"
    if user.wood < wood:
        return False, f"🪵 {fa_num(wood)} چوب می‌خواد و {fa_num(user.wood)} تا داری"
    user.cash -= tp
    take_res(user, "wood", wood)
    _set_level(user, fac_key, 1)
    if user.company_at is None:
        user.company_at = now_utc()
    return True, f"{cfg['emoji']} {cfg['name']} راه اومد"


async def upgrade(session: AsyncSession, user: User, fac_key: str) -> tuple[bool, str]:
    cfg = config.FACTORIES[fac_key]
    cur = factory_level(user, fac_key)
    if cur >= config.FACTORY_MAX_LEVEL:
        return False, "👑 این ساختمان لول مکسه"
    tp, wood = upgrade_cost(fac_key, cur + 1)
    if user.cash < tp:
        return False, "❌ تی‌پوینتت کافی نیس"
    if user.wood < wood:
        return False, f"🪵 {fa_num(wood)} چوب می‌خواد و {fa_num(user.wood)} تا داری"
    user.cash -= tp
    take_res(user, "wood", wood)
    _set_level(user, fac_key, cur + 1)
    return True, f"{cfg['emoji']} {cfg['name']} رفت رو لول {fa_num(cur + 1)}"


# ───────── متن‌ها ─────────

def company_text(user: User, got: dict | None = None) -> str:
    lines = ["<b>🏭 شرکت</b>", ""]
    if got and (got["wood"] or got["iron"]):
        parts = []
        if got["wood"]:
            parts.append(f"🪵 {fa_num(got['wood'])} چوب")
        if got["iron"]:
            parts.append(f"⛏️ {fa_num(got['iron'])} آهن")
        lines.append(f"📥 تولید انباشته: {' + '.join(parts)}")
        lines.append("")

    res_name = {"lumber": "چوب", "ironmill": "آهن"}
    for key, cfg in config.FACTORIES.items():
        lv = factory_level(user, key)
        if lv <= 0:
            lines.append(f"{cfg['emoji']} {cfg['name']} | ساخته نشده")
        else:
            lines.append(
                f"{cfg['emoji']} {cfg['name']} | لول {fa_num(lv)} | "
                f"هر ۱۰ دقیقه {fa_num(factory_production(key, lv))} {res_name[key]}"
            )
    lines.append("")
    lines.append(f"🪵 چوب {fa_num(user.wood)} | ⛏️ آهن {fa_num(user.iron)}")
    return "\n".join(lines)
