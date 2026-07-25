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
            "⚔️ تو گروه ریپلای بزن رو هرکی که میخوای و بنویس «تریاکی حمله» و جیبش رو خالی کن\n\n"
            "هر نیم دقیقه هم می‌تونی کلمه «کنده کاری» رو بفرستی و یه پول خرد بگیری\n\n"
            "دستورها همه با «تریاکی» شروع میشن، مثلا «تریاکی شاپ»، فقط کنده کاری خلاصه‌ست\n\n"
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
    await respond(
        update,
        "<b>🏠 منوی اصلی</b>\n\nکجا می‌خوای بری؟",
        kb.main_menu_kb(),
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
    "start": (
        "<b>📖 شروع بازی</b>\n\n"
        "با دستور «تریاکی پروفایل» حسابت رو ببین\n"
        "با «تریاکی کنده کاری» یا «کنده کاری» اولین پول و تجربه‌هات رو جمع کن\n"
        "از «تریاکی شاپ» بذر بخر و با «تریاکی کاشت [نام بذر]» بکار\n\n"
        "هر لول‌آپ جایزه می‌گیری و چیزای جدید برات باز میشه\n"
        "پولت رو با «تریاکی بانک» امن نگه دار\n\n"
        "از منوی اصلی همه بخش‌ها یکی‌دو دکمه فاصله‌ست"
    ),
    "battle": (
        "<b>⚔ نبرد</b>\n\n"
        "تو گروه روی پیام حریف ریپلای کن و «حمله» یا «شلیک» بفرست\n"
        "تو پی‌وی با «تریاکی حمله» لیست هدف باز میشه\n\n"
        "قدرت نبردت از سلاح و زره و سگ و آرتیفکت و لولت میاد\n"
        "هر ضربه تی‌پوینت و تجربه میده و سگ‌هات هم از نبرد تجربه می‌گیرن\n\n"
        "سلاح و زره رو تو شاپ تا لول 5 ارتقا بده\n"
        "HPت که کم شد با «تریاکی درمان» خودت رو به هم بزن\n"
        "HP حریف که صفر شد دوئل تمومه و طرف چند دقیقه‌ای از بازی خارجه\n\n"
        "با «تریاکی قمارخانه» هم می‌تونی شانست رو با پولت امتحان کنی"
    ),
    "farm": (
        "<b>🌱 مزرعه</b>\n\n"
        "اولین زمین رایگانه و هر زمین جدید قیمت و لول خودشو می‌خواد\n"
        "بذر از شاپ می‌خری و با «تریاکی کاشت [نام بذر]» یا دکمه کاشت می‌کاری\n"
        "بعد رشد با «تریاکی برداشت» محصولت رو نقد کن\n\n"
        "هر برداشت یه کیفیت داره و کیفیت بهتر پول بیشتری میده\n"
        "آب‌وهوا و بازار هم روی درآمدت اثر می‌ذارن\n\n"
        "⬆️ ارتقای زمین سرعت رشد رو بیشتر و شانس محصول افسانه‌ای رو بالا می‌بره\n"
        "ارتقا علاوه بر تی‌پوینت چوب هم می‌خواد\n\n"
        "بذرهای افسانه‌ای فروخته نمیشن و فقط از جستجو و کاروان میان"
    ),
    "dogs": (
        "<b>🐕 سگ‌ها</b>\n\n"
        "هر نژاد یه ویژگی اصلی داره\n\n"
        "🐕 پیتبول، قدرت حمله بیشتر\n"
        "🐕 دوبرمن، کاهش کولدون حمله\n"
        "🐕 ژرمن شپرد، تجربه بیشتر از نبرد\n"
        "🐕 کانگال، دفاع بیشتر\n"
        "👑 گرگ سیاه، غارت بیشتر و شخصیت هم نمی‌گیره\n\n"
        "هر نژاد فقط شخصیت‌های مخصوص خودش رو می‌گیره\n"
        "سگ‌ها از نبرد تجربه می‌گیرن و با لول قوی‌تر میشن\n"
        "با 🍖 غذا هم لولشون می‌بره\n\n"
        "اسم سگت رو با «اسم سگ [اسم فعلی] [اسم جدید]» عوض کن\n"
        "کارت هر سگ با «تریاکی آمار [اسم سگ]» میاد"
    ),
    "company": (
        "<b>🏭 شرکت</b>\n\n"
        "دو ساختمان داره\n"
        "🪵 چوب‌بری و ⛏️ کارخانه آهن\n\n"
        "هر لحظه که بازش کنی تولید انباشته واریز میشه\n"
        "لول ساختمان بالاتر بره تولید بیشتر میشه\n\n"
        "ساخت و ارتقا علاوه بر تی‌پوینت چوب هم می‌خواد\n"
        "حتی وقتی آفلاینی کارخونه‌هات کار می‌کنن"
    ),
    "shelter": (
        "<b>🏚 مخفیگاه</b>\n\n"
        "انبارت همینجاست\n"
        "ظرفیت بذر و چوب و آهن رو نشون میده\n"
        "با هر ارتقا ظرفیت همه بیشتر میشه\n\n"
        "پلیس هر چند وقت یه بار یورش میاره و محصولات انبار رو می‌سوزونه\n"
        "مخفیگاه خسارت یورش رو کم می‌کنه و شانس فرار هم میده"
    ),
    "team": (
        "<b>👥 تیم</b>\n\n"
        "از لول 10 با «ساخت تیم» رهبر شو\n"
        "از لول 3 با «جوین تیم [نام تیم]» درخواست عضویت بفرست\n"
        "درخواستت باید رهبر یا مدیران اون تیم قبول کنن\n\n"
        "رهبر و مدیران تو «تیم من» بخش 👑 مدیریت تیم رو دارن\n"
        "درخواست‌ها اونجا با دکمه یا دستور «تیم درخواست @یوزر قبول» جواب داده میشن\n"
        "اخراج عضو با «تیم کیک @یوزر» و مدیرسازی با «تیم ادمین @یوزر»\n\n"
        "کوئست روزانه تیم و کنده‌کاری تیمی به همه اعضا جایزه میده\n"
        "ساختمان تیم قدرت همه اعضا رو بالا می‌بره\n"
        "آخر هفته تیم‌های برتر جایزه می‌گیرن"
    ),
    "resources": (
        "<b>🎒 منابع</b>\n\n"
        "چوب و آهن دو منبع اصلی محله‌ان\n"
        "از سه راه به دست میان\n\n"
        "⛏ کنده‌کاری (شانسی میفتن)\n"
        "🛒 خرید پک از فروشگاه\n"
        "🏭 تولید چوب‌بری و کارخانه آهن\n\n"
        "سلاح و ارتقاشون آهن می‌خوان\n"
        "ارتقای زمین و ساختمان‌های شرکت چوب می‌خوان\n"
        "ظرفیتشون با لول مخفیگاه بیشتر میشه\n\n"
        "تبر تو چوب و کلنگ تو آهن بهت کمک می‌کنن\n"
        "لول ابزار بالاتر بره درآمد و شانس کمیابت بیشتر میشه"
    ),
    "shop": (
        "<b>🛒 فروشگاه</b>\n\n"
        "🔫 سلاح، دمیجت رو بالا می‌بره و خریدش آهن هم می‌خواد\n"
        "🛡 زره، دفاعت رو بالا می‌بره\n"
        "⬆️ ارتقای سلاح و زره تا لول 5، با تی‌پوینت و آهن\n"
        "🧿 آرتیفکت‌های کمیاب و گرون آخر بازی، از لول 10\n"
        "🎒 پک چوب و آهن\n"
        "🌱 بذر برای کاشت\n"
        "🐕 سگ‌ها با نژادهای مختلف\n"
        "🍖 غذای سگ\n\n"
        "دکمه سبز یعنی قابل خریده\n"
        "دکمه قرمز یعنی هنوز لولت کافی نیس\n\n"
        "با دستور «تریاکی خرید [نام آیتم]» هم می‌تونی بخری"
    ),
}
async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await respond(update, _HELP_INTRO, kb.help_menu_kb())


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
        "<b>🔥 تریاکی بات وارد گروه شد</b>\n\n"
        f"🎁 با دستور /start@{bot_username} بازی رو شروع کن و {money(config.START_CASH)} جایزه بگیر\n\n"
        "⚔️ برای حمله روی پیام حریف ریپلای کن و بنویس\n"
        "حمله\n"
        "⛏️ برای کسب تی‌پوینت بنویس\n"
        "کنده کاری\n\n"
        f"جهت مشاهده مابقی دستورات و قابلیت‌ها از دستور «تی راهنما» یا /help@{bot_username} استفاده کنید"
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
    "maxplot": "🌱 این زمین لول مکس، بهتر از این نمیشه",
    "maxplots": "🏡 به سقف زمین رسیدی",
    "plot": "🗺 اینم زمینته، از دکمه‌های زیرش استفاده کن",
    "grow": "⏳ صبر کن رشد کنه",
    "ready": "✅ آمادست، از دکمه برداشت پایین استفاده کن",
    "build": "🔨 زمینت داره ساخته میشه، صبر کن تحویل بگیرش",
    "maxbank": "🏦 این بانک لول مکس، بهتر از این نمیشه",
    "maxshelter": "🏚 این پناهگاه لول مکس، بهتر از این نمیشه",
    "maxdog": "🐕 این سگ لول مکس، بهتر از این نمیشه",
    "maxbld": "🏗 این ساختمان لول مکس، بهتر از این نمیشه",
    "depinfo": "💰 تو گروه یا پیوی بنویس «تیم واریز 1200»، عددش خودته",
    "feedinfo": "🍖 برای غذا دادن بنویس «تریاکی سگ‌های من» و دکمه 🍖 زیر سگت رو بزن",
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
