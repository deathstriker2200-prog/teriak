"""نقطه ورود ربات تریاکی — اجرا: python bot.py"""

import logging

from telegram import Update
from telegram.ext import Application

import config
from database import init_db
from handlers import register_handlers

logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)

logger = logging.getLogger("teriaky")


async def on_start(app: Application) -> None:
    await init_db()
    logger.info("دیتابیس آماده شد ✅")


def main() -> None:
    if not config.BOT_TOKEN:
        raise SystemExit(
            "❌ توکن ربات پیدا نشد\n"
            "متغیر محیطی TERIAKY_TOKEN رو تنظیم کن — نمونه توی .env.example هست"
        )

    app = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .post_init(on_start)
        .build()
    )
    register_handlers(app)

    logger.info("ربات تریاکی اومد بالا 🤖")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
