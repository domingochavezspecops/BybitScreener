"""
Utility functions for the Bybit Perpetual Futures Screener.
"""

import logging
import os
import sys
from typing import Dict, List, Optional, Any
from datetime import datetime

def setup_logging(log_level: str = "INFO", log_file: Optional[str] = None):
    """
    Set up logging configuration.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (optional)
    """
    # Convert string log level to logging constant
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")
    
    # Configure logging
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    handlers = [logging.StreamHandler(sys.stdout)]
    
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        handlers.append(logging.FileHandler(log_file))
    
    logging.basicConfig(
        level=numeric_level,
        format=log_format,
        handlers=handlers
    )
    
    # Reduce logging level for some noisy libraries
    logging.getLogger("websocket").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    logging.info(f"Logging configured with level {log_level}")

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

def format_timestamp(timestamp_ms: int) -> str:
    """
    Format a timestamp in milliseconds to a human-readable string.
    
    Args:
        timestamp_ms: Timestamp in milliseconds
        
    Returns:
        Formatted timestamp string
    """
    dt = datetime.fromtimestamp(timestamp_ms / 1000)
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def calculate_percentage_change(old_value: float, new_value: float) -> float:
    """
    Calculate percentage change between two values.
    
    Args:
        old_value: Old value
        new_value: New value
        
    Returns:
        Percentage change
    """
    if old_value == 0:
        return 0
    return ((new_value - old_value) / old_value) * 100
