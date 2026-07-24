"""حمله پی‌وی کلاسیک ⚔️: دکمه 🎯 هدف شانسی → پیش‌نمایش قربانی → یا میزنیش یا هدف دیگه می‌گیری
هدف دیگه هزینه‌داره (با لول جست‌وجوگر از 25 تا 1000 تی‌پوینت) و هر حمله 1 دقیقه کولدون داره
قربانی سپر 12 ساعته داشته باشه مهاجم انتخاب داره: با پول بشکنه یا بی‌خیال
بعد حمله، به قربانی تو پی‌وی خبر حمله می‌رسه که چقدر دزدیده شد و چه تجربه کمی گرفت
سیستم قدیمی: مقایسه قدرت حمله با دفاع حریف و شانس درصدی برد
نبرد HP فقط توی گروه‌ها با دستورهای جنگ انجام میشه، اینجا سیستم جداست"""

from telegram import Update
from telegram.constants import ChatType, ParseMode
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
    "🎯 هدف شانسی نزدیک لولت رو پیدا کن\n\n"
    "👀 قبل از حمله مشخصاتش رو می‌بینی و می‌تونی عوضش کنی\n"
    "🎲 نتیجه نبرد بر اساس قدرت حمله و دفاع محاسبه میشه\n"
    "🛡 بعد از حمله حریف مدتی از حمله‌های پی‌وی مصون میشه\n\n"
    "⚔️ نبردهای واقعی با HP فقط داخل گروه‌ها انجام میشن"
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
    """متن و کیبورد پیش‌نمایش هدف، با شانس برد و هزینه هدف دیگه محاسبه‌شده همون لحظه"""
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
    return text, kb.pv_target_kb(victim.id, pvattack.reroll_cost(user.level))


async def target_go_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """🎯 هدف شانسی، یه قربانی پیدا می‌کنه و پیش‌نمایشش رو نشون میده"""
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        users.apply_energy_regen(user)

        cd = pvattack.cooldown_left(user)
        if cd:
            await s.commit()
            return await pv_panel(update, alert=f"⏳ {fa_num(cd)} ثانیه دیگه می‌تونی حمله کنی")

        victim = await pvattack.pick_random_target(s, user)
        if victim is None:
            await s.commit()
            return await respond(update, NO_TARGET_TEXT, kb.pv_attack_kb())

        text, markup = await _target_view(s, user, victim)
        await s.commit()
    await respond(update, text, markup)


async def target_next_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """🎯 هدف دیگه، هزینه‌دار با لول | هدف فعلی رو کنار می‌ذاره و یه قربانی تازه میاره"""
    target_id = int(parts(update)[2])
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        users.apply_energy_regen(user)

        cur = await s.get(User, target_id)
        if cur is None:
            await s.commit()
            return await respond(update, NO_TARGET_TEXT, kb.pv_attack_kb())

        cost = pvattack.reroll_cost(user.level)
        if user.cash < cost:
            text, markup = await _target_view(s, user, cur)
            await s.commit()
            return await respond(update, text, markup, alert="💸 پولت برای هدف دیگه کمه")

        victim = await pvattack.pick_random_target(s, user, exclude_id=target_id)
        if victim is None:
            # هدف دیگه‌ای نیس، پولی هم کم نمیشه، همون پیش‌نمایش میمونه با یه الرت
            text, markup = await _target_view(s, user, cur)
            await s.commit()
            return await respond(update, text, markup, alert=NO_OTHER_TARGET_ALERT)

        user.cash -= cost
        text, markup = await _target_view(s, user, victim)
        await s.commit()
    await respond(update, text, markup)


async def target_back_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """🔙 بازگشت به پنل حمله پی‌وی"""
    await pv_panel(update)


def _victim_text(attacker_name: str, result: dict) -> str:
    """دی‌ام پی‌وی به قربانی: کی حمله کرد، چقدر دزدید/جریمه رفت، تجربه ناچیز"""
    name = esc(attacker_name)
    if result["won"]:
        head = f"⚔️ «{name}» بهت حمله کرد و برد"
        money_line = (f"💰 {money(result['steal'])} ازت دزدید" if result["steal"]
                      else "💰 جیبت خالی بود، چیزی نتونست بدزده")
    else:
        head = f"🛡 «{name}» بهت حمله کرد ولی دفاع کردی"
        money_line = (f"💵 {money(result['penalty'])} جریمه‌ش رسید به جیبت" if result["penalty"]
                      else "💸 جیبش خالی بود، جریمه‌ای گیرت نیومد")
    return (
        "<b>🚨 بهت حمله شد!</b>\n\n"
        f"{head}\n"
        f"{money_line}\n"
        f"✨ {fa_num(result['victim_xp'])} تجربه گرفتی\n\n"
        "🛡 تا 12 ساعت از حمله‌های پی‌وی مصونی"
    )


async def _run_attack(update: Update, context, target_id: int, break_shield: bool = False) -> None:
    """حمله روی هدف پیش‌نمایش‌شده، با کولدون و انتخاب شکستن سپر و دی‌ام قربانی"""
    dq_done, dq_left, uname = [], 0, ""

    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        users.apply_energy_regen(user)

        cd = pvattack.cooldown_left(user)
        if cd:
            await s.commit()
            return await pv_panel(update, alert=f"⏳ {fa_num(cd)} ثانیه دیگه می‌تونی حمله کنی")

        victim = await s.get(User, target_id)
        if victim is None:
            await s.commit()
            return await pv_panel(update, alert="🤷 هدف گم شد، یه هدف دیگه بگیر")

        name = users.display_name(victim)
        sl = pvattack.shield_left(victim)
        if sl and not break_shield:
            await s.commit()
            return await _shield_view_for(update, target_id, name)
        if sl:
            if user.cash < config.PV_ATTACK_SHIELD_BREAK_COST:
                await s.commit()
                return await _shield_view_for(update, target_id, name, alert="💸 پولت برای شکستن سپر کمه")
            user.cash -= config.PV_ATTACK_SHIELD_BREAK_COST
            victim.shield_until = None

        result = await pvattack.execute(s, user, victim)
        if not result["ok"]:
            await s.commit()
            reason = result["reason"]
            if reason == "cooldown":
                return await pv_panel(update, alert=f"⏳ {fa_num(result['left'])} ثانیه دیگه می‌تونی حمله کنی")
            if reason == "level":
                return await pv_panel(update, alert="⭐ لولتون دیگه حوالی هم نیس")
            if reason == "energy":
                return await pv_panel(update, alert="⚡ انرژیت برای حمله کمه")
            return await pv_panel(update, alert="🤷 یه مشکلی پیش اومد، دوباره بزن")

        from services import quests as dq_svc
        dq_done, dq_left = await dq_svc.track(s, user, "attack")
        uname = users.display_name(user)
        victim_tg = victim.telegram_id
        victim_dm = _victim_text(uname, result)
        await s.commit()

    if result["won"]:
        if result["steal"]:
            loot_line = f"💰 {money(result['steal'])} از جیب «{esc(name)}» غارت کردی"
        else:
            loot_line = f"💰 جیب «{esc(name)}» خالی بود"
        text = (
            f"<b>⚔️ بردی!</b>\n\n"
            f"{loot_line}\n"
            f"✨ {fa_num(result['xp'])} تجربه گرفتی"
        )
    else:
        if result["penalty"]:
            lose_line = f"💸 {money(result['penalty'])} از جیبت رفت تو جیبش"
        else:
            lose_line = "💸 جیبت خالی بود، چیزی باخت ندادی"
        text = (
            f"<b>🛡 «{esc(name)}» دفاع کرد، باختی</b>\n\n"
            f"{lose_line}\n"
            f"✨ {fa_num(result['xp'])} تجربه گرفتی"
        )

    await respond(update, text, kb.pv_attack_kb())
    from handlers import dquests
    await dquests.announce_completed(update, uname, dq_done, dq_left)

    # خبر حمله تو پی‌وی قربانی، ربات رو استارت نکرده یا بلاک کرده باشه بی‌خیال
    bot = getattr(context, "bot", None)
    if bot is not None:
        try:
            await bot.send_message(victim_tg, victim_dm, parse_mode=ParseMode.HTML)
        except Exception:
            pass


async def _shield_view_for(update: Update, target_id: int, victim_name: str, alert: str | None = None) -> None:
    """صفحه انتخاب شکستن سپر ۱۲ ساعته قربانی"""
    text = (
        f"<b>🛡 «{esc(victim_name)}» الان سپر داره</b>\n\n"
        f"بعد حمله قبلی {fa_num(config.PV_ATTACK_SHIELD_SECONDS // 3600)} ساعت مصونیت گرفته\n"
        f"💰 شکستنش {money(config.PV_ATTACK_SHIELD_BREAK_COST)} آب می‌خوره\n\n"
        "می‌زنی و می‌شکنیش یا بی‌خیال؟"
    )
    await respond(update, text, kb.pv_break_kb(target_id), alert=alert)


async def target_hit_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """⚔️ حمله روی هدف پیش‌نمایش‌شده"""
    await _run_attack(update, context, int(parts(update)[2]), break_shield=False)


async def target_break_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """💥 شکستن سپر قربانی با پول و اجرای حمله"""
    await _run_attack(update, context, int(parts(update)[2]), break_shield=True)
