from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS", "0").split(","))) if os.getenv("ADMIN_IDS") else []
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0")) if os.getenv("CHANNEL_ID") not in ("0", "") else None

# Остальные переменные — как у тебя было
REVOLUT_PAYMENT_LINK = os.getenv("REVOLUT_PAYMENT_LINK")
CRYPTO_ADDRESSES = {
    "sol": os.getenv("SOL_ADDRESS"),
    "eth": os.getenv("ETH_ADDRESS"),
    "bnb": os.getenv("BNB_ADDRESS"),
    "btc": os.getenv("BTC_ADDRESS"),
    "usdt_trc20": os.getenv("USDT_TRC20"),
    "usdt_bsc": os.getenv("USDT_BSC"),
    "usdt_sol": os.getenv("USDT_SOL"),
    "usdt_erc20": os.getenv("USDT_ERC20")
}
# + остальные, если есть