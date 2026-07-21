"""
کیبوردهای اینلاین با استایل رنگی تلگرام
primary = آبی (اکشن‌های اصلی) | success = سبز (تایید) | danger = قرمز (لغو)

ساختار callback_data یکدسته: «بخش:اکشن:پارتامترها»
مسیر تایید اکشن‌های مهم با پیشوند cf: اجرا میشه | cl همیشه لغوه
تایید دستورهای متنی گروه با پیشوند txcf: و id کاربر — فقط خودش بتونه تایید کنه

menu:home | menu:profile | menu:farm | menu:shop | menu:attack | menu:rank | menu:dogs
farm:buy                    → cf:farm:buy
farm:plant:<plot_id>        → انتخاب بذر از انبار
farm:plant:<plot_id>:<seed> → cf:plant:<plot_id>:<seed>
farm:hv                     → برداشت همه آماده‌ها (کولدون ۲ دقیقه)
farm:up:<plot_id>           → cf:farm:up:<plot_id>
shop:sec:<kind>             → بخش‌های شاپ: weap | arm | seed | dog | food
shop:buy:<kind>:<key>       → cf:shop:buy:<kind>:<key>
txcf:<kind>:<key>:<tg_id>   → تایید خرید دستور متنی (فقط خودش)
dogs:feed:<dog_id>          → انتخاب غذا → dogs:feed:<dog_id>:<food> → cf:feed:<dog_id>:<food>
att:find                    → cf:att:<target_id>
noop:<context>              → دکمه‌های اطلاعاتی
"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import config
from models import Dog, Plot, User
from services import economy
from services.dogs import dog_xp_need
from utils import fa_dur, fa_num, money_tp

PRIMARY = "primary"
SUCCESS = "success"
DANGER = "danger"

# یوزرنیم ربات موقع استارت ست میشه — برای دکمه «افزودن به گروه»
BOT_USERNAME = ""


def _btn(text: str, data: str, style: str | None = None) -> InlineKeyboardButton:
    kwargs = {"callback_data": data}
    if style:
        kwargs["style"] = style
    return InlineKeyboardButton(text, **kwargs)


# ───────── عمومی ─────────

def main_menu_kb() -> InlineKeyboardMarkup:
    rows = [
        [_btn("🏠 پروفایل", "menu:profile", PRIMARY),
         _btn("🌱 مزرعه من", "menu:farm", PRIMARY)],
        [_btn("🛒 فروشگاه", "menu:shop", PRIMARY),
         _btn("⚔️ حمله", "menu:attack", PRIMARY)],
        [_btn("🐕 سگ‌های من", "menu:dogs", PRIMARY),
         _btn("📊 رتبه‌بندی", "menu:rank", PRIMARY)],
    ]
    if BOT_USERNAME:
        rows.append([InlineKeyboardButton(
            "➕ افزودن به گروه",
            url=f"https://t.me/{BOT_USERNAME}?startgroup=true",
        )])
    return InlineKeyboardMarkup(rows)


def home_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[_btn("🏠 منوی اصلی", "menu:home", PRIMARY)]])


def confirm_kb(confirm_data: str) -> InlineKeyboardMarkup:
    """کیبورد تایید استاندارد — تایید سبز | لغو قرمز"""
    return InlineKeyboardMarkup([[
        _btn("✅ تایید", confirm_data, SUCCESS),
        _btn("❌ لغو", "cl", DANGER),
    ]])


def tx_confirm_kb(kind: str, key: str, tg_id: int) -> InlineKeyboardMarkup:
    """تایید خرید دستور متنی — id کاربر داخل دیتا ست میشه که غریبه نتونه بزنه"""
    return InlineKeyboardMarkup([[
        _btn("✅ تایید", f"txcf:{kind}:{key}:{tg_id}", SUCCESS),
        _btn("❌ لغو", f"txcl:{tg_id}", DANGER),
    ]])


def tx_attack_kb(target_id: int, owner_tg: int) -> InlineKeyboardMarkup:
    """تایید حمله با ریپلای — فقط مهاجم می‌تونه تایید یا لغو کنه"""
    return InlineKeyboardMarkup([[
        _btn("✅ تایید", f"txatt:{target_id}:{owner_tg}", SUCCESS),
        _btn("❌ لغو", f"txcl:{owner_tg}", DANGER),
    ]])


def admin_kb() -> InlineKeyboardMarkup:
    """پنل ساده ادمین"""
    return InlineKeyboardMarkup([
        [_btn("💵 +۱۰٬۰۰۰ TP", "adm:cash:10000", SUCCESS),
         _btn("💵 +۱۰۰٬۰۰۰ TP", "adm:cash:100000", SUCCESS)],
        [_btn("✨ +۱۰۰ XP", "adm:xp:100", PRIMARY),
         _btn("✨ +۱٬۰۰۰ XP", "adm:xp:1000", PRIMARY)],
        [_btn("🏠 منوی اصلی", "menu:home", PRIMARY)],
    ])


# ───────── پروفایل ─────────

def profile_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [_btn("🔃 رفرش", "menu:profile", PRIMARY)],
        [_btn("🏠 منوی اصلی", "menu:home", PRIMARY)],
    ])


# ───────── مزرعه ─────────

def farm_kb(user: User, plots: list[Plot], next_price: int, ready_count: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []

    for i, plot in enumerate(plots, 1):
        state, left = plot.current_status()
        rows.append([_btn(f"🗺 زمین {fa_num(i)} | لول {fa_num(plot.level)}", f"noop:plot:{plot.id}")])

        actions: list[InlineKeyboardButton] = []
        if state == "empty":
            actions.append(_btn("🌱 کاشت", f"farm:plant:{plot.id}"))
        elif state == "growing":
            actions.append(_btn(f"⏳ {fa_dur(left)}", "noop:grow"))
        else:
            actions.append(_btn("✅ آماده", "noop:ready"))

        if plot.level < config.PLOT_MAX_LEVEL:
            actions.append(_btn(f"⬆️ آپگرید | {money_tp(economy.upgrade_price(plot.level))}", f"farm:up:{plot.id}", PRIMARY))
        else:
            actions.append(_btn("⭐ مکس لول", "noop:maxplot"))
        rows.append(actions)

    if ready_count:
        rows.append([_btn(f"📦 برداشت همه آماده‌ها ({fa_num(ready_count)})", "farm:hv", SUCCESS)])

    if len(plots) < config.MAX_PLOTS:
        req = economy.plot_required_level(len(plots))
        if user.level >= req:
            rows.append([_btn(f"🛒 خرید زمین جدید | {money_tp(next_price)}", "farm:buy", PRIMARY)])
        else:
            rows.append([_btn(f"🔒 زمین بعدی لول {fa_num(req)} می‌خواد", "noop:lock", DANGER)])
    else:
        rows.append([_btn("🏡 همه زمین‌ها رو داری", "noop:maxplots")])

    rows.append([_btn("🏠 منوی اصلی", "menu:home", PRIMARY)])
    return InlineKeyboardMarkup(rows)


def seeds_kb(user: User, plot: Plot, stock: dict[str, int]) -> InlineKeyboardMarkup:
    """انتخاب بذر از انبار برای کاشت روی زمین"""
    rows: list[list[InlineKeyboardButton]] = []
    for key, seed in config.SEEDS.items():
        have = stock.get(key, 0)
        if have <= 0:
            continue
        label = (
            f"{seed['name']} ×{fa_num(have)}"
            f" | ⏱ {fa_dur(economy.crop_grow_seconds(key, plot.level))}"
            f" | 💰 {money_tp(economy.crop_yield(key, plot.level, user.level))}"
        )
        rows.append([_btn(label, f"farm:plant:{plot.id}:{key}")])
    rows.append([_btn("🌾 بذر ندارم | برم شاپ", "shop:sec:seed", PRIMARY)])
    rows.append([_btn("🔙 برگرد به مزرعه", "menu:farm", PRIMARY)])
    return InlineKeyboardMarkup(rows)


# ───────── فروشگاه ─────────

def shop_sections_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [_btn("🔪 سلاح‌ها", "shop:sec:weap", PRIMARY),
         _btn("🛡 زره‌ها", "shop:sec:arm", PRIMARY)],
        [_btn("🌱 بذرها", "shop:sec:seed", PRIMARY),
         _btn("🐕 سگ‌ها", "shop:sec:dog", PRIMARY)],
        [_btn("🍖 غذای سگ", "shop:sec:food", PRIMARY)],
        [_btn("🏠 منوی اصلی", "menu:home", PRIMARY)],
    ])


def _buy_row(key: str, item: dict, owned: bool, locked_level: int | None) -> list[InlineKeyboardButton]:
    if owned:
        return [_btn(f"✅ {item['name']}", "noop:own")]
    if locked_level is not None:
        return [_btn(f"🔒 {item['name']} | لول {fa_num(locked_level)}", "noop:lock", DANGER)]
    return [_btn(f"{item['name']} | {money_tp(item['price'])}", f"shop:buy:ROW:{key}", PRIMARY)]


def shop_weap_kb(user: User, owned: set[str]) -> InlineKeyboardMarkup:
    rows = []
    for key, w in config.WEAPONS.items():
        locked = w["min_level"] if user.level < w["min_level"] else None
        row = _buy_row(key, w, key in owned, locked)
        if w["min_level"] <= user.level and key not in owned:
            row[0] = _btn(f"🔪 {w['name']} | +{fa_num(w['attack'])} | {money_tp(w['price'])}", f"shop:buy:weap:{key}", PRIMARY)
        rows.append(row)
    rows.append([_btn("🔙 بخش‌های شاپ", "menu:shop", PRIMARY)])
    return InlineKeyboardMarkup(rows)


def shop_arm_kb(user: User, owned: set[str]) -> InlineKeyboardMarkup:
    rows = []
    for key, a in config.ARMORS.items():
        locked = a["min_level"] if user.level < a["min_level"] else None
        row = _buy_row(key, a, key in owned, locked)
        if a["min_level"] <= user.level and key not in owned:
            row[0] = _btn(f"🛡 {a['name']} | +{fa_num(a['defense'])} | {money_tp(a['price'])}", f"shop:buy:arm:{key}", PRIMARY)
        rows.append(row)
    rows.append([_btn("🔙 بخش‌های شاپ", "menu:shop", PRIMARY)])
    return InlineKeyboardMarkup(rows)


def shop_seed_kb(user: User, stock: dict[str, int]) -> InlineKeyboardMarkup:
    rows = []
    for key, s in config.SEEDS.items():
        if user.level < s["min_level"]:
            rows.append([_btn(f"🔒 {s['name']} | لول {fa_num(s['min_level'])}", "noop:lock", DANGER)])
        else:
            have = stock.get(key, 0)
            have_txt = f" | 📦 ×{fa_num(have)}" if have else ""
            rows.append([_btn(
                f"🌱 {s['name']} | {money_tp(s['price'])}{have_txt}",
                f"shop:buy:seed:{key}", PRIMARY,
            )])
    rows.append([_btn("🔙 بخش‌های شاپ", "menu:shop", PRIMARY)])
    return InlineKeyboardMarkup(rows)


def shop_dog_kb(user: User, owned_keys: set[str], dogs_count: int) -> InlineKeyboardMarkup:
    rows = []
    for key, d in config.DOGS.items():
        if key in owned_keys:
            rows.append([_btn(f"✅ {d['name']}", "noop:own")])
        elif user.level < d["min_level"]:
            rows.append([_btn(f"🔒 {d['name']} | لول {fa_num(d['min_level'])}", "noop:lock", DANGER)])
        else:
            crown = "👑 " if d.get("rare") else ""
            rows.append([_btn(
                f"{crown}🐕 {d['name']} | +{fa_num(d['attack'])} | {money_tp(d['price'])}",
                f"shop:buy:dog:{key}", PRIMARY,
            )])
    rows.append([_btn("🔙 بخش‌های شاپ", "menu:shop", PRIMARY)])
    return InlineKeyboardMarkup(rows)


def shop_food_kb() -> InlineKeyboardMarkup:
    rows = []
    for key, f in config.DOG_FOODS.items():
        rows.append([_btn(
            f"{f['name']} | +{fa_num(f['xp'])} XP | {money_tp(f['price'])}",
            "noop:feedinfo",
        )])
    rows.append([_btn("🔙 بخش‌های شاپ", "menu:shop", PRIMARY)])
    return InlineKeyboardMarkup(rows)


# ───────── سگ‌های من ─────────

def my_dogs_kb(dogs: list[Dog]) -> InlineKeyboardMarkup:
    rows = []
    for d in dogs:
        crown = "👑 " if d.cfg.get("rare") else ""
        rows.append([_btn(f"{crown}🐕 {d.name} | لول {fa_num(d.level)}", "noop:doginfo")])
        need = dog_xp_need(d.level)
        rows.append([_btn(f"🍖 غذا بده ({fa_num(d.xp)}/{fa_num(need)} XP)", f"dogs:feed:{d.id}", SUCCESS)])
    if len(dogs) < config.MAX_DOGS:
        rows.append([_btn("🛒 خرید سگ جدید", "shop:sec:dog", PRIMARY)])
    rows.append([_btn("🏠 منوی اصلی", "menu:home", PRIMARY)])
    return InlineKeyboardMarkup(rows)


def feed_foods_kb(dog_id: int) -> InlineKeyboardMarkup:
    rows = []
    for key, f in config.DOG_FOODS.items():
        rows.append([_btn(
            f"{f['name']} | +{fa_num(f['xp'])} XP | {money_tp(f['price'])}",
            f"cf:feed:{dog_id}:{key}", SUCCESS,
        )])
    rows.append([_btn("🔙 برگرد به سگ‌ها", "menu:dogs", PRIMARY)])
    return InlineKeyboardMarkup(rows)


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
