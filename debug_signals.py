from config import DEFAULT_CONFIG
from data_loader import create_data_loader
from strategy import create_strategy
from indicators import add_indicators

config = DEFAULT_CONFIG
loader = create_data_loader(config)
end_date = __import__('datetime').datetime.now()
start_date = end_date - __import__('datetime').timedelta(days=3*365)
data_dict = loader.fetch_multiple(config.NIFTY_100_TICKERS[:10], start_date, end_date)

strategy = create_strategy(config)

for ticker, df in data_dict.items():
    if len(df) >= 260:
        df = add_indicators(df, config)
        signals = strategy.generate_signals_historical(df, ticker, config.INITIAL_CAPITAL)
        if signals:
            print(f'{ticker}: {len(signals)} signals')
            for s in signals[:3]:
                print(f'  {s.date.strftime("%Y-%m-%d")} {s.signal_type} vol={s.volume_ratio:.2f}')
        else:
            print(f'{ticker}: 0 signals')
    else:
        print(f'{ticker}: insufficient data ({len(df)} rows)')