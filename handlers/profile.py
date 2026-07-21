"""پروفایل کاربر"""

from sqlalchemy import func, select
from telegram import Update
from telegram.ext import ContextTypes

import config
from database import session_scope
from handlers.common import respond
from keyboards import keyboards as kb
from models import Plot
from services import combat, economy, users
from utils import esc, fa_num, money


async def _profile_text(session, user) -> str:
    item_keys = await users.get_item_keys(session, user.id)
    atk, dfn = combat.combat_stats(user, item_keys)
    plots_count = (await session.execute(
        select(func.count(Plot.id)).where(Plot.user_id == user.id)
    )).scalar_one()

    name = esc(users.display_name(user))
    username = f"@{esc(user.username)}" if user.username else "بدون یوزرنیم"

    return (
        "<b>🏠 پروفایل</b>\n\n"
        f"👤 {name}\n"
        f"🆔 {username}\n"
        f"⭐ لول {fa_num(user.level)}\n"
        f"✨ تجربه {fa_num(user.xp)} از {fa_num(economy.xp_need(user.level))}\n"
        f"💵 نقدینگی {money(user.cash)}\n"
        f"⚡ انرژی {fa_num(user.energy)} از {fa_num(config.MAX_ENERGY)}\n"
        f"🌱 زمین‌ها {fa_num(plots_count)} تا\n\n"
        f"💪 قدرت حمله {fa_num(atk)}\n"
        f"🛡 دفاع {fa_num(dfn)}\n"
        f"⚔️ برد {fa_num(user.wins)} | ❌ باخت {fa_num(user.losses)}"
    )


async def profile_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        users.apply_energy_regen(user)
        text = await _profile_text(s, user)
        await s.commit()
    await respond(update, text, kb.profile_kb())


# /profile همین رندر رو استفاده می‌کنه
profile_cmd = profile_cb
