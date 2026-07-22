"""فروشگاه: چهار بخش + غذای سگ، هم منوی اینلاین هم دستور متنی"""

from telegram import Update
from telegram.ext import ContextTypes

import config
from database import session_scope
from handlers.common import parts, respond
from keyboards import keyboards as kb
from services import combat, dogs as dog_svc, farming, shop_svc, users
from utils import esc, fa_num, money, money_tp


# ───────── متن‌ها ─────────

def _sections_text(cash: int, level: int) -> str:
    return (
        "<b>🛒 فروشگاه زیرزمینی</b>\n\n"
        f"💵 نقدینگی {money(cash)}\n"
        f"🌟 سطح: {fa_num(level)}\n\n"
        "🔪 سلاح‌ها: قدرت حمله\n"
        "🛡 زره‌ها: قدرت دفاع\n"
        "🌱 بذرها: با کاشتنشون پول خوبی به چنگ میزنی\n"
        "🐕 سگ‌ها: بادیگارد شخصی\n"
        "🍖 غذای سگ: باهاش سگتو قویتر کن"
    )


async def _section_text(session, user, kind: str) -> str:
    if kind == "weap":
        return (
            "<b>🔪 بخش سلاح‌ها</b>\n\n"
            "هر سلاح یه Attack مشخص داره\n"
            "فقط بهترین سلاحت رو استت حساب میشه\n\n"
            "💡 برای خرید روی جنس کلیک کنید یا از دستور «خرید [اسم سلاح]» مثلا «خرید چاقو» استفاده کنید"
        )
    if kind == "arm":
        return (
            "<b>🛡 بخش زره‌ها</b>\n\n"
            "زره خسارت وارده رو کم می‌کنه\n"
            "فقط بهترین زرهت رو استت حساب میشه\n\n"
            "💡 برای خرید روی جنس کلیک کنید یا از دستور «خرید [اسم زره]» مثلا «خرید جلیقه سنگین» استفاده کنید\n\n"
            f"👑 {config.ARMORS['legend']['name']}:\n"
            f"{esc(config.ARMORS['legend']['desc'])}"
        )
    if kind == "seed":
        stock = await farming.get_stock(session, user.id)
        have = "\n".join(
            f"🌾 {config.SEEDS[k]['name']} ×{fa_num(v)}"
            for k, v in stock.items() if v > 0
        )
        return (
            "<b>🌱 بخش بذرها</b>\n\n"
            "صبر کن تا بذرها رشد کنن، بعدش میتونی برداشت کنی\n\n"
            f"📦 انبارت:\n{have or '▫️ خالیه'}\n\n"
            "💡 کاشت با دستور «کاشت ماری جوانا» هم میشه"
        )
    if kind == "dog":
        return (
            "<b>🐕 بخش سگ‌ها</b>\n\n"
            "سگ‌ها به قدرت حمله تو اضافه میشن\n"
            f"حداکثر {fa_num(config.MAX_DOGS)} سگ می‌تونی داشته باشی\n\n"
            "برای خرید روی سگ مورد نظر کلیک کنید یا از دستور «خرید سگ [نژاد] [اسم موردنظر]» استفاده کنید\n\n"
            "👑 گرگ سیاه شبح می‌تواند تا 30٪ از دفاع حریف را کاهش دهد و تا 10٪ غرامت بیشتری از حریف دریافت کند، با هر لول‌آپ به این مقدار نزدیک‌تر می‌شه"
        )
    if kind == "food":
        return (
            "<b>🍖 بخش غذای سگ</b>\n\n"
            f"هر سگ روزی فقط {fa_num(config.DOG_FEED_PER_DAY)} بار می‌تونه غذا دریافت کنه\n"
            "هر غذا مقدار مشخص XP به سگ میده و سگت رو لول آپ میکنه\n\n"
            "غذا همون لحظه خریده و خورده میشه\n"
            "برو تو «سگ‌های من» و دکمه 🍖 رو بزن"
        )
    return "❌ همچین بخشی نیس"


# ───────── نمایش ─────────

async def render_section(update: Update, kind: str, alert: str | None = None) -> None:
    """رندر یه بخش شاپ، بدون تکیه بر callback_data"""
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        text = await _section_text(s, user, kind)

        if kind == "weap":
            markup = kb.shop_weap_kb(user, set(await users.get_item_keys(s, user.id)))
        elif kind == "arm":
            markup = kb.shop_arm_kb(user, set(await users.get_item_keys(s, user.id)))
        elif kind == "seed":
            markup = kb.shop_seed_kb(user, await farming.get_stock(s, user.id))
        elif kind == "dog":
            user_dogs = await dog_svc.get_user_dogs(s, user.id)
            markup = kb.shop_dog_kb(user, {d.dog_key for d in user_dogs}, len(user_dogs))
        elif kind == "food":
            markup = kb.shop_food_kb()
        else:
            await s.commit()
            return await shop_cb(update, None)
        await s.commit()

    await respond(update, text, markup, alert=alert)


async def shop_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        text = _sections_text(user.cash, user.level)
        await s.commit()
    await respond(update, text, kb.shop_sections_kb())


async def section_cb(update: Update, context: ContextTypes.DEFAULT_TYPE, alert: str | None = None) -> None:
    await render_section(update, parts(update)[2], alert=alert)


# ───────── خرید (اینلاین) ─────────

async def buy_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, _, kind, key = parts(update)
    item = (shop_svc.CATALOGS.get(kind) or {}).get(key) or config.DOGS.get(key)
    if not item:
        return await shop_cb(update, context)

    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        cash = user.cash
        await s.commit()

    emoji = shop_svc.KIND_EMOJI.get(kind, "🛒")
    stat_lines = ""
    if kind == "weap":
        stat_lines = f"📈 قدرت حمله +{fa_num(item['attack'])}\n"
    elif kind == "arm":
        stat_lines = f"📈 دفاع +{fa_num(item['defense'])}\n"
    elif kind == "seed":
        stat_lines = (
            f"⏱ رشد {fa_num(item['grow_min'])} دقیقه\n"
            f"💰 فروش {money_tp(item['sell'])}\n"
        )
    elif kind == "dog":
        stat_lines = (
            f"🐾 نژاد {esc(item['breed'])}\n"
            f"💪 قدرت حمله {fa_num(item['attack'])}\n"
            f"🎖 {esc(item['ability'])}\n"
            f"📛 بعد از پرداخت اسمشو ازت می‌پرسم\n"
        )

    text = (
        "<b>🧾 فاکتور خرید</b>\n\n"
        f"{emoji} {esc(item['name'])}\n"
        f"{stat_lines}"
        f"💸 قیمت {money(item['price'])}\n"
        f"💵 بعد خرید {money(max(0, cash - item['price']))} برات میمونه\n\n"
        "معامله‌ست؟"
    )
    await respond(update, text, kb.confirm_kb(f"cf:shop:buy:{kind}:{key}"))


async def buy_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, _, _, kind, key = parts(update)
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        _, alert = await shop_svc.purchase(s, user, kind, key)
        await s.commit()
    # توجه: CallbackQuery تلگرام قابل تغییر نیس، به جای دست‌کاری data بخش رو مستقیم رندر می‌کنیم
    await render_section(update, kind, alert=alert)
