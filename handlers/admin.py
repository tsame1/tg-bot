# handlers/admin.py
from aiogram import types
from aiogram.dispatcher import FSMContext
from loader import dp, bot
from keyboards.main_menu import get_main_menu
from utils.db_api import confirm_payment, reject_payment, get_user_info
from config import ADMIN_IDS
from utils.i18n import tr
import os
import logging

# Сообщения «ожидайте подтверждения» и карта payment_id → user_id
pending_messages = {}
payment_user_map = {}

# Попробуем взять контакт администратора (для хвоста в уведомлении об отклонении)
try:
    from config import SUPPORT_USERNAME
except Exception:
    SUPPORT_USERNAME = None

try:
    from config import ADMIN_CONTACT_USERNAME
except Exception:
    ADMIN_CONTACT_USERNAME = None

try:
    from config import CURATOR_USERNAME
except Exception:
    CURATOR_USERNAME = None

log_file = os.path.join(os.path.dirname(__file__), 'bot.log')

logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


@dp.callback_query_handler(lambda c: c.from_user.id in ADMIN_IDS and c.data.startswith('confirm_'), state='*')
async def confirm_payment_handler(callback: types.CallbackQuery, state: FSMContext):
    logger.info(f"Admin {callback.from_user.id} confirming payment: {callback.data}, state: {await state.get_state()}")
    try:
        payment_id = callback.data.replace('confirm_', '')

        user_id, amount, new_balance = await confirm_payment(payment_id)

        if user_id:
            try:
                await callback.message.delete()
            except Exception as e:
                logger.warning(f"Не удалось удалить сообщение админки: {e}")

            await callback.message.answer(
                f"✅ <b>Платёж {payment_id} подтверждён.</b>",
                reply_markup=get_main_menu()
            )

            if new_balance is None:
                try:
                    info = await get_user_info(user_id)
                    new_balance = info.get("balance", 0.0)
                except Exception as e:
                    logger.error(f"Не удалось получить новый баланс пользователя {user_id}: {e}")

            try:
                if user_id in pending_messages:
                    await bot.delete_message(chat_id=user_id, message_id=pending_messages[user_id])
                    pending_messages.pop(user_id, None)
            except Exception as e:
                logger.warning(f"Не удалось удалить сообщение ожидания у пользователя {user_id}: {e}")

            try:
                lines = [
                    await tr(user_id, "payment_confirmed"),
                    await tr(user_id, "balance_topped_up", amount=amount)
                ]
                if new_balance is not None:
                    lines.append(await tr(user_id, "current_balance", balance=new_balance))

                await bot.send_message(user_id, "\n".join(lines), reply_markup=get_main_menu())
                logger.info(f"Client {user_id} notified about confirmed payment {payment_id}")
            except Exception as e:
                logger.error(f"Ошибка при отправке уведомления пользователю {user_id}: {e}")

            await callback.answer()
        else:
            await bot.send_message(
                callback.from_user.id,
                await tr(callback.from_user.id, "payment_not_found")
            )
            logger.error(f"Payment {payment_id} not found or already processed by admin {callback.from_user.id}")
            await callback.answer()
    except Exception as e:
        logger.error(f"Error in confirm_payment_handler for admin {callback.from_user.id}: {e}")
        try:
            await bot.send_message(
                callback.from_user.id,
                await tr(callback.from_user.id, "error_check_payment")
            )
        except Exception:
            pass
        await state.finish()
        await callback.answer()


@dp.callback_query_handler(lambda c: c.from_user.id in ADMIN_IDS and c.data.startswith('reject_'), state='*')
async def reject_payment_handler(callback: types.CallbackQuery, state: FSMContext):
    logger.info(f"Admin {callback.from_user.id} rejecting payment: {callback.data}, state: {await state.get_state()}")
    try:
        payment_id = callback.data.replace('reject_', '')

        result = await reject_payment(payment_id)
        if isinstance(result, tuple):
            success, user_id = result
        else:
            success, user_id = result, None

        if not user_id:
            user_id = payment_user_map.pop(payment_id, None)

        if success:
            try:
                await callback.message.delete()
            except Exception as e:
                logger.warning(f"Не удалось удалить сообщение админки: {e}")

            await callback.message.answer(
                f"❌ <b>Платёж {payment_id} отклонён.</b>",
                reply_markup=get_main_menu()
            )

            if user_id:
                try:
                    if user_id in pending_messages:
                        await bot.delete_message(chat_id=user_id, message_id=pending_messages[user_id])
                        pending_messages.pop(user_id, None)
                except Exception as e:
                    logger.warning(f"Не удалось удалить сообщение ожидания у пользователя {user_id}: {e}")

                # Переводим первую строку
                try:
                    base = await tr(user_id, "payment_rejected_plain")
                except Exception:
                    base = "❌ Your payment was rejected by the administrator."

                # Определяем язык
                try:
                    from utils.db_api import get_user_language
                    lang = (await get_user_language(user_id)) or "ru"
                except Exception:
                    lang = "ru"

                extra_by_lang = {
                    "ru": "Если считаете, что это ошибка — свяжитесь с администрацией",
                    "en": "If you believe this is a mistake, please contact the administration",
                    "de": "Wenn Sie glauben, dass dies ein Fehler ist, wenden Sie sich bitte an die Administration",
                    "pl": "Jeśli uważasz, że to błąd, skontaktuj się z administracją",
                }
                extra_line = extra_by_lang.get(lang, extra_by_lang["en"])

                admin_user = CURATOR_USERNAME or SUPPORT_USERNAME or ADMIN_CONTACT_USERNAME
                admin_at = None
                if admin_user:
                    admin_at = admin_user if str(admin_user).startswith("@") else f"@{admin_user}"
                    extra_line = f"{extra_line} {admin_at}."

                text = base + ("\n" + extra_line if extra_line else "")

                kb = None
                if admin_at:
                    try:
                        btn_text = await tr(user_id, "btn_contact_support")
                    except Exception:
                        btn_text = "📧 Contact support"
                    kb = types.InlineKeyboardMarkup().add(
                        types.InlineKeyboardButton(btn_text, url=f"https://t.me/{admin_at.lstrip('@')}")
                    )

                try:
                    await bot.send_message(
                        user_id,
                        text,
                        reply_markup=kb or get_main_menu()
                    )
                except Exception as e:
                    logger.error(f"Ошибка при отправке уведомления об отклонении пользователю {user_id}: {e}")

            logger.info(f"Payment {payment_id} rejected by admin {callback.from_user.id}")
        else:
            await bot.send_message(
                callback.from_user.id,
                await tr(callback.from_user.id, "payment_not_found_or_not_pending")
            )
            logger.error(f"Payment {payment_id} not found or not pending by admin {callback.from_user.id}")

        await callback.answer()
    except Exception as e:
        logger.error(f"Error in reject_payment_handler for admin {callback.from_user.id}: {e}")
        try:
            await bot.send_message(
                callback.from_user.id,
                await tr(callback.from_user.id, "error_check_payment")
            )
        except Exception:
            pass
        await state.finish()
        await callback.answer()
