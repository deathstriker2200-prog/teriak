"""
جاب‌های زمان‌دار بازی (JobQueue):
آب و هوا هر ۲ ساعت + اعلان به گروه‌های فعال ۱ ساعت اخیر 🌦
بازار سیاه هر ۴ ساعت 📈 | کاروان برای گروه‌های فعال ۲۴ ساعت اخیر 🚛
یورش پلیس هر ۲ ساعت به بازیکنان فعال ۲۴ ساعت اخیر 🚔
"""

import logging
import random
from datetime import timedelta

from telegram.error import BadRequest, Forbidden
from telegram.ext import ContextTypes

import config
from database import session_scope
from keyboards import keyboards as kb
from models import GroupActivity
from services import world as world_svc
from utils import now_utc

logger = logging.getLogger("teriaky.jobs")


async def _send(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str, markup=None) -> None:
    """ارسال امن — گروه ریمووشده/بلاک بی‌صدا رد میشه"""
    try:
        await context.bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
    except (BadRequest, Forbidden):
        pass
    except Exception as e:
        logger.warning("send to %s failed: %s", chat_id, e)


# ───────── آب و هوا 🌦 ─────────

async def weather_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    async with session_scope() as s:
        key, rolled = await world_svc.ensure_weather(s)
        groups = await world_svc.active_group_ids(s, config.WEATHER_GROUP_ACTIVE_HOURS) if rolled else []
        await s.commit()

    if not rolled:
        return
    text = world_svc.weather_announce_text(key)
    for gid in groups:
        await _send(context, gid, text)


# ───────── بازار سیاه 📈 ─────────

async def market_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    async with session_scope() as s:
        await world_svc.ensure_market(s)
        await s.commit()


# ───────── کاروان 🚛 ─────────

async def caravan_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    # ۱) کاروانهای منقضی رو تسویه کن
    for chat_id in list(world_svc.CARAVANS.keys()):
        async with session_scope() as s:
            res = await world_svc.caravan_expire(s, chat_id)
            rewards = res["rewards"] if res else None
            await s.commit()
        if rewards:
            await _send(context, chat_id, world_svc.caravan_end_text(rewards, killed=False))

    # ۲) اسپون جدید برای گروه‌های فعال ۲۴ ساعت اخیر
    async with session_scope() as s:
        groups = await world_svc.active_group_ids(s, config.CARAVAN_GROUP_ACTIVE_HOURS)
        cooldown_limit = now_utc() - timedelta(hours=config.CARAVAN_GROUP_COOLDOWN_HOURS)
        spawns: list[int] = []
        for gid in groups:
            if world_svc.caravan_active(gid):
                continue
            row = await s.get(GroupActivity, gid)
            if row and row.last_caravan_at and row.last_caravan_at > cooldown_limit:
                continue
            # شانس هر تیک: CARAVAN_SPAWN_CHANCE در ساعت → تقسیم بر تعداد تیک هر ساعت
            per_tick = config.CARAVAN_SPAWN_CHANCE * (config.CARAVAN_TICK_SECONDS / 3600)
            if random.random() >= per_tick:
                continue
            if row:
                row.last_caravan_at = now_utc()
            else:
                s.add(GroupActivity(chat_id=gid, last_caravan_at=now_utc()))
            spawns.append(gid)
        await s.commit()

    for gid in spawns:
        cv = world_svc.caravan_spawn(gid)
        await _send(context, gid, world_svc.caravan_board_text(cv), kb.caravan_kb())


# ───────── یورش پلیس 🚔 ─────────

async def police_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    async with session_scope() as s:
        records = await world_svc.police_wave(s)
        await s.commit()

    for rec in records:
        tg = rec["user"].telegram_id
        await _send(context, tg, world_svc.police_report_text(rec))


# ───────── ثبت جاب‌ها ─────────

def register_jobs(app) -> None:
    """ثبت جاب‌های دوره‌ای روی JobQueue — بدون دیپندنسی جاب پاکش میشه"""
    jq = getattr(app, "job_queue", None)
    if jq is None:
        logger.warning("JobQueue available نیس — جاب‌های زمان‌دار غیرفعال شدن (python-telegram-bot[job-queue] نصب کن)")
        return

    jq.run_repeating(weather_job, interval=config.WEATHER_ROLL_SECONDS, first=60, name="weather")
    jq.run_repeating(market_job, interval=config.MARKET_ROLL_SECONDS, first=90, name="market")
    jq.run_repeating(caravan_job, interval=config.CARAVAN_TICK_SECONDS, first=30, name="caravan")
    jq.run_repeating(police_job, interval=config.POLICE_ROLL_SECONDS, first=120, name="police")
    logger.info("جاب‌های زمان‌دار فعال شدن: آب‌وهوا | بازار | کاروان | پلیس")
