"""شروع | ثبت‌نام خودکار | منو | لغو | هلپ"""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatType
from telegram.ext import ContextTypes

import config
from database import session_scope
from handlers.common import respond, strip_home
from keyboards import keyboards as kb
from services import users
from utils import esc, money


async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with session_scope() as s:
        user, created = await users.get_or_create(s, update.effective_user)
        users.apply_energy_regen(user)
        name = esc(users.display_name(user))
        await s.commit()

    # ── /start تو گروه — پیام مخصوص ──
    if update.effective_chat.type != ChatType.PRIVATE:
        bot_username = kb.BOT_USERNAME or (await context.bot.get_me()).username
        text = (
            "🔥 سلام رفقا تریاکی اومد وسط این گروه 💊🔫\n\n"
            f"از الان هرکی بهم /start بزنه با {money(config.START_CASH)} وارد محله میشه\n\n"
            "⚔️ برای حمله ریپلای بزن و بنویس «حمله»\n"
            "⛏ برای درآمد بنویس «کنده کاری»\n"
            "🛒 برای خرید بنویس «خرید چاقو» یا «خرید سگ دوبرمن اصغر»\n\n"
            "بقیه کارای مدیریتی تو پیوی منه — برو اونجا /start بزن 🛒\n\n"
            "⚠️ من هنوز تو این گروه ادمین نیستم و بدون ادمین بودن نمی‌تونم پیام‌های متنی رو ببینم\n"
            "لطفا از تنظیمات گروه من رو ادمین کن تا همه چی درست کار کنه 🙏"
        )
        markup = InlineKeyboardMarkup([[InlineKeyboardButton(
            "💊 برو پیوی ربات", url=f"https://t.me/{bot_username}", style="primary",
        )]])
        await update.message.reply_html(text, reply_markup=markup)
        return

    # ── /start تو پیوی ──
    if created:
        text = (
            f"<b>🔥 سلام {name} به تریاکی خوش اومدی</b>\n\n"
            "اینجا یه محله‌ست و تو می‌خوای پادشاهش بشی\n"
            f"با {money(config.START_CASH)} سرمایه شروعت می‌کنی\n\n"
            "🌱 زمین بخری، بذر بخری و...همم چیزای خلاف بکاری\n"
            "📦 هر 2 دقیقه می‌تونی برداشت کنی\n"
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


# ───────── هلپ ─────────

_HELP_TEXT = (
    "<b>📖 راهنمای تریاکی</b>\n\n"
    "<b>🌱 مزرعه و درآمد</b>\n"
    "اولین زمین رایگانه — بقیه رو با پول می‌خری (سقف 5 زمین)\n"
    "هر زمین بعدی خیلی گرون‌تره و ساختش هم طول می‌کشه 🔨\n"
    "بذر از شاپ یا با «خرید تریاک» میاد\n"
    "کاشت با «کاشت تریاک» یا دکمه 🌱 تو مزرعه\n"
    "هر 2 دقیقه می‌تونی «برداشت محصول» کنی\n"
    "لولت بالاتر بره زمین و بذر بهتر باز میشه\n\n"
    "<b>⚔️ حمله و دزدی</b>\n"
    "تو گروه رو پیام طرف ریپلای کن و بنویس «حمله»\n"
    "بعد ✅ تایید می‌زنی و نتیجه مشخص میشه\n"
    "شانس بردت = حمله تو (پایه + سلاح + سگ‌ها) به دفاع طرف\n"
    "تو پیوی هم از منوی ⚔️ هدف رندوم پیدا کن\n"
    "هر 1 دقیقه یه حمله | بردی بین 10 تا 25٪ جیبشو می‌زنی\n"
    "زره افسانه‌ای طرف دزدی رو نصف می‌کنه 🛡\n"
    "گرگ سیاه دزدیتو تا 15٪ زیاد می‌کنه 🐺\n\n"
    "<b>🐕 سگ‌ها</b>\n"
    "از بخش سگ‌های شاپ بخر یا بنویس «خرید سگ دوبرمن»\n"
    "بعد از پرداخت اسمشو ازت می‌پرسم — با اون اسم صداش می‌زنی\n"
    "آمار هر سگ با «آمار [اسمش]» — از همونجا غذاشم می‌دی\n"
    "روزی 5 بار غذا میدی و لول‌آپ می‌کنه\n\n"
    "<b>🏴 تیم</b>\n"
    "ساخت تیم از لول 10 — «ساخت تیم» بزن و اسمشو بفرست\n"
    "عضویت از لول 5 — «جوین تیم [اسم]»\n"
    "آمار هر تیم با «تیم [اسم]» — مثلا «تیم فوتبالیست‌ها»\n"
    "بیوی تیم (پروفایل تیم) با «ست بیو تیم [متن]» (رهبر)\n"
    "کوئست‌های روزانه جمعی با «کوئست» — جایزه به همه میرسه\n"
    "«کنده کاری تیمی» 70٪ اعضا بزنن پول میره تو خزانه تیم\n\n"
    "<b>🛒 فروشگاه و بقیه</b>\n"
    "شاپ 4+1 بخشه: سلاح (چاقو تا آرپی‌جی 🔫) | زره | بذر | سگ | غذا\n"
    "دکمه قرمز 🔒 یعنی لولت کمه هنوز\n"
    "«کنده کاری» هر 30 ثانیه 10 تا 150 تی‌پوینت\n"
    "«پروفایل» عکس و مشخصات کاملت رو نشون میده\n"
    "لول‌آپ که بشی هم تبریک می‌گیری هم جایزه اسکناس و شارژ انرژی 🎉"
)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_html(
        _HELP_TEXT,
        reply_markup=strip_home(update, kb.home_kb()),
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
    "build": "🔨 زمینت داره ساخته میشه — صبر کن تحویل بگیرش",
    "feedinfo": "🍖 برای غذا دادن برو تو «سگ‌های من» و دکمه 🍖 زیر سگت رو بزن",
    "doginfo": "🐕 برای غذا دادن از دکمه 🍖 زیرش استفاده کن",
}


async def noop_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    key = query.data.split(":")[1] if ":" in query.data else ""
    await query.answer(_NOOP_ANSWERS.get(key, "👀"), show_alert=True)
