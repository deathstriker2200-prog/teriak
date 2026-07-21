"""ابزارهای کمکی: زمان | اعداد فارسی | فرمت مدت | escape"""

from datetime import datetime, timezone
from html import escape as _esc

_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def now_utc() -> datetime:
    """زمان UTC بدون tzinfo — مناسب ذخیره توی SQLite"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def fa(text) -> str:
    """تبدیل ارقام انگلیسی به فارسی"""
    return str(text).translate(_FA_DIGITS)


def fa_num(n) -> str:
    """عدد با جداکننده هزارگان و ارقام فارسی مثل ۱۲٬۵۰۰"""
    return f"{int(round(n)):,}".replace(",", "٬").translate(_FA_DIGITS)


def fa_dur(seconds: int | float) -> str:
    """فرمت مدت زمان به فارسی مثل «۲ ساعت و ۱۵ دقیقه»"""
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h and m:
        return f"{fa(h)} ساعت و {fa(m)} دقیقه"
    if h:
        return f"{fa(h)} ساعت"
    if m and s:
        return f"{fa(m)} دقیقه و {fa(s)} ثانیه"
    if m:
        return f"{fa(m)} دقیقه"
    return f"{fa(s)} ثانیه"


def esc(text) -> str:
    """escape برای تزریق امن اسم کاربرا توی HTML"""
    return _esc(str(text or ""))


# ───────── واحد پول ─────────
UNIT = "تی‌پوینت"
UNIT_SHORT = "TP"


def money(n) -> str:
    """مبلغ کامل برای متن پیام‌ها — مثل «۱۲٬۵۰۰ تی‌پوینت»"""
    return f"{fa_num(n)} {UNIT}"


def money_tp(n) -> str:
    """مبلغ خلاصه برای دکمه‌ها و لیست‌ها — مثل «۱۲٬۵۰۰ TP»"""
    return f"{fa_num(n)} {UNIT_SHORT}"
