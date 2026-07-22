"""سیم‌کشی هندلرها به اپلیکیشن، دستورهای متنی هم PV هم گروه جواب میدن"""

from telegram.ext import Application, CallbackQueryHandler, ChatMemberHandler, CommandHandler, MessageHandler, filters

from handlers import admin, attack, backup, bank, dogs, farm, mine, pending, profile, rank, shop, start, team, textcmd, world

ZWNJ = "‌"
S = rf"[\s{ZWNJ}]"  # فاصله یا نیم‌فاصله


def register_handlers(app: Application) -> None:
    fa_text = filters.TEXT & ~filters.COMMAND

    # ── ورودی معلق (اسم سگ بعد خرید | اسم تیم بعد ساخت)، قبل از همه دستورهای متنی ──
    app.add_handler(MessageHandler(fa_text, pending.capture), group=-1)

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
    app.add_handler(CommandHandler("help", start.help_cmd))
    app.add_handler(CommandHandler("backup", backup.backup_cmd))
    app.add_handler(CommandHandler("upload_backup", backup.upload_backup_cmd))
    app.add_handler(CommandHandler("user", admin.user_cmd))
    app.add_handler(CommandHandler("addtp", admin.addtp_cmd))
    app.add_handler(CommandHandler("addxp", admin.addxp_cmd))

    # ── اد شدن ربات به گروه، خودش متن خوش‌آمد می‌فرسته ──
    app.add_handler(ChatMemberHandler(start.bot_added, ChatMemberHandler.MY_CHAT_MEMBER))

    # ── دستورهای متنی فارسی (PV و گروه) ──
    # ترتیب اضافه شدن مهمه: الگوهای اختصاصی اول
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^کنده{S}*کاری{S}*تیمی!?$|^استخراج{S}*تیمی!?$"), team.team_mine_text))
    app.add_handler(MessageHandler(fa_text & filters.Regex(r"^کنده[\s‌]*کاری!?$"), mine.mine_cmd))
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^شاپ!?$|^فروشگاه!?$|^[sS]hop$|^/{S}?[sS]hop$"), textcmd.shop_text))
    app.add_handler(MessageHandler(fa_text & filters.Regex(r"^پروفایل!?$|^[pP]rofile$"), textcmd.profile_text))
    app.add_handler(MessageHandler(fa_text & filters.Regex(r"^حمله!?$"), textcmd.attack_text))
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^برداشت{S}*محصول!?$|^برداشت!?$"), textcmd.harvest_text))
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^خرید{S}+سگ{S}+(.+)$"), textcmd.buy_dog_text))
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^خرید{S}+(.+)$"), textcmd.buy_text))
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^کاشت{S}+(.+)$"), textcmd.plant_text))
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^سگ{S}*های{S}*من!?$"), textcmd.dogs_text))
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^مزرعه!?$|^زمین{S}*های{S}*من!?$|^زمین{S}*هام!?$|^زمین{S}*ها!?$|^زمین!?$"), textcmd.farm_text))
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^رتبه!?$|^رتبه{S}*بندی!?$|^لیدربرد!?$|^لیدر{S}*برد!?$"), rank.rank_cb))
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^آمار{S}+(.+)$"), dogs.dog_stats_text))

    # ── تیم ──
    # الگوهای «تیم X» اختصاصی قبل از الگوی عمومی «تیم [اسم]»
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^تیم{S}+ساختمان(?:{S}*ها)?!?$|^تیم{S}+ساخت!?$"), team.buildings_text))
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^تیم{S}+پروفایل!?$"), team.team_profile_text))
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^تیم{S}+عضویت!?$"), team.roster_text))
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^تیم{S}+لیدربرد!?$|^تیم{S}+لیدر{S}*برد!?$"), team.top_teams_text))
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^تیم{S}+(?:کوئست|چالش)!?$"), team.quests_text))
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^تیم{S}+بانک!?$"), team.team_bank_text))
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^تیم{S}+واریز(?:{S}+(.+))?!?$"), team.team_deposit_text))
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^تیم{S}+ارتقا{S}+(?:حمله|دفاع)!?$"), team.team_upgrade_text))
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^ساخت{S}+تیم!?$"), team.create_team_text))
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^جوین{S}+تیم{S}+(.+)$"), team.join_team_text))
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^ترک{S}+تیم!?$"), team.leave_confirm))
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^انحلال{S}+تیم!?$"), team.disband_confirm))
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^(?:ست{S}+)?بیو{S}+تیم{S}+(.+)$"), team.set_bio_text))
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^کوئست{S}*تیم!?$|^کوئست!?$|^استعلام{S}*کوئست!?$"), team.quests_text))
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^تیم(?:{S}+(.+))?!?$"), team.team_text))
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^لغو{S}*بک{S}*آپ!?$"), backup.cancel_upload_text))

    # ── سیستم‌های جهان ──
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^جستجو!?$|^جست{S}*و{S}*جو!?$"), world.search_cmd))
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^وضعیت{S}+آب{S}+و{S}+هوا!?$|^آب{S}*و{S}*هوا!?$|^وضعیت{S}+هواشناسی!?$|^وضعیت{S}+هوا!?$"), world.weather_cmd))
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^وضعیت{S}+بازار!?$|^بازار{S}*سیاه!?$"), world.market_cmd))
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^پناهگاه!?$"), world.shelter_cmd))
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^قمارخانه!?$|^قمار!?$"), world.casino_cmd))

    # ── بانک شخصی ──
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^بانک!?$"), bank.bank_cb))
    app.add_handler(MessageHandler(fa_text & filters.Regex(rf"^واریز{S}+(.+)$"), bank.deposit_text))
    app.add_handler(MessageHandler(fa_text & filters.Regex(r"^برداشت[\s‌]+([0-9۰-۹٠-٩,٬]+)$"), bank.withdraw_text))

    app.add_handler(MessageHandler(fa_text & filters.Regex(r"^راهنما!?$|^[hH]elp$"), start.help_cmd))

    # ── فایل بک‌آپ (فقط بعد از /upload_backup و فقط ادمین) ──
    app.add_handler(MessageHandler(filters.ATTACHMENT & ~filters.COMMAND, backup.backup_doc))

    # ── منوی اصلی ──
    app.add_handler(CallbackQueryHandler(start.menu_cb, pattern=r"^menu:home$"))
    app.add_handler(CallbackQueryHandler(profile.profile_cb, pattern=r"^menu:profile$"))
    app.add_handler(CallbackQueryHandler(farm.farm_cb, pattern=r"^menu:farm$"))
    app.add_handler(CallbackQueryHandler(shop.shop_cb, pattern=r"^menu:shop$"))
    app.add_handler(CallbackQueryHandler(attack.attack_cb, pattern=r"^menu:attack$"))
    app.add_handler(CallbackQueryHandler(rank.rank_cb, pattern=r"^menu:rank$"))
    app.add_handler(CallbackQueryHandler(dogs.dogs_cb, pattern=r"^menu:dogs$"))
    app.add_handler(CallbackQueryHandler(team.team_cb, pattern=r"^menu:team$"))

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
    app.add_handler(CallbackQueryHandler(dogs.dog_card_cb, pattern=r"^dog:card:\d+$"))
    app.add_handler(CallbackQueryHandler(dogs.release_confirm, pattern=r"^dog:rel:\d+$"))
    app.add_handler(CallbackQueryHandler(dogs.release_execute, pattern=r"^relcf:\d+:\d+$"))

    # ── تیم (دکمه‌ها) ──
    app.add_handler(CallbackQueryHandler(team.quests_text, pattern=r"^team:quests$"))
    app.add_handler(CallbackQueryHandler(team.team_mine_text, pattern=r"^team:mine$"))
    app.add_handler(CallbackQueryHandler(team.top_teams_text, pattern=r"^team:top$"))
    app.add_handler(CallbackQueryHandler(team.leave_confirm, pattern=r"^team:leave$"))
    app.add_handler(CallbackQueryHandler(team.disband_confirm, pattern=r"^team:disband$"))
    app.add_handler(CallbackQueryHandler(team.team_confirm_cb, pattern=r"^tmcf:(?:leave|disband):\d+$"))
    app.add_handler(CallbackQueryHandler(team.buildings_cb, pattern=r"^team:bld$"))
    app.add_handler(CallbackQueryHandler(team.team_bank_text, pattern=r"^team:bank$"))
    app.add_handler(CallbackQueryHandler(team.team_upgrade_cb, pattern=r"^tbup:(?:atk|def):\d+$"))
    app.add_handler(CallbackQueryHandler(team.team_upgrade_execute, pattern=r"^tbcf:(?:atk|def):\d+$"))

    # ── سیستم‌های جهان (دکمه‌ها) ──
    app.add_handler(CallbackQueryHandler(world.shelter_up_confirm, pattern=r"^shelter:up$"))
    app.add_handler(CallbackQueryHandler(world.shelter_up_execute, pattern=r"^cf:shelter:up$"))
    app.add_handler(CallbackQueryHandler(world.casino_bet_confirm, pattern=r"^cas:bet:\d+$"))
    app.add_handler(CallbackQueryHandler(world.casino_execute, pattern=r"^cascf:\d+$"))
    app.add_handler(CallbackQueryHandler(world.caravan_hit_cb, pattern=r"^cv:hit$"))

    # ── بانک شخصی (دکمه‌ها) ──
    app.add_handler(CallbackQueryHandler(bank.bank_cb, pattern=r"^menu:bank$"))
    app.add_handler(CallbackQueryHandler(bank.bank_ask_cb, pattern=r"^bank:(?:dep|wd)$"))
    app.add_handler(CallbackQueryHandler(bank.bank_upgrade_confirm, pattern=r"^bank:up$"))
    app.add_handler(CallbackQueryHandler(bank.bank_upgrade_execute, pattern=r"^cf:bank:up$"))

    # ── حمله ──
    app.add_handler(CallbackQueryHandler(attack.find_cb, pattern=r"^att:find$"))
    app.add_handler(CallbackQueryHandler(attack.attack_execute, pattern=r"^cf:att:\d+$"))

    # ── آموزشات (هلپ دکمه‌دار) ──
    app.add_handler(CallbackQueryHandler(start.help_section_cb, pattern=r"^help:sec:\w+$"))
    app.add_handler(CallbackQueryHandler(start.help_menu_cb, pattern=r"^help:menu$"))

    # ── تایید دستورهای متنی (فقط خود کاربر، اسم سگ اختیاریه) ──
    app.add_handler(CallbackQueryHandler(textcmd.tx_confirm_cb, pattern=r"^txcf:\w+:\w+:\d+(?::.+)?$"))
    app.add_handler(CallbackQueryHandler(textcmd.tx_attack_cb, pattern=r"^txatt:\d+:\d+$"))
    app.add_handler(CallbackQueryHandler(textcmd.tx_cancel_cb, pattern=r"^txcl:\d+$"))

    # ── ادمین ──
    app.add_handler(CallbackQueryHandler(admin.admin_cb, pattern=r"^adm:\w+:\d+$"))

    # ── عمومی ──
    app.add_handler(CallbackQueryHandler(start.cancel_cb, pattern=r"^cl$"))
    app.add_handler(CallbackQueryHandler(start.noop_cb, pattern=r"^noop:"))
