"""
مهاجرت دیتای تریاکی از SQLite به PostgreSQL، بدون از دست رفتن دیتای بازیکن‌ها

این اسکریپت به دیتابیس قدیمی (SQLite) و دیتابیس جدید (PostgreSQL) همزمان وصل میشه،
همه جدول‌ها رو به ترتیب وابستگی foreign key کپی می‌کنه و آخرش تعداد و محتوای
هر جدول رو دوطرفه چک می‌کنه تا مطمئن بشیم هیچی جا نمونده

اجرا (قبل از عوض کردن TERIAKY_DB روی Railway و بعد از خاموش کردن ربات):

    TERIAKY_MIGRATE_FROM="sqlite+aiosqlite:////data/teriaky.db" \
    TERIAKY_MIGRATE_TO="postgresql+asyncpg://USER:PASSWORD@HOST:PORT/DBNAME" \
    python migrate_to_postgres.py --yes

نکته‌ها:
    آدرس خام postgres:// یا postgresql:// ریلوی هم قبوله، خودش به postgresql+asyncpg تبدیلش می‌کنه
    مسیر خام فایل مثل /data/teriaky.db هم به جای آدرس مبدا قبوله
    اسکریپت idempotent عه، قبل از insert چک می‌کنه رکورد از قبل نباشه،
    پس اگه وسط کار خطا خورد با خیال راحت دوباره اجراش کن، ردیف تکراری نمی‌سازه
    فقط راستی‌آزمایی بدون کپی:  python migrate_to_postgres.py --verify-only
    هیچ رمزی تو این فایل نیس، آدرس‌ها فقط از متغیر محیطی یا آرگومان خط فرمان خونده میشن
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime

from sqlalchemy import inspect, select, text
from sqlalchemy.ext.asyncio import create_async_engine

import config
from database import Base, _ensure_columns
from models import models as _models  # noqa: F401  (ثبت همه مدل‌ها روی metadata)

_CHUNK = 500  # سایز بچ اینسرت


def _num(n) -> str:
    """عدد با جداکننده هزارگان (ارقام لاتین) برای لاگ خوانا"""
    return f"{int(n):,}"


def _mask(url: str) -> str:
    """آدرس برای چاپ توی لاگ، رمز لو نره"""
    if "://" in url and "@" in url:
        scheme, rest = url.split("://", 1)
        return f"{scheme}://***:***@{rest.split('@', 1)[1]}"
    return url


def norm_dt(v):
    """
    نرمالایز مقدار برای مقایسه بین دو دیالکت
    SQLite تاریخ رو رشته ذخیره می‌کنه و پستگرس datetime پس می‌ده، اینجا یکدست میشن
    """
    if isinstance(v, datetime):
        return v.replace(tzinfo=None)
    if isinstance(v, str) and len(v) >= 10 and v[4:5] == "-" and v[7:8] == "-":
        try:
            return datetime.fromisoformat(v)
        except ValueError:
            return v
    return v


def _table_order():
    """
    ترتیب کپی جداول، SQLAlchemy خودش با مرتب‌سازی توپولوژیک روی foreign keyها
    والدها رو قبل از بچه‌ها میذاره (کاربر قبل از زمین/سگ/تیم و…)
    """
    return Base.metadata.sorted_tables


async def _src_columns(engine, name: str):
    """ستون‌های موجود فعلی توی مبدا، اگه جدول اصلا نباشه None (بک‌آپ‌های خیلی قدیمی)"""
    async with engine.connect() as c:
        try:
            return await c.run_sync(lambda s: [col["name"] for col in inspect(s).get_columns(name)])
        except Exception:
            return None


async def _count(engine, name: str) -> int:
    async with engine.connect() as c:
        return int((await c.execute(text(f'SELECT COUNT(*) FROM "{name}"'))).scalar())


async def _rows(engine, q) -> list[dict]:
    async with engine.connect() as c:
        return [dict(r) for r in (await c.execute(q)).mappings().all()]


async def _flush(engine, table, batch: list[dict]) -> None:
    async with engine.begin() as c:
        await c.execute(table.insert(), batch)


async def _copy_table(src_e, dst_e, table, log) -> dict:
    """
    کپی یه جدول از مبدا به مقصد
    ردیف‌هایی که کلید اصلی‌شون از قبل تو مقصد هست رد میشن (idempotent)
    """
    name = table.name
    src_cols = await _src_columns(src_e, name)
    target_now = await _count(dst_e, name)
    if src_cols is None:
        log(f"⏭ {name}: این جدول تو مبدا نیس، رد شد")
        return {"table": name, "source": 0, "inserted": 0, "skipped": 0,
                "target": target_now, "missing": [], "extra": []}

    model_cols = {c.name for c in table.c}
    src_set = set(src_cols)
    use = [c for c in table.c if c.name in src_set]
    missing = [c.name for c in table.c if c.name not in src_set]
    extra = sorted(src_set - model_cols)
    if missing:
        log(f"⚠️ {name}: ستون‌های {missing} تو مبدا نیس، با مقدار پیش‌فرض مدل پر میشن")
    if extra:
        log(f"⚠️ {name}: ستون‌های {extra} تو مدل فعلی نیس و کپی نمیشن (دیتای اضافی مبدا)")

    pk = [c.name for c in table.primary_key.columns]
    async with dst_e.connect() as c:
        existing = {tuple(r) for r in (await c.execute(select(*[table.c[p] for p in pk]))).all()}

    inserted = skipped = 0
    batch: list[dict] = []
    sel = select(*use)
    async with src_e.connect() as c:
        stream = await c.stream(sel)
        async for row in stream.mappings():
            key = tuple(row[p] for p in pk)
            if key in existing:
                skipped += 1
                continue
            existing.add(key)
            batch.append({col.name: row[col.name] for col in use})
            if len(batch) >= _CHUNK:
                await _flush(dst_e, table, batch)
                inserted += len(batch)
                batch.clear()
    if batch:
        await _flush(dst_e, table, batch)
        inserted += len(batch)

    src_total = await _count(src_e, name)
    post = await _count(dst_e, name)
    mark = "✅" if post == src_total else "❌ ناهماهنگی"
    log(f"📦 {name}: مبدا {_num(src_total)} | مقصد قبل {_num(target_now)} | "
        f"کپی {_num(inserted)} | تکراری رد {_num(skipped)} | مقصد بعد {_num(post)} {mark}")
    return {"table": name, "source": src_total, "inserted": inserted,
            "skipped": skipped, "target": post, "missing": missing, "extra": extra}


async def _reset_sequences(dst_e, log) -> None:
    """
    مهم: بعد از کپی دستی idها سکوئنس‌های پستگرس عقب می‌مونن
    وگرنه اولین اینسرت اتوماتیک با UniqueViolation می‌ترکه
    """
    if dst_e.dialect.name != "postgresql":
        log("🔢 سکوئنس: مقصد پستگرس نیس، نیازی به تنظیم نیس")
        return
    async with dst_e.begin() as c:
        for table in _table_order():
            pk = list(table.primary_key.columns)
            if len(pk) != 1:
                continue
            col = pk[0]
            seq = (await c.execute(
                text("SELECT pg_get_serial_sequence(:t, :c)"), {"t": table.name, "c": col.name}
            )).scalar()
            if not seq:
                continue
            # GREATEST چون chat_id گروه‌ها منفیه و setval زیر 1 قبول نمی‌کنه
            maxid = int((await c.execute(
                text(f'SELECT GREATEST(1, COALESCE(MAX("{col.name}"), 0) + 1) FROM "{table.name}"')
            )).scalar())
            await c.execute(text("SELECT setval(:seq, :v, false)"), {"seq": seq, "v": maxid})
            log(f"🔢 سکوئنس {seq} تنظیم شد، شمارش بعدی از {_num(maxid)}")


async def _verify_tables(src_e, dst_e, log, deep: bool = True) -> bool:
    """
    راستی‌آزمایی: تعداد هر جدول دوطرفه + مقایسه دونه‌به‌دونه محتوای ردیف‌ها
    """
    ok_all = True
    for table in _table_order():
        name = table.name
        src_cols = await _src_columns(src_e, name)
        s_cnt = 0 if src_cols is None else await _count(src_e, name)
        d_cnt = await _count(dst_e, name)
        mark = "✅" if s_cnt == d_cnt else "❌"
        log(f"{mark} {name}: مبدا {_num(s_cnt)} ردیف | مقصد {_num(d_cnt)} ردیف")
        if s_cnt != d_cnt:
            ok_all = False
            continue
        if not deep or not s_cnt or src_cols is None:
            continue
        use = [c for c in table.c if c.name in set(src_cols)]
        pk = [c.name for c in table.primary_key.columns]
        q = select(*use).order_by(*[table.c[p] for p in pk])
        s_rows = await _rows(src_e, q)
        d_rows = await _rows(dst_e, q)
        s_map = {tuple(norm_dt(r[p]) for p in pk): r for r in s_rows}
        d_map = {tuple(norm_dt(r[p]) for p in pk): r for r in d_rows}
        bad = 0
        for key, sr in s_map.items():
            dr = d_map.get(key)
            if dr is None:
                bad += 1
                if bad <= 5:
                    log(f"   ⚠️ {name} کلید {key} تو مقصد نیس")
                continue
            for col in (c.name for c in use):
                if norm_dt(sr[col]) != norm_dt(dr[col]):
                    bad += 1
                    if bad <= 5:
                        log(f"   ⚠️ {name}.{col} کلید {key}: مبدا {sr[col]!r} مقصد {dr[col]!r}")
        extra_keys = set(d_map) - set(s_map)
        if extra_keys:
            bad += len(extra_keys)
            log(f"   ⚠️ {name}: {_num(len(extra_keys))} کلید فقط تو مقصد هست مثل {sorted(extra_keys)[:3]}")
        if bad:
            ok_all = False
        else:
            log(f"   🔍 {name}: {_num(len(s_map))} ردیف دونه‌به‌دونه یکی‌ان")
    return ok_all


async def migrate(source_url: str, target_url: str, *, verify_only: bool = False,
                  allow_any_target: bool = False, log=print) -> dict:
    """
    بدنه اصلی مهاجرت — خروجی گزارش با ok=True یعنی همه چیز سالم و کامل منتقل شده
    """
    report: dict = {"ok": False, "tables": [], "error": ""}
    src_url = config._normalize_db_url(source_url.strip())
    dst_url = config._normalize_db_url(target_url.strip())
    if src_url == dst_url:
        report["error"] = "آدرس مبدا و مقصد یکی‌ان، کپی روی خودش ممنوعه"
        log(f"❌ {report['error']}")
        return report
    if "postgresql" not in dst_url and not allow_any_target:
        report["error"] = "مقصد باید پستگرس باشه: postgresql+asyncpg://USER:PASSWORD@HOST:PORT/DBNAME"
        log(f"❌ {report['error']}")
        return report

    log(f"🛰 مبدا: {_mask(src_url)}")
    log(f"🎯 مقصد: {_mask(dst_url)}")

    src_e = create_async_engine(src_url, echo=False)
    dst_e = create_async_engine(dst_url, echo=False)
    try:
        async with src_e.connect() as c:
            await c.execute(text("SELECT 1"))
        async with dst_e.connect() as c:
            await c.execute(text("SELECT 1"))

        tables = _table_order()
        meta_names = {t.name for t in tables}
        expected = {"users", "teams", "plots", "inventory", "seed_stock", "dogs",
                    "team_members", "team_requests", "team_daily",
                    "group_activity", "game_meta", "seen_users", "message_owners"}
        if meta_names != expected:
            log(f"⚠️ لیست جداول مدل با لیست شناخته‌شده فرق داره: {sorted(meta_names ^ expected)}")

        if not verify_only:
            async with dst_e.begin() as c:
                await c.run_sync(Base.metadata.create_all)
                await c.run_sync(_ensure_columns)
            log("🏗 اسکیمای مقصد آماده شد (create_all + ستون‌های جدید)")
            for table in tables:
                rep = await _copy_table(src_e, dst_e, table, log)
                report["tables"].append(rep)
            await _reset_sequences(dst_e, log)

        log("🔍 راستی‌آزمایی شروع شد…")
        report["ok"] = await _verify_tables(src_e, dst_e, log)
        log("✅ مهاجرت کامل و سالمه، می‌تونی سوییچ کنی" if report["ok"]
            else "❌ ناهماهنگی پیدا شد، گزارش بالا رو بخون و دوباره با خیال راحت اجراش کن")
    finally:
        await src_e.dispose()
        await dst_e.dispose()
    return report


def _resolve_url(cli: str | None, env_name: str, fallback: str = "",
                 required: bool = False, role: str = "") -> str:
    raw = (cli or os.getenv(env_name, "") or fallback).strip()
    if not raw:
        if required:
            raise SystemExit(
                f"❌ آدرس {role} پیدا نشد، با آرگومان یا متغیر {env_name} بده\n"
                "مثال: TERIAKY_MIGRATE_TO=\"postgresql+asyncpg://USER:PASSWORD@HOST:PORT/DBNAME\""
            )
        return ""
    if "://" not in raw:
        # مسیر خام فایل SQLite مثل /data/teriaky.db
        raw = "sqlite+aiosqlite:///" + raw
    return config._normalize_db_url(raw)


def _parse(argv=None):
    p = argparse.ArgumentParser(description="مهاجرت دیتای تریاکی از SQLite به PostgreSQL")
    p.add_argument("--from", dest="src", default=None,
                   help="آدرس یا مسیر فایل دیتابیس قدیمی (پیش‌فرض: TERIAKY_MIGRATE_FROM یا TERIAKY_DB فعلی)")
    p.add_argument("--to", dest="dst", default=None,
                   help="آدرس پستگرس جدید (پیش‌فرض: TERIAKY_MIGRATE_TO)")
    p.add_argument("--verify-only", action="store_true",
                   help="فقط راستی‌آزمایی دو دیتابیس بدون کپی")
    p.add_argument("--yes", "-y", action="store_true",
                   help="بدون سوال تایید اجرا بشه (برای اجرای اسکریپتی)")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = _parse(argv)
    try:
        src = _resolve_url(args.src, "TERIAKY_MIGRATE_FROM",
                           os.getenv("TERIAKY_DB", "") or config.DATABASE_URL,
                           required=True, role="مبدا")
        dst = _resolve_url(args.dst, "TERIAKY_MIGRATE_TO",
                           os.getenv("TERIAKY_DB", "") if not args.src and not os.getenv("TERIAKY_MIGRATE_FROM") else "",
                           required=True, role="مقصد")
    except SystemExit as e:
        print(e)
        print("\nمثال کامل:")
        print("  python migrate_to_postgres.py \\")
        print("    --from sqlite+aiosqlite:////data/teriaky.db \\")
        print("    --to postgresql+asyncpg://USER:PASSWORD@HOST:PORT/DBNAME --yes")
        return 2

    asked = args.yes or os.getenv("TERIAKY_MIGRATE_YES", "").upper() in ("1", "YES", "TRUE")
    if not asked and not args.verify_only:
        print("⚠️ قبل از مهاجرت حتما باید سرویس ربات روی Railway خاموش (Stop) شده باشه")
        print("تا وسط کپی، هیچ نوشتن جدیدی روی SQLite قدیمی انجام نشه و دیتایی از قلم نیفته")
        try:
            ans = input("ربات خاموشه و مطمئنی؟ [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            ans = ""
        if ans not in ("y", "yes"):
            print("لغو شد. برای اجرای مستقیم از --yes استفاده کن")
            return 2

    report = asyncio.run(migrate(src, dst, verify_only=args.verify_only))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
