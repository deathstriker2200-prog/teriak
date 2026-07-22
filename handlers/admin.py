"""پنل ساده ادمین — دادن پول و XP به خودت (/admin)"""

from telegram import Update
from telegram.ext import ContextTypes

import config
from database import session_scope
from handlers.common import parts, respond
from keyboards import keyboards as kb
from services import economy, users
from utils import fa_num, money


def _is_admin(update: Update) -> bool:
    return bool(update.effective_user) and update.effective_user.id in config.ADMIN_IDS


def _panel_text(user, extra: str | None = None) -> str:
    text = (
        "<b>👑 پنل ادمین</b>\n\n"
        f"💵 {money(user.cash)}\n"
        f"⭐ لول {fa_num(user.level)} | ✨ {fa_num(user.xp)} از {fa_num(economy.xp_need(user.level))}\n\n"
        "چی بر داری رفیق؟"
    )
    if extra:
        text += f"\n\n{extra}"
    return text


async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return  # ادمین به پلیرهای عادی واکنش نشون نمیده

    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        text = _panel_text(user)
        await s.commit()

    await respond(update, text, kb.admin_kb())


async def admin_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        await update.callback_query.answer()
        return

    _, kind, amount = parts(update)
    amount = int(amount)

    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)

        if kind == "cash":
            user.cash += amount
            alert = f"💵 {money(amount)} اضافه شد"
            extra = None
        elif kind == "xp":
            notes = users.add_xp(user, amount)
            alert = f"✨ {fa_num(amount)} XP اضافه شد"
            extra = "\n".join(notes) if notes else None
        else:
            alert = "❌ چیزی نیست که"
            extra = None

        text = _panel_text(user, extra)
        await s.commit()

    await respond(update, text, kb.admin_kb(), alert=alert)
