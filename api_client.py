"""
API client for interacting with the Bybit API.
Handles rate limiting and provides methods for fetching market data.
"""

import time
import json
import logging
import asyncio
import websocket
import hmac
import hashlib
from collections import deque
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable

from pybit.unified_trading import HTTP
import config

logger = logging.getLogger(__name__)

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
            config.MAX_REQUESTS_PER_WINDOW,
            config.RATE_LIMIT_WINDOW,
            config.SAFETY_FACTOR
        )
        
        # WebSocket connections
        self.ws_public = None
        self.ws_callbacks = {}
        
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
    
    async def get_instruments(self, category: str = "linear") -> Dict:
        """
        Get instrument info for the specified category.
        
        Args:
            category: Product category (linear, inverse, spot, option)
            
        Returns:
            Dictionary containing instrument data
        """
        await self.rate_limiter.wait_if_needed()
        response = self.http.get_instruments_info(category=category)
        return response
    
    async def get_recent_trades(self, category: str = "linear", symbol: str = None, limit: int = 50) -> Dict:
        """
        Get recent trades for the specified category and symbol.
        
        Args:
            category: Product category (linear, inverse, spot, option)
            symbol: Symbol name
            limit: Number of trades to return
            
        Returns:
            Dictionary containing recent trade data
        """
        await self.rate_limiter.wait_if_needed()
        params = {"category": category, "limit": limit}
        if symbol:
            params["symbol"] = symbol
        
        response = self.http.get_public_trade_history(**params)
        return response
    
    def start_websocket(self, category: str = "linear", callback: Callable = None):
        """
        Start a WebSocket connection for the specified category.
        
        Args:
            category: Product category (linear, inverse, spot, option)
            callback: Callback function for handling messages
        """
        base_url = "wss://stream-testnet.bybit.com" if self.testnet else "wss://stream.bybit.com"
        ws_url = f"{base_url}/v5/public/{category}"
        
        def on_message(ws, message):
            data = json.loads(message)
            if callback:
                callback(data)
        
        def on_error(ws, error):
            logger.error(f"WebSocket error: {error}")
        
        def on_close(ws, close_status_code, close_msg):
            logger.info(f"WebSocket closed: {close_status_code} - {close_msg}")
        
        def on_open(ws):
            logger.info(f"WebSocket connected to {category}")
        
        # Create WebSocket connection
        self.ws_public = websocket.WebSocketApp(
            ws_url,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
            on_open=on_open
        )
        
        # Start WebSocket in a separate thread
        import threading
        ws_thread = threading.Thread(target=self.ws_public.run_forever)
        ws_thread.daemon = True
        ws_thread.start()
    
    def subscribe_topic(self, topic: str):
        """
        Subscribe to a WebSocket topic.
        
        Args:
            topic: Topic to subscribe to (e.g., "orderbook.50.BTCUSDT")
        """
        if self.ws_public and self.ws_public.sock and self.ws_public.sock.connected:
            self.ws_public.send(json.dumps({
                "op": "subscribe",
                "args": [topic]
            }))
            logger.info(f"Subscribed to {topic}")
        else:
            logger.error("WebSocket not connected")
    
    def send_ping(self):
        """Send a ping to keep the WebSocket connection alive."""
        if self.ws_public and self.ws_public.sock and self.ws_public.sock.connected:
            self.ws_public.send(json.dumps({"op": "ping"}))
            logger.debug("Sent WebSocket ping")
        else:
            logger.warning("WebSocket not connected, cannot send ping")
