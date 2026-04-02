from aiogram import Router

from .users import router as users_router

router = Router(name="root")
router.include_router(users_router)

__all__ = ["router"]
