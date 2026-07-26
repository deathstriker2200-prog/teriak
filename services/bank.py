"""
منطق بانک شخصی 🏦
پولی که تو بانکه موقع حمله دزدیده نمیشه، ظرفیت بانک با لولش زیاد میشه
و هر لول بانک حداقل لول بازیکن خودشو می‌خواد
"""

from sqlalchemy.ext.asyncio import AsyncSession

import config
from models import User
from utils import fa_num, money


# ───────── فرمول‌ها ─────────

def bank_capacity(level: int) -> int:
    """ظرفیت بانک بر اساس لولش، جدول ثابت"""
    lv = min(max(level, 1), config.BANK_MAX_LEVEL)
    return config.BANK_CAPS[lv - 1]


def bank_upgrade_price(level: int) -> int:
    """هزینه ارتقا از لول فعلی به لول بعد، جدول رند قیمت"""
    lv = min(max(level, 1), config.BANK_MAX_LEVEL)
    return config.BANK_UPGRADE_PRICES[lv - 1]


def bank_min_level(level: int) -> int:
    """حداقل لول بازیکن برای داشتن این لول بانک"""
    lv = min(max(level, 1), config.BANK_MAX_LEVEL)
    return config.BANK_MIN_LEVELS[lv - 1]


# ───────── عملیات ─────────

async def deposit(session: AsyncSession, user: User, amount: int) -> tuple[bool, str]:
    """واریز از جیب به بانک، تا سقف ظرفیت"""
    if amount <= 0:
        return False, "❌ مبلغو درست بگو، مثلا «تریاکی واریز 1200»"
    if user.cash < amount:
        return False, f"❌ این همه پول نقد نداری، جیبت {money(user.cash)} ـه"
    cap = bank_capacity(user.bank_level)
    if user.bank_balance + amount > cap:
        room = max(0, cap - user.bank_balance)
        if room <= 0:
            return False, "🏦 بانکت پره دیگه، اول ارتقاش بده «تریاکی بانک»"
        return False, f"🏦 ظرفیت بانکت تا {money(cap)} ـه، فقط {money(room)} جا داره"
    user.cash -= amount
    user.bank_balance += amount
    return True, f"🏦 {money(amount)} رفت تو بانک، امنه از هر دزدی 🛡"


async def withdraw(session: AsyncSession, user: User, amount: int) -> tuple[bool, str]:
    """برداشت از بانک به جیب"""
    if amount <= 0:
        return False, "❌ مبلغو درست بگو، مثلا «تریاکی برداشت 1200»"
    if user.bank_balance < amount:
        return False, f"❌ تو بانک این همه نداری، موجودیت {money(user.bank_balance)} ـه"
    user.bank_balance -= amount
    user.cash += amount
    return True, f"💸 {money(amount)} اومد تو جیبت"


async def upgrade_bank(session: AsyncSession, user: User) -> tuple[bool, str]:
    """ارتقای لول بانک، هر لول یه حداقل سطح بازیکن می‌خواد"""
    if user.bank_level >= config.BANK_MAX_LEVEL:
        return False, "⭐ بانکت مکس لوله"
    next_level = user.bank_level + 1
    req = bank_min_level(next_level)
    if user.level < req:
        return False, f"🔒 برای بانک لول {fa_num(next_level)} خودت باید لول {fa_num(req)} باشی"
    price = bank_upgrade_price(user.bank_level)
    if user.cash < price:
        return False, f"❌ ارتقا {money(price)} هزینه داره و پولت کمه"
    user.cash -= price
    user.bank_level = next_level
    return True, (
        f"⬆️ بانکت رفت رو لول {fa_num(next_level)}\n"
        f"🏦 ظرفیت جدید {money(bank_capacity(next_level))}"
    )
