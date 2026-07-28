"""اتصال دیتابیس — SQLAlchemy async روی SQLite (قابل سوییچ به PostgreSQL)"""

from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

import config


class Base(DeclarativeBase):
    pass


engine = create_async_engine(config.DATABASE_URL, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db() -> None:
    """ساخت جداول + مایگریشن سبک ستون‌های جدید روی دیتابیس قدیمی"""
    from models import models as _models  # noqa: F401  (ثبت مدل‌ها روی metadata)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_ensure_columns)
        await conn.run_sync(_migrate_data)


# ستون‌هایی که تو فازهای بعدی به جدول‌های موجود اضافه شدن
_NEW_COLUMNS = {
    "users": [
        ("last_harvest_at", "DATETIME"),
        ("feeds_used_today", "INTEGER NOT NULL DEFAULT 0"),
        ("feed_day", "VARCHAR(10)"),
        ("pending_action", "VARCHAR(16)"),
        ("pending_value", "VARCHAR(64)"),
        ("bank_balance", "INTEGER NOT NULL DEFAULT 0"),
        ("bank_level", "INTEGER NOT NULL DEFAULT 1"),
        ("shelter_level", "INTEGER NOT NULL DEFAULT 0"),
        ("last_search_at", "DATETIME"),
        ("last_casino_at", "DATETIME"),
        ("last_seen_at", "DATETIME"),
        ("shield_until", "DATETIME"),
        ("pv_attack_at", "DATETIME"),
        ("dq_date", "VARCHAR(10)"),
        ("dq_data", "VARCHAR(1024)"),
        ("hp", "INTEGER"),
        ("dead_until", "DATETIME"),
        ("wood", "INTEGER NOT NULL DEFAULT 0"),
        ("iron", "INTEGER NOT NULL DEFAULT 0"),
        ("axe_level", "INTEGER NOT NULL DEFAULT 1"),
        ("pick_level", "INTEGER NOT NULL DEFAULT 1"),
        ("lumber_level", "INTEGER NOT NULL DEFAULT 0"),
        ("ironmill_level", "INTEGER NOT NULL DEFAULT 0"),
        ("company_at", "DATETIME"),
        ("medals", "INTEGER NOT NULL DEFAULT 0"),
        ("medals_day", "INTEGER NOT NULL DEFAULT 0"),
        ("medals_day_date", "VARCHAR(10)"),
        ("medals_week", "INTEGER NOT NULL DEFAULT 0"),
        ("medals_week_id", "VARCHAR(10)"),
        ("fj_member_status", "INTEGER"),
        ("fj_checked_at", "DATETIME"),
        ("fj_left_at", "DATETIME"),
    ],
        "inventory": [
        ("level", "INTEGER NOT NULL DEFAULT 1"),
    ],
"plots": [
        ("built_at", "DATETIME"),
    ],
    "dogs": [
        ("personality", "VARCHAR(16)"),
        ("feeds_today", "INTEGER NOT NULL DEFAULT 0"),
        ("feed_day", "VARCHAR(10)"),
    ],
    "teams": [
        ("points", "INTEGER NOT NULL DEFAULT 0"),
        ("week_points", "INTEGER NOT NULL DEFAULT 0"),
        ("atk_bld", "INTEGER NOT NULL DEFAULT 0"),
        ("def_bld", "INTEGER NOT NULL DEFAULT 0"),
        ("level", "INTEGER NOT NULL DEFAULT 1"),
        ("xp", "INTEGER NOT NULL DEFAULT 0"),
    ],
    "team_members": [
        ("join_medals", "INTEGER NOT NULL DEFAULT 0"),
    ],
}

# ری‌نیم بذرها — ردیف‌های دیتابیس‌های قدیمی رو به کلید جدید منتقل می‌کنیم
_LEGACY_SEEDS = {"koka": "peyote", "ghat": "teriak"}


def _pg_type(coltype: str) -> str:
    """
    ترجمه نوع ستون برای پستگرس، فقط DATETIME به TIMESTAMP تبدیل میشه
    بقیه انواعی که تو _NEW_COLUMNS استفاده شدن (INTEGER، BIGINT، VARCHAR(n)) روی پستگرس هم معتبرن
    """
    head, _sep, tail = coltype.partition(" ")
    if head.upper() == "DATETIME":
        return f"TIMESTAMP {tail}".strip()
    return coltype


def _ensure_columns(sync_conn) -> None:
    """اگه دیتابیس قدیمی ستون جدید نداشت، با ALTER TABLE اضافه‌ش کن (SQLite و PostgreSQL)"""
    from sqlalchemy import text

    dialect = sync_conn.dialect.name
    for table, cols in _NEW_COLUMNS.items():
        if dialect == "postgresql":
            # پستگرس ADD COLUMN IF NOT EXISTS داره، پس چک دستی لازم نیس
            for name, coltype in cols:
                sync_conn.execute(
                    text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {name} {_pg_type(coltype)}")
                )
        else:
            rows = sync_conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
            existing = {r[1] for r in rows}
            for name, coltype in cols:
                if name not in existing:
                    sync_conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {coltype}"))


def _migrate_data(sync_conn) -> None:
    """مایگریشن دیتا — بذرهای قدیمی (کوکا/قات) به کلیدهای جدید + سقف لول ۲۰"""
    from sqlalchemy import text

    for old, new in _LEGACY_SEEDS.items():
        try:
            sync_conn.execute(text("UPDATE seed_stock SET seed_key=:n WHERE seed_key=:o"), {"n": new, "o": old})
            sync_conn.execute(text("UPDATE plots SET crop=:n WHERE crop=:o"), {"n": new, "o": old})
        except Exception:
            pass  # جدول هنوز نیس یا خطای جزئی — مهم نیس

    # نبرد HP: لول‌های بالاتر از سقف برمی‌گردن روی مکس
    try:
        import config as _cfg
        sync_conn.execute(
            text("UPDATE users SET level=:cap WHERE level > :cap"), {"cap": _cfg.MAX_LEVEL}
        )
    except Exception:
        pass


async def reload_engine(url: str | None = None) -> None:
    """
    موتور رو از نو می‌سازه — بعد از ری‌استور بک‌آپ استفاده میشه
    تا connectionهای قبلی روی فایل جدید سوار بشن
    """
    global engine, SessionLocal
    await engine.dispose()
    engine = create_async_engine(url or config.DATABASE_URL, echo=False, future=True)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    await init_db()


@asynccontextmanager
async def session_scope():
    """اسکوپ session برای هندلرها — کامیت دستی لازم است"""
    async with SessionLocal() as session:
        yield session
