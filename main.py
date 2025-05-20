"""
Main entry point for the Bybit Perpetual Futures Screener.
"""

import asyncio
import logging
import signal
import sys
import time
import threading
from typing import Dict, List, Optional, Any

import config
from api_client import BybitClient
from data_processor import MarketData
from dashboard import Dashboard
from utils import setup_logging

# Set up logging
setup_logging(log_level="INFO")
logger = logging.getLogger(__name__)

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
    
    def handle_signal(self, sig, frame):
        """
        Handle termination signals.
        
        Args:
            sig: Signal number
            frame: Current stack frame
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
        
        # Get top volume coins
        top_coins = self.market_data.get_top_volume_coins(config.TOP_COINS_LIMIT)
        
        # Fetch recent trades for top coins
        for coin in top_coins:
            symbol = coin.get('symbol')
            if symbol:
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
                
                # Get top volume coins
                top_coins = self.market_data.get_top_volume_coins(config.TOP_COINS_LIMIT)
                
                # Fetch recent trades for top coins
                for coin in top_coins:
                    symbol = coin.get('symbol')
                    if symbol:
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
    
    def websocket_callback(self, data: Dict):
        """
        Callback for WebSocket messages.
        
        Args:
            data: WebSocket message data
        """
        # Process WebSocket data here
        # This is a placeholder for future WebSocket implementation
        pass
    
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
