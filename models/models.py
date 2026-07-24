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

    # بانک شخصی — پولی که اینجاست تو حمله دزدیده نمیشه
    bank_balance: Mapped[int] = mapped_column(Integer, default=0)
    bank_level: Mapped[int] = mapped_column(Integer, default=1)

    # پناهگاه — لول ۰ یعنی نداره | خسارت یورش پلیس رو کم می‌کنه
    shelter_level: Mapped[int] = mapped_column(Integer, default=0)

    # کولدونهای سیستم‌های جهان
    last_search_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_casino_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # آخرین فعالیت — یورش پلیس فقط به فعال‌های ۲۴ ساعت اخیر میاد
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # اکشن معلق بعدی متن کاربر — «dogname» (اسم سگ بعد خرید) | «teamname» (اسم تیم)
    pending_action: Mapped[str | None] = mapped_column(String(16), nullable=True)
    pending_value: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # مصونیت حمله پی‌وی — بعد اینکه بهت حمله شد تا این زمان از لیست حمله‌های پی‌وی خارجی (۱۲ ساعت)
    shield_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # نبرد HP گروهی — جان دائمی بین نبردها میمونه | NULL یعنی هنوز مقداردهی نشده (فول حساب میشه)
    hp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # بعد شکست تا این زمان بیهوشه، بعدش خودکار با HP فول زنده میشه
    dead_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # کوئست‌های روزانه، تاریخ به‌وقت ایران + JSON پیشرفت و جایزه‌ها
    dq_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    dq_data: Mapped[str | None] = mapped_column(String(1024), nullable=True)

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

    # زمان تموم شدن ساخت زمین — NULL یعنی ساخته شده و قابل استفاده‌ست
    built_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    status: Mapped[str] = mapped_column(String(16), default="empty")  # empty / growing / ready
    crop: Mapped[str | None] = mapped_column(String(32), nullable=True)
    planted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)

    user: Mapped[User] = relationship(back_populates="plots")

    def current_status(self) -> tuple[str, int]:
        """(وضعیت, ثانیه‌ی مونده) — اگر تایمر گذشته باشه خودکار ready حساب میشه"""
        if self.built_at:
            left = int((self.built_at - now_utc()).total_seconds())
            if left > 0:
                return "building", left
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

    # شخصیت سگ (وفادار/جنگجو/نگهبان/شکارچی/خوش‌شانس) — گرگ سیاه نداره
    personality: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # سهمیه غذای روزانه مخصوص خودش — هر روز ساعت ۱۲ شب (به‌وقت ایران) ریست میشه
    feeds_today: Mapped[int] = mapped_column(Integer, default=0)
    feed_day: Mapped[str | None] = mapped_column(String(10), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)

    user: Mapped[User] = relationship(back_populates="dogs")

    @property
    def cfg(self) -> dict:
        return config.DOGS.get(self.dog_key, {})


class Team(Base):
    """تیم — اسم یکتا + خزانه مشترک + آمار کوئست"""
    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(48))
    name_norm: Mapped[str] = mapped_column(String(48), unique=True, index=True)  # یکدست‌شده برای مقایسه
    bio: Mapped[str] = mapped_column(String(160), default="")
    bank: Mapped[int] = mapped_column(Integer, default=0)
    owner_id: Mapped[int] = mapped_column(Integer)  # users.id رهبر

    total_kills: Mapped[int] = mapped_column(Integer, default=0)
    total_harvests: Mapped[int] = mapped_column(Integer, default=0)

    # امتیاز تیم — با برد حمله و برداشت جمع میشه | هفتگی برای رقابت ریست میشه
    points: Mapped[int] = mapped_column(Integer, default=0)
    week_points: Mapped[int] = mapped_column(Integer, default=0)

    # ساختمان‌های تیم — رهبر با بانک تیم آپگریدشون می‌کنه و بونسش به همه اعضاست
    atk_bld: Mapped[int] = mapped_column(Integer, default=0)  # لول ساختمان حمله
    def_bld: Mapped[int] = mapped_column(Integer, default=0)  # لول ساختمان دفاع

    last_team_mine_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)

    members: Mapped[list["TeamMember"]] = relationship(back_populates="team", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Team {self.name} bank={self.bank}>"


class TeamMember(Base):
    """عضویت — هر کاربر فقط تو یه تیم می‌تونه باشه"""
    __tablename__ = "team_members"
    __table_args__ = (UniqueConstraint("user_id", name="uq_team_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(8), default="member")  # owner / member
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)

    team: Mapped[Team] = relationship(back_populates="members")
    user: Mapped[User] = relationship()


class TeamDaily(Base):
    """پیشرفت کوئست‌های روزانه تیم — هر روز UTC یه ردیف تازه"""
    __tablename__ = "team_daily"

    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), primary_key=True)
    day: Mapped[str] = mapped_column(String(10), primary_key=True)  # YYYY-MM-DD

    kills: Mapped[int] = mapped_column(Integer, default=0)
    harvests: Mapped[int] = mapped_column(Integer, default=0)
    kills_done: Mapped[int] = mapped_column(Integer, default=0)     # 1 = جایزه واریز شده
    harvests_done: Mapped[int] = mapped_column(Integer, default=0)


class GroupActivity(Base):
    """فعالیت گروه‌ها — اعلان آب و هوا (۱ ساعت اخیر) و اسپون کاروان (۱ روز اخیر) بر اساس اینه"""
    __tablename__ = "group_activity"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    last_active_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)
    last_caravan_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class GameMeta(Base):
    """کلید-مقدار سراسری بازی — مثل آخرین هفته پردازش‌شده رقابت تیم‌ها"""
    __tablename__ = "game_meta"

    key: Mapped[str] = mapped_column(String(32), primary_key=True)
    value: Mapped[str] = mapped_column(String(512), default="")


class SeenUser(Base):
    """
    کاربرانی که ربات پیامشون رو دیده (بیشتر تو گروه‌ها)
    برای حمله با @یوزرنیم به کسایی که هنوز ربات رو استارت نکردن
    """
    __tablename__ = "seen_users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    first_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)


class MessageOwner(Base):
    """
    صاحب هر پیام منو — برای قفل مالکیت دکمه‌ها که با ری‌استارت ربات پاک نشه
    """
    __tablename__ = "message_owners"

    chat_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    message_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    owner_tg: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now_utc)
