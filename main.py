"""
Main CLI entry point for the Breakout Trading Tool.
"""
import argparse
import sys
from datetime import datetime
from typing import Dict
import pandas as pd
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, TextColumn

from config import DEFAULT_CONFIG, Config
from data_loader import create_data_loader, DataLoader
from strategy import create_strategy, BreakoutStrategy, Signal
from backtester import run_backtest, BacktestResult
from indicators import add_indicators

console = Console()


def print_banner():
    """Print application banner."""
    console.print(Panel.fit(
        "[bold cyan]Breakout Trading & Screening Tool[/bold cyan]\n"
        "[dim]Nifty 100 Systematic Breakout Strategy[/dim]",
        border_style="cyan"
    ))


def run_screen_mode(config: Config = DEFAULT_CONFIG) -> None:
    """Run screening mode - scan current market for breakout signals."""
    console.print("[bold]Running Screen Mode...[/bold]")
    
    loader = create_data_loader(config)
    strategy = create_strategy(config)
    
    console.print("Fetching latest data for Nifty 100...")
    
    # Get recent data for all tickers (last 90 days for indicators)
    data_dict = loader.get_latest_data(config.NIFTY_100_TICKERS)
    
    console.print("Calculating indicators and scanning...")
    
    # Add indicators to each ticker's data
    for ticker, df in data_dict.items():
        if len(df) >= 260:
            data_dict[ticker] = add_indicators(df, config)
    
    # Scan for signals
    signals = strategy.scan_universe(data_dict, config.INITIAL_CAPITAL)
    
    console.print("Screening complete!")
    
    # Display results
    if not signals:
        console.print("[yellow]No breakout signals found in current market data.[/yellow]")
        return
    
    # Create results table
    table = Table(title=f"Breakout Signals - {datetime.now().strftime('%Y-%m-%d')}", 
                  show_header=True, header_style="bold magenta")
    
    table.add_column("Ticker", style="cyan", no_wrap=True)
    table.add_column("Signal Type", style="green")
    table.add_column("Entry Price", justify="right", style="white")
    table.add_column("Stop Loss", justify="right", style="red")
    table.add_column("Position Size", justify="right", style="yellow")
    table.add_column("Risk/Share", justify="right", style="white")
    table.add_column("Volume Ratio", justify="right", style="blue")
    table.add_column("ATR (14)", justify="right", style="white")
    
    total_risk = 0
    for signal in signals:
        risk_per_share = signal.risk_per_share
        total_position_risk = risk_per_share * signal.position_size
        total_risk += total_position_risk
        
        table.add_row(
            signal.ticker.replace(".NS", ""),
            signal.signal_type,
            f"Rs.{signal.entry_price:,.2f}",
            f"Rs.{signal.stop_loss:,.2f}",
            f"{signal.position_size:,}",
            f"Rs.{risk_per_share:,.2f}",
            f"{signal.volume_ratio:.2f}x",
            f"Rs.{signal.atr:,.2f}"
        )
    
    console.print(table)
    
    # Summary
    console.print(Panel(
        f"[bold]Total Signals:[/bold] {len(signals)}\n"
        f"[bold]Total Capital at Risk:[/bold] Rs.{total_risk:,.2f} "
        f"({total_risk/config.INITIAL_CAPITAL*100:.2f}% of Rs.{config.INITIAL_CAPITAL:,.0f})",
        title="Summary",
        border_style="green"
    ))


def run_backtest_mode(config: Config = DEFAULT_CONFIG) -> None:
    """Run backtest mode - historical performance analysis."""
    console.print("[bold]Running Backtest Mode...[/bold]")
    
    loader = create_data_loader(config)
    
    console.print("Fetching historical data...")
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - pd.Timedelta(days=config.BACKTEST_YEARS * 365)
    
    # Fetch data for all tickers
    data_dict = loader.fetch_multiple(
        config.NIFTY_100_TICKERS,
        start_date=start_date,
        end_date=end_date,
        use_cache=True
    )
    
    console.print(f"Running backtest on {len(data_dict)} tickers...")
    
    # Run backtest
    result = run_backtest(data_dict, config)
    
    console.print("Backtest complete!")
    
    # Display results
    print_backtest_results(result)


def print_backtest_results(result: BacktestResult) -> None:
    """Print formatted backtest results."""
    # Main metrics table
    metrics_table = Table(title="Backtest Performance Metrics", 
                          show_header=True, header_style="bold magenta")
    metrics_table.add_column("Metric", style="cyan")
    metrics_table.add_column("Value", justify="right", style="white")
    
    metrics_table.add_row("Total Return", f"{result.total_return:.2f}%")
    metrics_table.add_row("Annualized Return", f"{result.annualized_return:.2f}%")
    metrics_table.add_row("Max Drawdown", f"{result.max_drawdown:.2f}%")
    metrics_table.add_row("Sharpe Ratio", f"{result.sharpe_ratio:.2f}")
    metrics_table.add_row("Win Rate", f"{result.win_rate:.2f}%")
    metrics_table.add_row("Profit Factor", f"{result.profit_factor:.2f}")
    metrics_table.add_row("Total Trades", str(result.total_trades))
    metrics_table.add_row("Winning Trades", str(result.winning_trades))
    metrics_table.add_row("Losing Trades", str(result.losing_trades))
    metrics_table.add_row("Avg Win", f"Rs.{result.avg_win:,.2f}")
    metrics_table.add_row("Avg Loss", f"Rs.{result.avg_loss:,.2f}")
    
    console.print(metrics_table)
    
    # Additional metrics
    if result.metrics:
        extra_table = Table(title="Additional Metrics", show_header=True, header_style="bold magenta")
        extra_table.add_column("Metric", style="cyan")
        extra_table.add_column("Value", justify="right", style="white")
        
        extra_table.add_row("Gross Profit", f"Rs.{result.metrics.get('gross_profit', 0):,.2f}")
        extra_table.add_row("Gross Loss", f"Rs.{result.metrics.get('gross_loss', 0):,.2f}")
        extra_table.add_row("Avg Trade P&L", f"Rs.{result.metrics.get('avg_trade', 0):,.2f}")
        extra_table.add_row("Max Consecutive Wins", str(result.metrics.get('max_consecutive_wins', 0)))
        extra_table.add_row("Max Consecutive Losses", str(result.metrics.get('max_consecutive_losses', 0)))
        
        console.print(extra_table)
    
    # Trade breakdown by exit reason
    if result.trades:
        trades_df = pd.DataFrame(result.trades)
        exit_reasons = trades_df['exit_reason'].value_counts()
        
        reason_table = Table(title="Exit Reasons", show_header=True, header_style="bold magenta")
        reason_table.add_column("Exit Reason", style="cyan")
        reason_table.add_column("Count", justify="right", style="white")
        reason_table.add_column("Avg P&L", justify="right", style="white")
        
        for reason, count in exit_reasons.items():
            avg_pnl = trades_df[trades_df['exit_reason'] == reason]['pnl'].mean()
            reason_table.add_row(reason, str(count), f"Rs.{avg_pnl:,.2f}")
        
        console.print(reason_table)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Breakout Trading & Screening Tool for Nifty 100",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --mode screen          # Scan current market for breakout signals
  python main.py --mode backtest        # Run 3-year historical backtest
  python main.py --mode screen --capital 500000  # Screen with custom capital
        """
    )
    
    parser.add_argument(
        '--mode',
        choices=['screen', 'backtest'],
        required=True,
        help='Operation mode: screen (live scan) or backtest (historical)'
    )
    
    parser.add_argument(
        '--capital',
        type=float,
        default=DEFAULT_CONFIG.INITIAL_CAPITAL,
        help=f'Capital for position sizing (default: {DEFAULT_CONFIG.INITIAL_CAPITAL:,.0f})'
    )
    
    parser.add_argument(
        '--tickers',
        type=str,
        help='Comma-separated list of tickers (default: Nifty 100)'
    )
    
    parser.add_argument(
        '--years',
        type=int,
        default=DEFAULT_CONFIG.BACKTEST_YEARS,
        help=f'Years of historical data for backtest (default: {DEFAULT_CONFIG.BACKTEST_YEARS})'
    )
    
    parser.add_argument(
        '--no-cache',
        action='store_true',
        help='Disable data caching'
    )
    
    args = parser.parse_args()
    
    # Create config with overrides
    config = Config(
        BACKTEST_YEARS=args.years,
        INITIAL_CAPITAL=args.capital,
        NIFTY_100_TICKERS=args.tickers.split(',') if args.tickers else DEFAULT_CONFIG.NIFTY_100_TICKERS
    )
    
    print_banner()
    
    try:
        if args.mode == 'screen':
            run_screen_mode(config)
        elif args.mode == 'backtest':
            run_backtest_mode(config)
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user.[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()