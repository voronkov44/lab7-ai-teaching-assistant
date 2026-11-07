from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher

from config import load_config
from app.adapters.database import create_engine_and_sessions, ensure_schema
from app.adapters.ollama import OllamaClient
from app.handlers.router import router
from app.services.processor import ProcessingService


async def main() -> None:
    cfg = load_config()
    logging.basicConfig(
        level=cfg.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger = logging.getLogger(__name__)

    engine, sessions = create_engine_and_sessions(cfg)
    ollama = OllamaClient(
        base_url=cfg.ollama_base_url,
        model=cfg.ollama_model,
    )
    bot = Bot(token=cfg.bot_token)

    dp = Dispatcher()
    processor = ProcessingService(
        sessions=sessions,
        ollama=ollama,
    )
    dp["processor"] = processor
    dp.include_router(router)

    try:
        await ensure_schema(engine)
        logger.info("PostgreSQL connected; tables ready")

        await ollama.check_ready()
        logger.info(
            "Ollama connected; model=%s",
            cfg.ollama_model,
        )

        me = await bot.get_me()
        logger.info(
            "Telegram bot authorized: @%s",
            me.username,
        )

        await processor.process_new_on_startup()
        logger.info("Starting Telegram polling; waiting for messages")
        await dp.start_polling(bot)

    finally:
        await bot.session.close()
        await ollama.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
