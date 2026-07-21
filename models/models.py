"""مدل‌های دیتابیس تریاکی — فاز ۲"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

import config
from database import Base
from utils import now_utc


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    level: Mapped[int] = mapped_column(Integer, default=1)
    xp: Mapped[int] = mapped_column(Integer, default=0)
    cash: Mapped[int] = mapped_column(Integer, default=config.START_CASH)
    energy: Mapped[int] = mapped_column(Integer, default=config.MAX_ENERGY)
    energy_updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)

    wins: Mapped[int] = mapped_column(Integer, default=0)
    losses: Mapped[int] = mapped_column(Integer, default=0)

    last_attack_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_mine_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_harvest_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # محدودیت روزانه غذای سگ
    feeds_used_today: Mapped[int] = mapped_column(Integer, default=0)
    feed_day: Mapped[str | None] = mapped_column(String(10), nullable=True)  # YYYY-MM-DD

    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)

    plots: Mapped[list["Plot"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    items: Mapped[list["InventoryItem"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    dogs: Mapped[list["Dog"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    seeds: Mapped[list["SeedStock"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User {self.telegram_id} lvl={self.level} cash={self.cash}>"


class Plot(Base):
    __tablename__ = "plots"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    level: Mapped[int] = mapped_column(Integer, default=1)

    status: Mapped[str] = mapped_column(String(16), default="empty")  # empty / growing / ready
    crop: Mapped[str | None] = mapped_column(String(32), nullable=True)
    planted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)

    user: Mapped[User] = relationship(back_populates="plots")

    def current_status(self) -> tuple[str, int]:
        """(وضعیت, ثانیه‌ی مونده) — اگر تایمر گذشته باشه خودکار ready حساب میشه"""
        if self.status == "growing" and self.ready_at:
            left = int((self.ready_at - now_utc()).total_seconds())
            if left <= 0:
                return "ready", 0
            return "growing", left
        return self.status, 0


class InventoryItem(Base):
    """سلاح‌ها و زره‌های خریداری‌شده"""
    __tablename__ = "inventory"
    __table_args__ = (UniqueConstraint("user_id", "item_key", name="uq_user_item"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    item_key: Mapped[str] = mapped_column(String(32))
    bought_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)

    user: Mapped[User] = relationship(back_populates="items")


class SeedStock(Base):
    """انبار بذر کاربر — خرید بذر زیادش می‌کنه | کاشت کمش می‌کنه"""
    __tablename__ = "seed_stock"
    __table_args__ = (UniqueConstraint("user_id", "seed_key", name="uq_user_seed"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    seed_key: Mapped[str] = mapped_column(String(32))
    count: Mapped[int] = mapped_column(Integer, default=0)

    user: Mapped[User] = relationship(back_populates="seeds")


class Dog(Base):
    """سگ‌های کاربر — هر نژاد یه بار قابل خریده"""
    __tablename__ = "dogs"
    __table_args__ = (UniqueConstraint("user_id", "dog_key", name="uq_user_dog"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    dog_key: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(64))
    breed: Mapped[str] = mapped_column(String(64))

    level: Mapped[int] = mapped_column(Integer, default=1)
    xp: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)

    user: Mapped[User] = relationship(back_populates="dogs")

    @property
    def cfg(self) -> dict:
        return config.DOGS.get(self.dog_key, {})
