"""
سیستم‌های جهان: جستجو 🔍 | آب و هوا 🌦 | بازار سیاه 📈 | پناهگاه 🏚 | قمارخانه 🎰 | کاروان 🚛
"""

from telegram import Update
from telegram.constants import ChatType
from telegram.error import BadRequest
from telegram.ext import ContextTypes

import config
from database import session_scope
from handlers.common import parts, respond
from keyboards import keyboards as kb
from services import combat, dogs as dog_svc, users
from services import world as world_svc
from utils import esc, fa_dur, fa_num, money, money_tp


# ═════════ جستجو 🔍 ═════════

async def search_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    dq_done, dq_left, uname = [], 0, ""
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        users.apply_energy_regen(user)
        dogs = await dog_svc.get_user_dogs(s, user.id)
        luck = dog_svc.search_luck(dogs)
        res = await world_svc.do_search(s, user, luck=luck)
        if res["status"] != "cooldown":
            from services import quests as dq_svc
            dq_done, dq_left = await dq_svc.track(s, user, "search")
            uname = users.display_name(user)
        cash = user.cash
        await s.commit()

    st = res["status"]
    if st == "cooldown":
        return await respond(update, f"⏳ هر {fa_num(config.SEARCH_COOLDOWN_MINUTES)} دقیقه یه جستجو، {fa_dur(res['left'])} دیگه بیا")

    o = res["outcome"]
    if st == "money":
        text = (
            "<b>🔍 جستجو</b>\n\n"
            f"{o['emoji']} {o['text']}، {money(res['amount'])} گیرت اومد\n\n"
            f"💵 نقدینگی {fa_num(cash)}TP"
        )
    elif st == "thief":
        text = (
            "<b>🔍 جستجو</b>\n\n"
            f"{o['emoji']} {o['text']}\n"
            f"💸 {money(res['lost'])} از جیبت رفت، نقدینگی {fa_num(cash)}TP"
        )
    else:
        seed_name = config.SEEDS[res["seed"]]["name"]
        text = (
            "<b>🔍 جستجو</b>\n\n"
            f"{o['emoji']} {o['text']} <b>({esc(seed_name)})</b>\n\n"
            "رفت تو انبارت، بکارش یا نگهش دار 🌾"
        )
    if luck > 1:
        text += "\n\n🍀 سگ خوش‌شانست شانس خوبت رو بیشتر کرد"
    await respond(update, text, kb.home_kb())
    from handlers import dquests
    await dquests.announce_completed(update, uname, dq_done, dq_left)


# ═════════ آب و هوا 🌦 ═════════

async def weather_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        view = await world_svc.weather_view(s)
        key = view["key"]
        left = view["left"]
        await s.commit()

    w = view["w"]
    lines = [
        "<b>🌦 وضعیت آب و هوا</b>",
        "",
        f"{w['emoji']} {w['name']}",
        f"⏳ {fa_dur(left)} دیگه عوض میشه",
        "",
    ]
    if key == "normal":
        lines.append("افکت خاصی فعال نیست، هوا عادیه")
    else:
        lines.append("افکت‌های فعلی:")
        for b in w.get("effects", []):
            lines.append(f"▫️ {b}")
    lines.append("")
    lines.append("🌦 هر 2 ساعت عوض میشه و تو گروه‌های فعال اعلام میشه")
    await respond(update, "\n".join(lines), kb.home_kb())


# ═════════ بازار سیاه 📈 ═════════

async def market_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        pcts, left = await world_svc.market_pcts(s)
        await s.commit()

    await respond(update, world_svc.market_view_text(pcts, left), kb.home_kb())


# ═════════ پناهگاه 🏚 ═════════

async def _shelter_text(user) -> str:
    cut = world_svc.shelter_raid_cut(user.shelter_level)
    dodge = world_svc.shelter_dodge_chance(user.shelter_level)
    cap = world_svc.seed_storage_cap(user)
    lines = [
        "<b>🏚 پناهگاه</b>",
        "",
        f"⭐ لول {fa_num(user.shelter_level)}" + (f" از {fa_num(config.SHELTER_MAX_LEVEL)}" if user.shelter_level else "، هنوز نداری"),
        "",
        f"🛡 خسارت یورش پلیس {fa_num(int(cut * 100))}% کمتره",
        f"🎲 شانس فرار کامل از یورش {fa_num(int(dodge * 100))}%",
        f"📦 ظرفیت انبار هر بذر {fa_num(cap)} تا",
        "",
        "🚔 پلیس هر چند ساعت به فعال‌های محله یورش میاره و 30% محصولات انبار رو نابود می‌کنه، پناهگاه جلوته",
    ]
    if user.shelter_level < config.SHELTER_MAX_LEVEL:
        price = world_svc.shelter_price(user.shelter_level + 1)
        lines.append(f"\n⬆️ ارتقای بعدی: لول {fa_num(user.shelter_level + 1)} | {money(price)}")
    return "\n".join(lines)


async def shelter_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        text = await _shelter_text(user)
        markup = kb.shelter_kb(user)
        await s.commit()
    await respond(update, text, markup)


async def shelter_up_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        if user.shelter_level >= config.SHELTER_MAX_LEVEL:
            await s.commit()
            return await shelter_cmd(update, None)
        price = world_svc.shelter_price(user.shelter_level + 1)
        level = user.shelter_level
        cash = user.cash
        await s.commit()

    text = (
        f"<b>🏚 ارتقای پناهگاه، لول {fa_num(level)} ← {fa_num(level + 1)}</b>\n\n"
        f"💸 هزینه {money(price)}\n"
        f"💵 الان {money(cash)} داری\n\n"
        "انجامش بدیم؟"
    )
    await respond(update, text, kb.confirm_kb("cf:shelter:up"))


async def shelter_up_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        ok, msg = await world_svc.upgrade_shelter(s, user)
        text = await _shelter_text(user)
        markup = kb.shelter_kb(user)
        cash = user.cash
        await s.commit()
    if ok:
        return await respond(
            update,
            text + f"\n\n{esc(msg)}\n💵 نقدینگی {fa_num(cash)}TP",
            markup, alert="🏚 پناهگاه ارتقا پیدا کرد",
        )
    await respond(update, text, markup, alert=msg)


# ═════════ قمارخانه 🎰 ═════════

async def casino_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        level, cash = user.level, user.cash
        left = world_svc.casino_cooldown_left(user)
        await s.commit()

    if level < config.CASINO_MIN_LEVEL:
        return await respond(update, f"🔒 قمارخانه از لول {fa_num(config.CASINO_MIN_LEVEL)} باز میشه")
    if left:
        return await respond(update, f"⏳ هر {fa_num(config.CASINO_COOLDOWN_HOURS)} ساعت یه دست می‌تونی بازی کنی، {fa_dur(left)} مونده")

    text = (
        "<b>🎰 قمارخانه</b>\n\n"
        f"شانس برد {fa_num(int(config.CASINO_WIN_CHANCE * 100))}% | برد = {config.CASINO_WIN_MULT} برابر شرط\n"
        f"یه دست هر {fa_num(config.CASINO_COOLDOWN_HOURS)} ساعت\n"
        f"💵 نقدینگی {fa_num(cash)}TP\n\n"
        "میزتو انتخاب کن 🎲"
    )
    await respond(update, text, kb.casino_kb())


async def casino_bet_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    bet = int(parts(update)[2])
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        cash = user.cash
        left = world_svc.casino_cooldown_left(user)
        await s.commit()

    if left:
        return await respond(update, f"⏳ {fa_dur(left)} دیگه می‌تونی بازی کنی")
    if cash < bet:
        return await respond(update, "❌ پولت به این میز نمی‌رسه")

    prize = int(bet * config.CASINO_WIN_MULT)
    text = (
        f"<b>🎰 میز {money(bet)}</b>\n\n"
        f"بردی → {money(prize)} جیبت میشه\n"
        f"باختی → {money(bet)} میره رو دیلر\n"
        f"شانس برد {fa_num(int(config.CASINO_WIN_CHANCE * 100))}%\n\n"
        "قماره ها، بازی کنیم؟"
    )
    await respond(update, text, kb.confirm_kb(f"cascf:{bet}"))


async def casino_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    bet = int(parts(update)[1])
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        res = await world_svc.casino_play(s, user, bet)
        await s.commit()

    st = res["status"]
    if st == "cooldown":
        return await respond(update, f"⏳ {fa_dur(res['left'])} دیگه می‌تونی بازی کنی")
    if st == "poor":
        return await respond(update, "❌ پولت به این میز نمی‌رسه")
    if st == "locked":
        return await respond(update, f"🔒 قمارخانه از لول {fa_num(config.CASINO_MIN_LEVEL)} باز میشه")

    if st == "win":
        text = (
            "<b>🎰 وین!</b>\n\n"
            f"دیلر پاشید، {money(res['prize'])} جیبت شد 😈\n\n"
            f"💵 نقدینگی {fa_num(res['cash'])}TP"
        )
    else:
        text = (
            "<b>🎰 آمپر نشد</b>\n\n"
            f"{money(res['bet'])} رفت رو دیلر 💸\n"
            f"💵 نقدینگی {fa_num(res['cash'])}TP\n\n"
            f"دست بعدی {fa_num(config.CASINO_COOLDOWN_HOURS)} ساعت دیگه"
        )
    await respond(update, text, kb.home_kb())


# ═════════ کاروان 🚛، دکمه حمله تو گروه ═════════

async def caravan_hit_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    chat_id = query.message.chat_id if query.message else update.effective_chat.id

    cv = world_svc.caravan_active(chat_id)
    if not cv:
        await query.answer("🚛 کاروانی تو محله نیس", show_alert=True)
        return

    left = world_svc.caravan_hit_left(chat_id, update.effective_user.id)
    if left:
        await query.answer(f"⏳ هر 1 دقیقه یه ضربه، {left} ثانیه مونده", show_alert=True)
        return

    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        items = await users.get_item_keys(s, user.id)
        dogs = await dog_svc.get_user_dogs(s, user.id)
        atk, _ = combat.combat_stats(user, items, dogs)

        user_team = None
        from services import teams as team_svc
        user_team = await team_svc.get_team_of(s, user.id)
        if user_team:
            atk = int(atk * (1 + team_svc.atk_bonus(user_team)))

        res = await world_svc.caravan_attack(s, chat_id, user, atk)
        await s.commit()

    if res["status"] == "cooldown":
        await query.answer(f"⏳ {res['left']} ثانیه مونده", show_alert=True)
        return

    await query.answer(f"⚔️ {fa_num(res['dmg'])} دمیج، 💰 {fa_num(res['cash'])}TP", show_alert=True)

    # برد کاروان ادیت میشه
    cv_now = world_svc.CARAVANS.get(chat_id)
    try:
        if cv_now:
            await context.bot.edit_message_text(
                chat_id=chat_id, message_id=query.message.message_id,
                text=world_svc.caravan_board_text(cv_now), parse_mode="HTML",
                reply_markup=kb.caravan_kb(),
            )
    except BadRequest:
        pass

    if res["status"] == "killed":
        end_text = world_svc.caravan_end_text(res.get("rewards", []), killed=True)
        try:
            if cv_now is None:
                await context.bot.edit_message_text(
                    chat_id=chat_id, message_id=query.message.message_id,
                    text=end_text, parse_mode="HTML",
                )
        except BadRequest:
            pass
        await context.bot.send_message(chat_id, end_text, parse_mode="HTML")
