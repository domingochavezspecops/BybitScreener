"""
Simple script to fetch and display top 24-hour volume coins from Bybit.
Also shows which coins are being monitored for alerts on each update loop.
"""

import asyncio
import logging
import time
import random
from collections import deque
from typing import Dict, List, Set
import pandas as pd
from datetime import datetime

from pybit.unified_trading import HTTP

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Configuration
TESTNET = False  # Set to True to use testnet instead of mainnet
DEFAULT_CATEGORY = "linear"  # linear for USDT perpetual futures
TOP_COINS_LIMIT = 20  # Number of top volume coins to display
MONITORED_COINS_PER_LOOP = 20  # Number of coins monitored for alerts in each loop
SIMULATION_LOOPS = 3  # Number of update loops to simulate

# Rate limiting configuration
MAX_REQUESTS_PER_WINDOW = 600  # Maximum requests per time window
RATE_LIMIT_WINDOW = 5  # Time window in seconds
SAFETY_FACTOR = 0.8  # Use only 80% of the allowed rate to be safe


class RateLimiter:
    """Rate limiter to prevent exceeding Bybit API limits."""

    def __init__(self, max_requests: int, window_seconds: int, safety_factor: float = 0.8):
        """
        Initialize the rate limiter.

        Args:
            max_requests: Maximum number of requests allowed in the time window
            window_seconds: Time window in seconds
            safety_factor: Factor to reduce the max requests (0.0 to 1.0)
        """
        self.max_requests = int(max_requests * safety_factor)
        self.window_seconds = window_seconds
        self.request_timestamps = deque()

    async def wait_if_needed(self):
        """Wait if we're about to exceed the rate limit."""
        now = time.time()

        # Remove timestamps older than the window
        while self.request_timestamps and self.request_timestamps[0] < now - self.window_seconds:
            self.request_timestamps.popleft()

        # If we've reached the max requests, wait until we can make another
        if len(self.request_timestamps) >= self.max_requests:
            oldest = self.request_timestamps[0]
            wait_time = oldest + self.window_seconds - now
            if wait_time > 0:
                logger.debug(f"Rate limit reached, waiting {wait_time:.2f} seconds")
                await asyncio.sleep(wait_time)

        # Add the current timestamp
        self.request_timestamps.append(time.time())


class BybitClient:
    """Client for interacting with the Bybit API."""

    def __init__(self, api_key: str = "", api_secret: str = "", testnet: bool = False):
        """
        Initialize the Bybit client.

        Args:
            api_key: Bybit API key (optional)
            api_secret: Bybit API secret (optional)
            testnet: Whether to use testnet
        """
        self.api_key = api_key
        self.api_secret = api_secret
        self.testnet = testnet

        # Initialize HTTP client
        self.http = HTTP(
            testnet=testnet,
            api_key=api_key,
            api_secret=api_secret
        )

        # Initialize rate limiter
        self.rate_limiter = RateLimiter(
            MAX_REQUESTS_PER_WINDOW,
            RATE_LIMIT_WINDOW,
            SAFETY_FACTOR
        )

        logger.info(f"Initialized Bybit client (testnet: {testnet})")

    async def get_tickers(self, category: str = "linear", symbol: str = None) -> Dict:
        """
        Get tickers for the specified category and symbol.

        Args:
            category: Product category (linear, inverse, spot, option)
            symbol: Symbol name (optional)

        Returns:
            Dictionary containing ticker data
        """
        await self.rate_limiter.wait_if_needed()
        params = {"category": category}
        if symbol:
            params["symbol"] = symbol

        response = self.http.get_tickers(**params)
        return response


class MarketData:
    """Class for processing market data."""

    def __init__(self):
        """Initialize the market data storage."""
        self.tickers = {}  # Symbol -> ticker data
        self.top_volume_coins = []  # List of top volume coins
        self.monitored_coins = set()  # Set of coins being monitored for alerts
        self.last_update = 0  # Timestamp of last update

    def update_tickers(self, tickers_data: Dict):
        """
        Update tickers with new data.

        Args:
            tickers_data: Ticker data from API
        """
        if not tickers_data or 'result' not in tickers_data or 'list' not in tickers_data['result']:
            logger.warning("Invalid ticker data received")
            return

        ticker_list = tickers_data['result']['list']

        for ticker in ticker_list:
            if 'symbol' in ticker:
                symbol = ticker['symbol']
                self.tickers[symbol] = ticker

        self.last_update = time.time()
        logger.debug(f"Updated tickers for {len(ticker_list)} symbols")

    def get_top_volume_coins(self, limit: int = 20) -> List[Dict]:
        """
        Get the top volume coins.

        Args:
            limit: Number of top coins to return

        Returns:
            List of top volume coins with their data
        """
        if not self.tickers:
            return []

        # Convert to DataFrame for easier sorting
        df = pd.DataFrame(self.tickers.values())

        # Ensure volume24h exists and convert to float
        if 'volume24h' in df.columns:
            df['volume24h'] = pd.to_numeric(df['volume24h'], errors='coerce')

            # Sort by volume and take top N
            top_coins = df.sort_values('volume24h', ascending=False).head(limit).to_dict('records')
            self.top_volume_coins = top_coins
            return top_coins
        else:
            logger.warning("volume24h not found in ticker data")
            return []

    def update_monitored_coins(self, limit: int = 20):
        """
        Update the set of coins being monitored for alerts.
        In the original app, this is the first 20 symbols from all available tickers.

        Args:
            limit: Number of coins to monitor
        """
        # Get all symbols
        all_symbols = list(self.tickers.keys())

        # Take the first N symbols (in the original app, this is what's monitored each loop)
        symbols_to_monitor = all_symbols[:limit]
        self.monitored_coins = set(symbols_to_monitor)

        return symbols_to_monitor


def format_number(value: float, decimals: int = 2, with_commas: bool = True) -> str:
    """
    Format a number with the specified number of decimal places.

    Args:
        value: Number to format
        decimals: Number of decimal places
        with_commas: Whether to include commas as thousand separators

    Returns:
        Formatted number as string
    """
    if with_commas:
        return f"{value:,.{decimals}f}"
    else:
        return f"{value:.{decimals}f}"


async def display_monitored_coins(market_data, top_coins, loop_num=None):
    """
    Display the coins being monitored for alerts.

    Args:
        market_data: MarketData instance
        top_coins: List of top volume coins
        loop_num: Current loop number (optional)
    """
    monitored_coins = list(market_data.monitored_coins)

    # Display header
    if loop_num is not None:
        print(f"\n===== COINS MONITORED FOR ALERTS (LOOP {loop_num}) =====")
    else:
        print("\n===== COINS MONITORED FOR ALERTS =====")
    print("These are the coins that would be checked for trading signals in each update loop")
    print("-" * 60)

    # Create lists to track which top volume coins are also being monitored
    monitored_top_coins = []
    other_monitored_coins = []

    # Separate monitored coins into those that are in top volume and those that aren't
    for symbol in monitored_coins:
        is_top_coin = any(coin.get('symbol') == symbol for coin in top_coins)
        if is_top_coin:
            monitored_top_coins.append(symbol)
        else:
            other_monitored_coins.append(symbol)

    # Display the results
    print(f"Total monitored coins: {len(monitored_coins)}")
    print(f"Top volume coins that are monitored: {len(monitored_top_coins)} of {len(top_coins)}")

    print("\nTop volume coins being monitored:")
    for i, symbol in enumerate(monitored_top_coins):
        print(f"{symbol:<10}", end=" ")
        # Print 5 symbols per line
        if (i + 1) % 5 == 0:
            print()
    if monitored_top_coins:
        print()  # Add a newline if we printed any symbols

    print("\nOther coins being monitored (not in top volume):")
    for i, symbol in enumerate(other_monitored_coins):
        print(f"{symbol:<10}", end=" ")
        # Print 5 symbols per line
        if (i + 1) % 5 == 0:
            print()
    if other_monitored_coins:
        print()  # Add a newline if we printed any symbols

    # Calculate overlap percentage
    if top_coins:
        overlap_percentage = (len(monitored_top_coins) / len(top_coins)) * 100
        print(f"Overlap between top volume and monitored coins: {overlap_percentage:.1f}%")

    return monitored_top_coins, other_monitored_coins


async def display_top_volume_coins(top_coins):
    """
    Display the top volume coins.

    Args:
        top_coins: List of top volume coins
    """
    print("\n===== TOP 24-HOUR VOLUME COINS =====")
    print(f"{'Symbol':<10} {'Price':<12} {'24h Volume':<20} {'24h Change':<12}")
    print("-" * 60)

    for coin in top_coins:
        symbol = coin.get('symbol', 'N/A')
        price = float(coin.get('lastPrice', 0))
        volume = float(coin.get('volume24h', 0))
        change_24h = float(coin.get('price24hPcnt', 0)) * 100

        # Format values
        price_str = format_number(price, decimals=4 if price < 1 else 2)
        volume_str = format_number(volume, decimals=2)
        change_str = f"{change_24h:+.2f}%"

        print(f"{symbol:<10} {price_str:<12} {volume_str:<20} {change_str:<12}")


async def main():
    """Main function to run the script."""
    logger.info("Starting Bybit Top Volume Coins Fetcher...")

    # Initialize client and market data
    client = BybitClient(testnet=TESTNET)
    market_data = MarketData()

    # Fetch tickers
    logger.info("Fetching ticker data...")
    tickers_data = await client.get_tickers(category=DEFAULT_CATEGORY)
    market_data.update_tickers(tickers_data)

    # Get top volume coins
    top_coins = market_data.get_top_volume_coins(TOP_COINS_LIMIT)

    # Display top volume results
    await display_top_volume_coins(top_coins)

    # Simulate multiple update loops
    all_monitored_symbols = set()
    top_volume_symbols = {coin.get('symbol') for coin in top_coins}

    for loop in range(1, SIMULATION_LOOPS + 1):
        # In each loop, we monitor a different subset of coins
        # In the real app, this would be the first 20 symbols from the full list
        # Here we'll simulate by taking a different slice of the symbols each time
        all_symbols = list(market_data.tickers.keys())
        start_idx = (loop - 1) * MONITORED_COINS_PER_LOOP % max(1, len(all_symbols) - MONITORED_COINS_PER_LOOP)
        symbols_to_monitor = all_symbols[start_idx:start_idx + MONITORED_COINS_PER_LOOP]
        market_data.monitored_coins = set(symbols_to_monitor)

        # Display monitored coins for this loop
        await display_monitored_coins(market_data, top_coins, loop)

        # Track all symbols that have been monitored
        all_monitored_symbols.update(market_data.monitored_coins)

    # Summary after all loops
    print("\n===== MONITORING SUMMARY AFTER ALL LOOPS =====")
    print(f"Total unique symbols monitored across all loops: {len(all_monitored_symbols)}")
    print(f"Total top volume symbols: {len(top_volume_symbols)}")

    # Calculate how many top volume coins were monitored across all loops
    monitored_top_volume = top_volume_symbols.intersection(all_monitored_symbols)
    print(f"Top volume coins monitored in at least one loop: {len(monitored_top_volume)} of {len(top_volume_symbols)}")

    # Calculate percentage
    if top_volume_symbols:
        coverage_percentage = (len(monitored_top_volume) / len(top_volume_symbols)) * 100
        print(f"Coverage of top volume coins: {coverage_percentage:.1f}%")

    logger.info("Script completed successfully")


if __name__ == "__main__":
    asyncio.run(main())
