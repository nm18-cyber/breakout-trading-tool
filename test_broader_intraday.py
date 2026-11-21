"""Broader intraday backtest with all Nifty 50 tickers"""
from data_loader import DataLoader
from opening_level_strategy import create_opening_level_strategy
from intraday_backtester import IntradayBacktester
from config import DEFAULT_CONFIG, Config
from indicators import add_indicators
from datetime import datetime, timedelta

config = DEFAULT_CONFIG
dl = DataLoader(config)

# Use all Nifty 50 tickers
tickers = config.NIFTY_50_TICKERS
print(f"Testing {len(tickers)} tickers")

# Test at 15m for 30 days
interval = "15m"
end_date = datetime.now()
start_date = end_date - timedelta(days=30)

print(f"\nFetching {interval} data for {len(tickers)} tickers ({start_date.date()} to {end_date.date()})...")
data_dict = dl.fetch_multiple(tickers, start_date, end_date, interval=interval)

print(f"Got data for {len(data_dict)} tickers")
for t, df in sorted(data_dict.items()):
    print(f"  {t}: {len(df)} bars")

# Add indicators
for ticker, df in data_dict.items():
    data_dict[ticker] = add_indicators(df, config)

# Run backtest
print(f"\nRunning backtest at {interval}...")
bt = IntradayBacktester(config)
result = bt.run_backtest(data_dict, config.INITIAL_CAPITAL)

print(f"\n=== {interval} RESULTS ({len(tickers)} tickers, 30 days) ===")
print(f"Total Return: {result.total_return:.2f}%")
print(f"Annualized: {result.annualized_return:.2f}%")
print(f"Max DD: {result.max_drawdown:.2f}%")
print(f"Sharpe: {result.sharpe_ratio:.2f}")
print(f"Win Rate: {result.win_rate:.2f}%")
print(f"Profit Factor: {result.profit_factor:.2f}")
print(f"Total Trades: {result.total_trades}")
print(f"  Wins: {result.winning_trades}, Losses: {result.losing_trades}")
print("Avg Win: {:,.0f}, Avg Loss: {:,.0f}".format(result.avg_win, result.avg_loss))
print(f"Avg R-Multiple: {result.avg_r_multiple:.2f}")
print(f"\nExit Reasons: {result.metrics.get('by_exit_reason', {})}")
print(f"Level Types: {result.metrics.get('by_level_type', {})}")
print(f"Directions: {result.metrics.get('by_direction', {})}")

# Per-ticker
if result.trades:
    import pandas as pd
    trades_df = pd.DataFrame(result.trades)
    ticker_summary = trades_df.groupby('ticker').agg(
        trades=('pnl', 'count'),
        total_pnl=('pnl', 'sum'),
        win_rate=('pnl', lambda x: (x > 0).mean() * 100)
    ).round(2)
    ticker_summary['ticker'] = ticker_summary.index.str.replace('.NS', '')
    print("\nPer-Ticker Summary (top 10 by P&L):")
    print(ticker_summary.sort_values('total_pnl', ascending=False).head(10).to_string(index=False))
