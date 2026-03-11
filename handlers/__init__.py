from aiogram import Router

from handlers import cancel, onboarding, profile, feed, chat, settings

def setup_routers() -> Router:
    root = Router()
    root.include_router(cancel.router)
    root.include_router(onboarding.router)
    root.include_router(profile.router)
    root.include_router(feed.router)
    root.include_router(chat.router)
    root.include_router(settings.router)
    return root
