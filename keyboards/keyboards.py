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
menu:team | team:quests | team:mine | team:top | team:leave | team:disband
tmcf:<leave|disband>:<tg_id> → تایید ترک/انحلال تیم (فقط خودش)
dog:card:<dog_id>           → کارت آمار سگ (آمار [اسم])
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


def _btn(text: str, data: str, style: str | None = PRIMARY) -> InlineKeyboardButton:
    """پیش‌فرض همه دکمه‌ها آبیه مگر اینکه سبز یا قرمز گفته شده باشه"""
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
         _btn("🏴 تیم من", "menu:team", PRIMARY)],
        [_btn("🏦 بانک", "menu:bank", PRIMARY),
         _btn("📊 رتبه‌بندی", "menu:rank", PRIMARY)],
    ]
    if BOT_USERNAME:
        rows.append([InlineKeyboardButton(
            "➕ افزودن به گروه",
            url=f"https://t.me/{BOT_USERNAME}?startgroup=true",
            style=PRIMARY,
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


def tx_confirm_kb(kind: str, key: str, tg_id: int, dog_name: str | None = None) -> InlineKeyboardMarkup:
    """تایید خرید دستور متنی — id کاربر داخل دیتا ست میشه که غریبه نتونه بزنه"""
    data = f"txcf:{kind}:{key}:{tg_id}"
    if dog_name:
        safe = dog_name.replace(":", " ").strip()[:12]  # سقف بایت callback_data
        if safe:
            data += f":{safe}"
    return InlineKeyboardMarkup([[
        _btn("✅ تایید", data, SUCCESS),
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
        [_btn("💵 +10,000 TP", "adm:cash:10000", SUCCESS),
         _btn("💵 +100,000 TP", "adm:cash:100000", SUCCESS)],
        [_btn("✨ +100 XP", "adm:xp:100", PRIMARY),
         _btn("✨ +1,000 XP", "adm:xp:1000", PRIMARY)],
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
        if state == "building":
            actions.append(_btn(f"🔨 ساخت: {fa_dur(left)}", "noop:build"))
        elif state == "empty":
            actions.append(_btn("🌱 کاشت", f"farm:plant:{plot.id}"))
        elif state == "growing":
            actions.append(_btn(f"⏳ {fa_dur(left)}", "noop:grow"))
        else:
            actions.append(_btn("✅ آماده", "noop:ready"))

        if state != "building":
            if plot.level < config.PLOT_MAX_LEVEL:
                actions.append(_btn(f"⬆️ آپگرید | {money_tp(economy.upgrade_price(plot.level))}", f"farm:up:{plot.id}", PRIMARY))
            else:
                actions.append(_btn("⭐ مکس لول", "noop:maxplot"))
        rows.append(actions)

    if ready_count:
        rows.append([_btn(f"📦 برداشت همه آماده‌ها ({fa_num(ready_count)})", "farm:hv", SUCCESS)])

    if len(plots) < config.MAX_PLOTS:
        req = economy.plot_required_level(len(plots))
        build = economy.plot_build_seconds(len(plots))
        n_next = len(plots) + 1
        if user.level >= req:
            label = f"🛒 زمین {fa_num(n_next)} | {money_tp(next_price)}"
            label += f" | 🔨 {fa_dur(build)}" if build else ""
            rows.append([_btn(label, "farm:buy", PRIMARY)])
        else:
            rows.append([_btn(
                f"🔒 زمین {fa_num(n_next)} | {money_tp(next_price)} | لول {fa_num(req)}",
                "noop:lock", DANGER,
            )])
    else:
        rows.append([_btn("🏡 هر 5 زمین رو داری", "noop:maxplots")])

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
        rows.append([_btn(f"{crown}🐕 {d.name} | لول {fa_num(d.level)}", f"dog:card:{d.id}")])
        need = dog_xp_need(d.level)
        rows.append([_btn(f"🍖 غذا بده ({fa_num(d.xp)}/{fa_num(need)} XP)", f"dogs:feed:{d.id}", SUCCESS)])
    if len(dogs) < config.MAX_DOGS:
        rows.append([_btn("🛒 خرید سگ جدید", "shop:sec:dog", PRIMARY)])
    rows.append([_btn("🏠 منوی اصلی", "menu:home", PRIMARY)])
    return InlineKeyboardMarkup(rows)


def dog_card_kb(dog: Dog, feeds_left: int) -> InlineKeyboardMarkup:
    """کیبورد کارت آمار یه سگ — از همونجا میشه غذاش داد («آمار اصغر»)"""
    rows: list[list[InlineKeyboardButton]] = []
    if dog.level < config.DOG_MAX_LEVEL and feeds_left > 0:
        for key, f in config.DOG_FOODS.items():
            rows.append([_btn(
                f"🍖 {f['name']} | +{fa_num(f['xp'])} XP | {money_tp(f['price'])}",
                f"cf:feed:{dog.id}:{key}", SUCCESS,
            )])
    elif feeds_left <= 0:
        rows.append([_btn("🍖 سهمیه غذای امروزت تمومه", "noop:feedinfo", DANGER)])
    rows.append([_btn("🔙 سگ‌های من", "menu:dogs", PRIMARY)])
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


# ───────── تیم ─────────

def team_kb(is_owner: bool = False) -> InlineKeyboardMarkup:
    """کیبورد صفحه «تیم من»"""
    rows: list[list[InlineKeyboardButton]] = [
        [_btn("📜 کوئست‌های امروز", "team:quests", PRIMARY),
         _btn("⛏ کنده‌کاری تیمی", "team:mine", PRIMARY)],
        [_btn("🏗 ساختمان‌ها", "team:bld", PRIMARY),
         _btn("🏆 لیدربرد", "team:top", PRIMARY)],
    ]
    if is_owner:
        rows.append([_btn("💥 انحلال تیم", "team:disband", DANGER)])
    else:
        rows.append([_btn("🚪 ترک تیم", "team:leave", PRIMARY)])
    rows.append([_btn("🔃 رفرش", "menu:team", PRIMARY)])
    rows.append([_btn("🏠 منوی اصلی", "menu:home", PRIMARY)])
    return InlineKeyboardMarkup(rows)


def team_bld_kb(team, is_owner: bool, tg_id: int) -> InlineKeyboardMarkup:
    """کیبورد ساختمان‌های تیم — ارتقا فقط برای رهبره"""
    rows: list[list[InlineKeyboardButton]] = []
    if is_owner:
        can_atk = team.atk_bld < config.TEAM_BUILDING_MAX_LEVEL
        can_def = team.def_bld < config.TEAM_BUILDING_MAX_LEVEL
        row: list[InlineKeyboardButton] = []
        if can_atk:
            row.append(_btn("⚔️ ارتقا حمله", f"tbup:atk:{tg_id}", SUCCESS))
        if can_def:
            row.append(_btn("🛡 ارتقا دفاع", f"tbup:def:{tg_id}", SUCCESS))
        if row:
            rows.append(row)
    rows.append([_btn("🔃 رفرش", "team:bld", PRIMARY)])
    rows.append([_btn("🔙 تیم من", "menu:team", PRIMARY)])
    return InlineKeyboardMarkup(rows)


def team_bld_confirm_kb(kind: str, tg_id: int) -> InlineKeyboardMarkup:
    """تایید ارتقای ساختمان — فقط خود رهبر می‌تونه بزنه"""
    return InlineKeyboardMarkup([[
        _btn("✅ تایید", f"tbcf:{kind}:{tg_id}", SUCCESS),
        _btn("❌ لغو", f"txcl:{tg_id}", DANGER),
    ]])


# ───────── بانک شخصی ─────────

def bank_kb(user: User) -> InlineKeyboardMarkup:
    """کیبورد بانک — واریز و برداشت مبلغ رو با پیام بعدی می‌پرسن"""
    from services.bank import bank_upgrade_price

    rows: list[list[InlineKeyboardButton]] = [
        [_btn("💰 واریز", "bank:dep", SUCCESS),
         _btn("💸 برداشت", "bank:wd", PRIMARY)],
    ]
    if user.bank_level < config.BANK_MAX_LEVEL:
        price = bank_upgrade_price(user.bank_level)
        rows.append([_btn(
            f"⬆️ ارتقای بانک | لول {fa_num(user.bank_level + 1)} | {money_tp(price)}",
            "bank:up", PRIMARY,
        )])
    else:
        rows.append([_btn("⭐ بانک مکس لوله", "noop:maxbank")])
    rows.append([_btn("🏠 منوی اصلی", "menu:home", PRIMARY)])
    return InlineKeyboardMarkup(rows)


def team_no_kb() -> InlineKeyboardMarkup:
    """کیبورد وقتی تیم نداری"""
    return InlineKeyboardMarkup([
        [_btn("🏆 برترین تیم‌ها", "team:top", PRIMARY)],
        [_btn("🏠 منوی اصلی", "menu:home", PRIMARY)],
    ])


def team_confirm_kb(action: str, tg_id: int) -> InlineKeyboardMarkup:
    """تایید اکشن تیمی (ترک/انحلال) — فقط صاحب دستور می‌تونه بزنه"""
    return InlineKeyboardMarkup([[
        _btn("✅ تایید", f"tmcf:{action}:{tg_id}", SUCCESS),
        _btn("❌ لغو", f"txcl:{tg_id}", DANGER),
    ]])
