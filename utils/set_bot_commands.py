# utils/set_bot_commands.py
from aiogram import types

# Тексты для /start
_CAPTIONS = {
    "ru": "Запустить бота",
    "en": "Start the bot",
    "de": "Bot starten",
    "pl": "Uruchom bota",
}
_FALLBACK = "Start the bot"


async def set_only_start_everywhere(dp):
    """
    Глобально (для всех пользователей) ставит ТОЛЬКО /start
    во всех локалях + fallback без language_code.
    """
    try:
        # локализованные наборы
        for lc, title in _CAPTIONS.items():
            await dp.bot.set_my_commands(
                [types.BotCommand("start", title)],
                language_code=lc,
            )
        # fallback без языка
        await dp.bot.set_my_commands([types.BotCommand("start", _FALLBACK)])
    except Exception as e:
        print(f"[set_bot_commands] set_only_start_everywhere error: {e}")


async def set_only_start_for_user(bot, user_id: int, lang: str | None = None):
    """
    Персонально для КОНКРЕТНОГО пользователя — тоже только /start.
    """
    title = _CAPTIONS.get((lang or "").lower(), _FALLBACK)
    try:
        await bot.set_my_commands(
            [types.BotCommand("start", title)],
            scope=types.BotCommandScopeChat(user_id),
        )
    except Exception as e:
        print(f"[set_bot_commands] set_only_start_for_user error: {e}")


async def clear_user_commands(bot, user_id: int):
    """
    На всякий: сброс персонального набора команд для пользователя.
    """
    try:
        await bot.delete_my_commands(scope=types.BotCommandScopeChat(user_id))
    except Exception as e:
        print(f"[set_bot_commands] clear_user_commands error: {e}")


# -------- обратная совместимость (чтобы старые импорты не падали) --------
# старое имя, которое у тебя импортируется в app.py
async def set_global_minimal_commands(dp):
    await set_only_start_everywhere(dp)

# если где-то ещё вызывалось set_user_commands — сведём к одному поведению
async def set_user_commands(bot, user_id: int, lang: str = "en"):
    await set_only_start_for_user(bot, user_id, lang)
