"""ابزارهای کمکی: زمان | اعداد (لاتین) | فرمت مدت | escape"""

from datetime import datetime, timezone
from html import escape as _esc


def now_utc() -> datetime:
    """زمان UTC بدون tzinfo — مناسب ذخیره توی SQLite"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def fa(text) -> str:
    """متن آماده نمایش — اعداد لاتین می‌مونن"""
    return str(text)


def fa_num(n) -> str:
    """عدد با جداکننده هزارگان و ارقام لاتین مثل 12,500"""
    return f"{int(round(n)):,}"


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


# ───────── پردازش اسم فارسی (برای دستورهای متنی مثل «خرید چاقو») ─────────

def normalize_fa(text: str) -> str:
    """یکدست‌سازی متن فارسی برای مقایسه اسم‌ها"""
    t = (text or "")
    t = t.replace("ي", "ی").replace("ك", "ک")
    t = t.replace("‌", " ").replace("_", " ")
    t = t.replace("!", "").replace("؟", "")
    return " ".join(t.split())


def find_by_name(catalog: dict, query: str):
    """
    پیدا کردن آیتم از روی اسم — اول مچ دقیق بعد مچ جزئی
    خروجی: (key, item) یا (None, None)
    """
    q = normalize_fa(query)
    if not q:
        return None, None

    for key, item in catalog.items():
        if normalize_fa(item["name"]) == q:
            return key, item

    partial = [
        (key, item) for key, item in catalog.items()
        if q in normalize_fa(item["name"]) or normalize_fa(item["name"]).startswith(q)
    ]
    if len(partial) == 1:
        return partial[0]
    return None, None
