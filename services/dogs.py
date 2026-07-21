"""منطق سگ‌ها: خرید | غذا دادن | لول‌آپ | قدرت"""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import config
from models import Dog, User
from utils import fa_num, money, normalize_fa, now_utc


def dog_xp_need(level: int) -> int:
    """xp لازم سگ برای رفتن از لول فعلی به بعدی"""
    return int(config.DOG_XP_BASE * (level ** config.DOG_XP_EXP))


def dog_attack(dog: Dog) -> int:
    """قدرت حمله سگ با در نظر گرفتن لولش"""
    cfg = config.DOGS.get(dog.dog_key)
    if not cfg:
        return 0
    return cfg["attack"] + cfg["atk_per_level"] * max(0, dog.level - 1)


def rare_steal_bonus(dogs: list[Dog]) -> float:
    """بونس سرقت بهترین سگ کمیاب — تا RARE_DOG_STEAL_MAX بر اساس لول"""
    best = 0.0
    for d in dogs:
        if config.DOGS.get(d.dog_key, {}).get("rare"):
            ratio = min(1.0, d.level / config.DOG_MAX_LEVEL)
            best = max(best, ratio * config.RARE_DOG_STEAL_MAX)
    return best


async def get_user_dogs(session: AsyncSession, user_id: int) -> list[Dog]:
    q = select(Dog).where(Dog.user_id == user_id).order_by(Dog.id)
    return list((await session.execute(q)).scalars())


async def buy_dog(session: AsyncSession, user: User, dog_key: str) -> tuple[bool, str]:
    """منطق خرید سگ — خروجی: (موفق, پیام)"""
    cfg = config.DOGS.get(dog_key)
    if not cfg:
        return False, "❌ همچین سگی نیس"

    dogs = await get_user_dogs(session, user.id)
    if any(d.dog_key == dog_key for d in dogs):
        return False, f"تو {cfg['name']} رو داری که رفیق"
    if len(dogs) >= config.MAX_DOGS:
        return False, f"🐕 بیشتر از {fa_num(config.MAX_DOGS)} سگ نمی‌تونی داشته باشی"
    if user.level < cfg["min_level"]:
        return False, f"🔒 لول {fa_num(cfg['min_level'])} می‌خواد"
    if user.cash < cfg["price"]:
        return False, "❌ تی‌پوینتت کافی نیس رفیق"

    user.cash -= cfg["price"]
    session.add(Dog(
        user_id=user.id,
        dog_key=dog_key,
        name=cfg["name"],
        breed=cfg["breed"],
    ))
    return True, f"🐕 {cfg['name']} شد رفیق جدیدت"


def feeds_left(user: User) -> int:
    """غذاهای باقی‌مونده امروز — با شروع روز جدید ریست میشه (صدا زدنش state رو عوض می‌کنه ولی نیاز به کامیت داره)"""
    today = now_utc().date().isoformat()
    if user.feed_day != today:
        user.feed_day = today
        user.feeds_used_today = 0
    return max(0, config.DOG_FEED_PER_DAY - user.feeds_used_today)


async def feed_dog(session: AsyncSession, user: User, dog: Dog, food_key: str) -> tuple[bool, str, list[str]]:
    """
    غذا دادن به سگ — هزینه غذا همون لحظه از جیب میره
    خروجی: (موفق, پیام, لیست پیام‌های لول‌آپ)
    """
    food = config.DOG_FOODS.get(food_key)
    if not food:
        return False, "❌ همچین غذایی نیس", []

    if dog.user_id != user.id:
        return False, "❌ این سگ مال تو نیس", []
    if feeds_left(user) <= 0:
        return False, f"🍖 امروز {fa_num(config.DOG_FEED_PER_DAY)} بار غذا دادی داداش — فردا بیا", []
    if dog.level >= config.DOG_MAX_LEVEL:
        return False, f"⭐ {dog.name} مکس لوله", []
    if user.cash < food["price"]:
        return False, "❌ تی‌پوینتت کافی نیس رفیق", []

    user.cash -= food["price"]
    user.feeds_used_today += 1
    dog.xp += food["xp"]

    notes: list[str] = []
    while dog.level < config.DOG_MAX_LEVEL and dog.xp >= dog_xp_need(dog.level):
        dog.xp -= dog_xp_need(dog.level)
        dog.level += 1
        notes.append(
            f"🆙 {dog.name} رفت رو لول {fa_num(dog.level)} و الان {fa_num(dog_attack(dog))} قدرت داره"
        )
    if dog.level >= config.DOG_MAX_LEVEL:
        dog.xp = 0

    msg = f"🍖 {dog.name} {food['name']} رو پس داد و {fa_num(food['xp'])} ایکس‌پی گرفت"
    return True, msg, notes


def find_dog(query: str):
    """پیدا کردن سگ از کاتالوگ با اسم — مثل «دوبرمن اصغر»"""
    q = normalize_fa(query)
    for key, d in config.DOGS.items():
        if normalize_fa(d["name"]) == q:
            return key, d
    for key, d in config.DOGS.items():
        if q and (q in normalize_fa(d["name"]) or q == normalize_fa(d["breed"])):
            return key, d
    return None, None
