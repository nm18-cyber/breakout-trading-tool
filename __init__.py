"""
Breakout Trading Tool - Main Package
"""
from .config import Config, DEFAULT_CONFIG
from .data_loader import DataLoader, create_data_loader
from .indicators import add_indicators, get_latest_indicators
from .strategy import BreakoutStrategy, Signal, Position, create_strategy
from .backtester import VectorizedBacktester, BacktestResult, run_backtest

__version__ = "1.0.0"
__author__ = "Quantitative Developer"

__all__ = [
    "Config",
    "DEFAULT_CONFIG",
    "DataLoader",
    "create_data_loader",
    "add_indicators",
    "get_latest_indicators",
    "BreakoutStrategy",
    "Signal",
    "Position",
    "create_strategy",
    "VectorizedBacktester",
    "BacktestResult",
    "run_backtest",
]