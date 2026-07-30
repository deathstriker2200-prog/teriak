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
        "🏴 <code>/addxpgroup اسم تیم 500</code>، دادن مستقیم XP به یه تیم (آیدی عددی تیم هم قبوله)\n"
        "💸 <code>/detp 123456789 5000</code> و <code>/dexp 123456789 100</code>، کم کردن مستقیم سکه و تجربه\n"
        "🧨 <code>/clearacc 123456789</code> یا یوزرنیم یا اسم، ریست کامل اکانت به حالت روز اول (با تاییدیه)\n"
        "🔧 /botdown و /botup، خاموش و روشن کلی ربات (مد تعمیر)\n"
        "👻 /hideboard، نامرئی شدن از همه لیدربردها (دوباره بزنی برمی‌گرده)\n"
        "🔄 /update، به‌روزرسانی فوری وضعیت بازی: لود دوباره کانفیگ، رول بازار، بازخوانی ظرفیت تیم‌ها و ریست کش‌ها (آب‌وهوا دست نمی‌خوره)\n"
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

async def hideboard_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """تاگل حالت نامرئی لیدربرد برای ادمین، دوباره بزنی برمی‌گرده"""
    if not _is_admin(update):
        return
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        user.lb_hidden = 0 if user.lb_hidden else 1
        hidden = bool(user.lb_hidden)
        await s.commit()
    if hidden:
        text = "👻 نامرئی شدی، دیگه تو لیدربردها دیده نمیشی\nبرای برگشت دوباره /hideboard بزن"
    else:
        text = "👀 برگشتی، از این به بعد تو لیدربردها دیده میشی"
    await update.message.reply_html(text)


async def update_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    🔄 /update، فقط ادمین: به‌روزرسانی فوری وضعیت بازی
    کانفیگ رو از روی فایل دوباره لود می‌کنه (تغییرای دستی سریع اعمال بشن)،
    بازار رو فورس رول می‌کنه، ظرفیت تیم‌ها رو بازخوانی می‌کنه و کش‌های حافظه رو ریست
    آب‌وهوا دست‌نخورده می‌مونه و سر مرزهای ساعت ایران خودش عوض میشه
    """
    if not _is_admin(update):
        return  # غیرادمین کاملاً بی‌صدا

    import importlib

    from sqlalchemy import func as sa_func, select as sa_select
    from models import Team, TeamMember

    reload_ok = True
    try:
        importlib.reload(config)  # عددهای config.py بدون ری‌استارت اعمال بشن
    except Exception:
        reload_ok = False

    async with session_scope() as s:
        market_rolled = await world_svc.ensure_market(s, force=True)
        # سطح تیم‌های قدیمی روی منحنی سخت‌تر بازنشانی میشه (فقط یه بار اجرا میشه)
        migrated_n = await team_svc.migrate_team_levels(s)
        # شخصیت سگ‌ها هم با همین آپدیت پاک میشه (سیستم شخصیت حذف شده)
        from models import Dog as _Dog
        from sqlalchemy import update as sa_update
        dogs_wiped = (await s.execute(
            sa_update(_Dog).where(_Dog.personality.isnot(None)).values(personality=None)
        )).rowcount or 0
        # ظرفیت تیم‌ها داینامیک از لول حساب میشه؛ اینجا بازخوانی و گزارش سرریز
        all_teams = (await s.execute(sa_select(Team))).scalars().all()
        over: list[tuple[str, int, int]] = []
        for t in all_teams:
            n = (await s.execute(sa_select(sa_func.count(TeamMember.id)).where(TeamMember.team_id == t.id))).scalar() or 0
            cap = team_svc.team_capacity(t)
            if n > cap:
                over.append((t.name, n, cap))
        await s.commit()

    # کش‌های حافظه ریست بشن تا وضعیت‌های قدیمی (ستینگ گیت | عضویت کاربرا) تازه بشن
    fj_svc.invalidate_settings()
    fj_svc.invalidate_members()

    lines = [
        "<b>🔄 وضعیت بازی به‌روز شد</b>",
        "",
        "⚙️ کانفیگ دوباره لود شد" if reload_ok else "⚠️ لود دوباره کانفیگ خطا داد، مقادیر قبلی موندن",
        f"📈 بازار: {'رول فوری انجام شد و قیمت‌ها تازه حساب شدن' if market_rolled else 'بدون تغییر'}",
        f"👥 ظرفیت {fa_num(len(all_teams))} تیم بازخوانی شد",
    ]
    if migrated_n:
        lines.append(f"⭐ سطح {fa_num(migrated_n)} تیم روی منحنی سخت‌تر بازنشانی شد")
    else:
        lines.append("✅ سطح تیم‌ها از قبل روی منحنی جدیده")
    if dogs_wiped:
        lines.append(f"🐕 شخصیت {fa_num(dogs_wiped)} سگ پاک شد (سیستم شخصیت حذف شده)")
    else:
        lines.append("🐕 سگ‌ها دیگه شخصیت ندارن")
    if over:
        lines.append(
            f"⚠️ {fa_num(len(over))} تیم سرریز ظرفیت دارن: "
            + "، ".join(f"{name} ({fa_num(n)}/{fa_num(c)})" for name, n, c in over[:5])
        )
    else:
        lines.append("✅ هیچ تیمی سرریز ظرفیت نیس")
    lines.append("🧹 کش تنظیمات گیت و عضویت کاربرا ریست شد")
    lines.append("🌦 آب‌وهوا دست‌نخورده موند، سر مرزهای ساعت ایران عوض میشه")
    await update.message.reply_html("\n".join(lines))


async def addxpgroup_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    ✨ /addxpgroup [اسم تیم] [مقدار]، فقط ادمین: دادن مستقیم XP به یه تیم
    اسم تیم می‌تونه چندکلمه‌ای باشه، مقدار آخرین آرگومانه؛ با آیدی عددی تیم هم کار می‌کنه
    """
    if not _is_admin(update):
        return
    args = context.args or []
    amount = parse_amount(args[-1]) if len(args) >= 2 else None
    if amount is None or amount <= 0:
        return await update.message.reply_html(
            "❌ فرم درست: <code>/addxpgroup اسم تیم 500</code>\n"
            "اسم تیم (چندکلمه‌ای هم اوکی) یا آیدی عددیش + مقدار xp آخرش"
        )

    from models import Team

    query = " ".join(args[:-1])
    async with session_scope() as s:
        team = None
        if query.isdigit():
            team = await s.get(Team, int(query))
        if team is None:
            team = await team_svc.get_team_by_name(s, query)
        if team is None:
            await s.commit()
            return await update.message.reply_html(f"🤷 تیمی با اسم «{esc(query)}» پیدا نشد")
        notes = await team_svc.give_team_xp(s, team, int(amount))
        t_name, t_level, t_xp, t_cap = team.name, team.level or 1, team.xp or 0, team_svc.team_capacity(team)
        await s.commit()

    lines = [
        f"✨ <b>{fa_num(int(amount))}</b> XP به تیم «{esc(t_name)}» دادی",
        "",
        f"⭐ لول تیم الان {fa_num(t_level)} ـه (✨ {fa_num(t_xp)})",
        f"👥 ظرفیت اعضا {fa_num(t_cap)} نفر",
    ]
    await update.message.reply_html("\n".join(lines))
    # تبریک لول‌آپ تیم (اگه لول‌آپ کرد) به‌صورت پیام جدا
    if notes:
        await update.message.reply_html("\n\n".join(notes))


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
        # آخرین پیام آمار یادش می‌مونه تا جاب ساعتی خودکار ادیتش کنه
        _m = update.callback_query.message if update.callback_query else None
        _cid, _mid = getattr(_m, "chat_id", None), getattr(_m, "message_id", None)
        if _cid is not None and _mid is not None:
            await _remember_stats_msg(_cid, _mid)
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

# کلید متا برای آدرس آخرین پیام آمار، تا جاب ساعتی خودکار ادیتش کنه
STATS_MSG_META_KEY = "admin_stats_msg"


async def _remember_stats_msg(chat_id: int, message_id: int) -> None:
    """آدرس آخرین پیام آمار رو تو متا نگه می‌داره (کامیت همینجاست)"""
    async with session_scope() as s:
        await team_svc.meta_set(s, STATS_MSG_META_KEY, f"{chat_id}:{message_id}")
        await s.commit()


async def stats_autoedit_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    هر ۱ ساعت یه بار آخرین پیام آمار ادمین رو بی‌صدا ادیت می‌کنه
    سبکه، فقط یه خوندن متا + رندر + یه ادیت، اگه پیام پاک شده باشه بی‌صدا رد میشه
    """
    async with session_scope() as s:
        ref = await team_svc.meta_get(s, STATS_MSG_META_KEY)
        await s.commit()
    if not ref or ":" not in ref:
        return
    try:
        chat_id, message_id = (int(x) for x in ref.split(":", 1))
    except ValueError:
        return
    try:
        text = await _stats_text(context.bot)
        await context.bot.edit_message_text(
            text, chat_id=chat_id, message_id=message_id,
            parse_mode="HTML", reply_markup=kb.admin_stats_kb(),
        )
    except Exception:
        pass  # پیام پاک شده یا دسترسی نیس، دور بعد سر فرصت


async def _stats_text(bot=None) -> str:
    """آمار کلی ربات برای ادمین"""
    from datetime import timedelta

    from sqlalchemy import func, select

    from handlers.common import cmd_per_min, proc_avg_ms
    from models import ActionEvent, Dog, GroupActivity, Plot, Team, User
    from utils import now_utc

    async with session_scope() as s:
        hour_ago = now_utc() - timedelta(hours=1)
        day_ago = now_utc() - timedelta(hours=24)
        # آمار بازیکنان: فعال ۱ ساعته و ۲۴ ساعته و جدید + کل
        users_n = (await s.execute(select(func.count(User.id)))).scalar() or 0
        active_h = (await s.execute(
            select(func.count(User.id)).where(User.last_seen_at >= hour_ago)
        )).scalar() or 0
        active_d = (await s.execute(
            select(func.count(User.id)).where(User.last_seen_at >= day_ago)
        )).scalar() or 0
        new_d = (await s.execute(
            select(func.count(User.id)).where(User.created_at >= day_ago)
        )).scalar() or 0
        groups_active_h = (await s.execute(
            select(func.count(GroupActivity.chat_id)).where(GroupActivity.last_active_at >= hour_ago)
        )).scalar() or 0
        groups_active_d = (await s.execute(
            select(func.count(GroupActivity.chat_id)).where(GroupActivity.last_active_at >= day_ago)
        )).scalar() or 0
        groups_n = (await s.execute(select(func.count(GroupActivity.chat_id)))).scalar() or 0
        # فعال‌ترین گروه‌های ساعت جاری ایران، با شمارنده دستورهای ساعتی که touch_group نگه می‌داره
        from utils import now_iran as _nir
        _ir = _nir()
        bucket = f"{_ir.date().isoformat()}-{_ir.hour:02d}"
        top_groups = list((await s.execute(
            select(GroupActivity).where(GroupActivity.hour_key == bucket)
            .order_by(GroupActivity.msgs_hour.desc()).limit(5)
        )).scalars())
        # تعداد پلیرای هر گروه (فعال ۲۴ ساعت اخیر اون گروه) برای جلوی اسم گروه‌های برتر
        from models import GroupPlayer
        gids = [g.chat_id for g in top_groups]
        players_in: dict[int, int] = {}
        if gids:
            pl_rows = (await s.execute(
                select(GroupPlayer.chat_id, func.count(GroupPlayer.user_tg))
                .where(GroupPlayer.chat_id.in_(gids), GroupPlayer.last_active_at >= day_ago)
                .group_by(GroupPlayer.chat_id)
            )).all()
            players_in = {cid: int(n) for cid, n in pl_rows}

        cash_sum = (await s.execute(
            select(func.coalesce(func.sum(User.cash + User.bank_balance), 0))
        )).scalar() or 0
        bank_sum = (await s.execute(
            select(func.coalesce(func.sum(User.bank_balance), 0))
        )).scalar() or 0
        # فقط نقد دست بازیکن‌ها، برای بخش اقتصاد
        hands_sum = (await s.execute(
            select(func.coalesce(func.sum(User.cash), 0))
        )).scalar() or 0
        teams_n = (await s.execute(select(func.count(Team.id)))).scalar() or 0
        dogs_n = (await s.execute(select(func.count(Dog.id)))).scalar() or 0
        # فقط پلات‌هایی که واقعاً در حال رشدن (ready_at نگذشته)، فیلتر روی status ایندکس‌دار
        growing_n = (await s.execute(
            select(func.count(Plot.id)).where(
                Plot.status == "growing", Plot.ready_at > now_utc())
        )).scalar() or 0

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

    # ── متن فنی: زمان پاسخ ربات = پینگ تلگرام + پردازش داخلی، چراغش از سر همین جمعه ──
    def _light(ms: float) -> str:
        if ms < config.PROC_LIGHT_GOOD_MS:
            return "🟢"
        if ms < config.PROC_LIGHT_WARN_MS:
            return "🟡"
        return "🔴"

    if ping_ms is not None and avg_proc_ms is not None:
        resp_ms = int(ping_ms + avg_proc_ms)
        resp_line = f"🚀 زمان پاسخ ربات: {fa_num(resp_ms)}ms {_light(resp_ms)}"
    else:
        resp_line = "🚀 زمان پاسخ ربات: ➖ نامعلوم"
    if ping_ms is None:
        ping_line = "📡 پینگ تلگرام: ➖ نامعلوم"
    else:
        ping_line = f"📡 پینگ تلگرام: {fa_num(ping_ms)}ms"
    if avg_proc_ms is None:
        proc_lines = ["⚙️ پردازش داخلی: هنوز نمونه‌ای نیس"]
    else:
        proc_lines = [
            f"⚙️ پردازش داخلی: {fa_num(avg_proc_ms)}ms",
            f"└ میانگین {fa_num(proc_count)} دستور اخیر",
        ]
    # نرخ دستورهای کاربرا رو پنجره اخیر (چت عادی تو گروه حساب نیس، فقط دستوره)
    rate_cmd, _cmd_n = cmd_per_min()
    if rate_cmd is None:
        cmd_line = "⌨️ میانگین دستور تو دقیقه: هنوز نمونه‌ای نیس"
    else:
        rate_txt = f"{rate_cmd:.1f}".rstrip("0").rstrip(".")
        cmd_line = f"⌨️ میانگین دستور تو دقیقه: {rate_txt}"

    # نرخ فعالیت: چند درصد بازیکن‌ها تو ۲۴ ساعت اخیر سر زدن
    rate = round(active_d * 100 / users_n) if users_n else 0
    attack_n = battle_n + pv_n
    actions_n = attack_n + mine_n + casino_n

    # قالب بخش‌بندی‌شده: عملکرد و بازیکنان بالا، اقتصاد و فعالیت وسط، گروه‌ها ته لیست
    lines = [
        "<b>📊 آمار زنده ربات</b>",
        "",
        "<b>⚡️ عملکرد</b>",
        resp_line,
        ping_line,
        *proc_lines,
        cmd_line,
        "",
        "<b>👥 بازیکنان</b>",
        f"⚡️ فعال ۱ ساعت اخیر: {fa_num(active_h)}",
        f"👤 فعال ۲۴ ساعت اخیر: {fa_num(active_d)}",
        f"🆕 بازیکنان جدید: {fa_num(new_d)}",
        f"🌍 کل بازیکنان: {fa_num(users_n)}",
        f"📈 نرخ فعالیت: %{fa_num(rate)}",
        "",
        "<b>🌍 وضعیت محله</b>",
        f"🏴 تیم‌ها: {fa_num(teams_n)}",
        f"🐕 سگ‌ها: {fa_num(dogs_n)}",
        f"🌱 محصولات در حال رشد: {fa_num(growing_n)}",
        f"🚛 کاروان‌های فعال: {fa_num(len(world_svc.CARAVANS))}",
        "",
        "<b>💰 اقتصاد</b>",
        f"💵 تی‌پوینت کل: {fa_num(cash_sum)}",
        f"🏦 موجودی بانک: {fa_num(bank_sum)}",
        f"💸 دست بازیکنان: {fa_num(hands_sum)}",
        "",
        "<b>🔥 فعالیت ۲۴ ساعت اخیر</b>",
        f"⛏️ استخراج: {fa_num(mine_n)}",
        f"⚔️ حمله: {fa_num(attack_n)}",
        f"🎰 قمار: {fa_num(casino_n)}",
        f"📊 مجموع اکشن‌ها: {fa_num(actions_n)}",
        "",
        "<b>🏘 گروه‌ها</b>",
        f"🟢 فعال ۱ ساعت اخیر: {fa_num(groups_active_h)}",
        f"👥 فعال ۲۴ ساعت اخیر: {fa_num(groups_active_d)}",
        f"🌐 کل گروه‌ها: {fa_num(groups_n)}",
    ]
    if top_groups:
        # شمارنده ساعتی، «دستورهای» این ساعت گروهه نه همه پیام‌ها (فعالیت = دستور)
        lines += ["", "<b>🏆 فعال‌ترین گروه‌های این ساعت</b>"]
        badges = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
        for i, g in enumerate(top_groups):
            gname = esc(g.title) if g.title else f"گروه {fa_num(g.chat_id)}"
            lines.append(
                f"{badges[i]} {gname} ⌨️ {fa_num(g.msgs_hour or 0)} دستور"
                f" │ 👥 {fa_num(players_in.get(g.chat_id, 0))}"
            )
    lines += [
        "",
        "⏱ آمار زنده‌ست، با 🔃 به‌روزرسانی میشه",
    ]
    return "\n".join(lines)


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
