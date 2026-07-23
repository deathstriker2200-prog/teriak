"""
عضویت اجباری (فورس جوین) 🔒
کانال هدف و وضعیتش توی game_meta ذخیره میشه تا با ری‌استارت بمونه
ست و مدیریتش از پنل ادمینه، چک عضویت توی handlers/gate.py قبل از همه دستورها انجام میشه
"""

import re

from telegram.error import BadRequest, Forbidden

from models import GameMeta

_KEY_CHANNEL = "fj_channel"
_KEY_LINK = "fj_link"
_KEY_ON = "fj_on"

GATE_CB = "fj:check"


# ─────── ستینگ ───────

async def _get(session, key: str) -> str | None:
    row = await session.get(GameMeta, key)
    return row.value if row else None


async def _set(session, key: str, value: str) -> None:
    row = await session.get(GameMeta, key)
    if row:
        row.value = value
    else:
        session.add(GameMeta(key=key, value=value))


async def get_settings(session) -> dict:
    return {
        "channel": await _get(session, _KEY_CHANNEL),
        "link": await _get(session, _KEY_LINK),
        "on": (await _get(session, _KEY_ON)) == "1",
    }


async def is_active(session) -> bool:
    st = await get_settings(session)
    return bool(st["on"] and st["channel"])


async def set_channel(session, channel: str, link: str) -> None:
    await _set(session, _KEY_CHANNEL, channel)
    await _set(session, _KEY_LINK, link)
    await _set(session, _KEY_ON, "1")


async def clear_channel(session) -> None:
    await _set(session, _KEY_CHANNEL, "")
    await _set(session, _KEY_LINK, "")
    await _set(session, _KEY_ON, "0")


async def set_enabled(session, on: bool) -> None:
    await _set(session, _KEY_ON, "1" if on else "0")


def parse_input(text: str) -> tuple[str, str] | None:
    """
    ورودی ادمین رو به (channel, link) تبدیل می‌کنه، فرمت بد = None
    فرم‌های قابل قبول: @username | https://t.me/username | -100xxxxxxxxxx + لینک دعوت
    """
    parts = text.strip().split()
    if not parts:
        return None
    first = parts[0]
    extra = parts[1] if len(parts) > 1 else ""

    if first.startswith("@") and re.fullmatch(r"@[A-Za-z0-9_]{4,64}", first):
        return first, f"https://t.me/{first[1:]}"

    m = re.fullmatch(r"(?:https?://)?t\.me/([A-Za-z0-9_]{4,64})/?", first)
    if m:
        return f"@{m.group(1)}", f"https://t.me/{m.group(1)}"

    if re.fullmatch(r"-100\d{8,16}", first):
        link = extra if "t.me/" in extra else ""
        return (first, link) if link else None

    return None


def _chat_ref(channel: str):
    if channel.lstrip("-").isdigit():
        return int(channel)
    return channel


# ─────── چک عضویت ───────

async def is_member(bot, channel: str, user_id: int) -> bool:
    """عضویت کاربر توی کانال، هر خطایی یعنی عضو نیس (ربات باید ادمین کانال باشه)"""
    try:
        m = await bot.get_chat_member(_chat_ref(channel), user_id)
        return getattr(m, "status", "") in ("member", "administrator", "creator")
    except (BadRequest, Forbidden):
        return False
    except Exception:
        return False


# ─────── متن گیت ───────

def gate_text() -> str:
    return (
        "<b>🔒 عضویت اجباری</b>\n\n"
        "برای استفاده از ربات اول باید توی کانال زیر عضو بشی 📢\n\n"
        "عضو که شدی «✅ تایید عضویت» رو بزن تا ادامه همون دستورت برات اجرا بشه"
    )
