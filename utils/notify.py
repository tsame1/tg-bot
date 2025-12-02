# utils/notify.py
from loader import dp
from config import CHANNEL_ID, ADMIN_IDS
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def _normalize_channel_id(value):
    """
    Приводит CHANNEL_ID к виду, который принимает send_message.
    Допускаем:
      - int (-1001234567890)
      - str с числом (-1001234567890)
      - str с @username канала
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value
    s = str(value).strip()
    if s.startswith("@"):
        return s
    if s.lstrip("-").isdigit():
        try:
            return int(s)
        except Exception:
            pass
    return s

_CHANNEL = _normalize_channel_id(CHANNEL_ID)

async def notify_new_user(user_id, username, full_name):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    username = username or "—"
    if username != "—" and not str(username).startswith("@"):
        username = "@" + str(username)
    full_name = full_name or "—"

    text = (
        "└ <b>Новый пользователь</b>\n"
        f"└ <b>Никнейм:</b> <i>{full_name}</i>\n"
        f"└ <b>Юзернейм:</b> <code>{username}</code>\n"
        f"└ <b>ID:</b> <u>{user_id}</u>\n"
        f"└ <b>Присоединился:</b> <i>{current_time}</i>\n"
        "📌 <b>Воркер</b>"
    )
    if not _CHANNEL:
        logger.error("CHANNEL_ID не задан, сообщение не отправлено.")
        return

    try:
        await dp.bot.send_message(_CHANNEL, text, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления в канал {_CHANNEL}: {e}")

async def on_startup_notify(dispatcher):
    for admin_id in ADMIN_IDS:
        try:
            await dispatcher.bot.send_message(
                admin_id,
                "🚀 <b>Бот [Shop Name] запущен!</b>\n└ <i>Добро пожаловать</i>",
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Ошибка отправки уведомления админу {admin_id}: {e}")
