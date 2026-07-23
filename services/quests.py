"""
کوئست‌های روزانه بازیکن 📅
هر روز ۲ تا ۳ ماموریت رندوم به‌وقت ایران | ریست هر شب ساعت ۱۲ به‌وقت ایران (تنبل، با اولین تعامل)
جایزه بر اساس سختی کوئست: تی‌پوینت | تجربه | بذر رندوم معمولی
روی خود کاربر ذخیره میشه (dq_date + dq_data) و جدول جدید نمی‌خواد
"""

import json
import random

from sqlalchemy.ext.asyncio import AsyncSession

import config
from models import User
from services.farming import add_seed_stock
from services.users import add_xp
from utils import fa_num, iran_today, money


# ───────── ذخیره و خواندن ─────────

def _load(user: User) -> list[dict]:
    """لیست کوئست‌های ذخیره‌شده روی کاربر، خراب/خالی → لیست خالی"""
    if not user.dq_data:
        return []
    try:
        data = json.loads(user.dq_data)
    except (ValueError, TypeError):
        return []
    return data if isinstance(data, list) else []


def _save(user: User, quests: list[dict]) -> None:
    user.dq_data = json.dumps(quests, ensure_ascii=False)


# ───────── متن‌ها ─────────

def quest_title(q: dict) -> str:
    """عنوان کوئست با عدد هدفش، مثل «انجام 5 حمله»"""
    cfg = config.DAILY_QUESTS[q["kind"]]
    return cfg["title"].format(n=fa_num(q["target"]))


def reward_text(q: dict) -> str:
    """متن جایزه کوئست برای نمایش"""
    r = q["reward"]
    if r["type"] == "tp":
        return money(r["amount"])
    if r["type"] == "xp":
        return f"✨ {fa_num(r['amount'])} تجربه"
    return f"🌱 بذر {config.SEEDS[r['seed']]['name']}"


def remaining(quests: list[dict]) -> int:
    """تعداد کوئست‌های ناتموم"""
    return sum(1 for q in quests if not q["done"])


# ───────── ساخت کوئست‌های روز ─────────

def _roll_reward(kind: str) -> dict:
    """قرعه جایزه بر اساس سختی کوئست، تی‌پوینت | تجربه | بذر"""
    cfg = config.DAILY_QUESTS[kind]
    r = random.random()
    if r < config.DAILY_QUEST_TP_WEIGHT:
        return {"type": "tp", "amount": cfg["tp"]}
    if r < config.DAILY_QUEST_TP_WEIGHT + config.DAILY_QUEST_XP_WEIGHT:
        return {"type": "xp", "amount": cfg["xp"]}
    seeds = [k for k, v in config.SEEDS.items() if not v.get("legendary")]
    return {"type": "seed", "seed": random.choice(seeds), "amount": 1}


async def ensure_quests(session: AsyncSession, user: User) -> list[dict]:
    """
    کوئست‌های امروز کاربر رو بگیر، اگه روز عوض شده باشه از نو می‌سازه
    ریست هر شب ساعت ۱۲ به‌وقت ایران، خودکار با اولین تعامل بعد از نیمه شب
    """
    today = iran_today()
    if user.dq_date == today and _load(user):
        return _load(user)

    kinds = random.sample(
        list(config.DAILY_QUESTS),
        k=random.randint(config.DAILY_QUEST_COUNT_MIN, config.DAILY_QUEST_COUNT_MAX),
    )
    quests = [
        {
            "kind": k,
            "target": config.DAILY_QUESTS[k]["target"],
            "progress": 0,
            "done": False,
            "reward": _roll_reward(k),
        }
        for k in kinds
    ]
    user.dq_date = today
    _save(user, quests)
    return quests


# ───────── ثبت پیشرفت ─────────

async def track(session: AsyncSession, user: User, kind: str, n: int = 1) -> tuple[list[dict], int]:
    """
    ثبت یه رویداد بازی: attack | harvest | mine | plant | search | feed
    خروجی: (کوئست‌های تازه تکمیل‌شده با جایزه اعمال‌شده، تعداد مونده بعدش)
    """
    quests = await ensure_quests(session, user)
    completed: list[dict] = []
    touched = False
    for q in quests:
        if q["kind"] != kind:
            continue
        touched = True
        if q["done"]:
            continue
        q["progress"] = min(q["target"], q["progress"] + n)
        if q["progress"] >= q["target"]:
            q["done"] = True
            notes: list[str] = []
            r = q["reward"]
            if r["type"] == "tp":
                user.cash += r["amount"]
            elif r["type"] == "xp":
                notes = add_xp(user, r["amount"])
            else:
                await add_seed_stock(session, user.id, r["seed"], r["amount"])
            q["notes"] = notes
            completed.append(q)
    if touched:
        _save(user, quests)
    return completed, remaining(quests)
