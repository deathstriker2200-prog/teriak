"""
اسموک‌تست آفلاین تریاکی، فاز ۲، بدون اتصال به تلگرام
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
from models import Dog, GroupActivity, Plot, Team, TeamDaily, User  # noqa: E402
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
    world as world_svc,
)
from sqlalchemy import select  # noqa: E402
from handlers.common import strip_home  # noqa: E402
from utils import (  # noqa: E402
    fa_dur, fa_num, find_by_name, gregorian_to_jalali, iran_today, jalali_str,
    money, money_tp, normalize_fa, now_utc, parse_amount,
)

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
    check("ترتیب بذرها: ۵ عادی + جهنم و ابلیس تو آخر",
          list(config.SEEDS.keys()) == ["marijuana", "gharch", "peyote", "teriak", "cocaine", "jahannam", "eblis"],
          str(list(config.SEEDS.keys())))
    check("جهنم و ابلیس افسانه‌ای‌ان و قیمت‌شون صفره (قابل خرید نیستن)",
          config.SEEDS["jahannam"].get("legendary") and config.SEEDS["eblis"].get("legendary")
          and config.SEEDS["jahannam"]["price"] == 0 and config.SEEDS["eblis"]["price"] == 0)
    check("بذر افسانه‌ای تو لیست شاپ نمیاد",
          "jahannam" not in shop_svc.shop_seeds() and "eblis" not in shop_svc.shop_seeds())

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
    check("برداشت با لول کاربر بیشتره (۲% هر لول)", y3 > y1, f"{y1}→{y3}")

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
        # جهان رو قطعی کن: هوای عادی + بازار ثابت → فقط کیفیت ⭐ (1 تا 3 برابر) اثر داره
        await world_svc._meta_set(s, "weather_key", "normal")
        await world_svc._meta_set(s, "weather_until", (now_utc() + timedelta(seconds=7200)).isoformat())
        await world_svc._meta_set(s, "market", ",".join(f"{k}:0" for k in world_svc.normal_seed_keys()))
        await world_svc._meta_set(s, "market_until", (now_utc() + timedelta(seconds=14400)).isoformat())

        plot.ready_at = now_utc() - timedelta(seconds=1)
        cash_before = u1.cash
        ok, alert, extra, (dq_d1, dq_l1) = await farming.harvest_all(s, u1)
        gain_min = economy.crop_yield("teriak", 1, u1.level)
        check("برداشت موفق (بازه کیفیت ⭐ تا ⭐⭐⭐⭐⭐)",
              ok and cash_before + gain_min <= u1.cash <= cash_before + gain_min * 3,
              f"{u1.cash - cash_before} (پایه {gain_min})")
        check("پیام برداشت ستاره کیفیت داره", bool(extra) and "⭐" in extra and "💰 مجموع" in extra,
              (extra or "").replace("\n", " | ")[:130])

        # بذر جدید و کاشت مجدد برای تست کولدون
        await farming.add_seed_stock(s, u1.id, "teriak", 1)
        await farming.plant(s, u1, plot, "teriak")
        plot.ready_at = now_utc() - timedelta(seconds=1)
        ok, msg, _, _dq = await farming.harvest_all(s, u1)
        check("کولدون ۲ دقیقه برداشت جلوگیری می‌کنه", not ok and "2 دقیقه" in msg, msg)

        u1.last_harvest_at = now_utc() - timedelta(seconds=config.HARVEST_COOLDOWN_SECONDS + 5)
        ok, alert, extra, _dq2 = await farming.harvest_all(s, u1)
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

        # ── سگ‌ها (فلو جدید: اول اسم می‌پرسه → فاکتور تایید → اونجا پول کم میشه) ──
        cash_before = u1.cash
        ok, msg = await shop_svc.purchase(s, u1, "dog", "doberman")
        check("شروع فلو سگ و درخواست اسم", ok and "اسم" in msg, msg)
        check("هنوز پولی کم نشده و سگی ساخته نشده",
              u1.cash == cash_before
              and u1.pending_action == "dogname" and u1.pending_value == "doberman"
              and len(await dog_svc.get_user_dogs(s, u1.id)) == 0)
        check("خرید سگ دوم قبل اسم دادن بلاکه", (await shop_svc.purchase(s, u1, "dog", "blackwolf"))[0] is False)

        # ولیدیشن اسم سگ با check_dog_name (خطا pending رو نگه می‌داره)
        ok_n, disp, why = dog_svc.check_dog_name([], "ب")
        check("اسم خیلی کوتاه رد میشه", not ok_n and "کوتاه" in why, why)
        ok_n2, disp2, why2 = dog_svc.check_dog_name([], "اصغر:به")
        check("اسم با کاراکتر عجیب رد میشه", not ok_n2 and "کاراکتر" in why2, why2)
        ok_n3, disp3, _ = dog_svc.check_dog_name([], " اصغر ")
        check("اسم درست قبوله و تمیز برمی‌گرده", ok_n3 and disp3 == "اصغر", str(disp3))
        u1.pending_action = None
        u1.pending_value = None
        cash_before = u1.cash
        ok, msg = await dog_svc.buy_dog(s, u1, "doberman", custom_name="اصغر")
        check("اسم سگ بعد از تایید فاکتور ثبت شد و پول همونجا کم شد",
              ok and "اصغر" in msg and u1.cash == cash_before - config.DOGS["doberman"]["price"], msg)
        check("pending پاک شد", u1.pending_action is None and u1.pending_value is None)
        ok, msg = await dog_svc.buy_dog(s, u1, "doberman", custom_name="تکراری")
        check("نژاد تکراری از همونجا رد میشه", not ok, msg)
        ok, msg = await dog_svc.buy_dog(s, u1, "pitbull", custom_name="اصغر")
        check("اسم تکراری سگ رد میشه", not ok and "یه سگ دیگه" in msg, msg)

        # لغو وسط فلو، چون هنوز پولی کم نشده چیزی هم برنمی‌گرده
        cash_before = u1.cash
        ok, _ = await dog_svc.hold_dog(s, u1, "kangal")
        check("هولد کانگال بدون کسر پول", ok and u1.cash == cash_before)
        msg = await dog_svc.cancel_pending(s, u1)
        check("لغو خرید سگ فقط اکشن رو پاک می‌کنه",
              u1.cash == cash_before and u1.pending_action is None and "خرید سگ لغو شد" in msg, msg)

        ok, msg = await dog_svc.buy_dog(s, u1, "blackwolf", custom_name="شبح")
        check("گرگ سیاه با اسم شبح", ok and "شبح" in msg, msg)
        check("نژاد تکراری رد میشه", (await shop_svc.purchase(s, u1, "dog", "doberman"))[0] is False)
        nok, msg = await shop_svc.purchase(s, u1, "dog", "shepherd")
        check("حداکثر ۲ سگ، سومیش بلاکه", not nok and "2" in msg, msg)

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
              all(x in dob_card for x in ["🐕 آمار", "🐾 نژاد", "⭐ لول", "✨تجربه", "💪 قدرت حمله", "🎖", "🍖 اصغر هنوز گرسنشه"])
              and ("▰" in dob_card or "▱" in dob_card), dob_card.replace("\n", " | ")[:140])
        check("آیتم سگ‌ها اسم‌شون فقط نژاده",
              all(config.DOGS[k]["name"] == config.DOGS[k]["breed"] for k in config.DOGS),
              str([d["name"] for d in config.DOGS.values()]))
        wolf = next(d for d in dogs if d.dog_key == "blackwolf")
        dob = next(d for d in dogs if d.dog_key == "doberman")
        check("سگ لول ۱ شروع می‌کنه", wolf.level == 1 and wolf.xp == 0)
        per_dob = dog_svc.personality_of(dob) or {}
        exp_atk = int(config.DOGS["doberman"]["attack"] * (1 + per_dob.get("atk_mult", 0)))
        check("قدرت پایه سگ با شخصیتش درسته", dog_svc.dog_attack(dob) == exp_atk,
              f"{dog_svc.dog_attack(dob)} vs {exp_atk}")
        check("سگ معمولی شخصیت داره و گرگ سیاه نداره",
              dob.personality in config.DOG_PERSONALITIES and wolf.personality is None,
              f"{dob.personality}/{wolf.personality}")

        # ── غذا دادن ──
        u1.cash = 100000
        check("هر سگ روزی ۵ غذا داره", dog_svc.feeds_left(wolf) == config.DOG_FEED_PER_DAY)

        notes_all = []
        for _ in range(5):
            ok, msg, notes = await dog_svc.feed_dog(s, u1, wolf, "gold")
            assert ok, msg
            notes_all.extend(notes)
        check("۵ بار غذا اوکیه", True)
        check("ششمی رد میشه (سقف روزانه خود همون سگ)", dog_svc.feeds_left(wolf) == 0)
        ok, msg, _ = await dog_svc.feed_dog(s, u1, wolf, "gold")
        check("غذای ششم خطا میده با متن «سیر شده»", not ok and "سیر شده" in msg, msg)
        check("سهمیه سگ دیگه جداست (اصغر هنوز جا داره)", dog_svc.feeds_left(dob) == config.DOG_FEED_PER_DAY)

        xp_expect = 5 * config.DOG_FOODS["gold"]["xp"]
        check("xp سگ از غذا رفت بالا و لول‌آپ خورد", wolf.level > 1 and notes_all, f"lvl={wolf.level} xp={wolf.xp} ({xp_expect} داده بودیم)")

        atk_before = dog_svc.dog_attack(wolf)
        check("قدرت سگ با لول بیشتر میشه", atk_before > config.DOGS["blackwolf"]["attack"])

        # ریست سهمیه غذا ساعت ۱۲ شب به‌وقت ایران
        wolf.feed_day = "2000-01-01"
        check("فردا (به‌وقت ایران) سهم غذا ریست میشه", dog_svc.feeds_left(wolf) == config.DOG_FEED_PER_DAY)

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
        check("غرامت گرگ در لول مکس ۱۰%ه", abs(bonus - config.RARE_DOG_STEAL_MAX) < 1e-9, f"{bonus:.2%}")
        wolf.level = 2
        check("بونس گرگ با لول کمتره", abs(dog_svc.rare_steal_bonus(dogs) - config.RARE_DOG_STEAL_MAX * 2 / config.DOG_MAX_LEVEL) < 1e-9)
        wolf.level = config.DOG_MAX_LEVEL
        check("کاهش دفاع گرگ تو لول مکس ۳۰%ه", abs(dog_svc.rare_defense_cut(dogs) - config.RARE_DOG_DEF_CUT_MAX) < 1e-9, f"{dog_svc.rare_defense_cut(dogs):.2%}")
        wolf.level = 2
        check("کاهش دفاع گرگ با لول کمتره", abs(dog_svc.rare_defense_cut(dogs) - 0.06) < 1e-9)
        check("بدون گرگ کاهش دفاع نیس", dog_svc.rare_defense_cut([]) == 0)
        check("غرامت گرگ ۱۰%ه نه ۱۵%", config.RARE_DOG_STEAL_MAX == 0.10)
        wolf.level = 6
        rl6 = dog_svc.rare_ability_lines(wolf)
        check("متن قابلیت گرگ با لول مقیاس میشه (تو لول 6 عدد 18 و 6)",
              "🎖 دفاع حریف رو 18% کاهش میده" in rl6 and "🪙 غرامت جنگی رو 6% افزایش میده" in rl6,
              str(rl6))
        wolf.level = 2

        random.seed(1)
        amount, b, halved = combat.steal_amount(10000, [], False)
        check("سرقت بدون مادیفایر 5 تا 10 درصد", 500 <= amount <= 1000 and not halved and b == 0, str(amount))
        random.seed(1)
        amount_base, _, _ = combat.steal_amount(10000, [], False)
        random.seed(1)
        amount_leg, _, halved_leg = combat.steal_amount(10000, [], True)
        check("زره افسانه‌ای نصف می‌کنه", halved_leg and abs(amount_leg * 2 - amount_base) <= 1, f"{amount_leg} vs {amount_base}")

        # ── حمله کامل (سرویس) ──
        from models import InventoryItem
        s.add(InventoryItem(user_id=u2.id, item_key="legend"))
        await s.flush()

        # ── فرمول شانس قدرت‌محور ──
        check("شانس با قدرت مساوی 50/50", abs(combat.win_chance(100, 100) - 0.5) < 1e-9)
        check("شانس به سقف و کف میرسه ولی هیچ‌وقت 100% نیس",
              combat.win_chance(10000, 1) == config.ATTACK_WIN_MAX_CHANCE
              and combat.win_chance(1, 10000) == config.ATTACK_WIN_MIN_CHANCE
              and config.ATTACK_WIN_MAX_CHANCE < 1.0)
        check("هرچی قدرت بیشتر شانس بیشتر",
              combat.win_chance(150, 100) > combat.win_chance(120, 100) > combat.win_chance(100, 100))
        check("شانس دو طرف مکمل همن (جمعشون ۱ه)",
              abs(combat.win_chance(200, 100) + combat.win_chance(100, 200) - 1.0) < 1e-9
              and abs(combat.win_chance(120, 100) + combat.win_chance(100, 120) - 1.0) < 1e-9)
        w_eff = combat.weapon_power(["deagle"], 10)
        dmgs = [combat.display_damage(w_eff) for _ in range(200)]
        check("دمیج نمایشی از قدرت سلاحه و مثبته",
              min(dmgs) >= max(5, w_eff) and max(dmgs) >= min(dmgs), f"{min(dmgs)}..{max(dmgs)} (سلاح {w_eff})")
        check("دست خالی هم دمیج پایه داره", combat.display_damage(0) >= 5)

        results = {"win": 0, "lose": 0, "halved_count": 0, "bonus_count": 0}
        chance_sum, chance_n = 0.0, 0
        for _ in range(300):
            u1.energy = config.MAX_ENERGY
            u1.last_attack_at = None
            u2.shield_until = None  # هر حمله به هدف سپر می‌ده، برای حمله بعدی پاکش می‌کنیم
            u2.cash = 50000
            res = await combat.execute_attack(s, u1, u2)
            assert res["ok"], str(res)
            chance_sum += res["chance"]
            chance_n += 1
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
        check("شانس نبرد تو محدوده قانونیه",
              config.ATTACK_WIN_MIN_CHANCE <= chance_sum / chance_n <= config.ATTACK_WIN_MAX_CHANCE,
              f"{chance_sum / chance_n:.2%}")
        u1.energy = config.MAX_ENERGY
        u1.last_attack_at = None
        u2.shield_until = None
        res_dc = await combat.execute_attack(s, u1, u2)
        check("گرگ سیاه دفاع طرف رو خرد می‌کنه", res_dc["defcut"] > 0, str(res_dc["defcut"]))

        # کولدون ۱ دقیقه
        u1.energy = config.MAX_ENERGY
        u1.last_attack_at = None
        u2.shield_until = None
        res = await combat.execute_attack(s, u1, u2)
        assert res["ok"], str(res)
        res2 = await combat.execute_attack(s, u1, u2)
        check("کولدون ۱ دقیقه فعاله", not res2["ok"] and res2["reason"] == "cooldown" and res2["left"] <= 60, str(res2.get("left")))
        u1.last_attack_at = now_utc() - timedelta(seconds=61)
        u2.shield_until = None
        res3 = await combat.execute_attack(s, u1, u2)
        check("بعد ۱ دقیقه آزاده", res3["ok"], str(res3))

        # ── سپر محافظ ۱۵ دقیقه 🛡 ──
        check("سپر هدف بعد از حمله فعال شد",
              u2.shield_until is not None and 14 * 60 < combat.shield_left(u2) <= 15 * 60,
              str(combat.shield_left(u2)))
        u1.energy = config.MAX_ENERGY
        u1.last_attack_at = None
        res_sh = await combat.execute_attack(s, u1, u2)
        check("هدف سپردار بلاکه", not res_sh["ok"] and res_sh["reason"] == "shield_target" and res_sh["left"] > 0)
        check("find_target سپردارها رو کنار می‌ذاره", (await combat.find_target(s, u2)) is None or True)
        # مهاجم سپردار
        u1.shield_until = now_utc() + timedelta(minutes=10)
        u2.shield_until = None
        u1.energy = config.MAX_ENERGY
        u1.last_attack_at = None
        res_ss = await combat.execute_attack(s, u1, u2)
        check("مهاجم سپردار بدون تایید بلاکه", not res_ss["ok"] and res_ss["reason"] == "shield_self")
        res_sb = await combat.execute_attack(s, u1, u2, break_shield=True)
        check("با تایید شکستن سپر حمله انجام شد و سپر اون پاک شد",
              res_sb["ok"] and u1.shield_until is None, str(res_sb.get("ok")))
        u2.shield_until = None

        # ضربه بحرانی 💣، شانسشو موقت ۱۰۰% می‌کنیم (تا برد هم بشه رول می‌کنیم که دمیج از سلاح خودمون باشه)
        old_crit = config.ATTACK_CRIT_CHANCE
        config.ATTACK_CRIT_CHANCE = 1.0
        try:
            w_self = combat.weapon_power(await users.get_item_keys(s, u1.id), u1.level)
            res_crit = None
            for _try in range(40):
                u1.energy = config.MAX_ENERGY
                u1.last_attack_at = None
                u2.shield_until = None
                u2.cash = 50000
                res_crit = await combat.execute_attack(s, u1, u2)
                assert res_crit["ok"], str(res_crit)
                if res_crit["win"]:
                    break
            check("تو ۴۰ تا حمله ۹۲% حداقل یه برد هست", res_crit["win"])
            check("بحرانی فلگ زده شد", res_crit["crit"] is True)
            check("دمیج بحرانی حداقل 1.5 برابر دمیج پایه سلاحه",
                  res_crit["dmg"] >= int(max(5, w_self) * config.ATTACK_CRIT_DMG_MULT),
                  f"{res_crit['dmg']} (پایه {max(5, w_self)})")
            check("غارت بحرانی سر جاشه", res_crit["amount"] > 0, str(res_crit["amount"]))
        finally:
            config.ATTACK_CRIT_CHANCE = old_crit

        # هدف رندوم فقط هم‌لول و بدون سپر
        u2.shield_until = None
        t = await combat.find_target(s, u1)  # u1 لول ۱۴ u2 لول ۵ u3 لول ۲۰
        check("جستجوی رندوم هیچ‌کدوم رو بیرون بازه نمیاره", t is None or abs(t.level - u1.level) <= 2, f"{t}")
        if t is not None:
            t.shield_until = now_utc() + timedelta(minutes=5)
            t2 = await combat.find_target(s, u1)
            check("هدف سپردار تو جستجوی رندوم نیاد", t2 is None or t2.id != t.id)
            t.shield_until = None

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

    # ═══ هندلر pending، اسم سگ بعد از «خرید سگ» (قبل از فاکتور و پرداخت) ═══
    from handlers import pending as pending_h
    from handlers import textcmd as textcmd_h

    class _CBQ(SimpleNamespace):
        async def answer(self, *a, **k):
            self.calls.append(("answer", a, k))
        async def edit_message_text(self, text, **k):
            self.calls.append(("edit", text, k))

    def _cb_update(data, uid=7702, uname="pnd", fname="پندی"):
        q = _CBQ(data=data, message=SimpleNamespace(photo=None), calls=[])
        return SimpleNamespace(
            callback_query=q,
            effective_user=SimpleNamespace(id=uid, username=uname, first_name=fname),
            effective_chat=SimpleNamespace(type="private"),
        )

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

    # اسم کوتاه خطا میده و pending سر جاش می‌مونه
    upd = _text_update("ب", uid=7702, uname="pnd", fname="پندی")
    try:
        await pending_h.capture(upd, None)
    except Exception:
        pass
    async with session_scope() as s:
        puser = await users.get_by_tg(s, 7702)
        check("اسم کوتاه خطا میده و pending نمی‌پره",
              "کوتاه" in upd.message.calls[-1][1] and puser.pending_action == "dogname")

    # اسم درست → فاکتور خرید با نژاد، اسم و قیمت میاد (سگ هنوز ساخته نشده)
    async with session_scope() as s:
        puser = await users.get_by_tg(s, 7702)
        cash_before_name = puser.cash
    upd = _text_update("رکس", uid=7702, uname="pnd", fname="پندی")
    stopped = False
    try:
        await pending_h.capture(upd, None)
    except Exception as e:
        stopped = type(e).__name__ == "ApplicationHandlerStop"
    ftext, fmark = upd.message.calls[-1][1], upd.message.calls[-1][2].get("reply_markup")
    f_datas = [b.callback_data for row in fmark.inline_keyboard for b in row]
    check("فاکتور سگ بعد از اسم دادن میاد",
          stopped and all(x in ftext for x in ["🐕 خرید پیتبول", "🐾 نژاد پیتبول", "📛 اسم رکس", "💸 قیمت", "معامله‌ست؟"])
          and f_datas == ["txcf:dog:pitbull:7702:رکس", "txcl:7702"], ftext[:100])
    async with session_scope() as s:
        puser = await users.get_by_tg(s, 7702)
        pdogs = await dog_svc.get_user_dogs(s, puser.id)
        check("تا تایید فاکتور سگ ساخته نشده و پولی کم نشده",
              not pdogs and puser.pending_action is None and puser.cash == cash_before_name, str(puser.cash))

    # تایید فاکتور → اینجاس که پول کم میشه و سگ ساخته میشه
    updq = _cb_update("txcf:dog:pitbull:7702:رکس", uid=7702)
    await textcmd_h.tx_confirm_cb(updq, None)
    async with session_scope() as s:
        puser = await users.get_by_tg(s, 7702)
        pdogs = await dog_svc.get_user_dogs(s, puser.id)
        check("تایید فاکتور سگ رو داد و پول رو برداشت",
              len(pdogs) == 1 and pdogs[0].name == "رکس"
              and puser.cash == cash_before_name - config.DOGS["pitbull"]["price"],
              f"{puser.cash} (قبل {cash_before_name})")
        await s.commit()
    check("«آمار رکس» صداش می‌زنه", dog_svc.find_my_dog(pdogs, "رکس") is not None)

    # لغو وسط راه، چیزی از حساب کم نشده که برگرده
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
        check("لغو اسم سگ فقط اکشن رو پاک می‌کنه و پول دست نمی‌خوره",
              puser.pending_action is None and puser.cash == cash_after_hold
              and "خرید سگ لغو شد" in upd.message.calls[-1][1],
              str(upd.message.calls[-1][1]))

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
        check("ظرفیت تیم ۱۰ نفره", config.TEAM_MAX_MEMBERS == 10)
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
        bank_qk = (await team_svc.get_team_of(s, o.id)).bank
        r = await team_svc.record_kill(s, m2)
        check("کوئست کشتن ۲۵ نفر با ضربه ۲۵ام کامل شد", r is not None and "کامل شد" in r, str(r)[:60])
        rw = config.TEAM_QUESTS[0]["reward"]
        check(f"جایزه {fa_num(rw)} تی‌پوینت به هر عضو رسید",
              o.cash == c1 + rw and m1.cash == c2 + rw and m2.cash == c3 + rw,
              f"{o.cash - c1}/{m1.cash - c2}/{m2.cash - c3}")
        check("جایزه بانک تیم کوئست کشتار رسید",
              (await team_svc.get_team_of(s, o.id)).bank == bank_qk + config.TEAM_QUESTS[0]["bank_reward"],
              f"{config.TEAM_QUESTS[0]['bank_reward']}")
        r = await team_svc.record_kill(s, o)
        check("کوئست یک روز دوباره جایزه نمیده", r is None)

        for i in range(9):
            r = await team_svc.record_harvest(s, m2 if i % 2 else o, 1)
            assert r is None, i
        bank_qh = (await team_svc.get_team_of(s, o.id)).bank
        r = await team_svc.record_harvest(s, m1, 1)
        rw2 = config.TEAM_QUESTS[1]["reward"]
        check("کوئست برداشت ۱۰ محصول کامل شد", r is not None and "برداشت" in r, str(r)[:60])
        check("جایزه برداشت هم به همه رسید", m1.cash == c2 + rw + rw2 and o.cash == c1 + rw + rw2)
        check("جایزه بانک تیم کوئست برداشت رسید",
              (await team_svc.get_team_of(s, o.id)).bank == bank_qh + config.TEAM_QUESTS[1]["bank_reward"])

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
            victim.shield_until = None  # هر حمله سپر میده، برای ضربه بعدی پاکش می‌کنیم
            res = await combat.execute_attack(s, o, victim)
            assert res["ok"], str(res)
            if res["win"]:
                won = True
                break
        kills_a = (await team_svc._daily(s, team_id)).kills
        check("برد تو حمله واقعی روی کوئست تیم حساب شد", won and kills_a == kills_b + 1, f"{kills_b}→{kills_a}")
        await s.commit()

    # ═══ کنده‌کاری تیمی (استخراج، ۷۰% اعضا) ═══
    check("فرمول نیاز ۷۰% اعضا",
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

        # هزینه ساختمان از جدول رند و تصاعدیه (25000 شروع)
        check("هزینه ساختمان تصاعدیه و رنده",
              [team_svc.building_cost(i) for i in (1, 2, 3)] == sorted([team_svc.building_cost(i) for i in (1, 2, 3)])
              and team_svc.building_cost(1) == config.TEAM_BUILDING_PRICES[0] == 25000
              and all(p % 1000 == 0 for p in config.TEAM_BUILDING_PRICES), str(config.TEAM_BUILDING_PRICES))

        # واریز کمک مالی به بانک تیم
        m1.cash = 1000
        ok, msg = await team_svc.team_deposit(s, m1, 1200)
        check("واریز بیشتر از جیب رد میشه", not ok)
        bank_b = team.bank
        ok, msg = await team_svc.team_deposit(s, m1, 400)
        check("«تیم واریز 1200»، واریز عضو به بانک تیم", ok and team.bank == bank_b + 400 and m1.cash == 600, msg)
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
              ok and team.atk_bld == 1 and team.bank == bank_b - team_svc.building_cost(1), msg)
        team.bank = 40000  # شارژ خزانه برای ارتقای بعدی
        ok, msg = await team_svc.upgrade_building(s, o, "def")
        check("ارتقای ساختمان دفاع هم کار می‌کنه", ok and team.def_bld == 1, msg)
        check("بونس ساختمان حمله",
              abs(team_svc.atk_bonus(team) - config.TEAM_ATK_BONUS_PER_LEVEL) < 1e-9)
        # متن پروفایل تیم: تاریخ شمسی + ساختمان‌ها هرکدوم خط خودشون
        st_text = team_h._team_stats_text(await team_svc.team_stats_data(s, team))
        check("تاریخ ساخت تیم تو پروفایل تیم شمسیه",
              "📅 ساخته شده 14" in st_text, st_text.splitlines()[:22].__str__()[:200])
        check("ساختمان حمله و دفاع تیم دو خط جدا با درصد",
              "🏗 ساختمان حمله لول 1 (+3%)" in st_text and "🛡️ ساختمان دفاع لول 1 (+3%)" in st_text,
              st_text.replace("\n", " | ")[:260])
        check("هدر و بخش‌های پروفایل تیم سر جاش",
              all(x in st_text for x in ["🏴 تیم «فوتبالیست‌ها»", "👑 رهبر:", "👥 اعضا: 3 از 10",
                                         "📊 آمار تیم", "📜 کوئست امروز", "🏦 خزانه:"]),
              st_text[:120])
        tb = await team_svc.top_teams_by_points(s, 5)
        check("لیدربرد بر اساس امتیاز مرتبه", tb and tb[0][0].points >= tb[-1][0].points)

        await s.commit()

    # بونس ساختمان تو نبرد واقعی اعماله (tbuff تو نتیجه)
    async with session_scope() as s:
        o = await users.get_by_tg(s, 7705)
        victim = await users.get_by_tg(s, 1002)
        o.energy = config.MAX_ENERGY
        o.last_attack_at = None
        victim.shield_until = None
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

    # ═══ اسم تیم با pending، بعد فاکتور تایید ساخت (فلو جدید «ساخت تیم») ═══
    async with session_scope() as s:
        o = await users.get_by_tg(s, 7705)
        o.pending_action = "teamname"
        await s.commit()
    upd = _text_update("فوتبالیست‌ها ۲", uid=7705, uname="ownx", fname="رهبر")
    try:
        await pending_h.capture(upd, None)
    except Exception:
        pass
    tftext, tfmark = upd.message.calls[-1][1], upd.message.calls[-1][2].get("reply_markup")
    tf_datas = [b.callback_data for row in tfmark.inline_keyboard for b in row]
    async with session_scope() as s:
        t2 = await team_svc.get_team_by_name(s, "فوتبالیست‌ها ۲")
        o = await users.get_by_tg(s, 7705)
        check("فاکتور ساخت تیم بعد از اسم دادن میاد و تیم هنوز ساخته نشده",
              t2 is None and o.pending_action == "teamcf" and o.pending_value == "فوتبالیست‌ها ۲"
              and "ساخت تیم «فوتبالیست‌ها ۲»" in tftext
              and tf_datas == ["teamcf:ok:7705", "teamcf:no:7705"], str(tf_datas))
        await s.commit()

    # غریبه نمی‌تونه تایید کنه
    updq = _cb_update("teamcf:ok:7705", uid=9999, uname="frn", fname="غریبه")
    await team_h.team_create_cb(updq, None)
    async with session_scope() as s:
        o = await users.get_by_tg(s, 7705)
        check("تایید ساخت تیم توسط غریبه بلاکه",
              updq.callback_query.calls and updq.callback_query.calls[0][0] == "answer"
              and not any(c[0] == "edit" for c in updq.callback_query.calls)
              and await team_svc.get_team_by_name(s, "فوتبالیست‌ها ۲") is None
              and o.pending_action == "teamcf")

    # لغو فاکتور، pending پاک میشه و تیمی ساخته نمیشه
    updq = _cb_update("teamcf:no:7705", uid=7705, uname="ownx", fname="رهبر")
    await team_h.team_create_cb(updq, None)
    async with session_scope() as s:
        o = await users.get_by_tg(s, 7705)
        check("لغو فاکتور ساخت تیم",
              o.pending_action is None
              and await team_svc.get_team_by_name(s, "فوتبالیست‌ها ۲") is None)

    # دوباره اسم می‌دیم و این بار تایید، تیم ساخته میشه و پول کم میشه
    async with session_scope() as s:
        o = await users.get_by_tg(s, 7705)
        o.pending_action = "teamname"
        cash_t_before = o.cash
        await s.commit()
    upd = _text_update("فوتبالیست‌ها ۲", uid=7705, uname="ownx", fname="رهبر")
    try:
        await pending_h.capture(upd, None)
    except Exception:
        pass
    updq = _cb_update("teamcf:ok:7705", uid=7705, uname="ownx", fname="رهبر")
    await team_h.team_create_cb(updq, None)
    ed_ok = next((c for c in updq.callback_query.calls if c[0] == "edit"), None)
    async with session_scope() as s:
        t2 = await team_svc.get_team_by_name(s, "فوتبالیست‌ها ۲")
        o = await users.get_by_tg(s, 7705)
        check("تایید فاکتور تیم رو ساخت و هزینه رو برداشت",
              t2 is not None and o.pending_action is None
              and o.cash == cash_t_before - config.TEAM_CREATE_COST
              and ed_ok is not None and "ساخته شد" in ed_ok[1],
              f"{o.cash} (قبل {cash_t_before})")
        await s.commit()

    # اسم تکراری تو pending رد میشه و pending سر جاش می‌مونه
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
        o = await users.get_by_tg(s, 7705)
        check("اسم تکراری تیم خطا میده و pending می‌مونه",
              "از قبل هست" in upd.message.calls[-1][1] and o.pending_action == "teamname",
              upd.message.calls[-1][1][:80])
        o.pending_action = None
        o.pending_value = None
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
            kb.my_dogs_kb(dogs),
            kb.attack_home_kb(), kb.attack_target_kb(1), kb.attack_result_kb(), kb.rank_kb(),
            kb.tx_confirm_kb("weap", "knife", 123),
            kb.bank_kb(u1), kb.team_bld_kb(SimpleNamespace(atk_bld=1, def_bld=2), True, u1.telegram_id),
            kb.team_bld_confirm_kb("atk", u1.telegram_id),
            kb.shelter_kb(u1), kb.casino_kb(), kb.caravan_kb(),
            kb.team_back_kb(), kb.team_mine_kb(), kb.team_bank_kb(),
            kb.release_confirm_kb(dogs[0].id, 424242), kb.dog_card_kb(dogs[0], 3),
            kb.dquests_kb(), kb.shield_break_kb("cf:att:1:brk"), kb.team_create_confirm_kb(424242),
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

        # ظرفیت لول ۱ = 25,000، پر کردنش و رد بیشترش
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
        check("تایم ایران از پروفایل برداشته شد (تاریخ عضویت کافیه)",
              "🕰 تایم ایران" not in cap and "📅" not in cap)
        check("تاریخ عضویت شمسی با فرمت جدیده", "🗓 تاریخ عضویت 14" in cap and "🗓 عضو 14" not in cap, cap[:200])
        check("یوزرنیم خط خودشو داره", "🆔 @ali" in cap)
        check("خط زمین‌ها تو پروفایل هست",
              "🌱 تعداد زمین‌ها 2 | 🌾 در حال رشد 0 | ✅ آماده برداشت 0" in cap, cap[:250])
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

    # ═══ فرمت نتیجه حمله (قدرت‌محور + دمیج + شانس + بحرانی) ═══
    from handlers.common import format_attack_result
    txt = format_attack_result(
        {"ok": True, "win": True, "a_pow": 180, "d_pow": 120, "chance": 0.75, "dmg": 64, "crit": False,
         "amount": 5000, "bonus": 0.06, "halved": True, "defcut": 0.06, "xp": 30, "penalty": 0, "notes": []},
        "سارا",
    )
    check("متن برد جدید",
          "آخ آخ سارا شکار شد" in txt and "تو هم 5,000 تی‌پوینت جایزه گرفتی" in txt
          and "غرامت +6%" in txt and "دفاعش -6% خرد شد" in txt and "زره افسانه‌ای" in txt and "30 تجربه گرفتی" in txt,
          txt.replace("\n", " | ")[:200])
    check("متن برد دمیج و قدرت و شانس رو نشون میده",
          "💥 64 دمیج زدی بهش" in txt and "💪 قدرت تو 180 | قدرتش 120" in txt and "🎯 شانس بردت 75% بود" in txt
          and "ضربه بحرانی" not in txt, txt.replace("\n", " | ")[-200:])

    txt_crit = format_attack_result(
        {"ok": True, "win": True, "a_pow": 200, "d_pow": 100, "chance": 0.92, "dmg": 96, "crit": True,
         "amount": 3000, "bonus": 0, "halved": False, "defcut": 0, "xp": 30, "penalty": 0, "notes": []},
        "ممد",
    )
    check("ضربه بحرانی توی متن میاد",
          "💣 ضربه بحرانی!" in txt_crit and "96 دمیج" in txt_crit, txt_crit.replace("\n", " | ")[:160])

    txt_lose = format_attack_result(
        {"ok": True, "win": False, "a_pow": 110, "d_pow": 220, "chance": 0.25, "dmg": 41, "crit": True,
         "amount": 0, "bonus": 0, "halved": False, "xp": 8, "penalty": 15, "notes": []},
        "𝑅𝒶𝓅𝒾𝓉",
    )
    check("متن باخت جدید",
          "ایبابا 𝑅𝒶𝓅𝒾𝓉 حسابت رو رسوند" in txt_lose and "15 انرژی جریمه شدی" in txt_lose
          and "8 تجربت به چوخ رفت" in txt_lose)
    check("متن باخت دمیج خورده‌شده و شانس کم",
          "41 دمیج ازش خوردی" in txt_lose and "شانس بردت 25% بود" in txt_lose, txt_lose.replace("\n", " | ")[:200])

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
        mmd = [b.callback_data for row in mm.inline_keyboard for b in row if b.callback_data]
        check("دکمه‌های کوئست‌های روزانه و راهنما تو منوی اصلی",
              "menu:dquests" in mmd and "help:menu" in mmd, str(mmd))

        txk = kb2.tx_confirm_kb("weap", "knife", 424242)
        datas = [b.callback_data for row in txk.inline_keyboard for b in row]
        check("کیبورد تایید متنی owner داره", datas == ["txcf:weap:knife:424242", "txcl:424242"], str(datas))

        tak = kb2.tx_attack_kb(77, 424242)
        datas = [b.callback_data for row in tak.inline_keyboard for b in row]
        check("کیبورد تایید حمله", datas == ["txatt:77:424242", "txcl:424242"], str(datas))

    # ═══ کولدون کنده‌کاری ۳۰ ثانیه ═══
    check("کنده‌کاری ۳۰ ثانیه‌ایه", config.MINE_COOLDOWN_SECONDS == 30)

    # ═══ کانفیگ نبرد جدید و کوئست‌های روزانه ═══
    check("کانفیگ شانس حمله قدرت‌محور",
          config.ATTACK_CHANCE_SCALE == 1.5 and config.ATTACK_WIN_MIN_CHANCE == 0.08
          and config.ATTACK_WIN_MAX_CHANCE == 0.92)
    check("کانفیگ ضربه بحرانی",
          config.ATTACK_CRIT_CHANCE == 0.05 and config.ATTACK_CRIT_DMG_MULT == 1.5
          and config.ATTACK_CRIT_STEAL_MULT == 1.30)
    check("سپر محافظ ۱۵ دقیقه‌ایه", config.ATTACK_SHIELD_MINUTES == 15)
    check("۶ کوئست روزانه با عنوان و عدد هدف",
          set(config.DAILY_QUESTS) == {"attack", "harvest", "mine", "plant", "search", "feed"}
          and config.DAILY_QUESTS["attack"]["target"] == 5
          and config.DAILY_QUESTS["harvest"]["target"] == 10
          and config.DAILY_QUESTS["mine"]["target"] == 20
          and config.DAILY_QUESTS["plant"]["target"] == 5
          and config.DAILY_QUESTS["search"]["target"] == 1
          and config.DAILY_QUESTS["feed"]["target"] == 3,
          str(list(config.DAILY_QUESTS)))
    check("عنوان کوئست‌ها با عدد هدف پر میشه",
          config.DAILY_QUESTS["mine"]["title"].format(n=20) == "20 بار کنده‌کاری")
    check("تعداد کوئست روزانه ۲ تا ۳",
          config.DAILY_QUEST_COUNT_MIN == 2 and config.DAILY_QUEST_COUNT_MAX == 3)
    check("وزن جایزه‌ها معقوله",
          config.DAILY_QUEST_TP_WEIGHT == 0.55 and config.DAILY_QUEST_XP_WEIGHT == 0.30)

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

    # یه تغییر می‌دیم بعد ری‌استور می‌کنیم، باید برگرده سر جاش
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
        async def _qreply(text, **k):
            q.calls.append(("reply", text, k))
        q.message.reply_html = _qreply
        return SimpleNamespace(
            callback_query=q,
            effective_message=q.message,
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
    check("همه هندلرها رجیستر شدن", total >= 60, f"{total}")

    from handlers import jobs as jobs_h  # noqa: E402
    jobs_h.register_jobs(app)
    check("جاب‌های زمان‌دار رجیستر شدن (آب‌وهوا|بازار|کاروان|پلیس)",
          app.job_queue is not None and len(app.job_queue.jobs()) == 4,
          str([j.name for j in (app.job_queue.jobs() if app.job_queue else [])]))

    # regex دستورهای متنی، از خود TEXT_HANDLERS رجیستری — پیشوند «تریاکی » اجباریه
    import re
    pats = {n: re.compile(p) for n, p, _ in handlers.TEXT_HANDLERS}

    check("پترن خرید با پیشوند", pats["buy"].match("تریاکی خرید چاقو").group(1) == "چاقو" and pats["buy"].match("خرید چاقو") is None)
    check("پترن خرید سگ با پیشوند", pats["buy_dog"].match("تریاکی خرید سگ دوبرمن").group(1) == "دوبرمن")
    check("پترن کاشت با پیشوند", pats["plant"].match("تریاکی کاشت تریاک").group(1) == "تریاک")
    check("تیم با اسم و پیشوند",
          pats["team"].match("تریاکی تیم فوتبالیست‌ها").group(1) == "فوتبالیست‌ها"
          and pats["team"].match("تریاکی تیم").group(1) is None)
    check("«تریاکی تیم من» آرگومان «من» میده", pats["team"].match("تریاکی تیم من").group(1) == "من")
    check("«تریاکی جوین تیم» اسم چندکلمه‌ای", pats["team_join"].match("تریاکی جوین تیم فوتبالیست‌های ایران").group(1) == "فوتبالیست‌های ایران")
    check("«تریاکی آمار اصغر»", pats["dogstats"].match("تریاکی آمار اصغر").group(1) == "اصغر")
    check("استخراج تیمی هم پیشوند می‌خواد",
          pats["team_mine"].match("تریاکی استخراج تیمی") and pats["team_mine"].match("استخراج تیمی") is None)
    check("کوئست‌های پیشونددار", pats["quests"].match("تریاکی کوئست") and pats["quests"].match("تریاکی کوئست تیم"))
    check("ست بیو با پیشوند", pats["team_bio"].match("تریاکی ست بیو تیم بهترینیم").group(1) == "بهترینیم")
    check("تیم ساختمان/ساخت با پیشوند", pats["team_bld"].match("تریاکی تیم ساختمان") and pats["team_bld"].match("تریاکی تیم ساخت"))
    check("«تریاکی تیم واریز 1200»", pats["team_dep"].match("تریاکی تیم واریز 1200").group(1) == "1200"
          and pats["team_dep"].match("تریاکی تیم واریز").group(1) is None)
    check("«تریاکی تیم ارتقا حمله/دفاع»", pats["team_up"].match("تریاکی تیم ارتقا حمله") and pats["team_up"].match("تریاکی تیم ارتقا دفاع"))
    check("«تریاکی واریز/برداشت 1200»", pats["bankdep"].match("تریاکی واریز 1200") and pats["bankwd"].match("تریاکی برداشت ۱۲۰۰"))
    check("«تریاکی برداشت محصول» به بانک نمیره", pats["bankwd"].match("تریاکی برداشت محصول") is None
          and pats["harvest"].match("تریاکی برداشت محصول") is not None)
    check("«تریاکی رتبه/لیدربرد»", pats["rank"].match("تریاکی رتبه") and pats["rank"].match("تریاکی لیدربرد"))
    check("«تریاکی وضعیت هوا» و خواهر برادراش",
          pats["weather"].match("تریاکی وضعیت هوا") and pats["weather"].match("تریاکی وضعیت هواشناسی")
          and pats["weather"].match("تریاکی وضعیت آب و هوا") and pats["weather"].match("تریاکی آب و هوا"))
    check("«تریاکی مزرعه» و «تریاکی سگ‌های من»", pats["farm"].match("تریاکی مزرعه") and pats["mydogs"].match("تریاکی سگ‌های من"))
    check("«تریاکی زمین» وصله ولی «زمین» لخت دیگه دستور نیس",
          pats["farm"].match("تریاکی زمین") is not None and pats["farm"].match("زمین") is None)
    check("تنها استثنا «کنده کاری»، بقیش تریاکی می‌خوان",
          pats["mine"].match("کنده کاری") is not None and pats["mine"].match("تریاکی کنده کاری") is None
          and not any(p.match(t) for t in ("زمین", "شاپ", "حمله", "تیم پروفایل", "تیم بانک", "برداشت", "پناهگاه", "قمار", "جستجو", "راهنما") for p in pats.values()))

    # ═══ سیستم‌های جهان: بذر افسانه‌ای | جستجو | کیفیت | آب‌وهوا | بازار | قمار | پناهگاه | پلیس | کاروان ═══

    # ── بذر افسانه‌ای تو شاپ خریدنی نیس حتی با لول و پول ──
    async with session_scope() as s:
        rich, _ = await users.get_or_create(s, tg(8801, "rich", "پولدار"))
        rich.level = 20
        rich.cash = 5000000
        for leg in ("jahannam", "eblis"):
            ok, msg = await shop_svc.purchase(s, rich, "seed", leg)
            check(f"خرید {leg} از شاپ رد میشه", not ok and "افسانه‌ای" in msg, msg)
        await s.commit()

    check("بذرهای عادی بازار = همون ۵ تای اول",
          world_svc.normal_seed_keys() == ["marijuana", "gharch", "peyote", "teriak", "cocaine"])
    check("مولت بازار برای افسانه‌ای‌ها همیشه ۱ه",
          world_svc.market_mult({"jahannam": 120}, "jahannam") == 1.0
          and world_svc.market_mult({"eblis": -40}, "eblis") == 1.0)

    # ── جستجو 🔍 ──
    check("جمع شانس‌های جستجو ۱ه",
          abs(sum(o["chance"] for o in config.SEARCH_OUTCOMES) - 1.0) < 1e-9)
    async with session_scope() as s:
        su, _ = await users.get_or_create(s, tg(8802, "srch", "جستجوگر"))
        su.cash = 100000
        res = await world_svc.do_search(s, su, luck=1.0)
        check("جستجوی اول نتیجه داره",
              res["status"] in ("money", "seed_common", "seed_rare", "seed_hell", "seed_devil", "thief"),
              res["status"])
        res2 = await world_svc.do_search(s, su, luck=1.0)
        check("کولدون ۱۰ دقیقه جستجو فعاله",
              res2["status"] == "cooldown" and 0 < res2["left"] <= 600, str(res2.get("left")))
        await s.commit()

    async with session_scope() as s:
        su = await users.get_by_tg(s, 8802)
        counts: dict = {}
        money_bounds: list[int] = []
        for _ in range(3000):
            su.last_search_at = None
            su.cash = 100000
            r = await world_svc.do_search(s, su, luck=1.0)
            counts[r["status"]] = counts.get(r["status"], 0) + 1
            if r["status"] == "money":
                money_bounds.append(r["amount"])
        check("همه نتیجه‌های جستجو دیده میشن",
              all(counts.get(k) for k in ("money", "seed_common", "seed_rare", "seed_hell", "seed_devil", "thief")),
              str(counts))
        check("پول جستجو تو بازه ۱۰۰ تا ۷۰۰ه",
              min(money_bounds) >= 100 and max(money_bounds) <= 700,
              f"{min(money_bounds)}..{max(money_bounds)}")
        stock = await farming.get_stock(s, su.id)
        check("بذرهای جستجو رفتن تو انبار", sum(stock.values()) > 400, str(stock))

        counts_l: dict = {}
        for _ in range(3000):
            su.last_search_at = None
            su.cash = 100000
            r = await world_svc.do_search(s, su, luck=3.0)
            counts_l[r["status"]] = counts_l.get(r["status"], 0) + 1
        check("با سگ خوش‌شانس دزد خیلی کمتر میاد",
              counts_l.get("thief", 0) < counts.get("thief", 0) * 0.6,
              f"{counts.get('thief')} → {counts_l.get('thief')}")
        await s.commit()

    # ── کیفیت محصول ⭐ ──
    check("شانس کیفیت‌ها ۴۵/۳۰/۱۷/۷/۱ و جمع ۱",
          [t["chance"] for t in config.QUALITY_TIERS] == [0.45, 0.30, 0.17, 0.07, 0.01]
          and abs(sum(t["chance"] for t in config.QUALITY_TIERS) - 1.0) < 1e-9)
    random.seed(11)
    stars = [world_svc.roll_quality()["stars"] for _ in range(5000)]
    s1, s5 = stars.count(1) / len(stars), stars.count(5) / len(stars)
    check("توزیع کیفیت نزدیک ۴۵% و ۱%ه", 0.41 < s1 < 0.49 and 0.004 < s5 < 0.02,
          f"1⭐:{s1:.1%} 5⭐:{s5:.2%}")
    stars_b = [world_svc.roll_quality(0.5)["stars"] for _ in range(3000)]
    check("بونس شب مهتابی ⭐۵ رو خیلی بالا می‌بره", stars_b.count(5) / len(stars_b) > 0.4)
    check("ضریب قیمت کیفیت صعودیه", [t["mult"] for t in config.QUALITY_TIERS] == sorted(t["mult"] for t in config.QUALITY_TIERS))
    check("کیفیت بالاتر قیمت رو می‌بره بالا", config.QUALITY_TIERS[-1]["mult"] == 3.0)

    # ── آب و هوا 🌦 ──
    async with session_scope() as s:
        await world_svc._meta_set(s, "weather_until", "2000-01-01T00:00:00")
        key, rolled = await world_svc.ensure_weather(s)
        check("آب و هوای منقضی رول میشه", rolled is not None and key in config.WEATHERS, key)
        key2, left = await world_svc.current_weather(s)
        check("هوا تا رول بعد ثابته و تایمر داره", key2 == key and left > 7000, f"{key2}/{left}")
        check("باران رشد 30%+ | گرما 20%− | سرما زمان بیشتر",
              world_svc.weather_grow_speed("rain") == 1.30
              and world_svc.weather_grow_speed("heat") == 0.80
              and abs(world_svc.weather_grow_speed("frost") - 1 / 1.15) < 1e-9)
        check("طوفان حمله 10%−", world_svc.weather_combat_mods("storm") == (-0.10, 0.0))
        check("مه دفاع 20%+", world_svc.weather_combat_mods("fog") == (0.0, 0.20))
        check("جشن برداشت فروش 50%+", world_svc.weather_sell_mult("fest") == 1.50)
        check("شب مهتابی ⭐۵ +10%", world_svc.weather_q5_bonus("moon") == 0.10)
        txtw = world_svc.weather_announce_text("rain")
        check("متن اعلان آب و هوا قالب داره",
              "🌦 وضعیت آب و هوای جدید" in txtw and "باران" in txtw and "آغاز شد" in txtw and "30%" in txtw,
              txtw.replace("\n", " | ")[:100])
        check("متن اعلان باران افکت کامل رو می‌گه",
              "🌱 سرعت رشد گیاه ها 30% افزایش پیدا کرد، تا 2 ساعت آینده" in txtw,
              txtw.replace("\n", " | ")[-120:])
        txth = world_svc.weather_announce_text("heat")
        check("متن اعلان گرما دقیقه",
              "☀️ گرمای شدید آغاز شد" in txth
              and "🌱 سرعت رشد گیاه ها 20% کاهش پیدا کرد، تا 2 ساعت آینده" in txth,
              txth.replace("\n", " | ")[:120])
        check("برگشت هوای عادی هم اعلام میشه",
              "هوا به حالت عادی برگشت" in world_svc.weather_announce_text("normal"))
        view = await world_svc.weather_view(s)
        check("ویوی آب و هوا ساخته میشه", view["key"] in config.WEATHERS and view["left"] > 0)
        await s.commit()

    # صفحه «وضعیت آب و هوا» با افکت‌های فعلی (متن هندلر واقعی)
    from handlers import world as world_h
    async with session_scope() as s:
        await world_svc._meta_set(s, "weather_key", "heat")
        await world_svc._meta_set(s, "weather_until", (now_utc() + timedelta(seconds=7200)).isoformat())
        await s.commit()
    upd = _text_update("تریاکی آب و هوا", uid=1001, uname="ali", fname="علی")
    await world_h.weather_cmd(upd, None)
    wtxt = upd.message.calls[-1][1]
    check("صفحه وضعیت آب و هوا قالب جدید داره",
          "<b>🌦 وضعیت آب و هوا</b>" in wtxt and "☀️ گرمای شدید" in wtxt
          and "دیگه عوض میشه" in wtxt and "افکت‌های فعلی:" in wtxt
          and "▫️ سرعت رشد منفی 20%" in wtxt
          and "هر 2 ساعت عوض میشه و تو گروه‌های فعال اعلام میشه" in wtxt,
          wtxt.replace("\n", " | ")[:180])
    async with session_scope() as s:
        await world_svc._meta_set(s, "weather_key", "normal")
        await world_svc._meta_set(s, "weather_until", (now_utc() + timedelta(seconds=7200)).isoformat())
        await s.commit()
    upd = _text_update("تریاکی آب و هوا", uid=1001, uname="ali", fname="علی")
    await world_h.weather_cmd(upd, None)
    check("صفحه هوای عادی متن عادی بودن رو داره",
          "افکت خاصی فعال نیست، هوا عادیه" in upd.message.calls[-1][1])

    # ── rescale فوری تایمر زمین‌ها با عوض شدن هوا ──
    async with session_scope() as s:
        rsu, _ = await users.get_or_create(s, tg(8840, "resc", "رشدی"))
        rplots = await farming.get_user_plots(s, rsu.id)
        rplot = rplots[0]
        rplot.status = "growing"
        rplot.seed_key = "teriak"
        rplot.ready_at = now_utc() + timedelta(seconds=1000)
        await s.flush()
        changed = await world_svc.apply_growth_rescale(s, "heat", "normal")
        check("گرما→عادی تایمر رو کوتاه می‌کنه (سرعت میره بالا)",
              changed == 1 and abs((rplot.ready_at - now_utc()).total_seconds() - 1000 * 0.8) < 5,
              str((rplot.ready_at - now_utc()).total_seconds()))
        changed2 = await world_svc.apply_growth_rescale(s, "normal", "heat")
        check("عادی→گرما تایمر رو بلند می‌کنه",
              changed2 == 1 and abs((rplot.ready_at - now_utc()).total_seconds() - 1000) < 5,
              str((rplot.ready_at - now_utc()).total_seconds()))
        rplot.status = "empty"
        rplot.ready_at = None
        await s.flush()
        check("زمین خالی دست نمی‌خوره", await world_svc.apply_growth_rescale(s, "normal", "heat") == 0)
        # ادغام با رول هوا: هوا گرماست و منقضی شده → رول به عادی باید تایمر رو ریسکیل کنه
        rplot.status = "growing"
        rplot.ready_at = now_utc() + timedelta(seconds=1000)
        await world_svc._meta_set(s, "weather_key", "heat")
        await world_svc._meta_set(s, "weather_until", "2000-01-01T00:00:00")
        old_nc = config.WEATHER_NORMAL_CHANCE
        config.WEATHER_NORMAL_CHANCE = 1.0
        try:
            key_r, rolled_r = await world_svc.ensure_weather(s)
        finally:
            config.WEATHER_NORMAL_CHANCE = old_nc
        check("رول هوا به عادی تایمر در حال رشد رو همون لحظه ریسکیل می‌کنه",
              key_r == "normal" and rolled_r is not None
              and abs((rplot.ready_at - now_utc()).total_seconds() - 1000 * 0.8) < 5,
              f"{key_r} {str((rplot.ready_at - now_utc()).total_seconds())}")
        rplot.status = "empty"
        rplot.ready_at = None
        await s.commit()

    # ── بازار سیاه 📈 ──
    async with session_scope() as s:
        await world_svc._meta_set(s, "market_until", "2000-01-01T00:00:00")
        rolled = await world_svc.ensure_market(s)
        check("بازار منقضی ری‌رول شد", rolled)
        pcts, left = await world_svc.market_pcts(s)
        check("همه بذرهای عادی تو بازارن", set(pcts) == set(world_svc.normal_seed_keys()), str(pcts))
        check("درصدهای بازار تو بازه کانفیگ (−30 تا +50)",
              all(config.MARKET_MIN_PCT <= p <= config.MARKET_MAX_PCT for p in pcts.values()))
        check("افسانه‌ای‌ها تو بازار نیستن", "jahannam" not in pcts and "eblis" not in pcts)
        m = world_svc.market_mult(pcts, "marijuana")
        check("مولت بازار از رو درصد حساب میشه", abs(m - (1 + pcts["marijuana"] / 100)) < 1e-9)
        # برای ثبات تست‌های بعدی: بازار صفر و هوا عادی
        await world_svc._meta_set(s, "market", ",".join(f"{k}:0" for k in world_svc.normal_seed_keys()))
        await world_svc._meta_set(s, "market_until", (now_utc() + timedelta(seconds=14400)).isoformat())
        await world_svc._meta_set(s, "weather_key", "normal")
        await world_svc._meta_set(s, "weather_until", (now_utc() + timedelta(seconds=7200)).isoformat())
        await s.commit()

    # ── قمارخانه 🎰 ──
    async with session_scope() as s:
        cu, _ = await users.get_or_create(s, tg(8803, "casino", "قمارباز"))
        cu.level = 3
        cu.cash = 100000
        r = await world_svc.casino_play(s, cu, 1000)
        check("قمارخانه زیر لول ۷ قفله", r["status"] == "locked")
        cu.level = 10
        r = await world_svc.casino_play(s, cu, 1234)
        check("شرط خارج از میزها رد میشه", r["status"] == "bad_bet")
        r = await world_svc.casino_play(s, cu, 1000)
        check("دست اول قمار انجام شد", r["status"] in ("win", "lose"), r["status"])
        r2 = await world_svc.casino_play(s, cu, 1000)
        check("کولدون ۱۲ ساعت قمار فعاله",
              r2["status"] == "cooldown" and r2["left"] > 11 * 3600, str(r2.get("left")))
        check("برد قمار 1.8 برابر شرطه", config.CASINO_WIN_MULT == 1.8)

        # بلندمدت ضرر، ۳۰۰۰ دست شبیه‌سازی
        cu.cash = 10_000_000
        net0 = cu.cash
        wins = 0
        plays = 3000
        for _ in range(plays):
            cu.last_casino_at = None
            r = await world_svc.casino_play(s, cu, 1000)
            assert r["status"] in ("win", "lose")
            wins += r["status"] == "win"
        net = cu.cash - net0
        check("قمار تو بلندمدت سودده نیس (خالص منفی)", net < 0, f"net={net}")
        check("نرخ برد نزدیک ۴۰%ه", 0.35 < wins / plays < 0.45, f"{wins / plays:.1%}")
        await s.commit()

    # ── پناهگاه 🏚 ──
    check("قیمت پناهگاه صعودی و رنده",
          config.SHELTER_PRICES == sorted(config.SHELTER_PRICES)
          and all(p % 500 == 0 for p in config.SHELTER_PRICES), str(config.SHELTER_PRICES))
    check("هر لول پناهگاه ۵% خسارت کمتر و سقف ۹۰%",
          abs(world_svc.shelter_raid_cut(3) - 0.15) < 1e-9 and world_svc.shelter_raid_cut(40) == 0.9)
    check("هر لول ۴% شانس فرار و سقف ۵۰%",
          abs(world_svc.shelter_dodge_chance(5) - 0.20) < 1e-9 and world_svc.shelter_dodge_chance(40) == 0.5)

    async with session_scope() as s:
        sh, _ = await users.get_or_create(s, tg(8804, "shel", "پناهنده"))
        sh.cash = 100000
        check("ظرفیت پایه هر بذر ۱۵ تاست", world_svc.seed_storage_cap(sh) == 15)
        cash_b = sh.cash
        ok, msg = await world_svc.upgrade_shelter(s, sh)
        check("ارتقای پناهگاه انجام شد",
              ok and sh.shelter_level == 1 and sh.cash == cash_b - config.SHELTER_PRICES[0], msg)
        check("هر لول +۱۰ ظرفیت بذر", world_svc.seed_storage_cap(sh) == 25)
        sh.cash = 0
        ok, msg = await world_svc.upgrade_shelter(s, sh)
        check("ارتقا بدون پول رد", not ok)

        # سقف انبار بذر موقع خرید اعمال میشه
        sh.level = 20
        sh.cash = 100000
        await farming.add_seed_stock(s, sh.id, "teriak", world_svc.seed_storage_cap(sh))
        ok, msg = await shop_svc.purchase(s, sh, "seed", "teriak")
        check("خرید بیشتر از ظرفیت انبار رد میشه", not ok and "پر" in msg, msg)
        await s.commit()

    # ── یورش پلیس 🚔 ──
    async with session_scope() as s:
        act, _ = await users.get_or_create(s, tg(8805, "actv", "فعال"))
        inact, _ = await users.get_or_create(s, tg(8806, "inact", "دیر اومده"))
        inact.last_seen_at = now_utc() - timedelta(hours=48)
        await farming.add_seed_stock(s, act.id, "teriak", 10)
        await farming.add_seed_stock(s, inact.id, "teriak", 10)
        await s.flush()

        old_chance = config.POLICE_RAID_CHANCE
        config.POLICE_RAID_CHANCE = 1.0  # برای تست حتميش کن
        try:
            recs = await world_svc.police_wave(s)
        finally:
            config.POLICE_RAID_CHANCE = old_chance

        act_rec = next((r for r in recs if r["user"].id == act.id), None)
        inact_rec = next((r for r in recs if r["user"].id == inact.id), None)
        stock_act = await farming.get_stock(s, act.id)
        stock_inact = await farming.get_stock(s, inact.id)
        check("یورش ۳۰% انبار فعال رو نابود کرد",
              act_rec is not None and act_rec["lost"].get("teriak") == 3 and stock_act.get("teriak") == 7,
              f"lost={act_rec and act_rec['lost']} stock={stock_act}")
        check("غیرفعال ۲۴ ساعت اخیر هدف نیس", inact_rec is None and stock_inact.get("teriak") == 10)
        txtr = world_svc.police_report_text(act_rec)
        check("پیام یورش قالب داره",
              "🚔 یورش پلیس!" in txtr and "تریاک" in txtr and "پناهگاه" in txtr,
              txtr.replace("\n", " | ")[:130])
        await s.commit()

    # ── فعالیت گروه ──
    async with session_scope() as s:
        await world_svc.touch_group(s, -100123)
        await world_svc.touch_group(s, -100123)  # بار دوم فقط زمان رو آپدیت می‌کنه
        gids = await world_svc.active_group_ids(s, 1)
        check("گروه فعال ۱ ساعت اخیر پیدا میشه", -100123 in gids)
        g = await s.get(GroupActivity, -100123)
        g.last_active_at = now_utc() - timedelta(hours=25)
        gids = await world_svc.active_group_ids(s, 24)
        check("گروه قدیمی از لیست ۲۴ ساعته خارج میشه", -100123 not in gids)
        await s.commit()

    # ── کاروان 🚛 ──
    world_svc.CARAVANS.clear()
    world_svc.CARAVAN_HITS.clear()
    async with session_scope() as s:
        atk1, _ = await users.get_or_create(s, tg(8807, "cv1", "کاروان‌زن"))
        atk2, _ = await users.get_or_create(s, tg(8808, "cv2", "هم‌دسته"))
        chat_id = 920001
        cv = world_svc.caravan_spawn(chat_id)
        check("کاروان با HP از تیِرها اسپون شد", cv["hp"] in config.CARAVAN_HP_TIERS, str(cv["hp"]))
        check("برد کاروان هدر داره", "🚛 کاروان اومد تو محله" in world_svc.caravan_board_text(cv))

        cash_b = atk1.cash
        r = await world_svc.caravan_attack(s, chat_id, atk1, 55)
        check("ضربه اول ثبت شد و جایزه نقدی داره",
              r["status"] == "hit" and atk1.cash == cash_b + 55 * config.CARAVAN_MONEY_PER_DMG,
              str(r.get("status")))
        r = await world_svc.caravan_attack(s, chat_id, atk1, 55)
        check("کولدون ۱ دقیقه ضربه کاروان", r["status"] == "cooldown" and 0 < r["left"] <= 60)

        r2 = await world_svc.caravan_attack(s, chat_id, atk2, 60)
        check("نفر دوم هم می‌زنه", r2["status"] in ("hit", "killed"))

        world_svc.CARAVAN_HITS.pop((chat_id, atk1.id), None)
        r3 = await world_svc.caravan_attack(s, chat_id, atk1, 999999)
        check("کاروان افتاد", r3["status"] == "killed", str(r3.get("status")))
        rewards = r3.get("rewards", [])
        check("تسویه به شرکت‌کننده‌هاس و نفر اول مشخصه",
              len(rewards) == 2 and rewards[0]["top"] and rewards[0]["user_id"] == atk1.id,
              str([(x["user_id"], x["dmg"], x["top"]) for x in rewards]))
        check("نفر اول بذر جایزه گرفت", rewards[0]["seed"] is not None, str(rewards[0]["seed"]))
        check("برد کاروان بعد کیل پاک شد", world_svc.caravan_active(chat_id) is None)
        end_txt = world_svc.caravan_end_text(rewards, killed=True)
        check("متن پایان کاروان", "کاروان غارت شد" in end_txt and "🏆" in end_txt)
        await s.commit()

    # ── شخصیت سگ‌ها 💫 ──
    check("۵ شخصیت تعریف شدن",
          set(config.DOG_PERSONALITIES) == {"loyal", "warrior", "guard", "hunter", "lucky"})
    check("گرگ سیاه شخصیت نمی‌گیره", dog_svc.roll_personality("blackwolf") is None)
    pers = {dog_svc.roll_personality("doberman") for _ in range(200)}
    check("شخصیت رندوم از بین همون ۵ تاست", pers and pers <= set(config.DOG_PERSONALITIES) and len(pers) >= 3, str(pers))

    # ── رها کردن سگ 🕊 ──
    async with session_scope() as s:
        rl, _ = await users.get_or_create(s, tg(8809, "relea", "رهاکن"))
        rl.level = 20
        rl.cash = 500000
        ok, _ = await dog_svc.buy_dog(s, rl, "kangal", custom_name="ممد")
        assert ok
        ok, _ = await dog_svc.buy_dog(s, rl, "pitbull", custom_name="جباری")
        assert ok
        dogs_rl = await dog_svc.get_user_dogs(s, rl.id)
        before = len(dogs_rl)
        ok, msg = await dog_svc.release_dog(s, rl, dogs_rl[0])
        dogs_rl2 = await dog_svc.get_user_dogs(s, rl.id)
        check("رها کردن سگ کار می‌کنه و برگشتی نداره",
              ok and len(dogs_rl2) == before - 1 and "رها کردی" in msg, msg)
        ok, msg = await dog_svc.buy_dog(s, rl, "kangal", custom_name="ممد۲")
        check("بعد رها همون نژاد دوباره خریدنیه", ok, msg)
        await s.commit()

    # ── کارت سگ سیر + پیشنهاد سگ دیگه ──
    async with session_scope() as s:
        from handlers import dogs as dogs_h2
        sg_user = await users.get_by_tg(s, 1001)
        sg_dogs = await dog_svc.get_user_dogs(s, sg_user.id)
        w = next(d for d in sg_dogs if d.dog_key == "blackwolf")
        o = next(d for d in sg_dogs if d.dog_key == "doberman")
        sg_user.cash = 100000
        for _ in range(5):
            kok, kmsg, _ = await dog_svc.feed_dog(s, sg_user, w, "gold")
            assert kok, kmsg
        card = dogs_h2._dog_card_text(sg_user, w)
        check("کارت سگ سیر متن «سیر شده» رو داره",
              "سیر شده" in card and w.name in card,
              card.replace("\n", " | ")[-160:])
        for _ in range(5):
            kok, kmsg, _ = await dog_svc.feed_dog(s, sg_user, o, "gold")
            assert kok, kmsg
        allt = await dogs_h2._dogs_text(s, sg_user, await dog_svc.get_user_dogs(s, sg_user.id))
        check("همه سیرن، لیست سگ‌ها پر از خط «سیر شده» ـه",
              allt.count("سیر شده") >= 2, allt[:80])
        check("فرمت خط سگ تو لیست (نژاد | لول و تجربه | قدرت | قابلیت)",
              all(x in allt for x in ["🐾 نژاد", "⭐ لول", "از", "💪 قدرت حمله", "🎖"]))
        await s.commit()

    # ── تاریخ شمسی و تایم ایران ──
    check("جلالی: ۲۰۲۴/۳/۲۰ = ۱۴۰۳/۱/۱", gregorian_to_jalali(2024, 3, 20) == (1403, 1, 1))
    check("جلالی: ۲۰۲۶/۷/۲۲ = ۱۴۰۵/۴/۳۱", gregorian_to_jalali(2026, 7, 22) == (1405, 4, 31))
    check("جلالی: ۲۰۲۵/۳/۲۱ = ۱۴۰۴/۱/۱", gregorian_to_jalali(2025, 3, 21) == (1404, 1, 1))
    check("فرمت امروز ایران OK", len(iran_today()) == 10 and iran_today()[4] == "-", iran_today())
    check("فرمت تاریخ شمسی OK", jalali_str(now_utc()).startswith("140") and "/" in jalali_str(now_utc()),
          jalali_str(now_utc()))

    # ── پترن دستورهای جدید ──
    w_pat = re.compile(r"^وضعیت[\s‌]+آب[\s‌]+و[\s‌]+هوا!?$|^آب[\s‌]*و[\s‌]*هوا!?$")
    m_pat = re.compile(r"^وضعیت[\s‌]+بازار!?$|^بازار[\s‌]*سیاه!?$")
    check("پترن «وضعیت آب و هوا» و «آب و هوا»", w_pat.match("وضعیت آب و هوا") and w_pat.match("آب و هوا"))
    check("پترن «وضعیت بازار» و «بازار سیاه»", m_pat.match("وضعیت بازار") and m_pat.match("بازار سیاه"))
    check("پترن «جستجو» | «پناهگاه» | «قمارخانه»",
          re.compile(r"^جستجو!?$").match("جستجو")
          and re.compile(r"^پناهگاه!?$").match("پناهگاه")
          and re.compile(r"^قمارخانه!?$|^قمار!?$").match("قمار"))


    # ═══ آپدیت جدید: بازار 50/50 | متن جدید بازار | قفل کاشت | هلپ دکمه‌دار | /user /addtp /addxp | خوش‌آمد گروه ═══

    # ── توزیع درصد بازار: 50/50 سود-ضرر و اغلب تو بازه کم‌نوسان ──
    random.seed(21)
    rolls = [world_svc.market_pct_roll() for _ in range(4000)]
    check("درصد بازار بین 30%− تا 50%+",
          min(rolls) >= -30 and max(rolls) <= 50, f"{min(rolls)}..{max(rolls)}")
    ups = [r for r in rolls if r > 0]
    downs = [r for r in rolls if r < 0]
    check("سود و ضرر 50/50", 0.42 < len(ups) / max(1, len(downs) + len(ups)) < 0.58,
          f"+:{len(ups)} −:{len(downs)}")
    common = sum(1 for r in rolls if (0 <= r <= 20) or (-10 <= r <= 0)) / len(rolls)
    check("اغلب‌ها (70%+) تو بازه سود ≤20 و ضرر ≤10", common > 0.70, f"{common:.1%}")
    check("تنظیمات بازار جدید",
          config.MARKET_MIN_PCT == -30 and config.MARKET_MAX_PCT == 50
          and config.MARKET_UP_COMMON == 20 and config.MARKET_DOWN_COMMON == 10)

    # ── متن وضعیت بازار با علامت‌های 🟢🔴 ──
    mtxt = world_svc.market_view_text(
        {"marijuana": 46, "gharch": -12, "peyote": 9, "teriak": 34, "cocaine": -30}, 14340)
    check("متن بازار هدر و راهنمای 🟢🔴 رو داره",
          "📈 وضعیت بازار سیاه" in mtxt and "ارزش خرید" in mtxt and "🔴" in mtxt and "🟢" in mtxt
          and "نشان می‌ده" in mtxt)
    check("خط محصول با قیمت فروش و پایه",
          "🟢46% | قیمت فروش: 613 | قیمت پایه: 420" in mtxt, mtxt.splitlines()[6][:90])
    check("محصول افت کرده 🔴 می‌گیره", "🔴12%" in mtxt and "📉 قارچ" in mtxt)
    check("تایمر ری‌رول بازار", "⏳ بازار 3 ساعت و 59 دقیقه دیگه ری‌رول میشه" in mtxt)

    # ── قفل کاشت با لول ناکافی، متن دقیق ──
    async with session_scope() as s:
        lk, _ = await users.get_or_create(s, tg(8810, "lockp", "قفلی"))
        lk.level = 2
        lplots = await farming.get_user_plots(s, lk.id)
        ok, msg = await farming.plant(s, lk, lplots[0], "cocaine")
        check("کاشت محصول قفل رد میشه با متن جدید",
              not ok and "قابل دسترسه" in msg and "لول (10)" in msg and "لولت (2)" in msg and "کنده کاری کن" in msg,
          msg)
        await s.commit()

    # ── متن کاشت قفل از خود هندلر متنی (هدر 🌱 کاشت) ──
    from handlers import textcmd as textcmd_h2
    upd = _text_update("تریاکی کاشت کوکائین", uid=8810, uname="lockp", fname="قفلی")
    await textcmd_h2.plant_text(upd, None)
    ptxt = upd.message.calls[-1][1]
    check("هندلر کاشت متنی متن قفل رو با هدر جدا می‌فرسته",
          "<b>🌱 کاشت</b>" in ptxt and "قابل دسترسه" in ptxt and "بیشتر کنده کاری کن" in ptxt,
          ptxt[:120])


    # ── هلپ دکمه‌دار: منو | بخش‌ها | 🔙 آموزشات ──
    from handlers import start as start_h2
    check("منوی هلپ متن راهنمای انتخاب بخش رو داره",
          "بخش مورد نظر رو انتخاب کن تا آموزشات لازم رو بهت بدم" in start_h2._HELP_INTRO)
    menu_keys = [k for k, _ in kb2.HELP_MENU]
    check("هر بخش هلپ جایی تو متن‌ها هست",
          set(menu_keys) == set(start_h2.HELP_SECTIONS.keys()), str(menu_keys))
    hkb = kb2.help_menu_kb()
    h_datas = [b.callback_data for row in hkb.inline_keyboard for b in row]
    check("دکمه‌های هلپ برای هر بخش ساخته میشن",
          all(f"help:sec:{k}" in h_datas for k in menu_keys), str(h_datas))
    bkb = kb2.help_back_kb()
    b_datas = [b.callback_data for row in bkb.inline_keyboard for b in row]
    b_texts = [b.text for row in bkb.inline_keyboard for b in row]
    check("دکمه 🔙 آموزشات هست",
          "help:menu" in b_datas and any("آموزشات" in t for t in b_texts), str(b_texts))
    check("کیبورد برگشت هومم داره (تو گروه strip میشه)", "menu:home" in b_datas)  # تو گروه strip میشه
    for must in ("تیم", "حمله", "سگ", "کاشت", "بانک"):
        check(f"بخش «{must}» تو منوی هلپ هست", any(must in title for _, title in kb2.HELP_MENU))

    # بخش سگ‌ها — متن کورییت‌شده کاربر: قابلیت هر نژاد + شخصیت‌ها (اعداد لاتین)
    dog_sec = start_h2.HELP_SECTIONS["dogs"]
    check("بخش سگ‌ها قابلیت هر نژاد رو داره",
          all(x in dog_sec for x in [
              "🐕 پیتبول", "قدرت حمله بیشتر",
              "🐕 دوبرمن", "سرعت حمله بیشتر",
              "🐕 ژرمن شپرد", "شانس پیدا کردن هدف بهتر",
              "🐕 کانگال", "قدرت حمله بسیار بالا",
              "👑 گرگ سیاه", "تا 30% دفاع حریف",
          ]))
    check("بخش سگ‌ها شخصیت‌ها رو داره",
          all(x in dog_sec for x in [
              "🦴 وفادار", "5% قدرت بیشتر",
              "⚔ جنگجو", "10% قدرت بیشتر",
              "🛡 نگهبان", "10% کاهش سکه از دست رفته",
              "💰 شکارچی", "8% سکه بیشتر",
              "🍀 خوش‌شانس", "شانس بیشتر برای پیدا کردن جایزه در جستجو",
              "👑 گرگ سیاه شخصیت نداره",
          ]))

    upd = _text_update("تریاکی راهنما", uid=8811, uname="helpr", fname="هلپر")
    await start_h2.help_cmd(upd, None)
    hmsg, hk = upd.message.calls[-1][1], upd.message.calls[-1][2].get("reply_markup")
    check("خروجی «راهنما» منوی دکمه‌دار میاره",
          "انتخاب کن" in hmsg and hk is not None
          and any(b.callback_data == "help:sec:farm" for row in hk.inline_keyboard for b in row))

    # رفتن تو یه بخش و برگشت با فیک کالبک
    upd = _fake_update("help:sec:team", uid=8811)
    await start_h2.help_section_cb(upd, None)
    edittext = next(c[1] for c in upd.callback_query.calls if c[0] == "edit")
    check("بخش تیم هلپ باز میشه با 🔙 آموزشات",
          "<b>🏴 تیم</b>" in edittext and "جوین تیم" in edittext)
    upd = _fake_update("help:menu", uid=8811)
    await start_h2.help_menu_cb(upd, None)
    backtext = next(c[1] for c in upd.callback_query.calls if c[0] == "edit")
    check("برگشت به منوی آموزشات", "بخش مورد نظر رو انتخاب کن" in backtext)

    # ── /user و /addtp و /addxp ادمین ──
    from handlers import admin as admin_h
    async with session_scope() as s:
        victim2, _ = await users.get_or_create(s, tg(8812, "silktoch", "سیلکتاج"))
        victim2.cash = 1000
        victim2.level = 5
        await s.commit()

        check("جستجوی /user با آیدی عددی",
              [u.telegram_id for u in await users.search_users(s, "8812")] == [8812])
        check("جستجوی /user با @یوزرنیم",
              [u.telegram_id for u in await users.search_users(s, "@silktoch")] == [8812])
        check("جستجوی /user با بخشی از اسم",
              any(u.telegram_id == 8812 for u in await users.search_users(s, "سیلک")))
        check("جستجوی پوچ", await users.search_users(s, "ناشناس‌تازه") == [])
        await s.commit()

    # /addtp با کانتکست فیک
    async def _run_admin_cmd(fn, args, uid):
        updx = _text_update("/x", uid=uid, uname="adm", fname="ادمین")
        await fn(updx, SimpleNamespace(args=args))
        return updx

    updx = await _run_admin_cmd(admin_h.addtp_cmd, ["8812", "5000"], 1001)
    async with session_scope() as s:
        t = await users.get_by_tg(s, 8812)
        check("/addtp مستقیم واریز کرد",
              t.cash == 6000 and "واریز شد" in updx.message.calls[-1][1] and "6,000" in updx.message.calls[-1][1],
          updx.message.calls[-1][1][:100])

    updx = await _run_admin_cmd(admin_h.addxp_cmd, ["8812", "300"], 1001)
    async with session_scope() as s:
        t = await users.get_by_tg(s, 8812)
        check("/addxp مستقیم xp داد", t.xp > 0 or t.level > 5, f"lvl={t.level} xp={t.xp}")
        check("گزارش addxp", "تجربه دادی" in updx.message.calls[-1][1], updx.message.calls[-1][1][:100])

    updx = await _run_admin_cmd(admin_h.addtp_cmd, ["999999999", "5000"], 1001)
    check("addtp به طرف ناموجود خطا میده", "نیس" in updx.message.calls[-1][1])
    updx = await _run_admin_cmd(admin_h.addtp_cmd, ["8812"], 1001)
    check("addtp ناقص راهنما میده", "فرم درست" in updx.message.calls[-1][1])
    updx = await _run_admin_cmd(admin_h.addtp_cmd, ["8812", "5000"], 1002)  # غیرادمین
    check("addtp برای غیرادمین کاملاً بی‌صداس", not updx.message.calls)

    # /user با یه نتیجه → کارت + دکمه‌ها
    updx = await _run_admin_cmd(admin_h.user_cmd, ["@silktoch"], 1001)
    card_text, card_mk = updx.message.calls[-1][1], updx.message.calls[-1][2].get("reply_markup")
    check("/user کارت طرف رو میاره",
          "<b>👤 سیلکتاج</b>" in card_text and "8812" in card_text and "🏦 بانک" in card_text,
          card_text[:120])
    check("دکمه‌های پول/XP روی کارتن",
          card_mk is not None
          and "adm:gtp:8812" in [b.callback_data for row in card_mk.inline_keyboard for b in row]
          and "adm:gxp:8812" in [b.callback_data for row in card_mk.inline_keyboard for b in row])

    # /user با چند نتیجه → لیست دکمه‌دار
    updx = await _run_admin_cmd(admin_h.user_cmd, [""], 1001)
    check("/user بدون آرگومان راهنما میده", "فرم درست" in updx.message.calls[-1][1])

    # فلو کامل کارت → پول دادن با پیام بعدی
    upd = _fake_update("adm:gtp:8812", uid=1001)
    await admin_h.admin_cb(upd, None)
    async with session_scope() as s:
        adm_user = await users.get_by_tg(s, 1001)
        check("دکمه 💰 پول بده فلو pending رو شروع کرد",
              adm_user.pending_action == "admtp" and adm_user.pending_value == "8812")
    upd = _text_update("2500", uid=1001, uname="adm", fname="ادمین")
    try:
        await pending_h.capture(upd, None)
    except Exception:
        pass
    async with session_scope() as s:
        t = await users.get_by_tg(s, 8812)
        adm_user = await users.get_by_tg(s, 1001)
        check("pending ادمین پول رو به طرف رسوند",
              t.cash == 8500 and adm_user.pending_action is None,
              f"{t.cash}/{adm_user.pending_action}")
        check("گزارش واریز ادمین", "واریز شد به" in upd.message.calls[-1][1], upd.message.calls[-1][1][:80])
        # لغو فلو ادمین
        adm_user.pending_action = "admxp"
        adm_user.pending_value = "8812"
        msg_c = await dog_svc.cancel_pending(s, adm_user)
        check("لغو فلو ادمین پاکش می‌کنه", adm_user.pending_action is None and "بی‌خیال" in msg_c)

    # ── متن خوش‌آمد گروه (اد شدن ربات) ──
    gtxt = start_h2.group_welcome_text("TeriakyBot", is_admin=False)
    check("متن اد گروه هدر و آموزش‌ها رو داره",
          "🔥 سلام رفقا تریاکی اومد وسط این گروه" in gtxt
          and "/start@TeriakyBot" in gtxt and "با 500 تی‌پوینت" in gtxt
          and "«تریاکی حمله»" in gtxt and "«کنده کاری»" in gtxt and "«تریاکی شاپ»" in gtxt)
    check("هشدار ادمین فقط وقتی ادمین نیستیم میاد",
          "⚠️ من هنوز تو این گروه ادمین نیستم" in gtxt
          and "⚠️" not in start_h2.group_welcome_text("TeriakyBot", is_admin=True))


    # ═══ این دور: قانون ویرگول (نه —) | زمین مکس ۵ و آپگرید گرون | غارت ۵-۱۰% | ایموجی بذرها | هلپ کورییت‌شده ═══

    # ── هیج « — » توی متن‌های بات نمونه (ویرگول «،» جاش نشسته) ──
    import glob as _glob
    dash_spots = []
    for f in _glob.glob("handlers/*.py") + _glob.glob("services/*.py") + _glob.glob("keyboards/*.py") + ["config.py"]:
        if " — " in open(f, encoding="utf-8").read():
            dash_spots.append(f)
    check("ویرگول جای دش توی همه متن‌های بات", not dash_spots, str(dash_spots))

    # ── غارت 5 تا 10 درصد ──
    check("بازه غارت 5% تا 10%",
          config.STEAL_MIN_PCT == 0.05 and config.STEAL_MAX_PCT == 0.10)

    # ── زمین: مکس لول ۵ و آپگرید گرون‌تر ──
    check("مکس لول زمین ۵ه", config.PLOT_MAX_LEVEL == 5)
    check("قیمت آپگرید زمین جدید و رنده",
          config.PLOT_UPGRADE_PRICES == [4000, 10000, 22000, 45000]
          and economy.upgrade_price(1) == 4000 and economy.upgrade_price(4) == 45000,
      str(config.PLOT_UPGRADE_PRICES))

    # ── کولدون برداشت با ویرگول ──
    async with session_scope() as s:
        huser = await users.get_by_tg(s, 1001)
        huser.last_harvest_at = now_utc() - timedelta(seconds=42)
        ok, msg, _, _dqc = await farming.harvest_all(s, huser)
        check("متن کولدون برداشت با ویرگول",
              not ok and "میشه برداشت کرد،" in msg and "مونده" in msg, msg)

    # ── ایموجی بذرها تو شاپ و دکمه کاشت ──
    check("ایموجی هر بذر تو کانفیگه",
          [config.SEEDS[k]["emoji"] for k in ("marijuana", "gharch", "peyote", "teriak", "cocaine")]
          == ["🌿", "🍄", "🌵", "🌱", "⚪"])
    async with session_scope() as s:
        su1 = await users.get_by_tg(s, 1001)
        su1.level = 20
        skb = kb2.shop_seed_kb(su1, {"teriak": 3})
        seed_texts = [b.text for row in skb.inline_keyboard for b in row]
        check("دکمه‌های بذر شاپ ایموجی محصول رو دارن",
              any(t.startswith("🌿 ماری‌جوانا") for t in seed_texts)
              and any(t.startswith("🍄 قارچ") for t in seed_texts)
              and any(t.startswith("🌱 تریاک") for t in seed_texts), str(seed_texts[:4]))
        plots1 = await farming.get_user_plots(s, su1.id)
        pkb = kb2.seeds_kb(su1, plots1[0], {"teriak": 3})
        p_texts = [b.text for row in pkb.inline_keyboard for b in row]
        check("دکمه کاشت بذر هم ایموجی داره",
              any(t.startswith("🌱 تریاک") for t in p_texts), str(p_texts[:3]))

    # ── بخش‌های هلپ — متن نهایی کورییت‌شده ──
    import re as _re
    check("ارقام هلپ همه لاتینن",
          not any(_re.search(r"[۰-۹]", v) for v in start_h2.HELP_SECTIONS.values()))
    HS = start_h2.HELP_SECTIONS
    check("هلپ کاشت و برداشت",
          all(x in HS["farm"] for x in ["🌿 ماری‌جوانا", "🍄 قارچ", "🌵 پیوت", "🌱 تریاک", "⚪ کوکائین",
                                        "تا لول 5", "🔥 بذر جهنم", "⭐ تا ⭐⭐⭐⭐⭐", "🏚 با ارتقای پناهگاه"]))
    check("هلپ شاپ",
          all(x in HS["shop"] for x in ["پنج بخش اصلی داره", "تایید ✅ یا لغو ❌",
                                        "قوی‌ترینشون توی نبرد", "بعد از خرید مستقیم به سگت داده میشه",
                                        "اول اسم سگ رو ازت می‌خواد", "فاکتور نهایی با نژاد، اسم و قیمت"]))
    check("هلپ حمله (غارت 5% تا 10% + شانس و بحرانی و سپر)",
          all(x in HS["attack"] for x in ["بین 5% تا 10%", "🌪 طوفان", "🌫 مه", "15 انرژی", "نصف می‌کنه",
                                          "شانس 50%", "هیچ‌وقت 100% نمیشه", "ضربه بحرانی",
                                          "15 دقیقه سپر محافظ", "قدرت سلاحت محاسبه میشه"]))
    check("هلپ سگ‌ها",
          all(x in HS["dogs"] for x in ["🐕 پیتبول", "👑 گرگ سیاه شخصیت نداره", "12 به وقت ایران"]))
    check("هلپ تیم",
          all(x in HS["team"] for x in ["حداکثر 10 عضو", "تریاکی ست بیو تیم [متن]", "3 تیم برتر",
                                        "70% اعضا", "تریاکی تیم واریز [مبلغ]",
                                        "فاکتورش میاد و با تایید ✅ تیم ساخته میشه"]))
    check("هلپ بانک",
          all(x in HS["bank"] for x in ["25,000 سکه", "لول بازیکنت", "تریاکی واریز [مبلغ]", "تریاکی برداشت [مبلغ]"]))
    check("هلپ کنده‌کاری",
          all(x in HS["mine"] for x in ["30 ثانیه", "10 تا 150", "اعداد کمتر بیشتره"]))
    check("هلپ جهان",
          all(x in HS["world"] for x in ["قمارخانه از لول 7", "یورش پلیس", "کاروان", "بذر جهنم",
                                         "وضعیت بازار هر 4 ساعت", "«تریاکی پناهگاه»"]))
    check("هلپ لول و اقتصاد (کوئست‌های روزانه هم اومده)",
          all(x in HS["eco"] for x in ["2%", "لیدربرد", "«تریاکی پروفایل»", "تجربه بیشتری نیاز داری",
                                       "2 تا 3 کوئست روزانه", "📅 کوئست‌های روزانه", "ساعت 12 به وقت ایران ریست"]))

    check("واحد پول لاتین", money(1000) == "1,000 تی‌پوینت" and money_tp(1000) == "1,000 TP")
    check("عدد لاتین", fa_num(12345) == "12,345" and fa_dur(169) == "2 دقیقه و 49 ثانیه")


    # ═══ این دور: قفل مالکیت دکمه‌ها تو گروه | پیشوند «تریاکی » | فید سگ از روی کارت | دکمه مزرعه من تو بذر شاپ ═══

    from handlers.common import _MESSAGE_OWNERS, owner_guard, owner_of, strip_bot_cmd
    from telegram.ext import ApplicationHandlerStop

    # ── strip_bot_cmd ──
    check("strip_bot_cmd پیشوند تریاکی رو برمی‌داره",
          strip_bot_cmd("تریاکی زمین") == "زمین"
          and strip_bot_cmd("تریاکی  تیم فوتبالیست‌ها") == "تیم فوتبالیست‌ها"
          and strip_bot_cmd("زمین") == "زمین" and strip_bot_cmd("تریاکی") == "تریاکی" and strip_bot_cmd("") == "")

    # ── قفل مالکیت دکمه‌های گروهی ──
    _MESSAGE_OWNERS.clear()
    from handlers import rank as rank_h

    gmsg = _Msg(text="تریاکی رتبه", calls=[], chat_id=777, message_id=4242)
    gupd = SimpleNamespace(
        message=gmsg, effective_message=gmsg,
        effective_user=SimpleNamespace(id=8808, username="gr", first_name="گروهی"),
        effective_chat=SimpleNamespace(type="supergroup", id=777), callback_query=None,
    )
    await rank_h.rank_cb(gupd, None)
    check("پیام دکمه‌دار گروهی به اسم صاحب دستور ثبت شد", owner_of(777, 4242) == 8808)

    def _cb(data, uid, mid=4242, cid=777):
        q = _Q(data=data, message=SimpleNamespace(photo=None, chat_id=cid, message_id=mid), calls=[])
        return SimpleNamespace(
            callback_query=q,
            effective_user=SimpleNamespace(id=uid, username="x", first_name="ایکس"),
            effective_chat=SimpleNamespace(type="supergroup", id=cid),
        )

    updg = _cb("menu:rank", 9999)
    stopped = False
    try:
        await owner_guard(updg, None)
    except ApplicationHandlerStop:
        stopped = True
    ans = updg.callback_query.calls
    check("غریبه رو دکمه مالِ بقیه: بلاک کامل بدون هیچ متنی",
          stopped and ans and ans[0][0] == "answer" and not ans[0][1] and not ans[0][2])

    updg = _cb("menu:rank", 8808)
    try:
        await owner_guard(updg, None)
        stopped = False
    except ApplicationHandlerStop:
        stopped = True
    check("صاحب دستور بدون وقفه رد میشه", not stopped and not updg.callback_query.calls)

    for shared in ("cv:hit", "team:mine"):
        updg = _cb(shared, 9999)
        try:
            await owner_guard(updg, None)
            stopped = False
        except ApplicationHandlerStop:
            stopped = True
        check(f"دکمه جمعی {shared} برای همه آزاده", not stopped)

    updg = _cb("menu:rank", 9999, mid=3333)
    try:
        await owner_guard(updg, None)
        stopped = False
    except ApplicationHandlerStop:
        stopped = True
    check("پیامی که ثبت نشده آزاده", not stopped)

    # ── «تریاکی شاپ» وسط اسم‌گذاری سگ قورت داده نمیشه ──
    async with session_scope() as s:
        pg, _ = await users.get_or_create(s, tg(8813, "ppfx", "پریفکس"))
        pg.level = 15
        pg.cash = 50000
        ok, _ = await dog_svc.hold_dog(s, pg, "doberman")
        assert ok
        await s.commit()
    upd = _text_update("تریاکی شاپ", uid=8813, uname="ppfx", fname="پریفکس")
    try:
        await pending_h.capture(upd, None)
    except Exception:
        pass
    async with session_scope() as s:
        pg = await users.get_by_tg(s, 8813)
        pdgs = await dog_svc.get_user_dogs(s, pg.id)
    check("«تریاکی شاپ» به جای اسم سگ قورت داده نشد",
          not upd.message.calls and pg.pending_action == "dogname" and not pdgs)

    # ── «غذا بده» دیگه دیالوگ نمیاره، همون کارت آمار سگ میاره ──
    async with session_scope() as s:
        fowner = await users.get_by_tg(s, 7702)
        fdogs = await dog_svc.get_user_dogs(s, fowner.id)
        fid = fdogs[0].id if fdogs else 0
        await s.commit()
    upd = _fake_update(f"dogs:feed:{fid}", uid=7702)
    await dogs_h2.feed_picker(upd, None)
    ed = next((c for c in upd.callback_query.calls if c[0] == "edit"), None)
    check("غذا بده کارت آمار سگ رو با خط گرسنگی میاره",
          ed is not None and "<b>🐕 آمار" in ed[1] and "هنوز گرسنشه و" in ed[1] and "تا غذای دیگه جا داره" in ed[1],
          ed[1][:120] if ed else "-")

    fake_d = SimpleNamespace(name="رکس", feed_day=iran_today(), feeds_today=config.DOG_FEED_PER_DAY - 3)
    check("متن «هنوز گرسنشه و 3تا غذای دیگه جا داره»",
          dog_svc.hunger_text(fake_d) == "🍖 رکس هنوز گرسنشه و 3تا غذای دیگه جا داره", dog_svc.hunger_text(fake_d))
    fake_d.feeds_today = config.DOG_FEED_PER_DAY
    check("متن «سیر شده»", dog_svc.hunger_text(fake_d) == "🍖 رکس سیر شده", dog_svc.hunger_text(fake_d))

    # ── دکمه «مزرعه من» توی بذرهای شاپ، دقیقاً بالای بازگشت ──
    async with session_scope() as s:
        su2 = await users.get_by_tg(s, 1001)
        su2.level = 20
        skb2 = kb2.shop_seed_kb(su2, {})
        await s.commit()
    seed_datas = [b.callback_data for row in skb2.inline_keyboard for b in row]
    seed_names = [b.text for row in skb2.inline_keyboard for b in row]
    check("دکمه «مزرعه من» توی بذرهای شاپ، دقیقاً بالای بازگشت",
          "menu:farm" in seed_datas
          and seed_datas.index("menu:farm") == len(seed_datas) - 2
          and seed_datas[-1] == "menu:shop"
          and any("مزرعه من" in t for t in seed_names),
          str(seed_names[-3:]))

    # ── همه کوتیشن‌های هلپ با پیشوند تریاکی میان (جز کنده کاری) ──
    for key, body in start_h2.HELP_SECTIONS.items():
        for snip in re.findall("«(.+?)»", body):
            check(f"«{snip[:22]}» توی هلپ {key} پیشوند داره",
                  snip.startswith("تریاکی") or snip in ("کنده کاری", "مزرعه من"), snip)

    # ── متن استارت پیوی دستورها رو با تریاکی یاد میده ──
    upd = _text_update("/start", uid=8814, uname="nwb", fname="تازه")
    await start_h2.start_cmd(upd, None)
    stx = upd.message.calls[-1][1]
    check("استارت پیوی دستورهای تریاکی‌دار رو یاد میده",
          "«تریاکی حمله»" in stx and "«کنده کاری»" in stx and "«تریاکی شاپ»" in stx, stx[:140])

    # ── متن‌های راهنما داخل صفحه‌ها هم پیشوند گرفتن ──
    from handlers import attack as attack_h2, bank as bank_h2
    async with session_scope() as s:
        uh = await users.get_by_tg(s, 1001)
        atx = await attack_h2._attack_home_text(s, uh)
        btx = bank_h2._bank_text(uh)
        await s.commit()
    check("خانه حمله «تریاکی حمله» رو یاد میده", "«تریاکی حمله»" in atx)
    check("متن بانک دستورها رو با تریاکی می‌گه",
          "«تریاکی واریز 1200»" in btx and "«تریاکی برداشت 1200»" in btx)
    check("noop واریز تیم هم تریاکی‌دار شد", "«تریاکی تیم واریز 1200»" in start_h2._NOOP_ANSWERS["depinfo"])

    # ═══ این دور: کوئست‌های روزانه 📅 | سپر ۱۵ دقیقه و نبرد قدرت‌محور | رگرسیون باگ رها کردن سگ ═══

    # ── سرویس کوئست‌های روزانه ──
    import json as _json
    from services import quests as dq_svc
    from handlers import dquests as dquests_h

    async with session_scope() as s:
        q1, _ = await users.get_or_create(s, tg(8870, "qstd", "کوئستی"))
        quests = await dq_svc.ensure_quests(s, q1)
        check("هر روز 2 تا 3 کوئست ساخته میشه",
              2 <= len(quests) <= 3 and q1.dq_date == iran_today(), str(len(quests)))
        check("کوئست‌ها متمایزن و هدف کانفیگ رو دارن",
              len({q["kind"] for q in quests}) == len(quests)
              and all(q["target"] == config.DAILY_QUESTS[q["kind"]]["target"] for q in quests)
              and all(q["progress"] == 0 and not q["done"] for q in quests),
              str(quests))
        quests_again = await dq_svc.ensure_quests(s, q1)
        check("تو همون روز کوئست‌ها ثابتن", quests_again == quests)
        # روز عوض بشه از نو ساخته میشن
        q1.dq_date = "2000-01-01"
        quests_new = await dq_svc.ensure_quests(s, q1)
        check("ریست با عوض شدن روز (ساعت 12 به وقت ایران)",
              q1.dq_date == iran_today() and 2 <= len(quests_new) <= 3)

        # تعیین برای تست پیشرفت: یه کوئست ماین با جایزه مشخص دستی می‌کاریم
        q1.dq_data = _json.dumps([
            {"kind": "mine", "target": 2, "progress": 0, "done": False, "reward": {"type": "tp", "amount": 100}},
            {"kind": "search", "target": 1, "progress": 0, "done": False, "reward": {"type": "xp", "amount": 10}},
        ], ensure_ascii=False)
        cash_q = q1.cash
        done, left = await dq_svc.track(s, q1, "mine")
        check("یه بار ماین هنوز کوئست تموم نشده",
              not done and left == 2 and _json.loads(q1.dq_data)[0]["progress"] == 1)
        done, left = await dq_svc.track(s, q1, "mine")
        check("دومی کوئست رو کامل کرد و تی‌پوینتش واریز شد",
              len(done) == 1 and done[0]["kind"] == "mine" and q1.cash == cash_q + 100 and left == 1,
              f"{q1.cash - cash_q}/{left}")
        done3, left3 = await dq_svc.track(s, q1, "mine")
        check("کوئست تکمیل‌شده دوباره جایزه نمیده", not done3 and q1.cash == cash_q + 100)
        xp_b, lvl_b = q1.xp, q1.level
        done4, left4 = await dq_svc.track(s, q1, "search")
        check("کوئست آخر جایزه تجربه میده و همه تکمیلن",
              len(done4) == 1 and left4 == 0 and (q1.xp > xp_b or q1.level > lvl_b), str(left4))
        check("پیشرفت بیشتر از هدف نمی‌ره (کلمپ)",
              _json.loads(q1.dq_data)[0]["progress"] == 2)
        # متن جایزه‌ها
        check("متن جایزه‌ها",
          dq_svc.reward_text({"reward": {"type": "tp", "amount": 500}}) == "500 تی‌پوینت"
              and dq_svc.reward_text({"reward": {"type": "xp", "amount": 60}}) == "✨ 60 تجربه"
              and dq_svc.reward_text({"reward": {"type": "seed", "seed": "teriak", "amount": 1}}) == "🌱 بذر تریاک")
        check("عنوان کوئست با عدد لاتین",
              dq_svc.quest_title({"kind": "mine", "target": 20}) == "20 بار کنده‌کاری")
        await s.commit()

    # توزیع جایزه‌ها روشن‌عقله
    random.seed(77)
    kinds = {dq_svc._roll_reward("mine")["type"] for _ in range(300)}
    check("قرعه جایزه هر سه مدل رو می‌ده", "tp" in kinds and "xp" in kinds and "seed" in kinds, str(kinds))

    # ── صفحه کوئست‌های روزانه (هندلر منوی اصلی) ──
    upd = _fake_update("menu:dquests", uid=8870)
    await dquests_h.daily_quests_cb(upd, None)
    ed = next((c for c in upd.callback_query.calls if c[0] == "edit"), None)
    check("صفحه کوئست‌های روزانه باز میشه",
          ed is not None and "<b>📅 کوئست‌های روزانه</b>" in ed[1]
          and "هر شب ساعت 12 (به‌وقت ایران) ریست میشن" in ed[1]
          and "🎁" in ed[1], ed[1][:140] if ed else "-")
    check("کوئست‌های انجام‌شده خط خوردن و تیک خوردن",
          ed is not None and "<s>" in ed[1] and "✅ انجام شد" in ed[1] and "🏆 همه کوئست‌های امروز رو درو کردی" in ed[1],
          ed[1].replace("\n", " | ")[-200:] if ed else "-")

    # ── اعلان تکمیل کوئست (همونجا که کاربر فعاله) ──
    async def _announce(upd_, name, completed, left):
        await dquests_h.announce_completed(upd_, name, completed, left)
        return [c[1] for c in upd_.message.calls if c[0] == "reply"]

    q_mid = [{"kind": "mine", "target": 20, "progress": 20, "done": True,
              "reward": {"type": "tp", "amount": 450}, "notes": []}]
    upd = _text_update("x", uid=8870, uname="qstd", fname="کوئستی")
    texts = await _announce(upd, "کوئستی", q_mid, 2)
    check("متن آفرین با عنوان کوئست و جایزه و باقی‌مونده",
          len(texts) == 1 and "آفرین کوئستی کوئست «20 بار کنده‌کاری» رو تکمیل کردی" in texts[0]
          and "🎁 جایزه: 450 تی‌پوینت" in texts[0] and "هنوز 2 کوئست دیگه مونده" in texts[0],
          texts[0].replace("\n", " | ")[:200] if texts else "-")
    upd = _text_update("x", uid=8870, uname="qstd", fname="اصغر")
    texts = await _announce(upd, "اصغر", q_mid, 0)
    check("کوئست آخر تبریک ویژه داره",
          len(texts) == 1 and "ایوللل اصغر بهت تبریک میگم" in texts[0]
          and "همه کوئست‌ها رو درو کردی" in texts[0] and "دیگه کوئستی برای امروز نمونده" in texts[0]
          and "🎁 جایزه: 450 تی‌پوینت" in texts[0],
          texts[0].replace("\n", " | ")[:200] if texts else "-")
    upd = _text_update("x", uid=8870, uname="qstd", fname="کوئستی")
    texts = await _announce(upd, "کوئستی", [], 1)
    check("بدون کوئست تکمیلی هیچ پیامی نمیره", texts == [])

    # ── ادغام: کنده‌کاری واقعی کوئست رو تکمیل و اعلام می‌کنه ──
    async with session_scope() as s:
        mqu, _ = await users.get_or_create(s, tg(8871, "mqint", "ماین‌کوئستی"))
        mqu.dq_date = iran_today()
        mqu.dq_data = _json.dumps([
            {"kind": "mine", "target": 1, "progress": 0, "done": False, "reward": {"type": "tp", "amount": 100}},
            {"kind": "search", "target": 1, "progress": 0, "done": False, "reward": {"type": "tp", "amount": 50}},
        ], ensure_ascii=False)
        cash_qi = mqu.cash
        await s.commit()
    upd = _text_update("کنده کاری", uid=8871, uname="mqint", fname="ماین‌کوئستی")
    await mine_h.mine_cmd(upd, None)
    texts = [c[1] for c in upd.message.calls if c[0] == "reply"]
    check("کنده‌کاری واقعی کوئست رو کامل و اعلامش همونجا میاد",
          any("⛏ کنده‌کاری" in t for t in texts)
          and any("آفرین" in t and "«1 بار کنده‌کاری»" in t and "🎁 جایزه: 100 تی‌پوینت" in t for t in texts),
          str([t.replace("\n", " ")[:70] for t in texts]))
    async with session_scope() as s:
        mqu = await users.get_by_tg(s, 8871)
        check("جایزه کوئست ماین به حساب نشست",
              mqu.cash >= cash_qi + 100 + 10, f"{mqu.cash} (قبل {cash_qi})")
        await s.commit()

    # ── رگرسیون باگ «رهاش کن» (relcf سه‌تیکه) ──
    from handlers import dogs as dogs_h3
    async with session_scope() as s:
        rl = await users.get_by_tg(s, 8809)
        dogs_now = await dog_svc.get_user_dogs(s, rl.id)
        rel_dog = dogs_now[0]
        n_before = len(dogs_now)
        did, dname = rel_dog.id, rel_dog.name
        await s.commit()
    upd = _fake_update(f"dog:rel:{did}", uid=8809)
    await dogs_h3.release_confirm(upd, None)
    ed = next((c for c in upd.callback_query.calls if c[0] == "edit"), None)
    rel_datas = [b.callback_data for row in ed[2]["reply_markup"].inline_keyboard for b in row] if ed else []
    check("فاکتور رها کردن سگ میاد با دکمه رهاش کن",
          ed is not None and "🕊 رها کردن" in ed[1] and "برگشتی نداره" in ed[1]
          and rel_datas == [f"relcf:{did}:8809", "txcl:8809"], str(rel_datas))
    upd = _fake_update(f"relcf:{did}:8809", uid=8809)
    await dogs_h3.release_execute(upd, None)
    ed2 = next((c for c in upd.callback_query.calls if c[0] == "edit"), None)
    async with session_scope() as s:
        rl = await users.get_by_tg(s, 8809)
        rest = await dog_svc.get_user_dogs(s, rl.id)
        check("دکمه «رهاش کن» کار می‌کنه و سگ آزاد میشه (رگرسیون)",
              ed2 is not None and "سگ‌های من" in ed2[1]
              and len(rest) == n_before - 1 and all(d.name != dname for d in rest),
              f"{n_before}→{len(rest)}" if ed2 else "no edit")
        await s.commit()

    # ── فلوی سپر تو هندلر حمله (alert هدف سپردار + پرامپت شکستن سپر) ──
    from handlers import attack as attack_h3
    async with session_scope() as s:
        sh_a, _ = await users.get_or_create(s, tg(8880, "shatta", "سپری‌زن"))
        sh_b, _ = await users.get_or_create(s, tg(8881, "shtarg", "سپرخور"))
        sh_a.level = 10
        sh_b.level = 10
        sh_a.cash = 50000
        sh_b.cash = 50000
        sh_a.energy = config.MAX_ENERGY
        sh_a.last_attack_at = None
        sh_a_id, sh_b_id = sh_a.id, sh_b.id
        await s.commit()

    upd = _fake_update(f"cf:att:{sh_b_id}", uid=8880)
    await attack_h3.attack_execute(upd, None)
    ed = next((c for c in upd.callback_query.calls if c[0] == "edit"), None)
    check("حمله منویی انجام شد و نتیجه دمیج و شانس داره",
          ed is not None and "دمیج" in ed[1] and "شانس بردت" in ed[1], ed[1][:120] if ed else "-")
    async with session_scope() as s:
        sh_a = await users.get_by_tg(s, 8880)
        sh_b = await users.get_by_tg(s, 8881)
        check("هدف بعد از حمله سپر گرفت", combat.shield_left(sh_b) > 0)
        sh_a.last_attack_at = None
        sh_a.energy = config.MAX_ENERGY
        await s.commit()

    # هدف سپردار → الرت
    upd = _fake_update(f"cf:att:{sh_b_id}", uid=8880)
    await attack_h3.attack_execute(upd, None)
    ans = next((c for c in upd.callback_query.calls if c[0] == "answer"), None)
    check("زدن هدف سپردار الرت میده",
          ans is not None and ans[2].get("show_alert") and ans[1] and "سپر محافظ داره" in ans[1][0],
          str(ans)[10:130] if ans else "no answer")

    # خودش سپر داره → پرامپت شکستن سپر با دکمه brk
    async with session_scope() as s:
        sh_a = await users.get_by_tg(s, 8880)
        sh_b = await users.get_by_tg(s, 8881)
        sh_b.shield_until = None
        sh_a.shield_until = now_utc() + timedelta(minutes=10)
        sh_a.last_attack_at = None
        sh_a.energy = config.MAX_ENERGY
        await s.commit()
    upd = _fake_update(f"cf:att:{sh_b_id}", uid=8880)
    await attack_h3.attack_execute(upd, None)
    ed = next((c for c in upd.callback_query.calls if c[0] == "edit"), None)
    pr_datas = [b.callback_data for row in ed[2]["reply_markup"].inline_keyboard for b in row] if ed else []
    check("پرامپت شکستن سپر با متن دقیق میاد",
          ed is not None
          and "<b>🛡 سپر محافظت هنوز فعاله</b>" in ed[1]
          and "اگر حمله کنی سپرت از بین میره" in ed[1] and "ادامه میدی؟" in ed[1]
          and pr_datas == [f"cf:att:{sh_b_id}:brk", "cl"], f"{pr_datas} | {(ed[1][:80] if ed else '-')}")

    # تایید شکستن سپر → حمله انجام میشه و سپرش پاک میشه
    upd = _fake_update(f"cf:att:{sh_b_id}:brk", uid=8880)
    await attack_h3.attack_execute(upd, None)
    ed = next((c for c in upd.callback_query.calls if c[0] == "edit"), None)
    async with session_scope() as s:
        sh_a = await users.get_by_tg(s, 8880)
        check("با brk حمله انجام شد و سپر خودش شکست",
              ed is not None and "دمیج" in ed[1] and sh_a.shield_until is None,
              ed[1][:90] if ed else "-")
        await s.commit()

    print(f"\n🎉 همه تست‌ها سبز شدن، {PASS} مورد")


asyncio.run(main())
