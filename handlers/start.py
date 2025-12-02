from aiogram import types
from aiogram.dispatcher import FSMContext
from loader import dp
from keyboards.main_menu import get_main_menu
from utils.db_api import register_user, user_exists, get_user_language, set_user_language
from utils.notify import notify_new_user
from utils.set_bot_commands import set_only_start_for_user  # фиксируем только /start у юзера
import logging
import os

log_path = os.path.join(os.path.dirname(__file__), '..', 'bot.log')
logging.basicConfig(
    filename=os.path.abspath(log_path),
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

LANG_PREFIX = "set_lang:"

LANG_CONFIRM = {
    "ru": "Готово! Язык: Русский.\nОткрываю меню…",
    "en": "Done! Language: English.\nOpening menu…",
    "de": "Fertig! Sprache: Deutsch.\nMenü wird geöffnet…",
    "pl": "Gotowe! Język: Polski.\nOtwieram menu…",
}

GREETINGS = {
    "ru": "👋 Привет, {first}! Добро пожаловать в наш магазин.",
    "en": "👋 Hi, {first}! Welcome to our shop.",
    "de": "👋 Hallo, {first}! Willkommen in unserem Shop.",
    "pl": "👋 Cześć, {first}! Witamy w naszym sklepie.",
}


def language_keyboard():
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("🇷🇺 Русский", callback_data=f"{LANG_PREFIX}ru"),
        InlineKeyboardButton("🇬🇧 English", callback_data=f"{LANG_PREFIX}en"),
        InlineKeyboardButton("🇩🇪 Deutsch", callback_data=f"{LANG_PREFIX}de"),
        InlineKeyboardButton("🇵🇱 Polski", callback_data=f"{LANG_PREFIX}pl"),
    )
    return kb


@dp.message_handler(commands=['start'])
async def start_command(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    logger.info(f"User {user_id} started the bot, current state: {await state.get_state()}")

    try:
        # 1) если язык ещё не выбран — показываем выбор языка и выходим
        lang = await get_user_language(user_id)
        if not lang:
            await message.answer(
                "Выберите язык / Choose your language / Wähle eine Sprache / Wybierz język:",
                reply_markup=language_keyboard()
            )
            return

        # 2) регистрация при первом запуске, когда язык уже известен
        is_new = not await user_exists(user_id)
        if is_new:
            await register_user(user_id, message.from_user.username, language=lang)
            logger.info(f"[start] Registered new user {user_id} (lang={lang})")

            # уведомление в канал
            await notify_new_user(
                user_id=user_id,
                username=message.from_user.username,
                full_name=message.from_user.full_name
            )

        # 2.1) закрепляем у этого пользователя ТОЛЬКО /start (персональные команды)
        try:
            await set_only_start_for_user(dp.bot, user_id, lang)
        except Exception as e:
            logger.warning(f"set_only_start_for_user failed for {user_id}: {e}")

        # 3) приветствие и главное меню
        greet = GREETINGS.get(lang, GREETINGS["ru"]).format(first=message.from_user.first_name)
        await message.answer(greet, reply_markup=get_main_menu())
        await state.finish()

    except Exception as e:
        logger.error(f"Error in start_command for user {user_id}: {e}", exc_info=True)
        await message.answer("❌ <b>Ошибка:</b> Попробуйте позже.")
        await state.finish()


@dp.callback_query_handler(lambda c: c.data and c.data.startswith(LANG_PREFIX))
async def set_language_callback(call: types.CallbackQuery):
    user_id = call.from_user.id
    lang = call.data.split(":")[1]  # ru|en|de|pl

    try:
        was_new = not await user_exists(user_id)

        # сохраняем язык
        await set_user_language(user_id, lang)

        # регистрируем (создаст запись, если её ещё нет)
        await register_user(
            user_id=user_id,
            username=call.from_user.username,
            language=lang
        )

        # лог о новом пользователе
        if was_new:
            logger.info(f"[lang] New user {user_id} set language '{lang}', sending channel notification")
            await notify_new_user(
                user_id=user_id,
                username=call.from_user.username,
                full_name=call.from_user.full_name
            )

        # закрепляем ТОЛЬКО /start у пользователя с учётом языка
        try:
            await set_only_start_for_user(dp.bot, user_id, lang)
        except Exception as e:
            logger.warning(f"set_only_start_for_user (lang callback) failed for {user_id}: {e}")

        # подтверждаем выбор языка и открываем меню
        await call.message.edit_text(LANG_CONFIRM.get(lang, "Language set."))
        greet = GREETINGS.get(lang, GREETINGS["ru"]).format(first=call.from_user.first_name)
        await call.message.answer(greet, reply_markup=get_main_menu())

    except Exception as e:
        logger.error(f"Error in set_language_callback for user {user_id}: {e}", exc_info=True)
        await call.answer("Ошибка. Попробуйте ещё раз.", show_alert=True)


# 🔒 Блокируем любые другие слэш-команды: всё кроме /start → ведём на сценарий старта
@dp.message_handler(lambda m: m.text and m.text.startswith('/') and m.text.strip().lower() != '/start', state='*')
async def block_other_commands(message: types.Message, state: FSMContext):
    try:
        await state.finish()
    except Exception:
        pass
    await start_command(message, state)
