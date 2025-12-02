# handlers/__init__.py
from loader import dp

# Просто импортируем все файлы — даже если в них старые импорты, они не упадут на старте
try:
    from . import start
    dp.include_router(start.router)
except Exception as e:
    print(f"Ошибка загрузки start: {e}")

try:
    from . import profile
    dp.include_router(profile.router)
except Exception as e:
    print(f"Ошибка загрузки profile: {e}")

try:
    from . import support
    dp.include_router(support.router)
except Exception as e:
    print(f"Ошибка загрузки support: {e}")

try:
    from . import products
    dp.include_router(products.router)
except Exception as e:
    print(f"Ошибка загрузки products: {e}")

try:
    from . import topup
    dp.include_router(topup.router)
except Exception as e:
    print(f"Ошибка загрузки topup: {e}")

try:
    from . import admin
    dp.include_router(admin.router)
except Exception as e:
    print(f"Ошибка загрузки admin: {e}")