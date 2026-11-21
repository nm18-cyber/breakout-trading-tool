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
else:
    print('No trades')