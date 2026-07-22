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

    # ── /start تو گروه، پیام مخصوص (هشدار ادمین فقط وقتی ادمین نیستیم) ──
    if update.effective_chat.type != ChatType.PRIVATE:
        bot_username = kb.BOT_USERNAME or (await context.bot.get_me()).username
        is_admin = await _bot_is_group_admin(context, update.effective_chat.id)
        markup = InlineKeyboardMarkup([[InlineKeyboardButton(
            "🛒 برو پیوی ربات", url=f"https://t.me/{bot_username}", style="primary",
        )]])
        await update.message.reply_html(group_welcome_text(bot_username, is_admin), reply_markup=markup)
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


# ───────── آموزشات (هلپ دکمه‌دار) 📖 ─────────

_HELP_INTRO = (
    "<b>📖 آموزشات تریاکی</b>\n\n"
    "بخش مورد نظر رو انتخاب کن تا آموزشات لازم رو بهت بدم 👇"
)


HELP_SECTIONS: dict[str, str] = {
    "farm": (
        "<b>🌱 کاشت و برداشت</b>\n\n"
        "اولین زمین رایگانه و می‌تونی تا ۵ زمین داشته باشی".replace("۵ زمین", "5 زمین") +
        "\nهر زمین قیمت و لول موردنیاز خودش رو داره\n"
        "بذرها رو از شاپ یا با دستور «خرید [نام بذر]» تهیه کن\n\n"
        "ترتیب بذرها\n"
        "🌿 ماری‌جوانا\n"
        "🍄 قارچ\n"
        "🌵 پیوت\n"
        "🌱 تریاک\n"
        "⚪ کوکائین\n\n"
        "برای کاشت از دستور «کاشت [نام بذر]» یا دکمه 🌱کاشت داخل مزرعه استفاده کن\n"
        "هر 2 دقیقه یک بار می‌تونی محصولت رو برداشت کنی\n"
        "محصولات با کیفیت ⭐ تا ⭐⭐⭐⭐⭐ برداشت میشن و کیفیت بالاتر سکه بیشتری میده\n"
        "هر زمین رو می‌تونی تا لول ۵ ارتقا بدی".replace("تا لول ۵", "تا لول 5") +
        "\n⬆️ هر ارتقا درآمد رو ۲۵٪ و سرعت رشد رو ۴۰٪ افزایش میده".replace("۲۵٪", "25٪").replace("۴۰٪", "40٪") +
        "\n\n🔥 بذر جهنم و 😈 بذر ابلیس قابل خرید نیستن و فقط از جستجو یا غارت کاروان به دست میان\n"
        "🏚 با ارتقای پناهگاه ظرفیت انبار محصولاتت بیشتر میشه"
    ),
    "shop": (
        "<b>🛒 شاپ</b>\n\n"
        "پنج بخش اصلی داره\n\n"
        "🔫 سلاح\n"
        "🛡 زره\n"
        "🌱 بذر\n"
        "🐕 سگ\n"
        "🍖 غذا\n\n"
        "🔒 و قرمزی دکمه یعنی هنوز لولت برای خرید اون آیتم کافی نیست\n\n"
        "با دستور «خرید [نام آیتم]» می‌تونی آیتم موردنظرت رو بخری\n"
        "با دستور «خرید سگ [نژاد سگ]» سگ موردنظرت رو بخری (پس از تایید باید یه اسمی رو براش انتخاب کنی)\n"
        "و بعد خرید رو تایید ✅ یا لغو ❌ کنی\n\n"
        "هر سلاح و زره فقط یک بار خریداری میشن و همیشه قوی‌ترینشون توی نبرد استفاده میشه\n\n"
        "🍖 غذای سگ داخل انبار ذخیره نمیشه و بعد از خرید مستقیم به سگت داده میشه"
    ),
    "attack": (
        "<b>⚔️ حمله</b>\n\n"
        "برای حمله در گروه روی پیام بازیکن ریپلای کن و بنویس حمله\n\n"
        "قدرت حمله از قدرت پایه، سلاح و سگت محاسبه میشه و با دفاع حریف مقایسه میشه\n\n"
        "در پیوی هم از بخش ⚔️ می‌تونی یک حریف در بازه لولی خودت پیدا کنی\n\n"
        "هر 1 دقیقه یک بار می‌تونی حمله کنی و هر حمله مقداری انرژی مصرف می‌کنه\n\n"
        "در صورت پیروزی بین 5% تا 10% سکه حریف رو غارت می‌کنی\n\n"
        "👑 گرگ سیاه تا ۳۰٪ دفاع حریف رو کاهش میده و سکه بیشتری از حمله به دست میاره".replace("۳۰٪", "30٪") +
        "\n👑 زره افسانه‌ای مقدار سکه‌ای که از صاحبش غارت میشه رو نصف می‌کنه\n\n"
        "اگر شکست بخوری ۱۵ انرژی از دست میدی اما همچنان تجربه دریافت می‌کنی".replace("۱۵", "15") +
        "\n\nوضعیت آب و هوایی موثر بر حمله\n\n"
        "🌪 طوفان شانس موفقیت حمله رو ۱۰٪ کاهش میده".replace("۱۰٪", "10٪") +
        "\n\n🌫 مه دفاع همه بازیکن‌ها رو ۲۰٪ افزایش میده".replace("۲۰٪", "20٪")
    ),
    "dogs": (
        "<b>🐕 سگ‌ها</b>\n\n"
        "سگ موردنظرت رو از شاپ یا با دستور «خرید سگ [نژاد]» بخر\n\n"
        "بعد از خرید اسمش رو انتخاب می‌کنی و از همون اسم برای دیدن اطلاعاتش استفاده می‌کنی\n"
        "مثال: «آمار اصغر»\n\n"
        "هر سگ روزانه ۵ وعده غذا می‌خوره و سهمیه غذا هر شب ساعت ۱۲ به وقت ایران ریست میشه".replace("۵ وعده", "5 وعده").replace("۱۲", "12") +
        "\n\nاز دکمه 🕊 رها سازی می‌تونی سگت رو برای همیشه آزاد کنی\n\n"
        "<b>قابلیت نژادها</b>\n\n"
        "🐕 پیتبول\nقدرت حمله بیشتر\n\n"
        "🐕 دوبرمن\nسرعت حمله بیشتر\n\n"
        "🐕 ژرمن شپرد\nشانس پیدا کردن هدف بهتر\n\n"
        "🐕 کانگال\nقدرت حمله بسیار بالا\n\n"
        "👑 گرگ سیاه\nبا لول‌آپ تا ۳۰٪ دفاع حریف رو کاهش میده و تا ۱۰٪ سکه بیشتری از حریف می‌گیره".replace("۳۰٪", "30٪").replace("۱۰٪", "10٪") +
        "\n\n<b>شخصیت سگ‌ها</b>\n\n"
        "هر سگ هنگام خرید به صورت تصادفی یک شخصیت دریافت می‌کنه\n\n"
        "🦴 وفادار\n۵٪ قدرت بیشتر".replace("۵٪", "5٪") +
        "\n\n⚔ جنگجو\n۱۰٪ قدرت بیشتر".replace("۱۰٪", "10٪") +
        "\n\n🛡 نگهبان\n۱۰٪ کاهش سکه از دست رفته در حمله".replace("۱۰٪", "10٪") +
        "\n\n💰 شکارچی\n۸٪ سکه بیشتر از حمله".replace("۸٪", "8٪") +
        "\n\n🍀 خوش‌شانس\nشانس بیشتر برای پیدا کردن جایزه در جستجو\n\n"
        "👑 گرگ سیاه شخصیت نداره و قدرتش فقط با لول‌آپ افزایش پیدا می‌کنه"
    ),
    "team": (
        "<b>🏴 تیم</b>\n\n"
        "از لول ۱۰ می‌تونی با دستور «ساخت تیم» تیم خودت رو بسازی و اسمش رو انتخاب کنی".replace("لول ۱۰", "لول 10") +
        "\n\nاز لول ۵ می‌تونی با دستور «جوین تیم [نام تیم]» به یک تیم ملحق بشی".replace("لول ۵", "لول 5") +
        "\n\nهر تیم حداکثر ۱۰ عضو می‌تونه داشته باشه".replace("۱۰ عضو", "10 عضو") +
        "\n\nبا دستور «تیم [نام تیم]» اطلاعات هر تیم رو ببین\n"
        "با «تیم من» اطلاعات تیم خودت نمایش داده میشه\n\n"
        "تیم پروفایل مشخصات کامل، ساختمان‌ها و آمار تیم رو نشون میده\n"
        "«تیم عضویت» فهرست اعضای تیم رو نمایش میده\n\n"
        "رهبر تیم می‌تونه با دستور «ست بیو تیم [متن]» توضیحات تیم رو تغییر بده\n\n"
        "با «تیم کوئست» مأموریت روزانه تیم رو انجام بدین تا همه اعضا جایزه بگیرن و بخشی از پاداش به بانک تیم اضافه بشه\n\n"
        "«کنده‌کاری تیمی» با حداقل ۳ عضو شروع میشه و باید حداقل ۷۰٪ اعضا شرکت کنن تا پاداش دریافت کنید".replace("۳ عضو", "3 عضو").replace("۷۰٪", "70٪") +
        "\n\nبا «تیم بانک» موجودی بانک تیم رو ببین\n"
        "با «تیم واریز [مبلغ]» به بانک تیم کمک مالی کن\n\n"
        "رهبر تیم از بخش «تیم ساختمان» می‌تونه ساختمان‌های حمله و دفاع رو با استفاده از موجودی بانک ارتقا بده و بونس اون به همه اعضا تعلق می‌گیره\n\n"
        "هر پیروزی در حمله و هر برداشت محصول برای تیم امتیاز ثبت می‌کنه\n\n"
        "🏆 در پایان هر هفته ۳ تیم برتر بر اساس امتیاز، جایزه ویژه دریافت می‌کنن".replace("۳ تیم", "3 تیم")
    ),
    "bank": (
        "<b>🏦 بانک</b>\n\n"
        "پولت رو داخل بانک نگه دار تا موقع حمله قابل سرقت نباشه 🛡\n\n"
        "با دستور «بانک» منو باز میشه\n"
        "با دستور «واریز [مبلغ]» سکه‌هات رو به بانک منتقل کن\n"
        "با دستور «برداشت [مبلغ]» سکه‌ها رو دوباره به کیف پولت برگردون\n\n"
        "از دکمه‌های واریز و برداشت توی بخش مربوطه هم می‌تونی استفاده کنی و فقط مبلغ رو وارد کنی\n\n"
        "ظرفیت بانک با هر ارتقا بیشتر میشه\n"
        "📦 ظرفیت هر لول بانک برابر با ۲۵٬۰۰۰ سکه است".replace("۲۵٬۰۰۰", "25,000") +
        "\n\n⬆️ لول بانک هیچ‌وقت نمی‌تونه از لول بازیکنت بیشتر باشه"
    ),
    "mine": (
        "<b>⛏ کنده‌کاری</b>\n\n"
        "با دستور کنده کاری هر ۳۰ ثانیه یک بار تی‌پوینت جمع کن".replace("۳۰ ثانیه", "30 ثانیه") +
        "\n\nدر هر بار بین ۱۰ تا ۱۵۰ تی‌پوینت به صورت تصادفی دریافت می‌کنی و شانس گرفتن اعداد کمتر بیشتره".replace("۱۰ تا ۱۵۰", "10 تا 150") +
        "\n\n⛏ کنده‌کاری سریع‌ترین راه برای گرفتن تجربه و افزایش لول اولیست\n\n"
        "🔓 با افزایش لول، زمین‌ها، بذرها و آیتم‌های جدید برات آزاد میشن"
    ),
    "world": (
        "<b>🌍 جستجو و رویدادها</b>\n\n"
        "🔍 با دستور جستجو هر ۱۰ دقیقه شانس خودت رو امتحان کن و پول، بذر، آیتم یا حتی 🔥 بذر جهنم و 😈 بذر ابلیس پیدا کن".replace("۱۰ دقیقه", "10 دقیقه") +
        "\n\n☠️ حواست باشه همیشه ممکنه دزد هم سر راهت سبز بشه\n\n"
        "🌦 وضعیت آب و هوا هر ۲ ساعت تغییر می‌کنه و روی رشد محصولات، نبردها و قیمت فروش تأثیر می‌ذاره".replace("۲ ساعت", "2 ساعت") +
        "\n\n📈 وضعیت بازار هر ۴ ساعت قیمت فروش محصولات رو تغییر می‌ده و شامل بذرهای افسانه‌ای نمیشه".replace("۴ ساعت", "4 ساعت") +
        "\n\n🚛 کاروان به صورت دوره‌ای در گروه‌های فعال ظاهر میشه و هر بازیکن هر ۱ دقیقه یک بار می‌تونه بهش حمله کنه".replace("۱ دقیقه", "1 دقیقه") +
        "\n\n🏆 در پایان رویداد، بیشترین جایزه به بازیکنی می‌رسه که بیشترین آسیب رو وارد کرده باشه\n\n"
        "🚔 یورش پلیس به صورت تصادفی اتفاق می‌افته و تا ۳۰٪ محصولات انبارت رو از بین می‌بره".replace("۳۰٪", "30٪") +
        "\n\n🏚 با ارتقای پناهگاه خسارت یورش پلیس کمتر میشه و ظرفیت انبارت افزایش پیدا می‌کنه\n"
        "برای ساخت یا ارتقا پناهگاه از دستور «پناهگاه» استفاده کن\n\n"
        "🎰 قمارخانه از لول ۷ باز میشه و هر ۱۲ ساعت یک بار می‌تونی با دستور «قمار» شانس خودت رو امتحان کنی".replace("لول ۷", "لول 7").replace("۱۲ ساعت", "12 ساعت")
    ),
    "eco": (
        "<b>⭐ لول و اقتصاد</b>\n\n"
        "هرچقدر لولت بالاتر بره، برای رسیدن به لول بعدی تجربه بیشتری نیاز داری\n\n"
        "🎉 با هر لول‌آپ سکه جایزه می‌گیری و انرژیت کامل شارژ میشه\n"
        "با افزایش لول، بذرها، سلاح‌ها، سگ‌ها و زمین‌های جدید برات آزاد میشن\n"
        "📈 هر لول درآمد برداشت محصولات و قدرت سلاح و زره رو ۲٪ افزایش میده".replace("۲٪", "2٪") +
        "\n\n⛏ کنده‌کاری سریع‌ترین راه برای گرفتن تجربه و افزایش لول اولیست\n\n"
        "🏆 با دستور «رتبه» یا «لیدربرد» می‌تونی ۱۰ بازیکن برتر محله رو ببینی".replace("۱۰ بازیکن", "10 بازیکن") +
        "\n\n👤 با دستور «پروفایل» اطلاعات کامل حسابت نمایش داده میشه"
    ),
}

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_html(
        _HELP_INTRO,
        reply_markup=strip_home(update, kb.help_menu_kb()),
    )


async def help_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """🔙 آموزشات، برگشت به منوی بخش‌ها"""
    await respond(update, _HELP_INTRO, kb.help_menu_kb())


async def help_section_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    key = update.callback_query.data.split(":")[-1]
    text = HELP_SECTIONS.get(key)
    if text is None:
        return await help_menu_cb(update, context)
    await respond(update, text, kb.help_back_kb())


# ───────── خوش‌آمد گروه 🔥 ─────────

def group_welcome_text(bot_username: str, is_admin: bool) -> str:
    """متن خوش‌آمد گروهی، موقع اد شدن یا /start گروهی (هشدار فقط وقتی ادمین نیستیم)"""
    text = (
        "🔥 سلام رفقا تریاکی اومد وسط این گروه\n\n"
        f"از الان هرکی دستور /start@{bot_username} رو بزنه با {money(config.START_CASH)} می‌تونه شروع کنه\n\n"
        "⚔️ برای حمله ریپلای بزن و بنویس «حمله»\n"
        "⛏ برای درآمد خرد بنویس «کنده کاری»\n"
        "🛒 برای خرید بنویس شاپ\n\n"
        "بقیه کارای مدیریتی تو پیوی منه، برو اونجا /start بزن 🛒"
    )
    if not is_admin:
        text += (
            "\n\n⚠️ من هنوز تو این گروه ادمین نیستم و بدون ادمین بودن نمی‌تونم پیام‌های متنی رو ببینم\n"
            "لطفا از تنظیمات گروه من رو ادمین کن تا همه چی درست کار کنه 🙏"
        )
    return text


async def _bot_is_group_admin(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> bool:
    """آیا ربات تو این گروه ادمینه؟"""
    try:
        me = await context.bot.get_me()
        member = await context.bot.get_chat_member(chat_id, me.id)
        return member.status in ("administrator", "creator")
    except Exception:
        return False


async def bot_added(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """موقع اد شدن به گروه (my_chat_member)، خودش متن خوش‌آمد رو می‌فرسته"""
    cm = update.my_chat_member
    if cm is None or cm.chat.type not in ("group", "supergroup"):
        return
    new = cm.new_chat_member
    status = new.status if new else ""
    if status not in ("member", "administrator"):
        return

    me = await context.bot.get_me()
    username = me.username or "TeriakyBot"
    kb.BOT_USERNAME = kb.BOT_USERNAME or username
    text = group_welcome_text(username, status == "administrator")
    markup = InlineKeyboardMarkup([[InlineKeyboardButton(
        "🛒 برو پیوی ربات", url=f"https://t.me/{username}", style="primary",
    )]])
    try:
        await context.bot.send_message(cm.chat.id, text, parse_mode="HTML", reply_markup=markup)
    except Exception:
        pass

    # گروه رو فعال ثبت کن (اعلان آب و هوا و کاروان بهش میرسه)
    from services import world as world_svc
    async with session_scope() as s:
        await world_svc.touch_group(s, cm.chat.id)
        await s.commit()


# پیام‌های کوتاه دکمه‌های اطلاعاتی
_NOOP_ANSWERS = {
    "lock": "🔒 اول باید لولت بره بالا",
    "own": "اینو داری که",
    "winfo": "🗡 سلاح قدرت حملتو می‌بره بالا، فقط بهترینش حساب میشه",
    "ainfo": "🛡 زره دفات رو قوی می‌کنه، فقط بهترینش حساب میشه",
    "maxplot": "این زمین مکس لوله",
    "maxplots": "🏡 به سقف زمین رسیدی",
    "plot": "🗺 اینم زمینته، از دکمه‌های زیرش استفاده کن",
    "grow": "⏳ صبر کن رشد کنه",
    "ready": "✅ آمادست، از دکمه برداشت پایین استفاده کن",
    "build": "🔨 زمینت داره ساخته میشه، صبر کن تحویل بگیرش",
    "maxbank": "⭐ بانکت مکس لوله",
    "maxshelter": "⭐ پناهگاهت مکس لوله",
    "depinfo": "💰 تو گروه یا پیوی بنویس «تیم واریز 1200»، عددش خودته",
    "feedinfo": "🍖 برای غذا دادن برو تو «سگ‌های من» و دکمه 🍖 زیر سگت رو بزن",
    "doginfo": "🐕 برای غذا دادن از دکمه 🍖 زیرش استفاده کن",
}


async def noop_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    parts_ = query.data.split(":")
    key = parts_[1] if len(parts_) > 1 else ""
    if key == "plot":
        # «زمین شماره n، از دکمه‌های زیرش استفاده کن»
        words = {1: "یکم", 2: "دوم", 3: "سوم", 4: "چهارم", 5: "پنجم"}
        try:
            idx = int(parts_[2])
        except (IndexError, ValueError):
            idx = 0
        word = words.get(idx, str(idx))
        await query.answer(f"زمین شماره {word}، از دکمه‌های زیرش استفاده کن", show_alert=True)
        return
    await query.answer(_NOOP_ANSWERS.get(key, "👀"), show_alert=True)
