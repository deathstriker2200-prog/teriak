"""
اسموک‌تست آفلاین تریاکی — فاز ۲ — بدون اتصال به تلگرام
اجرا:  python tests_smoke.py
"""

import asyncio
import os
import random
from datetime import timedelta
from types import SimpleNamespace

random.seed(7)

os.environ["TERIAKY_DB"] = "sqlite+aiosqlite:////tmp/teriaky_test.db"
os.environ["TERIAKY_ADMIN_IDS"] = "1001, 1003"
if os.path.exists("/tmp/teriaky_test.db"):
    os.remove("/tmp/teriaky_test.db")

import config  # noqa: E402
from database import init_db, session_scope  # noqa: E402
from models import Dog, Plot, User  # noqa: E402
from services import combat, dogs as dog_svc, economy, farming, shop_svc, users  # noqa: E402
from sqlalchemy import select  # noqa: E402
from utils import fa_dur, fa_num, find_by_name, money, money_tp, normalize_fa, now_utc  # noqa: E402

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

    # ═══ کاتالوگ‌ها ═══
    seed_lvls = [s["min_level"] for s in config.SEEDS.values()]
    check("ترتیب لول بذرها صعودیه", seed_lvls == sorted(seed_lvls), str(seed_lvls))

    legends = [k for k, a in config.ARMORS.items() if a.get("legendary")]
    check("فقط یه زره افسانه‌ای هست", legends == ["legend"])
    check("توضیح زره افسانه‌ای دقیق ست شده", "نصف مقدار سکه‌ای که دشمن از شما دریافت می‌کند از بین برود" in config.ARMORS["legend"]["desc"])

    rares = [k for k, d in config.DOGS.items() if d.get("rare")]
    check("فقط یه سگ کمیاب هست", len(rares) == 1, str(rares))

    check("قیمت و قدرت همه سلاح‌ها مثبته", all(w["price"] > 0 and w["attack"] > 0 for w in config.WEAPONS.values()))
    check("همه آیتم‌ها desc و min_level دارن",
          all(i.get("desc") and "min_level" in i for i in list(config.WEAPONS.values()) + list(config.ARMORS.values()) + list(config.SEEDS.values()) + list(config.DOGS.values())))

    # ═══ منحنی تجربه ═══
    needs = [economy.xp_need(l) for l in range(1, 21)]
    check("منحنی xp صعودیه", needs == sorted(needs), str(needs[:6]))
    diffs = [b - a for a, b in zip(needs, needs[1:])]
    check("سختی تدریجی زیاد میشه (محدب)", diffs == sorted(diffs), str(diffs[:6]))
    check("لول‌های اول سریعه", economy.xp_need(1) <= 60 and economy.xp_need(2) <= 180, f"1={economy.xp_need(1)} 2={economy.xp_need(2)}")

    # ═══ اقتصاد ═══
    prices = [economy.plot_price(i) for i in range(config.MAX_PLOTS)]
    check("قیمت زمین افزایشیه", all(a < b for a, b in zip(prices, prices[1:])), str(prices))
    check("گیت لول زمین", economy.plot_required_level(0) == 1 and economy.plot_required_level(7) == 8)

    y1 = economy.crop_yield("teriak", 1, 1)
    y2 = economy.crop_yield("teriak", 2, 1)
    y3 = economy.crop_yield("teriak", 1, 11)
    check("برداشت با لول زمین بیشتره", y2 > y1, f"{y1}→{y2}")
    check("برداشت با لول کاربر بیشتره (۲٪ هر لول)", y3 > y1, f"{y1}→{y3}")

    rolls = [economy.mine_roll() for _ in range(20000)]
    low = sum(1 for r in rolls if r <= config.MINE_COMMON_MAX) / len(rolls)
    check("کنده‌کاری تو بازه ۱۰ تا ۱۵۰", min(rolls) >= 10 and max(rolls) <= 150)
    check("بازه پایین کنده‌کاری پرشانسه", 0.68 < low < 0.82, f"{low:.2f}")

    # ═══ مچ اسم فارسی ═══
    check("نرمال سازی فارسی", normalize_fa("دوبرمن  اصغر!") == "دوبرمن اصغر")
    k, _ = find_by_name(config.WEAPONS, "چاقو")
    check("«خرید چاقو» سلاح رو پیدا می‌کنه", k == "knife")
    kind, key, _ = shop_svc.find_shop_item("تریاک")
    check("«خرید تریاک» بذر رو پیدا می‌کنه", kind == "seed" and key == "teriak")
    dk, _ = dog_svc.find_dog("دوبرمن اصغر")
    check("«خرید سگ دوبرمن اصغر» سگ رو پیدا می‌کنه", dk == "doberman")
    dk2, _ = dog_svc.find_dog("گرگ")
    check("مچ جزئی نژاد سگ", dk2 == "blackwolf")

    # ═══ فلو کاربر ═══
    async with session_scope() as s:
        u1, _ = await users.get_or_create(s, tg(1001, "ali", "علی"))
        u2, _ = await users.get_or_create(s, tg(1002, "sara", "سارا"))
        u3, _ = await users.get_or_create(s, tg(1003, "boss", "باس"))
        u3.level = 20

        # ── خرید زمین و بذر و کاشت ──
        u1.cash = 100000  # شارژ حساب برای تست‌ها
        ok, msg = await farming.buy_plot(s, u1)
        check("خرید زمین اول", ok and bool(msg))
        plots = await farming.get_user_plots(s, u1.id)
        plot = plots[0]

        u1.cash = 1000
        ok, msg = await shop_svc.purchase(s, u1, "seed", "teriak")
        check("خرید بذر تریاک", ok and u1.cash == 1000 - config.SEEDS["teriak"]["price"])
        stock = await farming.get_stock(s, u1.id)
        check("انبار بذر آپدیت شد", stock.get("teriak") == 1)

        ok, msg = await farming.plant(s, u1, plot, "teriak")
        check("کاشت با بذر", ok, msg)
        stock = await farming.get_stock(s, u1.id)
        check("بذر مصرف شد", stock.get("teriak") == 0)

        ok, msg = await farming.plant(s, u1, plot, "teriak")
        check("کاشت دوباره بدون بذر رد میشه", not ok)

        # ── برداشت و کولدون ۲ دقیقه ──
        plot.ready_at = now_utc() - timedelta(seconds=1)
        cash_before = u1.cash
        ok, alert, extra = await farming.harvest_all(s, u1)
        gain_expected = economy.crop_yield("teriak", 1, u1.level)
        check("برداشت موفق", ok and u1.cash == cash_before + gain_expected, f"gain={gain_expected}")
        check("پیام برداشت ساخته شد", bool(extra))

        # بذر جدید و کاشت مجدد برای تست کولدون
        await farming.add_seed_stock(s, u1.id, "teriak", 1)
        await farming.plant(s, u1, plot, "teriak")
        plot.ready_at = now_utc() - timedelta(seconds=1)
        ok, msg, _ = await farming.harvest_all(s, u1)
        check("کولدون ۲ دقیقه برداشت جلوگیری می‌کنه", not ok and "۲ دقیقه" in msg, msg)

        u1.last_harvest_at = now_utc() - timedelta(seconds=config.HARVEST_COOLDOWN_SECONDS + 5)
        ok, alert, extra = await farming.harvest_all(s, u1)
        check("بعد از کولدون برداشت میشه", ok)

        # ── گیت لول فروشگاه ──
        ok, msg = await shop_svc.purchase(s, u1, "weap", "plasma")
        check("سلاح قفل‌روی‌لول رد میشه", not ok and "لول" in msg)
        u1.cash = 500000
        ok, msg = await shop_svc.purchase(s, u1, "weap", "deagle")
        u1.level = 5
        check("سلاح بالاتر از لول قفله", not ok)
        u1.level = 15
        ok, msg = await shop_svc.purchase(s, u1, "weap", "deagle")
        check("با لول کافی خریده", ok)
        ok, msg = await shop_svc.purchase(s, u1, "weap", "deagle")
        check("خرید تکراری سلاح رد میشه", not ok)

        ok, msg = await shop_svc.purchase(s, u1, "arm", "legend")
        check("زره افسانه‌ای خریده", ok)

        # ── سگ‌ها ──
        ok, msg = await shop_svc.purchase(s, u1, "dog", "doberman")
        check("خرید سگ دوبرمن اصغر", ok, msg)
        ok, msg = await shop_svc.purchase(s, u1, "dog", "blackwolf")
        check("خرید گرگ سیاه کمیاب", ok)
        ok, msg = await shop_svc.purchase(s, u1, "dog", "doberman")
        check("خرید سگ تکراری رد میشه", not ok)

        dogs = await dog_svc.get_user_dogs(s, u1.id)
        wolf = next(d for d in dogs if d.dog_key == "blackwolf")
        dob = next(d for d in dogs if d.dog_key == "doberman")
        check("سگ لول ۱ شروع می‌کنه", wolf.level == 1 and wolf.xp == 0)
        check("قدرت پایه سگ درسته", dog_svc.dog_attack(dob) == config.DOGS["doberman"]["attack"])

        # ── غذا دادن ──
        u1.cash = 100000
        check("۵ غذا در روز داره", dog_svc.feeds_left(u1) == config.DOG_FEED_PER_DAY)

        notes_all = []
        for _ in range(5):
            ok, msg, notes = await dog_svc.feed_dog(s, u1, wolf, "gold")
            assert ok, msg
            notes_all.extend(notes)
        check("۵ بار غذا اوکیه", True)
        check("ششمی رد میشه (سقف روزانه)", dog_svc.feeds_left(u1) == 0)
        ok, msg, _ = await dog_svc.feed_dog(s, u1, wolf, "gold")
        check("غذای ششم خطا میده", not ok)

        xp_expect = 5 * config.DOG_FOODS["gold"]["xp"]
        check("xp سگ از غذا رفت بالا و لول‌آپ خورد", wolf.level > 1 and notes_all, f"lvl={wolf.level} xp={wolf.xp} ({xp_expect} داده بودیم)")

        atk_before = dog_svc.dog_attack(wolf)
        check("قدرت سگ با لول بیشتر میشه", atk_before > config.DOGS["blackwolf"]["attack"])

        # ریست روزانه غذا
        u1.feed_day = "2000-01-01"
        check("فردا سهم غذا ریست میشه", dog_svc.feeds_left(u1) == config.DOG_FEED_PER_DAY)

        # ── استت نبرد با سگ و بونس لول آیتم ──
        keys = await users.get_item_keys(s, u1.id)
        u2.level = 5
        atk, dfn = combat.combat_stats(u1, keys, dogs)
        base_atk = config.ATK_BASE + config.ATK_PER_LEVEL * u1.level
        weap_eff = int(config.WEAPONS["deagle"]["attack"] * (1 + config.LEVEL_ITEM_BONUS * (u1.level - 1)))
        expected = base_atk + weap_eff + dog_svc.dog_attack(dob) + dog_svc.dog_attack(wolf)
        check("حمله = پایه + سلاح + سگ‌ها", atk == expected, f"{atk} vs {expected}")

        # ── بونس سرقت گرگ و نصف زره ──
        wolf.level = config.DOG_MAX_LEVEL
        bonus = dog_svc.rare_steal_bonus(dogs)
        check("بونس گرگ در لول مکس ۱۵٪ه", abs(bonus - config.RARE_DOG_STEAL_MAX) < 1e-9, f"{bonus:.2%}")
        wolf.level = 2
        check("بونس گرگ با لول کمتره", abs(dog_svc.rare_steal_bonus(dogs) - 0.15 * 2 / config.DOG_MAX_LEVEL) < 1e-9)

        random.seed(1)
        amount, b, halved = combat.steal_amount(10000, [], False)
        check("سرقت بدون مادیفایر", 1000 <= amount <= 2500 and not halved and b == 0, str(amount))
        random.seed(1)
        amount_base, _, _ = combat.steal_amount(10000, [], False)
        random.seed(1)
        amount_leg, _, halved_leg = combat.steal_amount(10000, [], True)
        check("زره افسانه‌ای نصف می‌کنه", halved_leg and abs(amount_leg * 2 - amount_base) <= 1, f"{amount_leg} vs {amount_base}")

        # ── حمله کامل (سرویس) ──
        from models import InventoryItem
        s.add(InventoryItem(user_id=u2.id, item_key="legend"))
        await s.flush()

        results = {"win": 0, "lose": 0, "halved_count": 0, "bonus_count": 0}
        for _ in range(300):
            u1.energy = config.MAX_ENERGY
            u1.last_attack_at = None
            u2.cash = 50000
            res = await combat.execute_attack(s, u1, u2)
            assert res["ok"]
            if res["win"]:
                results["win"] += 1
                if res["halved"]:
                    results["halved_count"] += 1
                if res["bonus"]:
                    results["bonus_count"] += 1
            else:
                results["lose"] += 1
        check("تو فلو کامل هم برد هم باخت دیده میشه", results["win"] > 0 and results["lose"] > 0, str(results))
        check("زره افسانه‌ای قربانی همیشه نصف می‌کنه", results["halved_count"] == results["win"],
              f"halved={results['halved_count']} win={results['win']}")
        check("بونس گرگ تو هر برد اعماله", results["bonus_count"] == results["win"])

        # کولدون ۱ دقیقه
        u1.energy = config.MAX_ENERGY
        u1.last_attack_at = None
        res = await combat.execute_attack(s, u1, u2)
        res2 = await combat.execute_attack(s, u1, u2)
        check("کولدون ۱ دقیقه فعاله", not res2["ok"] and res2["reason"] == "cooldown" and res2["left"] <= 60, str(res2.get("left")))
        u1.last_attack_at = now_utc() - timedelta(seconds=61)
        res3 = await combat.execute_attack(s, u1, u2)
        check("بعد ۱ دقیقه آزاده", res3["ok"])

        # هدف رندوم فقط هم‌لول
        t = await combat.find_target(s, u1)  # u1 لول ۱۴ u2 لول ۵ u3 لول ۲۰
        check("جستجوی رندوم هیچ‌کدوم رو بیرون بازه نمیاره", t is None or abs(t.level - u1.level) <= 2, f"{t}")

        # ── لول‌آپ بازیکن روی منحنی جدید ──
        lvl_before = u1.level
        notes = users.add_xp(u1, economy.xp_need(u1.level))
        check("لول‌آپ با منحنی Idle", u1.level == lvl_before + 1 and notes)

        await s.commit()

    # ═══ کیبوردها ═══
    from keyboards import keyboards as kb
    from telegram import InlineKeyboardMarkup

    async with session_scope() as s:
        u1 = await users.get_by_tg(s, 1001)
        plots = await farming.get_user_plots(s, u1.id)
        stock = await farming.get_stock(s, u1.id)
        keys = await users.get_item_keys(s, u1.id)
        dogs = await dog_svc.get_user_dogs(s, u1.id)

        kbs = [
            kb.main_menu_kb(), kb.confirm_kb("cf:x"), kb.home_kb(), kb.profile_kb(),
            kb.farm_kb(u1, plots, economy.plot_price(len(plots)), 1),
            kb.seeds_kb(u1, plots[0], stock),
            kb.shop_sections_kb(),
            kb.shop_weap_kb(u1, set(keys)), kb.shop_arm_kb(u1, set(keys)),
            kb.shop_seed_kb(u1, stock), kb.shop_dog_kb(u1, {d.dog_key for d in dogs}, len(dogs)),
            kb.shop_food_kb(),
            kb.my_dogs_kb(dogs), kb.feed_foods_kb(dogs[0].id),
            kb.attack_home_kb(), kb.attack_target_kb(1), kb.attack_result_kb(), kb.rank_kb(),
            kb.tx_confirm_kb("weap", "knife", 123),
        ]
        for k in kbs:
            assert isinstance(k, InlineKeyboardMarkup)
            for row in k.inline_keyboard:
                for b in row:
                    assert b.callback_data is None or len(b.callback_data.encode()) <= 64, b.callback_data
                    assert b.style in (None, "primary", "success", "danger"), b.style
        check(f"{len(kbs)} کیبورد ولیدیت شدن", True)
        styled = sum(1 for k in kbs for r in k.inline_keyboard for b in r if b.style)
        check("دکمه‌های رنگی فعالن", styled >= 20, f"{styled}")

    # ═══ ادمین ═══
    check("پارس ادمین‌ها", 1001 in config.ADMIN_IDS and 1003 in config.ADMIN_IDS and 1002 not in config.ADMIN_IDS,
          str(sorted(config.ADMIN_IDS)))

    # ═══ فرمت نتیجه حمله ═══
    from handlers.common import format_attack_result
    txt = format_attack_result(
        {"ok": True, "win": True, "a_roll": 30, "d_roll": 20, "amount": 5000,
         "bonus": 0.06, "halved": True, "xp": 30, "penalty": 0, "notes": []},
        "سارا",
    )
    check("متن برد جدید",
          "آخ آخ سارا شکار شد" in txt and "تو هم ۵٬۰۰۰ تی‌پوینت جایزه گرفتی" in txt
          and "بونس سگ +۶٪" in txt and "زره افسانه‌ای" in txt and "۳۰ تجربه گرفتی" in txt)

    txt_lose = format_attack_result(
        {"ok": True, "win": False, "a_roll": 5, "d_roll": 5, "amount": 0,
         "bonus": 0, "halved": False, "xp": 8, "penalty": 15, "notes": []},
        "𝑅𝒶𝓅𝒾𝓉",
    )
    check("متن باخت جدید",
          "ایبابا 𝑅𝒶𝓅𝒾𝓉 حسابت رو رسوند" in txt_lose and "۱۵ انرژی جریمه شدی" in txt_lose
          and "۸ تجربت به چوخ رفت" in txt_lose)

    # ═══ دکمه‌های قفل قرمز + افزودن به گروه ═══
    from keyboards import keyboards as kb2
    async with session_scope() as s:
        low = User(telegram_id=9001, username="low", first_name="تازه‌کار", level=1)
        s.add(low)
        await s.flush()
        weap_kb = kb2.shop_weap_kb(low, set())
        locked_styles = [b.style for row in weap_kb.inline_keyboard for b in row if b.callback_data == "noop:lock"]
        check("آیتم‌های قفل شاپ قرمزن", len(locked_styles) >= 3 and all(st == "danger" for st in locked_styles))

        dog_kb = kb2.shop_dog_kb(low, set(), 0)
        dog_locked = [b.style for row in dog_kb.inline_keyboard for b in row if b.callback_data == "noop:lock"]
        check("قفل سگ‌ها هم قرمزه", len(dog_locked) >= 3 and all(st == "danger" for st in dog_locked))

        # سگ‌های من از شاپ حذف شده
        all_shop_datas = [b.callback_data for k in (kb2.shop_sections_kb(), kb2.shop_food_kb(), dog_kb)
                          for row in k.inline_keyboard for b in row]
        check("سگ‌های من تو شاپ نیس", "menu:dogs" not in all_shop_datas)

        kb2.BOT_USERNAME = "teriaky_bot"
        mm = kb2.main_menu_kb()
        urls = [b.url for row in mm.inline_keyboard for b in row if b.url]
        check("دکمه افزودن به گروه", any("startgroup=true" in u for u in urls), str(urls))

        txk = kb2.tx_confirm_kb("weap", "knife", 424242)
        datas = [b.callback_data for row in txk.inline_keyboard for b in row]
        check("کیبورد تایید متنی owner داره", datas == ["txcf:weap:knife:424242", "txcl:424242"], str(datas))

        tak = kb2.tx_attack_kb(77, 424242)
        datas = [b.callback_data for row in tak.inline_keyboard for b in row]
        check("کیبورد تایید حمله", datas == ["txatt:77:424242", "txcl:424242"], str(datas))

    # ═══ کولدون کنده‌کاری ۳۰ ثانیه ═══
    check("کنده‌کاری ۳۰ ثانیه‌ایه", config.MINE_COOLDOWN_SECONDS == 30)

    # ═══ ایمپورت و رجیستر هندلرها ═══
    import handlers  # noqa
    from telegram.ext import Application
    app = Application.builder().token("123:test").build()
    handlers.register_handlers(app)
    total = sum(len(h) for h in app.handlers.values())
    check("همه هندلرها رجیستر شدن", total >= 40, f"{total}")

    # regex دستورهای متنی
    import re
    pats = {
        "buy": re.compile(r"^خرید[\s‌]+(.+)$"),
        "buydog": re.compile(r"^خرید[\s‌]+سگ[\s‌]+(.+)$"),
        "plant": re.compile(r"^کاشت[\s‌]+(.+)$"),
    }
    check("پترن خرید چاقو", pats["buy"].match("خرید چاقو").group(1) == "چاقو")
    check("پترن خرید سگ دوبرمن اصغر", pats["buydog"].match("خرید سگ دوبرمن اصغر").group(1) == "دوبرمن اصغر")
    check("پترن کاشت", pats["plant"].match("کاشت تریاک"))

    check("واحد پول", money(1000) == "۱٬۰۰۰ تی‌پوینت" and money_tp(1000) == "۱٬۰۰۰ TP")

    print(f"\n🎉 همه تست‌ها سبز شدن — {PASS} مورد")


asyncio.run(main())
