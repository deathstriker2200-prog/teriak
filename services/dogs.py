"""منطق سگ‌ها: خرید | غذا دادن | لول‌آپ | قدرت"""

import random

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

import config
from models import Dog, User
from utils import fa_num, iran_today, money, normalize_fa, now_utc


def dog_xp_need(level: int) -> int:
    """xp لازم سگ برای رفتن از لول فعلی به بعدی"""
    return int(config.DOG_XP_BASE * (level ** config.DOG_XP_EXP))


def personality_of(dog: Dog) -> dict | None:
    """کانفیگ شخصیت سگ — گرگ سیاه شخصیت نداره"""
    if not dog.personality:
        return None
    return config.DOG_PERSONALITIES.get(dog.personality)


def ensure_personality(dog: Dog) -> None:
    """به سگ‌های قدیمی که شخصیت ندارن یه شخصیت رندوم بده (گرگ سیاه مستثنی)"""
    if dog.personality or config.DOGS.get(dog.dog_key, {}).get("rare"):
        return
    dog.personality = random.choice(list(config.DOG_PERSONALITIES.keys()))


def roll_personality(dog_key: str) -> str | None:
    """شخصیت رندوم موقع خرید — گرگ سیاه با قابلیت‌های خودش می‌مونه"""
    if config.DOGS.get(dog_key, {}).get("rare"):
        return None
    return random.choice(list(config.DOG_PERSONALITIES.keys()))


def dog_attack(dog: Dog) -> int:
    """قدرت حمله سگ با لول و شخصیتش (وفادار +۵٪ | جنگجو +۱۰٪)"""
    cfg = config.DOGS.get(dog.dog_key)
    if not cfg:
        return 0
    atk = cfg["attack"] + cfg["atk_per_level"] * max(0, dog.level - 1)
    per = personality_of(dog)
    if per and per.get("atk_mult"):
        atk = int(atk * (1 + per["atk_mult"]))
    return atk


def personality_steal_bonus(dogs: list[Dog]) -> float:
    """شکارچی 💰 — غرامت جنگی ۸٪+"""
    best = 0.0
    for d in dogs:
        per = personality_of(d)
        if per and per.get("steal_bonus"):
            best = max(best, per["steal_bonus"])
    return best


def personality_steal_cut(dogs: list[Dog]) -> float:
    """نگهبان 🛡 — دزدی از جیبت ۱۰٪−"""
    best = 0.0
    for d in dogs:
        per = personality_of(d)
        if per and per.get("def_steal_cut"):
            best = max(best, per["def_steal_cut"])
    return best


def search_luck(dogs: list[Dog]) -> float:
    """خوش‌شانس 🍀 — شانس جایزه‌های خوب جستجو بیشتر"""
    best = 1.0
    for d in dogs:
        per = personality_of(d)
        if per and per.get("luck"):
            best = max(best, per["luck"])
    return best


def rare_steal_bonus(dogs: list[Dog]) -> float:
    """غرامت بیشتر بهترین گرگ سیاه — تا RARE_DOG_STEAL_MAX (۱۰٪) بر اساس لول"""
    best = 0.0
    for d in dogs:
        if config.DOGS.get(d.dog_key, {}).get("rare"):
            ratio = min(1.0, d.level / config.DOG_MAX_LEVEL)
            best = max(best, ratio * config.RARE_DOG_STEAL_MAX)
    return best


def rare_defense_cut(dogs: list[Dog]) -> float:
    """کاهش دفاع حریف توسط گرگ سیاه — تا RARE_DOG_DEF_CUT_MAX (۳۰٪) بر اساس لول"""
    best = 0.0
    for d in dogs:
        if config.DOGS.get(d.dog_key, {}).get("rare"):
            ratio = min(1.0, d.level / config.DOG_MAX_LEVEL)
            best = max(best, ratio * config.RARE_DOG_DEF_CUT_MAX)
    return best


def rare_ability_lines(dog: Dog) -> list[str]:
    """متن قابلیت گرگ سیاه با اعداد مقیاس لولش — مثل «دفاع حریف رو 18٪ کاهش میده»"""
    if not config.DOGS.get(dog.dog_key, {}).get("rare"):
        return []
    ratio = min(1.0, dog.level / config.DOG_MAX_LEVEL)
    cut = round(ratio * config.RARE_DOG_DEF_CUT_MAX * 100)
    steal = round(ratio * config.RARE_DOG_STEAL_MAX * 100)
    return [
        f"🎖 دفاع حریف رو {fa_num(cut)}٪ کاهش میده",
        f"🪙 غرامت جنگی رو {fa_num(steal)}٪ افزایش میده",
    ]


async def get_user_dogs(session: AsyncSession, user_id: int) -> list[Dog]:
    q = select(Dog).where(Dog.user_id == user_id).order_by(Dog.id)
    dogs = list((await session.execute(q)).scalars())
    for d in dogs:
        ensure_personality(d)
    return dogs


def _check_buyable(user: User, dogs: list[Dog], dog_key: str) -> tuple[bool, str]:
    """چک‌های مشترک خرید سگ (قبل از پرداخت)"""
    cfg = config.DOGS.get(dog_key)
    if not cfg:
        return False, "❌ همچین سگی نیس"
    if any(d.dog_key == dog_key for d in dogs):
        return False, f"تو نژاد {cfg['breed']} رو داری که"
    if len(dogs) >= config.MAX_DOGS:
        return False, f"🐕 بیشتر از {fa_num(config.MAX_DOGS)} سگ نمی‌تونی داشته باشی"
    if user.level < cfg["min_level"]:
        return False, f"🔒 لول {fa_num(cfg['min_level'])} می‌خواد"
    if user.cash < cfg["price"]:
        return False, "❌ تی‌پوینتت کافی نیس"
    return True, ""


async def buy_dog(
    session: AsyncSession, user: User, dog_key: str, custom_name: str | None = None
) -> tuple[bool, str]:
    """خرید مستقیم سگ با اسم مشخص — وقتی اسمشو تو همون دستور داده"""
    dogs = await get_user_dogs(session, user.id)
    ok, alert = _check_buyable(user, dogs, dog_key)
    if not ok:
        return False, alert

    cfg = config.DOGS[dog_key]
    name = (custom_name or cfg["name"])[:32]
    if any(normalize_fa(d.name) == normalize_fa(name) for d in dogs):
        return False, f"❌ یه سگ دیگه اسمش «{name}» ـه — یه اسم دیگه بردار"

    user.cash -= cfg["price"]
    session.add(Dog(
        user_id=user.id,
        dog_key=dog_key,
        name=name,
        breed=cfg["breed"],
        personality=roll_personality(dog_key),
    ))
    return True, f"🐕 {name} شد رفیق جدیدت"


# ───────── فلو دو مرحله‌ای: پرداخت → پرسیدن اسم ─────────

async def hold_dog(session: AsyncSession, user: User, dog_key: str) -> tuple[bool, str]:
    """پرداخت می‌کنه و منتظر اسم می‌مونه — اسم با پیام بعدی کاربر ثبت میشه"""
    if user.pending_action:
        return False, "⏳ اول کار قبلیتو تموم کن یا «لغو» بزن"

    dogs = await get_user_dogs(session, user.id)
    ok, alert = _check_buyable(user, dogs, dog_key)
    if not ok:
        return False, alert

    cfg = config.DOGS[dog_key]
    user.cash -= cfg["price"]
    user.pending_action = "dogname"
    user.pending_value = dog_key
    return True, f"🐕 {cfg['breed']} رو خریدی — حالا اسمشو بفرست"


async def finalize_dog(session: AsyncSession, user: User, name: str) -> tuple[bool, str]:
    """ثبت اسم سگ بعد از پرداخت — سگ با همون اسم ساخته میشه و باهاش صداش می‌زنی"""
    if user.pending_action != "dogname" or not user.pending_value:
        return False, "🤷 خرید سگی در جریان نیس"

    dog_key = user.pending_value
    cfg = config.DOGS.get(dog_key)
    if not cfg:  # محتمل نیس ولی امنیت خوبه
        user.pending_action = None
        user.pending_value = None
        return False, "❌ مشکلی پیش اومد — پولت برگشت"

    clean = normalize_fa(name)
    if not clean or len(clean) < 2:
        return False, "❌ اسم خیلی کوتاهه — یه اسم درست بفرست"
    display = " ".join(str(name).split())  # نیم‌فاصله‌های کاربر حفظ میشه
    if len(display) > 24:
        return False, "❌ اسم حداکثر 24 حرف می‌تونه باشه"
    if ":" in clean or "<" in clean or ">" in clean:
        return False, "❌ تو اسم کاراکتر عجیب نذار"

    dogs = await get_user_dogs(session, user.id)
    if any(normalize_fa(d.name) == clean for d in dogs):
        return False, f"❌ یه سگ دیگه اسمش «{display}» ـه — یه اسم دیگه بفرست"

    user.pending_action = None
    user.pending_value = None
    session.add(Dog(
        user_id=user.id, dog_key=dog_key, name=display, breed=cfg["breed"],
        personality=roll_personality(dog_key),
    ))
    return True, display


async def cancel_pending(session: AsyncSession, user: User) -> str:
    """لغو کار معلق — پول سگ برمی‌گرده | اسم تیم و مبلغ بانک فقط پاک میشن"""
    action = user.pending_action
    if action == "dogname" and user.pending_value in config.DOGS:
        user.cash += config.DOGS[user.pending_value]["price"]
    elif action in ("teamname", "bankdep", "bankwd", "admtp", "admxp"):
        pass  # اینا هنوز پولی جابه‌جا نکردن — فقط اکشن معلق پاک میشه
    else:
        return "🤷 کاری در جریان نیس که"

    user.pending_action = None
    user.pending_value = None
    if action == "dogname":
        return "😅 خرید سگ لغو شد و پولت برگشت"
    return "😅 بی‌خیال شدیم"


def feeds_left(dog: Dog) -> int:
    """سهمیه غذای باقی‌مونده خودِ این سگ — هر روز ساعت ۱۲ شب (به‌وقت ایران) ریست میشه"""
    today = iran_today()
    if dog.feed_day != today:
        dog.feed_day = today
        dog.feeds_today = 0
    return max(0, config.DOG_FEED_PER_DAY - dog.feeds_today)


def full_text(dog: Dog) -> str:
    """متن سیر بودن یه سگ خاص"""
    return f"🍖 {dog.name} امروز حسابی لمبونده دیگه گرسنش نیست"


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
    if feeds_left(dog) <= 0:
        return False, full_text(dog), []
    if dog.level >= config.DOG_MAX_LEVEL:
        return False, f"⭐ {dog.name} مکس لوله", []
    if user.cash < food["price"]:
        return False, "❌ تی‌پوینتت کافی نیس", []

    user.cash -= food["price"]
    dog.feeds_today += 1
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

    msg = f"🍖 {dog.name} {food['name']} رو خورد و {fa_num(food['xp'])} تجربه گرفت"
    return True, msg, notes


async def release_dog(session: AsyncSession, user: User, dog: Dog) -> tuple[bool, str]:
    """رها کردن سگ — برگشتی نداره"""
    if dog.user_id != user.id:
        return False, "❌ این سگ مال تو نیس"
    name = dog.name
    await session.delete(dog)
    return True, f"🕊 {name} رو رها کردی — رفت دنبال زندگیش"


def find_my_dog(dogs: list[Dog], query: str) -> Dog | None:
    """پیدا کردن سگ کاربر با اسم — برای «آمار اصغر»"""
    q = normalize_fa(query)
    if not q:
        return None
    for d in dogs:
        if normalize_fa(d.name) == q:
            return d
    partial = [d for d in dogs if q in normalize_fa(d.name)]
    return partial[0] if len(partial) == 1 else None


def find_dog(query: str):
    """پیدا کردن سگ از کاتالوگ با نژاد — مثل «دوبرمن»"""
    q = normalize_fa(query)
    for key, d in config.DOGS.items():
        if normalize_fa(d["name"]) == q:
            return key, d
    for key, d in config.DOGS.items():
        if q and (q in normalize_fa(d["name"]) or q == normalize_fa(d["breed"])):
            return key, d
    return None, None


def parse_dog_query(query: str):
    """
    پارس «نژاد [اسم دلخواه]» برای خرید متنی
    خروجی: (key, cfg, custom_name یا None)
    مثال: «دوبرمن» → همون نژاد | «دوبرمن رکس» → نژاد دوبرمن با اسم رکس
    """
    q = normalize_fa(query)
    if not q:
        return None, None, None

    # مچ دقیق اسم پیش‌فرض
    for key, d in config.DOGS.items():
        if normalize_fa(d["name"]) == q:
            return key, d, None

    # نژاد + اسم دلخواه — نژادهای چندکلمه‌ای اول چک میشن
    for key, d in sorted(config.DOGS.items(), key=lambda kv: -len(kv[1]["breed"])):
        breed = normalize_fa(d["breed"])
        if q == breed:
            return key, d, None
        if q.startswith(breed + " "):
            custom = q[len(breed) + 1:].strip()
            return key, d, custom or None

    # مچ جزئی روی اسم
    key, cfg = find_dog(q)
    return key, cfg, None
