"""
پنل ادمین، دادن پول و XP به خودت + مدیریت کاربرا
/user @silktoch یا /user 123456789 یا /user بخشی‌از‌اسم → پیدا کردن و دیدن پروفایل و پول/XP دادن
/addtp [آیدی عددی] [مبلغ] | /addxp [آیدی عددی] [مقدار] → دادن مستقیم
به غریبه‌ها کاملاً بی‌صداس
"""

from telegram import Update
from telegram.ext import ContextTypes

import config
from database import session_scope
from handlers.common import parts, respond
from keyboards import keyboards as kb
from services import economy, users
from services import forcejoin as fj_svc
from services import teams as team_svc
from services import world as world_svc
from utils import esc, fa_num, jalali_str, money, parse_amount


def _is_admin(update: Update) -> bool:
    return bool(update.effective_user) and update.effective_user.id in config.ADMIN_IDS


def _panel_text(user, extra: str | None = None) -> str:
    text = (
        "<b>👑 پنل ادمین</b>\n\n"
        f"💵 {money(user.cash)}\n"
        f"⭐ لول {fa_num(user.level)} | ✨ {fa_num(user.xp)} از {fa_num(economy.xp_need(user.level))}\n\n"
        "چی بر داری؟\n\n"
        "<b>دستورهای مدیریتی:</b>\n"
        "▫️ <code>/user @username</code> یا <code>/user 123456789</code> یا بخشی از اسم، پیداش کن، پروفایلش رو ببین و از همونجا پول/XP بده\n"
        "▫️ <code>/addtp 123456789 5000</code>، واریز مستقیم تی‌پوینت\n"
        "▫️ <code>/addxp 123456789 100</code>، دادن مستقیم تجربه\n"
        "▫️ /backup و /upload_backup، بک‌آپ و ری‌استور"
    )
    if extra:
        text += f"\n\n{extra}"
    return text


async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return  # ادمین به پلیرهای عادی واکنش نشون نمیده

    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        text = _panel_text(user)
        await s.commit()

    await respond(update, text, kb.admin_kb())


async def _user_card_text(session, target) -> str:
    """کارت پروفایل یه کاربر برای پنل ادمین"""
    name = esc(users.display_name(target))
    uname = f"@{esc(target.username)}" if target.username else "بدون یوزرنیم"
    team = await team_svc.get_team_of(session, target.id)
    team_line = f"\n🏴 تیم «{esc(team.name)}»" if team else ""
    joined = jalali_str(target.created_at) if target.created_at else "—"
    return (
        f"<b>👤 {name}</b>\n\n"
        f"🆔 {uname} | <code>{target.telegram_id}</code>\n"
        f"⭐ لول {fa_num(target.level)} | ✨ {fa_num(target.xp)} از {fa_num(economy.xp_need(target.level))}\n"
        f"💵 نقدی {money(target.cash)}\n"
        f"🏦 بانک {money(target.bank_balance)} (لول {fa_num(target.bank_level)})\n"
        f"🏚 پناهگاه لول {fa_num(target.shelter_level)}{team_line}\n"
        f"✅ برد {fa_num(target.wins)} | ❌ باخت {fa_num(target.losses)}\n"
        f"🗓 عضو {joined}"
    )


# ───────── /user، پیدا کردن کاربر ─────────

async def user_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return

    query = " ".join(context.args or []).strip()
    if not query:
        return await update.message.reply_html(
            "❌ فرم درست: <code>/user @username</code> یا <code>/user 123456789</code> یا <code>/user بخشی از اسم</code>"
        )

    async with session_scope() as s:
        found = await users.search_users(s, query)
        if not found:
            await s.commit()
            return await update.message.reply_html(f"🤷 کسی با «{esc(query)}» پیدا نشد")

        if len(found) == 1:
            target = found[0]
            text = await _user_card_text(s, target)
            tg_id = target.telegram_id
            await s.commit()
            return await update.message.reply_html(text, reply_markup=kb.admin_user_kb(tg_id))

        names = "\n".join(f"▫️ {esc(users.display_name(u))} | <code>{u.telegram_id}</code>" for u in found)
        await s.commit()

    await update.message.reply_html(
        f"<b>👥 {fa_num(len(found))} نفر پیدا شدن</b>\n\n{names}\n\nروش بزن تا کارتش رو ببینی 👇",
        reply_markup=kb.admin_users_kb(found),
    )


# ───────── /addtp و /addxp، دادن مستقیم ─────────

async def addtp_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    args = context.args or []
    if len(args) < 2 or not args[0].lstrip("-").isdigit() or parse_amount(args[1]) is None:
        return await update.message.reply_html(
            "❌ فرم درست: <code>/addtp 123456789 5000</code>\n"
            "آیدی عددی طرف + مبلغ"
        )

    tg_id = int(args[0])
    amount = parse_amount(args[1])
    async with session_scope() as s:
        target = await users.get_by_tg(s, tg_id)
        if target is None:
            await s.commit()
            return await update.message.reply_html("❌ کاربری با این آیدی تو بازی نیس")
        target.cash += amount
        name = esc(users.display_name(target))
        cash = target.cash
        await s.commit()

    await update.message.reply_html(
        f"<b>💰 {money(amount)} واریز شد به {name}</b>\n\n"
        f"موجودی جدیدش {money(cash)}"
    )


async def addxp_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    args = context.args or []
    if len(args) < 2 or not args[0].lstrip("-").isdigit() or parse_amount(args[1]) is None:
        return await update.message.reply_html(
            "❌ فرم درست: <code>/addxp 123456789 100</code>\n"
            "آیدی عددی طرف + مقدار تجربه"
        )

    tg_id = int(args[0])
    amount = parse_amount(args[1])
    async with session_scope() as s:
        target = await users.get_by_tg(s, tg_id)
        if target is None:
            await s.commit()
            return await update.message.reply_html("❌ کاربری با این آیدی تو بازی نیس")
        notes = users.add_xp(target, amount)
        name = esc(users.display_name(target))
        level = target.level
        await s.commit()

    text = f"<b>✨ {fa_num(amount)} تجربه دادی به {name}</b>\n\n⭐ الان لول {fa_num(level)} ـه"
    if notes:
        text += "\n\n" + "\n".join(notes)
    await update.message.reply_html(text)


# ───────── دکمه‌های پنل (خودی + کارت کاربر) ─────────

async def admin_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        await update.callback_query.answer()
        return

    _, kind, value = parts(update)
    num = int(value)

    # ── برگشت به پنل ──
    if kind == "panel":
        async with session_scope() as s:
            user, _ = await users.get_or_create(s, update.effective_user)
            text = _panel_text(user)
            await s.commit()
        return await respond(update, text, kb.admin_kb())

    # ── 📊 آمار ربات ──
    if kind == "stats":
        text = await _stats_text()
        return await respond(update, text, kb.admin_stats_kb())

    # ── 📢 عضویت اجباری ──
    if kind == "fj":
        return await respond(update, await _fj_text(), await _fj_kb())

    if kind == "fjtog":
        async with session_scope() as s:
            st = await fj_svc.get_settings(s)
            await fj_svc.set_enabled(s, not st["on"])
            await s.commit()
        return await respond(update, await _fj_text(), await _fj_kb(),
                             alert="وضعیت عضویت اجباری عوض شد ✅")

    if kind == "fjdel":
        async with session_scope() as s:
            await fj_svc.clear_channel(s)
            await s.commit()
        return await respond(update, await _fj_text(), await _fj_kb(),
                             alert="کانل عضویت اجباری پاک شد 🗑")

    if kind == "fjset":
        async with session_scope() as s:
            me, _ = await users.get_or_create(s, update.effective_user)
            me.pending_action = "fjchan"
            me.pending_value = None
            await s.commit()
        return await respond(
            update,
            "<b>🔗 ست کردن کانال عضویت اجباری</b>\n\n"
            "یوزرنیم یا لینک کانال رو بفرست، مثلا:\n"
            "▫️ <code>@mychannel</code>\n"
            "▫️ <code>https://t.me/mychannel</code>\n\n"
            "کانال خصوصی؟ آیدی عددی + لینک دعوت بفرست:\n"
            "▫️ <code>-1001234567890 https://t.me/+AbCdEfGh</code>\n\n"
            "⚠️ ربات باید توی کانال ادمین باشه تا بتونه عضویت رو چک کنه\n\n"
            "❌ پشیمون شدی بنویس «لغو»",
        )

    # ── کارت یه کاربر ──
    if kind == "u":
        async with session_scope() as s:
            target = await users.get_by_tg(s, num)
            if target is None:
                await s.commit()
                await update.callback_query.answer("❌ پیداش نکردم", show_alert=True)
                return
            text = await _user_card_text(s, target)
            await s.commit()
        return await respond(update, text, kb.admin_user_kb(num))

    # ── شروع فلو پول/XP دادن به کاربر، مبلغ رو با پیام بعدی می‌پرسیم ──
    if kind in ("gtp", "gxp"):
        async with session_scope() as s:
            target = await users.get_by_tg(s, num)
            me, _ = await users.get_or_create(s, update.effective_user)
            if target is None:
                await s.commit()
                return await respond(update, "❌ طرف پیدا نشد", kb.admin_kb())
            me.pending_action = "admtp" if kind == "gtp" else "admxp"
            me.pending_value = str(num)
            name = esc(users.display_name(target))
            await s.commit()
        label = "💰 چند تی‌پوینت" if kind == "gtp" else "✨ چند XP"
        return await respond(
            update,
            f"<b>{label} به {name} بدیم؟</b>\n\n"
            "فقط عددشو بفرست، مثلا 5000\n\n"
            "❌ پشیمون شدی بنویس «لغو»",
        )

    # ── دادن به خودت (پنل کلاسیک) ──
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)

        if kind == "cash":
            user.cash += num
            alert = f"💵 {money(num)} اضافه شد"
            extra = None
        elif kind == "xp":
            notes = users.add_xp(user, num)
            alert = f"✨ {fa_num(num)} XP اضافه شد"
            extra = "\n".join(notes) if notes else None
        else:
            alert = "❌ چیزی نیست که"
            extra = None

        text = _panel_text(user, extra)
        await s.commit()

    await respond(update, text, kb.admin_kb(), alert=alert)


# ───────── 📊 آمار ربات ─────────

async def _stats_text() -> str:
    """آمار کلی ربات برای ادمین"""
    from datetime import timedelta

    from sqlalchemy import func, select

    from models import Dog, GroupActivity, Plot, Team, User
    from utils import now_utc

    async with session_scope() as s:
        day_ago = now_utc() - timedelta(hours=24)
        users_n = (await s.execute(select(func.count(User.id)))).scalar() or 0
        active_n = (await s.execute(
            select(func.count(User.id)).where(User.last_seen_at >= day_ago)
        )).scalar() or 0
        cash_sum = (await s.execute(
            select(func.coalesce(func.sum(User.cash + User.bank_balance), 0))
        )).scalar() or 0
        teams_n = (await s.execute(select(func.count(Team.id)))).scalar() or 0
        dogs_n = (await s.execute(select(func.count(Dog.id)))).scalar() or 0
        plots_n = (await s.execute(select(func.count(Plot.id)))).scalar() or 0
        groups_n = (await s.execute(select(func.count(GroupActivity.chat_id)))).scalar() or 0
        await s.commit()

    return (
        "<b>📊 آمار ربات</b>\n\n"
        f"👥 کاربرا: {fa_num(users_n)} نفر\n"
        f"🟢 فعال 24 ساعت اخیر: {fa_num(active_n)} نفر\n"
        f"🏘 گروه‌های فعال: {fa_num(groups_n)}\n"
        f"🏴 تیم‌ها: {fa_num(teams_n)}\n"
        f"🐕 سگ‌ها: {fa_num(dogs_n)}\n"
        f"🗺 زمین‌ها: {fa_num(plots_n)}\n"
        f"💰 مجموع تی‌پوینت کل بازیکنا: {money(cash_sum)}\n"
        f"🚛 کاروان زنده الان: {fa_num(len(world_svc.CARAVANS))}\n\n"
        "⏱ آمار زنده‌ست، با 🔃 رفرش میشه"
    )


# ───────── 📢 عضویت اجباری ─────────

async def _fj_text() -> str:
    async with session_scope() as s:
        st = await fj_svc.get_settings(s)
        await s.commit()
    st_link = st["link"] or ""
    if st["channel"]:
        state = "🟢 فعال" if st["on"] else "🔴 غیرفعال"
        return (
            "<b>📢 عضویت اجباری</b>\n\n"
            f"▫️ کانال: <code>{esc(st['channel'])}</code>\n"
            f"▫️ لینک: {esc(st_link)}\n"
            f"▫️ وضعیت: {state}\n\n"
            "هر دستوری که زده بشه اول عضویت کاربر چک میشه، "
            "عضو نباشه پیام گیت با دکمه عضویت و تایید می‌گیره\n\n"
            "⚠️ یادت نره ربات توی کانال ادمین باشه"
        )
    return (
        "<b>📢 عضویت اجباری</b>\n\n"
        "هنوز کانالی ست نشده\n\n"
        "با «🔗 ست کردن کانال» یوزرنیم یا لینک کانال رو بفرست، خاموش/روشنش هم می‌تونی کنی\n\n"
        "⚠️ ربات باید توی کانال ادمین باشه تا عضویت‌ها رو بتونه چک کنه"
    )


async def _fj_kb():
    async with session_scope() as s:
        st = await fj_svc.get_settings(s)
        await s.commit()
    return kb.admin_fj_kb(st)
