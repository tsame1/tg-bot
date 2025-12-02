from dotenv import load_dotenv
import os

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS").split(",")))
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
CRYPTO_API_URL = os.getenv("CRYPTO_API_URL")
REVOLUT_PAYMENT_LINK = os.getenv("REVOLUT_PAYMENT_LINK")
CRYPTO_WALLET_ADDRESS = os.getenv("CRYPTO_WALLET_ADDRESS")
CURATOR_USERNAME = os.getenv("CURATOR_USERNAME")

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
