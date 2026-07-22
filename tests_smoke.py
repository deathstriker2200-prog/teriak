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
from models import Dog, Plot, Team, TeamDaily, User  # noqa: E402
from services import (  # noqa: E402
    backup as backup_svc,
    bank as bank_svc,
    combat,
    dogs as dog_svc,
    economy,
    farming,
    shop_svc,
    teams as team_svc,
    users,
)
from sqlalchemy import select  # noqa: E402
from handlers.common import strip_home  # noqa: E402
from utils import fa_dur, fa_num, find_by_name, money, money_tp, normalize_fa, now_utc, parse_amount  # noqa: E402

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
    check("ترتیب بذرها: ماری‌جوانا، قارچ، پیوت، تریاک، کوکائین",
          list(config.SEEDS.keys()) == ["marijuana", "gharch", "peyote", "teriak", "cocaine"],
          str(list(config.SEEDS.keys())))

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
    check("قیمت زمین افزایشیه", all(a <= b for a, b in zip(prices, prices[1:])), str(prices))

    # ── کاتالوگ جدید زمین‌ها: ۱۰۰۰/۳۰ثانیه | ۱۰٬۰۰۰/۱۵دقیقه | ۲۰٬۰۰۰/۱ساعت | ۵۰٬۰۰۰/۱۲ساعت ──
    check("سقف زمین 5 تاست", config.MAX_PLOTS == 5)
    check("زمین اول رایگانه", config.PLOT_CATALOG[1]["price"] == 0 and config.PLOT_CATALOG[1]["build_sec"] == 0)
    check("زمین دوم ۱۰۰۰ و ۳۰ ثانیه",
          economy.plot_price(1) == 1000 and economy.plot_build_seconds(1) == 30,
          f"{economy.plot_price(1)}/{economy.plot_build_seconds(1)}")
    check("زمین سوم ۱۰٬۰۰۰ و ۱۵ دقیقه",
          economy.plot_price(2) == 10000 and economy.plot_build_seconds(2) == 900)
    check("زمین چهارم ۲۰٬۰۰۰ و ۱ ساعت",
          economy.plot_price(3) == 20000 and economy.plot_build_seconds(3) == 3600)
    check("زمین پنجم ۵۰٬۰۰۰ و ۱۲ ساعت",
          economy.plot_price(4) == 50000 and economy.plot_build_seconds(4) == 43200)
    check("گیت لول زمین‌ها هر کدوم مال خودشون",
          (economy.plot_required_level(0), economy.plot_required_level(1),
           economy.plot_required_level(2), economy.plot_required_level(3),
           economy.plot_required_level(4)) == (1, 2, 4, 6, 10),
          str([economy.plot_required_level(i) for i in range(5)]))

    # ── سلاح‌ها و زره‌های جدید ──
    check("13 تا سلاح داریم", len(config.WEAPONS) == 13, str(len(config.WEAPONS)))
    guns = sum(1 for w in config.WEAPONS.values() if w.get("gun"))
    check("هشت تفنگ اضافه شده", guns >= 8, str(guns))
    check("کلاش و آرپی‌جی هست", "ak47" in config.WEAPONS and "rpg" in config.WEAPONS)
    check("8 تا زره داریم", len(config.ARMORS) == 8, str(len(config.ARMORS)))
    check("کِولار و تیتانیومی هست", "kevlar" in config.ARMORS and "titan" in config.ARMORS)
    check("شوکر از کلت ضعیف‌تر و ارزون‌تره (اسلحه قوی‌تره)",
          config.WEAPONS["shocker"]["attack"] < config.WEAPONS["colt"]["attack"]
          and config.WEAPONS["shocker"]["price"] < config.WEAPONS["colt"]["price"])
    check("ترتیب نمایش سلاح‌ها از ضعیف به قویه (شوکر قبل کلت)",
          list(config.WEAPONS.keys()).index("shocker") < list(config.WEAPONS.keys()).index("colt"))
    w_sorted = sorted(config.WEAPONS.values(), key=lambda w: w["price"])
    check("قدرت سلاح با قیمت صعودیه", all(a["attack"] < b["attack"] for a, b in zip(w_sorted, w_sorted[1:])),
          str([(w["name"], w["price"], w["attack"]) for w in w_sorted][:5]))

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
    dk, _ = dog_svc.find_dog("دوبرمن")
    check("«خرید سگ دوبرمن» نژاد رو پیدا می‌کنه", dk == "doberman")
    dk2, _ = dog_svc.find_dog("گرگ")
    check("مچ جزئی نژاد سگ", dk2 == "blackwolf")

    # ═══ فلو کاربر ═══
    async with session_scope() as s:
        u1, _ = await users.get_or_create(s, tg(1001, "ali", "علی"))
        u2, _ = await users.get_or_create(s, tg(1002, "sara", "سارا"))
        u3, _ = await users.get_or_create(s, tg(1003, "boss", "باس"))
        u3.level = 20

        # ── زمین رایگان ثبت‌نام + خرید زمین دوم ──
        free_plots = await farming.get_user_plots(s, u1.id)
        check("زمین اول موقع ثبت‌نام رایگان داده میشه", len(free_plots) == 1, str(len(free_plots)))
        check("زمین رایگان از اول ساخته شدس", free_plots[0].built_at is None)
        check("ثبت‌نام دوباره زمین دوباره نمیده",
              len(await farming.get_user_plots(s, (await users.get_or_create(s, tg(1001, "ali", "علی")))[0].id)) == 1)

        u1.cash = 100000  # شارژ حساب برای تست‌ها
        check("زمین دوم زیر لول ۲ قفله", (await farming.buy_plot(s, u1))[0] is False or u1.level >= 2)
        u1.level = 10
        ok, msg = await farming.buy_plot(s, u1)
        check("خرید زمین دوم (۱۰۰۰ تی‌پوینت)", ok and u1.cash == 99000, msg)
        plots = await farming.get_user_plots(s, u1.id)
        check("دو تا زمین شد", len(plots) == 2)
        built_plot = plots[1]
        check("زمین خریدنی داره ساخته میشه", built_plot.built_at is not None, str(built_plot.built_at))
        st, left = built_plot.current_status()
        check("وضعیت «در حال ساخت» با زمان مونده", st == "building" and 0 < left <= 30, f"{st}/{left}")
        ok, msg = await farming.plant(s, u1, built_plot, "teriak")
        check("کاشت روی زمین نیم‌ساخت رد میشه", not ok and "ساخته" in msg, msg)
        built_plot.built_at = now_utc() - timedelta(seconds=1)
        st, _ = built_plot.current_status()
        check("بعد تموم شدن ساخت استفاده میشه", st == "empty", st)

        plot = plots[0]  # زمین رایگان برای کاشت تست‌ها

        u1.cash = 3000
        ok, msg = await shop_svc.purchase(s, u1, "seed", "teriak")
        check("خرید بذر تریاک", ok and u1.cash == 3000 - config.SEEDS["teriak"]["price"])
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
        check("کولدون ۲ دقیقه برداشت جلوگیری می‌کنه", not ok and "2 دقیقه" in msg, msg)

        u1.last_harvest_at = now_utc() - timedelta(seconds=config.HARVEST_COOLDOWN_SECONDS + 5)
        ok, alert, extra = await farming.harvest_all(s, u1)
        check("بعد از کولدون برداشت میشه", ok)

        # ── گیت لول فروشگاه ──
        u1.level = 1
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

        # ── سگ‌ها (فلو دو مرحله‌ای: اول پرداخت → بعد اسم می‌فرسته) ──
        cash_before = u1.cash
        ok, msg = await shop_svc.purchase(s, u1, "dog", "doberman")
        check("پرداخت سگ و درخواست اسم", ok and "اسم" in msg, msg)
        check("پول کم شد ولی سگ هنوز ساخته نشده",
              u1.cash == cash_before - config.DOGS["doberman"]["price"]
              and u1.pending_action == "dogname" and u1.pending_value == "doberman"
              and len(await dog_svc.get_user_dogs(s, u1.id)) == 0)
        check("خرید سگ دوم قبل اسم دادن بلاکه", (await shop_svc.purchase(s, u1, "dog", "blackwolf"))[0] is False)

        ok, res = await dog_svc.finalize_dog(s, u1, "اصغر")
        check("اسم سگ بعد از پرداخت ثبت شد", ok and res == "اصغر", res)
        check("pending پاک شد", u1.pending_action is None and u1.pending_value is None)
        ok, res = await dog_svc.finalize_dog(s, u1, "تکراری")
        check("بدون pending اسم نمیشه ثبت کرد", not ok)

        # لغو خرید → پول برمی‌گرده (قبل از رسیدن به سقف ۲ سگ)
        cash_before = u1.cash
        ok, _ = await shop_svc.purchase(s, u1, "dog", "kangal")
        check("هولد کانگال", ok)
        msg = await dog_svc.cancel_pending(s, u1)
        check("لغو خرید سگ پول رو برمی‌گردونه",
              u1.cash == cash_before and u1.pending_action is None and "برگشت" in msg, msg)

        ok, msg = await shop_svc.purchase(s, u1, "dog", "blackwolf")
        ok2, res2 = await dog_svc.finalize_dog(s, u1, "شبح")
        check("گرگ سیاه با اسم شبح", ok and ok2 and res2 == "شبح")
        check("نژاد تکراری رد میشه", (await shop_svc.purchase(s, u1, "dog", "doberman"))[0] is False)
        nok, msg = await shop_svc.purchase(s, u1, "dog", "shepherd")
        check("حداکثر ۲ سگ — سومیش بلاکه", not nok and "2" in msg, msg)

        dogs = await dog_svc.get_user_dogs(s, u1.id)
        check("دو سگ ثبت شد با اسم دلخواه", {d.dog_key: d.name for d in dogs} == {"doberman": "اصغر", "blackwolf": "شبح"})
        check("پیدا کردن سگ با اسم برای «آمار اصغر»",
              dog_svc.find_my_dog(dogs, "اصغر").dog_key == "doberman"
              and dog_svc.find_my_dog(dogs, "شب").dog_key == "blackwolf"
              and dog_svc.find_my_dog(dogs, "ناشناس") is None)

        # ── قالب دقیق کارت آمار سگ ──
        from handlers import dogs as dogs_h
        dob_card = dogs_h._dog_card_text(u1, dogs[0])
        check("کارت آمار سگ قالب دقیق داره",
              all(x in dob_card for x in ["🐕 آمار", "🐾 نژاد", "⭐ لول", "✨تجربه", "💪 قدرت حمله", "🎖", "🍖 امروز"])
              and ("▰" in dob_card or "▱" in dob_card), dob_card.replace("\n", " | ")[:140])
        check("آیتم سگ‌ها اسم‌شون فقط نژاده",
              all(config.DOGS[k]["name"] == config.DOGS[k]["breed"] for k in config.DOGS),
              str([d["name"] for d in config.DOGS.values()]))
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
        check("غرامت گرگ در لول مکس ۱۰٪ه", abs(bonus - config.RARE_DOG_STEAL_MAX) < 1e-9, f"{bonus:.2%}")
        wolf.level = 2
        check("بونس گرگ با لول کمتره", abs(dog_svc.rare_steal_bonus(dogs) - config.RARE_DOG_STEAL_MAX * 2 / config.DOG_MAX_LEVEL) < 1e-9)
        wolf.level = config.DOG_MAX_LEVEL
        check("کاهش دفاع گرگ تو لول مکس ۳۰٪ه", abs(dog_svc.rare_defense_cut(dogs) - config.RARE_DOG_DEF_CUT_MAX) < 1e-9, f"{dog_svc.rare_defense_cut(dogs):.2%}")
        wolf.level = 2
        check("کاهش دفاع گرگ با لول کمتره", abs(dog_svc.rare_defense_cut(dogs) - 0.06) < 1e-9)
        check("بدون گرگ کاهش دفاع نیس", dog_svc.rare_defense_cut([]) == 0)
        check("غرامت گرگ ۱۰٪ه نه ۱۵٪", config.RARE_DOG_STEAL_MAX == 0.10)

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
        u1.energy = config.MAX_ENERGY
        u1.last_attack_at = None
        res_dc = await combat.execute_attack(s, u1, u2)
        check("گرگ سیاه دفاع طرف رو خرد می‌کنه", res_dc["defcut"] > 0, str(res_dc["defcut"]))

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

    # ═══ لول‌آپ تبریکی با جایزه (اسکناس + شارژ انرژی) ═══
    async with session_scope() as s:
        u2x = await users.get_by_tg(s, 1002)
        u2x.energy = 10
        cash_b, lvl_b = u2x.cash, u2x.level
        notes = users.add_xp(u2x, economy.xp_need(u2x.level))
        check("پیام تبریک لول‌آپ میاد", bool(notes) and "تبریک" in notes[0], notes[0][:60] if notes else "-")
        check("جایزه اسکناس لول‌آپ واریز شد",
              u2x.cash == cash_b + config.LEVEL_CASH_REWARD * u2x.level and u2x.level == lvl_b + 1,
              f"{u2x.cash - cash_b}")
        check("انرژی با لول‌آپ فول شارژ شد", u2x.energy == config.MAX_ENERGY)
        await s.commit()

    # ═══ متن دقیق کنده‌کاری (هندلر واقعی) ═══
    from handlers import mine as mine_h

    class _Msg(SimpleNamespace):
        async def reply_html(self, text, **k):
            self.calls.append(("reply", text, k))
            return self

    def _text_update(txt, uid=7701, uname="miner", fname="ماینر"):
        msg = _Msg(text=txt, calls=[], chat_id=100)
        return SimpleNamespace(
            message=msg, effective_message=msg,
            effective_user=SimpleNamespace(id=uid, username=uname, first_name=fname),
            effective_chat=SimpleNamespace(type="private"), callback_query=None,
        )

    upd = _text_update("کنده کاری")
    await mine_h.mine_cmd(upd, None)
    mine_text = upd.message.calls[-1][1]
    check("متن کنده‌کاری قالب دقیق داره",
          all(x in mine_text for x in ["⛏ کنده‌کاری", "گیرت اومد", "الان", "تی‌پوینت داری", "ارزشش رو داشت", "پول حاصل از کار خلاف بیشتره"]),
          mine_text.replace("\n", " | ")[:100])

    # ═══ هندلر pending — اسم سگ بعد از پرداخت ═══
    from handlers import pending as pending_h

    upd = _text_update("رکس", uid=7702, uname="pnd", fname="پندی")
    await pending_h.capture(upd, None)
    check("بدون pending هیچ واکنشی نیس", not upd.message.calls)

    async with session_scope() as s:
        puser, _ = await users.get_or_create(s, tg(7702, "pnd", "پندی"))
        puser.level = 15
        puser.cash = 100000
        ok, _ = await dog_svc.hold_dog(s, puser, "pitbull")
        assert ok
        await s.commit()

    upd = _text_update("رکس", uid=7702, uname="pnd", fname="پندی")
    stopped = False
    try:
        await pending_h.capture(upd, None)
    except Exception as e:
        stopped = type(e).__name__ == "ApplicationHandlerStop"
    async with session_scope() as s:
        puser = await users.get_by_tg(s, 7702)
        pdogs = await dog_svc.get_user_dogs(s, puser.id)
    check("اسم سگ با پیام بعدی ثبت شد",
          stopped and upd.message.calls and any(d.name == "رکس" for d in pdogs), str([d.name for d in pdogs]))
    check("«آمار رکس» صداش می‌زنه", dog_svc.find_my_dog(pdogs, "رکس") is not None)

    # لغو وسط راه — پول برمی‌گرده
    async with session_scope() as s:
        puser = await users.get_by_tg(s, 7702)
        await dog_svc.hold_dog(s, puser, "doberman")
        cash_after_hold = puser.cash
        await s.commit()
    upd = _text_update("لغو", uid=7702, uname="pnd", fname="پندی")
    try:
        await pending_h.capture(upd, None)
    except Exception:
        pass
    async with session_scope() as s:
        puser = await users.get_by_tg(s, 7702)
        check("لغو اسم سگ پول رو برمی‌گردونه",
              puser.pending_action is None and puser.cash == cash_after_hold + config.DOGS["doberman"]["price"],
              str(puser.cash))

    # ═══ تیم: ساخت | جوین | بیو | آمار ═══
    async with session_scope() as s:
        o, _ = await users.get_or_create(s, tg(7705, "ownx", "رهبر"))
        m1, _ = await users.get_or_create(s, tg(7706, "mm1", "ممبر۱"))
        m2, _ = await users.get_or_create(s, tg(7707, "mm2", "ممبر۲"))
        o.level = 12
        o.cash = 60000
        m1.level = 4
        m2.level = 6

        ok, msg = await team_svc.can_create_team(s, o)
        check("لول ۱۲ و پول کافی می‌تونه بسازه", ok)
        o.level = 9
        check("زیر لول ۱۰ ساخت تیم بلاکه", (await team_svc.can_create_team(s, o))[0] is False)
        o.level = 12

        ok, name = await team_svc.create_team(s, o, "فوتبالیست‌ها")
        check("ساخت تیم فوتبالیست‌ها + هزینه کم شد",
              ok and name == "فوتبالیست‌ها" and o.cash == 60000 - config.TEAM_CREATE_COST, f"{name}/{o.cash}")
        check("عضو تیم ساخت دومی بلاکه", (await team_svc.create_team(s, o, "تیم دوم"))[0] is False)
        check("اسم تکراری بلاکه (حتی با فاصله عادی)",
              (await team_svc.create_team(s, m2, "فوتبالیست ها"))[0] is False)

        check("زیر لول ۵ جوین بلاکه", (await team_svc.join_team(s, m1, "فوتبالیست‌ها"))[0] is False)
        m1.level = 5
        ok, name1 = await team_svc.join_team(s, m1, "فوتبالیست‌ها")
        check("جوین ممبر۱", ok and name1 == "فوتبالیست‌ها", str(name1))
        ok, name2 = await team_svc.join_team(s, m2, "فوتبالیست ها")
        check("جوین با فاصله عادی (نرمالایز اسم)", ok, str(name2))
        check("جوین دوباره بلاکه", (await team_svc.join_team(s, m2, "فوتبالیست‌ها"))[0] is False)

        check("بیو رو فقط رهبر می‌ذاره", (await team_svc.set_bio(s, o, "بهترین تیم محله 🏆"))[0] is True
              and (await team_svc.set_bio(s, m1, "x"))[0] is False)

        team = await team_svc.get_team_of(s, o.id)
        data = await team_svc.team_stats_data(s, team)
        check("آمار تیم: ۳ عضو و رهبر درست",
              data["count"] == 3 and data["owner_name"] == "رهبر" and team.bio == "بهترین تیم محله 🏆",
              f"{data['count']}/{data['owner_name']}")
        check("تیم تو پروفایل اسمش دیده میشه", team.name == "فوتبالیست‌ها")
        team_id = team.id
        await s.commit()

    # ═══ کوئست‌های روزانه گروهی ═══
    async with session_scope() as s:
        o = await users.get_by_tg(s, 7705)
        m1 = await users.get_by_tg(s, 7706)
        m2 = await users.get_by_tg(s, 7707)
        c1, c2, c3 = o.cash, m1.cash, m2.cash

        for i in range(24):
            r = await team_svc.record_kill(s, o if i % 2 == 0 else m1)
            assert r is None, i
        r = await team_svc.record_kill(s, m2)
        check("کوئست کشتن ۲۵ نفر با ضربه ۲۵ام کامل شد", r is not None and "کامل شد" in r, str(r)[:60])
        rw = config.TEAM_QUESTS[0]["reward"]
        check("جایزه ۳۰۰ تی‌پوینت به هر عضو رسید",
              o.cash == c1 + rw and m1.cash == c2 + rw and m2.cash == c3 + rw,
              f"{o.cash - c1}/{m1.cash - c2}/{m2.cash - c3}")
        r = await team_svc.record_kill(s, o)
        check("کوئست یک روز دوباره جایزه نمیده", r is None)

        for i in range(9):
            r = await team_svc.record_harvest(s, m2 if i % 2 else o, 1)
            assert r is None, i
        r = await team_svc.record_harvest(s, m1, 1)
        rw2 = config.TEAM_QUESTS[1]["reward"]
        check("کوئست برداشت ۱۰ محصول کامل شد", r is not None and "برداشت" in r, str(r)[:60])
        check("جایزه برداشت هم به همه رسید", m1.cash == c2 + rw + rw2 and o.cash == c1 + rw + rw2)

        team = await team_svc.get_team_of(s, o.id)
        # ۲۶ برد (۲۵ کوئستی + ۱ تست «دوباره جایزه نمیده») + ۱۰ برداشت
        expected_pts = 26 * config.TEAM_POINT_KILL + 10 * config.TEAM_POINT_HARVEST
        check("امتیاز تیم با برد و برداشت جمع شد", team.points == expected_pts, str(team.points))
        check("امتیاز هفته هم همینه (قبل ریست)", team.week_points == expected_pts)

        daily = await team_svc._daily(s, team_id)
        check("استعلام کوئست هر دو رو done نشون میده",
              all(q["done"] for q in team_svc.quests_view(daily)),
          str(team_svc.quests_view(daily)))
        await s.commit()

        # هوک واقعی execute_attack → کوئست کشتار ثبت میشه
        kills_b = (await team_svc._daily(s, team_id)).kills
        victim = await users.get_by_tg(s, 1002)
        won = False
        for _ in range(80):
            o.energy = config.MAX_ENERGY
            o.last_attack_at = None
            res = await combat.execute_attack(s, o, victim)
            assert res["ok"]
            if res["win"]:
                won = True
                break
        kills_a = (await team_svc._daily(s, team_id)).kills
        check("برد تو حمله واقعی روی کوئست تیم حساب شد", won and kills_a == kills_b + 1, f"{kills_b}→{kills_a}")
        await s.commit()

    # ═══ کنده‌کاری تیمی (استخراج — ۷۰٪ اعضا) ═══
    check("فرمول نیاز ۷۰٪ اعضا",
          [team_svc.mine_needed(m) for m in (1, 2, 3, 7, 10)] == [3, 3, 3, 5, 7],
          str([team_svc.mine_needed(m) for m in (1, 2, 3, 7, 10)]))

    async with session_scope() as s:
        solo, _ = await users.get_or_create(s, tg(7799, "solo", "سولو"))
        solo.level = 12
        solo.cash = 50000
        ok, _ = await team_svc.create_team(s, solo, "تنهایی‌ها")
        team_svc.TEAM_MINE_SESSIONS.clear()
        r = await team_svc.team_mine_join(s, solo)
        check("تیم زیر ۳ نفره نمی‌تونه استخراج کنه", r["status"] == "too_few", r["status"])
        await s.commit()

    async with session_scope() as s:
        o = await users.get_by_tg(s, 7705)
        m1 = await users.get_by_tg(s, 7706)
        m2 = await users.get_by_tg(s, 7707)
        team = await team_svc.get_team_of(s, o.id)
        bank_b = team.bank

        team_svc.TEAM_MINE_SESSIONS.clear()
        r1 = await team_svc.team_mine_join(s, o)
        check("استارت کنده‌کاری تیمی (نفر ۱ از ۳ لازم)",
              r1["status"] == "started" and r1["needed"] == 3 and r1["joined"] == 1, str(r1["status"]))
        r2 = await team_svc.team_mine_join(s, o)
        check("دوبار پیوستن همون نفر «قبلا پیوستی»", r2["status"] == "already")
        r3 = await team_svc.team_mine_join(s, m1)
        check("نفر دوم پیوست", r3["status"] == "joined" and r3["joined"] == 2)
        r4 = await team_svc.team_mine_join(s, m2)
        check("با نفر سوم تکمیل شد", r4["status"] == "completed", str(r4["status"]))
        check("جایزه رفت تو خزانه تیم",
              3 * config.TEAM_MINE_PER_MIN <= r4["reward"] <= 3 * config.TEAM_MINE_PER_MAX
              and team.bank == bank_b + r4["reward"] and r4["bank"] == team.bank,
              f"reward={r4['reward']}")
        r5 = await team_svc.team_mine_join(s, o)
        check("بعد تکمیل کولدون فعاله", r5["status"] == "cooldown" and r5["left"] > 0)
        await s.commit()

    # متن پیوستن دقیقاً مثل فرمول کاربر: «۷ نفر از ۸ نفر … ۱ نفر تا تکمیل»
    from handlers import team as team_h
    fake_res = {"team": SimpleNamespace(name="فوتبالیست‌ها"), "joined": 6, "needed": 7, "member_count": 7, "expires_at": now_utc()}
    ptxt = team_h._mine_progress_text(fake_res)
    check("متن «6 نفر از 7 نفر به کنده‌کاری پیوستند / 1 نفر تا تکمیل»",
          "6 نفر از 7 نفر به کنده‌کاری پیوستند" in ptxt and "1 نفر تا تکمیل کنده‌کاری" in ptxt, ptxt[:120])
    fake_done = {"team": SimpleNamespace(name="فوتبالیست‌ها"), "reward": 900, "bank": 2000}
    dtxt = team_h._mine_complete_text(fake_done)
    check("پیام پاداش بعد از تکمیل میاد", "کامل شد" in dtxt and "خزانه" in dtxt, dtxt[:80])

    # ═══ بانک تیم + ساختمان‌ها + امتیاز هفتگی ═══
    async with session_scope() as s:
        o = await users.get_by_tg(s, 7705)
        m1 = await users.get_by_tg(s, 7706)
        team = await team_svc.get_team_of(s, o.id)

        # هزینه ساختمان تصاعدیه
        check("هزینه ساختمان تصاعدیه",
              [team_svc.building_cost(i) for i in (1, 2, 3)] == sorted([team_svc.building_cost(i) for i in (1, 2, 3)])
              and team_svc.building_cost(1) == config.TEAM_BUILDING_BASE_COST)

        # واریز کمک مالی به بانک تیم
        m1.cash = 1000
        ok, msg = await team_svc.team_deposit(s, m1, 1200)
        check("واریز بیشتر از جیب رد میشه", not ok)
        bank_b = team.bank
        ok, msg = await team_svc.team_deposit(s, m1, 400)
        check("«تیم واریز 1200» — واریز عضو به بانک تیم", ok and team.bank == bank_b + 400 and m1.cash == 600, msg)
        ok, msg = await team_svc.team_deposit(s, m1, 0)
        check("واریز صفر رد میشه", not ok)

        # ارتقا فقط با رهبره و پولش از بانک تیم میره
        ok, msg = await team_svc.upgrade_building(s, m1, "atk")
        check("ارتقا با غیر رهبر بلاکه", not ok and "رهبر" in msg, msg)
        team.bank = 100
        ok, msg = await team_svc.upgrade_building(s, o, "atk")
        check("بانک کم ارتقا رو رد می‌کنه", not ok and "بانک" in msg, msg)
        team.bank = 30000
        bank_b = team.bank
        ok, msg = await team_svc.upgrade_building(s, o, "atk")
        check("ارتقای ساختمان حمله به لول ۱",
              ok and team.atk_bld == 1 and team.bank == bank_b - config.TEAM_BUILDING_BASE_COST, msg)
        ok, msg = await team_svc.upgrade_building(s, o, "def")
        check("ارتقای ساختمان دفاع هم کار می‌کنه", ok and team.def_bld == 1, msg)
        check("بونس ساختمان حمله",
              abs(team_svc.atk_bonus(team) - config.TEAM_ATK_BONUS_PER_LEVEL) < 1e-9)
        tb = await team_svc.top_teams_by_points(s, 5)
        check("لیدربرد بر اساس امتیاز مرتبه", tb and tb[0][0].points >= tb[-1][0].points)

        await s.commit()

    # بونس ساختمان تو نبرد واقعی اعماله (tbuff تو نتیجه)
    async with session_scope() as s:
        o = await users.get_by_tg(s, 7705)
        victim = await users.get_by_tg(s, 1002)
        o.energy = config.MAX_ENERGY
        o.last_attack_at = None
        res_t = await combat.execute_attack(s, o, victim)
        check("بونس ساختمان حمله تو نتیجه نبرد اومد", res_t["ok"] and res_t.get("tbuff", 0) > 0, str(res_t.get("tbuff")))
        await s.commit()

    # رول‌اور هفتگی: ۳ تیم اول جایزه می‌گیرن و امتیاز هفته ریست میشه
    async with session_scope() as s:
        o = await users.get_by_tg(s, 7705)
        team = await team_svc.get_team_of(s, o.id)
        team.week_points = 7777
        bank_b = team.bank
        await team_svc.meta_set(s, "week_key", "2000-W01")  # شبیه‌سازی هفته قدیمی
        winners = await team_svc.maybe_weekly_rollover(s)
        check("رول‌اور اجرا شد چون هفته عوض شده", winners is not None and len(winners) >= 1)
        check("قهرمان رتبه ۱ جایزه‌شو گرفت تو بانک تیم",
              winners[0]["rank"] == 1 and winners[0]["team"].name == "فوتبالیست‌ها"
              and team.bank == bank_b + config.TEAM_WEEKLY_PRIZES[1],
              f"{team.bank - bank_b}")
        check("امتیاز هفته ریست شد", team.week_points == 0)
        check("هفته جدید ذخیره شد", (await team_svc.meta_get(s, "week_key")) == team_svc.current_week_key())
        check("نتیجه هفته پیش ذخیره شد", "فوتبالیست‌ها" in (await team_svc.meta_get(s, "last_week_result") or ""))
        again = await team_svc.maybe_weekly_rollover(s)
        check("تو همون هفته دوباره رول‌اور نمیشه", again is None)
        await s.commit()

    # ═══ ترک / انحلال ═══
    async with session_scope() as s:
        ok, name = await team_svc.leave_team(s, await users.get_by_tg(s, 7707))
        check("ممبر ترک می‌کنه", ok and name == "فوتبالیست‌ها", str(name))
        ok, msg = await team_svc.leave_team(s, await users.get_by_tg(s, 7705))
        check("رهبر نمی‌تونه ترک کنه", not ok, msg)
        ok, name = await team_svc.disband_team(s, await users.get_by_tg(s, 7705))
        check("انحلال توسط رهبر", ok and name == "فوتبالیست‌ها")
        check("تیم دیگه وجود نداره", await team_svc.get_team_by_name(s, "فوتبالیست‌ها") is None)
        m1x = await users.get_by_tg(s, 7706)
        check("عضوها آزاد شدن", await team_svc.get_team_of(s, m1x.id) is None)
        await s.commit()

    # ═══ اسم تیم با pending (مثل فلو واقعی «ساخت تیم») ═══
    async with session_scope() as s:
        o = await users.get_by_tg(s, 7705)
        o.pending_action = "teamname"
        await s.commit()
    upd = _text_update("فوتبالیست‌ها ۲", uid=7705, uname="ownx", fname="رهبر")
    try:
        await pending_h.capture(upd, None)
    except Exception:
        pass
    async with session_scope() as s:
        t2 = await team_svc.get_team_by_name(s, "فوتبالیست‌ها ۲")
        o = await users.get_by_tg(s, 7705)
        check("اسم تیم با پیام بعدی ساخته شد", t2 is not None and o.pending_action is None, str(t2))
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
            kb.bank_kb(u1), kb.team_bld_kb(SimpleNamespace(atk_bld=1, def_bld=2), True, u1.telegram_id),
            kb.team_bld_confirm_kb("atk", u1.telegram_id),
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

    # ═══ بانک شخصی 🏦 ═══
    check("پارس مبلغ فارسی و لاتین", parse_amount("۱۲۰۰") == 1200 and parse_amount("1,200") == 1200
          and parse_amount("الکی") is None and parse_amount("0") is None)
    check("ظرفیت بانک با لول رشد می‌کنه",
          bank_svc.bank_capacity(3) == 3 * config.BANK_CAP_BASE > bank_svc.bank_capacity(1))
    check("هزینه ارتقای بانک تصاعدیه", bank_svc.bank_upgrade_price(2) > bank_svc.bank_upgrade_price(1))

    async with session_scope() as s:
        b, _ = await users.get_or_create(s, tg(7711, "bnk", "بانکدار"))
        b.cash = 10000
        b.level = 1

        ok, msg = await bank_svc.deposit(s, b, 3000)
        check("واریز به بانک", ok and b.bank_balance == 3000 and b.cash == 7000, msg)
        ok, msg = await bank_svc.deposit(s, b, 0)
        check("واریز صفر رد", not ok)
        ok, msg = await bank_svc.deposit(s, b, 99999)
        check("واریز بیشتر از جیب رد", not ok)

        ok, msg = await bank_svc.withdraw(s, b, 1000)
        check("برداشت از بانک", ok and b.bank_balance == 2000 and b.cash == 8000, msg)
        ok, msg = await bank_svc.withdraw(s, b, 99999)
        check("برداشت بیشتر از موجودی بانک رد", not ok)

        # ظرفیت لول ۱ = 25,000 — پر کردنش و رد بیشترش
        b.cash = 100000
        ok, msg = await bank_svc.deposit(s, b, 23000)
        check("تا سقف ظرفیت واریز میشه", ok and b.bank_balance == 25000, f"{b.bank_balance}")
        ok, msg = await bank_svc.deposit(s, b, 1)
        check("بیشتر از ظرفیت رد میشه", not ok and "ظرفیت" in msg or "پر" in msg, msg)

        # ارتقای بانک به لول خودت گره خورده
        ok, msg = await bank_svc.upgrade_bank(s, b)
        check("ارتقا بدون لول کافی رد (لول ۱ می‌خواد بره لول ۲)", not ok and "لول" in msg, msg)
        b.level = 3
        cash_b = b.cash
        ok, msg = await bank_svc.upgrade_bank(s, b)
        check("ارتقا با لول کافی انجام شد",
              ok and b.bank_level == 2 and b.cash == cash_b - bank_svc.bank_upgrade_price(1), msg)
        ok, msg = await bank_svc.deposit(s, b, 1)
        check("بعد ارتقا ظرفیت بیشتر شده", ok)
        await s.commit()

    # ═══ پروفایل: سگ به تعداد + بانک ═══
    from handlers import profile as profile_h
    async with session_scope() as s:
        u1 = await users.get_by_tg(s, 1001)  # ۲ سگ داره (اصغر و شبح)
        cap = await profile_h._profile_caption(s, u1)
        check("پروفایل سگ‌ها رو فقط به تعداد میگه",
              "🐕 سگ 2 عدد" in cap and "اصغر" not in cap and "شبح" not in cap, cap[:120])
        check("خط بانک تو پروفایل هست", "🏦 بانک" in cap)
        u_b = await users.get_by_tg(s, 7711)
        cap2 = await profile_h._profile_caption(s, u_b)
        check("بدون سگ: «سگ نداری»", "🐕 سگ نداری" in cap2)
        await s.commit()

    # ═══ فلو pending بانک (دکمه واریز → مبلغ با پیام بعدی) ═══
    async with session_scope() as s:
        puser = await users.get_by_tg(s, 7702)
        puser.pending_action = "bankdep"
        puser.pending_value = ""
        await s.commit()
    upd = _text_update("۳۰۰۰", uid=7702, uname="pnd", fname="پندی")
    try:
        await pending_h.capture(upd, None)
    except Exception:
        pass
    async with session_scope() as s:
        puser = await users.get_by_tg(s, 7702)
        check("مبلغ فارسی به بانک واریز شد", puser.bank_balance == 3000 and puser.pending_action is None,
              str(puser.bank_balance))
        puser.pending_action = "bankwd"
        await s.commit()
    upd = _text_update("1000", uid=7702, uname="pnd", fname="پندی")
    try:
        await pending_h.capture(upd, None)
    except Exception:
        pass
    async with session_scope() as s:
        puser = await users.get_by_tg(s, 7702)
        check("برداشت pending هم کار می‌کنه", puser.bank_balance == 2000, str(puser.bank_balance))
        # لغو اکشن بانک
        puser.pending_action = "bankdep"
        await s.commit()
    upd = _text_update("لغو", uid=7702, uname="pnd", fname="پندی")
    try:
        await pending_h.capture(upd, None)
    except Exception:
        pass
    async with session_scope() as s:
        puser = await users.get_by_tg(s, 7702)
        check("لغو اکشن بانک پاکش می‌کنه", puser.pending_action is None)
        await s.commit()

    # ═══ ادمین ═══
    check("پارس ادمین‌ها", 1001 in config.ADMIN_IDS and 1003 in config.ADMIN_IDS and 1002 not in config.ADMIN_IDS,
          str(sorted(config.ADMIN_IDS)))

    # ═══ فرمت نتیجه حمله ═══
    from handlers.common import format_attack_result
    txt = format_attack_result(
        {"ok": True, "win": True, "a_roll": 30, "d_roll": 20, "amount": 5000,
         "bonus": 0.06, "halved": True, "defcut": 0.06, "xp": 30, "penalty": 0, "notes": []},
        "سارا",
    )
    check("متن برد جدید",
          "آخ آخ سارا شکار شد" in txt and "تو هم 5,000 تی‌پوینت جایزه گرفتی" in txt
          and "غرامت +6٪" in txt and "دفاعش -6٪ خرد شد" in txt and "زره افسانه‌ای" in txt and "30 تجربه گرفتی" in txt,
          txt.replace("\n", " | ")[:200])

    txt_lose = format_attack_result(
        {"ok": True, "win": False, "a_roll": 5, "d_roll": 5, "amount": 0,
         "bonus": 0, "halved": False, "xp": 8, "penalty": 15, "notes": []},
        "𝑅𝒶𝓅𝒾𝓉",
    )
    check("متن باخت جدید",
          "ایبابا 𝑅𝒶𝓅𝒾𝓉 حسابت رو رسوند" in txt_lose and "15 انرژی جریمه شدی" in txt_lose
          and "8 تجربت به چوخ رفت" in txt_lose)

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

    # ═══ اسم دلخواه سگ ═══
    k, d, custom = dog_svc.parse_dog_query("دوبرمن")
    check("پارس فقط نژاد (اسم آیتم‌ها نژاد خالصه)", k == "doberman" and custom is None)
    k, d, custom = dog_svc.parse_dog_query("دوبرمن اصغر")
    check("«دوبرمن اصغر» الان اسم دلخواه اصغر میشه", custom == "اصغر", str(custom))
    k, d, custom = dog_svc.parse_dog_query("دوبرمن رکس")
    check("پارس نژاد + اسم دلخواه", k == "doberman" and custom == "رکس", str(custom))
    k, d, custom = dog_svc.parse_dog_query("ژرمن شپرد هاجر")
    check("پارس نژاد دوکلمه‌ای + اسم", k == "shepherd" and custom == "هاجر", str(custom))
    k, d, custom = dog_svc.parse_dog_query("کانگال")
    check("پارس فقط نژاد", k == "kangal" and custom is None)

    tx_name_kb = kb2.tx_confirm_kb("dog", "doberman", 424242, "رکس")
    datas = [b.callback_data for row in tx_name_kb.inline_keyboard for b in row]
    check("اسم سگ تو callback میره", datas[0] == "txcf:dog:doberman:424242:رکس", str(datas))
    check("طول callback اوکیه", all(len(d.encode()) <= 64 for d in datas))

    # ═══ strip_home تو گروه ═══
    class _Chat(SimpleNamespace):
        pass
    from telegram import InlineKeyboardMarkup
    fake_upd = SimpleNamespace(effective_chat=_Chat(type="group"))
    markup = InlineKeyboardMarkup([
        [kb2._btn("الف", "x"), kb2._btn("ب", "y")],
        [kb2._btn("🏠 منوی اصلی", "menu:home")],
    ])
    stripped = strip_home(fake_upd, markup)
    check("منوی اصلی تو گروه برمی‌ره", stripped is not None and all(
        b.callback_data != "menu:home" for row in stripped.inline_keyboard for b in row))
    fake_upd_pv = SimpleNamespace(effective_chat=_Chat(type="private"))
    check("تو پیوی منو می‌مونه", strip_home(fake_upd_pv, markup) is markup)

    # ═══ بک‌آپ و ری‌استور (/backup و /upload_backup) ═══
    check("بک‌آپ روی SQLite پشتیبانی میشه", backup_svc.backup_supported() and config.sqlite_path() is not None)
    async with session_scope() as s:
        n_users_before = len(list((await s.execute(select(User))).scalars()))

    snap = await backup_svc.create_snapshot()
    check("اسنپ‌شات بک‌آپ ساخته شد و سالمه", os.path.exists(snap) and backup_svc.is_valid_backup_file(snap))
    with open(snap, "rb") as f:
        snap_bytes = f.read()
    os.remove(snap)

    ok, msg = await backup_svc.restore_bytes(b"this is definitely not a sqlite db")
    check("فایل الکی رد میشه", not ok, msg)

    ok, msg = await backup_svc.restore_bytes(bytes(300))
    check("فایل خرد شده هم رد میشه", not ok)

    # یه تغییر می‌دیم بعد ری‌استور می‌کنیم — باید برگرده سر جاش
    async with session_scope() as s:
        ghost, _ = await users.get_or_create(s, tg(999999, "ghost", "روح"))
        await s.commit()
    async with session_scope() as s:
        check("روح اضافه شد", await users.get_by_tg(s, 999999) is not None)

    ok, msg = await backup_svc.restore_bytes(snap_bytes)
    check("ری‌استور بک‌آپ موفق", ok, msg)
    async with session_scope() as s:
        n_after = len(list((await s.execute(select(User))).scalars()))
        ghost_gone = (await users.get_by_tg(s, 999999)) is None
    check("اطلاعات دقیقا مطابق فایل بک‌آپ شد (روح پاک شد)",
          n_after == n_users_before and ghost_gone, f"{n_after} vs {n_users_before}")

    # ═══ رگرسیون باگ تایید خرید (فلو واقعی هندلرها) ═══
    from handlers import shop as shop_h, textcmd as textcmd_h

    class _Q(SimpleNamespace):
        async def answer(self, *a, **k):
            self.calls.append(("answer", a, k))
        async def edit_message_text(self, text, **k):
            self.calls.append(("edit", text, k))

    def _fake_update(data, uid=6001):
        q = _Q(data=data, message=SimpleNamespace(photo=None), calls=[])
        return SimpleNamespace(
            callback_query=q,
            effective_user=SimpleNamespace(id=uid, username="flow", first_name="فلو"),
            effective_chat=_Chat(type="private"),
        )

    # خرید اینلاین سلاح: فاکتور → تایید → باید جنس خورده بشه (قبلا اینجا کرش می‌کرد)
    async with session_scope() as s:
        flow, _ = await users.get_or_create(s, _fake_update("x").effective_user)
        flow.cash = 200000
        flow.level = 15
        await s.commit()

    upd = _fake_update("shop:buy:weap:pipe")
    await shop_h.buy_confirm(upd, None)
    check("فاکتور خرید اینلاین ساخته شد", any(c[0] == "edit" for c in upd.callback_query.calls))

    upd = _fake_update("cf:shop:buy:weap:pipe")
    await shop_h.buy_execute(upd, None)
    async with session_scope() as s:
        flow = await users.get_by_tg(s, 6001)
        owns = await users.get_item_keys(s, flow.id)
    check("تایید خرید اینلاین کار می‌کنه (رگرسیون)", "pipe" in owns, str(owns))

    # خرید متنی سگ با اسم دلخواه
    upd = _fake_update("txcf:dog:pitbull:6001:رکسی")
    await textcmd_h.tx_confirm_cb(upd, None)
    async with session_scope() as s:
        flow = await users.get_by_tg(s, 6001)
        flow_dogs = await dog_svc.get_user_dogs(s, flow.id)
    check("سگ با اسم دلخواه خریده شد",
          len(flow_dogs) == 1 and flow_dogs[0].name == "رکسی" and flow_dogs[0].breed == "پیتبول",
          str([d.name for d in flow_dogs]))

    # غریبه نمی‌تونه فاکتور کسی رو تایید کنه
    upd = _fake_update("txcf:weap:knife:6001", uid=9999)
    await textcmd_h.tx_confirm_cb(upd, None)
    check("تایید فاکتور غریبه بلاکه", any(c[0] == "answer" for c in upd.callback_query.calls))

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
    check("پترن خرید سگ دوبرمن", pats["buydog"].match("خرید سگ دوبرمن").group(1) == "دوبرمن")
    check("پترن کاشت", pats["plant"].match("کاشت تریاک"))

    team_pat = re.compile(r"^تیم(?:[\s‌]+(.+))?!?$")
    check("پترن «تیم فوتبالیست‌ها»", team_pat.match("تیم فوتبالیست‌ها").group(1) == "فوتبالیست‌ها")
    check("پترن «تیم» بدون اسم", team_pat.match("تیم") and team_pat.match("تیم").group(1) is None)
    check("پترن «تیم من»", team_pat.match("تیم من").group(1) == "من")
    join_pat = re.compile(r"^جوین[\s‌]+تیم[\s‌]+(.+)$")
    check("پترن «جوین تیم» با اسم چندکلمه‌ای", join_pat.match("جوین تیم فوتبالیست‌های ایران").group(1) == "فوتبالیست‌های ایران")
    amar_pat = re.compile(r"^آمار[\s‌]+(.+)$")
    check("پترن «آمار اصغر»", amar_pat.match("آمار اصغر").group(1) == "اصغر")
    tmine_pat = re.compile(r"^کنده[\s‌]*کاری[\s‌]*تیمی!?$|^استخراج[\s‌]*تیمی!?$")
    check("پترن کنده‌کاری تیمی + استخراج تیمی",
          tmine_pat.match("کنده کاری تیمی") and tmine_pat.match("استخراج تیمی") and not tmine_pat.match("کنده کاری"))
    quest_pat = re.compile(r"^کوئست[\s‌]*تیم!?$|^کوئست!?$|^استعلام[\s‌]*کوئست!?$")
    check("پترن استعلام کوئست", quest_pat.match("کوئست") and quest_pat.match("کوئست تیم") and quest_pat.match("استعلام کوئست"))
    bio_pat = re.compile(r"^(?:ست[\s‌]+)?بیو[\s‌]+تیم[\s‌]+(.+)$")
    check("پترن «ست بیو تیم»", bio_pat.match("ست بیو تیم بهترینیم").group(1) == "بهترینیم")

    # پترن‌های دستورهای جدید تیم و بانک
    tbld_pat = re.compile(r"^تیم[\s‌]+ساختمان(?:[\s‌]*ها)?!?$|^تیم[\s‌]+ساخت!?$")
    check("پترن «تیم ساختمان» و «تیم ساخت»", tbld_pat.match("تیم ساختمان") and tbld_pat.match("تیم ساخت"))
    tdep_pat = re.compile(r"^تیم[\s‌]+واریز(?:[\s‌]+(.+))?!?$")
    check("پترن «تیم واریز 1200»", tdep_pat.match("تیم واریز 1200").group(1) == "1200")
    tup_pat = re.compile(r"^تیم[\s‌]+ارتقا[\s‌]+(?:حمله|دفاع)!?$")
    check("پترن «تیم ارتقا حمله/دفاع»", tup_pat.match("تیم ارتقا حمله") and tup_pat.match("تیم ارتقا دفاع"))
    dep_pat = re.compile(r"^واریز[\s‌]+(.+)$")
    wd_pat = re.compile(r"^برداشت[\s‌]+([0-9۰-۹٠-٩,٬]+)$")
    check("پترن «واریز 1200» و «برداشت ۱۲۰۰»", dep_pat.match("واریز 1200") and wd_pat.match("برداشت ۱۲۰۰"))
    check("«برداشت محصول» به بانک نمیره", wd_pat.match("برداشت محصول") is None)
    tbank_pat = re.compile(r"^تیم[\s‌]+بانک!?$")
    check("پترن «تیم بانک»", tbank_pat.match("تیم بانک"))

    check("واحد پول لاتین", money(1000) == "1,000 تی‌پوینت" and money_tp(1000) == "1,000 TP")
    check("عدد لاتین", fa_num(12345) == "12,345" and fa_dur(169) == "2 دقیقه و 49 ثانیه")

    print(f"\n🎉 همه تست‌ها سبز شدن — {PASS} مورد")


asyncio.run(main())
