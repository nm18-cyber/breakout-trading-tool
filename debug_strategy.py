"""Debug script to understand why Opening Level Strategy generates zero signals"""
import pandas as pd
import numpy as np
from data_loader import DataLoader
from opening_level_strategy import OpeningLevelStrategy, TradeDirection
from config import DEFAULT_CONFIG
from indicators import add_indicators
from datetime import datetime, timedelta

config = DEFAULT_CONFIG
dl = DataLoader(config)

# Test with RELIANCE at 15m
ticker = "RELIANCE.NS"
interval = "15m"
end_date = datetime.now()
start_date = end_date - timedelta(days=30)

df = dl.fetch_data(ticker, start_date, end_date, interval=interval)
if df.empty:
    print("No data fetched")
    exit(1)

print(f"Fetched {len(df)} bars for {ticker} [{interval}]")
print(f"Index tz: {df.index.tz}")
print(f"Time range: {df.index[0]} to {df.index[-1]}")
print(f"Price range: {df['low'].min():.2f} - {df['high'].max():.2f}")
print()

df = add_indicators(df, config)
df.attrs['ticker'] = ticker

# Check open==low / open==high
tol = 0.0001
df['open_eq_low'] = abs(df['open'] - df['low']) / df['open'] < tol
df['open_eq_high'] = abs(df['open'] - df['high']) / df['open'] < tol

print(f"Open==Low bars: {df['open_eq_low'].sum()}")
print(f"Open==High bars: {df['open_eq_high'].sum()}")
print()

# Show some examples
print("Sample Open==Low bars:")
for idx, row in df[df['open_eq_low']].head(5).iterrows():
    print(f"  {idx}: O={row['open']:.2f} H={row['high']:.2f} L={row['low']:.2f} C={row['close']:.2f} Vol={row['volume']:.0f} ATR={row.get('14_atr', 0):.2f} VolRatio={row.get('vol_ratio', 0):.2f}")
print()

print("Sample Open==High bars:")
for idx, row in df[df['open_eq_high']].head(5).iterrows():
    print(f"  {idx}: O={row['open']:.2f} H={row['high']:.2f} L={row['low']:.2f} C={row['close']:.2f} Vol={row['volume']:.0f} ATR={row.get('14_atr', 0):.2f} VolRatio={row.get('vol_ratio', 0):.2f}")
print()

# Check ATR
print(f"ATR stats: min={df['14_atr'].min():.4f}, max={df['14_atr'].max():.4f}, mean={df['14_atr'].mean():.4f}, NaN count={df['14_atr'].isna().sum()}")
print(f"Vol ratio stats: min={df['vol_ratio'].min():.4f}, max={df['vol_ratio'].max():.4f}, mean={df['vol_ratio'].mean():.4f}")
print()

# Now test the strategy
strategy = OpeningLevelStrategy(config)
signals = strategy.scan(df, config.INITIAL_CAPITAL)
print(f"Total signals: {len(signals)}")
for s in signals[:10]:
    print(f"  {s.entry_time}: {s.direction.value} @ {s.entry_price:.2f} SL={s.stop_loss:.2f} TP={s.target_price:.2f} Level={s.level_price:.2f} ({s.level_type})")
