"""فروشگاه سلاح و زره"""

from telegram import Update
from telegram.ext import ContextTypes

import config
from database import session_scope
from handlers.common import parts, respond
from keyboards import keyboards as kb
from models import InventoryItem
from services import combat, users
from utils import esc, fa_num, money

_TYPE_INFO = {
    "weapon": ("🗡", "قدرت حمله", "attack"),
    "armor": ("🛡", "دفاع", "defense"),
}


async def render_shop(update: Update, alert: str | None = None) -> None:
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        users.apply_energy_regen(user)
        keys = await users.get_item_keys(s, user.id)
        atk, dfn = combat.combat_stats(user, keys)

        text = (
            "<b>🛒 فروشگاه زیرزمینی</b>\n\n"
            f"💵 نقدینگی {money(user.cash)}\n"
            f"💪 حمله {fa_num(atk)} | 🛡 دفاع {fa_num(dfn)}\n\n"
            "💡 بهترین سلاح و بهترین زرهت حساب میشه\n"
            "روی جنس بزن تا فاکتورش بیاد"
        )
        markup = kb.shop_kb(user, set(keys))
        await s.commit()

    await respond(update, text, markup, alert=alert)


async def shop_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await render_shop(update)


async def buy_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    key = parts(update)[2]
    item = config.SHOP_ITEMS.get(key)
    if not item:
        return await render_shop(update, alert="❌ همچین جنسی نیس")

    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        keys = await users.get_item_keys(s, user.id)
        cash = user.cash
        owned = key in keys
        await s.commit()

    if owned:
        return await render_shop(update, alert="اینو داری که داداش")

    emoji, label, field = _TYPE_INFO[item["type"]]
    text = (
        "<b>🧾 فاکتور خرید</b>\n\n"
        f"{emoji} {esc(item['name'])}\n"
        f"📈 {label} +{fa_num(item[field])}\n"
        f"💸 قیمت {money(item['price'])}\n"
        f"💵 بعد خرید {money(max(0, cash - item['price']))} برات میمونه\n\n"
        "معامله‌ست؟"
    )
    await respond(update, text, kb.confirm_kb(f"cf:shop:buy:{key}"))


async def buy_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    key = parts(update)[3]
    item = config.SHOP_ITEMS.get(key)
    if not item:
        return await render_shop(update, alert="❌ همچین جنسی نیس")

    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        keys = await users.get_item_keys(s, user.id)

        if key in keys:
            alert = "اینو داری که داداش"
        elif user.cash < item["price"]:
            alert = "❌ پولت کافی نیس رفیق"
        else:
            user.cash -= item["price"]
            s.add(InventoryItem(user_id=user.id, item_key=key))
            alert = f"🎉 {item['name']} مالت شد"
        await s.commit()

    await render_shop(update, alert=alert)
