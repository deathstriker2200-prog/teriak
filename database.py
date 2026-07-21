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
    """ساخت جداول (فاز اول بدون Alembic)"""
    from models import models as _models  # noqa: F401  (ثبت مدل‌ها روی metadata)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def session_scope():
    """اسکوپ session برای هندلرها — کامیت دستی لازم است"""
    async with SessionLocal() as session:
        yield session
