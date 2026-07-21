"""شروع | ثبت‌نام خودکار | منو | لغو"""

from telegram import Update
from telegram.ext import ContextTypes

import config
from database import session_scope
from handlers.common import respond
from keyboards import keyboards as kb
from services import users
from utils import esc, money


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with session_scope() as s:
        user, created = await users.get_or_create(s, update.effective_user)
        users.apply_energy_regen(user)
        name = esc(users.display_name(user))
        await s.commit()

    if created:
        text = (
            f"<b>🔥 سلام {name} به تریاکی خوش اومدی</b>\n\n"
            "اینجا یه محله‌ست و تو می‌خوای پادشاهش بشی\n"
            f"با {money(config.START_CASH)} سرمایه شروعت می‌کنی\n\n"
            "🌱 زمین بخری، بذر بخری و...همم چیزای خلاف بکاری\n"
            "📦 هر ۲ دقیقه می‌تونی برداشت کنی\n"
            "🐕 سگ بگیر که باهات بجنگه\n"
            "🛒 سلاح و زره بگیر که قوی بشی\n"
            "⚔️ تو گروه ریپلای بزن رو هرکی که میخوای و بنویس «حمله» و جیبش رو خالی کن\n\n"
            "هر نیم دقیقه هم می‌تونی کلمه «کنده کاری» رو بفرستی و یه پول خرد بگیری\n\n"
            "از منوی زیر شروع کن 👇"
        )
    else:
        text = (
            f"<b>😎 سلام {name} خوب شد که دوباره اومدی</b>\n\n"
            "محله بی تو حال نمی‌داد\n"
            "فقط بگو کجا می‌خوای بری 👇"
        )

    await update.message.reply_html(text, reply_markup=kb.main_menu_kb())


async def menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_html(
        "<b>🏠 منوی اصلی</b>\n\nکجا می‌خوای بری داداش؟",
        reply_markup=kb.main_menu_kb(),
    )


async def menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await respond(
        update,
        "<b>🏠 منوی اصلی</b>\n\nکجا می‌خوای بری داداش؟",
        kb.main_menu_kb(),
    )


async def cancel_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await respond(
        update,
        "<b>😅 بی‌خیال شدیم</b>\n\nهر وقت نظرت عوض شد اینجام",
        kb.main_menu_kb(),
    )


# پیام‌های کوتاه دکمه‌های اطلاعاتی
_NOOP_ANSWERS = {
    "lock": "🔒 اول باید لولت بره بالا رفیق",
    "own": "اینو داری که داداش",
    "winfo": "🗡 سلاح قدرت حملتو می‌بره بالا — فقط بهترینش حساب میشه",
    "ainfo": "🛡 زره دفات رو قوی می‌کنه — فقط بهترینش حساب میشه",
    "maxplot": "این زمین مکس لوله",
    "maxplots": "🏡 به سقف زمین رسیدی رفیق",
    "plot": "🗺 اینم زمینته — از دکمه‌های زیرش استفاده کن",
    "grow": "⏳ صبر کن رشد کنه رفیق",
    "ready": "✅ آمادست — از دکمه برداشت پایین استفاده کن",
    "feedinfo": "🍖 برای غذا دادن برو تو «سگ‌های من» و دکمه 🍖 زیر سگت رو بزن",
    "doginfo": "🐕 برای غذا دادن از دکمه 🍖 زیرش استفاده کن",
}


async def noop_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    key = query.data.split(":")[1] if ":" in query.data else ""
    await query.answer(_NOOP_ANSWERS.get(key, "👀"), show_alert=True)
