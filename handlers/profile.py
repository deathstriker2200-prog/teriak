"""پروفایل کاربر — نسخه متنی برای منو و نسخه کامل با عکس تلگرام برای دستور"""

from telegram import Update
from telegram.ext import ContextTypes

import config
from database import session_scope
from handlers.common import respond
from keyboards import keyboards as kb
from services import combat, dogs as dog_svc, economy, farming, users
from utils import esc, fa_num, money, money_tp


async def _profile_text(session, user) -> str:
    item_keys = await users.get_item_keys(session, user.id)
    user_dogs = await dog_svc.get_user_dogs(session, user.id)
    atk, dfn = combat.combat_stats(user, item_keys, user_dogs)
    plots = await farming.get_user_plots(session, user.id)

    name = esc(users.display_name(user))
    username = f"@{esc(user.username)}" if user.username else "بدون یوزرنیم"

    growing = sum(1 for p in plots if p.current_status()[0] == "growing")
    ready = sum(1 for p in plots if p.current_status()[0] == "ready")

    weapon = combat.best_weapon_name(item_keys) or "دست خالی"
    armor = combat.best_armor_name(item_keys) or "بدون زره"

    return (
        "<b>🏠 پروفایل</b>\n\n"
        f"👤 {name}\n"
        f"🆔 {username}\n"
        f"⭐ لول {fa_num(user.level)}\n"
        f"✨ تجربه {fa_num(user.xp)} از {fa_num(economy.xp_need(user.level))}\n"
        f"🪙 {money(user.cash)}\n"
        f"⚡ انرژی {fa_num(user.energy)} از {fa_num(config.MAX_ENERGY)}\n"
        f"🌱 زمین‌ها {fa_num(len(plots))} تا | 🌾 در حال رشد {fa_num(growing)} | ✅ آماده {fa_num(ready)}\n\n"
        f"💪 قدرت حمله {fa_num(atk)}\n"
        f"🛡 دفاع {fa_num(dfn)}\n"
        f"🔪 {esc(weapon)} | 🛡 {esc(armor)}\n"
        f"🐕 سگ‌ها {fa_num(len(user_dogs))} تا\n"
        f"⚔️ برد {fa_num(user.wins)} | ❌ باخت {fa_num(user.losses)}"
    )


async def _caption_text(session, user) -> str:
    """نسخه فشرده برای کپشن عکس — زیر ۱۰۲۴ کاراکتر"""
    item_keys = await users.get_item_keys(session, user.id)
    user_dogs = await dog_svc.get_user_dogs(session, user.id)
    atk, dfn = combat.combat_stats(user, item_keys, user_dogs)
    plots = await farming.get_user_plots(session, user.id)

    name = esc(users.display_name(user))
    weapon = combat.best_weapon_name(item_keys) or "—"
    armor = combat.best_armor_name(item_keys) or "—"
    ready = sum(1 for p in plots if p.current_status()[0] == "ready")

    dogs_line = " | ".join(
        f"{d.name} (لول {fa_num(d.level)})" for d in user_dogs
    ) or "—"

    return (
        f"<b>🏠 {name}</b>\n\n"
        f"⭐ لول {fa_num(user.level)} | ✨ {fa_num(user.xp)}/{fa_num(economy.xp_need(user.level))}\n"
        f"🪙 {money(user.cash)}\n"
        f"💪 حمله {fa_num(atk)} | 🛡 دفاع {fa_num(dfn)}\n"
        f"🌱 زمین‌ها {fa_num(len(plots))} | ✅ آماده {fa_num(ready)}\n"
        f"🔪 {esc(weapon)} | 🛡 {esc(armor)}\n"
        f"🐕 {dogs_line}\n"
        f"⚔️ {fa_num(user.wins)} برد | {fa_num(user.losses)} باخت"
    )


# ───────── نمایش از منوی اینلاین (متنی) ─────────

async def profile_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        users.apply_energy_regen(user)
        text = await _profile_text(s, user)
        await s.commit()
    await respond(update, text, kb.profile_kb())


# ───────── دستور «پروفایل» و /profile — با عکس پروفایل تلگرام ─────────

async def profile_photo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        users.apply_energy_regen(user)
        caption = await _caption_text(s, user)
        tg_id = user.telegram_id
        await s.commit()

    file_id = None
    try:
        photos = await context.bot.get_user_profile_photos(tg_id, limit=1)
        if photos and photos.total_count:
            file_id = photos.photos[0][-1].file_id  # بزرگ‌ترین سایز
    except Exception:
        file_id = None  # سلب دسترسی یا خطا — میریم رو حالت متنی

    if file_id:
        await update.effective_message.reply_photo(
            photo=file_id,
            caption=caption,
            parse_mode="HTML",
            reply_markup=kb.main_menu_kb(),
        )
    else:
        await update.effective_message.reply_html(caption, reply_markup=kb.main_menu_kb())


# /profile همین نسخه عکس‌دار رو اجرا می‌کنه
profile_cmd = profile_photo_cmd
