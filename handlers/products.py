# handlers/products.py
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto

from loader import dp
from keyboards.main_menu import get_main_menu
from utils.db_api import get_user_info, update_balance
from utils.i18n import tr  # локализация
from config import ADMIN_IDS

import os
import logging
from datetime import datetime

# чтобы уводить незареганных в старт
from handlers.start import start_command

try:
    from config import CURATOR_USERNAME
except Exception:
    CURATOR_USERNAME = "supcartel"

# Путь к картинке каталога
PRODUCTS_IMAGE = os.path.join("images", "products.jpg")

log_file = os.path.join(os.path.dirname(__file__), 'bot.log')
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


class Purchase(StatesGroup):
    choose_quantity = State()
    waiting_confirmation = State()


# Каталог (названия будут переводиться через ключи)
PRODUCTS = {
    "1": {"name_key": "product_1", "price": 100.0},
    "2": {"name_key": "product_2", "price": 200.0},
    "3": {"name_key": "product_3", "price": 300.0}
}


async def _is_registered(user_id: int) -> bool:
    """Есть ли пользователь в БД (считаем зарегистрированным)"""
    try:
        info = await get_user_info(user_id)
        return bool(info)
    except Exception:
        return False


async def _guard_or_start(message_or_cb, state: FSMContext) -> bool:
    """
    Возвращает True, если зарегистрирован и можно продолжать.
    Если не зарегистрирован — отправляет в /start и возвращает False.
    Поддерживает и message, и callback.
    """
    if isinstance(message_or_cb, types.CallbackQuery):
        user_id = message_or_cb.from_user.id
        msg = message_or_cb.message
    else:
        user_id = message_or_cb.from_user.id
        msg = message_or_cb

    if not await _is_registered(user_id):
        await start_command(msg, state)
        try:
            if isinstance(message_or_cb, types.CallbackQuery):
                await message_or_cb.answer()
        except Exception:
            pass
        return False
    return True


async def build_products_keyboard(user_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=1)
    for pid, p in PRODUCTS.items():
        product_name = await tr(user_id, p["name_key"])
        kb.add(InlineKeyboardButton(text=product_name, callback_data=f"select_{pid}"))
    return kb


async def build_quantity_keyboard(user_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardMarkup(row_width=5)
    kb.add(
        InlineKeyboardButton("1", callback_data="qty_1"),
        InlineKeyboardButton("2", callback_data="qty_2"),
        InlineKeyboardButton("3", callback_data="qty_3"),
        InlineKeyboardButton("4", callback_data="qty_4"),
        InlineKeyboardButton("5", callback_data="qty_5"),
    )
    kb.add(InlineKeyboardButton(await tr(user_id, "cancel"), callback_data="cancel_purchase"))
    return kb


async def edit_photo_or_text(msg: types.Message, image_path: str, caption: str, reply_markup=None):
    """
    Универсально обновляет сообщение с фото/текстом:
    - если в сообщении фото -> пытается заменить медиа и подпись
    - если фото-файла нет -> меняет только текст/подпись
    - если в сообщении не фото -> правит текст
    В случае ошибки — отправляет новое сообщение.
    """
    try:
        if msg.photo:
            if os.path.exists(image_path):
                with open(image_path, "rb") as f:
                    media = InputMediaPhoto(f, caption=caption)
                    await msg.edit_media(media=media, reply_markup=reply_markup)
            else:
                await msg.edit_caption(caption=caption, reply_markup=reply_markup)
        else:
            await msg.edit_text(text=caption, reply_markup=reply_markup)
    except Exception as e:
        logger.debug(f"edit_photo_or_text fallback: {e}")
        try:
            if os.path.exists(image_path):
                with open(image_path, "rb") as f:
                    await msg.answer_photo(photo=f, caption=caption, reply_markup=reply_markup)
            else:
                await msg.answer(caption, reply_markup=reply_markup)
        except Exception as e2:
            logger.error(f"Unable to send fallback message: {e2}")


@dp.message_handler(text="🛒 Products")
async def products_command(message: types.Message, state: FSMContext):
    # ✅ защита: незарегистрированных отправляем в /start
    if not await _guard_or_start(message, state):
        return

    await state.finish()
    caption = await tr(message.from_user.id, "choose_product")

    # Пытаемся отправить фото каталога, иначе — просто текст
    try:
        if os.path.exists(PRODUCTS_IMAGE):
            with open(PRODUCTS_IMAGE, "rb") as f:
                await message.answer_photo(
                    photo=f,
                    caption=caption,
                    reply_markup=await build_products_keyboard(message.from_user.id)
                )
        else:
            await message.answer(
                caption,
                reply_markup=await build_products_keyboard(message.from_user.id)
            )
    except Exception as e:
        logger.error(f"Cannot send products image: {e}")
        await message.answer(
            caption,
            reply_markup=await build_products_keyboard(message.from_user.id)
        )

@dp.callback_query_handler(lambda c: c.data.startswith("select_"), state="*")
async def select_product(callback: types.CallbackQuery, state: FSMContext):
    if not await _guard_or_start(callback, state):
        return

    product_id = callback.data.replace("select_", "")
    if product_id not in PRODUCTS:
        await callback.answer(await tr(callback.from_user.id, "product_not_found"))
        return

    await state.update_data(product_id=product_id, quantity=1)  # фиксируем qty=1
    product = PRODUCTS[product_id]
    product_name = await tr(callback.from_user.id, product["name_key"])
    total = round(product["price"], 2)
    await state.update_data(total=total)

    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton(await tr(callback.from_user.id, "confirm"), callback_data="confirm_final"),
        InlineKeyboardButton(await tr(callback.from_user.id, "cancel"), callback_data="cancel_purchase")
    )

    caption = (
        f"{await tr(callback.from_user.id, 'confirm_purchase')}\n"
        f"{await tr(callback.from_user.id, 'product_label')}: <b>{product_name}</b>\n"
        f"{await tr(callback.from_user.id, 'total_label')}: <b>{total} EUR</b>\n\n"
        f"{await tr(callback.from_user.id, 'confirm_or_cancel')}"
    )

    await Purchase.waiting_confirmation.set()
    await edit_photo_or_text(callback.message, PRODUCTS_IMAGE, caption, keyboard)
    await callback.answer()







@dp.callback_query_handler(lambda c: c.data == "confirm_final", state=Purchase.waiting_confirmation)
async def finalize_purchase(callback: types.CallbackQuery, state: FSMContext):
    # ✅ защита
    if not await _guard_or_start(callback, state):
        return

    try:
        data = await state.get_data()
        product_id = data.get("product_id")
        qty = int(data.get("quantity", 1) or 1)

        if not product_id or product_id not in PRODUCTS:
            await callback.message.answer(
                await tr(callback.from_user.id, "error_try_later"),
                reply_markup=get_main_menu()
            )
            await state.finish()
            return

        user_id = callback.from_user.id
        product = PRODUCTS[product_id]
        product_name = await tr(user_id, product["name_key"])
        unit_price = product["price"]
        total = round(unit_price * qty, 2)

        info = await get_user_info(user_id)
        balance = float(info.get("balance", 0.0) or 0.0)

        if balance < total:
            need = round(total - balance, 2)
            caption = (
                f"{await tr(user_id, 'insufficient_funds')}\n"
                f"{await tr(user_id, 'total_needed')}: <b>{total} EUR</b>\n"
                f"{await tr(user_id, 'your_balance')}: <b>{balance} EUR</b>\n"
                f"{await tr(user_id, 'missing_amount')}: <b>{need} EUR</b>\n\n"
                f"{await tr(user_id, 'topup_hint')}"
            )
            await edit_photo_or_text(callback.message, PRODUCTS_IMAGE, caption, None)
            await state.finish()
            await callback.answer()
            return

        await update_balance(user_id, -total)

        curator_at = f"@{CURATOR_USERNAME}" if CURATOR_USERNAME else "supcartel"
        caption = (
            f"{await tr(user_id, 'purchase_success')}\n"
            f"{await tr(user_id, 'product_label')}: <b>{product_name}</b>\n"
            f"{await tr(user_id, 'quantity_label')}: <b>{qty}</b>\n"
            f"{await tr(user_id, 'debited_amount')}: <b>{total} EUR</b>\n\n"
            f"{await tr(user_id, 'contact_curator')}: {curator_at}"
        )
        await edit_photo_or_text(callback.message, PRODUCTS_IMAGE, caption, None)

        # уведомление админам (по-русски)
        try:
            when = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            buyer = callback.from_user
            uname = f"@{buyer.username}" if buyer.username else "—"
            text = (
                "🛍 <b>Покупка подтверждена</b>\n"
                f"└ <b>User:</b> <code>{buyer.full_name}</code> ({uname})\n"
                f"└ <b>User ID:</b> <code>{buyer.id}</code>\n"
                f"└ <b>Товар:</b> <code>{product_name}</code>\n"
                f"└ <b>Кол-во:</b> <b>{qty}</b>\n"
                f"└ <b>Сумма:</b> <b>{total} EUR</b>\n"
                f"└ <b>Время:</b> <code>{when}</code>"
            )
            for admin_id in ADMIN_IDS:
                await dp.bot.send_message(admin_id, text)
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление админам: {e}")

        logger.info(f"User {user_id} bought {product_name} x{qty} for {total} EUR")
        await state.finish()
        await callback.answer()

    except Exception as e:
        logger.error(f"Error in finalize_purchase for user {callback.from_user.id}: {e}")
        try:
            await edit_photo_or_text(callback.message, PRODUCTS_IMAGE, await tr(callback.from_user.id, "error_try_later"))
        finally:
            await state.finish()
            await callback.answer()


@dp.callback_query_handler(lambda c: c.data == "cancel_purchase", state="*")
async def cancel_purchase(callback: types.CallbackQuery, state: FSMContext):
    # ✅ защита
    if not await _guard_or_start(callback, state):
        return

    try:
        # Сообщение «покупка отменена»
        await edit_photo_or_text(callback.message, PRODUCTS_IMAGE, await tr(callback.from_user.id, "purchase_cancelled"))
    except Exception:
        await callback.message.answer(await tr(callback.from_user.id, "purchase_cancelled"))

    # Снова открыть каталог
    caption = await tr(callback.from_user.id, "choose_product")
    kb = await build_products_keyboard(callback.from_user.id)
    await edit_photo_or_text(callback.message, PRODUCTS_IMAGE, caption, kb)

    await state.finish()
    await callback.answer()
