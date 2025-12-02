from aiogram import executor
from loader import dp
from utils.db_api import create_db, ensure_language_column
from utils.set_bot_commands import set_only_start_everywhere  # только /start глобально
from config import ADMIN_IDS
# Регистрируем все хэндлеры (важно импортировать, чтобы они повесились на dp)
from handlers import start, profile, support, products, topup, admin
import logging
import os

# Логи рядом с приложением
log_path = os.path.join(os.path.dirname(__file__), 'bot.log')
logging.basicConfig(filename=log_path, level=logging.INFO)


async def on_startup(_):
    print("Starting bot...")
    # 1) Инициализация БД
    await create_db()
    # 2) Добавляем колонку language, если её нет
    await ensure_language_column()
    # 3) Устанавливаем глобальные команды: ТОЛЬКО /start (во всех локалях + fallback)
    try:
        await set_only_start_everywhere(dp)
    except Exception as e:
        logging.error(f"[startup] Failed to set only-start commands globally: {e}")

    logging.info("Database initialized, language ensured, only-start commands set. Bot started.")

    # 4) Оповещение админов о запуске (необязательно)
    for admin_id in ADMIN_IDS:
        try:
            await dp.bot.send_message(admin_id, "🤖 Бот успешно запущен!")
        except Exception as e:
            logging.error(f"Failed to notify admin {admin_id}: {e}")


if __name__ == '__main__':
    # Пропускаем старые апдейты
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
