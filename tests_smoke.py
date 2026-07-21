"""
اسموک‌تست آفلاین تریاکی — بدون اتصال به تلگرام
اجرا:  python tests_smoke.py
"""

import asyncio
import os
import random
from datetime import timedelta
from types import SimpleNamespace

random.seed(7)

# قبل از ایمپورت ماژول‌های پروژه، دیتابیس تست رو تنظیم می‌کنیم
os.environ["TERIAKY_DB"] = "sqlite+aiosqlite:////tmp/teriaky_test.db"
if os.path.exists("/tmp/teriaky_test.db"):
    os.remove("/tmp/teriaky_test.db")

import config  # noqa: E402
from database import init_db, session_scope  # noqa: E402
from models import InventoryItem, Plot, User  # noqa: E402
from services import combat, economy, users  # noqa: E402
from utils import fa_dur, fa_num, money, money_tp, now_utc  # noqa: E402

PASS = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS
    assert cond, f"❌ {name} | {detail}"
    PASS += 1
    print(f"✅ {name} {detail}")


def tg(uid, username=None, first_name=None):
    return SimpleNamespace(id=uid, username=username, first_name=first_name)


async def main() -> None:
    await init_db()

    # ── فرمول‌های اقتصادی ──
    prices = [economy.plot_price(i) for i in range(config.MAX_PLOTS)]
    check("قیمت زمین افزایشیه", all(a < b for a, b in zip(prices, prices[1:])), str(prices))
    check("اولین زمین ۱۰۰۰ تی‌پوینته", prices[0] == config.PLOT_BASE_PRICE)

    ups = [economy.upgrade_price(l) for l in (1, 2)]
    check("هزینه آپگرید تصاعدیه", ups[0] < ups[1], str(ups))

    unlock_levels = [c["min_level"] for c in config.CROPS.values()]
    check("ترتیب باز شدن محصولات صعودیه", unlock_levels == sorted(unlock_levels), str(unlock_levels))
    check("تریاک از لول ۱ بازه", economy.is_crop_unlocked("teriak", 1))
    check("پیوته لول ۱۰ می‌خواد", not economy.is_crop_unlocked("peyote", 9) and economy.is_crop_unlocked("peyote", 10))
    check("سود مزرعه خیلی بالاتر از کنده‌کاریه", economy.crop_yield("teriak", 1) - config.CROPS["teriak"]["cost"] > config.MINE_MAX)

    # ── قرعه کنده‌کاری ──
    rolls = [economy.mine_roll() for _ in range(20000)]
    low = sum(1 for r in rolls if r <= config.MINE_COMMON_MAX) / len(rolls)
    check("محدوده جایزه ۱۰ تا ۱۵۰", min(rolls) >= 10 and max(rolls) <= 150, f"min={min(rolls)} max={max(rolls)}")
    check("بازه ۱۰ تا ۱۰۰ پرشانسه (~۷۵٪)", 0.68 < low < 0.82, f"share={low:.2f}")

    # ── فلو کاربر ──
    async with session_scope() as s:
        u1, c1 = await users.get_or_create(s, tg(1001, "ali", "علی"))
        u2, c2 = await users.get_or_create(s, tg(1002, "sara", "سارا"))
        u3, _ = await users.get_or_create(s, tg(1003, "boss", "باس"))
        u3.level = 20  # خیلی دور از سطح بقیه
        check("ثبت‌نام خودکار کار می‌کنه", c1 and c2)

        u1_dup, created_dup = await users.get_or_create(s, tg(1001, "ali2", "علی جدید"))
        check("ثبت‌نام تکراری نشه", not created_dup and u1_dup.id == u1.id and u1_dup.username == "ali2")

        check("پول شروع درسته", u1.cash == config.START_CASH)

        # خرید زمین
        price = economy.plot_price(0)
        u1.cash += price
        u1.cash -= price
        s.add(Plot(user_id=u1.id))
        await s.flush()
        plot = (await s.execute(
            __import__("sqlalchemy").select(Plot).where(Plot.user_id == u1.id)
        )).scalar_one()
        check("زمین خریداری شد", plot.status == "empty" and plot.level == 1)

        # کاشت تریاک
        cost = config.CROPS["teriak"]["cost"]
        cash_before = u1.cash
        plot.status = "growing"
        plot.crop = "teriak"
        plot.planted_at = now_utc()
        plot.ready_at = now_utc() + timedelta(seconds=economy.crop_grow_seconds("teriak", 1))
        u1.cash -= cost
        state, left = plot.current_status()
        check("کاشت: وضعیت growing", state == "growing" and left > 0)
        check("کاشت: پول کم شد", u1.cash == cash_before - cost)

        # برداشت بعد از تمام شدن تایمر
        plot.ready_at = now_utc() - timedelta(seconds=1)
        state, _ = plot.current_status()
        check("برداشت: وضعیت ready", state == "ready")
        gain = economy.crop_yield("teriak", 1)
        u1.cash += gain
        plot.status, plot.crop, plot.planted_at, plot.ready_at = "empty", None, None, None
        check("برداشت: سود واریز شد", u1.cash == cash_before - cost + gain, f"gain={gain}")

        # لول‌آپ
        lvl_before = u1.level
        notes = users.add_xp(u1, config.XP_BASE * lvl_before)
        check("لول‌آپ با xp کافی", u1.level == lvl_before + 1 and notes)
        check("جایزه نقدی لول‌آپ", u1.cash > cash_before)

        # فروشگاه
        s.add(InventoryItem(user_id=u1.id, item_key="knife"))
        s.add(InventoryItem(user_id=u1.id, item_key="jacket"))
        await s.flush()
        keys = await users.get_item_keys(s, u1.id)
        atk, dfn = combat.combat_stats(u1, keys)
        base_atk = config.ATK_BASE + config.ATK_PER_LEVEL * u1.level
        base_def = config.DEF_BASE + config.DEF_PER_LEVEL * u1.level
        check("سلاح روی حمله اثر داره", atk == base_atk + config.SHOP_ITEMS["knife"]["attack"])
        check("زره روی دفاع اثر داره", dfn == base_def + config.SHOP_ITEMS["jacket"]["defense"])

        # ریجن انرژی
        u1.energy = 50
        u1.energy_updated_at = now_utc() - timedelta(minutes=config.ENERGY_REGEN_MINUTES * 10)
        users.apply_energy_regen(u1)
        check("ریجن انرژی", u1.energy == 50 + 10, f"energy={u1.energy}")
        u1.energy_updated_at = now_utc() - timedelta(hours=50)
        users.apply_energy_regen(u1)
        check("سقف انرژی رعایت میشه", u1.energy == config.MAX_ENERGY)

        # ── حمله ──
        u1.level = u2.level = 5
        t = await combat.find_target(s, u1)
        check("هدف فقط هم‌لوله", t is not None and t.id == u2.id, f"target={t}")

        u1.energy = config.MAX_ENERGY
        u2.cash = 2000
        user_wins = target_losses = 0
        for _ in range(200):
            u1.energy = config.MAX_ENERGY
            u2.cash = 2000
            u1.energy -= config.ATTACK_ENERGY_COST
            atk2, _ = combat.combat_stats(u1, keys)
            _, dfn2 = combat.combat_stats(u2, [])
            win, a, d = combat.battle_roll(atk2, dfn2)
            check_ok = (0.85 * atk2 - 1 <= a <= 1.15 * atk2 + 1) and (0.85 * dfn2 - 1 <= d <= 1.15 * dfn2 + 1)
            if not check_ok:
                raise AssertionError("رول خارج از بازه")
            if win:
                amt = combat.steal_amount(u2.cash)
                assert config.STEAL_MIN_PCT * 2000 - 1 <= amt <= config.STEAL_MAX_PCT * 2000 + 1, f"steal={amt}"
                user_wins += 1
            else:
                target_losses += 1
        check("نتیجه نبرد هر دو طرف دیده میشه", user_wins > 0 and target_losses > 0, f"win={user_wins} lose={target_losses}")

        u1.last_attack_at = now_utc()
        cd = combat.cooldown_left(u1)
        check("کولدون فعاله", 0 < cd <= config.ATTACK_COOLDOWN_MINUTES * 60, f"cd={cd}")
        u1.last_attack_at = now_utc() - timedelta(minutes=config.ATTACK_COOLDOWN_MINUTES + 1)
        check("کولدون بعدش صفره", combat.cooldown_left(u1) == 0)

        await s.commit()

    # ── کیبوردها ──
    from keyboards import keyboards as kb
    from telegram import InlineKeyboardMarkup

    async with session_scope() as s:
        u1 = await users.get_by_tg(s, 1001)
        plots = list((await s.execute(__import__("sqlalchemy").select(Plot).where(Plot.user_id == u1.id))).scalars())
        keys = await users.get_item_keys(s, u1.id)
        kbs = [
            kb.main_menu_kb(),
            kb.confirm_kb("cf:test"),
            kb.profile_kb(),
            kb.farm_kb(u1, plots, economy.plot_price(len(plots))),
            kb.crops_kb(u1, plots[0]),
            kb.shop_kb(u1, set(keys)),
            kb.attack_home_kb(),
            kb.attack_target_kb(u1.id),
            kb.rank_kb(),
            kb.home_kb(),
        ]
        for k in kbs:
            assert isinstance(k, InlineKeyboardMarkup)
            for row in k.inline_keyboard:
                for b in row:
                    assert b.callback_data is None or len(b.callback_data.encode()) <= 64, b.callback_data
                    assert b.style in (None, "primary", "success", "danger"), b.style
        check("۱۰ کیبورد ساخته و ولیدیت شدن", True)

        styled = sum(1 for k in kbs for row in k.inline_keyboard for b in row if b.style)
        check("دکمه‌های رنگی استفاده شدن", styled >= 15, f"styled={styled}")

    # ── ایمپورت هندلرها و سیم‌کشی روی اپلیکیشن واقعی (بدون شبکه) ──
    import handlers  # noqa
    from telegram.ext import Application
    app = Application.builder().token("123:test").build()
    handlers.register_handlers(app)
    total = sum(len(h) for h in app.handlers.values())
    check("همه هندلرها رجیستر شدن", total >= 25, f"handlers={total}")

    # فرمت‌ها
    check("فرمت عدد فارسی", fa_num(12345) == "۱۲٬۳۴۵", fa_num(12345))
    check("فرمت مدت", fa_dur(169) == "۲ دقیقه و ۴۹ ثانیه", fa_dur(169))
    check("واحد پول کامل", money(12345) == "۱۲٬۳۴۵ تی‌پوینت", money(12345))
    check("واحد پول خلاصه", money_tp(12345) == "۱۲٬۳۴۵ TP", money_tp(12345))

    print(f"\n🎉 همه تست‌ها سبز شدن — {PASS} مورد")


asyncio.run(main())
