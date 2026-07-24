"""استت‌های نبرد: قدرت حمله و دفاع از آیتم‌ها و سگ‌ها، مصرف‌کننده‌ها: services.battle | پروفایل | کاروان"""

import config
from models import User
from services import dogs as dog_svc


# ───────── استت‌ها ─────────

def _effective_bonus(base: int, user_level: int) -> int:
    """قدرت آیتم با بونس لول کاربر"""
    return int(base * (1 + config.LEVEL_ITEM_BONUS * max(0, user_level - 1)))


def weapon_power(item_keys: list[str], user_level: int) -> int:
    """قدرت موثر بهترین سلاح، مبنای دمیج کاروان"""
    base = max(
        (config.WEAPONS[k]["attack"] for k in item_keys if k in config.WEAPONS), default=0
    )
    return _effective_bonus(base, user_level)


def combat_stats(user: User, item_keys: list[str], dogs: list) -> tuple[int, int]:
    """
    (حمله, دفاع) = پایه بر اساس لول + بهترین سلاح + سگ‌ها / بهترین زره
    بونس شخصیت سگ‌ها داخل dog_attack لحاظ شده، بونس تیم و آب و هوا توی services.battle
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


def best_weapon_key(item_keys: list[str]) -> str | None:
    """کلید بهترین سلاح انبار، نداشت None"""
    owned = [k for k in item_keys if k in config.WEAPONS]
    if not owned:
        return None
    return max(owned, key=lambda k: config.WEAPONS[k]["attack"])


def best_weapon_name(item_keys: list[str]) -> str | None:
    key = best_weapon_key(item_keys)
    return config.WEAPONS[key]["name"] if key else None


def best_armor_name(item_keys: list[str]) -> str | None:
    owned = [k for k in item_keys if k in config.ARMORS]
    if not owned:
        return None
    best = max(owned, key=lambda k: config.ARMORS[k]["defense"])
    return config.ARMORS[best]["name"]


def has_legend_armor(item_keys: list[str]) -> bool:
    """آیا زره افسانه‌ای داره؟، سکه دزدیده‌شده ازش نصف میشه"""
    return any(config.ARMORS.get(k, {}).get("legendary") for k in item_keys)
