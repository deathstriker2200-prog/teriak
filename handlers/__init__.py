"""سیم‌کشی هندلرها به اپلیکیشن — دستورهای متنی هم PV هم گروه جواب میدن"""

from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from handlers import admin, attack, dogs, farm, mine, profile, rank, shop, start, textcmd

ZWNJ = "‌"
S = rf"[\s{ZWNJ}]"  # فاصله یا نیم‌فاصله


def register_handlers(app: Application) -> None:
    fa_text = filters.TEXT & ~filters.COMMAND

    # ── دستورهای اسلشی ──
    app.add_handler(CommandHandler("start", start.start_cmd))
    app.add_handler(CommandHandler("menu", start.menu_cmd))
    app.add_handler(CommandHandler("profile", profile.profile_cmd))
    app.add_handler(CommandHandler("farm", farm.farm_cb))
    app.add_handler(CommandHandler("shop", shop.shop_cb))
    app.add_handler(CommandHandler("attack", attack.attack_cb))
    app.add_handler(CommandHandler("rank", rank.rank_cb))
    app.add_handler(CommandHandler("dogs", dogs.dogs_cb))
    app.add_handler(CommandHandler("mine", mine.mine_cmd))
    app.add_handler(CommandHandler("admin", admin.admin_cmd))

    # ── دستورهای متنی فارسی (PV و گروه) ──
    # ترتیب اضافه شدن مهمه: الگوهای اختصاصی اول
    app.add_handler(MessageHandler(fa_text & filters.Regex(r"^کنده[\s‌]*کاری!?$"), mine.mine_cmd))
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^شاپ!?$|^فروشگاه!?$|^[sS]hop$|^/{S}?[sS]hop$"), textcmd.shop_text))
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^پروفایل!?$|^[pP]rofile$"), textcmd.profile_text))
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^حمله!?$"), textcmd.attack_text))
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^برداشت{S}*محصول!?$|^برداشت!?$"), textcmd.harvest_text))
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^خرید{S}+سگ{S}+(.+)$"), textcmd.buy_dog_text))
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^خرید{S}+(.+)$"), textcmd.buy_text))
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^کاشت{S}+(.+)$"), textcmd.plant_text))
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^سگ{S}*های{S}*من!?$"), textcmd.dogs_text))
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^مزرعه!?$"), textcmd.farm_text))

    # ── منوی اصلی ──
    app.add_handler(CallbackQueryHandler(start.menu_cb, pattern=r"^menu:home$"))
    app.add_handler(CallbackQueryHandler(profile.profile_cb, pattern=r"^menu:profile$"))
    app.add_handler(CallbackQueryHandler(farm.farm_cb, pattern=r"^menu:farm$"))
    app.add_handler(CallbackQueryHandler(shop.shop_cb, pattern=r"^menu:shop$"))
    app.add_handler(CallbackQueryHandler(attack.attack_cb, pattern=r"^menu:attack$"))
    app.add_handler(CallbackQueryHandler(rank.rank_cb, pattern=r"^menu:rank$"))
    app.add_handler(CallbackQueryHandler(dogs.dogs_cb, pattern=r"^menu:dogs$"))

    # ── مزرعه ──
    app.add_handler(CallbackQueryHandler(farm.buy_plot_confirm, pattern=r"^farm:buy$"))
    app.add_handler(CallbackQueryHandler(farm.buy_plot_execute, pattern=r"^cf:farm:buy$"))
    app.add_handler(CallbackQueryHandler(farm.plant_picker, pattern=r"^farm:plant:\d+$"))
    app.add_handler(CallbackQueryHandler(farm.plant_confirm, pattern=r"^farm:plant:\d+:\w+$"))
    app.add_handler(CallbackQueryHandler(farm.plant_execute, pattern=r"^cf:plant:\d+:\w+$"))
    app.add_handler(CallbackQueryHandler(farm.harvest_cb, pattern=r"^farm:hv$"))
    app.add_handler(CallbackQueryHandler(farm.upgrade_confirm, pattern=r"^farm:up:\d+$"))
    app.add_handler(CallbackQueryHandler(farm.upgrade_execute, pattern=r"^cf:farm:up:\d+$"))

    # ── فروشگاه ──
    app.add_handler(CallbackQueryHandler(shop.section_cb, pattern=r"^shop:sec:\w+$"))
    app.add_handler(CallbackQueryHandler(shop.buy_confirm, pattern=r"^shop:buy:\w+:\w+$"))
    app.add_handler(CallbackQueryHandler(shop.buy_execute, pattern=r"^cf:shop:buy:\w+:\w+$"))

    # ── سگ‌ها ──
    app.add_handler(CallbackQueryHandler(dogs.feed_picker, pattern=r"^dogs:feed:\d+$"))
    app.add_handler(CallbackQueryHandler(dogs.feed_execute, pattern=r"^cf:feed:\d+:\w+$"))

    # ── حمله ──
    app.add_handler(CallbackQueryHandler(attack.find_cb, pattern=r"^att:find$"))
    app.add_handler(CallbackQueryHandler(attack.attack_execute, pattern=r"^cf:att:\d+$"))

    # ── تایید دستورهای متنی (فقط خود کاربر) ──
    app.add_handler(CallbackQueryHandler(textcmd.tx_confirm_cb, pattern=r"^txcf:\w+:\w+:\d+$"))
    app.add_handler(CallbackQueryHandler(textcmd.tx_attack_cb, pattern=r"^txatt:\d+:\d+$"))
    app.add_handler(CallbackQueryHandler(textcmd.tx_cancel_cb, pattern=r"^txcl:\d+$"))

    # ── ادمین ──
    app.add_handler(CallbackQueryHandler(admin.admin_cb, pattern=r"^adm:\w+:\d+$"))

    # ── عمومی ──
    app.add_handler(CallbackQueryHandler(start.cancel_cb, pattern=r"^cl$"))
    app.add_handler(CallbackQueryHandler(start.noop_cb, pattern=r"^noop:"))
