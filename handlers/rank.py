"""رتبه‌بندی بازیکن‌ها"""

from sqlalchemy import func, select
from telegram import Update
from telegram.ext import ContextTypes

import config
from database import session_scope
from handlers.common import respond
from keyboards import keyboards as kb
from models import User
from services import users
from utils import esc, fa_num, money_tp

_MEDALS = ["🥇", "🥈", "🥉"]


async def rank_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with session_scope() as s:
        me, _ = await users.get_or_create(s, update.effective_user)

        top = list((await s.execute(
            select(User).order_by(User.cash.desc()).limit(config.RANK_LIMIT)
        )).scalars())

        my_rank = (await s.execute(
            select(func.count(User.id)).where(User.cash > me.cash)
        )).scalar_one() + 1

        lines: list[str] = []
        for i, u in enumerate(top, 1):
            medal = _MEDALS[i - 1] if i <= 3 else f"▫️ {fa_num(i)}"
            name = esc(users.display_name(u))
            me_mark = " 👈 تو" if u.id == me.id else ""
            lines.append(
                f"{medal} {name} | ⭐ {fa_num(u.level)} | 💵 {money_tp(u.cash)}{me_mark}"
            )

        if not lines:
            lines.append("هنوز کسی اینجا نیس 🤷")

        total = (await s.execute(select(func.count(User.id)))).scalar_one()
        text = (
            "<b>📊 تاپ محله</b>\n\n"
            + "\n".join(lines)
            + f"\n\nرتبه تو {fa_num(my_rank)} از {fa_num(total)} نفره"
        )
        await s.commit()

    await respond(update, text, kb.rank_kb())
