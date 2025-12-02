# Keyboards for support menu
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from utils.i18n import tr

# Берём логины из конфига, но не требуем их строго
try:
    from config import SUPPORT_USERNAME, ADMIN_USERNAME  # ADMIN_USERNAME можно не использовать
except Exception:
    SUPPORT_USERNAME = "your_support_username"  # без @, только имя
    ADMIN_USERNAME = None

def _tg_url(handle_or_url: str) -> str:
    """
    Возвращает корректный https-ссылку для кнопки.
    Поддерживает:
      - 'https://t.me/username'
      - '@username'
      - 'username'
    """
    if not handle_or_url:
        return "https://t.me/your_support_username"
    s = handle_or_url.strip()
    if s.startswith("http://") or s.startswith("https://"):
        return s
    if s.startswith("@"):
        s = s[1:]
    return f"https://t.me/{s}"

async def get_support_menu(user_id: int) -> InlineKeyboardMarkup:
    """
    Локализованное меню поддержки.
    """
    kb = InlineKeyboardMarkup(row_width=1)

    text_contact_support = await tr(user_id, "btn_contact_support")
    kb.add(
        InlineKeyboardButton(
            text=text_contact_support,
            url=_tg_url(SUPPORT_USERNAME)
        )
    )

    # Если захочешь отдельную кнопку админу — раскомментируй и добавь ключ перевода.
    # text_contact_admin = await tr(user_id, "btn_contact_admin")
    # if ADMIN_USERNAME:
    #     kb.add(
    #         InlineKeyboardButton(
    #             text=text_contact_admin,
    #             url=_tg_url(ADMIN_USERNAME)
    #         )
    #     )

    return kb
