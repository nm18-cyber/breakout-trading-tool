# Breakout Trading & Screening Tool

A modular, production-ready Python application for systematic breakout trading and screening of Nifty 100 stocks.

## Features

- **Screening Mode**: Real-time scanning of Nifty 100 stocks for breakout entry signals
- **Backtest Mode**: Vectorized 3-year historical backtest with comprehensive metrics
- **Risk Management**: 1% capital risk per trade, ATR-based stop losses
- **Local Caching**: Parquet-based caching to avoid API rate limits
- **Modular Architecture**: Clean separation of concerns for easy maintenance

## Strategy Logic

### Entry Signals (Buy Zone)
A signal is triggered when **ALL** conditions are met:
1. **Price Breakout**: Daily Close breaks above **ANY** of:
   - 20-day Rolling High
   - 52-week (252-day) Rolling High
   - Crosses above 200-day SMA
2. **Volume Confirmation**: Daily Volume ≥ 1.5x 20-day Average Volume

### Risk Management
- **Stop Loss**: Entry Price - (2 × 14-day ATR)
- **Position Size**: Calculated to risk exactly 1% of total capital per trade

## Installation

```bash
# Clone or navigate to the project directory
cd breakout_trading_tool

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Screen Mode (Live Scanning)
```bash
# Scan Nifty 100 with default capital (₹10L)
python main.py --mode screen

# Scan with custom capital
python main.py --mode screen --capital 500000

# Scan specific tickers
python main.py --mode screen --tickers "RELIANCE.NS,TCS.NS,INFY.NS"
```

### Backtest Mode (Historical Analysis)
```bash
# Run 3-year backtest on Nifty 100
python main.py --mode backtest

# Run 5-year backtest
python main.py --mode backtest --years 5

# Backtest with custom capital
python main.py --mode backtest --capital 2500000
```

## Output Examples

### Screen Mode Output
```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                                    Summary                                         ┃
┃  Total Signals: 3                                                                  ┃
┃  Total Capital at Risk: ₹1,25,000.00 (1.25% of ₹10,00,000)                         ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

### Backtest Mode Output
```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                         Backtest Performance Metrics                                ┃
┃ ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━┓                          ┃
┃ ┃ Metric                      ┃ Value                   ┃                          ┃
┃ ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━┩                          ┃
┃ │ Total Return                │ 42.35%                  │                          ┃
┃ │ Annualized Return           │ 12.85%                  │                          ┃
┃ │ Max Drawdown                │ -18.42%                 │                          ┃
┃ │ Sharpe Ratio                │ 1.23                    │                          ┃
┃ │ Win Rate                    │ 58.33%                  │                          ┃
┃ │ Profit Factor               │ 1.85                    │                          ┃
┃ │ Total Trades                │ 147                     │                          ┃
┃ └─────────────────────────────┴─────────────────────────┘                          ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
```

## Project Structure

```
breakout_trading_tool/
├── config.py          # Configuration parameters
├── data_loader.py     # Data fetching with caching
├── indicators.py      # Technical indicator calculations
├── strategy.py        # Core breakout logic
├── backtester.py      # Vectorized backtesting engine
├── main.py            # CLI entry point
├── requirements.txt   # Python dependencies
└── README.md          # This file
```

## Configuration

Key parameters in `config.py`:
- `SMA_LONG_PERIOD`: 200-day SMA period
- `VOLUME_AVG_PERIOD`: 20-day average volume period
- `ATR_PERIOD`: 14-day ATR period
- `BREAKOUT_SHORT_PERIOD`: 20-day high lookback
- `BREAKOUT_LONG_PERIOD`: 252-day (52-week) high lookback
- `VOLUME_MULTIPLIER`: 1.5x volume threshold
- `ATR_MULTIPLIER`: 2.0x ATR for stop loss
- `RISK_PER_TRADE_PCT`: 1% capital risk per trade

## Broker API Integration

The `strategy.py` includes placeholder hooks for broker integration:

```python
strategy = create_strategy()

# Set custom order executor (e.g., Zerodha Kite Connect)
def my_order_executor(signal: Signal):
    # Place order via broker API
    pass

strategy.set_order_executor(my_order_executor)

# Set position manager for live monitoring
def my_position_manager(positions: List[Position]):
    # Monitor and manage live positions
    pass

strategy.set_position_manager(my_position_manager)
```

## Data Caching

- Data is cached locally in `data_cache/` directory as Parquet files
- Cache is valid for 1 day by default
- Use `--no-cache` flag to force fresh data fetch

## Requirements

- Python 3.10+
- yfinance for data
- pandas, numpy for computation
- pandas-ta for technical indicators
- rich for terminal output

## Disclaimer

This tool is for educational and research purposes only. Not financial advice. Always do your own due diligence before trading. Past performance does not guarantee future results.