"""کنده‌کاری، درآمد روزانه با قرعه وزن‌دار"""

import random
from datetime import timedelta

from telegram import Update
from telegram.ext import ContextTypes

import config
from database import session_scope
from handlers.common import respond
from services import economy, users
from utils import fa_dur, fa_num, money, now_utc


async def mine_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    dq_done, dq_left, uname = [], 0, ""
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)

        cooldown = timedelta(seconds=config.MINE_COOLDOWN_SECONDS)
        now = now_utc()

        if user.last_mine_at and now - user.last_mine_at < cooldown:
            left = cooldown - (now - user.last_mine_at)
            text = (
                "<b>⛏ کنده‌کاری</b>\n\n"
                f"خستت شده نیاز به {fa_dur(left.total_seconds())} استراحت داری برای کنده کاری بعدی"
            )
        else:
            amount = economy.mine_roll()
            xp = random.randint(config.MINE_XP_MIN, config.MINE_XP_MAX)
            user.cash += amount
            user.last_mine_at = now
            notes = users.add_xp(user, xp)

            from services import quests as dq_svc
            dq_done, dq_left = await dq_svc.track(s, user, "mine")
            uname = users.display_name(user)

            text = (
                "<b>⛏ کنده‌کاری</b>\n\n"
                f"💰 {money(amount)} به دست آوردی\n"
                f"✨ {fa_num(xp)} تجربه گرفتی\n"
                f"🪙 موجودی: {money(user.cash)}\n\n"
                f"خستت شده نیاز به {fa_num(config.MINE_COOLDOWN_SECONDS)}ثانیه استراحت داری برای کنده کاری بعدی"
            )
            if notes:
                text += "\n\n" + "\n".join(notes)

        await s.commit()

    await respond(update, text)
    from handlers import dquests
    await dquests.announce_completed(update, uname, dq_done, dq_left)
