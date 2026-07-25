"""فروشگاه: سلاح | زره | ارتقای سلاح/زره | آرتیفکت | منابع | بذر | سگ | غذا
ظاهر همه بخش‌ها باکسی و تمیزه، سبز یعنی قابل خرید و قرمز یعنی قفل"""

from telegram import Update
from telegram.ext import ContextTypes

import config
from database import session_scope
from handlers import dogs as dogs_h
from handlers.common import parts, respond
from keyboards import keyboards as kb
from services import combat, dogs as dog_svc, economy, farming, shop_svc, users
from utils import esc, fa_num, money, money_tp

SEP = "━━━━━━━━━━━━━━"


# ───────── متن‌ها ─────────

def _sections_text(cash: int, level: int) -> str:
    return (
        "<b>🛒 فروشگاه</b>\n\n"
        f"💵 نقدینگی {money(cash)}\n"
        f"🌟 سطح {fa_num(level)}\n\n"
        "🔫 سلاح و زره | ⬆️ ارتقاشون\n"
        "🧿 آرتیفکت‌های آخر بازی\n"
        "🎒 چوب و آهن | 🌱 بذر | 🐕 سگ | 🍖 غذا"
    )


def _weap_text(user) -> str:
    """باکس هر سلاح: نام | دمیج | آهن | قیمت | وضعیت"""
    lines = ["<b>🛒 فروشگاه</b>", "", "🔫 سلاح‌ها", "", "برای خرید روی آیتم موردنظر بزن", ""]
    for key, w in config.WEAPONS.items():
        locked = user.level < w["min_level"]
        lines += [SEP, ""]
        lines.append(f"🔒 {w['name']} (قفل)" if locked else f"🔫 {w['name']}")
        lines.append(f"💥 دمیج {fa_num(w['attack'])}")
        lines.append(f"🪙 هزینه: ⛏️ {fa_num(w['iron'])} آهن + 💰 {money(w['price'])}")
        if locked:
            lines.append(f"⭕️ بازگشایی در سطح {fa_num(w['min_level'])}")
        lines.append("")
    lines.append(SEP)
    return "\n".join(lines)


def _arm_text(user) -> str:
    lines = ["<b>🛒 فروشگاه</b>", "", "🛡 زره‌ها", "", "برای خرید روی آیتم موردنظر بزن", ""]
    for a in config.ARMORS.values():
        locked = user.level < a["min_level"]
        lines += [SEP, ""]
        lines.append(f"🔒 {a['name']} (قفل)" if locked else f"🛡 {a['name']}")
        lines.append(f"🛡 دفاع {fa_num(a['defense'])}")
        lines.append(f"💰 {money(a['price'])}")
        if locked:
            lines.append(f"⭕️ بازگشایی در سطح {fa_num(a['min_level'])}")
        lines.append("")
    lines.append(SEP)
    return "\n".join(lines)


def _dog_text() -> str:
    """فقط ویژگی اصلی هر نژاد، بدون توضیح طولانی"""
    lines = ["<b>🛒 فروشگاه</b>", "", "🐕 سگ‌ها", "", "برای خرید روی سگ موردنظر بزن", ""]
    for key, d in config.DOGS.items():
        crown = "👑 " if d.get("rare") else ""
        lines += [SEP, ""]
        lines.append(f"{crown}🐕 {d['name']}")
        lines.append(d["trait_line"])
        lines.append(f"💰 {money_tp(d['price'])}")
        lines.append("")
    lines.append(SEP)
    lines.append("")
    lines.append(f"هر نژاد فقط شخصیت‌های مخصوص خودش رو می‌گیره")
    lines.append("سگ‌ها از نبرد تجربه می‌گیرن و با لول قوی‌تر میشن")
    return "\n".join(lines)


def _arti_text(user) -> str:
    lines = ["<b>🛒 فروشگاه</b>", "", "🧿 آرتیفکت‌ها", "", "آیتم‌های کمیاب آخر بازی", ""]
    for key, a in config.ARTIFACTS.items():
        locked = user.level < config.ARTIFACT_MIN_LEVEL
        lines += [SEP, ""]
        lines.append(f"🔒 {a['emoji']} {a['name']} (قفل)" if locked else f"{a['emoji']} {a['name']}")
        lines.append(a["line"])
        lines.append(f"💰 {money(a['price'])}")
        if locked:
            lines.append(f"⭕️ بازگشایی در سطح {fa_num(config.ARTIFACT_MIN_LEVEL)}")
        lines.append("")
    lines.append(SEP)
    return "\n".join(lines)


def _res_text(user) -> str:
    from services import resources as res_svc
    return "\n".join([
        "<b>🛒 فروشگاه</b>",
        "",
        "🎒 منابع",
        "",
        f"🪵 چوب {fa_num(user.wood)} از {fa_num(res_svc.wood_cap(user))}",
        f"⛏️ آهن {fa_num(user.iron)} از {fa_num(res_svc.iron_cap(user))}",
        "",
        "چوب و آهن از کنده‌کاری، شاپ و کارخانه به دست میان",
        "برای خرید روی پک موردنظر بزن",
    ])


def _gear_up_text(kind: str, owned_lvls: dict[str, int], user) -> str:
    catalog = economy.gear_catalog(kind)
    emoji = "🔫" if kind == "weap" else "🛡"
    stat_emoji = "💥" if kind == "weap" else "🛡"
    stat_name = "دمیج" if kind == "weap" else "دفاع"
    items = [(k, lv) for k, lv in owned_lvls.items() if k in catalog]
    lines = [f"<b>⬆️ ارتقای {'سلاح' if kind == 'weap' else 'زره'}</b>", ""]
    if not items:
        lines.append(f"اول یه {'سلاح' if kind == 'weap' else 'زره'} بخر")
        lines.append("هر آیتم تا لول 5 ارتقا داره و هر لول استتش بیشتر میشه")
        return "\n".join(lines)
    lines.append("هر ارتقا تی‌پوینت و آهن می‌خواد")
    lines.append("")
    for key, lv in sorted(items, key=lambda x: -x[1]):
        item = catalog[key]
        lines.append(SEP)
        lines.append("")
        lines.append(f"{emoji} {item['name']} | لول {fa_num(lv)}")
        lines.append(f"{stat_emoji} {stat_name} {fa_num(economy.gear_stat(kind, key, lv))}")
        if lv >= config.GEAR_UPG_MAX:
            lines.append("👑 لول مکس")
        else:
            tp = economy.gear_upg_tp(kind, key, lv)
            iron = economy.gear_upg_iron(kind, key, lv)
            lines.append(f"⬆️ لول بعدی: {stat_name} {fa_num(economy.gear_stat(kind, key, lv + 1))}")
            lines.append(f"🪙 هزینه: 💰 {money(tp)} + ⛏️ {fa_num(iron)} آهن")
            req = economy.gear_upg_min_level(lv)
            if user.level < req:
                lines.append(f"⭕️ بازگشایی در سطح {fa_num(req)}")
        lines.append("")
    lines.append(SEP)
    return "\n".join(lines)


async def _section_text(session, user, kind: str) -> str:
    if kind == "weap":
        return _weap_text(user)
    if kind == "arm":
        return _arm_text(user)
    if kind == "arti":
        return _arti_text(user)
    if kind == "res":
        return _res_text(user)
    if kind in ("wup", "aup"):
        gkind = "weap" if kind == "wup" else "arm"
        lvls = {
            k: v for k, v in (await users.get_item_levels(session, user.id)).items()
            if k in economy.gear_catalog(gkind)
        }
        return _gear_up_text(gkind, lvls, user)
    if kind == "seed":
        stock = await farming.get_stock(session, user.id)
        have = "\n".join(
            f"🌾 {config.SEEDS[k]['name']} ×{fa_num(v)}"
            for k, v in stock.items() if v > 0
        )
        return (
            "<b>🌱 بذرها</b>\n\n"
            "صبر کن تا بذرها رشد کنن، بعدش برداشت کن\n\n"
            f"📦 انبارت:\n{have or '▫️ خالیه'}"
        )
    if kind == "dog":
        return _dog_text()
    if kind == "food":
        return (
            "<b>🍖 غذای سگ</b>\n\n"
            "غذا همون لحظه خریده و خورده میشه\n"
            "بنویس «تریاکی سگ‌های من» و دکمه 🍖 زیر سگت رو بزن"
        )
    return "❌ همچین بخشی نیس"


# ───────── نمایش ─────────

async def render_section(update: Update, kind: str, alert: str | None = None) -> None:
    """رندر یه بخش شاپ، بدون تکیه بر callback_data"""
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        text = await _section_text(s, user, kind)

        item_keys = set(await users.get_item_keys(s, user.id))
        if kind == "weap":
            markup = kb.shop_weap_kb(user, item_keys)
        elif kind == "arm":
            markup = kb.shop_arm_kb(user, item_keys)
        elif kind == "seed":
            markup = kb.shop_seed_kb(user, await farming.get_stock(s, user.id))
        elif kind == "dog":
            user_dogs = await dog_svc.get_user_dogs(s, user.id)
            markup = kb.shop_dog_kb(user, {d.dog_key for d in user_dogs}, len(user_dogs))
        elif kind == "food":
            markup = kb.shop_food_kb()
        elif kind == "res":
            markup = kb.shop_res_kb()
        elif kind == "arti":
            markup = kb.shop_arti_kb(user, item_keys)
        elif kind in ("wup", "aup"):
            gkind = "weap" if kind == "wup" else "arm"
            lvls = {
                k: v for k, v in (await users.get_item_levels(s, user.id)).items()
                if k in economy.gear_catalog(gkind)
            }
            markup = kb.gear_up_kb(gkind, lvls, user)
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

    # خرید پک منابع، بدون فاکتور با یه کلیک
    if kind == "res":
        async with session_scope() as s:
            user, _ = await users.get_or_create(s, update.effective_user)
            ok, alert = await shop_svc.purchase_resource(s, user, key)
            await s.commit()
        return await render_section(update, "res", alert=alert)

    item = (shop_svc.CATALOGS.get(kind) or {}).get(key) or config.DOGS.get(key)
    if not item:
        return await shop_cb(update, context)

    # خرید سگ فاکتور نداره، اول اسمش پرسیده میشه و بعد فاکتور تایید میاد
    if kind == "dog":
        async with session_scope() as s:
            user, _ = await users.get_or_create(s, update.effective_user)
            ok, alert = await dog_svc.hold_dog(s, user, key)
            await s.commit()
        if not ok:
            return await render_section(update, kind, alert=alert)
        return await respond(update, dogs_h.dog_name_question_text(item))

    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        cash, iron = user.cash, user.iron
        await s.commit()

    emoji = shop_svc.KIND_EMOJI.get(kind, "🛒")
    stat_lines = ""
    if kind == "weap":
        stat_lines = (
            f"💥 دمیج +{fa_num(item['attack'])}\n"
            f"⛏️ آهن {fa_num(item['iron'])} (الان {fa_num(iron)} تا داری)\n"
        )
    elif kind == "arm":
        stat_lines = f"🛡 دفاع +{fa_num(item['defense'])}\n"
    elif kind == "arti":
        stat_lines = f"{item['line']}\n"
    elif kind == "seed":
        stat_lines = (
            f"⏱ رشد {fa_num(item['grow_min'])} دقیقه\n"
            f"💰 فروش {money_tp(item['sell'])}\n"
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


# ───────── ارتقای سلاح و زره ⬆️ ─────────

async def gear_up_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, kind, key = parts(update)
    catalog = economy.gear_catalog(kind)
    item = catalog.get(key)
    if not item:
        return await shop_cb(update, context)

    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        lv = (await users.get_item_levels(s, user.id)).get(key)
        await s.commit()

    if lv is None:
        return await render_section(update, "wup" if kind == "weap" else "aup", alert="❌ اینو نداری")
    if lv >= config.GEAR_UPG_MAX:
        return await render_section(update, "wup" if kind == "weap" else "aup", alert="👑 لول مکسه")

    tp = economy.gear_upg_tp(kind, key, lv)
    iron = economy.gear_upg_iron(kind, key, lv)
    stat_name = "دمیج" if kind == "weap" else "دفاع"
    stat_emoji = "💥" if kind == "weap" else "🛡"
    text = (
        f"<b>⬆️ ارتقای {esc(item['name'])}</b>\n\n"
        f"از لول {fa_num(lv)} به لول {fa_num(lv + 1)}\n"
        f"{stat_emoji} {stat_name} {fa_num(economy.gear_stat(kind, key, lv))} ← {fa_num(economy.gear_stat(kind, key, lv + 1))}\n"
        f"💸 تی‌پوینت {money(tp)}\n"
        f"⛏️ آهن {fa_num(iron)}\n\n"
        "انجامش بدیم؟"
    )
    await respond(update, text, kb.gear_up_confirm_kb(kind, key))


async def gear_up_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, _, kind, key = parts(update)
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        from models import InventoryItem
        from sqlalchemy import select
        q = select(InventoryItem).where(
            InventoryItem.user_id == user.id, InventoryItem.item_key == key
        )
        row = (await s.execute(q)).scalar_one_or_none()
        if not row:
            ok, alert = False, "❌ اینو نداری"
        elif row.level >= config.GEAR_UPG_MAX:
            ok, alert = False, "👑 لول مکسه"
        else:
            req = economy.gear_upg_min_level(row.level)
            tp = economy.gear_upg_tp(kind, key, row.level)
            iron = economy.gear_upg_iron(kind, key, row.level)
            if user.level < req:
                ok, alert = False, f"🔒 لول {fa_num(req)} می‌خواد"
            elif user.cash < tp:
                ok, alert = False, "❌ تی‌پوینتت کافی نیس"
            elif user.iron < iron:
                ok, alert = False, f"⛏️ {fa_num(iron)} آهن می‌خواد و {fa_num(user.iron)} تا داری"
            else:
                user.cash -= tp
                user.iron -= iron
                row.level += 1
                item = economy.gear_catalog(kind)[key]
                alert = f"⬆️ {item['name']} رفت رو لول {fa_num(row.level)}"
        await s.commit()
    await render_section(update, "wup" if kind == "weap" else "aup", alert=alert)


async def gear_up_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, kind = parts(update)
    await render_section(update, "wup" if kind == "weap" else "aup")
