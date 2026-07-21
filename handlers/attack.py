"""حمله PvP: جستجوی هدف | تایید | اجرا و نتیجه"""

from telegram import Update
from telegram.ext import ContextTypes

import config
from database import session_scope
from handlers.common import parts, respond
from keyboards import keyboards as kb
from models import User
from services import combat, users
from utils import esc, fa_dur, fa_num, money, now_utc


# ───────── خانه حمله ─────────

async def _attack_home_text(session, user) -> str:
    keys = await users.get_item_keys(session, user.id)
    atk, dfn = combat.combat_stats(user, keys)

    text = (
        "<b>⚔️ دزدی از همسایه‌ها</b>\n\n"
        f"💪 حمله تو {fa_num(atk)}\n"
        f"🛡 دفاع تو {fa_num(dfn)}\n\n"
        f"🎯 قربانی فقط تو بازه {fa_num(config.ATTACK_TARGET_LEVEL_RANGE)} لول بالا و پایین خودته\n"
        f"⚡ هر حمله {fa_num(config.ATTACK_ENERGY_COST)} انرژی می‌سوزونه\n"
        f"💰 بردی بین {fa_num(config.STEAL_MIN_PCT * 100)} تا {fa_num(config.STEAL_MAX_PCT * 100)} درصد جیبش مال توئه\n"
        f"💥 باختی {fa_num(config.ATTACK_LOSE_ENERGY)} انرژی اضافه میسوزونی\n"
        f"⏳ بین هر دو حمله {fa_num(config.ATTACK_COOLDOWN_MINUTES)} دقیقه استراحت"
    )

    left = combat.cooldown_left(user)
    if left:
        text += f"\n\n⏳ هنوز {fa_dur(left)} دیگه باید صبر کنی"
    return text


async def attack_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        users.apply_energy_regen(user)
        text = await _attack_home_text(s, user)
        await s.commit()
    await respond(update, text, kb.attack_home_kb())


# ───────── پیدا کردن هدف ─────────

async def find_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        users.apply_energy_regen(user)

        left = combat.cooldown_left(user)
        if left:
            text = await _attack_home_text(s, user)
            await s.commit()
            return await respond(update, text, kb.attack_home_kb(), alert=f"⏳ هنوز {fa_dur(left)} مونده")

        if user.energy < config.ATTACK_ENERGY_COST:
            await s.commit()
            return await attack_cb_no_session(update, alert="⚡ انرژیت کمه رفیق")

        target = await combat.find_target(s, user)
        if not target:
            await s.commit()
            return await attack_cb_no_session(update, alert="🤷 الان کسی تو سطح تو نیس")

        name = esc(users.display_name(target))
        text = (
            "<b>🎯 هدف قفل شد</b>\n\n"
            f"👤 {name}\n"
            f"⭐ لول {fa_num(target.level)}\n"
            f"⚔️ کارنامه {fa_num(target.wins)} برد | {fa_num(target.losses)} باخت\n"
            f"💵 وضعیت جیبش: {combat.cash_bucket(target.cash)}\n\n"
            f"هزینه حمله ⚡ {fa_num(config.ATTACK_ENERGY_COST)} انرژی\n"
            "مطمئنی داداش؟"
        )
        target_id = target.id
        await s.commit()

    await respond(update, text, kb.attack_target_kb(target_id))


async def attack_cb_no_session(update: Update, alert: str) -> None:
    """برگشت به خانه حمله با هشدار"""
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        text = await _attack_home_text(s, user)
        await s.commit()
    await respond(update, text, kb.attack_home_kb(), alert=alert)


# ───────── اجرای حمله ─────────

async def attack_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target_id = int(parts(update)[2])

    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        users.apply_energy_regen(user)

        left = combat.cooldown_left(user)
        if left:
            alert = f"⏳ هنوز {fa_dur(left)} مونده"
            await s.commit()
            return await attack_cb_no_session(update, alert)

        if user.energy < config.ATTACK_ENERGY_COST:
            return await attack_cb_no_session(update, "⚡ انرژیت کمه رفیق")

        target = await s.get(User, target_id)
        if not target or target.id == user.id:
            return await attack_cb_no_session(update, "🤷 هدفت تیک انداخت رفت")

        # استت‌ها
        atk, _ = combat.combat_stats(user, await users.get_item_keys(s, user.id))
        _, dfn = combat.combat_stats(target, await users.get_item_keys(s, target.id))

        # هزینه حمله
        user.energy -= config.ATTACK_ENERGY_COST
        user.last_attack_at = now_utc()

        win, a_roll, d_roll = combat.battle_roll(atk, dfn)
        name = esc(users.display_name(target))
        roll_line = f"🎲 تو {fa_num(a_roll)} | اون {fa_num(d_roll)}"

        if win:
            amount = combat.steal_amount(target.cash)
            target.cash -= amount
            user.cash += amount
            user.wins += 1
            target.losses += 1
            notes = users.add_xp(user, config.ATTACK_WIN_XP)

            steal_line = (
                f"{money(amount)} از جیب {name} خالی کردی"
                if amount else f"جیب {name} خالی بود بدبخت 🕳"
            )
            text = (
                "<b>✅ زدی تو خال داداش</b>\n\n"
                f"{steal_line}\n"
                f"{roll_line}\n"
                f"✨ {fa_num(config.ATTACK_WIN_XP)} تجربه گرفتی"
            )
        else:
            user.losses += 1
            target.wins += 1
            user.energy = max(0, user.energy - config.ATTACK_LOSE_ENERGY)
            notes = users.add_xp(user, config.ATTACK_LOSE_XP)

            text = (
                "<b>❌ له شدی داداش</b>\n\n"
                f"{name} حسابت رو رسوند\n"
                f"{roll_line}\n"
                f"⚡ {fa_num(config.ATTACK_LOSE_ENERGY)} انرژی سوختی\n"
                f"✨ {fa_num(config.ATTACK_LOSE_XP)} تجربه تسلیت"
            )

        if notes:
            text += "\n\n" + "\n".join(notes)

        await s.commit()

    await respond(update, text, kb.attack_result_kb())
