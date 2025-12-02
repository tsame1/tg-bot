import sqlite3
import asyncio
import uuid
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional

DB_PATH = 'shop.db'


@asynccontextmanager
async def db_transaction():
    """
    Асинхронный контекстный менеджер для транзакций SQLite.
    Разрешает использование соединения в разных потоках.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute('BEGIN TRANSACTION')
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


# ============== МИГРАЦИЯ КОЛОНКИ ЯЗЫКА ==============

async def ensure_language_column():
    """
    Мягкая миграция: добавляет колонку language в таблицу users, если её нет.
    Вызывать один раз при старте бота (on_startup).
    """
    loop = asyncio.get_event_loop()

    def sync_migrate():
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cur = conn.cursor()
        # Убедимся, что таблица есть (на случай чистой БД)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                balance REAL DEFAULT 0.0,
                registration_date TEXT,
                username TEXT
            )
        """)
        # Проверим наличие колонки language
        cur.execute("PRAGMA table_info(users)")
        cols = [r[1] for r in cur.fetchall()]
        if "language" not in cols:
            cur.execute("ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'ru'")
            conn.commit()
        conn.close()

    await loop.run_in_executor(None, sync_migrate)


# ============== USERS ==============

async def get_user_info(user_id: int):
    loop = asyncio.get_event_loop()

    def sync_get():
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT balance, registration_date, username
            FROM users
            WHERE user_id = ?
        """, (user_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            balance = 0.0 if row[0] is None else row[0]
            return {
                "user_id": user_id,
                "balance": balance,
                "registration_date": row[1] if row[1] else "N/A",
                "username": row[2] if row[2] else "N/A"
            }
        # Если вдруг нет записи — вернём заглушку
        return {"user_id": user_id, "balance": 0.0, "registration_date": "N/A", "username": "N/A"}

    return await loop.run_in_executor(None, sync_get)


async def get_user_language(user_id: int) -> Optional[str]:
    """
    Возвращает язык пользователя ('ru'/'en'/'de'/'pl') или None, если записи нет.
    """
    loop = asyncio.get_event_loop()

    def sync_get():
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cur = conn.cursor()
        # Если колонки ещё нет (бот впервые запустился без миграции) — вернём None
        try:
            cur.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
            row = cur.fetchone()
            conn.close()
            return row[0] if row else None
        except sqlite3.OperationalError:
            # Колонка language отсутствует
            conn.close()
            return None

    return await loop.run_in_executor(None, sync_get)


async def set_user_language(user_id: int, lang: str):
    """
    Устанавливает язык пользователю. Если пользователя ещё нет — создаёт запись.
    """
    loop = asyncio.get_event_loop()

    def sync_set():
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cur = conn.cursor()
        # Попробуем обновить существующую запись
        try:
            cur.execute("UPDATE users SET language = ? WHERE user_id = ?", (lang, user_id))
        except sqlite3.OperationalError:
            # Если колонки ещё нет (на всякий случай) — создадим её
            cur.execute("PRAGMA table_info(users)")
            cols = [r[1] for r in cur.fetchall()]
            if "language" not in cols:
                cur.execute("ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'ru'")
            cur.execute("UPDATE users SET language = ? WHERE user_id = ?", (lang, user_id))

        if cur.rowcount == 0:
            # пользователя ещё нет — создадим
            cur.execute("""
                INSERT OR IGNORE INTO users (user_id, balance, registration_date, username, language)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, 0.0, datetime.now().isoformat(), None, lang))
        conn.commit()
        conn.close()

    await loop.run_in_executor(None, sync_set)


async def update_balance(user_id: int, amount: float, conn=None):
    loop = asyncio.get_event_loop()

    def sync_update(conn_):
        cursor = conn_.cursor()
        # COALESCE на случай, если баланс ранее оказался NULL
        cursor.execute(
            "UPDATE users SET balance = COALESCE(balance, 0) + ? WHERE user_id = ?",
            (amount, user_id)
        )

    if conn:
        await loop.run_in_executor(None, sync_update, conn)
    else:
        async with db_transaction() as conn2:
            await loop.run_in_executor(None, sync_update, conn2)


async def create_db():
    """
    Базовая инициализация таблиц (без language — миграция добавит колонку отдельно,
    чтобы не ломать уже существующие БД).
    """
    loop = asyncio.get_event_loop()

    def sync_create():
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                balance REAL DEFAULT 0.0,
                registration_date TEXT,
                username TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payment_requests (
                payment_id TEXT PRIMARY KEY,
                user_id INTEGER,
                method TEXT,
                amount REAL,
                crypto TEXT,
                crypto_amount REAL,
                network TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    await loop.run_in_executor(None, sync_create)


async def register_user(user_id: int, username: str = None, language: Optional[str] = None):
    """
    Регистрирует пользователя при отсутствии записи.
    Параметр language опциональный, чтобы не ломать существующие вызовы.
    Если колонка language есть — проставим значение; если нет — просто создадим запись.
    """
    loop = asyncio.get_event_loop()

    def sync_register():
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cursor = conn.cursor()

        # Проверим, есть ли уже пользователь
        cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        exists = cursor.fetchone() is not None

        if not exists:
            # Пытаемся вставить с language, если колонка есть
            has_language = False
            try:
                cursor.execute("PRAGMA table_info(users)")
                cols = [r[1] for r in cursor.fetchall()]
                has_language = "language" in cols
            except Exception:
                has_language = False

            if has_language:
                cursor.execute("""
                    INSERT OR IGNORE INTO users (user_id, balance, registration_date, username, language)
                    VALUES (?, ?, ?, ?, ?)
                """, (user_id, 0.0, datetime.now().isoformat(), username, language or 'ru'))
            else:
                cursor.execute("""
                    INSERT OR IGNORE INTO users (user_id, balance, registration_date, username)
                    VALUES (?, ?, ?, ?)
                """, (user_id, 0.0, datetime.now().isoformat(), username))

            conn.commit()

        conn.close()

    await loop.run_in_executor(None, sync_register)


async def user_exists(user_id: int) -> bool:
    loop = asyncio.get_event_loop()

    def sync_check():
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        res = cursor.fetchone()
        conn.close()
        return res is not None

    return await loop.run_in_executor(None, sync_check)


# ============== PAYMENTS ==============

async def record_payment_request(user_id: int, method: str, amount: float,
                                 crypto: str = None, crypto_amount: float = None, network: str = None) -> str:
    loop = asyncio.get_event_loop()

    def sync_record():
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        cursor = conn.cursor()
        payment_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO payment_requests
                (payment_id, user_id, method, amount, crypto, crypto_amount, network, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')
        """, (payment_id, user_id, method, amount, crypto, crypto_amount, network))
        conn.commit()
        conn.close()
        return payment_id

    return await loop.run_in_executor(None, sync_record)


async def confirm_payment(payment_id: str):
    """
    Подтверждаем платёж и ВОЗВРАЩАЕМ (user_id, amount, new_balance).
    new_balance берём в той же транзакции — без гонок и кэша.
    """
    loop = asyncio.get_event_loop()

    async with db_transaction() as conn:
        def sync_confirm(conn_):
            cursor = conn_.cursor()
            cursor.execute("""
                SELECT user_id, amount
                FROM payment_requests
                WHERE payment_id = ? AND status = 'pending'
            """, (payment_id,))
            payment = cursor.fetchone()
            if not payment:
                return None, None, None

            user_id, amount = payment

            cursor.execute("UPDATE payment_requests SET status = 'confirmed' WHERE payment_id = ?", (payment_id,))
            cursor.execute(
                "UPDATE users SET balance = COALESCE(balance, 0) + ? WHERE user_id = ?",
                (amount, user_id)
            )
            # Сразу читаем новый баланс из этой же транзакции
            cursor.execute("SELECT COALESCE(balance, 0) FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            new_balance = row[0] if row else None
            return user_id, amount, new_balance

        return await loop.run_in_executor(None, sync_confirm, conn)


async def reject_payment(payment_id: str) -> bool:
    loop = asyncio.get_event_loop()

    async with db_transaction() as conn:
        def sync_reject(conn_):
            cursor = conn_.cursor()
            cursor.execute("""
                SELECT 1
                FROM payment_requests
                WHERE payment_id = ? AND status = 'pending'
            """, (payment_id,))
            if cursor.fetchone():
                cursor.execute("UPDATE payment_requests SET status = 'rejected' WHERE payment_id = ?", (payment_id,))
                return True
            return False

        return await loop.run_in_executor(None, sync_reject, conn)
