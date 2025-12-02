import asyncio
import logging
import os
from loader import dp, bot
from utils.db_api import create_db, ensure_language_column
from utils.set_bot_commands import set_only_start_everywhere
from config import ADMIN_IDS

log_path = os.path.join(os.path.dirname(__file__), 'bot.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_path, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

async def on_startup():
    logging.info("Бот запускается...")
    await create_db()
    await ensure_language_column()
    try:
        await set_only_start_everywhere()
    except Exception as e:
        logging.error(f"Ошибка установки команд: {e}")

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, "Бот запущен на Railway!")
        except Exception as e:
            logging.error(f"Не смог написать админу {admin_id}: {e}")

async def main():
    # Импортируем хэндлеры только после создания dp
    import handlers  # <-- просто импортируем папку, роутеры сами подключатся

    await on_startup()
    await dp.start_polling(bot, skip_updates=True)

if __name__ == '__main__':
    asyncio.run(main())