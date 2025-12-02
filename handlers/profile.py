# handlers/profile.py — Handler for Profile button (i18n-ready)
from aiogram import types
from aiogram.dispatcher import FSMContext
from loader import dp
from keyboards.main_menu import get_main_menu
from utils.db_api import get_user_info, get_user_language, user_exists
from utils.i18n import tr, tr_, T  # i18n helpers
from .start import start_command  # <-- чтобы увести незарегистрированных в /start
import os
import logging
from datetime import datetime

log_file = os.path.join(os.path.dirname(__file__), 'bot.log')

logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

PROFILE_BUTTON_TEXTS = {d.get("btn_profile") for d in T.values()} | {
    "👨‍💻 Profile", "👨‍💻 Профиль", "📁 Profile", "📁 Профиль", "📁 Profil"
}

def _pick_db_username(uinfo: dict) -> str:
    if not uinfo:
        return ""
    return (
        uinfo.get("username")
        or uinfo.get("tg_username")
        or uinfo.get("user_name")
        or uinfo.get("login")
        or uinfo.get("nick")
        or uinfo.get("uname")
        or ""
    )

def _format_username(*candidates: str) -> str:
    """
    Берём первый непустой кандидат, чистим и гарантируем '@'.
    Пустые/мусорные значения → '—'.
    """
    bad = {"n/a", "none", "null", "нет", "-", "—"}
    cand = ""
    for c in candidates:
        if not c:
            continue
        s = str(c).strip()
        if s and s.lower() not in bad:
            cand = s
            break
    if not cand:
        return "—"
    if not cand.startswith("@"):
        cand = "@" + cand
    while cand.startswith("@@"):
        cand = cand[1:]
    return cand

@dp.message_handler(commands=["profile"])
@dp.message_handler(lambda m: (m.text or "").strip() in PROFILE_BUTTON_TEXTS)
async def profile_command(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    logger.info(f"User {user_id} accessed Profile, current state: {await state.get_state()}")

    # ⛔ Блокируем доступ незарегистрированным: уводим в /start и выходим
    try:
        if not await user_exists(user_id):
            await start_command(message, state)
            return
    except Exception as e:
        logger.error(f"Error checking user_exists for {user_id}: {e}")
        # на всякий случай тоже уводим в /start
        await start_command(message, state)
        return

    try:
        await state.finish()
        name = message.from_user.full_name
        user_info = await get_user_info(user_id) or {}
        lang = await get_user_language(user_id) or "ru"

        # Дата регистрации
        reg_date_str = user_info.get("registration_date") or "—"
        try:
            reg_date = datetime.fromisoformat(str(reg_date_str))
            reg_date_str = reg_date.strftime("%Y-%m-%d")
        except Exception:
            pass

        # Username: пробуем (БД → get_chat → from_user)
        try:
            chat = await dp.bot.get_chat(user_id)
            chat_username = getattr(chat, "username", None)
        except Exception:
            chat_username = None

        db_username = _pick_db_username(user_info)
        tg_username = message.from_user.username  # может быть None
        nice_username = _format_username(db_username, chat_username, tg_username)

        balance = user_info.get("balance", 0.0)

        profile_text = (
            f"👨‍💻 <b>{tr_(lang, 'profile_title')}</b> <code>{name}</code>\n"
            f"🆔 <code>{user_id}</code>\n\n"
            f"🏧 <b>{tr_(lang, 'balance_label')}:</b> <code>{balance} EUR</code>\n"
            f"📅 <b>{tr_(lang, 'registration_date_label')}:</b> <code>{reg_date_str}</code>\n\n"
            f"📛 <b>{tr_(lang, 'username_label')}:</b> <code>{nice_username}</code>"
        )

        # Фото профиля: сначала юзерское, затем дефолт
        try:
            photos = await dp.bot.get_user_profile_photos(user_id, limit=1)
            if photos.photos:
                await message.answer_photo(
                    photos.photos[0][-1].file_id,
                    caption=profile_text,
                    reply_markup=get_main_menu()
                )
            else:
                raise FileNotFoundError("no user photo")
        except Exception:
            photo_path = os.path.join("images", "profile.jpg")
            try:
                with open(photo_path, 'rb') as photo:
                    await message.answer_photo(
                        photo=photo,
                        caption=profile_text,
                        reply_markup=get_main_menu()
                    )
            except FileNotFoundError:
                logger.error(f"Default profile photo not found at {photo_path}")
                await message.answer(
                    profile_text + f"\n({tr_(lang, 'image_unavailable')})",
                    reply_markup=get_main_menu()
                )

        await state.finish()

    except Exception as e:
        logger.error(f"Error in profile_command for user {message.from_user.id}: {e}")
        await message.answer(await tr(user_id, "error_try_later"))
        await state.finish()
