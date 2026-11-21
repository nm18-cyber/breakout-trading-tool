"""
Test script for Intraday Opening Level Breakout + Retest Strategy
"""
import pandas as pd
import sys
sys.path.insert(0, r'C:\breakout_trading_tool')

from config import DEFAULT_CONFIG, Config
from data_loader import create_data_loader
from intraday_backtester import run_intraday_backtest, IntradayBacktester


def test_timeframe(interval: str, days: int = 60, tickers: list = None):
    """Test strategy on specific timeframe"""
    
    if tickers is None:
        tickers = DEFAULT_CONFIG.NIFTY_50_TICKERS[:10]  # Start with 10
    
    config = Config(
        DATA_INTERVAL=interval,
        BACKTEST_YEARS=0,  # Not used for intraday
        INITIAL_CAPITAL=10_00_000
    )
    
    loader = create_data_loader(config)
    end_date = pd.Timestamp.now()
    start_date = end_date - pd.Timedelta(days=days)
    
    print(f"\n{'='*60}")
    print(f"Testing {interval} timeframe on {len(tickers)} tickers ({days} days)")
    print(f"{'='*60}")
    
    # Fetch data
    print("Fetching data...")
    data_dict = loader.fetch_multiple(tickers, start_date, end_date)
    
    if not data_dict:
        print("No data fetched!")
        return
    
    print(f"Got data for {len(data_dict)} tickers")
    for t, df in data_dict.items():
        print(f"  {t}: {len(df)} bars")
    
    # Run backtest
    print("\nRunning backtest...")
    try:
        result = run_intraday_backtest(data_dict, config)
        
        print(f"\n=== RESULTS for {interval} ===")
        print(f"Total Return: {result.total_return:.2f}%")
        print(f"Annualized: {result.annualized_return:.2f}%")
        print(f"Max DD: {result.max_drawdown:.2f}%")
        print(f"Sharpe: {result.sharpe_ratio:.2f}")
        print(f"Win Rate: {result.win_rate:.2f}%")
        print(f"Profit Factor: {result.profit_factor:.2f}")
        print(f"Avg R-Multiple: {result.avg_r_multiple:.2f}")
        print(f"Total Trades: {result.total_trades}")
        print(f"  Wins: {result.winning_trades}, Losses: {result.losing_trades}")
        print(f"Avg Win: Rs.{result.avg_win:,.0f}")
        print(f"Avg Loss: Rs.{result.avg_loss:,.0f}")
        
        # Exit reason breakdown
        if result.metrics.get('by_exit_reason'):
            print(f"\nExit Reasons:")
            for reason, count in result.metrics['by_exit_reason'].items():
                print(f"  {reason}: {count}")
        
        # Level type breakdown
        if result.metrics.get('by_level_type'):
            print(f"\nLevel Types:")
            for ltype, count in result.metrics['by_level_type'].items():
                print(f"  {ltype}: {count}")
        
        # Direction breakdown
        if result.metrics.get('by_direction'):
            print(f"\nDirections:")
            for direction, count in result.metrics['by_direction'].items():
                print(f"  {direction}: {count}")
        
        # Per ticker summary
        if result.trades:
            df = pd.DataFrame(result.trades)
            print(f"\nPer Ticker Summary:")
            per_ticker = df.groupby('ticker').agg(
                trades=('pnl', 'count'),
                total_pnl=('pnl', 'sum'),
                win_rate=('pnl', lambda x: (x > 0).sum() / len(x) * 100)
            ).sort_values('total_pnl', ascending=False)
            print(per_ticker.to_string())
        
        return result
        
    except Exception as e:
        print(f"Backtest failed: {e}")
        import traceback
        traceback.print_exc()
        return None


def compare_timeframes():
    """Compare strategy across multiple timeframes"""
    intervals = ['5m', '15m', '30m', '1h']
    
    print("\n" + "="*70)
    print("TIMEFRAME COMPARISON")
    print("="*70)
    
    results = {}
    for interval in intervals:
        try:
            result = test_timeframe(interval, days=30, tickers=DEFAULT_CONFIG.NIFTY_50_TICKERS[:5])
            if result:
                results[interval] = {
                    'return': result.total_return,
                    'sharpe': result.sharpe_ratio,
                    'win_rate': result.win_rate,
                    'trades': result.total_trades,
                    'profit_factor': result.profit_factor,
                    'max_dd': result.max_drawdown,
                    'avg_r': result.avg_r_multiple
                }
        except Exception as e:
            print(f"{interval} failed: {e}")
    
    print("\n" + "="*70)
    print("SUMMARY COMPARISON")
    print("="*70)
    print(f"{'Interval':<10} {'Return%':<10} {'Sharpe':<8} {'Win%':<8} {'Trades':<8} {'PF':<8} {'MaxDD%':<10} {'AvgR':<8}")
    print("-"*70)
    for interval, r in results.items():
        print(f"{interval:<10} {r['return']:<10.2f} {r['sharpe']:<8.2f} {r['win_rate']:<8.2f} {r['trades']:<8} {r['profit_factor']:<8.2f} {r['max_dd']:<10.2f} {r['avg_r']:<8.2f}")


if __name__ == '__main__':
    # Test single timeframe first
    # test_timeframe('5m', days=30, tickers=['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'ICICIBANK.NS'])
    
    # Compare all timeframes
    compare_timeframes()