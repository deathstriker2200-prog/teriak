"""حمله پی‌وی کلاسیک ⚔️، شانسی: دکمه 🎯 هدف شانسی می‌زنی، پیش‌نمایش قربانی رو می‌بینی
و بعد یا میزنیش یا هدف دیگه می‌گیری یا برمی‌گردی
سیستم قدیمی: مقایسه قدرت حمله با دفاع حریف و شانس درصدی برد
بعد هر حمله قربانی 12 ساعت مصونیت می‌گیره و از حمله‌های پی‌وی خارج میشه
نبرد HP فقط توی گروه‌ها با دستورهای جنگ انجام میشه، اینجا سیستم جداست"""

from telegram import Update
from telegram.constants import ChatType
from telegram.ext import ContextTypes

import config
from database import session_scope
from handlers.common import parts, respond
from keyboards import keyboards as kb
from models import User
from services import pvattack, users
from utils import esc, fa_num, money

# ───────── متن‌ها ─────────

PV_PANEL_TEXT = (
    "<b>⚔️ حمله پی‌وی</b>\n\n"
    "🎯 دکمه هدف شانسی رو بزن، یه قربانی حوالی لولت برات پیدا می‌کنم\n"
    "👀 قبل از زدن پیش‌نمایش هدف رو می‌بینی، یا میزنیش یا یه هدف دیگه می‌گیری\n"
    "🎲 شانس بردت از مقایسه قدرت حمله تو با دفاع طرف حساب میشه\n"
    "🛡 بعد هر حمله قربانی 12 ساعت مصونیت می‌گیره و از حمله‌های پی‌وی خارج میشه\n\n"
    "⚔️ نبرد واقعی با HP و سلاح فقط توی گروه‌هاست، اونجا دستور جنگ بفرست"
)

NO_TARGET_TEXT = "😴 هدفی حوالی لولت پیدا نشد"

NO_OTHER_TARGET_ALERT = "فعلا هدفی جز این در حوالی لولت پیدا نمیشه"


async def pv_panel(update: Update, alert: str | None = None) -> None:
    """پنل حمله پی‌وی، فقط یه دکمه هدف شانسی داره"""
    await respond(update, PV_PANEL_TEXT, kb.pv_attack_kb(), alert=alert)


async def attack_cb(update: Update, context: ContextTypes.DEFAULT_TYPE, alert: str | None = None) -> None:
    """دکمه ⚔️ حمله منو و دستور /attack | تو پی‌وی پنل باز میشه، تو گروه راهنمای نبرد گروهی"""
    chat = update.effective_chat
    if chat is not None and chat.type != ChatType.PRIVATE:
        from handlers.battle import ATTACK_GUIDE_TEXT
        return await respond(update, ATTACK_GUIDE_TEXT, kb.home_kb(), alert=alert)
    await pv_panel(update, alert=alert)


async def _target_view(s, user: User, victim: User) -> tuple[str, object]:
    """متن و کیبورد پیش‌نمایش هدف، با شانس برد محاسبه‌شده همون لحظه"""
    a_atk, _ = await pvattack.powers(s, user)
    _, t_dfn = await pvattack.powers(s, victim)
    pct = round(pvattack.win_chance(a_atk, t_dfn) * 100)
    name = users.display_name(victim)
    text = (
        "<b>🎯 هدف پیدا شد</b>\n\n"
        f"👤 {esc(name)}\n"
        f"⭐ لول {fa_num(victim.level)}\n"
        f"🎲 شانس برد {fa_num(pct)} درصد\n"
        f"⚡ هزینه حمله {fa_num(config.PV_ATTACK_ENERGY_COST)} انرژی\n\n"
        "می‌زنیش یا یه هدف دیگه می‌خوای؟"
    )
    return text, kb.pv_target_kb(victim.id)


async def target_go_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """🎯 هدف شانسی، یه قربانی پیدا می‌کنه و پیش‌نمایشش رو نشون میده"""
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        users.apply_energy_regen(user)

        victim = await pvattack.pick_random_target(s, user)
        if victim is None:
            await s.commit()
            return await respond(update, NO_TARGET_TEXT, kb.pv_attack_kb())

        text, markup = await _target_view(s, user, victim)
        await s.commit()
    await respond(update, text, markup)


async def target_next_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """🎯 هدف دیگه، هدف فعلی رو کنار می‌ذاره و یه قربانی تازه میاره"""
    target_id = int(parts(update)[2])
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        users.apply_energy_regen(user)

        victim = await pvattack.pick_random_target(s, user, exclude_id=target_id)
        if victim is None:
            cur = await s.get(User, target_id)
            if cur is None:
                await s.commit()
                return await respond(update, NO_TARGET_TEXT, kb.pv_attack_kb())
            # هدف دیگه‌ای نیس، همون پیش‌نمایش قبلی میمونه با یه الرت
            text, markup = await _target_view(s, user, cur)
            await s.commit()
            return await respond(update, text, markup, alert=NO_OTHER_TARGET_ALERT)

        text, markup = await _target_view(s, user, victim)
        await s.commit()
    await respond(update, text, markup)


async def target_back_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """🔙 بازگشت به پنل حمله پی‌وی"""
    await pv_panel(update)


async def target_hit_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """⚔️ حمله روی هدف پیش‌نمایش‌شده، همه چک‌ها دوباره انجام میشه"""
    dq_done, dq_left, uname = [], 0, ""
    target_id = int(parts(update)[2])

    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        users.apply_energy_regen(user)

        victim = await s.get(User, target_id)
        if victim is None:
            await s.commit()
            return await pv_panel(update, alert="🤷 هدف گم شد، یه هدف دیگه بگیر")

        result = await pvattack.execute(s, user, victim)
        name = users.display_name(victim)

        if not result["ok"]:
            await s.commit()
            reason = result["reason"]
            if reason == "shield":
                return await pv_panel(update, alert=f"🛡 «{esc(name)}» الان مصونیت داره")
            if reason == "level":
                return await pv_panel(update, alert="⭐ لولتون دیگه حوالی هم نیس")
            if reason == "energy":
                return await pv_panel(update, alert="⚡ انرژیت برای حمله کمه")
            return await pv_panel(update, alert="🤷 یه مشکلی پیش اومد، دوباره بزن")

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
            f"🛡 «{esc(name)}» تا 12 ساعت از حمله‌های پی‌وی خارج شد"
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
            f"🛡 «{esc(name)}» تا 12 ساعت از حمله‌های پی‌وی خارج شد"
        )

    await respond(update, text, kb.pv_attack_kb())
    from handlers import dquests
    await dquests.announce_completed(update, uname, dq_done, dq_left)
