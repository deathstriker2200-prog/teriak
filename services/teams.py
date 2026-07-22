"""
منطق تیم: ساخت | عضویت | ترک | آمار و بیو | کوئست روزانه گروهی | کنده‌کاری تیمی (استخراج)
امتیاز تیمی با برد حمله و برداشت جمع میشه | رقابت هفتگی با جایزه به ۳ تیم اول
ساختمان حمله و دفاع تیم رو رهبر با بانک تیم آپگرید می‌کنه و بونسش به همه اعضاست
کنده‌کاری تیمی: حداقل ۳ عضو | ۷۰٪ اعضا باید دستورشو بزنن تا پول بره تو خزانه تیم
"""

import math
import random
from datetime import timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

import config
from models import GameMeta, Team, TeamDaily, TeamMember, User
from utils import fa_num, money, normalize_fa, now_utc

# ───────── سشن‌های کنده‌کاری تیمی (درون حافظه — با ری‌استارت پاک میشن) ─────────
# team_id → {chat_id, message_id, members(set of user_id), needed, member_count, expires_at}
TEAM_MINE_SESSIONS: dict[int, dict] = {}


def _today() -> str:
    return now_utc().date().isoformat()


def team_name_norm(name: str) -> str:
    return normalize_fa(name)


# ───────── کوئری پایه ─────────

async def get_team_by_name(session: AsyncSession, name: str) -> Team | None:
    q = select(Team).where(Team.name_norm == team_name_norm(name))
    return (await session.execute(q)).scalar_one_or_none()


async def get_membership(session: AsyncSession, user_id: int) -> TeamMember | None:
    q = select(TeamMember).where(TeamMember.user_id == user_id)
    return (await session.execute(q)).scalar_one_or_none()


async def get_team_of(session: AsyncSession, user_id: int) -> Team | None:
    m = await get_membership(session, user_id)
    if not m:
        return None
    # lazy-load تو async ممنوعه — مستقیم می‌گیریم
    return await session.get(Team, m.team_id)


async def get_members(session: AsyncSession, team_id: int) -> list[TeamMember]:
    q = select(TeamMember).where(TeamMember.team_id == team_id).order_by(TeamMember.role, TeamMember.id)
    return list((await session.execute(q)).scalars())


async def member_count(session: AsyncSession, team_id: int) -> int:
    q = select(func.count(TeamMember.id)).where(TeamMember.team_id == team_id)
    return (await session.execute(q)).scalar_one()


# ───────── ساخت و عضویت و ترک ─────────

async def can_create_team(session: AsyncSession, user: User) -> tuple[bool, str]:
    """چک‌های قبل از پرسیدن اسم تیم"""
    if user.level < config.TEAM_CREATE_MIN_LEVEL:
        return False, f"🔒 ساخت تیم لول {fa_num(config.TEAM_CREATE_MIN_LEVEL)} می‌خواد رفیق"
    if await get_membership(session, user.id):
        return False, "🏴 عزیز خودت تو یه تیمی نمی‌تونی توی تیم دیگری عضو بشی — اول «ترک تیم» رو بزن"
    if user.cash < config.TEAM_CREATE_COST:
        return False, f"❌ ساخت تیم {money(config.TEAM_CREATE_COST)} هزینه داره و پولت کمه"
    return True, ""


def validate_team_name(name: str) -> tuple[bool, str, str]:
    """ولیدیشن اسم تیم — خروجی: (اوکی, اسم تمیز, دلیل رد)"""
    clean = normalize_fa(name)
    if not clean or len(clean) < 2:
        return False, clean, "❌ اسم تیم خیلی کوتاهه"
    if len(clean) > config.TEAM_NAME_MAX:
        return False, clean, f"❌ اسم تیم حداکثر {fa_num(config.TEAM_NAME_MAX)} حرف می‌تونه باشه"
    if ":" in clean or "<" in clean or ">" in clean:
        return False, clean, "❌ تو اسم تیم کاراکتر عجیب نذار"
    return True, clean, ""


async def create_team(session: AsyncSession, user: User, name: str) -> tuple[bool, str]:
    """ساخت تیم با اسم انتخابی — هزینه همونجا کم میشه"""
    ok, alert = await can_create_team(session, user)
    if not ok:
        return False, alert

    ok_name, clean, why = validate_team_name(name)
    if not ok_name:
        return False, why

    if await get_team_by_name(session, clean):
        return False, f"🏴 تیمی با اسم «{clean}» از قبل هست — یه اسم دیگه بردار"

    # اسم نمایشی همون چیزی میمونه که کاربر تایپ کرد (با نیم‌فاصله) — نسخه نرمال فقط برای یکتایی
    display = " ".join(str(name).split())
    user.cash -= config.TEAM_CREATE_COST
    team = Team(name=display, name_norm=team_name_norm(display), owner_id=user.id)
    session.add(team)
    await session.flush()
    session.add(TeamMember(team_id=team.id, user_id=user.id, role="owner"))
    return True, display


async def join_team(session: AsyncSession, user: User, name: str) -> tuple[bool, str]:
    if user.level < config.TEAM_JOIN_MIN_LEVEL:
        return False, f"🔒 عضویت تو تیم لول {fa_num(config.TEAM_JOIN_MIN_LEVEL)} می‌خواد"
    if await get_membership(session, user.id):
        return False, "🏴 عزیز خودت تو یه تیمی نمی‌تونی توی تیم دیگری عضو بشی — اول «ترک تیم» رو بزن"

    team = await get_team_by_name(session, name)
    if not team:
        return False, f"🤷 تیمی با اسم «{normalize_fa(name)}» پیدا نشد"

    count = await member_count(session, team.id)
    if count >= config.TEAM_MAX_MEMBERS:
        return False, f"🏴 تیم «{team.name}» پره"

    session.add(TeamMember(team_id=team.id, user_id=user.id, role="member"))
    return True, team.name


async def leave_team(session: AsyncSession, user: User) -> tuple[bool, str]:
    """عضو عادی خارج میشه — رهبر نمی‌تونه بره مگر تیم رو منحل کنه"""
    m = await get_membership(session, user.id)
    if not m:
        return False, "🏴 اصلا تو تیمی نیستی که"
    if m.role == "owner":
        return False, "👑 تو رهبری — یا تیم رو با «انحلال تیم» منحل کن یا اول جانشین بذار ندارم 😅"
    team = await session.get(Team, m.team_id)
    name = team.name if team else "؟"
    await session.delete(m)
    return True, name


async def disband_team(session: AsyncSession, user: User) -> tuple[bool, str]:
    """انحلال توسط رهبر — خزانه و آمار نابود میشه"""
    m = await get_membership(session, user.id)
    if not m or m.role != "owner":
        return False, "👑 فقط رهبر می‌تونه تیم رو منحل کنه"
    team = await session.get(Team, m.team_id)
    if not team:
        return False, "🤷 تیمی نیس که"
    name = team.name
    TEAM_MINE_SESSIONS.pop(team.id, None)
    await session.delete(team)  # memberها با cascade پاک میشن
    return True, name


async def set_bio(session: AsyncSession, user: User, bio: str) -> tuple[bool, str]:
    """ست کردن پروفایل/بیو تیم — فقط رهبر — تو آمار تیم نمایش داده میشه"""
    m = await get_membership(session, user.id)
    if not m or m.role != "owner":
        return False, "👑 فقط رهبر می‌تونه بیوی تیم رو عوض کنه"
    clean = normalize_fa(bio)
    if not clean:
        return False, "❌ بیو خالی که نمیشه"
    display = " ".join(str(bio).split())
    if len(display) > config.TEAM_BIO_MAX:
        return False, f"❌ بیو حداکثر {fa_num(config.TEAM_BIO_MAX)} حرف"
    team = await session.get(Team, m.team_id)
    if not team:
        return False, "🤷 تیمی نیس که"
    team.bio = display
    return True, display


# ───────── آمار تیم ─────────

async def team_stats_data(session: AsyncSession, team: Team) -> dict:
    """دیتای آمار تیم برای نمایش"""
    members = await get_members(session, team.id)
    users: list[User] = []
    for m in members:
        u = await session.get(User, m.user_id)
        if u:
            users.append(u)

    daily = await _daily(session, team.id)
    owner_name = "؟"
    for m in members:
        if m.role == "owner":
            for u in users:
                if u.id == m.user_id:
                    owner_name = u.first_name or u.username or "؟"
            break

    return {
        "team": team,
        "members": members,
        "users": users,
        "count": len(members),
        "owner_name": owner_name,
        "wins": sum(u.wins for u in users),
        "losses": sum(u.losses for u in users),
        "level_sum": sum(u.level for u in users),
        "daily": daily,
    }


async def top_teams(session: AsyncSession, limit: int = 10) -> list[tuple[Team, int]]:
    """برترین تیم‌ها بر اساس خزانه"""
    q = select(Team).order_by(Team.bank.desc(), Team.total_kills.desc()).limit(limit)
    teams = list((await session.execute(q)).scalars())
    return [(t, await member_count(session, t.id)) for t in teams]


# ───────── کوئست روزانه ─────────

async def _daily(session: AsyncSession, team_id: int) -> TeamDaily:
    """ردیف امروز تیم رو بگیر — اگه نبود بساز"""
    day = _today()
    q = select(TeamDaily).where(TeamDaily.team_id == team_id, TeamDaily.day == day)
    row = (await session.execute(q)).scalar_one_or_none()
    if not row:
        row = TeamDaily(team_id=team_id, day=day)
        session.add(row)
        await session.flush()
    return row


def _quest_progress(daily: TeamDaily, key: str) -> tuple[int, bool]:
    if key == "kills":
        return daily.kills, bool(daily.kills_done)
    return daily.harvests, bool(daily.harvests_done)


async def _record(session: AsyncSession, user: User, key: str, n: int) -> str | None:
    """
    ثبت پیشرفت کوئست + امتیاز تیم — اگه سقف پر شد جایزه به همه اعضا میرسه
    خروجی: متن اعلان تکمیل کوئست یا None
    """
    await maybe_weekly_rollover(session)  # اول هفته جدید چک بشه

    team = await get_team_of(session, user.id)
    if not team:
        return None

    daily = await _daily(session, team.id)

    if key == "kills":
        daily.kills += n
        team.total_kills += n
        team.points += config.TEAM_POINT_KILL * n
        team.week_points += config.TEAM_POINT_KILL * n
    else:
        daily.harvests += n
        team.total_harvests += n
        team.points += config.TEAM_POINT_HARVEST * n
        team.week_points += config.TEAM_POINT_HARVEST * n

    for quest in config.TEAM_QUESTS:
        if quest["key"] != key:
            continue
        progress, done = _quest_progress(daily, key)
        if progress >= quest["target"] and not done:
            if key == "kills":
                daily.kills_done = 1
            else:
                daily.harvests_done = 1

            members = await get_members(session, team.id)
            for m in members:
                u = await session.get(User, m.user_id)
                if u:
                    u.cash += quest["reward"]

            return (
                f"🏴 کوئست {quest['emoji']} «{quest['title']}» تیم «{team.name}» کامل شد!\n"
                f"🎁 {money(quest['reward'])} به هر عضو تیم رسید"
            )
    return None


async def record_kill(session: AsyncSession, user: User) -> str | None:
    """هر برد تو حمله — با قلاب execute_attack صدا زده میشه"""
    return await _record(session, user, "kills", 1)


async def record_harvest(session: AsyncSession, user: User, n: int) -> str | None:
    """هر محصول برداشت‌شده — با قلاب harvest_all صدا زده میشه"""
    return await _record(session, user, "harvest", n)


def quests_view(daily: TeamDaily) -> list[dict]:
    """نمایش کوئست‌ها با پیشرفت — برای متن استعلام"""
    out = []
    for q in config.TEAM_QUESTS:
        progress, done = _quest_progress(daily, q["key"])
        out.append({**q, "progress": min(progress, q["target"]), "done": done})
    return out


# ───────── کنده‌کاری تیمی (استخراج) ─────────

def mine_needed(member_n: int) -> int:
    """تعداد نفرات لازم — سقف ۷۰٪ اعضا و حداقل ۳ نفر (تیم زیر ۳ نفره نمی‌تونه استخراج کنه)"""
    return max(3, math.ceil(config.TEAM_MINE_JOIN_PCT * member_n))


async def team_mine_join(session: AsyncSession, user: User) -> dict:
    """
    پیوستن/استارت کنده‌کاری تیمی با دستور متنی
    خروجی: دیکشنری وضعیت برای هندلر — status:
      no_team | cooldown | started | joined | already | completed | failed_expired_* (+ restart)
    """
    await maybe_weekly_rollover(session)

    team = await get_team_of(session, user.id)
    if not team:
        return {"status": "no_team"}

    m_count = await member_count(session, team.id)
    if m_count < 3:
        return {"status": "too_few", "team": team, "member_count": m_count}
    needed = mine_needed(m_count)
    now = now_utc()

    # پاکسازی سشن منقضی
    sess = TEAM_MINE_SESSIONS.get(team.id)
    expired_restart = False
    if sess and sess["expires_at"] < now:
        expired_restart = True
        TEAM_MINE_SESSIONS.pop(team.id, None)
        sess = None

    if not sess:
        # کولدون بعد از آخرین کنده‌کاری موفق
        if team.last_team_mine_at:
            cd = timedelta(minutes=config.TEAM_MINE_COOLDOWN_MINUTES)
            if now - team.last_team_mine_at < cd:
                left = int((cd - (now - team.last_team_mine_at)).total_seconds())
                return {"status": "cooldown", "left": left, "team": team}

        sess = {
            "members": set(),
            "needed": needed,
            "member_count": m_count,
            "expires_at": now + timedelta(seconds=config.TEAM_MINE_WINDOW_SECONDS),
            "chat_id": None,
            "message_id": None,
        }
        TEAM_MINE_SESSIONS[team.id] = sess

    if user.id in sess["members"]:
        return {
            "status": "already", "team": team,
            "joined": len(sess["members"]), "needed": sess["needed"],
            "member_count": sess["member_count"],
        }

    sess["members"].add(user.id)
    joined = len(sess["members"])
    result = {
        "team": team,
        "joined": joined,
        "needed": sess["needed"],
        "member_count": sess["member_count"],
        "expires_at": sess["expires_at"],
        "restart": expired_restart,
        "status": "started" if joined == 1 else "joined",
    }

    if joined >= sess["needed"]:
        # تکمیل — پول میره تو خزانه
        per = [random.randint(config.TEAM_MINE_PER_MIN, config.TEAM_MINE_PER_MAX) for _ in sess["members"]]
        total = sum(per)
        team.bank += total
        team.last_team_mine_at = now
        TEAM_MINE_SESSIONS.pop(team.id, None)
        result.update(status="completed", reward=total, bank=team.bank)

    return result


def bind_mine_message(team_id: int, chat_id: int, message_id: int) -> None:
    """آی‌دی پیام نمایش کنده‌کاری رو نگه می‌داریم که با هر پیوستن ادیتش کنیم"""
    sess = TEAM_MINE_SESSIONS.get(team_id)
    if sess:
        sess["chat_id"] = chat_id
        sess["message_id"] = message_id


# ───────── امتیاز تیم و رقابت هفتگی 🏆 ─────────

def current_week_key() -> str:
    """کلید هفته جاری (ISO) — مثل 2026-W30"""
    iso = now_utc().isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


async def meta_get(session: AsyncSession, key: str) -> str | None:
    row = await session.get(GameMeta, key)
    return row.value if row else None


async def meta_set(session: AsyncSession, key: str, value: str) -> None:
    row = await session.get(GameMeta, key)
    if row:
        row.value = value
    else:
        session.add(GameMeta(key=key, value=value))


async def top_teams_by_points(session: AsyncSession, limit: int = 10) -> list[tuple[Team, int]]:
    """لیدربرد کلی — بر اساس امتیاز تیم"""
    q = select(Team).order_by(Team.points.desc(), Team.total_kills.desc()).limit(limit)
    teams_ = list((await session.execute(q)).scalars())
    return [(t, await member_count(session, t.id)) for t in teams_]


async def top_teams_week(session: AsyncSession, limit: int = 10) -> list[tuple[Team, int]]:
    """رقابت این هفته — بر اساس امتیاز هفته"""
    q = select(Team).order_by(Team.week_points.desc(), Team.points.desc()).limit(limit)
    teams_ = list((await session.execute(q)).scalars())
    return [(t, await member_count(session, t.id)) for t in teams_]


async def member_telegram_ids(session: AsyncSession, team_id: int) -> list[int]:
    """تلگرام‌آی‌دی اعضا — برای اطلاع‌رسانی جایزه هفتگی"""
    q = select(TeamMember.user_id).where(TeamMember.team_id == team_id)
    ids = list((await session.execute(q)).scalars())
    out: list[int] = []
    for uid in ids:
        u = await session.get(User, uid)
        if u:
            out.append(u.telegram_id)
    return out


async def maybe_weekly_rollover(session: AsyncSession) -> list[dict] | None:
    """
    رول‌اور رقابت هفتگی — اگه هفته (ISO) عوض شده باشه:
    به ۳ تیم اول امتیاز هفته جایزه میرسه (به بانک تیم) و امتیاز هفته همه ریست میشه
    خروجی: لیست برنده‌ها [{team, rank, prize, points}] یا None اگه هفته عوض نشده
    نتیجه هفته قبل هم تو game_meta ذخیره میشه تا تو «تیم لیدربرد» نمایش داده بشه
    """
    wk = current_week_key()
    last = await meta_get(session, "week_key")
    if last == wk:
        return None

    q = (
        select(Team)
        .where(Team.week_points > 0)
        .order_by(Team.week_points.desc(), Team.points.desc())
        .limit(3)
    )
    winners = list((await session.execute(q)).scalars())

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    out: list[dict] = []
    summary: list[str] = []
    for i, t in enumerate(winners, 1):
        prize = config.TEAM_WEEKLY_PRIZES.get(i, 0)
        t.bank += prize
        rec = {"team": t, "rank": i, "prize": prize, "points": t.week_points}
        out.append(rec)
        summary.append(
            f"{medals[i]} «{t.name}» با {fa_num(t.week_points)} امتیاز — {money(prize)} به بانک تیم"
        )

    await session.execute(update(Team).values(week_points=0))
    await meta_set(session, "week_key", wk)
    # فقط وقتی برنده‌ای داشتیم نتیجه رو به‌روز کن — نتیجه خالی قهرمانای قبلی رو نپوشونه
    if summary:
        await meta_set(session, "last_week_result", "\n".join(summary))
    await session.flush()
    return out


# ───────── ساختمان‌های تیم 🏗 ─────────

def building_cost(level: int) -> int:
    """هزینه ارتقا به لول level (لول ۱ = هزینه پایه)"""
    return int(config.TEAM_BUILDING_BASE_COST * (config.TEAM_BUILDING_COST_GROWTH ** max(0, level - 1)))


def atk_bonus(team: Team | None) -> float:
    """ضریب بونس حمله همه اعضا — مثلا ۰٫۰۹ برای ساختمان لول ۳"""
    if not team:
        return 0.0
    return config.TEAM_ATK_BONUS_PER_LEVEL * (team.atk_bld or 0)


def def_bonus(team: Team | None) -> float:
    """ضریب بونس دفاع همه اعضا"""
    if not team:
        return 0.0
    return config.TEAM_DEF_BONUS_PER_LEVEL * (team.def_bld or 0)


async def upgrade_building(session: AsyncSession, user: User, kind: str) -> tuple[bool, str]:
    """
    ارتقای ساختمان توسط رهبر — پولش از بانک تیم میره
    kind: «atk» ساختمان حمله | «def» ساختمان دفاع
    """
    if kind not in ("atk", "def"):
        return False, "❌ همچین ساختمونی نیس"
    m = await get_membership(session, user.id)
    if not m:
        return False, "🏴 اصلا تو تیمی نیستی که"
    if m.role != "owner":
        return False, "👑 ارتقای ساختمان فقط با رهبر تیمه"

    team = await session.get(Team, m.team_id)
    if not team:
        return False, "🤷 تیمی نیس که"

    title = "⚔️ ساختمان حمله" if kind == "atk" else "🛡 ساختمان دفاع"
    level = team.atk_bld if kind == "atk" else team.def_bld
    if level >= config.TEAM_BUILDING_MAX_LEVEL:
        return False, f"⭐ {title} مکس لوله"

    cost = building_cost(level + 1)
    if team.bank < cost:
        return False, (
            f"❌ ارتقا {money(cost)} می‌خواد ولی بانک تیم {money(team.bank)} ـه\n"
            "اعضا با «تیم واریز 1200» کمک کنن یا کنده‌کاری تیمی بزنین"
        )

    team.bank -= cost
    if kind == "atk":
        team.atk_bld += 1
        bonus_pct = int(config.TEAM_ATK_BONUS_PER_LEVEL * team.atk_bld * 100)
        effect = f"+{fa_num(bonus_pct)}٪ قدرت حمله همه اعضا"
    else:
        team.def_bld += 1
        bonus_pct = int(config.TEAM_DEF_BONUS_PER_LEVEL * team.def_bld * 100)
        effect = f"+{fa_num(bonus_pct)}٪ دفاع همه اعضا"

    new_level = team.atk_bld if kind == "atk" else team.def_bld
    return True, f"🏗 {title} رفت رو لول {fa_num(new_level)} — {effect}"


async def team_deposit(session: AsyncSession, user: User, amount: int) -> tuple[bool, str]:
    """واریز کمک مالی عضو به بانک تیم — «تیم واریز 1200»"""
    if amount <= 0:
        return False, "❌ مبلغو درست بگو — مثلا «تیم واریز 1200»"
    team = await get_team_of(session, user.id)
    if not team:
        return False, "🏴 تو تیمی نیستی که بخوای بهش کمک کنی"
    if user.cash < amount:
        return False, f"❌ این همه پول نقد نداری — جیبت {money(user.cash)} ـه"
    user.cash -= amount
    team.bank += amount
    return True, f"🏦 {money(amount)} به بانک تیم «{team.name}» واریز شد — دستت درد نکنه رفیق 🙏"
