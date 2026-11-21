from config import DEFAULT_CONFIG
from data_loader import create_data_loader
from backtester import run_backtest
import pandas as pd

config = DEFAULT_CONFIG
loader = create_data_loader(config)
end_date = __import__('datetime').datetime.now()
start_date = end_date - __import__('datetime').timedelta(days=3*365)
data_dict = loader.fetch_multiple(config.NIFTY_100_TICKERS, start_date, end_date)
result = run_backtest(data_dict, config)

if result.trades:
    df = pd.DataFrame(result.trades)
    print('=== PER TICKER SUMMARY (Top 20) ===')
    per_ticker = df.groupby('ticker').agg(
        trades=('pnl', 'count'),
        total_pnl=('pnl', 'sum'),
        avg_return=('return_pct', 'mean'),
        wins=('pnl', lambda x: (x > 0).sum()),
        losses=('pnl', lambda x: (x < 0).sum()),
        win_rate=('pnl', lambda x: (x > 0).sum() / len(x) * 100)
    ).sort_values('total_pnl', ascending=False)
    print(per_ticker.head(20).to_string())
    
    print('\n=== PER TICKER SUMMARY (Bottom 10) ===')
    print(per_ticker.tail(10).to_string())
    
    print(f'\n=== OVERALL ===')
    print(f'Total Return: {result.total_return:.2f}%')
    print(f'Annualized: {result.annualized_return:.2f}%')
    print(f'Max DD: {result.max_drawdown:.2f}%')
    print(f'Sharpe: {result.sharpe_ratio:.2f}')
    print(f'Win Rate: {result.win_rate:.2f}%')
    print(f'Profit Factor: {result.profit_factor:.2f}')
    print(f'Total Trades: {result.total_trades}')
else:
    print('No trades')