# Bybit Perpetual Futures Screener

A terminal-based dashboard that scans the Bybit API for trading opportunities in perpetual futures markets. The screener displays top volume coins, detects big buys/sells, tracks percentage gains/losses, and presents real-time market opportunities in a colorful terminal interface.

## Features

- **Top Volume Coins**: Displays the highest volume coins in the market
- **Big Trade Detection**: Identifies large buy and sell orders
- **Price Movement Alerts**: Highlights significant price changes
- **Volume Spike Detection**: Detects unusual volume activity
- **Real-time Updates**: Continuously refreshes with the latest market data
- **Rate Limiting**: Properly manages API request rates to avoid bans
- **Colorful Terminal UI**: Easy-to-read dashboard with color-coded alerts

## Requirements

- Python 3.8+
- Required Python packages (see `requirements.txt`)

## Installation

1. Clone this repository:
   ```
   git clone <repository-url>
   cd bybit-screener
   ```

2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

3. (Optional) Configure API keys in `config.py` if you want to use authenticated endpoints:
   ```python
   API_KEY = "your_api_key"
   API_SECRET = "your_api_secret"
   ```

## Usage

Run the screener:
```
python main.py
```

The terminal will display a dashboard with two main sections:
- **Top Volume Coins**: Shows the highest volume coins with their current price, 24-hour change, and volume
- **Trading Opportunities**: Displays real-time trading opportunities including big trades, price movements, and volume spikes

## Configuration

You can customize the screener by modifying the settings in `config.py`:

- `TESTNET`: Set to `True` to use Bybit's testnet instead of mainnet
- `TOP_COINS_LIMIT`: Number of top volume coins to track
- `UPDATE_INTERVAL`: How often to update the data (in seconds)
- `VOLUME_THRESHOLD_PERCENTAGE`: Threshold for detecting volume spikes
- `PRICE_CHANGE_THRESHOLD`: Threshold for significant price changes
- `BIG_TRADE_THRESHOLD`: Size in USD to consider a trade as "big"
- `REFRESH_RATE`: Dashboard refresh rate (in seconds)

## How It Works

1. The screener connects to the Bybit API and fetches market data for perpetual futures
2. It processes the data to identify trading opportunities based on configurable thresholds
3. The dashboard displays the processed data in a user-friendly terminal interface
4. The data is continuously updated at regular intervals

## Rate Limiting

The screener implements proper rate limiting to comply with Bybit's API restrictions:
- Maximum 600 requests per 5-second window
- Safety factor of 0.8 (uses only 80% of the allowed rate)
- Automatic request throttling when approaching limits

## License

[MIT License](LICENSE)

## Disclaimer

This tool is for informational purposes only and does not constitute financial advice. Trading cryptocurrency futures involves significant risk. Always do your own research before making investment decisions.
