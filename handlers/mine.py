"""کنده‌کاری ⛏: بخش مستقل تو منوی اصلی + ابزار (تبر/کلنگ) + دراپ منابع
دستور متنی «کنده کاری» هم مستقیم ضربه می‌زنه"""

from datetime import timedelta

from telegram import Update
from telegram.ext import ContextTypes

import config
from database import session_scope
from handlers.common import parts, respond
from keyboards import keyboards as kb
from services import resources as res_svc
from services import users
from utils import esc, fa_dur, fa_num, money, money_tp, now_utc


# ───────── متن‌ها ─────────

def mine_home_text(user) -> str:
    return "\n".join([
        "<b>⛏ کنده کاری</b>",
        "",
        "تی‌پوینت و تجربه می‌گیری",
        "شانسی چوب و آهن هم پیدا می‌کنی",
        "",
        f"🪓 تبر لول {fa_num(user.axe_level)} | ⛏️ کلنگ لول {fa_num(user.pick_level)}",
        f"🪵 چوب {fa_num(user.wood)} | ⛏️ آهن {fa_num(user.iron)}",
    ])


def _loot_text(loot: dict, user) -> str:
    lines = ["<b>⛏ کنده‌کاری</b>", ""]
    lines.append(f"💰 {money(loot['cash'])} به دست آوردی")
    lines.append(f"✨ {fa_num(loot['xp'])} تجربه گرفتی")
    if loot["wood"]:
        lines.append(f"🪵 {fa_num(loot['wood'])} چوب پیدا کردی")
    if loot["iron"]:
        lines.append(f"⛏️ {fa_num(loot['iron'])} آهن پیدا کردی")
    if loot["rare"]:
        lines.append("✨ شکار کمیاب")
    lines += [
        "",
        f"🪙 موجودی: {money(user.cash)}",
        "",
        f"خستت شده نیاز به {fa_num(config.MINE_COOLDOWN_SECONDS)}ثانیه استراحت داری برای کنده کاری بعدی",
    ]
    return "\n".join(lines)


def _tired_text(left: float) -> str:
    return (
        "<b>⛏ کنده‌کاری</b>\n\n"
        f"خستت شده نیاز به {fa_dur(left)} استراحت داری برای کنده کاری بعدی"
    )


def tools_text(user) -> str:
    lines = ["<b>🎒 وضعیت ابزار</b>", ""]
    for key, cfg in config.TOOLS.items():
        lv = user.axe_level if key == "axe" else user.pick_level
        lines.append(f"{cfg['emoji']} {cfg['name']} | لول {fa_num(lv)}")
        if lv >= config.TOOL_MAX_LEVEL:
            lines.append("👑 لول مکس")
        else:
            tp, iron = res_svc.tool_upgrade_cost(key, lv)
            lines.append(f"⬆️ بعدی: 💰 {money_tp(tp)} + ⛏️ {fa_num(iron)} آهن")
        lines.append("")
    lines.append("هر لول ابزار چوب و آهن و تی‌پوینت بیشتری میده")
    lines.append("شانس پیدا کردن منابع کمیاب هم بیشتر میشه")
    return "\n".join(lines)


# ───────── ضربه ─────────

async def _do_roll(update: Update) -> None:
    dq_done, dq_left, uname = [], 0, ""
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        now = now_utc()
        cooldown = timedelta(seconds=config.MINE_COOLDOWN_SECONDS)

        if user.last_mine_at and now - user.last_mine_at < cooldown:
            left = cooldown - (now - user.last_mine_at)
            text = _tired_text(left.total_seconds())
            kb_out = kb.mine_kb()
        else:
            loot = res_svc.mine_loot(user)
            user.cash += loot["cash"]
            got_w = res_svc.add_res(user, "wood", loot["wood"])
            got_i = res_svc.add_res(user, "iron", loot["iron"])
            loot["wood"], loot["iron"] = got_w, got_i
            user.last_mine_at = now
            notes = users.add_xp(user, loot["xp"])

            from services import quests as dq_svc
            dq_done, dq_left = await dq_svc.track(s, user, "mine")
            uname = users.display_name(user)

            text = _loot_text(loot, user)
            if notes:
                text += "\n\n" + "\n".join(notes)
            kb_out = kb.mine_kb()
        await s.commit()

    await respond(update, text, kb_out)
    from handlers import dquests
    await dquests.announce_completed(update, uname, dq_done, dq_left)


async def mine_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """«کنده کاری» متنی، مستقیم ضربه"""
    await _do_roll(update)


async def mine_home_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        text = mine_home_text(user)
        await s.commit()
    await respond(update, text, kb.mine_kb())


async def mine_roll_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _do_roll(update)


async def mine_tools_cb(update: Update, context: ContextTypes.DEFAULT_TYPE, alert: str | None = None) -> None:
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        text = tools_text(user)
        await s.commit()
    await respond(update, text, kb.mine_kb(), alert=alert)


async def mine_upg_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tool_key = parts(update)[2]
    cfg = config.TOOLS.get(tool_key)
    if not cfg:
        return await mine_home_cb(update, context)
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        lv = user.axe_level if tool_key == "axe" else user.pick_level
        cost = res_svc.tool_upgrade_cost(tool_key, lv)
        await s.commit()

    if cost is None:
        return await mine_home_cb(update, context)
    tp, iron = cost
    text = (
        f"<b>⬆️ ارتقای {esc(cfg['emoji'])} {esc(cfg['name'])}</b>\n\n"
        f"از لول {fa_num(lv)} به لول {fa_num(lv + 1)}\n"
        f"💸 تی‌پوینت {money(tp)}\n"
        f"⛏️ آهن {fa_num(iron)}\n\n"
        "انجامش بدیم؟"
    )
    await respond(update, text, kb.mine_up_confirm_kb(tool_key))


async def mine_upg_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tool_key = parts(update)[3]
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        lv = user.axe_level if tool_key == "axe" else user.pick_level
        cost = res_svc.tool_upgrade_cost(tool_key, lv) if tool_key in config.TOOLS else None
        if cost is None:
            alert = "👑 ابزارت لول مکسه"
        else:
            tp, iron = cost
            if user.cash < tp:
                alert = "❌ تی‌پوینتت کافی نیس"
            elif user.iron < iron:
                alert = f"⛏️ {fa_num(iron)} آهن می‌خواد و {fa_num(user.iron)} تا داری"
            else:
                user.cash -= tp
                user.iron -= iron
                if tool_key == "axe":
                    user.axe_level += 1
                else:
                    user.pick_level += 1
                alert = f"⬆️ {config.TOOLS[tool_key]['name']} رفت رو لول {fa_num(lv + 1)}"
        await s.commit()
    await mine_tools_cb(update, context, alert=alert)


async def mine_upg_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await mine_tools_cb(update, context)
