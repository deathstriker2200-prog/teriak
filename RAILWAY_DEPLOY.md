# 🚂 دیپلوی تریاکی روی Railway

آموزش قدم‌به‌قدم از صفر تا روشن شدن ربات — حدود ۱۰ دقیقه طول می‌کشه

---

## قدم ۰ — چی لازم داری

- اکانت [Railway](https://railway.app) (با گیت‌هاب لاگین کن)
- اکانت [GitHub](https://github.com)
- توکن ربات از [@BotFather](https://t.me/BotFather) → دستور `/newbot`

---

## قدم ۱ — پروژه رو ببر روی گیت‌هاب

```bash
unzip teriaky.zip && cd teriaky
git init
git add .
git commit -m "teriaky phase 1"
# یه ریپوی خالی تو گیت‌هاب بساز (بدون README) بعد:
git remote add origin https://github.com/USERNAME/teriaky.git
git push -u origin main
```

💡 فایل `.gitignore` جلوی رفتن `*.db` و `.env` رو می‌گیره پس دیتابیس و توکن لو نمیره

---

## قدم ۲ — ساخت پروژه تو Railway

1. تو داشبورد Railway بزن **New Project**
2. انتخاب کن **Deploy from GitHub repo**
3. ریپوی `teriaky` رو انتخاب کن

خود Railway با دیدن `requirements.txt` پایتونی بودنش رو تشخیص میده و با `railway.json` دستور استارت `python bot.py` ست میشه — هیچ کاری لازم نیست

> ربات با **Long Polling** کار می‌کنه پس به دامنه و پورت وب احتیاجی نیست — فقط پروسه زنده می‌مونه

---

## قدم ۳ — ساخت Volume (برای اینکه دیتابیس نپره) ⭐ مهم‌ترین قدم

SQLite روی دیسک فایل می‌سازه و دیسک Railway با هر ری‌دیپلوی ریست میشه — پس باید Volume بسازی:

1. برو تو **سرویس** ربات → تب **Settings**
2. پایین بیا تا **Volumes** → بزن **New Volume** (یا **Attach Volume**)
3. تو فیلد **Mount Path** بنویس: `/data`
4. ذخیره کن — railway خودش ری‌دیپلوی می‌کنه

از الان هر فایلی توی `/data` موندگاره

---

## قدم ۴ — تنظیم متغیرها (Variables)

توی سرویس → تب **Variables** این دو تا رو اضافه کن:

| کلید | مقدار |
|---|---|
| `TERIAKY_TOKEN` | توکن ربات از BotFather |
| `TERIAKY_DB` | `sqlite+aiosqlite:////data/teriaky.db` |

⚠️ دقت کن `TERIAKY_DB` چهار تا اسلش داره — سه تا برای URL و یکی برای مسیر absolute داخل `/data`

---

## قدم ۵ — تست

1. تب **Deployments** → لاگ‌ها رو باز کن
2. باید این دو خط رو ببینی:

```
دیتابیس آماده شد ✅
ربات تریاکی اومد بالا 🤖
```

3. برو تو تلگرام به ربات `/start` بزن 🎉

---

## قدم ۶ — فعال کردن گروه‌ها (مهم) ⚠️

تا «حمله» با ریپلای و دستورهای متنی مثل «خرید چاقو» تو گروه کار کنه باید Privacy Mode ربات خاموش باشه:

1. تو تلگرام برو به [@BotFather](https://t.me/BotFather)
2. بزن `/setprivacy` → رباتت رو انتخاب کن → **Disable**
3. اگه ربات رو قبلا به گروه اضافه کرده بودی: **حذفش کن و دوباره ادش کن** (تا تنظیم جدید اعمال بشه)

بدون این کار ربات فقط دستورهای اسلشی‌دار (`/`دار) رو تو گروه می‌بینه

---

## به‌روزرسانی بازی

```bash
git add . && git commit -m "update" && git push
```

Railway خودش اتوماتیک ری‌دیپلوی می‌کنه — دیتابیس تو Volume می‌مونه و هیچی پاک نمیشه

---

## نکته‌های مهم

- **دیتا فقط با حذف Volume پاک میشه** — پس مواظب دکمه Delete volume باش
- بکاپ دستی: توی ترمینال railway (یا با `railway run` لوکال) می‌تونی فایل `/data/teriaky.db` رو دانلود کنی
- پلن Hobby ماهی ۵ دلار اعتبار رایگان میده — این ربات با polling خیلی کم مصرفه و راحت جا میشه
- **آپگرید به PostgreSQL در آینده**: توی Railway دکمه **New → Database → PostgreSQL** رو بزن — خودش متغیر `DATABASE_URL` میسازه — بعد پکیج `asyncpg` رو به requirements اضافه کن و توی `config.py` مقدار `TERIAKY_DB` رو به اون متغیر وصل کن (اول `postgres://` رو به `postgresql+asyncpg://` تبدیل کن)

## مشکل دیدی؟

| علامت | دلیل احتمالی |
|---|---|
| `توکن ربات پیدا نشد` | متغیر `TERIAKY_TOKEN` ست نشده |
| ری‌استارت مداوم | توکن اشتباهه — تو لاگ خطای `Unauthorized` میبینی |
| بعد ری‌دیپلوی همه چی ریسته | Volume نساختی یا `TERIAKY_DB` به `/data` وصل نیست |
| ربات جواب نمیده | Services → سرویس Sleeping نباشه — تو لاگ آخرین خط رو چک کن |
