"""
Core breakout trading strategy logic.
"""
from dataclasses import dataclass
from typing import Optional, List, Dict, Callable
import pandas as pd
import numpy as np
from config import DEFAULT_CONFIG, Config
from indicators import add_indicators, get_latest_indicators


@dataclass
class Signal:
    """Trading signal with entry, stop loss, target, and position size."""
    ticker: str
    date: pd.Timestamp
    entry_price: float
    stop_loss: float
    target_price: float
    position_size: int
    signal_type: str  # '20d_breakout', '50d_breakout', '52w_breakout', '200sma_cross'
    volume_ratio: float
    atr: float
    
    @property
    def risk_per_share(self) -> float:
        """Risk per share (entry - stop loss)."""
        return self.entry_price - self.stop_loss
    
    @property
    def reward_per_share(self) -> float:
        """Reward per share (target - entry)."""
        return self.target_price - self.entry_price
    
    @property
    def risk_reward_ratio(self) -> float:
        """Risk-reward ratio."""
        risk = self.risk_per_share
        return self.reward_per_share / risk if risk > 0 else 0.0


@dataclass
class Position:
    """Represents an open position."""
    signal: Signal
    entry_date: pd.Timestamp
    shares: int
    entry_price: float
    stop_loss: float
    target_price: float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    
    def update_price(self, price: float):
        """Update current price and unrealized P&L."""
        self.current_price = price
        self.unrealized_pnl = (price - self.entry_price) * self.shares
    
    def check_stop_loss(self, low_price: float) -> bool:
        """Check if stop loss was hit."""
        return low_price <= self.stop_loss
    
    def check_target(self, high_price: float) -> bool:
        """Check if target was hit."""
        return high_price >= self.target_price


class BreakoutStrategy:
    """Breakout trading strategy implementation."""
    
    def __init__(self, config: Config = DEFAULT_CONFIG):
        self.config = config
        # Placeholder hooks for broker API integration
        self.order_executor: Optional[Callable] = None
        self.position_manager: Optional[Callable] = None
    
    def set_order_executor(self, executor: Callable):
        """Hook for broker API order execution (e.g., Zerodha Kite Connect)."""
        self.order_executor = executor
    
    def set_position_manager(self, manager: Callable):
        """Hook for position management via broker API."""
        self.position_manager = manager
    
    def _calculate_position_size(
        self,
        entry_price: float,
        stop_loss: float,
        capital: float
    ) -> int:
        """Calculate position size risking 1% of capital."""
        risk_per_share = entry_price - stop_loss
        if risk_per_share <= 0:
            return 0
        risk_amount = capital * self.config.RISK_PER_TRADE_PCT
        shares = int(risk_amount / risk_per_share)
        return max(0, shares)
    
    def check_entry_signal(
        self,
        df: pd.DataFrame,
        ticker: str,
        capital: float
    ) -> Optional[Signal]:
        """
        Check for entry signal on the latest bar.
        
        Entry conditions:
        1. Close breaks above 20-day High OR 50-day High OR 52-week High OR crosses above 200 SMA
        2. Volume >= 1.0x 20-day average volume
        """
        min_periods = max(self.config.BREAKOUT_LONG_PERIOD, self.config.SMA_LONG_PERIOD, self.config.BREAKOUT_MEDIUM_PERIOD)
        if len(df) < min_periods:
            return None
        
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) > 1 else latest
        
        # Get indicator values
        close = latest['close']
        volume = latest['volume']
        avg_vol = latest['20_avg_vol']
        atr = latest['14_atr']
        high_20d = latest['20_day_high']
        high_50d = latest.get('50_day_high', 0)
        high_52w = latest['52w_high']
        sma_200 = latest['200_sma']
        
        # Skip if any indicator is NaN
        if any(pd.isna([close, volume, avg_vol, atr, high_20d, high_52w, sma_200])):
            return None
        
        # Volume condition
        vol_ratio = volume / avg_vol if avg_vol > 0 else 0
        if vol_ratio < self.config.VOLUME_MULTIPLIER:
            return None
        
        # Trend filter: Only long when price > 200 SMA (if enabled)
        if self.config.USE_TREND_FILTER and close <= sma_200:
            return None
        
        # Check breakout conditions
        signal_types = []
        
        # 1. 20-day high breakout (close > previous 20-day high)
        prev_high_20d = df.iloc[-2]['20_day_high'] if len(df) > 1 else high_20d
        if close > prev_high_20d:
            signal_types.append('20d_breakout')
        
        # 2. 50-day high breakout
        prev_high_50d = df.iloc[-2].get('50_day_high', 0) if len(df) > 1 else high_50d
        if high_50d > 0 and close > prev_high_50d:
            signal_types.append('50d_breakout')
        
        # 3. 52-week high breakout
        prev_high_52w = df.iloc[-2]['52w_high'] if len(df) > 1 else high_52w
        if close > prev_high_52w:
            signal_types.append('52w_breakout')
        
        # 4. 200 SMA cross (close > 200 SMA and previous close <= 200 SMA)
        prev_close = prev['close']
        prev_sma_200 = prev['200_sma']
        if close > sma_200 and prev_close <= prev_sma_200:
            signal_types.append('200sma_cross')
        
        if not signal_types:
            return None
        
        signal_type = '_'.join(signal_types)
        
        # Calculate stop loss: Entry - ATR_MULTIPLIER * ATR
        entry_price = close
        stop_loss = entry_price - (self.config.ATR_MULTIPLIER * atr)
        
        # Calculate target: Entry + TARGET_MULTIPLIER * risk
        risk_per_share = entry_price - stop_loss
        target_price = entry_price + (self.config.TARGET_MULTIPLIER * risk_per_share)
        
        # Calculate position size
        position_size = self._calculate_position_size(entry_price, stop_loss, capital)
        
        if position_size == 0:
            return None
        
        return Signal(
            ticker=ticker,
            date=df.index[-1],
            entry_price=entry_price,
            stop_loss=stop_loss,
            target_price=target_price,
            position_size=position_size,
            signal_type=signal_type,
            volume_ratio=vol_ratio,
            atr=atr
        )
    
    def scan_universe(
        self,
        data_dict: Dict[str, pd.DataFrame],
        capital: float = None
    ) -> List[Signal]:
        """
        Scan all tickers for current entry signals.
        
        Args:
            data_dict: Dictionary of ticker -> DataFrame with indicators
            capital: Available capital (defaults to config.INITIAL_CAPITAL)
            
        Returns:
            List of Signal objects
        """
        if capital is None:
            capital = self.config.INITIAL_CAPITAL
        
        signals = []
        for ticker, df in data_dict.items():
            if len(df) < 260:  # Need enough data for indicators
                continue
            
            # Add indicators if not present
            if '200_sma' not in df.columns:
                df = add_indicators(df, self.config)
            
            signal = self.check_entry_signal(df, ticker, capital)
            if signal:
                signals.append(signal)
        
        return signals
    
    def generate_signals_historical(
        self,
        df: pd.DataFrame,
        ticker: str,
        capital: float
    ) -> List[Signal]:
        """Generate all historical signals for backtesting."""
        signals = []
        
        # Need enough data for all indicators
        min_periods = max(self.config.BREAKOUT_LONG_PERIOD, self.config.SMA_LONG_PERIOD, self.config.BREAKOUT_MEDIUM_PERIOD)
        if len(df) < min_periods + 1:
            return signals
        
        # Add indicators
        df = add_indicators(df, self.config)
        
        # Iterate through each day
        for i in range(min_periods, len(df)):
            window = df.iloc[:i+1]
            signal = self.check_entry_signal(window, ticker, capital)
            if signal:
                signals.append(signal)
        
        return signals


def create_strategy(config: Config = DEFAULT_CONFIG) -> BreakoutStrategy:
    """Factory function to create a BreakoutStrategy instance."""
    return BreakoutStrategy(config)