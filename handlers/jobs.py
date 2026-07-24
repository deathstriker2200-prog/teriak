"""
جاب‌های زمان‌دار بازی (JobQueue):
آب و هوا هر ۲ ساعت + اعلان به گروه‌های فعال ۱ ساعت اخیر 🌦
بازار سیاه هر ۴ ساعت 📈 | کاروان برای گروه‌های فعال ۲۴ ساعت اخیر 🚛 (بردش هر ۲ دقیقه رفرش میشه)
یورش پلیس هر ۲ ساعت به بازیکنان فعال ۲۴ ساعت اخیر 🚔
نبض انرژی هر ۵ دقیقه به همه کاربرا (یه کوئری دسته‌جمعی، بدون حلقه تک‌تک) ⚡
"""

import logging
import random
from datetime import timedelta

from sqlalchemy import update as sql_update
from telegram.error import BadRequest, Forbidden
from telegram.ext import ContextTypes

import config
from database import session_scope
from keyboards import keyboards as kb
from models import GroupActivity, User
from services import world as world_svc
from utils import now_utc

logger = logging.getLogger("teriaky.jobs")


async def _send(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str, markup=None):
    """ارسال امن، پیام فرستاده‌شده رو برمی‌گردونه (گروه ریموو/بلاک None)"""
    try:
        return await context.bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=markup)
    except (BadRequest, Forbidden):
        return None
    except Exception as e:
        logger.warning("send to %s failed: %s", chat_id, e)
        return None


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


# ───────── نبض انرژی ⚡ ─────────

def _energy_pulse_stmt():
    """UPDATE دسته‌جمعی: min(انرژی + نبض, سقف) برای همه کاربرای زیر سقف"""
    from sqlalchemy import case
    return (
        sql_update(User)
        .where(User.energy < config.MAX_ENERGY)
        .values(energy=case(
            (User.energy + config.ENERGY_PULSE_AMOUNT > config.MAX_ENERGY, config.MAX_ENERGY),
            else_=User.energy + config.ENERGY_PULSE_AMOUNT,
        ))
    )


async def energy_pulse_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """هر ۵ دقیقه ۲۰ انرژی به همه کاربرا، یه کوئری دسته‌جمعی که سرور سنگین نشه"""
    async with session_scope() as s:
        await s.execute(_energy_pulse_stmt())
        await s.commit()


# ───────── کاروان 🚛 ─────────

async def caravan_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    # ۱) کاروانهای منقضی رو تسویه کن، بردشون پاک میشه و پیام «رد شد» تازه میاد
    for chat_id in list(world_svc.CARAVANS.keys()):
        cv = world_svc.CARAVANS.get(chat_id)
        mid = cv.get("message_id") if cv else None
        async with session_scope() as s:
            res = await world_svc.caravan_expire(s, chat_id)
            await s.commit()
        if res is not None:
            if mid:
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=mid)
                except (BadRequest, Forbidden):
                    pass
            await _send(context, chat_id, world_svc.caravan_end_text(res["rewards"], killed=False))

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
        msg = await _send(context, gid, world_svc.caravan_board_text(cv), kb.caravan_kb())
        if msg:
            cv["message_id"] = msg.message_id


async def caravan_refresh_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """برد کاروان فقط با این تایمر رفرش میشه (نه بعد هر ضربه)، دمیج‌ها رو تازه می‌کنه"""
    for chat_id, cv in list(world_svc.CARAVANS.items()):
        if world_svc.caravan_active(chat_id) is None:
            continue
        mid = cv.get("message_id")
        if not mid:
            continue
        try:
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=mid,
                text=world_svc.caravan_board_text(cv), parse_mode="HTML",
                reply_markup=kb.caravan_kb(),
            )
        except BadRequest:
            pass
        except Exception as e:
            logger.debug("رفرش برد کاروان %s خطا: %s", chat_id, e)


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
    """ثبت جاب‌های دوره‌ای روی JobQueue، بدون دیپندنسی جاب پاکش میشه"""
    jq = getattr(app, "job_queue", None)
    if jq is None:
        logger.warning("JobQueue available نیس، جاب‌های زمان‌دار غیرفعال شدن (python-telegram-bot[job-queue] نصب کن)")
        return

    jq.run_repeating(weather_job, interval=config.WEATHER_ROLL_SECONDS, first=60, name="weather")
    jq.run_repeating(market_job, interval=config.MARKET_ROLL_SECONDS, first=90, name="market")
    jq.run_repeating(caravan_job, interval=config.CARAVAN_TICK_SECONDS, first=30, name="caravan")
    jq.run_repeating(caravan_refresh_job, interval=config.CARAVAN_BOARD_REFRESH_SECONDS, first=60, name="caravan-board")
    jq.run_repeating(police_job, interval=config.POLICE_ROLL_SECONDS, first=120, name="police")
    jq.run_repeating(energy_pulse_job, interval=config.ENERGY_PULSE_SECONDS, first=config.ENERGY_PULSE_SECONDS, name="energy-pulse")
    logger.info("جاب‌های زمان‌دار فعال شدن: آب‌وهوا | بازار | کاروان | برد کاروان | پلیس | نبض انرژی")
