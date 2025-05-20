"""
Data processor for the Bybit Perpetual Futures Screener.
Processes market data and identifies trading opportunities.
"""

import logging
import pandas as pd
from typing import Dict, List, Optional, Any
from datetime import datetime
import time

import config

logger = logging.getLogger(__name__)

class MarketData:
    """Class to store and process market data."""

    def __init__(self):
        """Initialize the market data storage."""
        self.tickers = {}  # Symbol -> ticker data
        self.instruments = {}  # Symbol -> instrument data
        self.recent_trades = {}  # Symbol -> list of recent trades
        self.opportunities = []  # List of identified opportunities
        self.opportunities_history = []  # Historical list of opportunities (persists across updates)
        self.top_volume_coins = []  # List of top volume coins
        self.last_update = 0  # Timestamp of last update
        self.signal_history = {}  # Symbol -> dict of signal types and their last occurrence time
        self.price_history = {}  # Symbol -> list of recent prices for trend analysis
        self.volume_history = {}  # Symbol -> list of recent volumes for correlation analysis

    def update_tickers(self, tickers_data: Dict):
        """
        Update the tickers data.

        Args:
            tickers_data: Tickers data from the API
        """
        if not tickers_data or 'result' not in tickers_data or 'list' not in tickers_data['result']:
            logger.warning("Invalid tickers data format")
            return

        ticker_list = tickers_data['result']['list']
        for ticker in ticker_list:
            symbol = ticker.get('symbol')
            if symbol:
                # Store previous price if it exists
                if symbol in self.tickers:
                    ticker['prev_stored_price'] = self.tickers[symbol].get('lastPrice')

                # Update ticker
                self.tickers[symbol] = ticker

                # Update price history for trend analysis
                if 'lastPrice' in ticker:
                    if symbol not in self.price_history:
                        self.price_history[symbol] = []

                    # Keep only the last 10 prices
                    price_history = self.price_history[symbol]
                    price_history.append(float(ticker['lastPrice']))
                    self.price_history[symbol] = price_history[-10:]

                # Update volume history for correlation analysis
                if 'volume24h' in ticker:
                    if symbol not in self.volume_history:
                        self.volume_history[symbol] = []

                    # Keep only the last 10 volume readings
                    volume_history = self.volume_history[symbol]
                    volume_history.append(float(ticker['volume24h']))
                    self.volume_history[symbol] = volume_history[-10:]

        self.last_update = time.time()
        logger.debug(f"Updated tickers for {len(ticker_list)} symbols")

    def update_instruments(self, instruments_data: Dict):
        """
        Update the instruments data.

        Args:
            instruments_data: Instruments data from the API
        """
        if not instruments_data or 'result' not in instruments_data or 'list' not in instruments_data['result']:
            logger.warning("Invalid instruments data format")
            return

        instrument_list = instruments_data['result']['list']
        for instrument in instrument_list:
            symbol = instrument.get('symbol')
            if symbol:
                self.instruments[symbol] = instrument

        logger.debug(f"Updated instruments for {len(instrument_list)} symbols")

    def update_recent_trades(self, symbol: str, trades_data: Dict):
        """
        Update the recent trades data for a symbol.

        Args:
            symbol: Symbol name
            trades_data: Recent trades data from the API
        """
        if not trades_data or 'result' not in trades_data or 'list' not in trades_data['result']:
            logger.warning(f"Invalid trades data format for {symbol}")
            return

        trade_list = trades_data['result']['list']
        self.recent_trades[symbol] = trade_list

        logger.debug(f"Updated {len(trade_list)} recent trades for {symbol}")

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

    def identify_big_trades(self, symbol: str, threshold: float = config.BIG_TRADE_THRESHOLD) -> List[Dict]:
        """
        Identify big trades for a symbol.

        Args:
            symbol: Symbol name
            threshold: Size threshold in USD

        Returns:
            List of big trades
        """
        if symbol not in self.recent_trades:
            return []

        big_trades = []
        for trade in self.recent_trades[symbol]:
            # Calculate trade value
            price = float(trade.get('price', 0))
            size = float(trade.get('size', 0))
            value = price * size

            if value >= threshold:
                # Apply signal cooldown
                side = trade.get('side', '')
                signal_type = f"big_trade_{side.lower()}"
                if not self.check_signal_cooldown(symbol, signal_type):
                    continue

                trade_info = {
                    'symbol': symbol,
                    'price': price,
                    'size': size,
                    'value': value,
                    'side': side,
                    'time': datetime.fromtimestamp(int(trade.get('time', 0)) / 1000).strftime('%H:%M:%S'),
                    'type': 'big_trade',
                    'score': 0  # Will be calculated later
                }
                big_trades.append(trade_info)

        return big_trades

    def identify_price_movements(self, threshold: float = config.PRICE_CHANGE_THRESHOLD) -> List[Dict]:
        """
        Identify significant price movements.

        Args:
            threshold: Price change threshold in percentage

        Returns:
            List of symbols with significant price movements
        """
        movements = []

        for symbol, ticker in self.tickers.items():
            if 'lastPrice' in ticker and 'prev_stored_price' in ticker and ticker['prev_stored_price']:
                current_price = float(ticker['lastPrice'])
                prev_price = float(ticker['prev_stored_price'])

                # Calculate percentage change
                pct_change = ((current_price - prev_price) / prev_price) * 100

                if abs(pct_change) >= threshold:
                    direction = 'up' if pct_change > 0 else 'down'

                    # Apply signal cooldown
                    signal_type = f"price_movement_{direction}"
                    if not self.check_signal_cooldown(symbol, signal_type):
                        continue

                    # Check for trend confirmation
                    has_trend = self.check_trend_confirmation(symbol, direction)

                    movement = {
                        'symbol': symbol,
                        'current_price': current_price,
                        'prev_price': prev_price,
                        'pct_change': pct_change,
                        'direction': direction,
                        'has_trend': has_trend,
                        'time': datetime.now().strftime('%H:%M:%S'),
                        'type': 'price_movement',
                        'score': 0  # Will be calculated later
                    }
                    movements.append(movement)

        return movements

    def check_signal_cooldown(self, symbol: str, signal_type: str) -> bool:
        """
        Check if a signal is in cooldown period.

        Args:
            symbol: Symbol name
            signal_type: Type of signal

        Returns:
            True if signal is allowed (not in cooldown), False otherwise
        """
        current_time = time.time()

        # Initialize signal history for symbol if not exists
        if symbol not in self.signal_history:
            self.signal_history[symbol] = {}

        # Check if signal type exists and is in cooldown
        if signal_type in self.signal_history[symbol]:
            last_time = self.signal_history[symbol][signal_type]
            if current_time - last_time < config.SIGNAL_COOLDOWN_SECONDS:
                return False

        # Update last occurrence time
        self.signal_history[symbol][signal_type] = current_time
        return True

    def check_trend_confirmation(self, symbol: str, direction: str) -> bool:
        """
        Check if there's a confirmed trend in the specified direction.

        Args:
            symbol: Symbol name
            direction: Trend direction ('up' or 'down')

        Returns:
            True if trend is confirmed, False otherwise
        """
        if symbol not in self.price_history:
            return False

        prices = self.price_history[symbol]
        if len(prices) < config.TREND_CONFIRMATION_PERIODS + 1:
            return False

        # Check last N periods for consistent direction
        is_confirmed = True
        for i in range(1, config.TREND_CONFIRMATION_PERIODS + 1):
            if direction == 'up' and prices[-i] <= prices[-i-1]:
                is_confirmed = False
                break
            elif direction == 'down' and prices[-i] >= prices[-i-1]:
                is_confirmed = False
                break

        return is_confirmed

    def calculate_volume_price_correlation(self, symbol: str) -> float:
        """
        Calculate correlation between volume and price changes.

        Args:
            symbol: Symbol name

        Returns:
            Correlation coefficient (-1 to 1)
        """
        if symbol not in self.price_history or symbol not in self.volume_history:
            return 0

        prices = self.price_history[symbol]
        volumes = self.volume_history[symbol]

        # Need at least 3 data points for meaningful correlation
        if len(prices) < 3 or len(volumes) < 3:
            return 0

        # Use only the common length
        min_len = min(len(prices), len(volumes))
        prices = prices[-min_len:]
        volumes = volumes[-min_len:]

        # Calculate price changes
        price_changes = [prices[i] - prices[i-1] for i in range(1, len(prices))]

        # Calculate correlation using pandas
        try:
            df = pd.DataFrame({
                'price_change': price_changes,
                'volume': volumes[1:]  # Align with price_changes
            })
            correlation = df['price_change'].corr(df['volume'])
            return correlation if not pd.isna(correlation) else 0
        except Exception as e:
            logger.warning(f"Error calculating correlation: {e}")
            return 0

    def calculate_signal_score(self, signal: Dict) -> float:
        """
        Calculate a quality score for a signal.

        Args:
            signal: Signal data

        Returns:
            Signal quality score
        """
        symbol = signal.get('symbol', '')
        signal_type = signal.get('type', '')
        base_score = 0
        directional_bias = None  # 'long', 'short', or None

        if signal_type == 'big_trade':
            # Score based on trade size relative to threshold
            value = signal.get('value', 0)
            side = signal.get('side', '')

            # Higher score for larger trades
            base_score = (value / config.BIG_TRADE_THRESHOLD) * 10

            # Set directional bias based on trade side
            if side.lower() == 'buy':
                directional_bias = 'long'
                # Check if price is also moving up for stronger confirmation
                if self.check_trend_confirmation(symbol, 'up'):
                    base_score *= 1.5
            elif side.lower() == 'sell':
                directional_bias = 'short'
                # Check if price is also moving down for stronger confirmation
                if self.check_trend_confirmation(symbol, 'down'):
                    base_score *= 1.5

        elif signal_type == 'price_movement':
            # Score based on price change magnitude and trend confirmation
            pct_change = abs(signal.get('pct_change', 0))
            direction = signal.get('direction', '')

            # Higher base score for price movements
            base_score = (pct_change / config.PRICE_CHANGE_THRESHOLD) * 8

            # Set directional bias
            if direction == 'up':
                directional_bias = 'long'
            else:
                directional_bias = 'short'

            # Significant bonus for trend confirmation
            if self.check_trend_confirmation(symbol, direction):
                base_score *= 2.0

            # Additional bonus for stronger moves
            if pct_change > config.PRICE_CHANGE_THRESHOLD * 2:
                base_score *= 1.5

        elif signal_type == 'volume_spike':
            # Score based on volume spike ratio
            ratio = signal.get('ratio', 0)
            base_score = (ratio / (config.VOLUME_THRESHOLD_PERCENTAGE / 100)) * 5

            # Determine directional bias based on recent price action
            if symbol in self.price_history and len(self.price_history[symbol]) >= 3:
                prices = self.price_history[symbol]
                if prices[-1] > prices[-3]:  # Price trending up
                    directional_bias = 'long'
                elif prices[-1] < prices[-3]:  # Price trending down
                    directional_bias = 'short'

            # Bonus for volume-price correlation
            correlation = self.calculate_volume_price_correlation(symbol)
            if abs(correlation) > config.VOLUME_PRICE_CORRELATION_THRESHOLD:
                base_score *= 1.8
                # Use correlation sign to determine direction if not already set
                if directional_bias is None:
                    if correlation > 0:
                        directional_bias = 'long'
                    else:
                        directional_bias = 'short'

        # Apply combined signal bonus if applicable
        if self.has_combined_signals(symbol):
            base_score *= config.COMBINED_SIGNAL_BONUS

        # Store directional bias in the signal
        signal['directional_bias'] = directional_bias

        # If directional bias is required but not present, significantly reduce score
        if config.DIRECTIONAL_BIAS_REQUIRED and directional_bias is None:
            base_score *= 0.3

        return base_score

    def has_combined_signals(self, symbol: str) -> bool:
        """
        Check if a symbol has multiple types of signals recently.

        Args:
            symbol: Symbol name

        Returns:
            True if symbol has multiple signal types, False otherwise
        """
        if symbol not in self.signal_history:
            return False

        signal_types = self.signal_history[symbol]
        current_time = time.time()
        recent_signals = 0

        for signal_type, last_time in signal_types.items():
            if current_time - last_time < config.SIGNAL_COOLDOWN_SECONDS * 2:
                recent_signals += 1

        return recent_signals > 1

    def identify_volume_spikes(self, threshold_pct: float = config.VOLUME_THRESHOLD_PERCENTAGE) -> List[Dict]:
        """
        Identify volume spikes.

        Args:
            threshold_pct: Volume spike threshold as percentage of 24h average

        Returns:
            List of symbols with volume spikes
        """
        spikes = []

        for symbol, ticker in self.tickers.items():
            if 'volume24h' in ticker:
                volume_24h = float(ticker['volume24h'])
                # Calculate hourly average volume (24h volume / 24)
                avg_hourly_volume = volume_24h / 24

                # Get recent trades volume
                if symbol in self.recent_trades:
                    recent_trades = self.recent_trades[symbol]
                    # Calculate recent volume (last 10 minutes)
                    recent_volume = sum(float(trade.get('size', 0)) for trade in recent_trades
                                      if int(trade.get('time', 0)) > (time.time() - 600) * 1000)

                    # Check if recent volume exceeds threshold
                    ratio = recent_volume / avg_hourly_volume
                    if ratio > (threshold_pct / 100):
                        # Apply signal cooldown
                        if not self.check_signal_cooldown(symbol, 'volume_spike'):
                            continue

                        spike = {
                            'symbol': symbol,
                            'recent_volume': recent_volume,
                            'avg_hourly_volume': avg_hourly_volume,
                            'ratio': ratio,
                            'time': datetime.now().strftime('%H:%M:%S'),
                            'type': 'volume_spike',
                            'score': 0  # Will be calculated later
                        }
                        spikes.append(spike)

        return spikes

    def update_opportunities(self):
        """Update the list of trading opportunities."""
        new_opportunities = []

        # Process each top volume coin
        top_coins = self.get_top_volume_coins(config.TOP_COINS_LIMIT)
        for coin in top_coins:
            symbol = coin.get('symbol')
            if not symbol:
                continue

            # Add big trades
            big_trades = self.identify_big_trades(symbol)
            new_opportunities.extend(big_trades)

        # Add price movements
        price_movements = self.identify_price_movements()
        new_opportunities.extend(price_movements)

        # Add volume spikes
        volume_spikes = self.identify_volume_spikes()
        new_opportunities.extend(volume_spikes)

        # Calculate signal scores
        for opportunity in new_opportunities:
            score = self.calculate_signal_score(opportunity)
            opportunity['score'] = round(score, 2)

        # Mark high-quality signals with directional bias
        for opportunity in new_opportunities:
            score = opportunity.get('score', 0)
            directional_bias = opportunity.get('directional_bias')

            # Only consider signals with sufficient score AND directional bias as high quality
            opportunity['high_quality'] = (score >= config.MIN_SIGNAL_SCORE and
                                          (not config.DIRECTIONAL_BIAS_REQUIRED or directional_bias is not None))

            # Add a unique ID to each opportunity for deduplication
            symbol = opportunity.get('symbol', '')
            opp_type = opportunity.get('type', '')
            time_str = opportunity.get('time', '')
            opportunity['id'] = f"{symbol}_{opp_type}_{time_str}"

        # Add new opportunities to history
        if new_opportunities:
            # Add timestamp to track when the opportunity was added to history
            current_time = datetime.now().strftime('%H:%M:%S')
            for opp in new_opportunities:
                opp['added_time'] = current_time

            # Add to history
            self.opportunities_history.extend(new_opportunities)

            # Deduplicate by ID (keep the newest)
            unique_ids = {}
            for opp in self.opportunities_history:
                opp_id = opp.get('id')
                if opp_id:
                    unique_ids[opp_id] = opp

            # Convert back to list and sort by time (newest first)
            self.opportunities_history = list(unique_ids.values())
            self.opportunities_history.sort(key=lambda x: x.get('time', ''), reverse=True)

            # Keep only the most recent 20 opportunities in history
            self.opportunities_history = self.opportunities_history[:20]

        # Set current opportunities to the history
        self.opportunities = self.opportunities_history

        # Log statistics
        high_quality_count = sum(1 for opp in self.opportunities if opp.get('high_quality', False))
        logger.info(f"Updated opportunities: {len(self.opportunities)} signals in history, {high_quality_count} high-quality")

        return self.opportunities
