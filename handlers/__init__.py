# handlers/__init__.py — автоматически подключает все хэндлеры

from loader import dp

# Импортируем роутеры из всех файлов
from .start import router as start_router
from .profile import router as profile_router
from .support import router as support_router
from .products import router as products_router
from .topup import router as topup_router
from .admin import router as admin_router

# Подключаем их к диспетчеру
dp.include_router(start_router)
dp.include_router(profile_router)
dp.include_router(support_router)
dp.include_router(products_router)
dp.include_router(topup_router)
dp.include_router(admin_router)