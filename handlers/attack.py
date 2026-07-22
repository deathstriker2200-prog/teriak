"""حمله PvP: خانه | جستجوی هدف رندوم | تایید | اجرا — منطق توی services.combat"""

from telegram import Update
from telegram.ext import ContextTypes

import config
from database import session_scope
from handlers.common import format_attack_result, parts, respond
from keyboards import keyboards as kb
from models import User
from services import combat, dogs as dog_svc, users
from utils import esc, fa_dur, fa_num


# ───────── خانه حمله ─────────

async def _attack_home_text(session, user) -> str:
    keys = await users.get_item_keys(session, user.id)
    dogs = await dog_svc.get_user_dogs(session, user.id)
    atk, dfn = combat.combat_stats(user, keys, dogs)

    dog_power = sum(dog_svc.dog_attack(d) for d in dogs)

    text = (
        "<b>⚔️ دزدی از همسایه‌ها</b>\n\n"
        f"💪 حمله تو {fa_num(atk)}"
        + (f" (🐕 {fa_num(dog_power)} از سگ‌ها)" if dog_power else "")
        + f"\n🛡 دفاع تو {fa_num(dfn)}\n\n"
        f"🎯 تو گروه: ریپلای روی پیام طرف و بنویس «حمله»\n"
        f"🎲 اینجا: هدف رندوم تو بازه {fa_num(config.ATTACK_TARGET_LEVEL_RANGE)} لول بالا و پایین خودت\n\n"
        f"⚡ هر حمله {fa_num(config.ATTACK_ENERGY_COST)} انرژی می‌سوزونه\n"
        f"💰 بردی بین {fa_num(config.STEAL_MIN_PCT * 100)} تا {fa_num(config.STEAL_MAX_PCT * 100)} درصد جیبش مال توئه\n"
        f"🐺 گرگ سیاه تا {fa_num(config.RARE_DOG_STEAL_MAX * 100)}٪ غرامت بیشتر می‌گیره و تا {fa_num(config.RARE_DOG_DEF_CUT_MAX * 100)}٪ دفاع طرف رو خرد می‌کنه\n"
        f"🛡 اگه زره افسانه‌ای داشت نصفش میشه\n"
        f"⏳ هر {fa_num(config.ATTACK_COOLDOWN_MINUTES)} دقیقه فقط یه حمله"
    )

    left = combat.cooldown_left(user)
    if left:
        text += f"\n\n⏳ {fa_dur(left)} مونده تا حمله بعدی"
    return text


async def attack_cb(update: Update, context: ContextTypes.DEFAULT_TYPE, alert: str | None = None) -> None:
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        users.apply_energy_regen(user)
        text = await _attack_home_text(s, user)
        await s.commit()
    await respond(update, text, kb.attack_home_kb(), alert=alert)


# ───────── پیدا کردن هدف رندوم ─────────

async def find_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        users.apply_energy_regen(user)

        left = combat.cooldown_left(user)
        if left:
            await s.commit()
            return await attack_cb(update, context, alert=f"⏳ هنوز {fa_dur(left)} مونده")

        if user.energy < config.ATTACK_ENERGY_COST:
            await s.commit()
            return await attack_cb(update, context, alert="⚡ انرژیت کمه")

        target = await combat.find_target(s, user)
        if not target:
            await s.commit()
            return await attack_cb(update, context, alert="🤷 الان کسی تو سطح تو نیس")

        name = esc(users.display_name(target))
        text = (
            "<b>🎯 هدف قفل شد</b>\n\n"
            f"👤 {name}\n"
            f"⭐ لول {fa_num(target.level)}\n"
            f"⚔️ کارنامه {fa_num(target.wins)} برد | {fa_num(target.losses)} باخت\n"
            f"💵 وضعیت جیبش: {combat.cash_bucket(target.cash)}\n\n"
            f"هزینه حمله ⚡ {fa_num(config.ATTACK_ENERGY_COST)} انرژی\n"
            "مطمئنی؟"
        )
        target_id = target.id
        await s.commit()

    await respond(update, text, kb.attack_target_kb(target_id))


# ───────── اجرای حمله ─────────

async def attack_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    target_id = int(parts(update)[2])

    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        users.apply_energy_regen(user)

        target = await s.get(User, target_id)
        if not target:
            return await attack_cb(update, context, "🤷 هدفت تیک انداخت رفت")

        result = await combat.execute_attack(s, user, target)
        target_name = esc(users.display_name(target))
        await s.commit()

    if not result["ok"]:
        msg = (
            f"⏳ هنوز {fa_dur(result['left'])} مونده" if result["reason"] == "cooldown"
            else "⚡ انرژیت کمه"
        )
        return await attack_cb(update, context, alert=msg)

    await respond(update, format_attack_result(result, target_name), kb.attack_result_kb())
