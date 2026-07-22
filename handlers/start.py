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

    # ── /start تو گروه — پیام مخصوص (هشدار ادمین فقط وقتی ادمین نیستیم) ──
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


def _breed_lines() -> str:
    """قابلیت هر نژاد — همیشه سینک با کاتالوگ"""
    out = []
    for d in config.DOGS.values():
        crown = "👑 " if d.get("rare") else "🐕 "
        out.append(f"{crown}{d['breed']} — {d['ability']}")
    return "\n".join(out)


def _personality_lines() -> str:
    return "\n".join(f"{p['emoji']} {p['name']}: {p['desc']}" for p in config.DOG_PERSONALITIES.values())


HELP_SECTIONS: dict[str, str] = {
    "farm": (
        "<b>🌱 کاشت و برداشت</b>\n\n"
        "اولین زمین رایگانه — بقیه هرکدوم قیمت و لول خودشونو دارن (سقف 5 زمین) 🔨\n"
        "بذر از شاپ یا با «خرید ماری جوانا» میاد\n"
        "ترتیب بذرها: ماری‌جوانا ← قارچ ← پیوت ← تریاک ← کوکائین\n"
        "کاشت با «کاشت ماری جوانا» یا دکمه 🌱 زیر هر زمین تو مزرعه\n"
        "هر 2 دقیقه می‌تونی «برداشت محصول» کنی\n"
        "هر برداشت یه کیفیت ⭐ داره — کیفیت بالاتر پول بیشتری میده\n"
        "هر زمین رو تا لول 10 آپ کن: هر بار 25٪ درآمد بیشتر و 40٪ سرعت رشد ⬆️\n"
        "بذر جهنم 🔥 و ابلیس 😈 قابل خرید نیستن — از جستجو و کاروان میان\n"
        "ظرفیت انبار هر بذر رو با «پناهگاه» بیشتر کن"
    ),
    "shop": (
        "<b>🛒 شاپ</b>\n\n"
        "4+1 بخشه: سلاح (از چاقو تا آرپی‌جی 🔫) | زره | بذر | سگ | غذا\n"
        "دکمه قرمز 🔒 یعنی لولت کمه — بیشتر کنده کاری کن\n"
        "خرید مستقیم با «خرید [اسم آیتم]» + تاییدیه ✅❌\n"
        "سلاح و زره یه بار خرید میشن و فقط بهترینشون تو نبرد حسابه\n"
        "زره افسانه‌ای 👑 دزدی ازت رو نصف می‌کنه\n"
        "غذا تو شاپ انبار نمیشه — همون لحظه به سگت داده میشه 🍖"
    ),
    "attack": (
        "<b>⚔️ حمله</b>\n\n"
        "تو گروه رو پیام طرف ریپلای کن و بنویس «حمله»\n"
        "تاییدیه ✅ میاد و فقط خودت می‌تونی بزنی\n"
        "شانس بردت = حمله تو (پایه + سلاح + سگ‌ها) به دفاع طرف\n"
        "تو پیوی هم از منوی ⚔️ هدف رندوم پیدا کن (هم‌لولای خودت)\n"
        "هر 1 دقیقه یه حمله | هزینه انرژی داره\n"
        "بردی بین 10 تا 25٪ جیبشو می‌زنی\n"
        "گرگ سیاه 👑 دفاعش رو می‌شکنه و غرامت رو بیشتر می‌کنه | زره افسانه‌ای طرف دزدی رو نصف می‌کنه\n"
        "باختی 15 انرژی جریمه می‌شی ولی تجربه می‌گیری\n"
        "طوفان 10٪ موفقیت حمله رو کم و مه 20٪ دفاع رو زیاد می‌کنه 🌦"
    ),
    "dogs": (
        "<b>🐕 سگ‌ها</b>\n\n"
        "از بخش سگ‌های شاپ بخر یا بنویس «خرید سگ دوبرمن»\n"
        "بعد پرداخت اسمشو ازت می‌پرسم — با اون اسم صداش می‌زنی («آمار اصغر»)\n"
        "هر سگ روزی 5 غذا داره (سهمیه خودش) و ساعت 12 شب به‌وقت ایران ریست میشه\n"
        "از دکمه 🕊 تو کارتش می‌تونی رهاش کنی\n\n"
        "<b>قابلیت هر نژاد:</b>\n"
        + _breed_lines() +
        "\n\n<b>شخصیت هر سگ (موقع خرید رندوم):</b>\n"
        + _personality_lines() +
        "\n\n👑 گرگ سیاه شخصیت نمی‌گیره — قابلیت خودش با لول‌آپ تقویت میشه"
    ),
    "team": (
        "<b>🏴 تیم</b>\n\n"
        "ساخت تیم از لول 10 — «ساخت تیم» بزن و اسمشو بفرست\n"
        "عضویت از لول 5 — «جوین تیم [اسم]» (سقف 10 نفر)\n"
        "«تیم [اسم]» آمار هر تیمی | «تیم من» تیم خودت\n"
        "«تیم پروفایل» آمار کامل + ساختمان‌ها | «تیم عضویت» لیست اعضا\n"
        "بیوی تیم با «ست بیو تیم [متن]» (رهبر)\n"
        "کوئست روزانه با «تیم کوئست» — جایزه به همه اعضا + بانک تیم می‌رسه\n"
        "«کنده کاری تیمی» حداقل 3 عضو — 70٪ اعضا باید بزنن و پول میره تو بانک تیم\n"
        "«تیم بانک» موجودی | «تیم واریز 1200» کمک مالی\n"
        "ساختمان حمله/دفاع با «تیم ساختمان» — رهبر از بانک تیم ارتقا میده و بونسش به همه میرسه\n"
        "هر برد و برداشت امتیاز تیمی میده — آخر هفته 3 تیم اول جایزه می‌گیرن 🏆"
    ),
    "bank": (
        "<b>🏦 بانک شخصی</b>\n\n"
        "«بانک» رو بزن — پولی که تو بانکه موقع حمله دزدیده نمیشه 🛡\n"
        "«واریز 1200» از جیب به بانک | «برداشت 1200» برمی‌گرده جیبت\n"
        "یا دکمه‌های واریز/برداشت رو بزن و مبلغو بفرست\n"
        "ظرفیت بانک = 25,000 × لول بانک — با ⬆️ ارتقا بیشترش کن\n"
        "لول بانک نمی‌تونه از لول خودت جلوتر بزنه"
    ),
    "mine": (
        "<b>⛏ کنده‌کاری</b>\n\n"
        "بنویس «کنده کاری» — هر 30 ثانیه یه بار\n"
        "10 تا 150 تی‌پوینت شانسی (اعداد کوچیک پرتکرارترن)\n"
        "سریع‌ترین راه لول‌آپه — قفل محصولاتو با لول بالاتر باز کن 🔓"
    ),
    "world": (
        "<b>🌍 جستجو و رویدادها</b>\n\n"
        "«جستجو» هر 10 دقیقه — پول/بذر/حتی بذر جهنم 🔥 و ابلیس 😈 — مراقب دزد ☠️\n"
        "🌦 «وضعیت آب و هوا» هر 2 ساعت عوض میشه و روی رشد و نبرد و قیمت اثر داره\n"
        "📈 «وضعیت بازار» هر 4 ساعت قیمت‌ها رو عوض می‌کنه (افسانه‌ای‌ها نه)\n"
        "🚛 کاروان تو گروه‌های فعال میاد — هرکی هر 1 دقیقه ضربه می‌زنه و 🏆 نفر اول بیشترین جایزه رو می‌گیره\n"
        "🚔 پلیس به فعال‌های محله یورش میاره و 30٪ انبارتو نابود می‌کنه\n"
        "🏚 «پناهگاه» رو ارتقا بده تا خسارت یورش کمتر و انبارت بزرگ‌تر شه\n"
        "🎰 «قمارخانه» از لول 7 — هر 12 ساعت یه دست، برد 1.8 برابر شرط ولی خونه همیشه سود می‌کنه"
    ),
    "eco": (
        "<b>⭐ لول و اقتصاد</b>\n\n"
        "xp لازم هر لول = 50 × لول^1.6 — اولا سریعه بعدا سنگین‌تر\n"
        "لول‌آپ: تبریک + اسکناس (250 × لول) + شارژ کامل انرژی 🎉\n"
        "لول بالاتر: محصول و سلاح و سگ و زمین بهتر باز میشه\n"
        "درآمد برداشت هر لول +2٪ بیشتره | قدرت سلاح و زره هر لول +2٪\n"
        "«کنده کاری» سریع‌ترین راه لول‌آپه\n"
        "«رتبه» یا «لیدربرد» 10 نفر برتر محله رو نشون میدن\n"
        "«پروفایل» رو بزن — تایمش ایرانه و تاریخش شمسیه 🕰"
    ),
}


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_html(
        _HELP_INTRO,
        reply_markup=strip_home(update, kb.help_menu_kb()),
    )


async def help_menu_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """🔙 آموزشات — برگشت به منوی بخش‌ها"""
    await respond(update, _HELP_INTRO, kb.help_menu_kb())


async def help_section_cb(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    key = update.callback_query.data.split(":")[-1]
    text = HELP_SECTIONS.get(key)
    if text is None:
        return await help_menu_cb(update, context)
    await respond(update, text, kb.help_back_kb())


# ───────── خوش‌آمد گروه 🔥 ─────────

def group_welcome_text(bot_username: str, is_admin: bool) -> str:
    """متن خوش‌آمد گروهی — موقع اد شدن یا /start گروهی (هشدار فقط وقتی ادمین نیستیم)"""
    text = (
        "🔥 سلام رفقا تریاکی اومد وسط این گروه\n\n"
        f"از الان هرکی دستور /start@{bot_username} رو بزنه با {money(config.START_CASH)} می‌تونه شروع کنه\n\n"
        "⚔️ برای حمله ریپلای بزن و بنویس «حمله»\n"
        "⛏ برای درآمد خرد بنویس «کنده کاری»\n"
        "🛒 برای خرید بنویس شاپ\n\n"
        "بقیه کارای مدیریتی تو پیوی منه — برو اونجا /start بزن 🛒"
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
    """موقع اد شدن به گروه (my_chat_member) — خودش متن خوش‌آمد رو می‌فرسته"""
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
