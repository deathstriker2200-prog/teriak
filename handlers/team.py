"""
تیم 🏴 — ساخت (لول ۱۰) | جوین (لول ۵) | آمار با «تیم [اسم]» | بیو | ترک/انحلال
کوئست روزانه گروهی با «کوئست» | کنده‌کاری تیمی با «کنده کاری تیمی» (حداقل ۳ نفر، ۷۰٪ اعضا)
امتیاز تیمی + لیدربرد هفتگی («تیم لیدربرد») | ساختمان حمله/دفاع با آپگرید رهبر («تیم ساختمان»)
بانک تیم («تیم بانک») + کمک مالی اعضا («تیم واریز 1200») | لیست اعضا («تیم عضویت»)
"""

import re

from telegram import Update
from telegram.error import BadRequest
from telegram.ext import ContextTypes

import config
from database import session_scope
from handlers.common import parts, respond, strip_home
from keyboards import keyboards as kb
from services import teams, users
from utils import esc, fa_dur, fa_num, money, money_tp, parse_amount


# ───────── متن‌ها ─────────

def _no_team_text() -> str:
    return (
        "<b>🏴 تیم نداری</b>\n\n"
        f"👑 ساخت تیم از لول {fa_num(config.TEAM_CREATE_MIN_LEVEL)} و با {money(config.TEAM_CREATE_COST)} — «ساخت تیم» بزن و اسمشو بفرست\n"
        f"🤝 عضویت تو تیم رفیقات از لول {fa_num(config.TEAM_JOIN_MIN_LEVEL)} — «جوین تیم [اسم]»\n\n"
        "📜 کوئست‌های روزانه جمعی جایزه به همه میدن\n"
        "⛏ کنده‌کاری تیمی هم پول میریزه تو خزانه\n\n"
        "🏆 «تیم» رو بزن تا برترین تیم‌ها رو ببینی"
    )


def _team_stats_text(data: dict) -> str:
    team = data["team"]
    created = team.created_at.strftime("%Y/%m/%d") if team.created_at else "—"

    lines = [f"<b>🏴 تیم «{esc(team.name)}»</b>"]
    if team.bio:
        lines.append(f"📜 <i>{esc(team.bio)}</i>")
    lines.append("")
    lines.append(f"👑 رهبر: {esc(data['owner_name'])}")
    lines.append(f"👥 اعضا: {fa_num(data['count'])} از {fa_num(config.TEAM_MAX_MEMBERS)}")
    lines.append(f"🏦 خزانه: {money(team.bank)}")
    lines.append("")
    lines.append("━━━━━━ 📊 آمار تیم ━━━━━━")
    lines.append(f"⚔️ برد اعضا {fa_num(data['wins'])} | ❌ باخت {fa_num(data['losses'])}")
    lines.append(f"⭐ مجموع لول اعضا {fa_num(data['level_sum'])}")
    lines.append(f"🎯 کشتارهای تیم {fa_num(team.total_kills)} | 🌾 برداشت‌های تیم {fa_num(team.total_harvests)}")
    lines.append(f"💎 امتیاز تیم {fa_num(team.points)} | 📅 امتیاز این هفته {fa_num(team.week_points)}")
    atk_pct = int(config.TEAM_ATK_BONUS_PER_LEVEL * (team.atk_bld or 0) * 100)
    def_pct = int(config.TEAM_DEF_BONUS_PER_LEVEL * (team.def_bld or 0) * 100)
    lines.append(
        f"🏗 ساختمان حمله لول {fa_num(team.atk_bld or 0)} (+{fa_num(atk_pct)}٪)"
        f" | ساختمان دفاع لول {fa_num(team.def_bld or 0)} (+{fa_num(def_pct)}٪)"
    )
    lines.append(f"📅 ساخته شده {created}")
    lines.append("")
    lines.append("━━━━━━ 👥 اعضا ━━━━━━")

    by_id = {u.id: u for u in data["users"]}
    shown = 0
    for m in data["members"]:
        u = by_id.get(m.user_id)
        if not u or shown >= 12:
            continue
        tag = "👑" if m.role == "owner" else "🔸"
        name = u.first_name or u.username or "؟"
        lines.append(f"{tag} {esc(name)} | لول {fa_num(u.level)}")
        shown += 1
    if data["count"] > shown:
        lines.append(f"🔸 و {fa_num(data['count'] - shown)} نفر دیگه")

    lines.append("")
    lines.append("━━━━━━ 📜 کوئست امروز ━━━━━━")
    lines.extend(_quest_lines(data["daily"]))
    return "\n".join(lines)


def _quest_lines(daily) -> list[str]:
    lines: list[str] = []
    for q in teams.quests_view(daily):
        if q["done"]:
            state = f"✅ انجام شد — {money(q['reward'])} به همه رسید"
        else:
            state = f"{fa_num(q['progress'])} از {fa_num(q['target'])}"
        lines.append(f"{q['emoji']} {esc(q['title'])} — {state}")
    return lines


def _quests_text(team_name: str, daily) -> str:
    lines = [f"<b>📜 کوئست‌های امروز تیم «{esc(team_name)}»</b>", ""]
    for q in teams.quests_view(daily):
        if q["done"]:
            state = "✅ کامل شد"
        else:
            state = f"{fa_num(q['progress'])} از {fa_num(q['target'])}"
        lines.append(f"{q['emoji']} <b>{esc(q['title'])}</b>")
        lines.append(f"پیشرفت: {state}")
        lines.append(f"🎁 جایزه: {money(q['reward'])} برای هر عضو")
        lines.append(f"<i>{esc(q['desc'])}</i>")
        lines.append("")
    lines.append("🕛 هر روز ریست میشن — استعلام با «کوئست»")
    return "\n".join(lines)


def _mine_progress_text(res: dict) -> str:
    team = res["team"]
    joined, needed, m_count = res["joined"], res["needed"], res["member_count"]
    remaining = max(0, needed - joined)
    pct = int(config.TEAM_MINE_JOIN_PCT * 100)

    text = (
        f"<b>⛏ کنده‌کاری تیمی — تیم «{esc(team.name)}»</b>\n\n"
        f"لازمه {fa_num(pct)}٪ اعضا ({fa_num(needed)} نفر از {fa_num(m_count)}) دستور رو بزنن\n\n"
        f"{fa_num(joined)} نفر از {fa_num(m_count)} نفر به کنده‌کاری پیوستند\n"
    )
    if remaining:
        text += f"{fa_num(remaining)} نفر تا تکمیل کنده‌کاری\n"
        text += f"\n⏳ تا {fa_dur(config.TEAM_MINE_WINDOW_SECONDS)} دیگه فرصت\nبقیه اعضا هم بنویسن «کنده کاری تیمی»"
    return text.rstrip()


def _mine_complete_text(res: dict) -> str:
    team = res["team"]
    return (
        "<b>✅ کنده‌کاری تیمی کامل شد</b>\n\n"
        f"تیم «{esc(team.name)}» ته کار رو گرفت 😈\n"
        f"💰 {money(res['reward'])} رفت تو خزانه تیم\n"
        f"🏦 خزانه الان {money(res['bank'])} ـه\n\n"
        f"⏳ کنده‌کاری بعدی {fa_num(config.TEAM_MINE_COOLDOWN_MINUTES)} دقیقه دیگه"
    )


# ───────── تیم من / آمار تیم ─────────

async def render_my_team(update: Update, alert: str | None = None) -> None:
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        membership = await teams.get_membership(s, user.id)
        team = await teams.get_team_of(s, user.id)
        if not membership or not team:
            await s.commit()
            return await respond(update, _no_team_text(), kb.team_no_kb(), alert=alert)

        data = await teams.team_stats_data(s, team)
        is_owner = membership.role == "owner"
        text = _team_stats_text(data)
        await s.commit()

    await respond(update, text, kb.team_kb(is_owner), alert=alert)


async def team_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await render_my_team(update)


async def team_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """«تیم» «تیم من» «تیم [اسم]» — آمار تیم با دستور خاص"""
    arg = ""
    txt = (update.message.text or "").strip()
    p = txt.split(None, 1)
    if len(p) > 1:
        arg = p[1].strip()

    if not arg:
        # بدون اسم — اگه تیمی دارم مال خودم، وگرنه برترین‌ها
        async with session_scope() as s:
            user, _ = await users.get_or_create(s, update.effective_user)
            membership = await teams.get_membership(s, user.id)
            await s.commit()
        if membership:
            return await render_my_team(update)
        return await top_teams_text(update, context)

    if arg in ("من", "خودم"):
        return await render_my_team(update)

    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        team = await teams.get_team_by_name(s, arg)
        if not team:
            await s.commit()
            return await respond(update, f"🤷 تیمی با اسم «{esc(arg)}» پیدا نشد\n\nآمار هر تیم با «تیم [اسم]» — مثلا «تیم فوتبالیست‌ها»")
        data = await teams.team_stats_data(s, team)
        text = _team_stats_text(data)
        await s.commit()

    await respond(update, text)


async def _announce_winners(context: ContextTypes.DEFAULT_TYPE, winners: list[dict]) -> None:
    """پیام خصوصی جایزه هفتگی به اعضای تیم‌های برنده — بیشترین تلاش، بی‌صدا رد میشه"""
    if context is None or not winners:
        return
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    per_team: list[tuple[dict, list[int]]] = []
    async with session_scope() as s:
        for w in winners:
            tg_ids = await teams.member_telegram_ids(s, w["team"].id)
            per_team.append((w, tg_ids))
        await s.commit()

    for w, tg_ids in per_team:
        text = (
            f"<b>{medals[w['rank']]} تیم «{esc(w['team'].name)}» مقام {fa_num(w['rank'])} هفته رو گرفت</b>\n\n"
            f"💎 با {fa_num(w['points'])} امتیاز هفتگی\n"
            f"🎁 {money(w['prize'])} به بانک تیم واریز شد\n\n"
            "هفته جدید شروع شده — دوباره بجنگین 💪"
        )
        for tg in tg_ids:
            try:
                await context.bot.send_message(tg, text, parse_mode="HTML")
            except Exception:
                pass  # بلاک یا ریستارت — مهم نیس


async def top_teams_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """🏆 لیدربرد تیم‌ها — امتیاز کلی + رقابت این هفته + قهرمانای هفته پیش («تیم لیدربرد»)"""
    async with session_scope() as s:
        winners = await teams.maybe_weekly_rollover(s)
        tops = await teams.top_teams_by_points(s, config.RANK_LIMIT)
        week_tops = await teams.top_teams_week(s, config.RANK_LIMIT)
        last_week = await teams.meta_get(s, "last_week_result")
        await s.commit()

    if winners:
        await _announce_winners(context, winners)

    if not tops:
        text = (
            "<b>🏆 لیدربرد تیم‌ها</b>\n\n"
            "هنوز هیچ تیمی ساخته نشده\n"
            "اولیشو تو بساز 😎 «ساخت تیم»"
        )
        return await respond(update, text, kb.team_back_kb())

    medals_row = []
    lines = ["<b>🏆 لیدربرد تیم‌ها</b>", ""]
    lines.append("━━━━ 🎯 بر اساس امتیاز ━━━━")
    for i, (t, n) in enumerate(tops, 1):
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{fa_num(i)}.")
        lines.append(f"{medal} «{esc(t.name)}» | 💎 {fa_num(t.points)} | 👥 {fa_num(n)}")

    lines.append("")
    lines.append("━━━━ 📅 رقابت این هفته ━━━━")
    for i, (t, n) in enumerate(week_tops[:5], 1):
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f"{fa_num(i)}.")
        lines.append(f"{medal} «{esc(t.name)}» | 💎 {fa_num(t.week_points)}")
    p1, p2, p3 = (config.TEAM_WEEKLY_PRIZES.get(i, 0) for i in (1, 2, 3))
    lines.append(
        f"🏁 آخر هفته: 🥇 {money_tp(p1)} | 🥈 {money_tp(p2)} | 🥉 {money_tp(p3)} — به بانک تیم"
    )

    if last_week:
        lines.append("")
        lines.append("━━━━ 👑 قهرمانای هفته پیش ━━━━")
        lines.append(esc(last_week))

    lines.append("")
    lines.append("💎 امتیاز با برد تو حمله و برداشت محصول جمع میشه")
    lines.append("💡 آمار هر تیم با «تیم [اسم]» — مثلا «تیم فوتبالیست‌ها»")
    text = "\n".join(lines)
    await respond(update, text, kb.team_back_kb())


# ───────── ساخت تیم ─────────

async def create_team_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        ok, alert = await teams.can_create_team(s, user)
        if ok:
            if user.pending_action:
                ok, alert = False, "⏳ اول کار قبلیتو تموم کن یا «لغو» بزن"
            else:
                user.pending_action = "teamname"
                user.pending_value = ""
        await s.commit()

    if not ok:
        return await respond(update, alert)

    await respond(
        update,
        "<b>🏴 اسم تیمت رو بفرست</b>\n\n"
        f"💸 ساخت تیم {money(config.TEAM_CREATE_COST)} هزینه داره\n"
        "هر اسمی دوست داری همینجا بنویس و بفرست — مثلا «فوتبالیست‌ها»\n\n"
        "❌ پشیمون شدی بنویس «لغو»",
    )


# ───────── جوین تیم ─────────

async def join_team_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    txt = (update.message.text or "").strip()
    # «جوین تیم فوتبالیست‌ها» — اسم میتونه چندکلمه‌ای باشه
    m = re.match(r"^جوین[\s‌]+تیم[\s‌]+(.+)$", txt)
    arg = m.group(1) if m else ""

    if not arg:
        return await respond(update, "🤷 این‌جوری بنویس: «جوین تیم [اسم تیم]»")

    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        ok, res = await teams.join_team(s, user, arg)
        await s.commit()

    if ok:
        text = (
            f"<b>🏴 خوش اومدی به تیم «{esc(res)}»</b>\n\n"
            "📜 کوئست‌های روزانه با «کوئست»\n"
            "⛏ کنده‌کاری تیمی با «کنده کاری تیمی»\n"
            "📊 آمار تیم با «تیم من»"
        )
        return await respond(update, text, kb.team_kb(is_owner=False))
    await respond(update, res)


# ───────── ترک / انحلال ─────────

async def leave_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        membership = await teams.get_membership(s, user.id)
        t = await teams.get_team_of(s, user.id)
        name = t.name if t else None
        role = membership.role if membership else None
        await s.commit()

    if not membership:
        return await respond(update, "🏴 اصلا تو تیمی نیستی که", alert="🏴 تو تیمی نیستی" if update.callback_query else None)
    if role == "owner":
        return await respond(
            update,
            "<b>👑 تو رهبر تیمی</b>\n\nنمی‌تونی بری — باید تیم رو منحل کنی\nاگه تصمیمت قطعیه «انحلال تیم» رو بزن",
        )

    text = (
        f"<b>🚪 ترک تیم «{esc(name)}»</b>\n\n"
        "مطمئنی می‌خوای بری؟"
    )
    await respond(update, text, kb.team_confirm_kb("leave", update.effective_user.id))


async def disband_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        membership = await teams.get_membership(s, user.id)
        t = await teams.get_team_of(s, user.id)
        name = t.name if t else None
        bank = t.bank if t else 0
        role = membership.role if membership else None
        await s.commit()

    if role != "owner":
        return await respond(update, "👑 فقط رهبر می‌تونه تیم رو منحل کنه")

    text = (
        f"<b>💥 انحلال تیم «{esc(name)}»</b>\n\n"
        f"🏦 خزانه {money(bank)} می‌سوزه\n"
        "📊 آمار و کوئست‌ها پاک میشه\n"
        "👥 همه اعضا سرباز میشن\n\n"
        "مطمئنی؟ برگشتی نداره"
    )
    await respond(update, text, kb.team_confirm_kb("disband", update.effective_user.id))


async def team_confirm_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """اجرای ترک/انحلال — فقط صاحب دستور"""
    _, action, owner_tg = parts(update)

    if update.effective_user.id != int(owner_tg):
        await update.callback_query.answer("این تصمیم مال تو نیس 😅", show_alert=True)
        return

    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        if action == "leave":
            ok, res = await teams.leave_team(s, user)
            msg = f"🚪 از تیم «{res}» رفتی برو بیرون 😅" if ok else res
        else:
            ok, res = await teams.disband_team(s, user)
            msg = f"💥 تیم «{res}» منحل شد — همه آزادن" if ok else res
        await s.commit()

    if not ok:
        return await respond(update, msg)

    await respond(update, f"<b>{esc(msg)}</b>", kb.home_kb())


# ───────── بیوی تیم ─────────

async def set_bio_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    txt = (update.message.text or "").strip()
    m = re.match(r"^(?:ست[\s‌]+)?بیو[\s‌]+تیم[\s‌]+(.+)$", txt)
    arg = m.group(1) if m else ""

    if not arg:
        return await respond(update, "✏️ این‌جوری بنویس: «ست بیو تیم [متن]»")

    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        ok, res = await teams.set_bio(s, user, arg)
        await s.commit()

    if ok:
        return await respond(update, f"✏️ بیوی تیم ست شد:\n<i>{esc(res)}</i>\n\nتو آمار تیم با «تیم من» نمایش داده میشه")
    await respond(update, res)


# ───────── کوئست ─────────

async def quests_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        team = await teams.get_team_of(s, user.id)
        if not team:
            await s.commit()
            return await respond(
                update,
                "<b>📜 کوئست‌های گروهی</b>\n\n"
                "کوئست‌ها مال تیم‌ان — اول عضو یه تیم شو\n"
                f"«جوین تیم [اسم]» (لول {fa_num(config.TEAM_JOIN_MIN_LEVEL)}+) یا «ساخت تیم» (لول {fa_num(config.TEAM_CREATE_MIN_LEVEL)}+)",
            )

        daily = await teams._daily(s, team.id)
        text = _quests_text(team.name, daily)
        await s.commit()

    await respond(update, text, kb.team_back_kb())


# ───────── کنده‌کاری تیمی ─────────

async def _push_mine_state(update: Update, context: ContextTypes.DEFAULT_TYPE, res: dict) -> None:
    """نمایش وضعیت کنده‌کاری — تکست جدید می‌فرسته یا پیام قدیمی رو ادیت می‌کنه"""
    status = res["status"]

    if status == "no_team":
        return await respond(update, "🏴 کنده‌کاری تیمی مال تیم‌ست — اول عضو یه تیم شو 😅")
    if status == "too_few":
        return await respond(update, "⛏ کنده‌کاری تیمی حداقل 3 نفره می‌خواد — اول تیمتو بزرگ کن 😅")
    if status == "cooldown":
        return await respond(update, f"⏳ کنده‌کاری تیمی هر {fa_num(config.TEAM_MINE_COOLDOWN_MINUTES)} دقیقه یه باره — {fa_dur(res['left'])} مونده")

    if status == "completed":
        return await respond(update, _mine_complete_text(res), kb.team_back_kb())

    text = _mine_progress_text(res)
    if res.get("restart"):
        text = "⏰ دفعه قبل به " + fa_num(int(config.TEAM_MINE_JOIN_PCT * 100)) + "٪ نرسید — پایین دوباره استارتش کردیم 👇\n\n" + text

    if update.callback_query:
        return await respond(update, text, kb.team_mine_kb())

    # متنی: اگه پیام نمایش قبلی هست ادیتش کن وگرنه جدید بفرست و بایند کن
    team = res["team"]
    sess = teams.TEAM_MINE_SESSIONS.get(team.id)
    if res["status"] == "started" or not sess or not sess.get("message_id"):
        msg = await update.message.reply_html(text, reply_markup=kb.team_mine_kb())
        teams.bind_mine_message(team.id, msg.chat_id, msg.message_id)
        return

    # پیوستن توسط نفر بعدی — پیام قبلی رو ادیت کن + به خودش جواب کوتاه بده
    try:
        await context.bot.edit_message_text(
            chat_id=sess["chat_id"], message_id=sess["message_id"],
            text=text, parse_mode="HTML",
            reply_markup=strip_home(update, kb.team_mine_kb()),
        )
    except BadRequest:
        # پیام قبلی دیگه نیس — همینجا تازه بفرست و بایند کن
        msg = await update.message.reply_html(text)
        teams.bind_mine_message(team.id, msg.chat_id, msg.message_id)
        return

    joined, needed, m_count = res["joined"], res["needed"], res["member_count"]
    remaining = max(0, needed - joined)
    ack = f"✔ پیوستی — {fa_num(joined)} نفر از {fa_num(m_count)} نفره"
    if remaining:
        ack += f" | {fa_num(remaining)} نفر تا تکمیل"
    await update.message.reply_html(ack)


async def team_mine_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        res = await teams.team_mine_join(s, user)
        await s.commit()
    await _push_mine_state(update, context, res)


# ───────── ساختمان‌های تیم («تیم ساختمان» / «تیم ساخت» + دکمه) ─────────

def _buildings_text(team) -> str:
    def _line(kind_emoji: str, title: str, level: int, per_level: float) -> list[str]:
        pct_now = int(per_level * level * 100)
        out = [f"{kind_emoji} <b>{title}</b> — لول {fa_num(level)}"]
        out.append(f"قدرت فعلی: +{fa_num(pct_now)}٪ برای همه اعضا")
        if level >= config.TEAM_BUILDING_MAX_LEVEL:
            out.append("⭐ مکس لوله")
        else:
            cost = teams.building_cost(level + 1)
            pct_next = int(per_level * (level + 1) * 100)
            out.append(f"⬆️ لول {fa_num(level + 1)} (+{fa_num(pct_next)}٪) — هزینه {money(cost)}")
        return out

    lines = [f"<b>🏗 ساختمان‌های تیم «{esc(team.name)}»</b>", ""]
    lines += _line("⚔️", "ساختمان حمله", team.atk_bld or 0, config.TEAM_ATK_BONUS_PER_LEVEL)
    lines.append("")
    lines += _line("🛡", "ساختمان دفاع", team.def_bld or 0, config.TEAM_DEF_BONUS_PER_LEVEL)
    lines.append("")
    lines.append(f"🏦 بانک تیم: {money(team.bank)}")
    lines.append("")
    lines.append("👑 ارتقا فقط با رهبره — دستورش: «تیم ارتقا حمله» / «تیم ارتقا دفاع»")
    lines.append("💰 کمک مالی اعضا: «تیم واریز 1200»")
    return "\n".join(lines)


async def render_buildings(update: Update, alert: str | None = None, extra: str | None = None) -> None:
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        membership = await teams.get_membership(s, user.id)
        team = await teams.get_team_of(s, user.id)
        if not membership or not team:
            await s.commit()
            return await respond(update, _no_team_text(), kb.team_no_kb(), alert=alert)
        text = _buildings_text(team)
        if extra:
            text += f"\n\n{extra}"
        markup = kb.team_bld_kb(team, membership.role == "owner", user.telegram_id)
        await s.commit()
    await respond(update, text, markup, alert=alert)


async def buildings_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await render_buildings(update)


async def buildings_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await render_buildings(update)


# ───────── لیست اعضا («تیم عضویت») ─────────

async def roster_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        team = await teams.get_team_of(s, user.id)
        if not team:
            await s.commit()
            return await respond(update, _no_team_text(), kb.team_no_kb())
        data = await teams.team_stats_data(s, team)
        await s.commit()

    lines = [f"<b>👥 اعضای تیم «{esc(team.name)}» — {fa_num(data['count'])} نفر</b>", ""]
    by_id = {u.id: u for u in data["users"]}
    for m in data["members"]:
        u = by_id.get(m.user_id)
        if not u:
            continue
        tag = "👑" if m.role == "owner" else "🔸"
        name = esc(u.first_name or u.username or "؟")
        lines.append(f"{tag} {name} | لول {fa_num(u.level)} | ⚔️ {fa_num(u.wins)} برد")
    lines.append("")
    lines.append("آمار کامل تیم با «تیم پروفایل»")
    await respond(update, "\n".join(lines), kb.team_back_kb())


# ───────── بانک تیم («تیم بانک») ─────────

async def team_bank_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        team = await teams.get_team_of(s, user.id)
        if not team:
            await s.commit()
            return await respond(update, _no_team_text(), kb.team_no_kb())
        bank = team.bank
        name = team.name
        await s.commit()

    text = (
        f"<b>🏦 بانک تیم «{esc(name)}»</b>\n\n"
        f"💰 موجودی: {money(bank)}\n\n"
        "پول بانک از کجا میاد:\n"
        "⛏ کنده‌کاری تیمی | 🏆 جایزه هفتگی رقابت‌ها | 💰 واریز اعضا\n\n"
        "کجا خرج میشه:\n"
        "🏗 ارتقای ساختمان حمله و دفاع توسط رهبر\n\n"
        "💰 کمک مالی: «تیم واریز 1200»"
    )
    await respond(update, text, kb.team_bank_kb())


# ───────── واریز به بانک تیم («تیم واریز 1200») ─────────

async def team_deposit_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    txt = (update.message.text or "").strip()
    m = re.match(r"^تیم[\s‌]+واریز[\s‌]+(.+)$", txt)
    amount = parse_amount(m.group(1)) if m else None
    if amount is None:
        return await respond(update, "❌ مبلغو درست بگو — مثلا «تیم واریز 1200»")

    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        ok, msg = await teams.team_deposit(s, user, amount)
        team = await teams.get_team_of(s, user.id)
        bank = team.bank if team else 0
        await s.commit()

    if not ok:
        return await respond(update, msg)
    await respond(update, f"<b>{esc(msg)}</b>\n\n🏦 موجودی بانک تیم {money(bank)}")


# ───────── ارتقای ساختمان («تیم ارتقا حمله/دفاع» + دکمه‌ها) ─────────

async def _building_confirm_payload(update: Update, kind: str) -> tuple[str, object] | None:
    """متن صفحه تایید ارتقا + کیبورد — یا پیام خطا"""
    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        membership = await teams.get_membership(s, user.id)
        team = await teams.get_team_of(s, user.id)
        tg = user.telegram_id
        details = (membership, team)
        await s.commit()

    membership, team = details
    if not membership or not team:
        await respond(update, _no_team_text(), kb.team_no_kb())
        return None
    if membership.role != "owner":
        await respond(update, "👑 ارتقای ساختمان فقط با رهبر تیمه")
        return None

    title = "⚔️ ساختمان حمله" if kind == "atk" else "🛡 ساختمان دفاع"
    level = team.atk_bld if kind == "atk" else team.def_bld
    per = config.TEAM_ATK_BONUS_PER_LEVEL if kind == "atk" else config.TEAM_DEF_BONUS_PER_LEVEL
    if level >= config.TEAM_BUILDING_MAX_LEVEL:
        await respond(update, f"⭐ {title} مکس لوله")
        return None

    cost = teams.building_cost(level + 1)
    pct_next = int(per * (level + 1) * 100)
    effect = "قدرت حمله" if kind == "atk" else "دفاع"
    text = (
        f"<b>🏗 ارتقای {title} — لول {fa_num(level)} ← {fa_num(level + 1)}</b>\n\n"
        f"💸 هزینه {money(cost)} از بانک تیم\n"
        f"📈 {effect} همه اعضا +{fa_num(pct_next)}٪ میشه\n"
        f"🏦 موجودی بانک تیم {money(team.bank)}\n\n"
        "انجامش بدیم؟"
    )
    return text, kb.team_bld_confirm_kb(kind, tg)


async def team_upgrade_text(update: Update, context: ContextTypes.DEFAULT_TYPE, kind: str | None = None) -> None:
    """«تیم ارتقا حمله» / «تیم ارتقا دفاع» — صفحه تایید"""
    if kind is None:
        kind = "atk" if "حمله" in (update.message.text or "") else "def"
    payload = await _building_confirm_payload(update, kind)
    if payload:
        await respond(update, payload[0], payload[1])


async def team_upgrade_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دکمه ارتقا از صفحه ساختمان‌ها (tbup) — فقط خود رهبر"""
    _, kind, owner_tg = parts(update)
    if update.effective_user.id != int(owner_tg):
        await update.callback_query.answer("این کار مال رهبره 😅", show_alert=True)
        return
    payload = await _building_confirm_payload(update, kind)
    if payload:
        await respond(update, payload[0], payload[1])


async def team_upgrade_execute(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """اجرای ارتقا بعد از تایید (tbcf) — فقط خود رهبر"""
    _, kind, owner_tg = parts(update)
    if update.effective_user.id != int(owner_tg):
        await update.callback_query.answer("این کار مال رهبره 😅", show_alert=True)
        return

    async with session_scope() as s:
        user, _ = await users.get_or_create(s, update.effective_user)
        ok, msg = await teams.upgrade_building(s, user, kind)
        await s.commit()

    if ok:
        return await render_buildings(update, alert="🏗 ساختمان ارتقا پیدا کرد", extra=msg)
    await render_buildings(update, alert=msg)


async def team_profile_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """«تیم پروفایل» — همون آمار کامل تیم خودم با لول ساختمان‌ها و قدرتشون"""
    await render_my_team(update)
