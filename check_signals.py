from config import DEFAULT_CONFIG
from data_loader import create_data_loader
from strategy import create_strategy
from indicators import add_indicators

config = DEFAULT_CONFIG
loader = create_data_loader(config)
end_date = __import__('datetime').datetime.now()
start_date = end_date - __import__('datetime').timedelta(days=3*365)

# Check specific tickers
tickers = ['SBIN.NS', 'ICICIBANK.NS', 'AXISBANK.NS', 'KOTAKBANK.NS', 'TITAN.NS', 'BHARTIARTL.NS', 'NESTLEIND.NS', 'HDFCBANK.NS']
data_dict = loader.fetch_multiple(tickers, start_date, end_date)

strategy = create_strategy(config)

for ticker, df in data_dict.items():
    if len(df) >= 260:
        df = add_indicators(df, config)
        signals = strategy.generate_signals_historical(df, ticker, config.INITIAL_CAPITAL)
        print(f'{ticker}: {len(signals)} total signals')
        for s in signals:
            print(f'  {s.date.strftime("%Y-%m-%d")} {s.signal_type} Entry={s.entry_price:.2f} SL={s.stop_loss:.2f} Target={s.target_price:.2f} vol={s.volume_ratio:.2f}')
    print()