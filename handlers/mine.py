"""کنده‌کاری، درآمد روزانه با قرعه وزن‌دار"""

from datetime import timedelta

from telegram import Update
from telegram.ext import ContextTypes

import config
from database import session_scope
from handlers.common import respond
from services import economy, users
from utils import fa_dur, money, now_utc


async def mine_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    dq_done, dq_left, uname = [], 0, ""
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)

        cooldown = timedelta(seconds=config.MINE_COOLDOWN_SECONDS)
        now = now_utc()

        if user.last_mine_at and now - user.last_mine_at < cooldown:
            left = cooldown - (now - user.last_mine_at)
            text = (
                "<b>⏳ هول نکن</b>\n\n"
                f"{fa_dur(left.total_seconds())} دیگه بیا"
            )
        else:
            amount = economy.mine_roll()
            user.cash += amount
            user.last_mine_at = now
            notes = users.add_xp(user, config.MINE_XP)

            from services import quests as dq_svc
            dq_done, dq_left = await dq_svc.track(s, user, "mine")
            uname = users.display_name(user)

            text = (
                "<b>⛏ کنده‌کاری</b>\n\n"
                f"{money(amount)} گیرت اومد\n"
                f"الان {money(user.cash)} داری\n"
                "ارزشش رو داشت\n\n"
                "💡 پول حاصل از کار خلاف بیشتره عزیز، میتونی از پی‌وی مواد بکاری پولش خوبه🤫"
            )
            if notes:
                text += "\n\n" + "\n".join(notes)

        await s.commit()

    await respond(update, text)
    from handlers import dquests
    await dquests.announce_completed(update, uname, dq_done, dq_left)
