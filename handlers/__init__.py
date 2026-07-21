"""سیم‌کشی هندلرها به اپلیکیشن"""

from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from handlers import attack, farm, mine, profile, rank, shop, start


def register_handlers(app: Application) -> None:
    # ── دستورها ──
    app.add_handler(CommandHandler("start", start.start_cmd))
    app.add_handler(CommandHandler("menu", start.menu_cmd))
    app.add_handler(CommandHandler("profile", profile.profile_cmd))
    app.add_handler(CommandHandler("farm", farm.farm_cb))
    app.add_handler(CommandHandler("shop", shop.shop_cb))
    app.add_handler(CommandHandler("attack", attack.attack_cb))
    app.add_handler(CommandHandler("rank", rank.rank_cb))
    app.add_handler(CommandHandler("mine", mine.mine_cmd))

    # ── «کنده کاری» به صورت متن آزاد (دستور فارسی در تلگرام ممکن نیست) ──
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.Regex(r"^کنده[\s\u200c]*کاری!?$"),
        mine.mine_cmd,
    ))

    # ── منوی اصلی ──
    app.add_handler(CallbackQueryHandler(start.menu_cb, pattern=r"^menu:home$"))
    app.add_handler(CallbackQueryHandler(profile.profile_cb, pattern=r"^menu:profile$"))
    app.add_handler(CallbackQueryHandler(farm.farm_cb, pattern=r"^menu:farm$"))
    app.add_handler(CallbackQueryHandler(shop.shop_cb, pattern=r"^menu:shop$"))
    app.add_handler(CallbackQueryHandler(attack.attack_cb, pattern=r"^menu:attack$"))
    app.add_handler(CallbackQueryHandler(rank.rank_cb, pattern=r"^menu:rank$"))

    # ── مزرعه ──
    app.add_handler(CallbackQueryHandler(farm.buy_plot_confirm, pattern=r"^farm:buy$"))
    app.add_handler(CallbackQueryHandler(farm.buy_plot_execute, pattern=r"^cf:farm:buy$"))
    app.add_handler(CallbackQueryHandler(farm.plant_picker, pattern=r"^farm:plant:\d+$"))
    app.add_handler(CallbackQueryHandler(farm.plant_confirm, pattern=r"^farm:plant:\d+:\w+$"))
    app.add_handler(CallbackQueryHandler(farm.plant_execute, pattern=r"^cf:plant:\d+:\w+$"))
    app.add_handler(CallbackQueryHandler(farm.harvest_cb, pattern=r"^farm:hv:\d+$"))
    app.add_handler(CallbackQueryHandler(farm.upgrade_confirm, pattern=r"^farm:up:\d+$"))
    app.add_handler(CallbackQueryHandler(farm.upgrade_execute, pattern=r"^cf:farm:up:\d+$"))

    # ── فروشگاه ──
    app.add_handler(CallbackQueryHandler(shop.buy_confirm, pattern=r"^shop:buy:\w+$"))
    app.add_handler(CallbackQueryHandler(shop.buy_execute, pattern=r"^cf:shop:buy:\w+$"))

    # ── حمله ──
    app.add_handler(CallbackQueryHandler(attack.find_cb, pattern=r"^att:find$"))
    app.add_handler(CallbackQueryHandler(attack.attack_execute, pattern=r"^cf:att:\d+$"))

    # ── عمومی ──
    app.add_handler(CallbackQueryHandler(start.cancel_cb, pattern=r"^cl$"))
    app.add_handler(CallbackQueryHandler(start.noop_cb, pattern=r"^noop:"))
