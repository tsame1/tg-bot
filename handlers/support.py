# Handler for Support button
from aiogram import types
from aiogram.dispatcher import FSMContext
from loader import dp
from keyboards.support import get_support_menu
from utils.i18n import tr
import os
import logging

log_file = os.path.join(os.path.dirname(__file__), 'bot.log')

logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


@dp.message_handler(text=["📞 Support", "📞 Поддержка"])
async def support_command(message: types.Message, state: FSMContext):
    logger.info(
        f"User {message.from_user.id} accessed Support, current state: {await state.get_state()}"
    )
    try:
        await state.finish()  # Сброс состояния

        # Локализация текста
        support_title = await tr(message.from_user.id, "support_title")
        support_description = await tr(message.from_user.id, "support_description")
        image_unavailable = await tr(message.from_user.id, "image_unavailable")
        error_try_later = await tr(message.from_user.id, "error_try_later")

        support_text = f"📞 <b>{support_title}</b>\n{support_description}"

        # Загружаем фото
        photo_path = os.path.join("images", "support.jpg")
        try:
            with open(photo_path, 'rb') as photo:
                await message.answer_photo(
                    photo=photo,
                    caption=support_text,
                    reply_markup=await get_support_menu(message.from_user.id)
                )
        except FileNotFoundError:
            logger.error(f"Support photo not found at {photo_path}")
            await message.answer(
                f"{support_text}\n({image_unavailable})",
                reply_markup=await get_support_menu(message.from_user.id)
            )
        except Exception as e:
            logger.error(f"Error sending support message to {message.from_user.id}: {e}")
            await message.answer(
                error_try_later,
                reply_markup=await get_support_menu(message.from_user.id)
            )

    except Exception as e:
        logger.error(f"Error in support_command for user {message.from_user.id}: {e}")
        error_try_later = await tr(message.from_user.id, "error_try_later")
        await message.answer(
            error_try_later,
            reply_markup=await get_support_menu(message.from_user.id)
        )
