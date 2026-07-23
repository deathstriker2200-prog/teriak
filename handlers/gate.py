"""
گیت عضویت اجباری 🔒
توی گروه -3 رجیستر میشه (قبل از قفل مالکیت و همه دستورها) ولی فقط روی پی‌وی ربات
داخل گروه همه‌چی مثل قبل عادی کار می‌کنه و چک عضویت انجام نمیشه
کاربر عضو کانال نباشه دستور پی‌وی‌اش بلاک میشه و پیام گیت با دکمه‌های عضویت/تایید می‌گیره
آپدیت بلاک‌شده توی حافظه نگه داشته میشه تا بعد «تایید عضویت» خودشش ادامه پیدا کنه
"""

import logging
import time

from telegram import Update
from telegram.ext import ApplicationHandlerStop, ContextTypes

import config
from database import session_scope
from keyboards import keyboards as kb
from services import forcejoin as fj

logger = logging.getLogger("teriaky.gate")

# user_id → آپدیت بلاک‌شده (هر نفر آخرین دستوری که بلاک شده)
PENDING: dict[int, Update] = {}
# user_id → timestamp آخرین پیام گیت (آنتی‌اسپم برای کالبک‌ها)
_LAST_GATE: dict[int, float] = {}


def _skip(update: Update) -> bool:
    u = update.effective_user
    return u is None or getattr(u, "is_bot", False) or u.id in config.ADMIN_IDS


def _in_pv(update: Update) -> bool:
    """گیت فقط توی پی‌وی ربات اعمال میشه، گروه‌ها آزادن"""
    chat = update.effective_chat
    return chat is not None and chat.type == "private"


async def _settings_and_member(context, user_id: int) -> tuple[dict, bool]:
    """ستینگ فعال + عضویت، غیرفعال باشه (False, {}) نیس همیشه pass"""
    async with session_scope() as s:
        st = await fj.get_settings(s)
        await s.commit()
    if not (st["on"] and st["channel"]):
        return st, True
    return st, await fj.is_member(context.bot, st["channel"], user_id)


async def gate_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """متن‌ها و کامندهای پی‌وی قبل از هر هندلری از اینجا رد میشن"""
    if _skip(update) or not _in_pv(update):
        return
    st, member = await _settings_and_member(context, update.effective_user.id)
    if member:
        return

    PENDING[update.effective_user.id] = update
    if update.message:
        await update.message.reply_html(fj.gate_text(), reply_markup=kb.force_join_kb(st["link"]))
    raise ApplicationHandlerStop()


async def gate_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دکمه‌های پی‌وی هم گیت میشن (بجز خود دکمه تایید که هندلر جدا داره و زودتر رجیستر شده)"""
    if not update.callback_query or _skip(update) or not _in_pv(update):
        return
    st, member = await _settings_and_member(context, update.effective_user.id)
    if member:
        return

    uid = update.effective_user.id
    PENDING[uid] = update
    await update.callback_query.answer(
        "🔒 اول توی کانال عضو شو، بعد «✅ تایید عضویت» رو بزن", show_alert=True,
    )
    # پیام گیت با دکمه لینک فقط یه بار هر چند لحظه، که گروه اسپم نشه
    now = time.monotonic()
    if now - _LAST_GATE.get(uid, 0) > config.FORCE_JOIN_STALE_SECONDS:
        _LAST_GATE[uid] = now
        try:
            await context.bot.send_message(
                update.effective_chat.id, fj.gate_text(),
                parse_mode="HTML", reply_markup=kb.force_join_kb(st["link"]),
            )
        except Exception as e:
            logger.debug("فرستادن پیام گیت %s: %s", uid, e)
    raise ApplicationHandlerStop()


async def gate_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """«✅ تایید عضویت»، اگه عضو شده باشه ادامه همون دستور بلاک‌شده اجرا میشه"""
    q = update.callback_query
    async with session_scope() as s:
        st = await fj.get_settings(s)
        await s.commit()

    if not st["channel"]:
        await q.answer("عضویت اجباری غیرفعاله ✅")
        try:
            await q.edit_message_text("✅ عضویت اجباری خاموشه، دستورت رو دوباره بزن")
        except Exception:
            pass
        return

    member = True
    if st["on"]:
        member = await fj.is_member(context.bot, st["channel"], update.effective_user.id)

    if not member:
        await q.answer("❌ هنوز عضو کانال نشدی، اول عضو شو بعد دوباره تایید رو بزن", show_alert=True)
        return

    await q.answer("✅ عضویتت تایید شد")
    try:
        await q.edit_message_text("✅ <b>عضویتت تایید شد، خوش اومدی</b> 🌹", parse_mode="HTML")
    except Exception:
        pass

    uid = update.effective_user.id
    pending_update = PENDING.pop(uid, None)
    if pending_update is None:
        return
    # ادامه همون دستوری که بلاک شده بود از نو دیسپچ میشه
    try:
        await context.application.process_update(pending_update)
    except Exception as e:
        logger.warning("ادامه دستور بلاک‌شده %s خطا: %s", uid, e)
