# loader.py — рабочий вариант под aiogram 3.13.1 + Railway 2025

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from config import BOT_TOKEN

# ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
# ВОТ ЭТА СТРОЧКА НОВАЯ — без неё падает
default_properties = DefaultBotProperties(parse_mode=ParseMode.HTML)

bot = Bot(token=BOT_TOKEN, default=default_properties)
# ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑

storage = MemoryStorage()
dp = Dispatcher(storage=storage)