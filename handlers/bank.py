"""
بانک شخصی 🏦 — «بانک» با دکمه‌های واریز/برداشت | «واریز 1200» | «برداشت 1200»
پول بانک موقع حمله دزدیده نمیشه — واریز/برداشت با دکمه، مبلغ رو با پیام بعدی می‌پرسه
"""

from telegram import Update
from telegram.ext import ContextTypes

import config
from database import session_scope
from handlers.common import respond
from keyboards import keyboards as kb
from services import users
from services import bank as bank_svc
from utils import bar, esc, fa_num, money, parse_amount


def _bank_text(user) -> str:
    cap = bank_svc.bank_capacity(user.bank_level)
    return (
        "<b>🏦 بانک شخصی</b>\n\n"
        f"💰 موجودی بانک {money(user.bank_balance)}\n"
        f"📦 ظرفیت {bar(user.bank_balance, cap)} {fa_num(user.bank_balance)}/{fa_num(cap)}\n"
        f"⭐ لول بانک {fa_num(user.bank_level)}\n\n"
        "🛡 پولی که تو بانکه موقع حمله دزدیده نمیشه — امنه\n\n"
        "💰 واریز با دستور «واریز 1200»\n"
        "💸 برداشت با دستور «برداشت 1200»"
    )


async def render_bank(update: Update, alert: str | None = None, extra: str | None = None) -> None:
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        users.apply_energy_regen(user)
        text = _bank_text(user)
        if extra:
            text += f"\n\n{extra}"
        markup = kb.bank_kb(user)
        await s.commit()
    await respond(update, text, markup, alert=alert)


async def bank_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await render_bank(update)


# ───────── دستورهای متنی «واریز n» / «برداشت n» ─────────

async def _amount_cmd(update: Update, action: str, sample: str) -> int | None:
    """خواندن مبلغ از آخر دستور — نامعتبر/بدون مبلغ → پیام راهنما و None"""
    txt = (update.message.text or "").strip()
    p = txt.split(None, 1)
    amount = parse_amount(p[1]) if len(p) > 1 else None
    if amount is None:
        await respond(update, f"❌ مبلغو درست بگو — مثلا «{sample}»")
    return amount


async def deposit_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    amount = await _amount_cmd(update, "dep", "واریز 1200")
    if amount is None:
        return
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        ok, msg = await bank_svc.deposit(s, user, amount)
        bal, cash = user.bank_balance, user.cash
        await s.commit()
    if not ok:
        return await respond(update, msg)
    await respond(
        update,
        f"<b>{esc(msg)}</b>\n\n🏦 موجودی بانک {money(bal)}\n💵 نقدینگی {money(cash)}",
    )


async def withdraw_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    amount = await _amount_cmd(update, "wd", "برداشت 1200")
    if amount is None:
        return
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        ok, msg = await bank_svc.withdraw(s, user, amount)
        bal, cash = user.bank_balance, user.cash
        await s.commit()
    if not ok:
        return await respond(update, msg)
    await respond(
        update,
        f"<b>{esc(msg)}</b>\n\n💵 نقدینگی {money(cash)}\n🏦 موجودی بانک {money(bal)}",
    )


# ───────── دکمه‌های واریز/برداشت — مبلغ با پیام بعدی ─────────

async def bank_ask_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دکمه 💰 واریز / 💸 برداشت — اکشن معلق می‌ذاره و مبلغ می‌خواد"""
    action = update.callback_query.data.split(":")[1]  # dep | wd
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        if user.pending_action:
            alert = "⏳ اول کار قبلیتو تموم کن یا «لغو» بزن"
            await s.commit()
            return await render_bank(update, alert=alert)
        user.pending_action = "bankdep" if action == "dep" else "bankwd"
        user.pending_value = ""
        await s.commit()

    if action == "dep":
        text = (
            "<b>💰 مبلغ واریز به بانک</b>\n\n"
            "عددشو همینجا بنویس و بفرست — مثلا 1200\n\n"
            "❌ پشیمون شدی بنویس «لغو»"
        )
    else:
        text = (
            "<b>💸 مبلغ برداشت از بانک</b>\n\n"
            "عددشو همینجا بنویس و بفرست — مثلا 1200\n\n"
            "❌ پشیمون شدی بنویس «لغو»"
        )
    await respond(update, text)


# ───────── ارتقای بانک ─────────

async def bank_upgrade_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        if user.bank_level >= config.BANK_MAX_LEVEL:
            await s.commit()
            return await render_bank(update, alert="⭐ بانکت مکس لوله")
        price = bank_svc.bank_upgrade_price(user.bank_level)
        cap_now = bank_svc.bank_capacity(user.bank_level)
        cap_next = bank_svc.bank_capacity(user.bank_level + 1)
        level = user.bank_level
        await s.commit()

    text = (
        f"<b>⬆️ ارتقای بانک — از لول {fa_num(level)} به {fa_num(level + 1)}</b>\n\n"
        f"💸 هزینه {money(price)}\n"
        f"📦 ظرفیت {fa_num(cap_now)} ← {fa_num(cap_next)}\n\n"
        "انجامش بدیم؟"
    )
    await respond(update, text, kb.confirm_kb("cf:bank:up"))


async def bank_upgrade_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        ok, msg = await bank_svc.upgrade_bank(s, user)
        await s.commit()
    if ok:
        return await render_bank(update, alert="⬆️ بانک ارتقا پیدا کرد", extra=msg)
    await render_bank(update, alert=msg)
