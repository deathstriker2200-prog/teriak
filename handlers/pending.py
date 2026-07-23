"""
گرفتن ورودی معلق کاربر، بعد از «خرید سگ» اسم سگ | بعد از «ساخت تیم» اسم تیم
تو گروه -1 رجیستر میشه (قبل از دستورهای متنی) و اگه ورودی مال pending بود
با ApplicationHandlerStop بقیه هندلرها رو متوقف می‌کنه
"""

from telegram import Update
from telegram.ext import ApplicationHandlerStop, ContextTypes

import config
from database import session_scope
from keyboards import keyboards as kb
from services import bank as bank_svc
from services import dogs as dog_svc
from services import teams, users
from utils import esc, fa_num, money, normalize_fa, parse_amount

# متن‌هایی که دستورن و نباید به‌عنوان اسم قورت داده بشن («لغو» جداگانه هندل میشه)
_KNOWN_TEXTS = {
    "شاپ", "فروشگاه", "shop", "پروفایل", "profile", "حمله", "برداشت", "برداشت محصول",
    "مزرعه", "زمین هام", "زمین‌ها", "زمین‌های من", "سگ‌های من", "سگهای من",
    "راهنما", "help", "کنده کاری", "کنده کاری تیمی", "استخراج تیمی",
    "کوئست", "کوئست تیم", "استعلام کوئست", "تیم", "تیم من", "ترک تیم",
    "انحلال تیم", "ساخت تیم", "رتبه", "رتبه بندی", "بانک", "واریز",
    "تیم ساختمان", "تیم ساختمان ها", "تیم ساخت", "تیم پروفایل", "تیم عضویت",
    "تیم لیدربرد", "تیم چالش", "تیم کوئست", "تیم بانک", "تیم واریز",
    "جستجو", "جست و جو", "آب و هوا", "وضعیت آب و هوا", "وضعیت هوا", "وضعیت هواشناسی", "وضعیت بازار",
    "بازار سیاه", "بازار", "هواشناسی", "پناهگاه", "قمار", "قمارخانه", "زمین", "لیدربرد", "رتبه بندی",
}

_KNOWN_PREFIXES = ("خرید", "کاشت", "جوین", "آمار", "تیم ", "ست بیو", "بیو ", "واریز ", "برداشت ")


async def capture(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()
    if not text or text.startswith("/"):
        return

    chat = update.effective_chat
    is_group = chat is not None and chat.type in ("group", "supergroup")

    async with session_scope() as s:
        # ردیابی فعالیت گروه، برای اعلان آب و هوا و اسپون کاروان
        if is_group:
            from services import world as world_svc
            await world_svc.touch_group(s, chat.id)
            await s.commit()

        user = await users.get_by_tg(s, update.effective_user.id)
        if user is None or not user.pending_action:
            return

        norm = normalize_fa(text)
        if norm in ("تریاکی", "تریاک", "تی") or norm.startswith(("تریاکی ", "تریاک ", "تی ")):
            return  # دستور با پیشوند رو نباید به عنوان ورودی معلق قورت بدن
        if norm != "لغو" and (norm in _KNOWN_TEXTS or norm.startswith(_KNOWN_PREFIXES)):
            return  # دستوره، بذار بقیه هندلرها بگیرنش

        action = user.pending_action

        # ── لغو ──
        if norm == "لغو":
            msg = await dog_svc.cancel_pending(s, user)
            await s.commit()
            await update.message.reply_html(f"<b>{esc(msg)}</b>")
            raise ApplicationHandlerStop()

        # ── اسم سگ بعد از «خرید سگ»، فاکتور نهایی با نژاد و اسم و قیمت میاد ──
        if action == "dogname":
            dog_key = user.pending_value or ""
            cfg = config.DOGS.get(dog_key)
            if not cfg:
                user.pending_action = None
                user.pending_value = None
                await s.commit()
                await update.message.reply_html("❌ مشکلی پیش اومد، دوباره از شاپ شروع کن")
                raise ApplicationHandlerStop()

            dogs = await dog_svc.get_user_dogs(s, user.id)
            ok, display, why = dog_svc.check_dog_name(dogs, text)
            if not ok:
                await s.commit()
                await update.message.reply_html(why)  # pending می‌مونه تا اسم درست بفرسته
                raise ApplicationHandlerStop()

            user.pending_action = None
            user.pending_value = None
            await s.commit()
            await update.message.reply_html(
                f"<b>🐕 خرید {esc(cfg['breed'])}</b>\n\n"
                f"🐾 نژاد {esc(cfg['breed'])}\n"
                f"📛 اسم {esc(display)}\n"
                f"💸 قیمت {money(cfg['price'])}\n\n"
                "معامله‌ست؟",
                reply_markup=kb.tx_confirm_kb("dog", dog_key, update.effective_user.id, display),
            )
            raise ApplicationHandlerStop()

        # ── مبلغ واریز/برداشت بانک (بعد از دکمه‌های «بانک») ──
        if action in ("bankdep", "bankwd"):
            amount = parse_amount(text)
            if amount is None:
                await update.message.reply_html("❌ فقط عددشو بفرست، مثلا 1200\n\n❌ پشیمون شدی بنویس «لغو»")
                raise ApplicationHandlerStop()

            user.pending_action = None
            user.pending_value = None
            if action == "bankdep":
                ok, res = await bank_svc.deposit(s, user, amount)
            else:
                ok, res = await bank_svc.withdraw(s, user, amount)
            cash, bal = user.cash, user.bank_balance
            await s.commit()

            if ok:
                await update.message.reply_html(
                    f"<b>{esc(res)}</b>\n\n🏦 موجودی بانک {money(bal)}\n💵 نقدینگی {money(cash)}"
                )
            else:
                await update.message.reply_html(res)
            raise ApplicationHandlerStop()

        # ── مبلغ هدیه ادمین به یه کاربر دیگه (از کارت /user) ──
        if action in ("admtp", "admxp"):
            if update.effective_user.id not in config.ADMIN_IDS:
                user.pending_action = None
                user.pending_value = None
                await s.commit()
                return

            amount = parse_amount(text)
            if amount is None:
                await update.message.reply_html("❌ فقط عددشو بفرست، مثلا 5000\n\n❌ پشیمون شدی بنویس «لغو»")
                raise ApplicationHandlerStop()

            target_tg = int(user.pending_value or 0)
            target = await users.get_by_tg(s, target_tg)
            user.pending_action = None
            user.pending_value = None
            if target is None:
                await s.commit()
                await update.message.reply_html("❌ طرف پیدا نشد")
                raise ApplicationHandlerStop()

            name = esc(users.display_name(target))
            if action == "admtp":
                target.cash += amount
                cash = target.cash
                await s.commit()
                await update.message.reply_html(
                    f"<b>💰 {money(amount)} واریز شد به {name}</b>\n\n"
                    f"موجودی جدیدش {money(cash)}"
                )
            else:
                notes = users.add_xp(target, amount)
                level = target.level
                await s.commit()
                out = f"<b>✨ {fa_num(amount)} تجربه دادی به {name}</b>\n\n⭐ الان لول {fa_num(level)} ـه"
                if notes:
                    out += "\n\n" + "\n".join(notes)
                await update.message.reply_html(out)
            raise ApplicationHandlerStop()

        # ── اسم تیم بعد از «ساخت تیم»، فاکتور تایید ساخت میاد ──
        if action == "teamname":
            ok_name, clean, why = teams.validate_team_name(text)
            if not ok_name:
                await s.commit()
                await update.message.reply_html(why)  # pending می‌مونه تا اسم درست بفرسته
                raise ApplicationHandlerStop()
            if await teams.get_team_by_name(s, clean):
                await s.commit()
                await update.message.reply_html(f"🏴 تیمی با اسم «{esc(clean)}» از قبل هست، یه اسم دیگه بفرست")
                raise ApplicationHandlerStop()

            display = " ".join(str(text).split())
            user.pending_action = "teamcf"
            user.pending_value = display[:48]
            await s.commit()
            await update.message.reply_html(
                f"<b>🏴 ساخت تیم «{esc(display)}»</b>\n\n"
                f"💸 هزینه ساخت {money(config.TEAM_CREATE_COST)}\n"
                f"👑 تو رهبرش میشی و تا {fa_num(config.TEAM_MAX_MEMBERS)} نفر عضو میگیره\n\n"
                "می‌سازیمش؟",
                reply_markup=kb.team_create_confirm_kb(update.effective_user.id),
            )
            raise ApplicationHandlerStop()
