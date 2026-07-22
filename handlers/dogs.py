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
from utils import bar, esc, fa_num, money_tp


async def _dogs_text(session, user, dogs: list[Dog]) -> str:
    lines = ["<b>🐕 سگ‌های من</b>\n"]

    if not dogs:
        lines.append("هنوز سگی نداری رفیق")
        lines.append("از بخش 🐕 سگ‌های شاپ یکی بخر و باهات بجنگه")
    else:
        for d in dogs:
            crown = "👑 " if d.cfg.get("rare") else ""
            need = dog_svc.dog_xp_need(d.level)
            atk = dog_svc.dog_attack(d)
            lines.append(
                f"\n{crown}<b>{esc(d.name)}</b>"
                f"\n🐾 نژاد {esc(d.breed)}"
                f"\n⭐ لول {fa_num(d.level)} | ✨ {fa_num(d.xp)} از {fa_num(need)}"
                f"\n💪 قدرت حمله {fa_num(atk)}"
                f"\n🎖 {esc(d.cfg.get('ability', '—'))}"
            )

    left = dog_svc.feeds_left(user)
    lines.append(f"\n\n🍖 امروز {fa_num(left)} غذای دیگه می‌تونی بدی")
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


# ───────── کارت آمار یه سگ — «آمار اصغر» ─────────

def _dog_card_text(user, dog: Dog, extra: str | None = None) -> str:
    need = dog_svc.dog_xp_need(dog.level)
    atk = dog_svc.dog_attack(dog)
    maxed = dog.level >= config.DOG_MAX_LEVEL
    crown = " 👑" if dog.cfg.get("rare") else ""

    if maxed:
        xp_line = f"✨تجربه مکس 😎 {bar(1, 1)}"
    else:
        xp_line = f"✨تجربه {fa_num(dog.xp)}/{fa_num(need)} {bar(dog.xp, need)}"

    left = dog_svc.feeds_left(user)
    if left > 0:
        food_line = f"🍖 امروز {fa_num(left)} غذا مونده — از دکمه‌های پایین غذاش بده"
    else:
        food_line = "🍖 امروز دیگه نمی‌تونی غذا بهش بدی سگت گرسنش نیست"

    text = (
        f"<b>🐕 آمار {esc(dog.name)}</b>\n\n"
        f"🐾 نژاد {esc(dog.breed)}{crown}\n"
        f"⭐ لول {fa_num(dog.level)}\n"
        f"{xp_line}\n"
        f"💪 قدرت حمله {fa_num(atk)}\n"
        f"🎖 {esc(dog.cfg.get('ability', '—'))}\n\n"
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
        left = dog_svc.feeds_left(user)
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
    """«آمار [اسم سگ]» — کارت سگ با دکمه‌های غذا"""
    m = re.match(r"^آمار[\s‌]+(.+)$", (update.message.text or "").strip())
    query = m.group(1) if m else ""

    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        dogs = await dog_svc.get_user_dogs(s, user.id)
        await s.commit()

    dog = dog_svc.find_my_dog(dogs, query)
    if not dog:
        if not dogs:
            return await respond(update, "🐕 اصلا سگی نداری که — از شاپ یدونه بخر")
        names = " | ".join(d.name for d in dogs)
        return await respond(update, f"🤷 سگی با این اسم پیدا نشد\n\nسگ‌هات: {esc(names)}")
    await render_dog_card(update, dog)


async def feed_picker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    dog_id = int(parts(update)[2])
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        dog = await s.get(Dog, dog_id)

        if not dog or dog.user_id != user.id:
            await s.commit()
            return await render_my_dogs(update, alert="❌ همچین سگی نداری")

        left = dog_svc.feeds_left(user)
        if left <= 0:
            await s.commit()
            return await render_my_dogs(
                update, alert=f"امروز {fa_num(config.DOG_FEED_PER_DAY)} بار به سگت غذا دادی، دیگه گرسنش نیست فردا بیا"
            )
        if dog.level >= config.DOG_MAX_LEVEL:
            await s.commit()
            return await render_my_dogs(update, alert=f"⭐ {dog.name} مکس لوله")

        text = (
            f"<b>🍖 غذا برای {esc(dog.name)}</b>\n\n"
            f"امروز {fa_num(left)} غذای دیگه داری\n"
            "هر غذا همون لحظه خریده و خورده میشه\n\n"
            "کدومشو بدی؟"
        )
        markup = kb.feed_foods_kb(dog.id)
        await s.commit()

    await respond(update, text, markup)


async def feed_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, _, dog_id, food_key = parts(update)
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        dog = await s.get(Dog, int(dog_id))

        if not dog or dog.user_id != user.id:
            await s.commit()
            return await render_my_dogs(update, alert="❌ همچین سگی نداری")

        ok, msg, notes = await dog_svc.feed_dog(s, user, dog, food_key)
        left = dog_svc.feeds_left(user)
        cash = user.cash
        await s.commit()

    if not ok:
        return await render_dog_card(update, dog, alert=msg)

    # غذا از همون کارت سگ داده میشه — برمی‌گردیم همونجا
    extra = f"{msg}\n💵 نقدینگی {fa_num(cash)}TP"
    if notes:
        extra += "\n" + "\n".join(notes)
    await render_dog_card(update, dog, alert="🍖 نوش جون", extra=extra)
