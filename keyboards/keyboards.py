"""
کیبوردهای اینلاین با استایل رنگی تلگرام
primary = آبی (اکشن‌های اصلی) | success = سبز (تایید) | danger = قرمز (لغو)

ساختار callback_data یکدسته: «بخش:اکشن:پارتامترها»
مسیر تایید اکشن‌های مهم با پیشوند cf: اجرا میشه | cl همیشه لغوه
تایید دستورهای متنی گروه با پیشوند txcf: و id کاربر، فقط خودش بتونه تایید کنه

menu:home | menu:profile | menu:farm | menu:shop | menu:attack | menu:rank | menu:dogs
farm:buy                    → cf:farm:buy
farm:plant:<plot_id>        → انتخاب بذر از انبار
farm:plant:<plot_id>:<seed> → cf:plant:<plot_id>:<seed>
farm:hv                     → برداشت همه آماده‌ها (کولدون ۲ دقیقه)
farm:up:<plot_id>           → cf:farm:up:<plot_id>
shop:sec:<kind>             → بخش‌های شاپ: weap | arm | seed | dog | food
shop:buy:<kind>:<key>       → cf:shop:buy:<kind>:<key>
txcf:<kind>:<key>:<tg_id>   → تایید خرید دستور متنی (فقط خودش)
dogs:feed:<dog_id>          → کارت آمار سگ با همان دکمه‌های غذا (cf:feed:<dog_id>:<food>)
heal:buy:<key>              → خرید و استفاده همون لحظه آیتم درمان
patt:go:<tg_id> | patt:re   → حمله پی‌وی کلاسیک: تایید حمله | رفرش لیست، اجرا با cf:patt:x:<tg_id>
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

# یوزرنیم ربات موقع استارت ست میشه، برای دکمه «افزودن به گروه»
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
        [_btn("📅 کوئست‌های روزانه", "menu:dquests", PRIMARY),
         _btn("📖 راهنما", "help:menu", PRIMARY)],
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
    """کیبورد تایید استاندارد، تایید سبز | لغو قرمز"""
    return InlineKeyboardMarkup([[
        _btn("✅ تایید", confirm_data, SUCCESS),
        _btn("❌ لغو", "cl", DANGER),
    ]])


def tx_confirm_kb(kind: str, key: str, tg_id: int, dog_name: str | None = None) -> InlineKeyboardMarkup:
    """تایید خرید دستور متنی، id کاربر داخل دیتا ست میشه که غریبه نتونه بزنه"""
    data = f"txcf:{kind}:{key}:{tg_id}"
    if dog_name:
        safe = dog_name.replace(":", " ").strip()[:12]  # سقف بایت callback_data
        if safe:
            data += f":{safe}"
    return InlineKeyboardMarkup([[
        _btn("✅ تایید", data, SUCCESS),
        _btn("❌ لغو", f"txcl:{tg_id}", DANGER),
    ]])


def admin_kb() -> InlineKeyboardMarkup:
    """پنل ادمین، پول/XP + آمار + عضویت اجباری"""
    return InlineKeyboardMarkup([
        [_btn("💵 +10,000 TP", "adm:cash:10000", SUCCESS),
         _btn("💵 +100,000 TP", "adm:cash:100000", SUCCESS)],
        [_btn("✨ +100 XP", "adm:xp:100", PRIMARY),
         _btn("✨ +1,000 XP", "adm:xp:1000", PRIMARY)],
        [_btn("📊 آمار ربات", "adm:stats:0", PRIMARY)],
        [_btn("📢 عضویت اجباری", "adm:fj:0", PRIMARY)],
        [_btn("🏠 منوی اصلی", "menu:home", PRIMARY)],
    ])


def admin_stats_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [_btn("🔃 رفرش", "adm:stats:0", PRIMARY)],
        [_btn("🔙 پنل ادمین", "adm:panel:0", PRIMARY)],
    ])


def admin_fj_kb(st: dict) -> InlineKeyboardMarkup:
    """کیبورد مدیریت عضویت اجباری بر اساس وضعیت فعلی"""
    rows: list[list[InlineKeyboardButton]] = []
    if st.get("channel"):
        rows.append([_btn(
            "⏸ غیرفعال کن" if st.get("on") else "▶️ فعال کن",
            "adm:fjtog:0", DANGER if st.get("on") else SUCCESS,
        )])
        rows.append([_btn("🗑 حذف کانال", "adm:fjdel:0", DANGER)])
    rows.append([_btn("🔗 ست کردن کانال", "adm:fjset:0", SUCCESS)])
    rows.append([_btn("🔙 پنل ادمین", "adm:panel:0", PRIMARY)])
    return InlineKeyboardMarkup(rows)


def force_join_kb(link: str) -> InlineKeyboardMarkup:
    """دکمه‌های پیام گیت عضویت اجباری"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 عضویت در کانال", url=link)],
        [_btn("✅ تایید عضویت", "fj:check", SUCCESS)],
    ])


def admin_users_kb(users: list) -> InlineKeyboardMarkup:
    """لیست نتایج جستجوی /user، هرکدوم یه دکمه"""
    rows = []
    for u in users:
        name = u.first_name or u.username or f"کاربر {u.telegram_id}"
        rows.append([_btn(f"👤 {name} | {u.telegram_id}", f"adm:u:{u.telegram_id}", PRIMARY)])
    rows.append([_btn("🏠 منوی اصلی", "menu:home", PRIMARY)])
    return InlineKeyboardMarkup(rows)


def admin_user_kb(tg_id: int) -> InlineKeyboardMarkup:
    """دکمه‌های کارت کاربر تو پنل ادمین (gtp/gxp = دادن به اون کاربر)"""
    return InlineKeyboardMarkup([
        [_btn("💰 پول بده", f"adm:gtp:{tg_id}", SUCCESS)],
        [_btn("✨ XP بده", f"adm:gxp:{tg_id}", PRIMARY)],
        [_btn("🏠 منوی اصلی", "menu:home", PRIMARY)],
    ])


# ───────── آموزشات (هلپ دکمه‌دار) 📖 ─────────
# key → عنوان دکمه، متن کامل هر بخش تو handlers/start.py (HELP_SECTIONS)
HELP_MENU = [
    ("farm",   "🌱 کاشت و برداشت"),
    ("shop",   "🛒 شاپ"),
    ("attack", "⚔️ حمله"),
    ("dogs",   "🐕 سگ‌ها"),
    ("team",   "🏴 تیم"),
    ("bank",   "🏦 بانک"),
    ("mine",   "⛏ کنده‌کاری"),
    ("world",  "🌍 جستجو و رویدادها"),
    ("eco",    "⭐ لول و اقتصاد"),
]


def help_menu_kb() -> InlineKeyboardMarkup:
    """منوی بخش‌های آموزشات، هر بخش یه دکمه + دکمه منوی اصلی تهش"""
    rows: list[list[InlineKeyboardButton]] = []
    for i in range(0, len(HELP_MENU), 2):
        chunk = HELP_MENU[i:i + 2]
        rows.append([_btn(title, f"help:sec:{key}", PRIMARY) for key, title in chunk])
    rows.append([_btn("🏠 منوی اصلی", "menu:home", PRIMARY)])
    return InlineKeyboardMarkup(rows)


def help_back_kb() -> InlineKeyboardMarkup:
    """🔙 آموزشات، برگشت به منوی اصلی هلپ"""
    return InlineKeyboardMarkup([
        [_btn("🔙 آموزشات", "help:menu", PRIMARY)],
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
        lvl_label = "👑 لول مکس" if plot.level >= config.PLOT_MAX_LEVEL else f"لول {fa_num(plot.level)}"
        rows.append([_btn(f"🗺 زمین {fa_num(i)} | {lvl_label}", f"noop:plot:{i}")])

        actions: list[InlineKeyboardButton] = []
        if state == "building":
            actions.append(_btn(f"🔨 ساخت: {fa_dur(left)}", "noop:build", DANGER))
        elif state == "empty":
            actions.append(_btn("🌱 کاشت", f"farm:plant:{plot.id}"))
        elif state == "growing":
            actions.append(_btn(f"⏳ {fa_dur(left)}", "noop:grow", DANGER))
        else:
            actions.append(_btn("✅ آماده", "noop:ready"))

        if state != "building":
            if plot.level < config.PLOT_MAX_LEVEL:
                up_req = economy.plot_upgrade_required_level(plot.level)
                if user.level >= up_req:
                    actions.append(_btn(f"⬆️ آپگرید | {money_tp(economy.upgrade_price(plot.level))}", f"farm:up:{plot.id}", PRIMARY))
                else:
                    actions.append(_btn(f"🔒 آپگرید | لول {fa_num(up_req)}", "noop:uplock", DANGER))
            else:
                actions.append(_btn("👑 لول مکس", "noop:maxplot"))
        rows.append(actions)

    if ready_count:
        rows.append([_btn(f"📦 برداشت همه آماده‌ها ({fa_num(ready_count)})", "farm:hv", SUCCESS)])

    if len(plots) < config.MAX_PLOTS:
        req = economy.plot_required_level(len(plots))
        n_next = len(plots) + 1
        if user.level >= req:
            rows.append([_btn(
                f"🔨 ساخت زمین {fa_num(n_next)} | 🪙 {money_tp(next_price)}",
                "farm:buy", PRIMARY,
            )])
        else:
            rows.append([_btn(
                f"🔒 ساخت زمین {fa_num(n_next)} | 🪙 {money_tp(next_price)} | لول {fa_num(req)}",
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
            f"{seed.get('emoji', '🌱')} {seed['name']} ×{fa_num(have)}"
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
        if s.get("legendary"):
            continue  # بذر افسانه‌ای تو شاپ نیس، فقط جستجو/کاروان
        if user.level < s["min_level"]:
            rows.append([_btn(f"🔒 {s['name']} | لول {fa_num(s['min_level'])}", "noop:lock", DANGER)])
        else:
            have = stock.get(key, 0)
            have_txt = f" | 📦 ×{fa_num(have)}" if have else ""
            rows.append([_btn(
                f"{s.get('emoji', '🌱')} {s['name']} | {money_tp(s['price'])}{have_txt}",
                f"shop:buy:seed:{key}", PRIMARY,
            )])
    rows.append([_btn("🌱 مزرعه من", "menu:farm", PRIMARY)])
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
    """کیبورد کارت آمار یه سگ، از همونجا میشه غذاش داد («آمار اصغر»)"""
    rows: list[list[InlineKeyboardButton]] = []
    if dog.level >= config.DOG_MAX_LEVEL:
        rows.append([_btn("👑 لول مکس", "noop:maxdog")])
    elif feeds_left > 0:
        for key, f in config.DOG_FOODS.items():
            rows.append([_btn(
                f"🍖 {f['name']} | +{fa_num(f['xp'])} XP | {money_tp(f['price'])}",
                f"cf:feed:{dog.id}:{key}", SUCCESS,
            )])
    else:
        rows.append([_btn("🍖 سیر شده", "noop:feedinfo", DANGER)])
    rows.append([_btn("🔙 سگ‌های من", "menu:dogs", PRIMARY),
                 _btn("🕊 رهاش کن", f"dog:rel:{dog.id}", DANGER)])
    rows.append([_btn("🏠 منوی اصلی", "menu:home", PRIMARY)])
    return InlineKeyboardMarkup(rows)


def release_confirm_kb(dog_id: int, tg_id: int) -> InlineKeyboardMarkup:
    """تایید رها کردن سگ، فقط صاحبش"""
    return InlineKeyboardMarkup([[
        _btn("✅ رهاش کن", f"relcf:{dog_id}:{tg_id}", SUCCESS),
        _btn("❌ لغو", f"txcl:{tg_id}", DANGER),
    ]])


def team_create_confirm_kb(tg_id: int) -> InlineKeyboardMarkup:
    """تایید ساخت تیم بعد از اسم دادن، فقط خودش"""
    return InlineKeyboardMarkup([[
        _btn("✅ تایید", f"teamcf:ok:{tg_id}", SUCCESS),
        _btn("❌ لغو", f"teamcf:no:{tg_id}", DANGER),
    ]])



# ───────── درمان ❤️ ─────────

def pv_attack_kb(targets: list) -> InlineKeyboardMarkup:
    """لیست هدف‌های حمله پی‌وی، هر هدف یه دکمه قرمز حمله + رفرش لیست"""
    rows: list[list[InlineKeyboardButton]] = []
    for u in targets:
        name = (u.first_name or u.username or "ناشناس")[:14]
        rows.append([_btn(f"⚔️ حمله به {name}", f"patt:go:{u.telegram_id}", DANGER)])
    rows.append([_btn("🔄 لیست جدید", "patt:re", PRIMARY)])
    rows.append([_btn("🏠 منوی اصلی", "menu:home", PRIMARY)])
    return InlineKeyboardMarkup(rows)


def pv_attack_result_kb() -> InlineKeyboardMarkup:
    """بعد نتیجه حمله پی‌وی، برگرد به لیست یا منو"""
    return InlineKeyboardMarkup([
        [_btn("🔄 لیست حمله", "patt:re", PRIMARY)],
        [_btn("🏠 منوی اصلی", "menu:home", PRIMARY)],
    ])


def heal_kb() -> InlineKeyboardMarkup:
    """کیبورد بخش درمان، هر آیتم با یه کلیک خریده و همون لحظه استفاده میشه"""
    rows: list[list[InlineKeyboardButton]] = []
    for key, it in config.HEAL_ITEMS.items():
        gain = "فول" if it["heal"] is None else f"+{fa_num(it['heal'])} HP"
        rows.append([_btn(
            f"{it['name']} | {gain} | {money_tp(it['price'])}",
            f"heal:buy:{key}", SUCCESS,
        )])
    rows.append([_btn("🏠 منوی اصلی", "menu:home", PRIMARY)])
    return InlineKeyboardMarkup(rows)


# ───────── رتبه‌بندی ─────────

def rank_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [_btn("🔃 رفرش", "menu:rank", PRIMARY)],
        [_btn("🏠 منوی اصلی", "menu:home", PRIMARY)],
    ])


# ───────── کوئست‌های روزانه 📅 ─────────

def dquests_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [_btn("🔃 رفرش", "menu:dquests", PRIMARY)],
        [_btn("🏠 منوی اصلی", "menu:home", PRIMARY)],
    ])


# ───────── تیم ─────────

def team_kb(is_owner: bool = False) -> InlineKeyboardMarkup:
    """کیبورد صفحه «تیم من»"""
    rows: list[list[InlineKeyboardButton]] = [
        [_btn("📜 کوئست‌های امروز", "team:quests", PRIMARY),
         _btn("⛏ کنده‌کاری تیمی", "team:mine", PRIMARY)],
        [_btn("🏗 ساختمان‌ها", "team:bld", PRIMARY),
         _btn("🏦 بانک تیم", "team:bank", PRIMARY)],
        [_btn("🏆 لیدربرد", "team:top", PRIMARY)],
    ]
    if is_owner:
        rows.append([_btn("💥 انحلال تیم", "team:disband", DANGER)])
    else:
        rows.append([_btn("🚪 ترک تیم", "team:leave", PRIMARY)])
    rows.append([_btn("🔃 رفرش", "menu:team", PRIMARY)])
    rows.append([_btn("🏠 منوی اصلی", "menu:home", PRIMARY)])
    return InlineKeyboardMarkup(rows)


def team_bld_kb(team, is_owner: bool, tg_id: int) -> InlineKeyboardMarkup:
    """کیبورد ساختمان‌های تیم، ارتقا فقط برای رهبره"""
    rows: list[list[InlineKeyboardButton]] = []
    if is_owner:
        can_atk = team.atk_bld < config.TEAM_BUILDING_MAX_LEVEL
        can_def = team.def_bld < config.TEAM_BUILDING_MAX_LEVEL
        row: list[InlineKeyboardButton] = []
        if can_atk:
            row.append(_btn("⚔️ ارتقا حمله", f"tbup:atk:{tg_id}", SUCCESS))
        else:
            row.append(_btn("⚔️ حمله 👑 لول مکس", "noop:maxbld"))
        if can_def:
            row.append(_btn("🛡 ارتقا دفاع", f"tbup:def:{tg_id}", SUCCESS))
        else:
            row.append(_btn("🛡 دفاع 👑 لول مکس", "noop:maxbld"))
        if row:
            rows.append(row)
    rows.append([_btn("🔃 رفرش", "team:bld", PRIMARY)])
    rows.append([_btn("🔙 تیم من", "menu:team", PRIMARY)])
    rows.append([_btn("🏠 منوی اصلی", "menu:home", PRIMARY)])
    return InlineKeyboardMarkup(rows)


def team_bld_confirm_kb(kind: str, tg_id: int) -> InlineKeyboardMarkup:
    """تایید ارتقای ساختمان، فقط خود رهبر می‌تونه بزنه"""
    return InlineKeyboardMarkup([[
        _btn("✅ تایید", f"tbcf:{kind}:{tg_id}", SUCCESS),
        _btn("❌ لغو", f"txcl:{tg_id}", DANGER),
    ]])


# ───────── بانک شخصی ─────────

def bank_kb(user: User) -> InlineKeyboardMarkup:
    """کیبورد بانک، واریز و برداشت مبلغ رو با پیام بعدی می‌پرسن"""
    from services.bank import bank_upgrade_price

    rows: list[list[InlineKeyboardButton]] = [
        [_btn("💰 واریز", "bank:dep", SUCCESS),
         _btn("💸 برداشت", "bank:wd", DANGER)],
    ]
    if user.bank_level < config.BANK_MAX_LEVEL:
        price = bank_upgrade_price(user.bank_level)
        rows.append([_btn(
            f"⬆️ ارتقای بانک | لول {fa_num(user.bank_level + 1)} | {money_tp(price)}",
            "bank:up", PRIMARY,
        )])
    else:
        rows.append([_btn("🏦 بانک 👑 لول مکس", "noop:maxbank")])
    rows.append([_btn("🏠 منوی اصلی", "menu:home", PRIMARY)])
    return InlineKeyboardMarkup(rows)


def team_no_kb() -> InlineKeyboardMarkup:
    """کیبورد وقتی تیم نداری"""
    return InlineKeyboardMarkup([
        [_btn("🏆 برترین تیم‌ها", "team:top", PRIMARY)],
        [_btn("🏠 منوی اصلی", "menu:home", PRIMARY)],
    ])


def team_confirm_kb(action: str, tg_id: int) -> InlineKeyboardMarkup:
    """تایید اکشن تیمی (ترک/انحلال)، فقط صاحب دستور می‌تونه بزنه"""
    return InlineKeyboardMarkup([[
        _btn("✅ تایید", f"tmcf:{action}:{tg_id}", SUCCESS),
        _btn("❌ لغو", f"txcl:{tg_id}", DANGER),
    ]])


# ───────── صفحات فرعی تیم، برگشت به تیم من + منوی اصلی ─────────

def team_back_kb(home: bool = True) -> InlineKeyboardMarkup:
    """🔙 تیم من + 🏠 منوی اصلی (تو گروه home با strip_home برمی‌ره)"""
    rows = [[_btn("🔙 تیم من", "menu:team", PRIMARY)]]
    if home:
        rows.append([_btn("🏠 منوی اصلی", "menu:home", PRIMARY)])
    return InlineKeyboardMarkup(rows)


def team_mine_kb() -> InlineKeyboardMarkup:
    """دکمه‌های کنده‌کاری تیمی، جوین/رفرش + برگشت"""
    return InlineKeyboardMarkup([
        [_btn("⛏ میام استخراج", "team:mine", SUCCESS)],
        [_btn("🔙 تیم من", "menu:team", PRIMARY)],
        [_btn("🏠 منوی اصلی", "menu:home", PRIMARY)],
    ])


def team_bank_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [_btn("💰 واریز به بانک تیم | آموزش: «تیم واریز 1200»", "noop:depinfo", PRIMARY)],
        [_btn("🔙 تیم من", "menu:team", PRIMARY)],
        [_btn("🏠 منوی اصلی", "menu:home", PRIMARY)],
    ])


# ───────── پناهگاه 🏚 ─────────

def shelter_kb(user: User) -> InlineKeyboardMarkup:
    from services.world import shelter_price
    rows: list[list[InlineKeyboardButton]] = []
    if user.shelter_level < config.SHELTER_MAX_LEVEL:
        price = shelter_price(user.shelter_level + 1)
        rows.append([_btn(
            f"⬆️ ارتقا | لول {fa_num(user.shelter_level + 1)} | {money_tp(price)}",
            "shelter:up", PRIMARY,
        )])
    else:
        rows.append([_btn("🏚 پناهگاه 👑 لول مکس", "noop:maxshelter")])
    rows.append([_btn("🏠 منوی اصلی", "menu:home", PRIMARY)])
    return InlineKeyboardMarkup(rows)


# ───────── قمارخانه 🎰 ─────────

def casino_kb() -> InlineKeyboardMarkup:
    rows = []
    for bet in config.CASINO_BETS:
        rows.append([_btn(f"🎲 میز {money_tp(bet)} | برد {money_tp(int(bet * config.CASINO_WIN_MULT))}", f"cas:bet:{bet}", SUCCESS)])
    rows.append([_btn("🏠 منوی اصلی", "menu:home", PRIMARY)])
    return InlineKeyboardMarkup(rows)


# ───────── کاروان 🚛 ─────────

def caravan_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[_btn("⚔️ حمله به کاروان", "cv:hit", DANGER)]])
