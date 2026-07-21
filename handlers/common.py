"""ابزار مشترک هندلرها"""

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import BadRequest


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
