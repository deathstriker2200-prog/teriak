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
            "🛒 برای خرید بنویس «خرید چاقو» یا «خرید سگ دوبرمن»\n\n"
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
        "<b>🏠 منوی اصلی</b>\n\nکجا می‌خوای بری؟",
        reply_markup=kb.main_menu_kb(),
    )


async def menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await respond(
        update,
        "<b>🏠 منوی اصلی</b>\n\nکجا می‌خوای بری؟",
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
    "بذر از شاپ یا با «خرید ماری جوانا» میاد\n"
    "ترتیب بذرها: ماری‌جوانا ← قارچ ← پیوت ← تریاک ← کوکائین\n"
    "کاشت با «کاشت ماری جوانا» یا دکمه 🌱 تو مزرعه\n"
    "هر 2 دقیقه می‌تونی «برداشت محصول» کنی\n"
    "لولت بالاتر بره زمین و بذر بهتر باز میشه\n"
    "هر زمین رو هم تا لول 10 لول‌آپ کن: هر بار 25٪ درآمد بیشتر و 40٪ سرعت رشد ⬆️\n\n"
    "<b>⚔️ حمله و دزدی</b>\n"
    "تو گروه رو پیام طرف ریپلای کن و بنویس «حمله»\n"
    "بعد ✅ تایید می‌زنی و نتیجه مشخص میشه\n"
    "شانس بردت = حمله تو (پایه + سلاح + سگ‌ها) به دفاع طرف\n"
    "تو پیوی هم از منوی ⚔️ هدف رندوم پیدا کن\n"
    "هر 1 دقیقه یه حمله | بردی بین 10 تا 25٪ جیبشو می‌زنی\n"
    "زره افسانه‌ای طرف دزدی رو نصف می‌کنه 🛡\n"
    "گرگ سیاه تا 10٪ غرامت بیشتر می‌گیره و تا 30٪ دفاع طرف رو خرد می‌کنه 🐺\n\n"
    "<b>🐕 سگ‌ها</b>\n"
    "از بخش سگ‌های شاپ بخر یا بنویس «خرید سگ دوبرمن»\n"
    "بعد از پرداخت اسمشو ازت می‌پرسم — با اون اسم صداش می‌زنی\n"
    "آمار هر سگ با «آمار [اسمش]» — از همونجا غذاشم می‌دی\n"
    "هر سگ روزی 5 بار غذا می‌خوره — ساعت 12 شب (به‌وقت ایران) سهمیه ریست میشه\n"
    "هر سگ یه شخصیت هم داره: وفادار 🦴 جنگجو ⚔ نگهبان 🛡 شکارچی 💰 خوش‌شانس 🍀\n"
    "از دکمه تو کارتش می‌تونی رهاشم کنی 🕊\n\n"
    "<b>🏴 تیم</b>\n"
    "ساخت تیم از لول 10 — «ساخت تیم» بزن و اسمشو بفرست\n"
    "عضویت از لول 5 — «جوین تیم [اسم]»\n"
    "«تیم پروفایل» آمار کامل + لول ساختمان‌ها و بونسشون\n"
    "«تیم عضویت» لیست اعضا | «تیم لیدربرد» رقابت تیم‌ها\n"
    "بیوی تیم با «ست بیو تیم [متن]» (رهبر)\n"
    "کوئست‌های روزانه با «تیم کوئست» — جایزه به همه میرسه\n"
    "«کنده کاری تیمی» (حداقل 3 عضو) پول میریزه تو بانک تیم\n"
    "«تیم بانک» موجودی تیم | «تیم واریز 1200» کمک مالی\n"
    "🏗 ساختمان حمله/دفاع با «تیم ساختمان» — رهبر با «تیم ارتقا حمله» و «تیم ارتقا دفاع» از بانک تیم آپگرید می‌کنه و بونسش به همه میرسه\n"
    "💎 هر برد و برداشت به تیمت امتیاز میده — آخر هفته 3 تیم اول جایزه می‌گیرن 🏆\n\n"
    "<b>🏦 بانک شخصی</b>\n"
    "«بانک» رو بزن — پولی که تو بانکه موقع حمله دزدیده نمیشه 🛡\n"
    "«واریز 1200» پول میره تو بانک | «برداشت 1200» برمی‌گرده جیبت\n"
    "بانکتو لول‌آپ کن تا ظرفیتش بیشتر شه — به اندازه لول خودت\n\n"
    "<b>🔍 جستجو و رویدادها</b>\n"
    "«جستجو» هر 10 دقیقه — پول/بذر/حتی بذر جهنم 🔥 و ابلیس 😈 — مراقب دزد باش ☠️\n"
    "🌦 «وضعیت آب و هوا» هر 2 ساعت عوض میشه و روی رشد/دفاع/قیمت اثر داره\n"
    "📈 «وضعیت بازار» هر 4 ساعت قیمت بذرها رو عوض می‌کنه (افسانه‌ای‌ها نه)\n"
    "🚛 کاروان تو گروه‌های فعال میاد — هرکی هر 1 دقیقه ضربه می‌زنه، نفر اول بیشترین جایزه\n"
    "🚔 پلیس هر چند ساعت به فعالا یورش میاره — با «پناهگاه» خسارتشو کم کن\n"
    "🎰 «قمارخانه» از لول 7 — هر 12 ساعت یه دست، برد 1.8 برابر شرط ولی اون‌ورش 60٪ باخته\n\n"
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
    "lock": "🔒 اول باید لولت بره بالا",
    "own": "اینو داری که",
    "winfo": "🗡 سلاح قدرت حملتو می‌بره بالا — فقط بهترینش حساب میشه",
    "ainfo": "🛡 زره دفات رو قوی می‌کنه — فقط بهترینش حساب میشه",
    "maxplot": "این زمین مکس لوله",
    "maxplots": "🏡 به سقف زمین رسیدی",
    "plot": "🗺 اینم زمینته — از دکمه‌های زیرش استفاده کن",
    "grow": "⏳ صبر کن رشد کنه",
    "ready": "✅ آمادست — از دکمه برداشت پایین استفاده کن",
    "build": "🔨 زمینت داره ساخته میشه — صبر کن تحویل بگیرش",
    "maxbank": "⭐ بانکت مکس لوله",
    "maxshelter": "⭐ پناهگاهت مکس لوله",
    "depinfo": "💰 تو گروه یا پیوی بنویس «تیم واریز 1200» — عددش خودته",
    "feedinfo": "🍖 برای غذا دادن برو تو «سگ‌های من» و دکمه 🍖 زیر سگت رو بزن",
    "doginfo": "🐕 برای غذا دادن از دکمه 🍖 زیرش استفاده کن",
}


async def noop_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    parts_ = query.data.split(":")
    key = parts_[1] if len(parts_) > 1 else ""
    if key == "plot":
        # «زمین شماره n — از دکمه‌های زیرش استفاده کن»
        words = {1: "یکم", 2: "دوم", 3: "سوم", 4: "چهارم", 5: "پنجم"}
        try:
            idx = int(parts_[2])
        except (IndexError, ValueError):
            idx = 0
        word = words.get(idx, str(idx))
        await query.answer(f"زمین شماره {word} — از دکمه‌های زیرش استفاده کن", show_alert=True)
        return
    await query.answer(_NOOP_ANSWERS.get(key, "👀"), show_alert=True)
