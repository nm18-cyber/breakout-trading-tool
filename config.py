"""
Configuration parameters for the Breakout Trading and Screening Tool.
"""
from dataclasses import dataclass
from typing import List


@dataclass
class Config:
    """Main configuration class for the breakout trading tool."""
    
    # Lookback periods
    SMA_LONG_PERIOD: int = 200
    VOLUME_AVG_PERIOD: int = 20
    ATR_PERIOD: int = 14
    BREAKOUT_SHORT_PERIOD: int = 20
    BREAKOUT_MEDIUM_PERIOD: int = 50
    BREAKOUT_LONG_PERIOD: int = 252  # 52 weeks
    
    # Volume threshold multiplier
    VOLUME_MULTIPLIER: float = 1.5
    
    # ATR multiplier for stop loss
    ATR_MULTIPLIER: float = 2.0
    
    # Target multiplier (risk-reward ratio)
    TARGET_MULTIPLIER: float = 2.0  # 2R target
    
    # Risk management
    RISK_PER_TRADE_PCT: float = 0.01  # 1% of capital per trade
    
    # Trend filter
    USE_TREND_FILTER: bool = True  # Only long when price > 200 SMA
    
    # Backtest settings
    BACKTEST_YEARS: int = 3
    INITIAL_CAPITAL: float = 10_00_000  # ₹10 Lakhs default
    
    # Data settings
    CACHE_DIR: str = "data_cache"
    DATA_INTERVAL: str = "1d"
    
    # === INTRADAY OPENING LEVEL STRATEGY PARAMETERS ===
    OPENING_LOOKBACK: int = 50          # Bars to look back for Open==Low/High
    RETEST_TIMEOUT: int = 20            # Max bars to wait for retest after breakout
    MIN_VOLUME_RATIO: float = 1.2       # Min volume ratio for entry
    ATR_MULT_SL: float = 1.5            # ATR multiplier for stop loss
    TARGET_R_MULT: float = 2.0          # Target as multiple of risk (R-multiple)
    USE_VOLUME_FILTER: bool = True      # Apply volume filter
    REQUIRE_BULLISH_RETEST: bool = True # Require bullish/bearish candle on retest
    
    # Session times (IST)
    SESSION_START: str = "09:15"
    SESSION_END: str = "15:30"
    SQUARE_OFF_TIME: str = "15:15"      # Force close before market close
    MAX_HOLDING_BARS: int = 100         # Max bars to hold position
    
    # Nifty 50 tickers (current as of 2024)
    NIFTY_50_TICKERS: List[str] = None
    
    # Nifty 100 tickers
    NIFTY_100_TICKERS: List[str] = None
    
    def __post_init__(self):
        if self.NIFTY_50_TICKERS is None:
            # Current Nifty 50 constituents with .NS suffix for yfinance
            # Updated to remove delisted/incorrect symbols
            self.NIFTY_50_TICKERS = [
                "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
                "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
                "LT.NS", "AXISBANK.NS", "ASIANPAINT.NS", "MARUTI.NS", "SUNPHARMA.NS",
                "TITAN.NS", "ULTRACEMCO.NS", "WIPRO.NS", "NESTLEIND.NS", "POWERGRID.NS",
                "NTPC.NS", "TECHM.NS", "BAJFINANCE.NS", "HCLTECH.NS",
                "JSWSTEEL.NS", "ADANIENT.NS", "ADANIPORTS.NS", "COALINDIA.NS", "GRASIM.NS",
                "INDUSINDBK.NS", "CIPLA.NS", "DRREDDY.NS", "EICHERMOT.NS", "HEROMOTOCO.NS",
                "BAJAJFINSV.NS", "BRITANNIA.NS", "DIVISLAB.NS", "UPL.NS", "APOLLOHOSP.NS",
                "SBILIFE.NS", "HDFCLIFE.NS", "TATACONSUM.NS", "ONGC.NS", "SHREECEM.NS",
                "BPCL.NS", "M&M.NS"
            ]
        
        if self.NIFTY_100_TICKERS is None:
            # Nifty 100 = Nifty 50 + Nifty Next 50
            # Removed delisted: TATAMOTORS.NS, ZOMATO.NS, PAYTM.NS, NYKAA.NS, POLICYBZR.NS
            self.NIFTY_100_TICKERS = self.NIFTY_50_TICKERS + [
                "PIDILITIND.NS", "DABUR.NS", "GODREJCP.NS", "MARICO.NS", "COLPAL.NS",
                "HAVELLS.NS", "BERGEPAINT.NS", "PAGEIND.NS", "BOSCHLTD.NS", "MUTHOOTFIN.NS",
                "CHOLAFIN.NS", "SRF.NS", "NAUKRI.NS", "CARBORUNIV.NS", "DEEPAKNTR.NS",
                "ASTRAL.NS", "CAMS.NS", "CDSL.NS", "MCX.NS", "ANGELONE.NS",
                "ICICIGI.NS", "ICICIPRULI.NS", "HDFCAMC.NS", "AUBANK.NS", "BANDHANBNK.NS",
                "FEDERALBNK.NS", "IDFCFIRSTB.NS", "RBLBANK.NS", "YESBANK.NS", "PNB.NS",
                "CANBK.NS", "UNIONBANK.NS", "BANKBARODA.NS", "INDIANB.NS", "CENTRALBK.NS",
                "BANKINDIA.NS", "TATASTEEL.NS", "HINDALCO.NS", "IOC.NS"
            ]


# Default configuration instance
DEFAULT_CONFIG = Config()