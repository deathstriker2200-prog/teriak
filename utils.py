"""ابزارهای کمکی: زمان | اعداد (لاتین) | فرمت مدت | escape"""

from datetime import datetime, timedelta, timezone
from html import escape as _esc


def now_utc() -> datetime:
    """زمان UTC بدون tzinfo — مناسب ذخیره توی SQLite"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


_IRAN_OFFSET = timedelta(hours=3, minutes=30)


def now_iran() -> datetime:
    """زمان ایران (UTC+3:30 ثابت)"""
    return now_utc() + _IRAN_OFFSET


def iran_today() -> str:
    """تاریخ امروز به‌وقت ایران — مبنای ریست ساعت ۱۲ شب (سهمیه غذای سگ)"""
    return now_iran().date().isoformat()


def gregorian_to_jalali(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    """تبدیل میلادی به شمسی — بدون هیچ دیپندنسی (الگوریتم کلاسیک jdf)"""
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy - 1600
    gm2 = gm - 1
    gd2 = gd - 1
    day_no = 365 * gy2 + (gy2 + 3) // 4 - (gy2 + 99) // 100 + (gy2 + 399) // 400
    if gm2 > 1 and ((gy2 % 4 == 0 and gy2 % 100 != 0) or (gy2 % 400 == 0)):
        day_no += 1
    day_no += g_d_m[gm2] + gd2
    j_day_no = day_no - 79
    j_np = j_day_no // 12053
    j_day_no %= 12053
    jy = 979 + 33 * j_np + 4 * (j_day_no // 1461)
    j_day_no %= 1461
    if j_day_no >= 366:
        jy += (j_day_no - 1) // 365
        j_day_no = (j_day_no - 1) % 365
    if j_day_no < 186:
        jm = 1 + j_day_no // 31
        jd = 1 + j_day_no % 31
    else:
        jm = 7 + (j_day_no - 186) // 30
        jd = 1 + (j_day_no - 186) % 30
    return jy, jm, jd


def jalali_str(dt: datetime) -> str:
    """تاریخ شمسی با ارقام لاتین — مثل 1405/05/01"""
    jy, jm, jd = gregorian_to_jalali(dt.year, dt.month, dt.day)
    return f"{jy}/{jm:02d}/{jd:02d}"


def iran_clock() -> str:
    """ساعت ایران — مثل 23:45"""
    n = now_iran()
    return f"{n.hour:02d}:{n.minute:02d}"


def fa(text) -> str:
    """متن آماده نمایش — اعداد لاتین می‌مونن"""
    return str(text)


def fa_num(n) -> str:
    """عدد با جداکننده هزارگان و ارقام لاتین مثل 12,500"""
    return f"{int(round(n)):,}"


def bar(cur: int, total: int, cells: int = 10) -> str:
    """نوار پر و خالی با ▰▱ — مثل ▰▰▰▰▰▰▰▰▰▱"""
    total = max(total, 1)
    filled = round(min(cur, total) / total * cells)
    return "▰" * filled + "▱" * (cells - filled)


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


# ───────── پارس مبلغ از متن (واریز ۱۲۰۰ | واریز 1200) ─────────
_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def parse_amount(text: str) -> int | None:
    """عدد مثبت از متن کاربر — فارسی/عربی/لاتین با کاما هم قبوله — غلط → None"""
    t = str(text or "").translate(_FA_DIGITS)
    t = t.replace(",", "").replace("٬", "").replace(" ", "").replace("‌", "")
    if not t.isdigit():
        return None
    n = int(t)
    return n if n > 0 else None


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


# ───────── اسم فانتزی پروفایل ─────────
# حروف لاتین به Mathematical Bold Script (مثل 𝑅𝒶𝓅𝒾𝓉)، فارسی و بقیه دست نمی‌خورن
# R بولد اسکریپت تو یونیکد نداره، طبق نمونه پروفایل از 𝑅 استفاده میشه
_SCRIPT_UPPER = "𝒜ℬ𝒞𝒟ℰℱ𝒢ℋℐ𝒥𝒦ℒℳ𝒩𝒪𝒫𝒬𝑅𝒮𝒯𝒰𝒱𝒲𝒳𝒴𝒵"
_SCRIPT_LOWER = "𝒶𝒷𝒸𝒹ℯ𝒻ℊ𝒽𝒾𝒿𝓀𝓁𝓂𝓃ℴ𝓅𝓆𝓇𝓈𝓉𝓊𝓋𝓌𝓍𝓎𝓏"


def fancy_name(name: str) -> str:
    """اسم رو با فونت فانتزی لاتین می‌نویسه، حروف فارسی و ایموجی همون میمونن"""
    out: list[str] = []
    for ch in name or "":
        if "A" <= ch <= "Z":
            out.append(_SCRIPT_UPPER[ord(ch) - 65])
        elif "a" <= ch <= "z":
            out.append(_SCRIPT_LOWER[ord(ch) - 97])
        else:
            out.append(ch)
    return "".join(out)
