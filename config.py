"""
Configuration settings for the Bybit Perpetual Futures Screener.
"""

# API Configuration
API_KEY = ""  # Optional: Your Bybit API key
API_SECRET = ""  # Optional: Your Bybit API secret
TESTNET = False  # Set to True to use testnet instead of mainnet

# Rate Limiting
MAX_REQUESTS_PER_WINDOW = 600  # Maximum requests per time window
RATE_LIMIT_WINDOW = 5  # Time window in seconds
SAFETY_FACTOR = 0.8  # Use only 80% of the allowed rate to be safe

# WebSocket Configuration
WS_PING_INTERVAL = 20  # Send ping every 20 seconds to keep connection alive

# Market Data
DEFAULT_CATEGORY = "linear"  # linear for USDT perpetual futures
TOP_COINS_LIMIT = 20  # Number of top volume coins to track
UPDATE_INTERVAL = 5  # Update interval in seconds

# Opportunity Detection
VOLUME_THRESHOLD_PERCENTAGE = 5.0  # Volume spike threshold (% of 24h avg)
PRICE_CHANGE_THRESHOLD = 1.5  # Significant price change threshold (%)
BIG_TRADE_THRESHOLD = 200000  # Size in USD to consider a trade as "big"

# Advanced Signal Quality Settings
SIGNAL_COOLDOWN_SECONDS = 600  # Minimum time between similar signals for the same symbol
TREND_CONFIRMATION_PERIODS = 4  # Number of consecutive periods to confirm a trend
COMBINED_SIGNAL_BONUS = 2.5  # Score multiplier for combined signals
MIN_SIGNAL_SCORE = 12.0  # Minimum score for a signal to be displayed (much higher)
VOLUME_PRICE_CORRELATION_THRESHOLD = 0.8  # Correlation threshold for volume and price
DIRECTIONAL_BIAS_REQUIRED = True  # Require clear directional bias for signals

# UI Configuration
REFRESH_RATE = 1  # Dashboard refresh rate in seconds
COLOR_POSITIVE = "green"
COLOR_NEGATIVE = "red"
COLOR_NEUTRAL = "yellow"
COLOR_HEADER = "cyan"
