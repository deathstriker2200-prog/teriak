"""
گرفتن ورودی معلق کاربر — بعد از «خرید سگ» اسم سگ | بعد از «ساخت تیم» اسم تیم
تو گروه -1 رجیستر میشه (قبل از دستورهای متنی) و اگه ورودی مال pending بود
با ApplicationHandlerStop بقیه هندلرها رو متوقف می‌کنه
"""

from telegram import Update
from telegram.ext import ApplicationHandlerStop, ContextTypes

from database import session_scope
from services import dogs as dog_svc
from services import teams, users
from utils import esc, normalize_fa

# متن‌هایی که دستورن و نباید به‌عنوان اسم قورت داده بشن («لغو» جداگانه هندل میشه)
_KNOWN_TEXTS = {
    "شاپ", "فروشگاه", "shop", "پروفایل", "profile", "حمله", "برداشت", "برداشت محصول",
    "مزرعه", "زمین هام", "زمین‌ها", "زمین‌های من", "سگ‌های من", "سگهای من",
    "راهنما", "help", "کنده کاری", "کنده کاری تیمی", "استخراج تیمی",
    "کوئست", "کوئست تیم", "استعلام کوئست", "تیم", "تیم من", "ترک تیم",
    "انحلال تیم", "ساخت تیم", "رتبه", "رتبه بندی",
}

_KNOWN_PREFIXES = ("خرید", "کاشت", "جوین", "آمار", "تیم ", "ست بیو", "بیو ")


async def capture(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (update.message.text or "").strip()
    if not text or text.startswith("/"):
        return

    async with session_scope() as s:
        user = await users.get_by_tg(s, update.effective_user.id)
        if user is None or not user.pending_action:
            return

        norm = normalize_fa(text)
        if norm != "لغو" and (norm in _KNOWN_TEXTS or norm.startswith(_KNOWN_PREFIXES)):
            return  # دستوره — بذار بقیه هندلرها بگیرنش

        action = user.pending_action

        # ── لغو ──
        if norm == "لغو":
            msg = await dog_svc.cancel_pending(s, user)
            await s.commit()
            await update.message.reply_html(f"<b>{esc(msg)}</b>")
            raise ApplicationHandlerStop()

        # ── اسم سگ بعد از پرداخت ──
        if action == "dogname":
            ok, res = await dog_svc.finalize_dog(s, user, text)
            await s.commit()
            if ok:
                await update.message.reply_html(
                    f"<b>🐕 {esc(res)} شد رفیق جدیدت</b>\n\n"
                    f"باهوشه و به اسمش جواب میده 😎\n"
                    f"هر وقت خواستی بنویس «آمار {esc(res)}» تا کارتو ببینی و از همونجا غذاش بدی"
                )
            else:
                await update.message.reply_html(res)
            raise ApplicationHandlerStop()

        # ── اسم تیم بعد از «ساخت تیم» ──
        if action == "teamname":
            ok, res = await teams.create_team(s, user, text)
            if ok:
                user.pending_action = None
                user.pending_value = None
            await s.commit()
            if ok:
                await update.message.reply_html(
                    f"<b>🏴 تیم «{esc(res)}» ساخته شد</b>\n\n"
                    f"📜 کوئست‌های روزانه با «کوئست»\n"
                    f"⛏ کنده‌کاری تیمی با «کنده کاری تیمی»\n"
                    f"✏️ بیوی تیم با «ست بیو تیم [متن]»\n"
                    f"📊 آمار تیم با «تیم من»\n\n"
                    f"به رفقات بگو بنویسن «جوین تیم {esc(res)}» 😈"
                )
            else:
                await update.message.reply_html(res)
            raise ApplicationHandlerStop()
