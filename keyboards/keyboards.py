"""
کیبوردهای اینلاین با استایل رنگی تلگرام
primary = آبی (اکشن‌های اصلی) | success = سبز (تایید) | danger = قرمز (لغو)

ساختار callback_data ها یکدسته: «بخش:اکشن:پارتامترها»
مسیر تایید هر اکشن مهم با پیشوند cf: اجرا میشه و کلید cl همیشه لغوه
menu:home | menu:farm | menu:shop | menu:attack | menu:rank | menu:profile
farm:buy → cf:farm:buy
farm:plant:<plot_id> → farm:plant:<plot_id>:<crop> → cf:plant:<plot_id>:<crop>
farm:hv:<plot_id>     (برداشت بدون هزینه‌ست پس تایید نمی‌خواد)
farm:up:<plot_id>    → cf:farm:up:<plot_id>
shop:buy:<item_key>  → cf:shop:buy:<item_key>
att:find             → cf:att:<target_id>
noop:<context>       (دکمه‌های اطلاعاتی)
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import config
from models import Plot, User
from services import economy
from utils import fa_dur, fa_num, money_tp

PRIMARY = "primary"
SUCCESS = "success"
DANGER = "danger"


def _btn(text: str, data: str, style: str | None = None) -> InlineKeyboardButton:
    kwargs = {"callback_data": data}
    if style:
        kwargs["style"] = style
    return InlineKeyboardButton(text, **kwargs)


# ───────── عمومی ─────────

def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [_btn("🏠 پروفایل", "menu:profile", PRIMARY),
         _btn("🌱 مزرعه من", "menu:farm", PRIMARY)],
        [_btn("🛒 فروشگاه", "menu:shop", PRIMARY),
         _btn("⚔️ حمله", "menu:attack", PRIMARY)],
        [_btn("📊 رتبه‌بندی", "menu:rank", PRIMARY)],
    ])


def home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[_btn("🏠 منوی اصلی", "menu:home", PRIMARY)]])


def confirm_kb(confirm_data: str) -> InlineKeyboardMarkup:
    """کیبورد تایید استاندارد — تایید سبز | لغو قرمز"""
    return InlineKeyboardMarkup([[
        _btn("✅ تایید", confirm_data, SUCCESS),
        _btn("❌ لغو", "cl", DANGER),
    ]])


# ───────── پروفایل ─────────

def profile_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [_btn("🔃 رفرش", "menu:profile", PRIMARY)],
        [_btn("🏠 منوی اصلی", "menu:home", PRIMARY)],
    ])


# ───────── مزرعه ─────────

def farm_kb(user: User, plots: list[Plot], next_price: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    for i, plot in enumerate(plots, 1):
        state, left = plot.current_status()
        rows.append([_btn(f"🗺 زمین {fa_num(i)} | لول {fa_num(plot.level)}", f"noop:plot:{plot.id}")])

        actions: list[InlineKeyboardButton] = []
        if state == "empty":
            actions.append(_btn("🌱 کاشت", f"farm:plant:{plot.id}"))
        elif state == "growing":
            actions.append(_btn(f"⏳ {fa_dur(left)}", f"farm:hv:{plot.id}"))
        else:  # ready
            actions.append(_btn("📦 برداشت", f"farm:hv:{plot.id}", SUCCESS))

        if plot.level < config.PLOT_MAX_LEVEL:
            actions.append(_btn(f"⬆️ آپگرید | {money_tp(economy.upgrade_price(plot.level))}", f"farm:up:{plot.id}", PRIMARY))
        else:
            actions.append(_btn("⭐ مکس لول", "noop:maxplot"))
        rows.append(actions)

    if len(plots) < config.MAX_PLOTS:
        rows.append([_btn(f"🛒 خرید زمین جدید | {money_tp(next_price)}", "farm:buy", PRIMARY)])
    else:
        rows.append([_btn("🏡 همه زمین‌ها رو داری", "noop:maxplots")])

    rows.append([_btn("🏠 منوی اصلی", "menu:home", PRIMARY)])
    return InlineKeyboardMarkup(rows)


def crops_kb(user: User, plot: Plot) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for key, crop in config.CROPS.items():
        if economy.is_crop_unlocked(key, user.level):
            label = (
                f"{crop['name']} | 💸 {fa_num(crop['cost'])}"
                f" | ⏱ {fa_dur(economy.crop_grow_seconds(key, plot.level))}"
                f" | 💰 {fa_num(economy.crop_yield(key, plot.level))}"
            )
            rows.append([_btn(label, f"farm:plant:{plot.id}:{key}")])
        else:
            rows.append([_btn(f"🔒 {crop['name']} | لول {fa_num(crop['min_level'])} می‌خواد", "noop:lock")])
    rows.append([_btn("🔙 برگرد به مزرعه", "menu:farm", PRIMARY)])
    return InlineKeyboardMarkup(rows)


# ───────── فروشگاه ─────────

def shop_kb(user: User, owned: set[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [[_btn("— 🗡 سلاح‌ها —", "noop:winfo")]]

    for key, item in config.SHOP_ITEMS.items():
        if item["type"] != "weapon":
            continue
        rows.append(_shop_row(key, item, owned))

    rows.append([_btn("— 🛡 زره‌ها —", "noop:ainfo")])
    for key, item in config.SHOP_ITEMS.items():
        if item["type"] != "armor":
            continue
        rows.append(_shop_row(key, item, owned))

    rows.append([_btn("🏠 منوی اصلی", "menu:home", PRIMARY)])
    return InlineKeyboardMarkup(rows)


def _shop_row(key: str, item: dict, owned: set[str]) -> list[InlineKeyboardButton]:
    if key in owned:
        return [_btn(f"✅ {item['name']}", "noop:own")]
    bonus = item.get("attack") or item.get("defense")
    sign = "🗡" if item["type"] == "weapon" else "🛡"
    label = f"{item['name']} | {sign} +{fa_num(bonus)} | {money_tp(item['price'])}"
    return [_btn(label, f"shop:buy:{key}", PRIMARY)]


# ───────── حمله ─────────

def attack_home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [_btn("🎯 پیدا کردن هدف", "att:find", PRIMARY)],
        [_btn("🏠 منوی اصلی", "menu:home", PRIMARY)],
    ])


def attack_target_kb(target_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [_btn("✅ تایید", f"cf:att:{target_id}", SUCCESS),
         _btn("❌ لغو", "cl", DANGER)],
        [_btn("🔄 یه هدف دیگه", "att:find", PRIMARY)],
    ])


def attack_result_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [_btn("⚔️ بخش حمله", "menu:attack", PRIMARY),
         _btn("🏠 منوی اصلی", "menu:home", PRIMARY)],
    ])


# ───────── رتبه‌بندی ─────────

def rank_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [_btn("🔃 رفرش", "menu:rank", PRIMARY)],
        [_btn("🏠 منوی اصلی", "menu:home", PRIMARY)],
    ])
