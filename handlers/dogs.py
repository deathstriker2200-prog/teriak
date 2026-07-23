"""سگ‌های من: نمایش اطلاعات سگ | غذا دادن | لول‌آپ | کارت آمار («آمار اصغر»)"""

import re

from telegram import Update
from telegram.ext import ContextTypes

import config
from database import session_scope
from handlers.common import parts, respond
from keyboards import keyboards as kb
from models import Dog
from services import dogs as dog_svc
from services import users
from utils import bar, esc, fa_num, money, money_tp

# عدد به حروف برای زمین شماره n (دکمه noop پلات)، مشترک با کیبوردها
FA_WORDS = {1: "یکم", 2: "دوم", 3: "سوم", 4: "چهارم", 5: "پنجم"}


def dog_name_question_text(item: dict) -> str:
    """متن پرسیدن اسم سگ موقع خرید، قبل از فاکتور و پرداخت"""
    return (
        f"<b>🐕 خرید {esc(item['breed'])}</b>\n\n"
        f"🐾 نژاد {esc(item['breed'])}\n"
        f"💪 قدرت حمله {fa_num(item['attack'])}\n"
        f"🎖 {esc(item['ability'])}\n"
        f"💸 قیمت {money(item['price'])}\n\n"
        "📛 اول بگو اسمش چی باشه، اسمشو همینجا بنویس و بفرست، مثلا «اصغر»\n\n"
        "❌ پشیمون شدی بنویس «لغو»"
    )


async def _dogs_text(session, user, dogs: list[Dog]) -> str:
    lines = ["<b>🐕 سگ‌های من</b>\n"]

    if not dogs:
        lines.append("هنوز سگی نداری")
        lines.append("از بخش 🐕 سگ‌های شاپ یکی بخر و باهات بجنگه")
    else:
        for d in dogs:
            crown = "👑 " if d.cfg.get("rare") else ""
            need = dog_svc.dog_xp_need(d.level)
            atk = dog_svc.dog_attack(d)
            entry = (
                f"\n{crown}<b>{esc(d.name)}</b>"
                f"\n🐾 نژاد {esc(d.breed)}"
                f"\n⭐ لول {fa_num(d.level)} | ✨ {fa_num(d.xp)} از {fa_num(need)}"
                f"\n💪 قدرت حمله {fa_num(atk)}"
            )
            rare_lines = dog_svc.rare_ability_lines(d)
            if rare_lines:
                entry += "\n" + "\n".join(rare_lines)
            else:
                entry += f"\n🎖 {esc(d.cfg.get('ability', '—'))}"
            per = dog_svc.personality_of(d)
            if per:
                entry += f"\n💫 شخصیت {per['emoji']} {esc(per['name'])}، {esc(per['desc'])}"
            entry += f"\n{dog_svc.hunger_text(d)}"
            lines.append(entry)

    return "\n".join(lines)


async def render_my_dogs(update: Update, alert: str | None = None, extra: str | None = None) -> None:
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        dogs = await dog_svc.get_user_dogs(s, user.id)
        text = await _dogs_text(s, user, dogs)
        if extra:
            text += f"\n\n{extra}"
        markup = kb.my_dogs_kb(dogs)
        await s.commit()
    await respond(update, text, markup, alert=alert)


async def dogs_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await render_my_dogs(update)


# ───────── کارت آمار یه سگ، «آمار اصغر» ─────────

def _dog_card_text(user, dog: Dog, extra: str | None = None) -> str:
    need = dog_svc.dog_xp_need(dog.level)
    atk = dog_svc.dog_attack(dog)
    maxed = dog.level >= config.DOG_MAX_LEVEL
    crown = " 👑" if dog.cfg.get("rare") else ""

    if maxed:
        xp_line = f"✨تجربه مکس 😎 {bar(1, 1)}"
    else:
        xp_line = f"✨تجربه {fa_num(dog.xp)}/{fa_num(need)} {bar(dog.xp, need)}"

    # قابلیت: گرگ سیاه با اعداد مقیاس لول | بقیه متن ثابت نژاد
    rare_lines = dog_svc.rare_ability_lines(dog)
    ability_block = "\n".join(rare_lines) if rare_lines else f"🎖 {esc(dog.cfg.get('ability', '—'))}"

    per = dog_svc.personality_of(dog)
    per_line = ""
    if per:
        per_line = f"\n💫 شخصیت {per['emoji']} {esc(per['name'])}، {esc(per['desc'])}"

    food_line = dog_svc.hunger_text(dog)

    text = (
        f"<b>🐕 آمار {esc(dog.name)}</b>\n\n"
        f"🐾 نژاد {esc(dog.breed)}{crown}\n"
        f"⭐ لول {fa_num(dog.level)}\n"
        f"{xp_line}\n"
        f"💪 قدرت حمله {fa_num(atk)}\n"
        f"{ability_block}{per_line}\n\n"
        f"{food_line}"
    )
    if extra:
        text += f"\n\n{extra}"
    return text


async def render_dog_card(update: Update, dog: Dog | None, alert: str | None = None, extra: str | None = None) -> None:
    if dog is None:
        return await render_my_dogs(update, alert=alert or "❌ همچین سگی نداری")
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        left = dog_svc.feeds_left(dog)
        text = _dog_card_text(user, dog, extra)
        markup = kb.dog_card_kb(dog, left)
        await s.commit()
    await respond(update, text, markup, alert=alert)


async def dog_card_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    dog_id = int(parts(update)[2])
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        dog = await s.get(Dog, dog_id)
        if not dog or dog.user_id != user.id:
            await s.commit()
            return await render_my_dogs(update, alert="❌ همچین سگی نداری")
        await s.commit()
    await render_dog_card(update, dog)


async def dog_stats_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """«تریاکی آمار [اسم سگ]»، کارت سگ با دکمه‌های غذا"""
    from handlers.common import strip_bot_cmd
    m = re.match(r"^آمار[\s‌]+(.+)$", strip_bot_cmd(update.message.text or ""))
    query = m.group(1) if m else ""

    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        dogs = await dog_svc.get_user_dogs(s, user.id)
        await s.commit()

    dog = dog_svc.find_my_dog(dogs, query)
    if not dog:
        if not dogs:
            return await respond(update, "🐕 اصلا سگی نداری که، از شاپ یدونه بخر")
        names = " | ".join(d.name for d in dogs)
        return await respond(update, f"🤷 سگی با این اسم پیدا نشد\n\nسگ‌هات: {esc(names)}")
    await render_dog_card(update, dog)


async def feed_picker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دکمه «🍖 غذا بده» دیالوگ جدا نمیاره، همون کارت آمار سگ میاد تا از اونجا غذا بدی"""
    dog_id = int(parts(update)[2])
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        dog = await s.get(Dog, dog_id)

        if not dog or dog.user_id != user.id:
            await s.commit()
            return await render_my_dogs(update, alert="❌ همچین سگی نداری")
        await s.commit()

    await render_dog_card(update, dog)


async def feed_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, _, dog_id, food_key = parts(update)
    dq_done, dq_left, uname = [], 0, ""
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        dog = await s.get(Dog, int(dog_id))

        if not dog or dog.user_id != user.id:
            await s.commit()
            return await render_my_dogs(update, alert="❌ همچین سگی نداری")

        ok, msg, notes = await dog_svc.feed_dog(s, user, dog, food_key)
        if ok:
            from services import quests as dq_svc
            dq_done, dq_left = await dq_svc.track(s, user, "feed")
            uname = users.display_name(user)
        cash = user.cash
        await s.commit()

    if not ok:
        return await render_dog_card(update, dog, alert=msg)

    # غذا از همون کارت سگ داده میشه، برمی‌گردیم همونجا
    extra = f"{msg}\n💵 نقدینگی {fa_num(cash)}TP"
    if notes:
        extra += "\n" + "\n".join(notes)
    await render_dog_card(update, dog, alert="🍖 نوش جون", extra=extra)
    from handlers import dquests
    await dquests.announce_completed(update, uname, dq_done, dq_left)


# ───────── رها کردن سگ 🕊 ─────────

async def release_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    dog_id = int(parts(update)[2])
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        dog = await s.get(Dog, dog_id)
        if not dog or dog.user_id != user.id:
            await s.commit()
            return await render_my_dogs(update, alert="❌ همچین سگی نداری")
        name = dog.name
        breed = dog.breed
        await s.commit()

    text = (
        f"<b>🕊 رها کردن {esc(name)}</b>\n\n"
        f"🐾 نژاد {esc(breed)}\n\n"
        "برگشتی نداره ها، مطمئنی؟"
    )
    await respond(update, text, kb.release_confirm_kb(dog_id, update.effective_user.id))


async def release_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """اجرای رها کردن، فقط صاحب سگ (دیتا: relcf:<dog_id>:<tg_id>)"""
    _, dog_id, owner_tg = parts(update)
    if update.effective_user.id != int(owner_tg):
        await update.callback_query.answer()  # غریبه هیچ واکنشی نمی‌بینه
        return

    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        dog = await s.get(Dog, int(dog_id))
        if not dog or dog.user_id != user.id:
            await s.commit()
            return await render_my_dogs(update, alert="❌ همچین سگی نداری")
        ok, msg = await dog_svc.release_dog(s, user, dog)
        await s.commit()

    if ok:
        return await render_my_dogs(update, alert=msg)
    await render_my_dogs(update, alert=msg)
