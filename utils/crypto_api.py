# Crypto price fetching
import aiohttp
import logging
import os

log_file = os.path.join(os.path.dirname(__file__), 'bot.log')

logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


async def get_crypto_price(crypto):
    logger.info(f"Fetching price for {crypto}")
    try:
        # Map bot crypto IDs to CoinGecko IDs
        crypto_map = {
            "bitcoin": "bitcoin",
            "ethereum": "ethereum",
            "solana": "solana",
            "usdt": "tether"
        }
        coin_id = crypto_map.get(crypto.lower(), crypto)
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://api.coingecko.com/api/v3/simple/price?ids={coin_id}&vs_currencies=eur"
            ) as response:
                data = await response.json()
                if coin_id in data and "eur" in data[coin_id]:
                    price = data[coin_id]["eur"]
                    logger.info(f"Price for {crypto}: {price} EUR")
                    return price
                else:
                    logger.error(f"No price data for {coin_id}")
                    return 1.0  # Fallback price
    except Exception as e:
        logger.error(f"Error fetching price for {crypto}: {e}")
        return 1.0  # Fallback price