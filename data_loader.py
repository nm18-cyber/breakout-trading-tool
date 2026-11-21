"""
Data loader module for fetching historical OHLCV data with local caching.
"""
import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import pandas as pd
import yfinance as yf
from pathlib import Path

from config import DEFAULT_CONFIG, Config

logger = logging.getLogger(__name__)


class DataLoader:
    """Handles fetching and caching of historical market data."""
    
    def __init__(self, config: Config = DEFAULT_CONFIG):
        self.config = config
        self.cache_dir = Path(config.CACHE_DIR)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_cache_path(self, ticker: str, interval: str = None) -> Path:
        """Generate cache file path for a ticker."""
        if interval is None:
            interval = self.config.DATA_INTERVAL
        safe_ticker = ticker.replace(".", "_").replace("/", "_")
        safe_interval = interval.replace("m", "min").replace("h", "hr")
        return self.cache_dir / f"{safe_ticker}_{safe_interval}.parquet"
    
    def _is_cache_valid(self, cache_path: Path, max_age_days: int = 1) -> bool:
        """Check if cache file exists and is recent enough."""
        if not cache_path.exists():
            return False
        file_age = datetime.now() - datetime.fromtimestamp(cache_path.stat().st_mtime)
        return file_age.days < max_age_days
    
    def _normalize_index(self, df: pd.DataFrame) -> pd.DataFrame:
        """Keep IST timezone for session filtering."""
        # Keep timezone info as-is (yfinance returns IST for NSE)
        return df
    
    def _get_yfinance_params(self, start_date: datetime, end_date: datetime, interval: str) -> dict:
        """Get optimal yfinance parameters based on interval and date range."""
        days_diff = (end_date - start_date).days
        
        # yfinance intraday limits:
        # 1m: 7 days, 5m/15m/30m: 60 days, 1h: 730 days
        if interval in ['1m']:
            max_days = 7
        elif interval in ['5m', '15m', '30m']:
            max_days = 60
        elif interval in ['1h']:
            max_days = 730
        else:  # daily and above
            max_days = 365 * 10
        
        # Use period parameter for intraday (more reliable)
        if interval in ['1m', '5m', '15m', '30m', '1h'] and days_diff <= max_days:
            # Calculate period string
            if days_diff <= 1:
                period = '1d'
            elif days_diff <= 5:
                period = '5d'
            elif days_diff <= 30:
                period = '1mo'
            elif days_diff <= 90:
                period = '3mo'
            else:
                period = 'max'  # For 1h up to 730 days
            
            return {'period': period, 'interval': interval}
        
        # For daily or long range, use start/end
        return {'start': start_date, 'end': end_date + timedelta(days=1), 'interval': interval}
    
    def fetch_data(
        self,
        ticker: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        use_cache: bool = True,
        interval: str = None
    ) -> pd.DataFrame:
        """
        Fetch historical OHLCV data for a ticker.
        
        Args:
            ticker: Stock ticker symbol (e.g., 'RELIANCE.NS')
            start_date: Start date for data (defaults to config.BACKTEST_YEARS years ago)
            end_date: End date for data (defaults to today)
            use_cache: Whether to use cached data if available
            interval: Data interval (overrides config.DATA_INTERVAL)
            
        Returns:
            DataFrame with OHLCV data
        """
        if interval is None:
            interval = self.config.DATA_INTERVAL
        
        if start_date is None:
            start_date = datetime.now() - timedelta(days=self.config.BACKTEST_YEARS * 365)
        if end_date is None:
            end_date = datetime.now()
        
        cache_path = self._get_cache_path(ticker, interval)
        
        # Try to load from cache first
        if use_cache and self._is_cache_valid(cache_path):
            try:
                df = pd.read_parquet(cache_path)
                # Normalize index to handle timezone
                df = self._normalize_index(df)
                # Filter to requested date range (handle timezone-aware indices)
                # Convert both to naive for comparison
                idx = df.index
                if idx.tz is not None:
                    idx = idx.tz_localize(None)
                start_naive = start_date.replace(tzinfo=None) if hasattr(start_date, 'tzinfo') and start_date.tzinfo else start_date
                end_naive = end_date.replace(tzinfo=None) if hasattr(end_date, 'tzinfo') and end_date.tzinfo else end_date
                df = df[(idx >= start_naive) & (idx <= end_naive)]
                if not df.empty:
                    logger.info(f"Loaded {ticker} [{interval}] from cache ({len(df)} rows)")
                    return df
            except Exception as e:
                logger.warning(f"Failed to load cache for {ticker} [{interval}]: {e}")
        
        # Fetch from yfinance
        try:
            logger.info(f"Fetching {ticker} [{interval}] from yfinance...")
            yf_ticker = yf.Ticker(ticker)
            
            # Get optimal yfinance parameters
            yf_params = self._get_yfinance_params(start_date, end_date, interval)
            yf_params['auto_adjust'] = True
            yf_params['actions'] = False
            
            df = yf_ticker.history(**yf_params)
            
            if df.empty:
                logger.warning(f"No data returned for {ticker} [{interval}]")
                return pd.DataFrame()
            
            # Standardize column names
            df.columns = [col.lower() for col in df.columns]
            df.index = pd.to_datetime(df.index)
            df = self._normalize_index(df)
            df = df.sort_index()
            
            # Filter to requested date range (handle timezone-aware indices)
            idx = df.index
            if idx.tz is not None:
                idx = idx.tz_localize(None)
            start_naive = start_date.replace(tzinfo=None) if hasattr(start_date, 'tzinfo') and start_date.tzinfo else start_date
            end_naive = end_date.replace(tzinfo=None) if hasattr(end_date, 'tzinfo') and end_date.tzinfo else end_date
            df = df[(idx >= start_naive) & (idx <= end_naive)]
            
            # Keep only OHLCV columns
            df = df[['open', 'high', 'low', 'close', 'volume']]
            
            # Save to cache
            if use_cache:
                try:
                    df.to_parquet(cache_path)
                    logger.info(f"Cached {ticker} [{interval}] ({len(df)} rows)")
                except Exception as e:
                    logger.warning(f"Failed to cache {ticker} [{interval}]: {e}")
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching data for {ticker} [{interval}]: {e}")
            return pd.DataFrame()
    
    def fetch_multiple(
        self,
        tickers: List[str],
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        use_cache: bool = True,
        interval: str = None
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch data for multiple tickers.
        
        Returns:
            Dictionary mapping ticker to DataFrame
        """
        if interval is None:
            interval = self.config.DATA_INTERVAL
        
        results = {}
        for ticker in tickers:
            df = self.fetch_data(ticker, start_date, end_date, use_cache, interval)
            if not df.empty:
                results[ticker] = df
        return results
    
    def get_latest_data(self, tickers: List[str], interval: str = None) -> Dict[str, pd.DataFrame]:
        """Get the most recent data for screening (last ~60 days for indicators)."""
        if interval is None:
            interval = self.config.DATA_INTERVAL
        end_date = datetime.now()
        start_date = end_date - timedelta(days=90)  # Extra buffer for indicators
        return self.fetch_multiple(tickers, start_date, end_date, use_cache=True, interval=interval)


def create_data_loader(config: Config = DEFAULT_CONFIG) -> DataLoader:
    """Factory function to create a DataLoader instance."""
    return DataLoader(config)