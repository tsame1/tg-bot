# Main menu keyboard
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_menu():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row(KeyboardButton("👨‍💻 Profile"), KeyboardButton("🛒 Products"))
    keyboard.row(KeyboardButton("💰 Top-up Balance"), KeyboardButton("📞 Support"))
    return keyboard