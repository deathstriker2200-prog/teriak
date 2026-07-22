"""مزرعه: خرید زمین | کاشت بذر | برداشت هر ۲ دقیقه | آپگرید"""

from telegram import Update
from telegram.ext import ContextTypes

import config
from database import session_scope
from handlers.common import parts, respond
from keyboards import keyboards as kb
from services import economy, farming, users
from utils import esc, fa_dur, fa_num, money


# ───────── نمایش مزرعه ─────────

async def render_farm(update: Update, extra: str | None = None, alert: str | None = None) -> None:
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        users.apply_energy_regen(user)

        plots = await farming.get_user_plots(s, user.id)
        ready_count = 0
        lines: list[str] = []

        for i, p in enumerate(plots, 1):
            state, left = p.current_status()
            seed_name = config.SEEDS.get(p.crop or "", {}).get("name", "؟")
            head = f"زمین {fa_num(i)} (لول {fa_num(p.level)})"
            if state == "building":
                lines.append(f"🔨 {head} | داره ساخته میشه — {fa_dur(left)} مونده")
            elif state == "empty":
                lines.append(f"▫️ {head} خالیه")
            elif state == "growing":
                lines.append(f"🌱 {head} | {esc(seed_name)} | {fa_dur(left)} مونده")
            else:
                ready_count += 1
                lines.append(f"✅ {head} | {esc(seed_name)} آماده برداشته")

        if not plots:
            lines.append("هنوز زمینی نداری رفیق")

        text = "<b>🌱 مزرعه من</b>\n\n" + "\n".join(lines)
        text += f"\n\n💵 نقدینگی {money(user.cash)}"

        cd_left = farming.harvest_cooldown_left(user)
        if cd_left:
            text += f"\n⏳ برداشت بعدی {fa_dur(cd_left)} دیگه"
        elif ready_count:
            text += f"\n📦 {fa_num(ready_count)} تا آماده برداشته"

        next_price = economy.plot_price(len(plots))
        markup = kb.farm_kb(user, plots, next_price, ready_count)
        await s.commit()

    await respond(update, text, markup, alert=alert)


async def farm_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await render_farm(update)


# ───────── خرید زمین ─────────

async def buy_plot_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        count = await farming.plots_count(s, user.id)
        price = economy.plot_price(count)
        req_level = economy.plot_required_level(count)
        cash = user.cash
        level = user.level
        await s.commit()

    if count >= config.MAX_PLOTS:
        return await render_farm(update, alert="🏡 به سقف 5 زمین رسیدی رفیق")
    if level < req_level:
        return await render_farm(update, alert=f"🔒 زمین شماره {fa_num(count + 1)} لول {fa_num(req_level)} می‌خواد")

    build = economy.plot_build_seconds(count)
    text = (
        f"<b>🛒 خرید زمین شماره {fa_num(count + 1)}</b>\n\n"
        f"قیمتش {money(price)}\n"
        f"الان {money(cash)} داری\n"
        + (f"🔨 بعد خرید {fa_dur(build)} طول می‌کشه ساخته بشه\n" if build else "")
        + "\nمی‌خری رفیق؟"
    )
    await respond(update, text, kb.confirm_kb("cf:farm:buy"))


async def buy_plot_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        _, alert = await farming.buy_plot(s, user)
        await s.commit()
    await render_farm(update, alert=alert)


# ───────── کاشت ─────────

def _picker_text(stock: dict[str, int]) -> str:
    if any(v > 0 for v in stock.values()):
        return (
            "<b>🌱 چی بکاریم؟</b>\n\n"
            "بذرهات | ⏱ زمان رشد | 💰 درآمد برداشت\n\n"
            "یکی رو انتخاب کن رفیق"
        )
    return (
        "<b>🌾 انبار بذرت خالیه</b>\n\n"
        "از بخش 🌱 بذرهای شاپ بذر بخر\n"
        "یا تو گروه بنویس «خرید ماری جوانا»"
    )


async def plant_picker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    plot_id = int(parts(update)[2])
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        plot = await farming.get_plot(s, user.id, plot_id)

        if not plot or plot.current_status()[0] != "empty":
            await s.commit()
            return await render_farm(update, alert="❌ این زمین الان خالی نیس")

        stock = await farming.get_stock(s, user.id)
        markup = kb.seeds_kb(user, plot, stock)
        text = _picker_text(stock)
        await s.commit()

    await respond(update, text, markup)


async def plant_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, _, plot_id, seed_key = parts(update)
    seed = config.SEEDS.get(seed_key)
    if not seed:
        return await render_farm(update, alert="❌ همچین بذری نیس")

    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        plot = await farming.get_plot(s, user.id, int(plot_id))

        if not plot or plot.current_status()[0] != "empty":
            await s.commit()
            return await render_farm(update, alert="❌ این زمین الان خالی نیس")

        stock = await farming.get_stock(s, user.id)
        have = stock.get(seed_key, 0)
        yield_ = economy.crop_yield(seed_key, plot.level, user.level)
        grow = economy.crop_grow_seconds(seed_key, plot.level)
        text = (
            f"<b>🌱 کاشت {esc(seed['name'])}</b>\n\n"
            f"🌾 {fa_num(have)} بذر داری و یدونه مصرف میشه\n"
            f"⏱ {fa_dur(grow)} دیگه آمادست\n"
            f"💰 برداشتش حدود {money(yield_)} میشه\n\n"
            "شروع کنیم؟"
        )
        markup = kb.confirm_kb(f"cf:plant:{plot.id}:{seed_key}")
        await s.commit()

    await respond(update, text, markup)


async def plant_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, _, plot_id, seed_key = parts(update)
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        plot = await farming.get_plot(s, user.id, int(plot_id))
        if not plot:
            alert = "❌ همچین زمینی نداری"
        else:
            _, alert = await farming.plant(s, user, plot, seed_key)
        await s.commit()
    await render_farm(update, alert=alert)


# ───────── برداشت (همه آماده‌ها — کولدون ۲ دقیقه) ─────────

async def harvest_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        _, alert, extra = await farming.harvest_all(s, user)
        await s.commit()
    await render_farm(update, extra=extra, alert=alert)


# ───────── آپگرید ─────────

async def upgrade_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    plot_id = int(parts(update)[2])
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        plot = await farming.get_plot(s, user.id, plot_id)

        if not plot:
            await s.commit()
            return await render_farm(update, alert="❌ همچین زمینی نداری")
        if plot.level >= config.PLOT_MAX_LEVEL:
            await s.commit()
            return await render_farm(update, alert="⭐ این زمین مکس لوله")

        price = economy.upgrade_price(plot.level)
        old_y = economy.plot_yield_mult(plot.level)
        new_y = economy.plot_yield_mult(plot.level + 1)
        old_sp = economy.plot_speed_mult(plot.level)
        new_sp = economy.plot_speed_mult(plot.level + 1)
        text = (
            f"<b>⬆️ لول‌آپ زمین — تا لول {fa_num(config.PLOT_MAX_LEVEL)}</b>\n\n"
            f"از لول {fa_num(plot.level)} به {fa_num(plot.level + 1)}\n"
            f"💸 هزینه {money(price)}\n"
            f"📈 درآمد 25٪ بهتر میشه (×{old_y:.2f} ← ×{new_y:.2f})\n"
            f"⚡ سرعت رشد 40٪ بیشتر میشه (×{old_sp:.1f} ← ×{new_sp:.1f})\n\n"
            "انجامش بدیم؟"
        )
        markup = kb.confirm_kb(f"cf:farm:up:{plot.id}")
        await s.commit()

    await respond(update, text, markup)


async def upgrade_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    plot_id = int(parts(update)[3])
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        plot = await farming.get_plot(s, user.id, plot_id)
        if not plot:
            alert = "❌ همچین زمینی نداری"
        else:
            _, alert = await farming.upgrade_plot(s, user, plot)
        await s.commit()
    await render_farm(update, alert=alert)
