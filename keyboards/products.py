from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_product_menu(products: dict) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(row_width=1)
    for product_id, product in products.items():
        markup.add(
            InlineKeyboardButton(
                text=product["name"],
                callback_data=f"buy_{product_id}"
            )
        )
    return markup
