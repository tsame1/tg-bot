# Keyboards for payment selection
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_payment_menu():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("💸 Crypto", callback_data="crypto")
    )
    return keyboard

def get_crypto_menu():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("₿ Bitcoin", callback_data="bitcoin"),
        InlineKeyboardButton("Ξ Ethereum", callback_data="ethereum"),
        InlineKeyboardButton("◎ Solana", callback_data="solana"),
        InlineKeyboardButton("₮ USDT", callback_data="usdt")
    )
    return keyboard

def get_usdt_network_menu():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("TRC20", callback_data="TRC20"),
        InlineKeyboardButton("ERC20", callback_data="ERC20"),
        InlineKeyboardButton("BEP20", callback_data="BEP20"),
        InlineKeyboardButton("SOL", callback_data="SOL")
    )
    return keyboard