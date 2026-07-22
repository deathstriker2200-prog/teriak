"""
بک‌آپ و ری‌استور دیتابیس، فقط ادمین (مثل /admin به غریبه اصلا جواب نمیده)
/backup → فایل کامل دی‌بی رو می‌فرسته
/upload_backup → فایل رو می‌گیره و اگه سالم بود جایگزین می‌کنه (روی ولوم ذخیره میشه)
"""

import os
from datetime import datetime

from sqlalchemy import func, select
from telegram import Update
from telegram.ext import ContextTypes

import config
from database import session_scope
from models import Team, User
from services import backup, users
from utils import fa_num


def _is_admin(update: Update) -> bool:
    return bool(update.effective_user) and update.effective_user.id in config.ADMIN_IDS


async def backup_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return  # سکوت محض

    if not backup.backup_supported():
        return await update.effective_message.reply_html(
            "❌ دیتابیس SQLite نیس، بک‌آپ فایلی فقط روی SQLite کار می‌کنه"
        )

    async with session_scope() as s:
        n_users = (await s.execute(select(func.count(User.id)))).scalar_one()
        n_teams = (await s.execute(select(func.count(Team.id)))).scalar_one()

    try:
        snapshot = await backup.create_snapshot()
    except FileNotFoundError:
        return await update.effective_message.reply_html("❌ فایل دیتابیس پیدا نشد")

    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    caption = (
        f"💾 بک‌آپ کامل تریاکی\n"
        f"👥 {fa_num(n_users)} بازیکن | 🏴 {fa_num(n_teams)} تیم\n"
        f"🗓 {stamp}\n"
        f"برای برگردوندنش: /upload_backup بزن و همین فایل رو برگردون"
    )
    try:
        with open(snapshot, "rb") as f:
            await update.effective_message.reply_document(
                document=f,
                filename=f"teriaky-backup-{stamp}.db",
                caption=caption,
            )
    finally:
        os.remove(snapshot)


async def upload_backup_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_admin(update):
        return  # سکوت محض

    if not backup.backup_supported():
        return await update.effective_message.reply_html(
            "❌ دیتابیس SQLite نیس، بک‌آپ فایلی فقط روی SQLite کار می‌کنه"
        )

    context.user_data["await_backup"] = True
    await update.effective_message.reply_html(
        "<b>📤 آپلود بک‌آپ</b>\n\n"
        "فایل بک‌آپ رو همینجا بفرست (همون فایلی که /backup بهت داده)\n"
        "⚠️ اگه سالم باشه تمام اطلاعات فعلی ربات با اطلاعات فایل جایگزین میشه\n\n"
        "منصرف شدی بنویس «لغو بک‌آپ»"
    )


async def cancel_upload_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """«لغو بک‌آپ»، کنسل کردن حالت انتظار فایل"""
    if not _is_admin(update):
        return
    if (context.user_data or {}).pop("await_backup", False):
        await update.effective_message.reply_html("😅 بی‌خیال آپلود بک‌آپ شدیم")


async def backup_doc(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """گرفتن فایل بک‌آپ بعد از /upload_backup"""
    if not _is_admin(update):
        return
    if not (context.user_data or {}).pop("await_backup", False):
        return  # منتظر فایل نبودیم

    doc = update.effective_message.document
    if not doc:
        return await update.effective_message.reply_html("❌ فایل نفرستادی که ")

    if doc.file_size and doc.file_size > 25 * 1024 * 1024:
        return await update.effective_message.reply_html("❌ فایل خیلی گنده‌ست، دی‌بی این‌قدری نداریم")

    await update.effective_message.reply_html("⏳ دارم فایل رو بررسی می‌کنم...")

    try:
        tg_file = await doc.get_file()
        data = await tg_file.download_as_bytearray()
    except Exception:
        return await update.effective_message.reply_html("❌ دانلود فایل از تلگرام نشد، دوباره بفرست")

    ok, msg = await backup.restore_bytes(bytes(data))
    await update.effective_message.reply_html(f"<b>{msg}</b>")
