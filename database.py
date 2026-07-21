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


# ستون‌هایی که تو فازهای بعدی به جدول‌های موجود اضافه شدن
_NEW_COLUMNS = {
    "users": [
        ("last_harvest_at", "DATETIME"),
        ("feeds_used_today", "INTEGER NOT NULL DEFAULT 0"),
        ("feed_day", "VARCHAR(10)"),
    ],
}


def _ensure_columns(sync_conn) -> None:
    """اگه دیتابیس قدیمی ستون جدید نداشت، با ALTER TABLE اضافه‌ش کن"""
    from sqlalchemy import text

    for table, cols in _NEW_COLUMNS.items():
        rows = sync_conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
        existing = {r[1] for r in rows}
        for name, coltype in cols:
            if name not in existing:
                sync_conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {coltype}"))


@asynccontextmanager
async def session_scope():
    """اسکوپ session برای هندلرها — کامیت دستی لازم است"""
    async with SessionLocal() as session:
        yield session
