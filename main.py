"""
Main entry point for the Bybit Perpetual Futures Screener.
"""

import asyncio
import logging
import signal
import sys
import time
import threading

import config
from api_client import BybitClient
from data_processor import MarketData
from dashboard import Dashboard
from utils import setup_logging

# Set up logging
setup_logging(log_level="INFO")
logger = logging.getLogger(__name__)

# Prompt for signal strength at startup
def prompt_signal_strength():
    """Prompt the user to select the minimum signal strength level."""
    print("\nSelect minimum signal strength level:")
    print("1. Low (Score >= 8)")
    print("2. Moderate (Score >= 12)")
    print("3. Strong (Score >= 16)")

    while True:
        choice = input("\nEnter your choice (1-3) [default=2]: ").strip()

        if choice == "":
            # Default to moderate
            config.MIN_SIGNAL_SCORE = 12.0
            print("Using Moderate signal strength (Score >= 12)")
            break
        elif choice == "1":
            config.MIN_SIGNAL_SCORE = 8.0
            print("Using Low signal strength (Score >= 8)")
            break
        elif choice == "2":
            config.MIN_SIGNAL_SCORE = 12.0
            print("Using Moderate signal strength (Score >= 12)")
            break
        elif choice == "3":
            config.MIN_SIGNAL_SCORE = 16.0
            print("Using Strong signal strength (Score >= 16)")
            break
        else:
            print("Invalid choice. Please enter 1, 2, or 3.")

# Prompt for signal strength before starting
prompt_signal_strength()

class BybitScreener:
    """Main class for the Bybit Perpetual Futures Screener."""

    def __init__(self):
        """Initialize the screener."""
        self.running = False
        self.market_data = MarketData()
        self.client = BybitClient(
            api_key=config.API_KEY,
            api_secret=config.API_SECRET,
            testnet=config.TESTNET
        )
        self.dashboard = Dashboard(self.market_data)

        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)

        logger.info("Bybit Screener initialized")

    def handle_signal(self, sig, _):
        """
        Handle termination signals.

        Args:
            sig: Signal number
            _: Current stack frame (unused)
        """
        logger.info(f"Received signal {sig}, shutting down...")
        self.stop()

    async def fetch_initial_data(self):
        """Fetch initial market data."""
        logger.info("Fetching initial market data...")

        # Fetch instruments
        instruments_data = await self.client.get_instruments(category=config.DEFAULT_CATEGORY)
        self.market_data.update_instruments(instruments_data)

        # Fetch tickers
        tickers_data = await self.client.get_tickers(category=config.DEFAULT_CATEGORY)
        self.market_data.update_tickers(tickers_data)

        # Get symbols to monitor (we'll use a subset of available symbols)
        symbols = list(self.market_data.tickers.keys())
        symbols_to_fetch = symbols[:20]  # Limit to 20 symbols for initial fetch

        # Fetch recent trades for selected symbols
        for symbol in symbols_to_fetch:
            trades_data = await self.client.get_recent_trades(
                category=config.DEFAULT_CATEGORY,
                symbol=symbol,
                limit=100
            )
            self.market_data.update_recent_trades(symbol, trades_data)

        # Update opportunities
        self.market_data.update_opportunities()

        logger.info("Initial data fetched successfully")

    async def update_data_loop(self):
        """Continuously update market data."""
        while self.running:
            try:
                # Fetch tickers
                tickers_data = await self.client.get_tickers(category=config.DEFAULT_CATEGORY)
                self.market_data.update_tickers(tickers_data)

                # Get symbols to monitor (we'll use all available symbols)
                symbols = list(self.market_data.tickers.keys())

                # Fetch recent trades for a subset of symbols (to avoid rate limiting)
                # We'll rotate through all symbols over time
                symbols_to_fetch = symbols[:20]  # Limit to 20 symbols per update

                for symbol in symbols_to_fetch:
                    trades_data = await self.client.get_recent_trades(
                        category=config.DEFAULT_CATEGORY,
                        symbol=symbol,
                        limit=100
                    )
                    self.market_data.update_recent_trades(symbol, trades_data)

                # Update opportunities
                self.market_data.update_opportunities()

                # Update dashboard
                self.dashboard.update()

                # Wait for next update
                await asyncio.sleep(config.UPDATE_INTERVAL)

            except Exception as e:
                logger.error(f"Error updating data: {e}")
                await asyncio.sleep(5)  # Wait a bit before retrying

    async def websocket_ping_loop(self):
        """Send periodic pings to keep WebSocket connections alive."""
        while self.running:
            try:
                self.client.send_ping()
                await asyncio.sleep(config.WS_PING_INTERVAL)
            except Exception as e:
                logger.error(f"Error sending WebSocket ping: {e}")
                await asyncio.sleep(5)  # Wait a bit before retrying

    def websocket_callback(self, data):
        """
        Callback for WebSocket messages.

        Args:
            data: WebSocket message data
        """
        # Process WebSocket data here
        # This is a placeholder for future WebSocket implementation
        logger.debug(f"Received WebSocket data: {data.get('topic', 'unknown topic')}")

    async def run(self):
        """Run the screener."""
        self.running = True
        logger.info("Starting Bybit Screener...")

        # Fetch initial data
        await self.fetch_initial_data()

        # Start the dashboard
        self.dashboard.start()

        # Start WebSocket connection
        self.client.start_websocket(
            category=config.DEFAULT_CATEGORY,
            callback=self.websocket_callback
        )

        # Create tasks
        tasks = [
            self.update_data_loop(),
            self.websocket_ping_loop()
        ]

        # Run tasks
        await asyncio.gather(*tasks)

    def stop(self):
        """Stop the screener."""
        logger.info("Stopping Bybit Screener...")
        self.running = False

        # Stop the dashboard
        self.dashboard.stop()

        # Exit the program
        sys.exit(0)

async def main():
    """Main entry point."""
    screener = BybitScreener()
    await screener.run()

if __name__ == "__main__":
    # Run the main function
    asyncio.run(main())
