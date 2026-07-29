"""
پنل ادمین، دادن پول و XP به خودت + مدیریت کاربرا
/user @silktoch یا /user 123456789 یا /user بخشی‌از‌اسم → پیدا کردن و دیدن پروفایل و پول/XP دادن
/addtp [آیدی عددی] [مبلغ] | /addxp [آیدی عددی] [مقدار] → دادن مستقیم
به غریبه‌ها کاملاً بی‌صداس
"""

import time

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
        "👤 <code>/user @username</code> یا <code>/user 123456789</code> یا بخشی از اسم، پیداش کن، پروفایلش رو ببین و از همونجا پول/XP بده\n"
        "💵 <code>/addtp 123456789 5000</code>، واریز مستقیم تی‌پوینت\n"
        "✨ <code>/addxp 123456789 100</code>، دادن مستقیم تجربه\n"
        "💸 <code>/detp 123456789 5000</code> و <code>/dexp 123456789 100</code>، کم کردن مستقیم سکه و تجربه\n"
        "🧨 <code>/clearacc 123456789</code> یا یوزرنیم یا اسم، ریست کامل اکانت به حالت روز اول (با تاییدیه)\n"
        "🔧 /botdown و /botup، خاموش و روشن کلی ربات (مد تعمیر)\n"
        "💾 /backup و /upload_backup، بک‌آپ و ری‌استور\n"
        "🔌 /botoff و /boton توی گروه، خاموش و روشن کردن ربات فقط تو همون گروه"
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
    await update.message.reply_html(text)
    # پیام تبریک لول‌آپ جدا میاد، قاطی گزارش ادمین نمیشه
    from handlers.common import announce_notes
    await announce_notes(update, notes)


# ───────── /detp و /dexp، کم کردن مستقیم ─────────

async def detp_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    args = context.args or []
    if len(args) < 2 or not args[0].lstrip("-").isdigit() or parse_amount(args[1]) is None:
        return await update.message.reply_html(
            "❌ فرم درست: <code>/detp 123456789 5000</code>\n"
            "آیدی عددی طرف + مبلغ"
        )

    tg_id = int(args[0])
    amount = parse_amount(args[1])
    async with session_scope() as s:
        target = await users.get_by_tg(s, tg_id)
        if target is None:
            await s.commit()
            return await update.message.reply_html("❌ کاربری با این آیدی تو بازی نیس")
        target.cash = max(0, target.cash - amount)
        name = esc(users.display_name(target))
        cash = target.cash
        await s.commit()

    await update.message.reply_html(
        f"<b>💸 {money(amount)} از {name} کم شد</b>\n\n"
        f"موجودی جدیدش {money(cash)}"
    )


async def dexp_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return
    args = context.args or []
    if len(args) < 2 or not args[0].lstrip("-").isdigit() or parse_amount(args[1]) is None:
        return await update.message.reply_html(
            "❌ فرم درست: <code>/dexp 123456789 100</code>\n"
            "آیدی عددی طرف + مقدار تجربه"
        )

    tg_id = int(args[0])
    amount = parse_amount(args[1])
    async with session_scope() as s:
        target = await users.get_by_tg(s, tg_id)
        if target is None:
            await s.commit()
            return await update.message.reply_html("❌ کاربری با این آیدی تو بازی نیس")
        target.xp = max(0, target.xp - amount)
        name = esc(users.display_name(target))
        xp = target.xp
        await s.commit()

    await update.message.reply_html(
        f"<b>✨ {fa_num(amount)} تجربه از {name} کم شد</b>\n\n"
        f"⭐ الان ✨ {fa_num(xp)} تجربه داره"
    )


# ───────── /clearacc، ریست کامل اکانت ─────────

async def clearacc_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return

    query = " ".join(context.args or []).strip()
    if not query:
        return await update.message.reply_html(
            "❌ فرم درست: <code>/clearacc 123456789</code> یا <code>/clearacc @username</code> یا بخشی از اسم"
        )

    async with session_scope() as s:
        found = await users.search_users(s, query)
        if not found:
            await s.commit()
            return await update.message.reply_html(f"🤷 کسی با «{esc(query)}» پیدا نشد")
        if len(found) > 1:
            names = "\n".join(f"▫️ {esc(users.display_name(u))} | <code>{u.telegram_id}</code>" for u in found)
            await s.commit()
            return await update.message.reply_html(
                f"<b>👥 {fa_num(len(found))} نفر پیدا شدن، دقیق‌تر بگو:</b>\n\n{names}"
            )
        target = found[0]
        name = esc(users.display_name(target))
        uname = f"@{esc(target.username)}" if target.username else "بدون یوزرنیم"
        tg_id = target.telegram_id
        level, cash = target.level, target.cash
        await s.commit()

    text = (
        "<b>🧨 ریست اکانت</b>\n\n"
        f"می‌خوای حساب «{name}» ({uname} | <code>{tg_id}</code>) رو کامل پاک کنی؟\n\n"
        f"⭐ لول {fa_num(level)} و 💵 {money(cash)} و همه زمین‌ها و سگ‌ها و آیتم‌هاش می‌پره\n"
        f"برمی‌گرده به حالت روز اول با {money(config.START_CASH)}\n\n"
        "انجامش بدیم؟"
    )
    await update.message.reply_html(text, reply_markup=kb.clearacc_confirm_kb(tg_id))


async def clearacc_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """تایید/لغو ریست اکانت، فقط ادمین"""
    if not _is_admin(update):
        await update.callback_query.answer()
        return
    _, action, raw = parts(update)
    tg_id = int(raw)

    if action == "no":
        return await respond(update, "<b>😅 بی‌خیال ریست شدیم</b>\n\nاکانت دست نخورده موند", kb.admin_kb())

    async with session_scope() as s:
        target = await users.get_by_tg(s, tg_id)
        if target is None:
            await s.commit()
            return await respond(update, "❌ طرف دیگه تو بازی نیس", kb.admin_kb())
        name = esc(users.display_name(target))
        await users.wipe_account(s, target)
        await s.commit()

    await respond(
        update,
        f"<b>✅ اکانت «{name}» ریست شد</b>\n\n"
        f"همه چیش پاک شد، الان مثل روز اوله\n"
        f"💰 {money(config.START_CASH)} تو جیبشه",
        kb.admin_kb(),
    )
    # به خود طرف هم خبر بدیم، استارت کرده باشه
    try:
        await context.bot.send_message(
            tg_id,
            "<b>🔄 اکانتت ریست شد</b>\n\n"
            f"حسابت توسط مدیریت به حالت روز اول برگشت\n"
            f"💰 دوباره با {money(config.START_CASH)} شروع می‌کنی",
            parse_mode="HTML",
        )
    except Exception:
        pass


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
        text = await _stats_text(context.bot)
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
            notes = None
        elif kind == "xp":
            notes = users.add_xp(user, num)
            alert = f"✨ {fa_num(num)} XP اضافه شد"
        else:
            alert = "❌ چیزی نیست که"
            notes = None

        text = _panel_text(user)
        await s.commit()

    await respond(update, text, kb.admin_kb(), alert=alert)
    # تبریک لول‌آپ پیام جداشو داره، قاطی پنل نمیشه
    from handlers.common import announce_notes
    await announce_notes(update, notes)


# ───────── 📊 آمار ربات ─────────

async def _stats_text(bot=None) -> str:
    """آمار کلی ربات برای ادمین"""
    from datetime import timedelta

    from sqlalchemy import func, select

    from handlers.common import proc_avg_ms, proc_light
    from models import ActionEvent, Dog, GroupActivity, Plot, Team, User
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

        # ── اقتصاد و اقلام، همه با SUM/COUNT مستقیم توی SQL ──
        res_row = (await s.execute(select(
            func.coalesce(func.sum(User.wood), 0),
            func.coalesce(func.sum(User.iron), 0),
        ))).one()
        wood_sum, iron_sum = int(res_row[0]), int(res_row[1])
        # فقط پلات‌هایی که واقعاً در حال رشدن (ready_at نگذشته)، فیلتر روی status ایندکس‌دار
        growing_n = (await s.execute(
            select(func.count(Plot.id)).where(
                Plot.status == "growing", Plot.ready_at > now_utc())
        )).scalar() or 0
        # پول بانک‌ها جدا از نقد، تا نسبت پول امن و در معرض خطر معلوم بشه
        bank_sum = (await s.execute(
            select(func.coalesce(func.sum(User.bank_balance), 0))
        )).scalar() or 0
        stay_sum = cash_sum - bank_sum

        # ── فعالیت ۲۴ ساعت اخیر، COUNT گروه‌بندی‌شده روی ایندکس (action, at) ──
        ev_rows = (await s.execute(
            select(ActionEvent.action, func.count(ActionEvent.id))
            .where(ActionEvent.at >= day_ago)
            .group_by(ActionEvent.action)
        )).all()
        ev = {action: n for action, n in ev_rows}
        battle_n = int(ev.get("battle", 0))
        pv_n = int(ev.get("pvattack", 0))
        mine_n = int(ev.get("mine", 0))
        casino_n = int(ev.get("casino", 0))
        # تازه‌واردها نه فقط فعال‌ها، فیلتر روی created_at ایندکس‌دار
        new_n = (await s.execute(
            select(func.count(User.id)).where(User.created_at >= day_ago)
        )).scalar() or 0

        # ── لول و پیشرفت، AVG و MAX مستقیم توی SQL ──
        avg_lvl = (await s.execute(
            select(func.avg(User.level)).where(User.last_seen_at >= day_ago)
        )).scalar()
        max_lvl = (await s.execute(select(func.max(User.level)))).scalar() or 0
        await s.commit()

    # ── فنی، پینگ API تلگرام با یه فراخوانی سبک (بدون bot، نامعلومه) ──
    ping_ms = None
    if bot is not None:
        try:
            t0 = time.monotonic()
            await bot.get_me()
            ping_ms = int((time.monotonic() - t0) * 1000)
        except Exception:
            ping_ms = None
    avg_proc_ms, proc_count = proc_avg_ms()

    # ── متن فنی ──
    if ping_ms is None:
        ping_line = "📡 پینگ API تلگرام: ➖ نامعلوم"
    else:
        ping_line = f"📡 پینگ API تلگرام: {fa_num(ping_ms)}ms {proc_light(ping_ms)}"
    if avg_proc_ms is None:
        proc_line = "⚙️ پردازش داخلی: هنوز نمونه‌ای نیس"
    else:
        proc_line = (
            f"⚙️ پردازش داخلی: {fa_num(avg_proc_ms)}ms {proc_light(avg_proc_ms)} "
            f"(میانگین آخرین {fa_num(proc_count)} دستور)"
        )
    avg_lvl_txt = f"{avg_lvl:.1f}" if avg_lvl is not None else "➖ نامعلوم"

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
        "<b>📦 اقتصاد و اقلام</b>\n\n"
        f"🎒 مجموع انبار کل بازیکنا: {fa_num(wood_sum + iron_sum)} (چوب {fa_num(wood_sum)} | آهن {fa_num(iron_sum)})\n"
        f"🌱 بذر کاشته‌شده فعال: {fa_num(growing_n)} پلات\n"
        f"🏦 پول داخل بانک‌ها: {money(bank_sum)}\n"
        f"💵 نقد بیرون بانک (در معرض خطر): {money(stay_sum)}\n\n"
        "<b>🔥 فعالیت 24 ساعت اخیر</b>\n\n"
        f"⚔️ نبردها: {fa_num(battle_n + pv_n)} (گروهی {fa_num(battle_n)} | پی‌وی {fa_num(pv_n)})\n"
        f"⛏ کنده‌کاری: {fa_num(mine_n)}\n"
        f"🎰 دست‌های قمارخانه: {fa_num(casino_n)}\n"
        f"🆕 کاربر جدید: {fa_num(new_n)} نفر\n\n"
        "<b>📈 لول و پیشرفت</b>\n\n"
        f"⭐ میانگین لول فعال‌های 24 ساعت اخیر: {avg_lvl_txt}\n"
        f"🏆 بالاترین لول ثبت‌شده: {fa_num(max_lvl)}\n\n"
        "<b>🛠 فنی</b>\n\n"
        f"{ping_line}\n"
        f"{proc_line}\n\n"
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
