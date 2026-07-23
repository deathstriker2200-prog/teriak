"""ابزار مشترک هندلرها + قفل مالکیت دکمه‌ها تو گروه‌ها"""

import re

from telegram import InlineKeyboardMarkup, Update
from telegram.constants import ChatType, ParseMode
from telegram.error import BadRequest
from telegram.ext import ApplicationHandlerStop

from utils import fa_num, money


def strip_home(update: Update, markup):
    """دکمه «🏠 منوی اصلی» رو تو گروه‌ها برمی‌داره"""
    if markup is None or update.effective_chat is None:
        return markup
    if update.effective_chat.type == ChatType.PRIVATE:
        return markup
    rows = [[b for b in row if b.callback_data != "menu:home"] for row in markup.inline_keyboard]
    rows = [r for r in rows if r]
    if not rows:
        return None
    return InlineKeyboardMarkup(rows)


# ───────── قفل مالکیت دکمه‌ها 🔒 ─────────
# پیام دکمه‌داری که از دستور متنی یه نفر تو گروه ساخته شده فقط مال خودشه
# غریبه بزنه هیچ واکنشی نمی‌بینه (نه جواب، نه ادیت، نه الرت)

_MESSAGE_OWNERS: dict[tuple[int, int], int] = {}
_OWNER_CAP = 4000

# دکمه‌های جمعی که مال همه‌ان، تو گارد مستثنی میشن (استخراج تیمی و کاروان)
_SHARED_OPEN = ("team:mine", "cv:hit")


def track_message(chat_id: int | None, message_id: int | None, owner_tg: int | None) -> None:
    """ثبت مالک پیام دکمه‌دار، چت/آیدی/مالک خالی رد میشه"""
    if not chat_id or not message_id or not owner_tg:
        return
    _MESSAGE_OWNERS[(chat_id, message_id)] = owner_tg
    if len(_MESSAGE_OWNERS) > _OWNER_CAP:  # سقف حافظه، قدیمی‌ترین‌ها پاک میشن
        stale = list(_MESSAGE_OWNERS.keys())[:-_OWNER_CAP // 2]
        for key in stale:
            _MESSAGE_OWNERS.pop(key, None)


def owner_of(chat_id: int | None, message_id: int | None) -> int | None:
    """مالک ثبت‌شده پیام، نبود یعنی آزاد"""
    if not chat_id or not message_id:
        return None
    return _MESSAGE_OWNERS.get((chat_id, message_id))


async def owner_guard(update: Update, context) -> None:
    """
    گارد مالکیت دکمه، تو گروه -1 قبل از همه هندلرهای کالبک اجرا میشه
    اگه کلیک‌کننده صاحب دستور نباشه با ApplicationHandlerStop می‌بلاکه
    """
    query = update.callback_query
    if query is None or query.data is None:
        return
    if query.data.startswith(_SHARED_OPEN):
        return
    owner = owner_of(
        getattr(query.message, "chat_id", None),
        getattr(query.message, "message_id", None),
    )
    if owner is None:
        return
    if update.effective_user and update.effective_user.id == owner:
        return
    try:
        await query.answer()  # جواب خالی، فقط لودینگ دکمه قطع میشه بدون هیچ متنی
    except Exception:
        pass
    raise ApplicationHandlerStop()


_CMD_PREFIX_RE = re.compile(r"^تریاکی[\s\u200c]+([\s\S]+)$")


def strip_bot_cmd(text: str) -> str:
    """پیشوند «تریاکی » رو از روی متن دستور برمی‌داره، خود متن اگه پیشوند نداشت دست نمی‌خوره"""
    m = _CMD_PREFIX_RE.match((text or "").strip())
    return m.group(1).strip() if m else (text or "").strip()


async def respond(update: Update, text: str, markup=None, alert: str | None = None) -> None:
    """
    اگر پیام از کیبورد اومده همون رو ادیت می‌کنه وگرنه ریپلای میده
    اگر پیام عکسی باشه (مثل پروفایل) پاکش می‌کنه و دوباره می‌فرسته
    دکمه منوی اصلی هم تو گروه حذف میشه
    پیام‌های دکمه‌داری که تو گروه با دستور متنی ساخته میشن به اسم صاحبشون ثبت میشن
    """
    markup = strip_home(update, markup)
    query = update.callback_query
    if query:
        await query.answer(alert, show_alert=bool(alert))
        if getattr(query.message, "photo", None):
            try:
                await query.message.delete()
            except BadRequest:
                pass
            sent = await query.message.reply_html(text, reply_markup=markup)
            if markup is not None:
                track_message(
                    getattr(sent, "chat_id", None),
                    getattr(sent, "message_id", None),
                    update.effective_user.id if update.effective_user else None,
                )
        else:
            try:
                await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
            except BadRequest as e:
                if "not modified" not in str(e).lower():
                    raise
    else:
        sent = await update.effective_message.reply_html(text, reply_markup=markup)
        chat = update.effective_chat
        if markup is not None and chat is not None and chat.type in (ChatType.GROUP, ChatType.SUPERGROUP):
            track_message(
                getattr(sent, "chat_id", None) or chat.id,
                getattr(sent, "message_id", None),
                update.effective_user.id if update.effective_user else None,
            )


def parts(update: Update) -> list[str]:
    """تیکه‌های callback_data به ازای : """
    return update.callback_query.data.split(":")


def format_attack_result(result: dict, target_name: str) -> str:
    """متن نتیجه حمله، مشترک بین حمله منویی و حمله ریپلای تو گروه"""
    chance_line = ""
    if result.get("chance") is not None:
        pct = int(round(result["chance"] * 100))
        chance_line = f"\n🎯 شانس بردت {fa_num(pct)}% بود"

    crit_txt = " 💣 ضربه بحرانی!" if result.get("crit") else ""

    mods: list[str] = []
    if result.get("weather") and result["weather"] != "normal":
        import config as _cfg
        _w = _cfg.WEATHERS.get(result["weather"], {})
        if _w:
            mods.append(f"{_w['emoji']} {_w['name']}")
    if result.get("tbuff"):
        mods.append(f"🏰 ساختمان حمله تیمت +{fa_num(int(result['tbuff'] * 100))}%")
    if result.get("defcut"):
        mods.append(f"🐺 دفاعش -{fa_num(int(result['defcut'] * 100))}% خرد شد")
    if result.get("bonus"):
        mods.append(f"🐺 غرامت +{fa_num(int(result['bonus'] * 100))}%")
    if result.get("halved"):
        mods.append("🛡 زره افسانه‌ایش نصفش کرد")
    mods_line = ("\n" + " | ".join(mods)) if mods else ""

    if result["win"]:
        prize_line = (
            f"تو هم {money(result['amount'])} جایزه گرفتی"
            if result["amount"] else "ولی جیبش خالی بود بدبخت 🕳"
        )
        text = (
            "<b>✅ زدی تو خال</b>\n\n"
            f"آخ آخ {target_name} شکار شد\n"
            f"{prize_line}\n"
            f"💥 {fa_num(result.get('dmg', 0))} دمیج زدی بهش{crit_txt}\n"
            f"💪 قدرت تو {fa_num(result.get('a_pow', 0))} | قدرتش {fa_num(result.get('d_pow', 0))}{chance_line}{mods_line}\n"
            f"✨ {fa_num(result.get('xp', 0))} تجربه گرفتی"
        )
    else:
        text = (
            "<b>❌ له شدی</b>\n\n"
            f"ایبابا {target_name} حسابت رو رسوند\n"
            f"💥 {fa_num(result.get('dmg', 0))} دمیج ازش خوردی{crit_txt}\n"
            f"💪 قدرت تو {fa_num(result.get('a_pow', 0))} | قدرتش {fa_num(result.get('d_pow', 0))}{chance_line}{mods_line}\n"
            f"⚡ {fa_num(result.get('penalty', 0))} انرژی جریمه شدی\n"
            f"✨ {fa_num(result.get('xp', 0))} تجربت به چوخ رفت"
        )

    notes = result.get("notes") or []
    if notes:
        text += "\n\n" + "\n".join(notes)
    return text
