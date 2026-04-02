from aiogram import Router

from .shop import router as shop_router
from .user_menu import router as user_menu_router

router = Router(name="users")
router.include_router(user_menu_router)
router.include_router(shop_router)

__all__ = ["router"]
