"""
سیم‌کشی هندلرها به اپلیکیشن، دستورهای متنی هم PV هم گروه جواب میدن

دستورهای متنی با پیشوند «تریاکی | تریاک | تی » میان، مثلا:
«تریاکی زمین» «تریاک شاپ» «تی حمله» «تریاکی تیم پروفایل» «تریاکی تیم بانک»
«کنده کاری» و «حمله» و دستورهای تیم بدون پیشوند هم کار می‌کنن

قفل مالکیت دکمه‌ها: پیام دکمه‌داری که از دستور یه نفر تو گروه ساخته شده
فقط خودش می‌تونه بزنه، بقیه هیچ واکنشی نمی‌بینن (handlers/common.owner_guard)
"""

from telegram.ext import Application, CallbackQueryHandler, ChatMemberHandler, CommandHandler, MessageHandler, filters

from handlers import admin, attack, backup, bank, common, dogs, dquests, farm, gate, mine, pending, profile, rank, shop, start, team, textcmd, world

ZWNJ = "‌"
S = rf"[\s{ZWNJ}]"  # فاصله یا نیم‌فاصله
T = rf"^(?:تریاکی|تریاک|تی){S}+"   # پیشوند دستورها، هر سه شکل قبوله
TP = rf"^(?:(?:تریاکی|تریاک|تی){S}+)?"  # پیشوند اختیاری، برای دستورهای تیم

# ── دستورهای متنی فارسی (PV و گروه) ──
# ترتیب مهمه: الگوهای اختصاصی بالاترن (مثلا «تریاکی تیم بانک» قبل از «تریاکی تیم [اسم]»)
# فرمت: (اسم، الگو، هندلر)، تست‌ها روی همین جدول پترن‌ها رو چک می‌کنن
TEXT_HANDLERS: list[tuple[str, str, object]] = [
    ("team_mine", rf"{TP}کنده{S}*کاری{S}*تیمی!?$|{TP}استخراج{S}*تیمی!?$", team.team_mine_text),
    ("mine", rf"^کنده[\s‌]*کاری!?$|{T}کنده{S}*کاری!?$", mine.mine_cmd),  # با و بدون پیشوند
    ("shop", rf"{T}شاپ!?$|{T}فروشگاه!?$", textcmd.shop_text),
    ("profile", rf"{T}پروفایل!?$", textcmd.profile_text),
    ("attack", rf"^حمله!?$|{T}حمله!?$", textcmd.attack_text),  # با و بدون پیشوند
    ("harvest", rf"{T}برداشت{S}*محصول!?$|{T}برداشت!?$", textcmd.harvest_text),
    ("buy_dog", rf"{T}خرید{S}+سگ{S}+(.+)$", textcmd.buy_dog_text),
    ("buy", rf"{T}خرید{S}+(.+)$", textcmd.buy_text),
    ("plant", rf"{T}کاشت{S}+(.+)$", textcmd.plant_text),
    ("mydogs", rf"{T}سگ{S}*های{S}*من!?$|{T}سگ{S}*هام!?$|{T}سگ{S}*ها!?$", textcmd.dogs_text),
    ("farm", rf"{T}مزرعه!?$|{T}زمین{S}*های{S}*من!?$|{T}زمین{S}*هام!?$|{T}زمین{S}*ها!?$|{T}زمین!?$", textcmd.farm_text),
    ("rank", rf"{T}رتبه!?$|{T}رتبه{S}*بندی!?$|{T}لیدربرد!?$|{T}لیدر{S}*برد!?$", rank.rank_cb),
    ("dogstats", rf"{T}آمار{S}+(.+)$", dogs.dog_stats_text),
    # ── تیم ──
    ("team_bld", rf"{TP}تیم{S}+ساختمان(?:{S}*ها)?!?$|{TP}تیم{S}+ساخت!?$", team.buildings_text),
    ("team_profile", rf"{TP}تیم{S}+پروفایل!?$", team.team_profile_text),
    ("roster", rf"{TP}تیم{S}+عضویت!?$", team.roster_text),
    ("team_top", rf"{TP}تیم{S}+لیدربرد!?$|{TP}تیم{S}+لیدر{S}*برد!?$", team.top_teams_text),
    ("team_quests", rf"{TP}تیم{S}+(?:کوئست|چالش)!?$", team.quests_text),
    ("team_bank", rf"{TP}تیم{S}+بانک!?$", team.team_bank_text),
    ("team_dep", rf"{TP}تیم{S}+واریز(?:{S}+(.+))?!?$", team.team_deposit_text),
    ("team_up", rf"{TP}تیم{S}+ارتقا{S}+(?:حمله|دفاع)!?$", team.team_upgrade_text),
    ("team_create", rf"{TP}ساخت{S}+تیم!?$", team.create_team_text),
    ("team_join", rf"{TP}جوین{S}+تیم{S}+(.+)$", team.join_team_text),
    ("team_leave", rf"{TP}ترک{S}+تیم!?$", team.leave_confirm),
    ("team_disband", rf"{TP}انحلال{S}+تیم!?$", team.disband_confirm),
    ("team_bio", rf"{TP}تیم{S}+ست{S}+بیو{S}+(.+)$", team.set_bio_text),
    ("quests", rf"{TP}کوئست{S}*تیم!?$|{TP}کوئست!?$|{TP}استعلام{S}*کوئست!?$", team.quests_text),
    ("team", rf"{TP}تیم(?:{S}+(.+))?!?$", team.team_text),
    ("backup_cancel", rf"{T}لغو{S}*بک{S}*آپ!?$", backup.cancel_upload_text),
    # ── سیستم‌های جهان ──
    ("search", rf"{T}جستجو!?$|{T}جست{S}*و{S}*جو!?$", world.search_cmd),
    ("weather", rf"{T}وضعیت{S}+آب{S}+و{S}+هوا!?$|{T}آب{S}*و{S}*هوا!?$|{T}وضعیت{S}+هواشناسی!?$|{T}هواشناسی!?$|{T}وضعیت{S}+هوا!?$", world.weather_cmd),
    ("market", rf"{T}وضعیت{S}+بازار!?$|{T}بازار{S}*سیاه!?$|{T}بازار!?$", world.market_cmd),
    ("shelter", rf"{T}پناهگاه!?$", world.shelter_cmd),
    ("casino", rf"{T}قمارخانه!?$|{T}قمار!?$", world.casino_cmd),
    # ── بانک شخصی ──
    ("bankhome", rf"{T}بانک!?$", bank.bank_cb),
    ("bankdep", rf"{T}واریز{S}+(.+)$", bank.deposit_text),
    ("bankwd", rf"{T}برداشت{S}+([0-9۰-۹٠-٩,٬]+)$", bank.withdraw_text),
    ("help", rf"{T}راهنما!?$|{T}آموزشات!?$", start.help_cmd),
    ("caravan_spawn", rf"{T}اسپان{S}+کاروان!?$", world.caravan_spawn_cmd),  # فقط ادمین
]


def register_handlers(app: Application) -> None:
    fa_text = filters.TEXT & ~filters.COMMAND

    # ── گیت عضویت اجباری، قبل از همه هندلرها (غیرفعال که باشه کاملاً عبوریه) ──
    app.add_handler(MessageHandler(filters.TEXT | filters.COMMAND, gate.gate_messages), group=-3)
    app.add_handler(CallbackQueryHandler(gate.gate_confirm, pattern=r"^fj:check$"), group=-3)
    app.add_handler(CallbackQueryHandler(gate.gate_callbacks), group=-3)

    # ── گارد مالکیت دکمه‌ها، قبل از همه کالبک‌ها (غریبه هیچ واکنشی نمی‌بینه) ──
    app.add_handler(CallbackQueryHandler(common.owner_guard), group=-2)

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
    app.add_handler(CommandHandler("detp", admin.detp_cmd))
    app.add_handler(CommandHandler("dexp", admin.dexp_cmd))

    # ── اد شدن ربات به گروه، خودش متن خوش‌آمد می‌فرسته ──
    app.add_handler(ChatMemberHandler(start.bot_added, ChatMemberHandler.MY_CHAT_MEMBER))

    # ── دستورهای متنی فارسی (PV و گروه)، همه با پیشوند «تریاکی » به‌جز کنده کاری ──
    for _name, pattern, func in TEXT_HANDLERS:
        app.add_handler(MessageHandler(fa_text & filters.Regex(pattern), func))

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
    app.add_handler(CallbackQueryHandler(dquests.daily_quests_cb, pattern=r"^menu:dquests$"))

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
    app.add_handler(CallbackQueryHandler(team.team_mine_text, pattern=r"^team:mine$"))  # دکمه جمعی
    app.add_handler(CallbackQueryHandler(team.top_teams_text, pattern=r"^team:top$"))
    app.add_handler(CallbackQueryHandler(team.leave_confirm, pattern=r"^team:leave$"))
    app.add_handler(CallbackQueryHandler(team.disband_confirm, pattern=r"^team:disband$"))
    app.add_handler(CallbackQueryHandler(team.team_confirm_cb, pattern=r"^tmcf:(?:leave|disband):\d+$"))
    app.add_handler(CallbackQueryHandler(team.team_create_cb, pattern=r"^teamcf:(?:ok|no):\d+$"))
    app.add_handler(CallbackQueryHandler(team.buildings_cb, pattern=r"^team:bld$"))
    app.add_handler(CallbackQueryHandler(team.team_bank_text, pattern=r"^team:bank$"))
    app.add_handler(CallbackQueryHandler(team.team_upgrade_cb, pattern=r"^tbup:(?:atk|def):\d+$"))
    app.add_handler(CallbackQueryHandler(team.team_upgrade_execute, pattern=r"^tbcf:(?:atk|def):\d+$"))

    # ── سیستم‌های جهان (دکمه‌ها) ──
    app.add_handler(CallbackQueryHandler(world.shelter_up_confirm, pattern=r"^shelter:up$"))
    app.add_handler(CallbackQueryHandler(world.shelter_up_execute, pattern=r"^cf:shelter:up$"))
    app.add_handler(CallbackQueryHandler(world.casino_bet_confirm, pattern=r"^cas:bet:\d+$"))
    app.add_handler(CallbackQueryHandler(world.casino_execute, pattern=r"^cascf:\d+$"))
    app.add_handler(CallbackQueryHandler(world.caravan_hit_cb, pattern=r"^cv:hit$"))  # دکمه جمعی

    # ── بانک شخصی (دکمه‌ها) ──
    app.add_handler(CallbackQueryHandler(bank.bank_cb, pattern=r"^menu:bank$"))
    app.add_handler(CallbackQueryHandler(bank.bank_ask_cb, pattern=r"^bank:(?:dep|wd)$"))
    app.add_handler(CallbackQueryHandler(bank.bank_upgrade_confirm, pattern=r"^bank:up$"))
    app.add_handler(CallbackQueryHandler(bank.bank_upgrade_execute, pattern=r"^cf:bank:up$"))

    # ── حمله ──
    app.add_handler(CallbackQueryHandler(attack.find_cb, pattern=r"^att:find$"))
    app.add_handler(CallbackQueryHandler(attack.attack_execute, pattern=r"^cf:att:\d+(?::brk)?$"))

    # ── آموزشات (هلپ دکمه‌دار) ──
    app.add_handler(CallbackQueryHandler(start.help_section_cb, pattern=r"^help:sec:\w+$"))
    app.add_handler(CallbackQueryHandler(start.help_menu_cb, pattern=r"^help:menu$"))

    # ── تایید دستورهای متنی (فقط خود کاربر، اسم سگ اختیاریه) ──
    app.add_handler(CallbackQueryHandler(textcmd.tx_confirm_cb, pattern=r"^txcf:\w+:\w+:\d+(?::.+)?$"))
    app.add_handler(CallbackQueryHandler(textcmd.tx_attack_cb, pattern=r"^txatt:\d+:\d+(?::brk)?$"))
    app.add_handler(CallbackQueryHandler(textcmd.tx_cancel_cb, pattern=r"^txcl:\d+$"))

    # ── ادمین ──
    app.add_handler(CallbackQueryHandler(admin.admin_cb, pattern=r"^adm:\w+:\d+$"))

    # ── عمومی ──
    app.add_handler(CallbackQueryHandler(start.cancel_cb, pattern=r"^cl$"))
    app.add_handler(CallbackQueryHandler(start.noop_cb, pattern=r"^noop:"))
