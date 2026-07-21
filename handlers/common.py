"""ابزار مشترک هندلرها"""

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import BadRequest

from utils import fa_num, money


async def respond(update: Update, text: str, markup=None, alert: str | None = None) -> None:
    """
    اگر پیام از کیبورد اومده همون رو ادیت می‌کنه وگرنه ریپلای میده
    alert هم اگر پر باشه به صورت پاپ‌آپ نشون داده میشه
    """
    query = update.callback_query
    if query:
        await query.answer(alert, show_alert=bool(alert))
        try:
            await query.edit_message_text(text, parse_mode=ParseMode.HTML, reply_markup=markup)
        except BadRequest as e:
            if "not modified" not in str(e).lower():
                raise
    else:
        await update.effective_message.reply_html(text, reply_markup=markup)


def parts(update: Update) -> list[str]:
    """تیکه‌های callback_data به ازای : """
    return update.callback_query.data.split(":")


def format_attack_result(result: dict, target_name: str) -> str:
    """متن نتیجه حمله — مشترک بین حمله منویی و حمله ریپلای تو گروه"""
    roll_line = f"🎲 تو {fa_num(result['a_roll'])} | اون {fa_num(result['d_roll'])}"

    mods: list[str] = []
    if result.get("bonus"):
        mods.append(f"🐺 بونس سگ +{fa_num(int(result['bonus'] * 100))}٪")
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
            f"{roll_line}{mods_line}\n"
            f"✨ {fa_num(result.get('xp', 0))} تجربه گرفتی"
        )
    else:
        text = (
            "<b>❌ له شدی داداش</b>\n\n"
            f"ایبابا {target_name} حسابت رو رسوند\n"
            f"{roll_line}{mods_line}\n"
            f"⚡ {fa_num(result.get('penalty', 0))} انرژی جریمه شدی\n"
            f"✨ {fa_num(result.get('xp', 0))} تجربت به چوخ رفت"
        )

    notes = result.get("notes") or []
    if notes:
        text += "\n\n" + "\n".join(notes)
    return text
