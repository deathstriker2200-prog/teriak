"""
سیستم‌های جهان بازی: آب و هوا 🌦 | بازار سیاه 📈 | جستجو 🔍 | قمارخانه 🎰
یورش پلیس 🚔 | کاروان 🚛 | فعالیت گروه‌ها

همه state ها یا توی game_meta هستن (آب و هوا/بازار — با ری‌استارت می‌مونن)
یا توی حافظه (کاروان — مثل کنده‌کاری تیمی، زودگذره)
"""

import random
from datetime import timedelta

from sqlalchemy import select, update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

import config
from models import GameMeta, GroupActivity, SeedStock, User
from services.farming import get_stock, add_seed_stock
from services.users import add_xp
from utils import fa_dur, fa_num, money, now_utc


# ═════════ فعالیت گروه‌ها ═════════

async def touch_group(session: AsyncSession, chat_id: int) -> None:
    """آپدیت آخرین فعالیت گروه — موجب میشه گروه تو لیست اعلان آب و هوا و کاروان بمونه"""
    row = await session.get(GroupActivity, chat_id)
    if row:
        row.last_active_at = now_utc()
    else:
        session.add(GroupActivity(chat_id=chat_id))


async def active_group_ids(session: AsyncSession, hours: float) -> list[int]:
    """گروه‌های فعال تو x ساعت اخیر"""
    limit = now_utc() - timedelta(hours=hours)
    q = select(GroupActivity.chat_id).where(GroupActivity.last_active_at >= limit)
    return list((await session.execute(q)).scalars())


# ═════════ متا ═════════

async def _meta(session: AsyncSession, key: str) -> str | None:
    row = await session.get(GameMeta, key)
    return row.value if row else None


async def _meta_set(session: AsyncSession, key: str, value: str) -> None:
    row = await session.get(GameMeta, key)
    if row:
        row.value = value
    else:
        session.add(GameMeta(key=key, value=value))


# ═════════ آب و هوا 🌦 ═════════

def weather_of(key: str) -> dict:
    return config.WEATHERS.get(key) or config.WEATHERS["normal"]


def weather_announce_text(key: str) -> str:
    """پیام اعلان آب و هوای جدید برای گروه‌ها"""
    w = weather_of(key)
    lines = ["<b>🌦 وضعیت آب و هوای جدید</b>", ""]
    if key == "normal":
        lines.append(f"{w['emoji']} هوا به حالت عادی برگشت")
        lines.append("محله به روال خودش برگشته")
    else:
        lines.append(f"{w['emoji']} {w['name']} آغاز شد")
        for b in w.get("boosts", []):
            lines.append(f"🌱 {b} — تا 2 ساعت آینده")
    return "\n".join(lines)


async def ensure_weather(session: AsyncSession) -> tuple[str, object | None]:
    """
    آب و هوای فعلی رو بگیر — اگه زمانش گذشته بود همینجا رول کن (تنبل، رول‌بک‌پروف)
    خروجی: (کلید, رکورد جدید اگه همین لحظه رول شده وگرنه None)
    """
    until_raw = await _meta(session, "weather_until")
    cur_key = await _meta(session, "weather_key") or "normal"
    now = now_utc()

    until = None
    if until_raw:
        try:
            from datetime import datetime as _dt
            until = _dt.fromisoformat(until_raw)
        except ValueError:
            until = None

    if cur_key in config.WEATHERS and until and until > now:
        return cur_key, None

    # رول جدید
    if random.random() < config.WEATHER_NORMAL_CHANCE:
        key = "normal"
    else:
        specials = [k for k in config.WEATHERS if k != "normal"]
        key = random.choice(specials)

    new_until = now + timedelta(seconds=config.WEATHER_ROLL_SECONDS)
    await _meta_set(session, "weather_key", key)
    await _meta_set(session, "weather_until", new_until.isoformat())
    return key, {"key": key, "until": new_until}


async def current_weather(session: AsyncSession) -> tuple[str, int]:
    """(کلید آب و هوا, ثانیه مونده) — برای نمایش و افکت‌ها"""
    key, _ = await ensure_weather(session)
    until_raw = await _meta(session, "weather_until")
    from datetime import datetime as _dt
    try:
        left = int((_dt.fromisoformat(until_raw) - now_utc()).total_seconds()) if until_raw else 0
    except ValueError:
        left = 0
    return key, max(0, left)


def weather_grow_speed(key: str) -> float:
    """ضریب سرعت رشد (باران +30٪ | گرمای شدید ۲۰٪− | سرمای شدید +15٪ زمان)"""
    return weather_of(key).get("speed", 1.0)


def weather_sell_mult(key: str) -> float:
    """ضریب قیمت فروش (جشن برداشت +50٪)"""
    return 1.0 + weather_of(key).get("sell_mod", 0.0)


def weather_combat_mods(key: str) -> tuple[float, float]:
    """(اصلاح حمله, اصلاح دفاع) — طوفان −10٪ موفقیت حمله | مه +20٪ دفاع"""
    w = weather_of(key)
    return w.get("atk_mod", 0.0), w.get("def_mod", 0.0)


def weather_q5_bonus(key: str) -> float:
    """شانس اضافه محصول ۵ ستاره (شب مهتابی +10٪)"""
    return weather_of(key).get("q5", 0.0)


async def weather_view(session: AsyncSession) -> dict:
    """دیتای بخش «وضعیت آب و هوا»"""
    key, left = await current_weather(session)
    w = weather_of(key)
    return {"key": key, "w": w, "left": left}


# ═════════ بازار سیاه 📈 ═════════

def _parse_market(raw: str | None) -> dict[str, int]:
    out: dict[str, int] = {}
    if not raw:
        return out
    for chunk in raw.split(","):
        if ":" in chunk:
            k, v = chunk.split(":", 1)
            try:
                out[k] = int(v)
            except ValueError:
                pass
    return out


def normal_seed_keys() -> list[str]:
    """فقط بذرهای معمولی — بذرهای افسانه‌ای تو بازار سیاه نمیان"""
    return [k for k, v in config.SEEDS.items() if not v.get("legendary")]


def market_pct_roll() -> int:
    """
    قرعه درصد تغییر یه محصول — سود/ضرر 50/50
    اغلب‌ها تو بازه کم‌نوسانن (سود 0..20 | ضرر 0..10) و گاهی بازه کامل (تا +50 / تا −30)
    """
    up = random.random() < 0.5
    if random.random() < config.MARKET_COMMON_WEIGHT:
        return random.randint(0, config.MARKET_UP_COMMON) if up else -random.randint(0, config.MARKET_DOWN_COMMON)
    if up:
        return random.randint(config.MARKET_UP_COMMON + 1, config.MARKET_MAX_PCT)
    return -random.randint(config.MARKET_DOWN_COMMON + 1, -config.MARKET_MIN_PCT)


async def ensure_market(session: AsyncSession) -> bool:
    """اگه زمان بازار گذشته بود رول کن — خروجی True یعنی همین لحظه رول شد"""
    until_raw = await _meta(session, "market_until")
    from datetime import datetime as _dt
    try:
        until = _dt.fromisoformat(until_raw) if until_raw else None
    except ValueError:
        until = None

    if until and until > now_utc():
        return False

    parts = []
    for k in normal_seed_keys():
        pct = market_pct_roll()
        parts.append(f"{k}:{pct}")
    await _meta_set(session, "market", ",".join(parts))
    await _meta_set(session, "market_until", (now_utc() + timedelta(seconds=config.MARKET_ROLL_SECONDS)).isoformat())
    return True


async def market_pcts(session: AsyncSession) -> tuple[dict[str, int], int]:
    """(نسبت‌های تغییر برای هر بذر معمولی, ثانیه مونده)"""
    await ensure_market(session)
    pcts = _parse_market(await _meta(session, "market"))
    from datetime import datetime as _dt
    raw = await _meta(session, "market_until")
    try:
        left = int((_dt.fromisoformat(raw) - now_utc()).total_seconds()) if raw else 0
    except ValueError:
        left = 0
    return pcts, max(0, left)


def market_mult(pcts: dict[str, int], seed_key: str) -> float:
    """ضریب قیمت بازار — فقط بذرهای معمولی"""
    if seed_key not in pcts:
        return 1.0
    cfg = config.SEEDS.get(seed_key, {})
    if cfg.get("legendary"):
        return 1.0
    return max(0.1, 1.0 + pcts[seed_key] / 100)


def market_view_text(pcts: dict[str, int], left: int) -> str:
    """متن بخش «وضعیت بازار سیاه» — 🟢 ارزش خرید بالا | 🔴 ارزش خرید نداره"""
    lines = [
        "<b>📈 وضعیت بازار سیاه</b>",
        "",
        "اونایی که با 🔴 علامت گذاری شدن ارزش خرید ندارن چون الان ارزشش توی بازار پایین اومده اما، برعکس اونایی که با 🟢 علامت گذاری شدن ارزش خرید بالایی دارن چون ارزششون توی بازار بالا رفته",
        "درصد کنارشم مقدار افزایش یا کاهش رو نشان می‌ده",
        "",
    ]
    for key in normal_seed_keys():
        sd = config.SEEDS[key]
        pct = pcts.get(key, 0)
        trend = "📈" if pct >= 0 else "📉"
        dot = "🟢" if pct >= 0 else "🔴"
        cur = int(sd["sell"] * (1 + pct / 100))
        lines.append(f"{trend} {sd['name']}")
        lines.append(f"{dot}{fa_num(abs(pct))}% | قیمت فروش: {fa_num(cur)} | قیمت پایه: {fa_num(sd['sell'])}")
    lines.append("")
    lines.append(f"⏳ بازار {fa_dur(left)} دیگه ری‌رول میشه")
    return "\n".join(lines)


# ═════════ کیفیت محصول ⭐ ═════════

def roll_quality(q5_bonus: float = 0.0) -> dict:
    """قرعه کیفیت برداشت — شب مهتابی شانس ⭐⭐⭐⭐⭐ رو بالا می‌بره (بقیه به‌تناسب کوچیک میشن)"""
    p5 = min(1.0, config.QUALITY_TIERS[-1]["chance"] + q5_bonus)
    scale = (1.0 - p5) / (1.0 - config.QUALITY_TIERS[-1]["chance"])
    r = random.random()
    acc = 0.0
    for t in config.QUALITY_TIERS:
        chance = p5 if t["stars"] == 5 else t["chance"] * scale
        acc += chance
        if r < acc:
            return t
    return config.QUALITY_TIERS[-1]


def quality_stars(tier: dict) -> str:
    return "⭐" * tier["stars"]


# ═════════ جستجو 🔍 ═════════

def search_cooldown_left(user: User) -> int:
    if not user.last_search_at:
        return 0
    cd = config.SEARCH_COOLDOWN_MINUTES * 60
    left = cd - (now_utc() - user.last_search_at).total_seconds()
    return max(0, int(left))


async def do_search(session: AsyncSession, user: User, luck: float = 1.0) -> dict:
    """
    اجرای جستجو — نتیجه کاملاً تصادفی با شانس‌های مستقل
    luck (شخصیت خوش‌شانس 🍀): وزن نتایج خوب رو زیاد و دزد رو کم می‌کنه
    خروجی دیکشنری با status: cooldown | money | seed_* | thief
    """
    left = search_cooldown_left(user)
    if left:
        return {"status": "cooldown", "left": left}

    # وزن‌ها با اثر شانس
    weights = []
    for o in config.SEARCH_OUTCOMES:
        w = o["chance"]
        if o["key"] == "thief" and luck > 1:
            w /= luck
        elif o["key"] != "thief" and luck > 1:
            w *= luck
        weights.append(w)

    outcome = random.choices(config.SEARCH_OUTCOMES, weights=weights, k=1)[0]
    user.last_search_at = now_utc()

    if outcome["key"] == "money":
        amount = random.randint(outcome["min"], outcome["max"])
        user.cash += amount
        return {"status": "money", "amount": amount, "outcome": outcome}

    if outcome["key"] == "thief":
        lost = int(user.cash * random.uniform(outcome["pct_min"], outcome["pct_max"]))
        user.cash = max(0, user.cash - lost)
        return {"status": "thief", "lost": lost, "outcome": outcome}

    # بذرها
    seed_key = random.choice(outcome["pool"])
    await add_seed_stock(session, user.id, seed_key, 1)
    return {"status": outcome["key"], "seed": seed_key, "outcome": outcome}


# ═════════ قمارخانه 🎰 ═════════

def casino_cooldown_left(user: User) -> int:
    if not user.last_casino_at:
        return 0
    cd = config.CASINO_COOLDOWN_HOURS * 3600
    left = cd - (now_utc() - user.last_casino_at).total_seconds()
    return max(0, int(left))


async def casino_play(session: AsyncSession, user: User, bet: int) -> dict:
    """
    یه دست قمار — ۴۰٪ برد ۶۰٪ باخت | برد = ۱٫۸ برابر شرط (تو بلندمدت ضرره)
    """
    if user.level < config.CASINO_MIN_LEVEL:
        return {"status": "locked"}
    left = casino_cooldown_left(user)
    if left:
        return {"status": "cooldown", "left": left}
    if bet not in config.CASINO_BETS:
        return {"status": "bad_bet"}
    if user.cash < bet:
        return {"status": "poor"}

    user.cash -= bet
    user.last_casino_at = now_utc()

    if random.random() < config.CASINO_WIN_CHANCE:
        prize = int(bet * config.CASINO_WIN_MULT)
        user.cash += prize
        return {"status": "win", "bet": bet, "prize": prize, "cash": user.cash}
    return {"status": "lose", "bet": bet, "prize": 0, "cash": user.cash}


# ═════════ پناهگاه 🏚 ═════════

def shelter_price(level: int) -> int:
    """هزینه ارتقا به لول level (۱..۱۰)"""
    return config.SHELTER_PRICES[min(max(level, 1), config.SHELTER_MAX_LEVEL) - 1]


def shelter_raid_cut(level: int) -> float:
    """کاهش خسارت یورش — هر لول ۵٪"""
    return min(0.9, config.SHELTER_RAID_CUT_PER_LEVEL * level)


def shelter_dodge_chance(level: int) -> float:
    """شانس فرار کامل از یورش — هر لول ۴٪"""
    return min(0.5, config.SHELTER_DODGE_PER_LEVEL * level)


def seed_storage_cap(user: User) -> int:
    """ظرفیت انبار هر بذر — پناهگاه بالاتر، محل نگهداری بیشتر"""
    return config.SHELTER_SEED_CAP_BASE + config.SHELTER_SEED_CAP_PER_LEVEL * user.shelter_level


async def upgrade_shelter(session: AsyncSession, user: User) -> tuple[bool, str]:
    """ارتقای پناهگاه از جیب"""
    if user.shelter_level >= config.SHELTER_MAX_LEVEL:
        return False, "⭐ پناهگاهت مکس لوله"
    next_level = user.shelter_level + 1
    price = shelter_price(next_level)
    if user.cash < price:
        return False, f"❌ ارتقا {money(price)} هزینه داره و پولت کمه"
    user.cash -= price
    user.shelter_level = next_level
    return True, (
        f"🏚 پناهگاهت رفت رو لول {fa_num(next_level)}\n"
        f"🛡 خسارت یورش {fa_num(int(shelter_raid_cut(next_level) * 100))}٪ کمتره\n"
        f"📦 ظرفیت انبار هر بذر {fa_num(seed_storage_cap(user))} تا شد"
    )


# ═════════ یورش پلیس 🚔 ═════════

async def police_wave(session: AsyncSession) -> list[dict]:
    """
    موج یورش — برای هر بازیکن فعال ۲۴ ساعت اخیر که انبار محصول داره
    خروجی: لیست [{user, lost(dict seed→count), dodged}] برای اطلاع‌رسانی
    """
    limit = now_utc() - timedelta(hours=config.POLICE_ACTIVITY_HOURS)
    q = select(User).where(User.last_seen_at >= limit)
    users_ = list((await session.execute(q)).scalars())

    out: list[dict] = []
    for u in users_:
        stock = await get_stock(session, u.id)
        total = sum(stock.values())
        if total <= 0:
            continue
        if random.random() >= config.POLICE_RAID_CHANCE:
            continue

        if u.shelter_level and random.random() < shelter_dodge_chance(u.shelter_level):
            out.append({"user": u, "lost": {}, "dodged": True})
            continue

        cut = shelter_raid_cut(u.shelter_level)
        eff_pct = config.POLICE_DESTROY_PCT * (1 - cut)
        lost: dict[str, int] = {}
        q2 = select(SeedStock).where(SeedStock.user_id == u.id, SeedStock.count > 0)
        for row in (await session.execute(q2)).scalars():
            n = int(row.count * eff_pct + 0.5)
            if n > 0:
                row.count -= n
                lost[row.seed_key] = n
        out.append({"user": u, "lost": lost, "dodged": False})
    return out


def police_report_text(rec: dict) -> str:
    """پیام یورش برای خود بازیکن"""
    u = rec["user"]
    if rec["dodged"]:
        return (
            "<b>🚔 موج پلیس اومد ولی رد شد</b>\n\n"
            "🏚 پناهگاهت کاری کرد که چیزی پیدا نکنن 😮‍💨\n"
            "محله امنه — به کارت ادامه بده"
        )
    lost = rec["lost"]
    total = sum(lost.values())
    lines = ["<b>🚔 یورش پلیس!</b>", ""]
    if total <= 0:
        lines.append("پلیس اومد ولی چیز مهمی گیرش نیومد 😅")
    else:
        lines.append("🚨 مأمورا یه سری از محصولات انبارتو نابود کردن:")
        for k, n in lost.items():
            nm = config.SEEDS.get(k, {}).get("name", k)
            lines.append(f"▫️ {nm} ×{fa_num(n)}")
        if u.shelter_level:
            lines.append("")
            lines.append(f"🏚 بدون پناهگاه لول {fa_num(u.shelter_level)} ضررت بیشتر بود")
        lines.append("💡 پناهگاهتو ارتقا بده تا یورش‌های بعدی کمتر ضرر بزنه")
    return "\n".join(lines)


# ═════════ کاروان 🚛 (درون حافظه) ═════════

# chat_id → {hp, max_hp, started_at, expires_at, damages: {user_id: dmg}, names: {user_id: name}, message_id}
CARAVANS: dict[int, dict] = {}
# (chat_id, user_id) → last hit datetime
CARAVAN_HITS: dict[tuple[int, int], object] = {}


def caravan_spawn(chat_id: int) -> dict:
    """اسپون کاروان جدید با HP از تیِرها"""
    hp = random.choice(config.CARAVAN_HP_TIERS)
    cv = {
        "hp": hp,
        "max_hp": hp,
        "expires_at": now_utc() + timedelta(minutes=config.CARAVAN_LIFETIME_MINUTES),
        "damages": {},
        "names": {},
        "message_id": None,
    }
    CARAVANS[chat_id] = cv
    return cv


def caravan_active(chat_id: int) -> dict | None:
    cv = CARAVANS.get(chat_id)
    if cv and cv["expires_at"] > now_utc() and cv["hp"] > 0:
        return cv
    return None


def caravan_hit_left(chat_id: int, user_id: int) -> int:
    """ثانیه مونده از کولدون ضربه (هر ۱ دقیقه)"""
    last = CARAVAN_HITS.get((chat_id, user_id))
    if not last:
        return 0
    left = config.CARAVAN_HIT_COOLDOWN_SECONDS - (now_utc() - last).total_seconds()
    return max(0, int(left))


def caravan_loot_key() -> str:
    """قرعه بذر جایزه نهایی کاروان"""
    r = random.random()
    acc = 0.0
    for loot in config.CARAVAN_LOOT:
        acc += loot["chance"]
        if r < acc:
            return random.choice(loot["pool"])
    return random.choice(config.CARAVAN_LOOT[0]["pool"])


async def caravan_attack(session: AsyncSession, chat_id: int, user: User, dmg: int) -> dict:
    """
    ضربه به کاروان — دمیج = قدرت حمله بازیکن
    هر ضربه جایزه نقدی و XP همون لحظه میده
    خروجی: {status: none|cooldown|hit|killed, ...}
    """
    cv = caravan_active(chat_id)
    if not cv:
        return {"status": "none"}

    left = caravan_hit_left(chat_id, user.id)
    if left:
        return {"status": "cooldown", "left": left}

    CARAVAN_HITS[(chat_id, user.id)] = now_utc()
    dmg = max(1, dmg)
    cv["hp"] -= dmg
    cv["damages"][user.id] = cv["damages"].get(user.id, 0) + dmg
    name = user.first_name or user.username or "؟"
    cv["names"][user.id] = name

    cash_gain = dmg * config.CARAVAN_MONEY_PER_DMG
    user.cash += cash_gain
    notes = add_xp(user, config.CARAVAN_HIT_XP)

    res = {
        "status": "hit",
        "dmg": dmg,
        "cash": cash_gain,
        "hp_left": max(0, cv["hp"]),
        "max_hp": cv["max_hp"],
        "notes": notes,
    }

    if cv["hp"] <= 0:
        res["status"] = "killed"
        res["rewards"] = await _caravan_settle(session, chat_id, killed=True)
    return res


async def caravan_expire(session: AsyncSession, chat_id: int) -> dict | None:
    """تایم کاروان تموم شده — اگه فعال بود تسویه جزئی کن"""
    cv = CARAVANS.get(chat_id)
    if not cv or cv["expires_at"] > now_utc() or cv["hp"] <= 0:
        return None
    rewards = await _caravan_settle(session, chat_id, killed=False)
    return {"rewards": rewards}


async def _caravan_settle(session: AsyncSession, chat_id: int, killed: bool) -> list[dict]:
    """
    تسویه کاروان — بذر به هر شرکت‌کننده (قرعه) + نفر اول بیشترین جایزه
    خروجی: [{user_id, name, dmg, seed(seed name or None), top(bool), money}]
    """
    cv = CARAVANS.pop(chat_id, None)
    if not cv:
        return []

    damages = cv["damages"]
    if not damages:
        return []

    top_uid = max(damages, key=damages.get)
    out: list[dict] = []
    for uid, dmg in sorted(damages.items(), key=lambda kv: -kv[1]):
        user = await session.get(User, uid)
        if not user:
            continue
        is_top = uid == top_uid
        # نفر اول حتماً بذر می‌گیره (کشته‌شده: معمولاً درجه بالا | فرار کرده: معمولی)
        if is_top:
            seed_key = caravan_loot_key() if killed else random.choice(config.CARAVAN_LOOT[0]["pool"])
        elif killed:
            seed_key = caravan_loot_key() if random.random() < 0.75 else None
        else:
            seed_key = random.choice(config.CARAVAN_LOOT[0]["pool"]) if random.random() < 0.4 else None

        seed_name = None
        if seed_key:
            await add_seed_stock(session, uid, seed_key, 1)
            seed_name = config.SEEDS[seed_key]["name"]

        money_prize = dmg * config.CARAVAN_MONEY_PER_DMG * (3 if (killed and is_top) else 1)
        user.cash += money_prize

        out.append({
            "user_id": uid,
            "name": cv["names"].get(uid, "؟"),
            "dmg": dmg,
            "seed": seed_name,
            "top": is_top,
            "money": money_prize,
        })
    return out


def caravan_board_text(cv: dict) -> str:
    """متن برد کاروان برای گروه"""
    pct = max(0, cv["hp"]) / cv["max_hp"]
    filled = round(pct * 10)
    bar = "🟥" * filled + "⬜" * (10 - filled)
    left = max(0, int((cv["expires_at"] - now_utc()).total_seconds()))

    lines = [
        "<b>🚛 کاروان اومد تو محله!</b>",
        "",
        f"❤️ HP {bar} {fa_num(max(0, cv['hp']))}/{fa_num(cv['max_hp'])}",
        f"⏳ تا {fa_dur(left)} دیگه فرار می‌کنه",
        "",
        "هرکی هر 1 دقیقه یه ضربه می‌تونه بزنه — دمیجت = قدرت حمله‌ته",
        "🏆 نفر اول بیشترین جایزه رو می‌گیره — شاید بذر جهنم 🔥 یا ابلیس 😈",
        "",
    ]
    top = sorted(cv["damages"].items(), key=lambda kv: -kv[1])[:5]
    if top:
        lines.append("⚔️ دمیج‌ها:")
        medals = ["🥇", "🥈", "🥉"]
        for i, (uid, dmg) in enumerate(top):
            medal = medals[i] if i < 3 else f"{i + 1}."
            lines.append(f"{medal} {cv['names'].get(uid, '؟')} — {fa_num(dmg)}")
    return "\n".join(lines)


def caravan_result_text(cv: dict, res: dict) -> str:
    """متن نتیجه ضربه"""
    lines = [f"<b>⚔️ {fa_num(res['dmg'])} دمیج به کاروان</b>", ""]
    lines.append(f"💰 جایزه ضربه {money(res['cash'])} | ❤️ مونده {fa_num(res['hp_left'])}")
    if res["status"] == "killed":
        lines.append("")
        lines.append("💀 کاروان افتاد! جایزه‌ها تقسیم شد")
    return "\n".join(lines)


def caravan_end_text(rewards: list[dict], killed: bool) -> str:
    """متن پایان کاروان (کشته‌شده یا فرارکرده)"""
    if not rewards:
        return "🚛 کاروان بدون اینکه کسی برسه رد شد و رفت 💨"
    head = "💀 <b>کاروان غارت شد!</b>" if killed else "🚛 <b>کاروان از محله رد شد</b>"
    lines = [head, ""]
    for r in rewards:
        tag = "🏆 " if r["top"] else "▫️ "
        part = f"{tag}{r['name']} — {fa_num(r['dmg'])} دمیج | 💰 {fa_num(r['money'])}TP"
        if r["seed"]:
            part += f" | 🎁 {r['seed']}"
        lines.append(part)
    if killed:
        lines.append("")
        lines.append("🏆 نفر اول بیشترین جایزه رو گرفت 😈")
    return "\n".join(lines)
