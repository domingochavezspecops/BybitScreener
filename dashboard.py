"""
Dashboard for the Bybit Perpetual Futures Screener.
Creates a terminal-based UI using the Rich library.
"""

import logging
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.live import Live
from rich.text import Text
from rich import box

import config
from data_processor import MarketData

logger = logging.getLogger(__name__)

class Dashboard:
    """Terminal-based dashboard for displaying market data."""

    def __init__(self, market_data: MarketData):
        """
        Initialize the dashboard.

        Args:
            market_data: MarketData instance
        """
        self.market_data = market_data
        self.console = Console()
        self.layout = self._create_layout()
        self.live = Live(self.layout, refresh_per_second=1/config.REFRESH_RATE, screen=True)

    def _create_layout(self) -> Layout:
        """
        Create the dashboard layout.

        Returns:
            Layout object
        """
        layout = Layout(name="root")

        # Split into header and body
        layout.split(
            Layout(name="header", size=3),
            Layout(name="alerts")
        )

        return layout

    def _generate_header(self) -> Panel:
        """
        Generate the header panel.

        Returns:
            Panel object
        """
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        last_update = datetime.fromtimestamp(self.market_data.last_update).strftime("%H:%M:%S") if self.market_data.last_update else "N/A"

        title = Text("Bybit Perpetual Futures Screener", style=f"bold {config.COLOR_HEADER}")
        subtitle = Text(f"Last Update: {last_update} | Current Time: {now}", style="dim")

        return Panel(
            title + "\n" + subtitle,
            box=box.ROUNDED,
            style=config.COLOR_HEADER,
            border_style=config.COLOR_HEADER
        )

    def _generate_opportunities_table(self) -> Table:
        """
        Generate the opportunities table.

        Returns:
            Table object
        """
        table = Table(
            title="Trading Opportunities",
            box=box.ROUNDED,
            title_style=f"bold {config.COLOR_HEADER}",
            border_style=config.COLOR_HEADER,
            expand=True
        )

        # Add columns
        table.add_column("Time", style="dim")
        table.add_column("Direction", style="bold")
        table.add_column("Symbol", style="bold")
        table.add_column("Signal Type", style="bold")
        table.add_column("Details", justify="right")
        table.add_column("Strength", justify="center")

        # Filter for only high-quality signals with directional bias
        filtered_opportunities = [
            opp for opp in self.market_data.opportunities
            if opp.get('high_quality', False) and opp.get('directional_bias') is not None
        ]

        # Add rows
        for opp in filtered_opportunities:
            time_str = opp.get('time', '')
            added_time = opp.get('added_time', '')
            symbol = opp.get('symbol', '')
            opp_type = opp.get('type', '')
            score = opp.get('score', 0)
            directional_bias = opp.get('directional_bias', '')

            # Format time with added time indicator
            if added_time:
                # If the signal was added in the current session, mark it as "NEW"
                now = datetime.now()
                current_time_str = now.strftime('%H:%M:%S')
                time_parts = added_time.split(':')
                current_parts = current_time_str.split(':')

                # Check if the signal was added within the last 30 seconds
                if (time_parts[0] == current_parts[0] and  # Same hour
                    time_parts[1] == current_parts[1] and  # Same minute
                    abs(int(time_parts[2]) - int(current_parts[2])) < 30):  # Within 30 seconds
                    time_str = f"[bright_white]NEW[/bright_white] {time_str}"

            # Format direction with clear LONG/SHORT indicator
            if directional_bias == 'long':
                direction = f"[{config.COLOR_POSITIVE}]LONG[/{config.COLOR_POSITIVE}]"
            elif directional_bias == 'short':
                direction = f"[{config.COLOR_NEGATIVE}]SHORT[/{config.COLOR_NEGATIVE}]"
            else:
                direction = "NEUTRAL"

            # Format signal strength
            if score >= 20:
                strength_color = "bright_green"
                strength_text = "VERY STRONG"
            elif score >= 15:
                strength_color = "green"
                strength_text = "STRONG"
            else:
                strength_color = config.COLOR_NEUTRAL
                strength_text = "GOOD"

            strength = f"[{strength_color}]{strength_text} ({score:.1f})[/{strength_color}]"

            # Format details and signal type based on opportunity type
            if opp_type == 'big_trade':
                value = opp.get('value', 0)
                details = f"${value:,.0f}"

                # Format type
                signal_type = "Large Order"

                # Add trend confirmation indicator if available
                has_trend = self.market_data.check_trend_confirmation(symbol, 'up' if directional_bias == 'long' else 'down')
                if has_trend:
                    signal_type += " + Trend ✓"

            elif opp_type == 'price_movement':
                pct_change = opp.get('pct_change', 0)
                has_trend = opp.get('has_trend', False)

                # Add trend confirmation indicator
                trend_indicator = "✓" if has_trend else ""
                details = f"{abs(pct_change):.2f}% {trend_indicator}"

                # Format type
                signal_type = "Price Move"

                # Check for volume confirmation
                if self.market_data.has_combined_signals(symbol):
                    signal_type += " + Volume"

            elif opp_type == 'volume_spike':
                ratio = opp.get('ratio', 0)
                details = f"{ratio:.2f}x avg"

                # Check if there's a combined signal
                has_combined = self.market_data.has_combined_signals(symbol)

                # Format type
                signal_type = "Volume Spike"
                if has_combined:
                    signal_type += " + Price"

            else:
                details = ""
                signal_type = opp_type.capitalize()

            table.add_row(time_str, direction, symbol, signal_type, details, strength)

        # If no opportunities, add a message
        if not filtered_opportunities:
            table.add_row("", "", "[dim]No trading opportunities at this time[/dim]", "", "", "")

        return table

    def update(self):
        """Update the dashboard with the latest data."""
        # Update header
        self.layout["header"].update(self._generate_header())

        # Update alerts
        self.layout["alerts"].update(self._generate_opportunities_table())

    def start(self):
        """Start the live dashboard."""
        logger.info("Starting dashboard")
        self.live.start()

    def stop(self):
        """Stop the live dashboard."""
        logger.info("Stopping dashboard")
        self.live.stop()
