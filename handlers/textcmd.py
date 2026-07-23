"""
دستورهای متنی فارسی، هم PV هم گروه، همه با پیشوند «تریاکی »
«تریاکی شاپ» «تریاکی پروفایل» «تریاکی خرید چاقو» «تریاکی خرید سگ دوبرمن» «تریاکی کاشت ماری جوانا»
«تریاکی واریز 1200» «تریاکی برداشت محصول» «تریاکی حمله» (با ریپلای) «تریاکی مزرعه» «تریاکی سگ‌های من»

⚠️ برای کار کردن تو گروه، Privacy Mode ربات باید توی BotFather خاموش باشه
"""

import re

from telegram import Update
from telegram.ext import ContextTypes

import config
from database import session_scope
from handlers.common import format_attack_result, parts, respond, strip_bot_cmd
from handlers import dogs as dogs_h
from handlers import farm as farm_h
from handlers import profile as profile_h
from handlers import shop as shop_h
from keyboards import keyboards as kb
from models import User
from services import combat, dogs as dog_svc, economy, farming, shop_svc, users
from utils import esc, fa_dur, fa_num, find_by_name, money, normalize_fa


# ───────── ابزار ─────────

def _match_arg(update: Update) -> str:
    """بخش بعد از فعل دستور، مثلا «چاقو» از «تریاکی خرید چاقو»"""
    text = strip_bot_cmd(update.message.text or "")
    m = re.match(r"^\S+\s+(.+)$", text)
    return m.group(1) if m else ""


# ───────── شاپ و پروفایل و مزرعه و سگ‌ها (متنی) ─────────

async def shop_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await shop_h.shop_cb(update, context)


async def profile_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await profile_h.profile_photo_cmd(update, context)


async def farm_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await farm_h.render_farm(update)


async def dogs_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await dogs_h.render_my_dogs(update)


# ───────── خرید متنی ─────────

async def buy_dog_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = _match_arg(update)
    dog_query = normalize_fa(query)
    if dog_query.startswith("سگ "):
        dog_query = dog_query[3:]

    key, dog, custom_name = dog_svc.parse_dog_query(dog_query)
    if not key:
        names = " | ".join(d["name"] for d in config.DOGS.values())
        return await respond(update, f"🤷 سگی با این اسم پیدا نشد\n\nموجودی:\n{names}")

    # اسم تو دستور نیومده، اول اسمش پرسیده میشه و بعد فاکتور میاد
    if not custom_name:
        async with session_scope() as s:
            user, _ = await users.get_or_create(s, update.effective_user)
            ok, alert = await dog_svc.hold_dog(s, user, key)
            await s.commit()
        if not ok:
            return await respond(update, alert)
        return await respond(update, dogs_h.dog_name_question_text(dog))

    text = (
        f"<b>🐕 خرید {esc(dog['breed'])}</b>\n\n"
        f"🐾 نژاد {esc(dog['breed'])}\n"
        f"📛 اسم {esc(custom_name)}\n"
        f"💸 قیمت {money(dog['price'])}\n\n"
        "معامله‌ست؟"
    )
    await respond(update, text, kb.tx_confirm_kb("dog", key, update.effective_user.id, custom_name))


async def buy_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = _match_arg(update)

    # سگ فقط با فرمت «خرید سگ ...»
    if normalize_fa(query).startswith("سگ"):
        return await buy_dog_text(update, context)

    kind, key, item = shop_svc.find_shop_item(query)
    if not key:
        return await respond(update, "🤷 جنسی با این اسم پیدا نشد")

    emoji = shop_svc.KIND_EMOJI.get(kind, "🛒")
    extra = ""
    if kind == "weap":
        extra = f"📈 قدرت حمله +{fa_num(item['attack'])}\n"
    elif kind == "arm":
        extra = f"📈 دفاع +{fa_num(item['defense'])}\n"
        if item.get("legendary"):
            extra += f"👑 <i>{esc(item['desc'])}</i>\n"
    elif kind == "seed":
        extra = f"⏱ رشد {fa_num(item['grow_min'])} دقیقه\n💰 فروش {money(item['sell'])}\n"

    text = (
        f"<b>🧾 فاکتور خرید</b>\n\n"
        f"{emoji} {esc(item['name'])}\n"
        f"{extra}"
        f"💸 قیمت {money(item['price'])}\n\n"
        "معامله‌ست؟"
    )
    await respond(update, text, kb.tx_confirm_kb(kind, key, update.effective_user.id))


async def tx_confirm_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """اجرای تایید خرید دستور متنی، فقط خودِ صاحب دستور می‌تونه بزنه"""
    p = parts(update)
    kind, key, owner_id = p[1], p[2], p[3]
    dog_name = p[4] if len(p) > 4 else None  # اسم دلخواه سگ

    if update.effective_user.id != int(owner_id):
        await update.callback_query.answer()  # غریبه هیچ واکنشی نمی‌بینه
        return

    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        _, alert = await shop_svc.purchase(s, user, kind, key, dog_name=dog_name)
        cash = user.cash
        await s.commit()

    text = f"<b>{esc(alert)}</b>\n\n💵 نقدینگی {money(cash)}"
    await respond(update, text, kb.home_kb())


# ───────── کاشت متنی ─────────

async def plant_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = _match_arg(update)
    key, seed = find_by_name(config.SEEDS, query)
    if not key:
        names = " | ".join(s["name"] for s in config.SEEDS.values())
        return await respond(update, f"🤷 محصولی با این اسم ندارم\n\nگزینه‌ها:\n{names}")

    dq_done, dq_left, uname = [], 0, ""
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)

        plots = await farming.get_user_plots(s, user.id)
        empty = next((p for p in plots if p.current_status()[0] == "empty"), None)
        building = next((p for p in plots if p.current_status()[0] == "building"), None)

        if not plots:
            msg = "🌱 زمینی نداری، اول از مزرعه زمین بخر"
        elif empty is None:
            if building is not None:
                _, left = building.current_status()
                msg = f"🔨 زمین جدیدت داره ساخته میشه، {fa_dur(left)} دیگه می‌تونی بکاری"
            else:
                msg = "🌱 همه زمین‌هات پره صبر کن یدونه آماده بشه"
        else:
            ok, msg = await farming.plant(s, user, empty, key)
            if ok:
                from services import quests as dq_svc
                dq_done, dq_left = await dq_svc.track(s, user, "plant")
                uname = users.display_name(user)
        await s.commit()

    await respond(update, f"<b>🌱 کاشت</b>\n\n{esc(msg)}", kb.home_kb())
    from handlers import dquests
    await dquests.announce_completed(update, uname, dq_done, dq_left)


# ───────── برداشت متنی ─────────

async def harvest_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    dq_done, dq_left, uname = [], 0, ""
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        ok, msg, extra, dq = await farming.harvest_all(s, user)
        if ok:
            dq_done, dq_left = dq
            uname = users.display_name(user)
        await s.commit()

    if not ok:
        return await respond(update, f"<b>📦 برداشت</b>\n\n{esc(msg)}", kb.home_kb())

    text = "<b>📦 برداشت</b>\n\n" + esc(extra or msg)
    await respond(update, text, kb.home_kb())
    from handlers import dquests
    await dquests.announce_completed(update, uname, dq_done, dq_left)


# ───────── حمله با ریپلای (گروه و PV)، با تاییدیه ─────────

async def attack_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    reply = update.message.reply_to_message

    if not reply or not reply.from_user:
        return await respond(
            update,
            "<b>⚔️ حمله</b>\n\n"
            "روی پیام هدفت ریپلای کن و بنویس «حمله» یا «تریاکی حمله»\n"
            "یا از منوی ⚔️ حمله هدف رندوم پیدا کن",
            kb.home_kb(),
        )

    tg_target = reply.from_user
    if tg_target.is_bot:
        return await respond(update, "😅 ربات‌ها رو نمیشه زد")
    if tg_target.id == update.effective_user.id:
        return await respond(update, "😅 خودتو نزن")

    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        users.apply_energy_regen(user)

        left = combat.cooldown_left(user)
        if left:
            await s.commit()
            return await respond(update, f"⏳ هنوز {fa_dur(left)} از کولدونت مونده")
        if user.energy < config.ATTACK_ENERGY_COST:
            await s.commit()
            return await respond(update, "⚡ انرژیت کمه")

        target = await users.get_by_tg(s, tg_target.id)
        if not target:
            await s.commit()
            return await respond(update, "🤷 این هنوز وارد محله نشده، اول باید به بات /start بزنه")

        name = esc(users.display_name(target))

        # هدف سپرداره، تا تموم شدن سپرش نمیشه زدش
        t_shield = combat.shield_left(target)
        if t_shield:
            await s.commit()
            return await respond(
                update,
                f"🛡 {name} سپر محافظ داره\n\n{fa_dur(t_shield)} دیگه دوباره می‌تونی بزنیش",
            )

        target_id = target.id

        # خودش سپر داره، اول باید تایید کنه سپرشو می‌شکنه
        if combat.shield_left(user):
            await s.commit()
            from handlers.attack import shield_prompt_text
            return await respond(
                update, shield_prompt_text(),
                kb.shield_break_kb(f"txatt:{target_id}:{update.effective_user.id}:brk", f"txcl:{update.effective_user.id}"),
            )

        text = (
            f"<b>⚔️ حمله به {name}</b>\n\n"
            f"⭐ لول {fa_num(target.level)}\n"
            f"💵 وضعیت جیبش: {combat.cash_bucket(target.cash)}\n"
            f"هزینه حمله ⚡ {fa_num(config.ATTACK_ENERGY_COST)} انرژی\n\n"
            "مطمئنی رفیق؟"
        )
        await s.commit()

    await respond(update, text, kb.tx_attack_kb(target_id, update.effective_user.id))


async def tx_attack_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """اجرای حمله بعد از تایید، فقط خود مهاجم می‌تونه بزنه (brk یعنی سپرشو تایید کرده بشکنه)"""
    p = parts(update)
    target_id, owner_tg = p[1], p[2]
    break_shield = len(p) > 3 and p[3] == "brk"

    if update.effective_user.id != int(owner_tg):
        await update.callback_query.answer()  # غریبه هیچ واکنشی نمی‌بینه
        return

    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        users.apply_energy_regen(user)

        target = await s.get(User, int(target_id))
        if not target:
            await s.commit()
            return await respond(update, "🤷 طرفت تیک انداخت رفت")

        result = await combat.execute_attack(s, user, target, break_shield=break_shield)
        target_name = esc(users.display_name(target))
        dq_done, dq_left = [], 0
        if result["ok"]:
            from services import quests as dq_svc
            dq_done, dq_left = await dq_svc.track(s, user, "attack")
        uname = users.display_name(user)
        await s.commit()

    if not result["ok"]:
        if result["reason"] == "shield_self":
            from handlers.attack import shield_prompt_text
            return await respond(
                update, shield_prompt_text(),
                kb.shield_break_kb(f"txatt:{target_id}:{owner_tg}:brk", f"txcl:{owner_tg}"),
            )
        msg = (
            f"⏳ هنوز {fa_dur(result['left'])} از کولدونت مونده"
            if result["reason"] == "cooldown"
            else f"🛡 طرف سپر محافظ داره، {fa_dur(result['left'])} دیگه میشه زدش"
            if result["reason"] == "shield_target"
            else "⚡ انرژیت کمه"
        )
        return await respond(update, msg)
    await respond(update, format_attack_result(result, target_name), kb.attack_result_kb())
    from handlers import dquests
    await dquests.announce_completed(update, uname, dq_done, dq_left)


async def tx_cancel_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """لغو فاکتور/تایید متنی، فقط صاحبش"""
    _, owner_tg = parts(update)

    if update.effective_user.id != int(owner_tg):
        await update.callback_query.answer()  # غریبه هیچ واکنشی نمی‌بینه
        return
    await respond(update, "<b>😅 بی‌خیال شدیم</b>")
