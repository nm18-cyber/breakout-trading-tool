"""
Technical indicators calculation module.
"""
import pandas as pd
import numpy as np
from config import DEFAULT_CONFIG, Config


def calculate_sma(close: pd.Series, period: int) -> pd.Series:
    """Calculate Simple Moving Average."""
    return close.rolling(window=period, min_periods=1).mean()


def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    """
    Calculate Average True Range (ATR) using Wilder's smoothing method.
    
    True Range = max(high - low, abs(high - prev_close), abs(low - prev_close))
    ATR = SMA of True Range over period (Wilder's smoothing)
    """
    prev_close = close.shift(1)
    
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # Wilder's smoothing (equivalent to EMA with alpha = 1/period)
    atr = true_range.ewm(alpha=1/period, adjust=False).mean()
    
    return atr


def calculate_rolling_high(high: pd.Series, period: int) -> pd.Series:
    """Calculate rolling highest high over period."""
    return high.rolling(window=period, min_periods=1).max()


def calculate_rolling_low(low: pd.Series, period: int) -> pd.Series:
    """Calculate rolling lowest low over period."""
    return low.rolling(window=period, min_periods=1).min()


def calculate_avg_volume(volume: pd.Series, period: int) -> pd.Series:
    """Calculate average volume over period."""
    return volume.rolling(window=period, min_periods=1).mean()


def add_indicators(df: pd.DataFrame, config: Config = DEFAULT_CONFIG) -> pd.DataFrame:
    """
    Add all required technical indicators to the DataFrame.
    
    Args:
        df: DataFrame with OHLCV columns (open, high, low, close, volume)
        config: Configuration object with indicator periods
        
    Returns:
        DataFrame with added indicator columns
    """
    df = df.copy()
    
    # Ensure required columns exist
    required_cols = ['open', 'high', 'low', 'close', 'volume']
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")
    
    # 200-day SMA
    df['200_sma'] = calculate_sma(df['close'], config.SMA_LONG_PERIOD)
    
    # 20-day Average Volume
    df['20_avg_vol'] = calculate_avg_volume(df['volume'], config.VOLUME_AVG_PERIOD)
    
    # 14-day ATR
    df['14_atr'] = calculate_atr(
        df['high'], df['low'], df['close'], config.ATR_PERIOD
    )
    
    # Rolling 20-day High
    df['20_day_high'] = calculate_rolling_high(df['high'], config.BREAKOUT_SHORT_PERIOD)
    
    # Rolling 50-day High
    df['50_day_high'] = calculate_rolling_high(df['high'], config.BREAKOUT_MEDIUM_PERIOD)
    
    # Rolling 52-week (252-day) High
    df['52w_high'] = calculate_rolling_high(df['high'], config.BREAKOUT_LONG_PERIOD)
    
    # Volume ratio (current volume / average volume)
    df['vol_ratio'] = df['volume'] / df['20_avg_vol']
    
    # Distance from 200 SMA (percentage)
    df['dist_from_200sma'] = (df['close'] - df['200_sma']) / df['200_sma'] * 100
    
    # Distance from 20-day high (percentage)
    df['dist_from_20d_high'] = (df['close'] - df['20_day_high']) / df['20_day_high'] * 100
    
    # Distance from 50-day high (percentage)
    df['dist_from_50d_high'] = (df['close'] - df['50_day_high']) / df['50_day_high'] * 100
    
    # Distance from 52-week high (percentage)
    df['dist_from_52w_high'] = (df['close'] - df['52w_high']) / df['52w_high'] * 100
    
    return df


def get_latest_indicators(df: pd.DataFrame) -> dict:
    """Extract the latest indicator values as a dictionary."""
    if df.empty:
        return {}
    
    latest = df.iloc[-1]
    return {
        'close': latest.get('close'),
        '200_sma': latest.get('200_sma'),
        '20_avg_vol': latest.get('20_avg_vol'),
        '14_atr': latest.get('14_atr'),
        '20_day_high': latest.get('20_day_high'),
        '50_day_high': latest.get('50_day_high'),
        '52w_high': latest.get('52w_high'),
        'vol_ratio': latest.get('vol_ratio'),
        'dist_from_200sma': latest.get('dist_from_200sma'),
        'dist_from_20d_high': latest.get('dist_from_20d_high'),
        'dist_from_50d_high': latest.get('dist_from_50d_high'),
        'dist_from_52w_high': latest.get('dist_from_52w_high'),
        'volume': latest.get('volume'),
    }