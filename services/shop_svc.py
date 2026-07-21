"""منطق خرید فروشگاه — مرکزی برای هندلرهای اینلاین و دستورهای متنی"""

from sqlalchemy.ext.asyncio import AsyncSession

import config
from models import InventoryItem, User
from services import dogs as dog_svc
from services import economy, users
from services.farming import add_seed_stock
from utils import fa_num

# نوع کاتالوگ‌ها برای routing خرید
CATALOGS = {
    "weap": config.WEAPONS,
    "arm": config.ARMORS,
    "seed": config.SEEDS,
}

KIND_EMOJI = {"weap": "🗡", "arm": "🛡", "seed": "🌱", "dog": "🐕"}


async def purchase(
    session: AsyncSession, user: User, kind: str, key: str, dog_name: str | None = None
) -> tuple[bool, str]:
    """
    خرید از هر بخش فروشگاه
    خروجی: (موفق, پیام کوتاه)
    """
    if kind == "dog":
        return await dog_svc.buy_dog(session, user, key, custom_name=dog_name)

    catalog = CATALOGS.get(kind)
    if not catalog:
        return False, "❌ همچین بخشی نیس"

    item = catalog.get(key)
    if not item:
        return False, "❌ همچین جنسی نیس"

    # گیت لول
    min_level = item.get("min_level", 1)
    if user.level < min_level:
        return False, f"🔒 لول {fa_num(min_level)} می‌خواد"

    # سلاح و زره یه بار خرید میشن
    if kind in ("weap", "arm"):
        owned = await users.get_item_keys(session, user.id)
        if key in owned:
            return False, "اینو داری که داداش"

    if user.cash < item["price"]:
        return False, "❌ تی‌پوینتت کافی نیس رفیق"

    user.cash -= item["price"]

    if kind in ("weap", "arm"):
        session.add(InventoryItem(user_id=user.id, item_key=key))
    elif kind == "seed":
        await add_seed_stock(session, user.id, key, 1)

    emoji = KIND_EMOJI.get(kind, "🎉")
    return True, f"{emoji} {item['name']} مالت شد"


def find_shop_item(query: str) -> tuple[str | None, str | None, dict | None]:
    """
    پیدا کردن آیتم از اسم — ترتیب جستجو: سلاح → زره → بذر
    خروجی: (kind, key, item)
    """
    from utils import find_by_name

    for kind, catalog in CATALOGS.items():
        key, item = find_by_name(catalog, query)
        if key:
            return kind, key, item
    return None, None, None
