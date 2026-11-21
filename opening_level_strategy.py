"""
Opening Support/Resistance Breakout + Retest Strategy
Intraday strategy using Open==Low (Support) and Open==High (Resistance) candles
"""
from dataclasses import dataclass
from typing import Optional, List, Dict, Literal
from enum import Enum
import pandas as pd
import numpy as np
from config import DEFAULT_CONFIG, Config
from indicators import add_indicators


class TradeDirection(Enum):
    LONG = "long"
    SHORT = "short"


class SetupState(Enum):
    IDLE = 0
    BREAKOUT_CONFIRMED = 1
    WAITING_RETEST = 2


@dataclass
class Level:
    """Support or Resistance level from Open==Low/High candle"""
    price: float
    timestamp: pd.Timestamp
    bar_index: int
    level_type: Literal["support", "resistance"]
    
    def is_valid(self, current_index: int, lookback: int) -> bool:
        return (current_index - self.bar_index) <= lookback


@dataclass
class RetestSignal:
    """Signal generated from retest setup"""
    ticker: str
    direction: TradeDirection
    entry_price: float
    stop_loss: float
    target_price: float
    entry_time: pd.Timestamp
    setup_state: int  # 1=breakout, 2=retest
    level_price: float
    level_type: str
    volume_ratio: float
    atr: float
    signal_details: str


class OpeningLevelStrategy:
    """
    Intraday Breakout + Retest strategy using Opening Support/Resistance levels.
    
    Level Formation:
    - Support Floor: candle where open == low (buyers in control from open)
    - Resistance Ceiling: candle where open == high (sellers in control from open)
    
    State Machine (Long):
    - State 0: Price below resistance
    - State 1: Breakout confirmed (close > resistance)
    - State 2: Waiting for retest (low <= resistance, close > resistance, bullish candle)
    
    State Machine (Short):
    - State 0: Price above support
    - State 1: Breakdown confirmed (close < support)
    - State 2: Waiting for retest (high >= support, close < support, bearish candle)
    """
    
    def __init__(self, config: Config = DEFAULT_CONFIG):
        self.config = config
        
        # Strategy-specific parameters
        self.lookback_length = getattr(config, 'OPENING_LOOKBACK', 50)
        self.retest_timeout = getattr(config, 'RETEST_TIMEOUT', 20)
        self.min_volume_ratio = getattr(config, 'MIN_VOLUME_RATIO', 1.2)
        self.atr_mult_sl = getattr(config, 'ATR_MULT_SL', 1.5)
        self.target_r_mult = getattr(config, 'TARGET_R_MULT', 2.0)
        self.use_volume_filter = getattr(config, 'USE_VOLUME_FILTER', True)
        self.require_bullish_retest = getattr(config, 'REQUIRE_BULLISH_RETEST', True)
        
        # State tracking per ticker
        self.support_level: Optional[Level] = None
        self.resistance_level: Optional[Level] = None
        self.long_state = SetupState.IDLE
        self.short_state = SetupState.IDLE
        self.breakout_bar_index = 0
        
    def reset_state(self):
        """Reset state machine for new ticker/session"""
        self.support_level = None
        self.resistance_level = None
        self.long_state = SetupState.IDLE
        self.short_state = SetupState.IDLE
        self.breakout_bar_index = 0
    
    def _is_open_eq_low(self, row: pd.Series, tolerance: float = 0.0001) -> bool:
        """Check if open == low (with small tolerance for floating point)"""
        return abs(row['open'] - row['low']) / row['open'] < tolerance
    
    def _is_open_eq_high(self, row: pd.Series, tolerance: float = 0.0001) -> bool:
        """Check if open == high (with small tolerance for floating point)"""
        return abs(row['open'] - row['high']) / row['open'] < tolerance
    
    def _is_bullish_candle(self, row: pd.Series) -> bool:
        return row['close'] > row['open']
    
    def _is_bearish_candle(self, row: pd.Series) -> bool:
        return row['close'] < row['open']
    
    def update_levels(self, df: pd.DataFrame, current_idx: int):
        """Update support/resistance levels from most recent qualifying candles"""
        lookback_start = max(0, current_idx - self.lookback_length)
        window = df.iloc[lookback_start:current_idx+1]
        
        # Find most recent Open==Low (Support) - search backwards
        for i in range(len(window)-1, -1, -1):
            row = window.iloc[i]
            if self._is_open_eq_low(row):
                self.support_level = Level(
                    price=row['low'],
                    timestamp=row.name,
                    bar_index=lookback_start + i,
                    level_type="support"
                )
                break
        
        # Find most recent Open==High (Resistance) - search backwards
        for i in range(len(window)-1, -1, -1):
            row = window.iloc[i]
            if self._is_open_eq_high(row):
                self.resistance_level = Level(
                    price=row['high'],
                    timestamp=row.name,
                    bar_index=lookback_start + i,
                    level_type="resistance"
                )
                break
    
    def check_long_setup(self, df: pd.DataFrame, current_idx: int, capital: float) -> Optional[RetestSignal]:
        """Check for Long setup: Resistance Breakout + Retest"""
        if current_idx < 1:
            return None
            
        current = df.iloc[current_idx]
        prev = df.iloc[current_idx - 1]
        
        # Need valid resistance level
        if not self.resistance_level or not self.resistance_level.is_valid(current_idx, self.lookback_length):
            return None
        
        resistance = self.resistance_level.price
        atr = current.get('14_atr', 0)
        if atr <= 0 or pd.isna(atr):
            return None
        
        # Volume filter
        if self.use_volume_filter:
            vol_ratio = current.get('vol_ratio', 0)
            if vol_ratio < self.min_volume_ratio:
                return None
        
        # State Machine for Long
        if self.long_state == SetupState.IDLE:
            # Check for breakout: close crosses above resistance
            if prev['close'] <= resistance and current['close'] > resistance:
                self.long_state = SetupState.BREAKOUT_CONFIRMED
                self.breakout_bar_index = current_idx
        
        elif self.long_state == SetupState.BREAKOUT_CONFIRMED:
            self.long_state = SetupState.WAITING_RETEST
        
        elif self.long_state == SetupState.WAITING_RETEST:
            # Check timeout
            if current_idx - self.breakout_bar_index > self.retest_timeout:
                self.long_state = SetupState.IDLE
                return None
            
            # Check invalidation: close back below resistance
            if current['close'] < resistance:
                self.long_state = SetupState.IDLE
                return None
            
            # Check retest trigger: low touches resistance, closes bullishly above
            retest_touched = current['low'] <= resistance * 1.001  # small tolerance
            bullish_close = current['close'] > resistance
            bullish_candle = self._is_bullish_candle(current) if self.require_bullish_retest else True
            
            if retest_touched and bullish_close and bullish_candle:
                # LONG ENTRY SIGNAL
                entry_price = current['close']
                risk_per_share = atr * self.atr_mult_sl
                stop_loss = entry_price - risk_per_share
                target_price = entry_price + (risk_per_share * self.target_r_mult)
                
                signal = RetestSignal(
                    ticker=df.attrs.get('ticker', 'UNKNOWN'),
                    direction=TradeDirection.LONG,
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    target_price=target_price,
                    entry_time=current.name,
                    setup_state=2,
                    level_price=resistance,
                    level_type="resistance_retest",
                    volume_ratio=current.get('vol_ratio', 0),
                    atr=atr,
                    signal_details=f"Resistance breakout @ {resistance:.2f}, retest entry"
                )
                
                # Reset state
                self.long_state = SetupState.IDLE
                return signal
        
        return None
    
    def check_short_setup(self, df: pd.DataFrame, current_idx: int, capital: float) -> Optional[RetestSignal]:
        """Check for Short setup: Support Breakdown + Retest"""
        if current_idx < 1:
            return None
            
        current = df.iloc[current_idx]
        prev = df.iloc[current_idx - 1]
        
        # Need valid support level
        if not self.support_level or not self.support_level.is_valid(current_idx, self.lookback_length):
            return None
        
        support = self.support_level.price
        atr = current.get('14_atr', 0)
        if atr <= 0 or pd.isna(atr):
            return None
        
        # Volume filter
        if self.use_volume_filter:
            vol_ratio = current.get('vol_ratio', 0)
            if vol_ratio < self.min_volume_ratio:
                return None
        
        # State Machine for Short
        if self.short_state == SetupState.IDLE:
            # Check for breakdown: close crosses below support
            if prev['close'] >= support and current['close'] < support:
                self.short_state = SetupState.BREAKOUT_CONFIRMED
                self.breakout_bar_index = current_idx
        
        elif self.short_state == SetupState.BREAKOUT_CONFIRMED:
            self.short_state = SetupState.WAITING_RETEST
        
        elif self.short_state == SetupState.WAITING_RETEST:
            # Check timeout
            if current_idx - self.breakout_bar_index > self.retest_timeout:
                self.short_state = SetupState.IDLE
                return None
            
            # Check invalidation: close back above support
            if current['close'] > support:
                self.short_state = SetupState.IDLE
                return None
            
            # Check retest trigger: high touches support, closes bearishly below
            retest_touched = current['high'] >= support * 0.999  # small tolerance
            bearish_close = current['close'] < support
            bearish_candle = self._is_bearish_candle(current) if self.require_bullish_retest else True
            
            if retest_touched and bearish_close and bearish_candle:
                # SHORT ENTRY SIGNAL
                entry_price = current['close']
                risk_per_share = atr * self.atr_mult_sl
                stop_loss = entry_price + risk_per_share
                target_price = entry_price - (risk_per_share * self.target_r_mult)
                
                signal = RetestSignal(
                    ticker=df.attrs.get('ticker', 'UNKNOWN'),
                    direction=TradeDirection.SHORT,
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                    target_price=target_price,
                    entry_time=current.name,
                    setup_state=2,
                    level_price=support,
                    level_type="support_retest",
                    volume_ratio=current.get('vol_ratio', 0),
                    atr=atr,
                    signal_details=f"Support breakdown @ {support:.2f}, retest entry"
                )
                
                # Reset state
                self.short_state = SetupState.IDLE
                return signal
        
        return None
    
    def check_direct_support_bounce(self, df: pd.DataFrame, current_idx: int, capital: float) -> Optional[RetestSignal]:
        """Optional: Direct bounce from Support Floor (Open==Low)"""
        if current_idx < 1:
            return None
            
        current = df.iloc[current_idx]
        
        if not self.support_level or not self.support_level.is_valid(current_idx, self.lookback_length):
            return None
        
        support = self.support_level.price
        atr = current.get('14_atr', 0)
        if atr <= 0:
            return None
        
        # Low touches support, bullish close above
        if (current['low'] <= support * 1.001 and 
            current['close'] > support and 
            self._is_bullish_candle(current)):
            
            entry_price = current['close']
            risk_per_share = atr * self.atr_mult_sl
            stop_loss = entry_price - risk_per_share
            target_price = entry_price + (risk_per_share * self.target_r_mult)
            
            return RetestSignal(
                ticker=df.attrs.get('ticker', 'UNKNOWN'),
                direction=TradeDirection.LONG,
                entry_price=entry_price,
                stop_loss=stop_loss,
                target_price=target_price,
                entry_time=current.name,
                setup_state=0,  # Direct bounce
                level_price=support,
                level_type="support_bounce",
                volume_ratio=current.get('vol_ratio', 0),
                atr=atr,
                signal_details=f"Direct support bounce @ {support:.2f}"
            )
        
        return None
    
    def scan(self, df: pd.DataFrame, capital: float) -> List[RetestSignal]:
        """Scan entire dataframe for signals"""
        signals = []
        df = df.copy()
        df.attrs['ticker'] = 'UNKNOWN'  # Will be set by caller
        
        # Need indicators
        if '14_atr' not in df.columns:
            from indicators import add_indicators
            df = add_indicators(df, self.config)
        
        for i in range(len(df)):
            # Update levels on each bar
            self.update_levels(df, i)
            
            # Check setups
            long_signal = self.check_long_setup(df, i, capital)
            if long_signal:
                signals.append(long_signal)
            
            short_signal = self.check_short_setup(df, i, capital)
            if short_signal:
                signals.append(short_signal)
            
            # Optional: direct support bounce
            bounce_signal = self.check_direct_support_bounce(df, i, capital)
            if bounce_signal:
                signals.append(bounce_signal)
        
        return signals


def create_opening_level_strategy(config: Config = DEFAULT_CONFIG) -> OpeningLevelStrategy:
    return OpeningLevelStrategy(config)