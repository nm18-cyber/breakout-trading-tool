from config import DEFAULT_CONFIG
from data_loader import create_data_loader
from backtester import run_backtest
import pandas as pd

config = DEFAULT_CONFIG
loader = create_data_loader(config)
end_date = __import__('datetime').datetime.now()
start_date = end_date - __import__('datetime').timedelta(days=3*365)

# Use only first 20 tickers for faster testing
test_tickers = config.NIFTY_100_TICKERS[:20]
data_dict = loader.fetch_multiple(test_tickers, start_date, end_date)
result = run_backtest(data_dict, config)

if result.trades:
    df = pd.DataFrame(result.trades)
    print('=== ALL TRADES ===')
    for _, row in df.iterrows():
        print(f"{row['ticker'].replace('.NS','')}: Entry={row['entry_date'].strftime('%Y-%m-%d')} Exit={row['exit_date'].strftime('%Y-%m-%d')} P&L=Rs.{row['pnl']:,.0f} Return={row['return_pct']:.2f}% Reason={row['exit_reason']}")
    
    print('\n=== PER TICKER SUMMARY ===')
    per_ticker = df.groupby('ticker').agg(
        trades=('pnl', 'count'),
        total_pnl=('pnl', 'sum'),
        avg_return=('return_pct', 'mean'),
        wins=('pnl', lambda x: (x > 0).sum()),
        losses=('pnl', lambda x: (x < 0).sum())
    ).sort_values('total_pnl', ascending=False)
    print(per_ticker.to_string())
    
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