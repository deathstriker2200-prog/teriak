"""رتبه‌بندی بازیکن‌ها بر اساس مدال 🎖️، تب روزانه و هفتگی و کلی با یه دکمه چرخشی"""

from telegram import Update
from telegram.ext import ContextTypes

import config
from database import session_scope
from handlers.common import respond
from keyboards import keyboards as kb
from services import users
from utils import esc, fa_num

_MEDALS = ["🥇", "🥈", "🥉"]

TAB_TITLES = {"day": "📅 روزانه", "week": "🗓 هفتگی", "all": "🌍 کلی"}
TAB_ORDER = ["day", "week", "all"]


def _next_tab(tab: str) -> str:
    try:
        return TAB_ORDER[(TAB_ORDER.index(tab) + 1) % len(TAB_ORDER)]
    except ValueError:
        return TAB_ORDER[0]


async def rank_cb(update: Update, context: ContextTypes.DEFAULT_TYPE, tab: str | None = None) -> None:
    if tab not in TAB_ORDER:
        tab = "week"  # پیش‌فرض لیدربرد هفتگی

    async with session_scope() as s:
        from sqlalchemy import func as _func, select as _select
        from models import User as _User

        me, _ = await users.get_or_create(s, update.effective_user)
        top = await users.top_by_medals(s, tab, config.RANK_LIMIT)
        my_rank = await users.medal_rank(s, me, tab)
        my_medals = users.medal_value(me, tab)
        total = (await s.execute(_select(_func.count(_User.id)))).scalar_one()

        lines: list[str] = []
        for i, u in enumerate(top, 1):
            medal = _MEDALS[i - 1] if i <= 3 else f"▫️ {fa_num(i)}"
            name = esc(users.display_name(u))
            me_mark = " 👈 تو" if u.id == me.id else ""
            lines.append(f"{medal} {name} | 🎖️ {fa_num(users.medal_value(u, tab))}{me_mark}")

        if not lines:
            lines.append("هنوز کسی مدالی نگرفته 🤷")

        text = (
            f"<b>🏆 لیدربرد {TAB_TITLES[tab]}</b>\n\n"
            + "\n".join(lines)
            + f"\n\nرتبه‌ات توی جدول: {fa_num(my_rank)} از {fa_num(total)} با (🎖️{fa_num(my_medals)})\n"
            + "مدال‌هاتون از روی تجربه‌اتون حساب میشه"
        )
        await s.commit()

    await respond(update, text, kb.rank_kb(tab, _next_tab(tab), TAB_TITLES[_next_tab(tab)]))


async def rank_tab_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """تعویض تب لیدربرد"""
    tab = update.callback_query.data.split(":")[-1]
    await rank_cb(update, context, tab=tab)
