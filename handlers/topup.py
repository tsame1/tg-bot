# handlers/topup.py
# Handler for Top-up Balance button and payment processing
from aiogram import types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InputMediaPhoto
from loader import dp

from keyboards.payment import get_payment_menu, get_crypto_menu, get_usdt_network_menu
from keyboards.main_menu import get_main_menu
from utils.crypto_api import get_crypto_price
from utils.db_api import record_payment_request
from utils.i18n import tr  # локализация
from config import REVOLUT_PAYMENT_LINK, ADMIN_IDS, CRYPTO_WALLET_ADDRESS, CRYPTO_ADDRESSES
from .profile import profile_command
from .products import products_command
from .support import support_command
import os
import logging
import asyncio

# === берём pending_messages (id сообщения "ждите подтверждения")
# и payment_user_map (payment_id -> user_id) из admin
from handlers.admin import pending_messages, payment_user_map
# =================

# Пути к изображениям
PAYMENT_IMAGE = os.path.join("images", "payment.jpg")   # дефолт при входе в топап
REVOLUT_IMAGE = os.path.join("images", "revolut.jpg")   # при выборе Revolut
CRYPTO_IMAGE  = os.path.join("images", "crypto.jpg")    # при выборе Crypto (и дальше в крипто-ветке)

# НОВОЕ: отдельные картинки для монет
ETH_IMAGE = os.path.join("images", "eth.jpg")
BNB_IMAGE = os.path.join("images", "bnb.jpg")
SOL_IMAGE = os.path.join("images", "sol.jpg")
BTC_IMAGE = os.path.join("images", "btc.jpg")  # опционально, если используешь BTC

def get_crypto_image(crypto: str) -> str:
    """Возвращает путь к картинке выбранной монеты. USDT и неизвестные — общий CRYPTO_IMAGE."""
    c = (crypto or "").lower()
    mapping = {
        "eth": ETH_IMAGE, "ethereum": ETH_IMAGE,
        "bnb": BNB_IMAGE, "binancecoin": BNB_IMAGE,
        "sol": SOL_IMAGE, "solana": SOL_IMAGE,
        "btc": BTC_IMAGE, "bitcoin": BTC_IMAGE,
        "usdt": CRYPTO_IMAGE,
    }
    return mapping.get(c, CRYPTO_IMAGE)

# Определяем путь к файлу логов (рядом с этим скриптом)
log_file = os.path.join(os.path.dirname(__file__), 'bot.log')

logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


class TopupStates(StatesGroup):
    SelectMethod = State()
    EnterAmount = State()
    SelectCrypto = State()
    SelectUSDTNetwork = State()
    ConfirmPayment = State()


def get_crypto_address(crypto: str = None, network: str = None) -> str:
    """Возвращает адрес для указанной криптовалюты и сети"""
    if not crypto:
        return CRYPTO_WALLET_ADDRESS

    c = (crypto or "").lower()
    n = (network or "").lower() if network else None

    # соответствия названий
    aliases = {
        "bitcoin": "btc",
        "btc": "btc",
        "ethereum": "eth",
        "eth": "eth",
        "solana": "sol",
        "sol": "sol",
        "binancecoin": "bnb",
        "bnb": "bnb",
        "usdt_trc20": "usdt_trc20",
        "usdt_erc20": "usdt_erc20",
        "usdt_bep20": "usdt_bsc",
        "usdt_sol": "usdt_sol",
        "trc20": "usdt_trc20",
        "erc20": "usdt_erc20",
        "bep20": "usdt_bsc",
        "bsc": "usdt_bsc",
    }

    # если это USDT + сеть
    if c == "usdt" and n:
        key = aliases.get(n)
        return CRYPTO_ADDRESSES.get(key, CRYPTO_WALLET_ADDRESS)

    # обычные монеты
    key = aliases.get(c)
    return CRYPTO_ADDRESSES.get(key, CRYPTO_WALLET_ADDRESS)


async def edit_photo_or_text(msg: types.Message, image_path: str, caption: str, reply_markup=None):
    """
    Пытается заменить фото + подпись в существующем сообщении, если там фото.
    Если картинки нет на диске — просто меняет текст/подпись.
    Если в сообщении не фото — редактирует текст.
    """
    try:
        if msg.photo:
            # есть фото в сообщении — пробуем заменить медиа
            if os.path.exists(image_path):
                with open(image_path, "rb") as f:
                    media = InputMediaPhoto(f, caption=caption)
                    await msg.edit_media(media=media, reply_markup=reply_markup)
            else:
                # картинки нет — меняем только подпись
                await msg.edit_caption(caption=caption, reply_markup=reply_markup)
        else:
            # обычное сообщение — меняем текст
            await msg.edit_text(text=caption, reply_markup=reply_markup)
    except Exception as e:
        # если что-то не вышло — отправим новое сообщение с фото/текстом
        logger.debug(f"edit_photo_or_text fallback: {e}")
        try:
            if os.path.exists(image_path):
                with open(image_path, "rb") as f:
                    await msg.answer_photo(photo=f, caption=caption, reply_markup=reply_markup)
            else:
                await msg.answer(caption, reply_markup=reply_markup)
        except Exception as e2:
            logger.error(f"Unable to send fallback message: {e2}")


# реагируем на кнопку в 4 языках
@dp.message_handler(text=["💰 Top-up Balance", "💳 Пополнить баланс", "💳 Guthaben aufladen", "💳 Doładuj saldo"])
async def topup_command(message: types.Message, state: FSMContext):
    logger.info(f"User {message.from_user.id} pressed Top-up Balance, current state: {await state.get_state()}")
    try:
        await state.finish()

        caption = await tr(message.from_user.id, "topup_choose_method")
        image_unavailable = await tr(message.from_user.id, "image_unavailable")

        try:
            with open(PAYMENT_IMAGE, 'rb') as photo:
                await message.answer_photo(
                    photo=photo,
                    caption=caption,
                    reply_markup=get_payment_menu()
                )
        except FileNotFoundError:
            logger.error(f"Payment photo not found at {PAYMENT_IMAGE}")
            await message.answer(
                f"{caption}\n({image_unavailable})",
                reply_markup=get_payment_menu()
            )
        await TopupStates.SelectMethod.set()
    except Exception as e:
        logger.error(f"Error in topup_command for user {message.from_user.id}: {e}")
        await message.answer(await tr(message.from_user.id, "error_try_later"))
        await state.finish()


@dp.callback_query_handler(state=TopupStates.SelectMethod)
async def select_method(callback: types.CallbackQuery, state: FSMContext):
    logger.info(f"User {callback.from_user.id} selected payment method: {callback.data}, state: {await state.get_state()}")
    try:
        method = callback.data
        await state.update_data(method=method, crypto=None, network=None, amount=None, crypto_amount=None)

        prompt_amount = await tr(callback.from_user.id, "prompt_enter_amount")

        if method == "revolut":
            # Показать картинку Revolut + поле ввода суммы
            btn_cancel = await tr(callback.from_user.id, "cancel")
            kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(btn_cancel, callback_data="cancel_payment"))
            await edit_photo_or_text(callback.message, REVOLUT_IMAGE, prompt_amount, kb)
            await TopupStates.EnterAmount.set()
        else:
            # Показать картинку Crypto + выбор монеты
            text = await tr(callback.from_user.id, "choose_crypto")
            await edit_photo_or_text(callback.message, CRYPTO_IMAGE, text, get_crypto_menu())
            await TopupStates.SelectCrypto.set()

        await callback.answer()
    except Exception as e:
        logger.error(f"Error in select_method for user {callback.from_user.id}: {e}")
        await callback.message.answer(await tr(callback.from_user.id, "error_try_later"))
        await state.finish()
        await callback.answer()


@dp.callback_query_handler(state=TopupStates.SelectCrypto)
async def select_crypto(callback: types.CallbackQuery, state: FSMContext):
    logger.info(f"User {callback.from_user.id} selected crypto: {callback.data}, state: {await state.get_state()}")
    try:
        await state.update_data(crypto=callback.data)
        btn_cancel = await tr(callback.from_user.id, "cancel")
        if callback.data == "usdt":
            text = await tr(callback.from_user.id, "choose_usdt_network")
            # для USDT остаёмся на общей картинке
            await edit_photo_or_text(callback.message, CRYPTO_IMAGE, text, get_usdt_network_menu())
            await TopupStates.SelectUSDTNetwork.set()
        else:
            text = await tr(callback.from_user.id, "prompt_enter_amount")
            kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(btn_cancel, callback_data="cancel_payment"))
            # НОВОЕ: показываем картинку выбранной монеты
            coin_image = get_crypto_image(callback.data)
            await edit_photo_or_text(callback.message, coin_image, text, kb)
            await TopupStates.EnterAmount.set()
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in select_crypto for user {callback.from_user.id}: {e}")
        await callback.message.answer(await tr(callback.from_user.id, "error_try_later"))
        await state.finish()
        await callback.answer()


@dp.callback_query_handler(state=TopupStates.SelectUSDTNetwork)
async def select_usdt_network(callback: types.CallbackQuery, state: FSMContext):
    logger.info(f"User {callback.from_user.id} selected USDT network: {callback.data}, state: {await state.get_state()}")
    try:
        await state.update_data(network=callback.data)
        text = await tr(callback.from_user.id, "prompt_enter_amount")
        btn_cancel = await tr(callback.from_user.id, "cancel")
        kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(btn_cancel, callback_data="cancel_payment"))
        # для USDT продолжаем использовать общую картинку
        await edit_photo_or_text(callback.message, CRYPTO_IMAGE, text, kb)
        await TopupStates.EnterAmount.set()
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in select_usdt_network for user {callback.from_user.id}: {e}")
        await callback.message.answer(await tr(callback.from_user.id, "error_try_later"))
        await state.finish()
        await callback.answer()


@dp.message_handler(lambda m: m.text and (m.text.isdigit() or m.text.replace('.', '', 1).isdigit()), state=TopupStates.EnterAmount)
async def enter_amount(message: types.Message, state: FSMContext):
    logger.info(f"User {message.from_user.id} entered amount: {message.text}, state: {await state.get_state()}")
    try:
        amount = float(message.text)
        if amount <= 0:
            await message.answer(await tr(message.from_user.id, "enter_positive_amount"))
            return

        data = await state.get_data()
        method = data.get("method")
        crypto = data.get("crypto")
        network = data.get("network")

        crypto_amount = None
        if method != "revolut" and crypto:
            price = await get_crypto_price(crypto)
            if price > 0:
                if crypto == "usdt":
                    crypto_amount = round(amount / price, 2)
                else:
                    crypto_amount = round(amount / price, 6)

        await state.update_data(amount=amount, crypto_amount=crypto_amount)

        if method == "revolut":
            kb = types.InlineKeyboardMarkup(row_width=1)
            kb.add(
                types.InlineKeyboardButton(await tr(message.from_user.id, "revolut_open"), url=REVOLUT_PAYMENT_LINK),
                types.InlineKeyboardButton(await tr(message.from_user.id, "revolut_confirm_btn"), callback_data="confirm_revolut"),
                types.InlineKeyboardButton(await tr(message.from_user.id, "cancel"), callback_data="cancel_payment")
            )
            await message.answer(
                f"💳 <b>{await tr(message.from_user.id, 'revolut_payment_title')}</b>\n"
                f"{await tr(message.from_user.id, 'amount_label')}: <b>{amount} EUR</b>\n\n"
                f"{await tr(message.from_user.id, 'revolut_instruction')}",
                reply_markup=kb
            )
            await TopupStates.ConfirmPayment.set()
        else:
            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.add(
                types.InlineKeyboardButton(await tr(message.from_user.id, "confirm"), callback_data="confirm_payment"),
                types.InlineKeyboardButton(await tr(message.from_user.id, "cancel"), callback_data="cancel_payment")
            )
            address = get_crypto_address(crypto, network)
            crypto_amount_str = (
                f"{crypto_amount:.2f}" if (crypto == "usdt" and crypto_amount is not None)
                else (f"{crypto_amount:.6f}" if crypto_amount is not None else "N/A")
            )
            await message.answer(
                f"💰 <b>{await tr(message.from_user.id, 'payment_confirmation')}</b>\n"
                f"{await tr(message.from_user.id, 'method_label')}: {method}\n"
                f"{await tr(message.from_user.id, 'amount_label')}: {amount} EUR\n"
                f"{await tr(message.from_user.id, 'crypto_label')}: {crypto if crypto else 'N/A'}\n"
                f"{await tr(message.from_user.id, 'network_label')}: {network if network else 'N/A'}\n"
                f"{await tr(message.from_user.id, 'crypto_amount_label')}: {crypto_amount_str}\n"
                f"{await tr(message.from_user.id, 'address_label')}: <code>{address}</code>",
                reply_markup=kb
            )
            await TopupStates.ConfirmPayment.set()

    except ValueError:
        await message.answer(await tr(message.from_user.id, "enter_valid_number"))
    except Exception as e:
        logger.error(f"Error in enter_amount for user {message.from_user.id}: {e}")
        await message.answer(await tr(message.from_user.id, "error_try_later"))
        await state.finish()


@dp.callback_query_handler(lambda c: c.data == "confirm_revolut", state=TopupStates.ConfirmPayment)
async def confirm_revolut(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = callback.from_user.id
    method = data.get("method") or "revolut"
    amount = data.get("amount")

    try:
        if not amount:
            kb = types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton(await tr(user_id, "cancel"), callback_data="cancel_payment")
            )
            prompt_amount = await tr(user_id, "prompt_enter_amount")
            await edit_photo_or_text(callback.message, REVOLUT_IMAGE, prompt_amount, kb)
            await TopupStates.EnterAmount.set()
            await callback.answer(await tr(user_id, "enter_amount_first"))
            return

        # удаляем кнопки
        try:
            await callback.message.delete()
        except Exception:
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass

        payment_id = await record_payment_request(user_id, method, amount)

        # сохраняем payment_id -> user_id для уведомления при ОТКЛОНЕНИИ
        try:
            payment_user_map[payment_id] = user_id
        except Exception as e:
            logger.debug(f"Cannot map payment_id to user_id ({payment_id} -> {user_id}): {e}")

        notify_text = await tr(user_id, "payment_request_sent")
        wait_text = await tr(user_id, "wait_admin_confirm")
        notify_msg = await callback.message.answer(f"{notify_text} {wait_text}")
        pending_messages[user_id] = notify_msg.message_id  # сохраняем ID сообщения "ожидания"
        await state.update_data(notify_msg_id=notify_msg.message_id)

        # Сообщение админам (по-русски)
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            types.InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{payment_id}"),
            types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{payment_id}")
        )
        for admin_id in ADMIN_IDS:
            await dp.bot.send_message(
                admin_id,
                f"💰 Новый запрос на оплату (Revolut):\n"
                f"User ID: {user_id}\n"
                f"Method: {method}\n"
                f"Amount: {amount} EUR\n"
                f"Payment ID: {payment_id}",
                reply_markup=keyboard
            )
        logger.info(f"Revolut payment request {payment_id} sent to admins for user {user_id}")
        await state.finish()

    except Exception as e:
        logger.error(f"Error in confirm_revolut for user {user_id}: {e}")
        await callback.message.answer(await tr(user_id, "error_try_later"))
        await state.finish()
        await callback.answer()


@dp.callback_query_handler(lambda c: c.data == "confirm_payment", state=TopupStates.ConfirmPayment)
async def confirm_payment(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user_id = callback.from_user.id
    method = data.get("method")
    amount = data.get("amount")
    crypto = data.get("crypto")
    crypto_amount = data.get("crypto_amount")
    network = data.get("network")

    try:
        # удаляем кнопки
        try:
            await callback.message.delete()
        except Exception:
            try:
                await callback.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass

        payment_id = await record_payment_request(user_id, method, amount, crypto, crypto_amount, network)

        # сохраняем payment_id -> user_id для уведомления при ОТКЛОНЕНИИ
        try:
            payment_user_map[payment_id] = user_id
        except Exception as e:
            logger.debug(f"Cannot map payment_id to user_id ({payment_id} -> {user_id}): {e}")

        notify_text = await tr(user_id, "payment_request_sent")
        wait_text = await tr(user_id, "wait_admin_confirm")
        notify_msg = await callback.message.answer(f"{notify_text} {wait_text}")
        pending_messages[user_id] = notify_msg.message_id  # сохраняем ID сообщения "ожидания"
        await state.update_data(notify_msg_id=notify_msg.message_id)

        # Сообщение админам (по-русски)
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            types.InlineKeyboardButton("✅ Подтвердить", callback_data=f"confirm_{payment_id}"),
            types.InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{payment_id}")
        )
        crypto_amount_str = (
            f"{crypto_amount:.2f}" if (crypto == "usdt" and crypto_amount is not None)
            else (f"{crypto_amount:.6f}" if crypto_amount is not None else "N/A")
        )
        for admin_id in ADMIN_IDS:
            await dp.bot.send_message(
                admin_id,
                f"💰 Новый запрос на оплату:\n"
                f"User ID: {user_id}\n"
                f"Method: {method}\n"
                f"Amount: {amount} EUR\n"
                f"Crypto: {crypto if crypto else 'N/A'}\n"
                f"Crypto Amount: {crypto_amount_str}\n"
                f"Network: {network if network else 'N/A'}\n"
                f"Payment ID: {payment_id}",
                reply_markup=keyboard
            )
        logger.info(f"Payment request {payment_id} sent to admins for user {user_id}")
        await state.finish()

    except Exception as e:
        logger.error(f"Error in confirm_payment for user {user_id}: {e}")
        await callback.message.answer(await tr(user_id, "error_try_later"))
        await state.finish()
        await callback.answer()


@dp.callback_query_handler(lambda c: c.data == "cancel_payment", state='*')
async def cancel_payment(callback: types.CallbackQuery, state: FSMContext):
    logger.info(f"User {callback.from_user.id} cancelled payment, state: {await state.get_state()}")
    try:
        await callback.answer()
        try:
            await callback.message.delete()
        except Exception as e:
            logger.debug(f"Cannot delete payment message on cancel: {e}")
            try:
                if callback.message.photo:
                    await callback.message.edit_caption(caption="")
                else:
                    await callback.message.edit_text(text="")
            except Exception as e2:
                logger.debug(f"Cannot clear message on cancel: {e2}")

        # удаляем "ожидайте" если есть
        if callback.from_user.id in pending_messages:
            try:
                await dp.bot.delete_message(callback.from_user.id, pending_messages[callback.from_user.id])
            except Exception:
                pass
            pending_messages.pop(callback.from_user.id, None)

        await dp.bot.send_message(callback.from_user.id, await tr(callback.from_user.id, "payment_cancelled"))
        await state.finish()
    except Exception as e:
        logger.error(f"Error in cancel_payment for user {callback.from_user.id}: {e}")
        await callback.message.answer(await tr(callback.from_user.id, "error_try_later"))
        await state.finish()


@dp.callback_query_handler(lambda c: c.from_user.id not in ADMIN_IDS and not c.data.startswith(('confirm_', 'reject_', 'buy_', 'buy_confirm_')), state='*')
async def handle_stray_callbacks(callback: types.CallbackQuery, state: FSMContext):
    logger.warning(f"Stray callback received from user {callback.from_user.id}: {callback.data}, state: {await state.get_state()}")
    try:
        await callback.message.answer(
            await tr(callback.from_user.id, "invalid_action"),
            reply_markup=get_main_menu()
        )
        await state.finish()
        await callback.answer()
    except Exception as e:
        logger.error(f"Error in handle_stray_callbacks for user {callback.from_user.id}: {e}")
        await callback.answer()


@dp.message_handler(state='*')
async def handle_stray_messages(message: types.Message, state: FSMContext):
    logger.info(f"Handling stray message from user {message.from_user.id}: {message.text}, state: {await state.get_state()}")
    try:
        await asyncio.sleep(0.3)
        main_menu_commands = {
            "👨‍💻 Profile": profile_command,
            "🛒 Products": products_command,
            "📞 Support": support_command,
            "💰 Top-up Balance": topup_command,
            # на случай, если кнопки уже локализованы, можно добавить ещё варианты:
            "📁 Профиль": profile_command,
            "🛒 Товары": products_command,
            "📞 Поддержка": support_command,
            "💳 Пополнить баланс": topup_command,
            "📁 Profil": profile_command,
            "🛒 Produkte": products_command,
            "📞 Support": support_command,      # DE текст совпадает
            "💳 Guthaben aufladen": topup_command,
            "📁 Profil": profile_command,       # PL/DE одинаково пишут Profil
            "🛒 Produkty": products_command,
            "📞 Wsparcie": support_command,
            "💳 Doładuj saldo": topup_command
        }
        handler = main_menu_commands.get(message.text)
        if handler:
            await state.finish()
            await handler(message, state)
        else:
            await message.answer(
                await tr(message.from_user.id, "invalid_action"),
                reply_markup=get_main_menu()
            )
            await state.finish()
    except Exception as e:
        logger.error(f"Error in handle_stray_messages for user {message.from_user.id}: {e}")
        await message.answer(await tr(message.from_user.id, "error_try_later"))
        await state.finish()
