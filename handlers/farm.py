"""مزرعه: خرید زمین | کاشت | برداشت | آپگرید"""

from datetime import timedelta

from sqlalchemy import func, select
from telegram import Update
from telegram.ext import ContextTypes

import config
from database import session_scope
from handlers.common import parts, respond
from keyboards import keyboards as kb
from models import Plot
from services import economy, users
from utils import esc, fa_dur, fa_num, money, money_tp, now_utc


# ───────── نمایش مزرعه ─────────

async def render_farm(update: Update, extra: str | None = None, alert: str | None = None) -> None:
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        users.apply_energy_regen(user)

        plots = list((await s.execute(
            select(Plot).where(Plot.user_id == user.id).order_by(Plot.id)
        )).scalars())

        lines: list[str] = []
        for i, p in enumerate(plots, 1):
            state, left = p.current_status()
            crop_name = config.CROPS.get(p.crop or "", {}).get("name", "؟")
            head = f"زمین {fa_num(i)} (لول {fa_num(p.level)})"
            if state == "empty":
                lines.append(f"▫️ {head} خالیه")
            elif state == "growing":
                lines.append(f"🌱 {head} | {esc(crop_name)} | {fa_dur(left)} مونده")
            else:
                lines.append(f"✅ {head} | {esc(crop_name)} آماده برداشته")

        if not plots:
            lines.append("هنوز زمینی نداری رفیق")

        text = "<b>🌱 مزرعه من</b>\n\n" + "\n".join(lines)
        text += f"\n\n💵 نقدینگی {money(user.cash)}"

        next_price = economy.plot_price(len(plots))
        if len(plots) < config.MAX_PLOTS:
            text += f"\n🛒 زمین بعدی {money(next_price)}"
        if extra:
            text += f"\n\n{extra}"

        markup = kb.farm_kb(user, plots, next_price)
        await s.commit()

    await respond(update, text, markup, alert=alert)


async def farm_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await render_farm(update)


# ───────── ابزار داخلی ─────────

async def _get_plot(session, user, plot_id: int) -> Plot | None:
    q = select(Plot).where(Plot.id == plot_id, Plot.user_id == user.id)
    return (await session.execute(q)).scalar_one_or_none()


async def _plots_count(session, user) -> int:
    q = select(func.count(Plot.id)).where(Plot.user_id == user.id)
    return (await session.execute(q)).scalar_one()


# ───────── خرید زمین ─────────

async def buy_plot_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        count = await _plots_count(s, user)
        if count >= config.MAX_PLOTS:
            pass  # پایین هندل میشه
        price = economy.plot_price(count)
        cash = user.cash
        await s.commit()

    if count >= config.MAX_PLOTS:
        return await render_farm(update, alert="🏡 به سقف زمین رسیدی رفیق")

    text = (
        "<b>🛒 خرید زمین جدید</b>\n\n"
        f"قیمتش {money(price)}\n"
        f"الان {money(cash)} داری\n\n"
        "می‌خری داداش؟"
    )
    await respond(update, text, kb.confirm_kb("cf:farm:buy"))


async def buy_plot_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        count = await _plots_count(s, user)
        price = economy.plot_price(count)

        if count >= config.MAX_PLOTS:
            alert = "🏡 به سقف زمین رسیدی رفیق"
        elif user.cash < price:
            alert = "❌ پولت کافی نیس رفیق"
        else:
            user.cash -= price
            s.add(Plot(user_id=user.id))
            alert = "🎉 زمین جدید مالت شد"
        await s.commit()

    await render_farm(update, alert=alert)


# ───────── کاشت ─────────

async def plant_picker(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    plot_id = int(parts(update)[2])
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        plot = await _get_plot(s, user, plot_id)
        if not plot or plot.current_status()[0] != "empty":
            await s.commit()
            ok = False
            markup = None
            text = ""
        else:
            text = (
                "<b>🌱 چی بکاریم؟</b>\n\n"
                "💸 هزینه کاشت | ⏱ زمان آماده شدن | 💰 درآمد برداشت\n\n"
                "یکی رو انتخاب کن رفیق"
            )
            markup = kb.crops_kb(user, plot)
            await s.commit()
            ok = True

    if not ok:
        return await render_farm(update, alert="❌ این زمین الان خالی نیس")
    await respond(update, text, markup)


async def plant_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, _, plot_id, crop_key = parts(update)
    crop = config.CROPS.get(crop_key)
    if not crop:
        return await render_farm(update, alert="❌ چیزی نیست که")

    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        plot = await _get_plot(s, user, int(plot_id))
        if not plot or plot.current_status()[0] != "empty":
            await s.commit()
            ok = False
            text = markup = None
        else:
            yield_ = economy.crop_yield(crop_key, plot.level)
            grow = economy.crop_grow_seconds(crop_key, plot.level)
            text = (
                f"<b>🌱 کاشت {esc(crop['name'])}</b>\n\n"
                f"💸 هزینه {money(crop['cost'])}\n"
                f"⏱ {fa_dur(grow)} دیگه آمادست\n"
                f"💰 برداشتش حدود {money(yield_)} میشه\n\n"
                "شروع کنیم؟"
            )
            markup = kb.confirm_kb(f"cf:plant:{plot.id}:{crop_key}")
            await s.commit()
            ok = True

    if not ok:
        return await render_farm(update, alert="❌ این زمین الان خالی نیس")
    await respond(update, text, markup)


async def plant_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    _, _, plot_id, crop_key = parts(update)
    crop = config.CROPS.get(crop_key)
    if not crop:
        return await render_farm(update, alert="❌ چیزی نیست که")

    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        plot = await _get_plot(s, user, int(plot_id))

        if not plot or plot.current_status()[0] != "empty":
            alert = "❌ این زمین الان خالی نیس"
        elif not economy.is_crop_unlocked(crop_key, user.level):
            alert = "🔒 این محصول هنوز برات باز نشده"
        elif user.cash < crop["cost"]:
            alert = "❌ پولت کافی نیس رفیق"
        else:
            user.cash -= crop["cost"]
            seconds = economy.crop_grow_seconds(crop_key, plot.level)
            plot.status = "growing"
            plot.crop = crop_key
            plot.planted_at = now_utc()
            plot.ready_at = now_utc() + timedelta(seconds=seconds)
            alert = f"🌱 {crop['name']} کاشته شد"
        await s.commit()

    await render_farm(update, alert=alert)


# ───────── برداشت ─────────

async def harvest_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    plot_id = int(parts(update)[2])
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        plot = await _get_plot(s, user, plot_id)

        if not plot:
            alert, extra = "❌ همچین زمینی نداری", None
        else:
            state, left = plot.current_status()
            if state == "empty":
                alert, extra = "▫️ این زمین خالیه رفیق", None
            elif state == "growing":
                alert, extra = f"⏳ هنوز {fa_dur(left)} مونده", None
            else:
                crop = config.CROPS[plot.crop]
                gain = economy.crop_yield(plot.crop, plot.level)
                user.cash += gain
                notes = users.add_xp(user, crop["xp"])

                plot.status = "empty"
                plot.crop = None
                plot.planted_at = None
                plot.ready_at = None

                extra = f"📦 برداشت شد و {money(gain)} خالص گیرت اومد"
                if notes:
                    extra += "\n" + "\n".join(notes)
                alert = f"💰 {money_tp(gain)}"
        await s.commit()

    await render_farm(update, extra=extra, alert=alert)


# ───────── آپگرید ─────────

async def upgrade_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    plot_id = int(parts(update)[2])
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        plot = await _get_plot(s, user, plot_id)

        if not plot:
            await s.commit()
            ok = False
            text = markup = None
        elif plot.level >= config.PLOT_MAX_LEVEL:
            await s.commit()
            return await render_farm(update, alert="⭐ این زمین مکس لوله")
        else:
            price = economy.upgrade_price(plot.level)
            old_mult = config.PLOT_YIELD_MULT[plot.level]
            new_mult = config.PLOT_YIELD_MULT[plot.level + 1]
            text = (
                f"<b>⬆️ آپگرید زمین</b>\n\n"
                f"از لول {fa_num(plot.level)} به {fa_num(plot.level + 1)}\n"
                f"💸 هزینه {money(price)}\n"
                f"📈 درآمد از ×{fa_num(old_mult)} میره رو ×{fa_num(new_mult)}\n"
                "⚡ سرعت رشد هم بهتر میشه\n\n"
                "انجامش بدیم؟"
            )
            markup = kb.confirm_kb(f"cf:farm:up:{plot.id}")
            ok = True
        await s.commit()

    if not ok:
        return await render_farm(update, alert="❌ همچین زمینی نداری")
    await respond(update, text, markup)


async def upgrade_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    plot_id = int(parts(update)[3])
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        plot = await _get_plot(s, user, plot_id)

        if not plot:
            alert = "❌ همچین زمینی نداری"
        elif plot.level >= config.PLOT_MAX_LEVEL:
            alert = "⭐ این زمین مکس لوله"
        else:
            price = economy.upgrade_price(plot.level)
            if user.cash < price:
                alert = "❌ پولت کافی نیس رفیق"
            else:
                user.cash -= price
                plot.level += 1
                alert = f"⬆️ زمین رفت رو لول {fa_num(plot.level)}"
        await s.commit()

    await render_farm(update, alert=alert)
