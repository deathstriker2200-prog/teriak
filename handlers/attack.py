"""
حمله پی‌وی کلاسیک ⚔️، منوی ⚔️ حمله، ‎/attack و دستورهای متنی تو پی‌وی
سیستم قدیمی: لیست هدف‌های ±۲ لول با شانس درصدی، بعد هر حمله قربانی 12 ساعت مصونیت می‌گیره
نبرد HP فقط توی گروه‌هاست، اینجا سیستم جدا داره
"""

from telegram import Update
from telegram.constants import ChatType
from telegram.ext import ContextTypes

import config
from database import session_scope
from handlers.common import parts, respond
from keyboards import keyboards as kb
from services import pvattack, users
from utils import esc, fa_num, money

# ───────── متن‌ها ─────────

PANEL_HEADER = "<b>⚔️ لیست حمله</b>"

PANEL_FOOTER = (
    "بعد هر حمله قربانی 12 ساعت از لیست خارج میشه\n"
    "برای نبرد HP با بند و بساط کامل برو توی گروه‌ها سراغ حریفت"
)

PANEL_EMPTY_TEXT = (
    f"{PANEL_HEADER}\n\n"
    "😴 فعلا هدفی حوالی لولت پیدا نشد\n"
    "یه کم دیگه کنده کاری کن و برگرد"
)


def _target_line(u, chance: float) -> str:
    pct = round(chance * 100)
    return f"🎯 {esc(users.display_name(u))} | لول {fa_num(u.level)} | شانس {fa_num(pct)} درصد"


async def _gather(session, user):
    """لیست هدف‌ها + شانس هرکدوم"""
    targets = await pvattack.find_targets(session, user)
    a_atk, _ = await pvattack.powers(session, user)
    out = []
    for t in targets:
        _, t_dfn = await pvattack.powers(session, t)
        out.append((t, pvattack.win_chance(a_atk, t_dfn)))
    return out


# ───────── پنل لیست ─────────

async def pv_panel(update: Update, alert: str | None = None) -> None:
    """لیست حمله پی‌وی، نقطه ورود منو و دستورهای متنی پی‌وی"""
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        users.apply_energy_regen(user)
        rows = await _gather(s, user)
        await s.commit()

    if not rows:
        return await respond(update, PANEL_EMPTY_TEXT, kb.pv_attack_kb([]), alert=alert)

    lines = [PANEL_HEADER, ""]
    lines += [_target_line(u, ch) for u, ch in rows]
    lines += ["", PANEL_FOOTER]
    await respond(update, "\n".join(lines), kb.pv_attack_kb([u for u, _ in rows]), alert=alert)


async def attack_cb(update: Update, context: ContextTypes.DEFAULT_TYPE, alert: str | None = None) -> None:
    """دکمه ⚔️ حمله منو و دستور /attack | تو پی‌وی لیست باز میشه، تو گروه راهنمای نبرد گروهی"""
    chat = update.effective_chat
    if chat is not None and chat.type != ChatType.PRIVATE:
        from handlers.battle import ATTACK_GUIDE_TEXT
        return await respond(update, ATTACK_GUIDE_TEXT, kb.home_kb(), alert=alert)
    await pv_panel(update, alert=alert)


async def panel_refresh_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """🔄 رفرش لیست حمله"""
    await pv_panel(update)


# ───────── تایید و اجرا ─────────

async def target_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """انتخاب هدف از لیست، صفحه تایید با شانس برد"""
    tg_id = int(parts(update)[2])
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        victim = await users.get_by_tg(s, tg_id)

        if victim is None:
            await s.commit()
            return await pv_panel(update, alert="🤷 اینو پیدا نکردم")

        sl = pvattack.shield_left(victim)
        if sl:
            name = users.display_name(victim)
            await s.commit()
            return await pv_panel(update, alert=f"🛡 «{name}» هنوز تو مصونیته")

        if abs(victim.level - user.level) > config.PV_ATTACK_LEVEL_RANGE:
            name = users.display_name(victim)
            await s.commit()
            return await pv_panel(update, alert=f"🎯 «{name}» دیگه تو رنج لولت نیس")

        a_atk, _ = await pvattack.powers(s, user)
        _, t_dfn = await pvattack.powers(s, victim)
        chance = pvattack.win_chance(a_atk, t_dfn)
        name = users.display_name(victim)
        victim_level = victim.level
        await s.commit()

    pct = round(chance * 100)
    text = (
        f"<b>⚔️ حمله به «{esc(name)}»</b>\n\n"
        f"🎯 لول {fa_num(victim_level)}\n"
        f"🎲 شانس برد {fa_num(pct)} درصد\n"
        f"⚡ هزینه {fa_num(config.PV_ATTACK_ENERGY_COST)} انرژی\n"
        f"🛡 بعد حمله طرف 12 ساعت مصونیت می‌گیره\n\n"
        "می‌زنی؟"
    )
    await respond(update, text, kb.confirm_kb(f"cf:patt:x:{tg_id}"))


async def execute_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """تایید نهایی حمله پی‌وی"""
    tg_id = int(parts(update)[3])
    dq_done, dq_left, uname = [], 0, ""

    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        users.apply_energy_regen(user)
        victim = await users.get_by_tg(s, tg_id)

        if victim is None:
            await s.commit()
            return await pv_panel(update, alert="🤷 اینو پیدا نکردم")

        result = await pvattack.execute(s, user, victim)
        name = users.display_name(victim)

        if not result["ok"]:
            await s.commit()
            reason = result["reason"]
            if reason == "shield":
                return await pv_panel(update, alert=f"🛡 «{name}» هنوز تو مصونیته")
            if reason == "level":
                return await pv_panel(update, alert=f"🎯 «{name}» دیگه تو رنج لولت نیس")
            if reason == "energy":
                return await pv_panel(update, alert="⚡ انرژیت برای حمله کمه")
            return await pv_panel(update, alert="😅 خودتو نزن رفیق")

        from services import quests as dq_svc
        dq_done, dq_left = await dq_svc.track(s, user, "attack")
        uname = users.display_name(user)
        await s.commit()

    if result["won"]:
        if result["steal"]:
            loot_line = f"💰 {money(result['steal'])} از جیب «{esc(name)}» غارت کردی"
        else:
            loot_line = f"💰 جیب «{esc(name)}» خالی بود"
        text = (
            f"<b>⚔️ بردی!</b>\n\n"
            f"{loot_line}\n"
            f"✨ {fa_num(result['xp'])} تجربه گرفتی\n"
            f"🛡 «{esc(name)}» تا 12 ساعت از لیست حمله خارج شد"
        )
    else:
        if result["penalty"]:
            lose_line = f"💸 {money(result['penalty'])} از جیبت رفت تو جیبش"
        else:
            lose_line = "💸 جیبت خالی بود، چیزی باخت ندادی"
        text = (
            f"<b>🛡 «{esc(name)}» دفاع کرد، باختی</b>\n\n"
            f"{lose_line}\n"
            f"✨ {fa_num(result['xp'])} تجربه گرفتی\n"
            f"🛡 «{esc(name)}» تا 12 ساعت از لیست حمله خارج شد"
        )

    await respond(update, text, kb.pv_attack_result_kb())
    from handlers import dquests
    await dquests.announce_completed(update, uname, dq_done, dq_left)
