"""Entry point: long polling, webhook option, init DB, destiny worker."""
import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import get_config
from db.database import init_db
from handlers import setup_routers
from bot.middleware import IdempotencyMiddleware
from services.destiny_queue import start_destiny_worker, set_destiny_bot

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def main() -> None:
    config = get_config()
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.update.outer_middleware(IdempotencyMiddleware())
    dp.include_router(setup_routers())

    await init_db()
    set_destiny_bot(bot)
    worker_task = start_destiny_worker()
    retention_task = None
    if getattr(config, "messages_retention_months", 0) > 0:
        from services.message_retention import retention_loop
        retention_task = asyncio.create_task(retention_loop(config.messages_retention_months))

    if config.webhook_host and config.webhook_path:
        from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
        from aiohttp import web
        await bot.set_webhook(f"{config.webhook_host}{config.webhook_path}")
        app = web.Application()
        webhook_requests = SimpleRequestHandler(dispatcher=dp, bot=bot)
        webhook_requests.register(app, path=config.webhook_path)
        setup_application(app, dp, bot=bot)

        async def on_shutdown(_app):
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass
            if retention_task:
                retention_task.cancel()
                try:
                    await retention_task
                except asyncio.CancelledError:
                    pass

        app.on_shutdown.append(on_shutdown)
        web.run_app(app, host="0.0.0.0", port=8080)
    else:
        logger.info("Starting long polling")
        try:
            await dp.start_polling(bot)
        finally:
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass
            if retention_task:
                retention_task.cancel()
                try:
                    await retention_task
                except asyncio.CancelledError:
                    pass


if __name__ == "__main__":
    asyncio.run(main())
