"""
Vectorized backtesting engine for the breakout strategy.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np
from config import DEFAULT_CONFIG, Config
from strategy import BreakoutStrategy, Signal, Position, create_strategy


@dataclass
class BacktestResult:
    """Container for backtest results."""
    total_return: float
    annualized_return: float
    max_drawdown: float
    sharpe_ratio: float
    win_rate: float
    profit_factor: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    avg_win: float
    avg_loss: float
    equity_curve: pd.Series
    trades: List[Dict]
    metrics: Dict


class VectorizedBacktester:
    """Vectorized backtester for breakout strategy."""
    
    def __init__(self, config: Config = DEFAULT_CONFIG):
        self.config = config
        self.strategy = create_strategy(config)
    
    def run_backtest(
        self,
        data_dict: Dict[str, pd.DataFrame],
        capital: float = None
    ) -> BacktestResult:
        """
        Run vectorized backtest across all tickers.
        
        Args:
            data_dict: Dictionary of ticker -> OHLCV DataFrame
            capital: Initial capital
            
        Returns:
            BacktestResult with performance metrics
        """
        if capital is None:
            capital = self.config.INITIAL_CAPITAL
        
        all_trades = []
        daily_returns = []
        equity = capital
        equity_curve = []
        
        # Get all unique dates across all tickers
        all_dates = set()
        for df in data_dict.values():
            all_dates.update(df.index)
        all_dates = sorted(all_dates)
        
        # Track open positions
        open_positions: Dict[str, Position] = {}
        
        for date in all_dates:
            day_trades = []
            
            # Check each ticker for exit and new entries
            for ticker, df in data_dict.items():
                # Get data up to current date
                mask = df.index <= date
                if not mask.any():
                    continue
                hist_df = df[mask]
                
                if len(hist_df) < 260:
                    continue
                
                # Add indicators
                hist_df = self._add_indicators_cached(hist_df)
                
                # Check for exit on existing positions
                if ticker in open_positions:
                    pos = open_positions[ticker]
                    current_bar = hist_df.iloc[-1]
                    
                    # Update position
                    pos.update_price(current_bar['close'])
                    
                    # Check stop loss
                    if pos.check_stop_loss(current_bar['low']):
                        # Exit at stop loss
                        pnl = (pos.stop_loss - pos.entry_price) * pos.shares
                        equity += pnl
                        day_trades.append({
                            'ticker': ticker,
                            'entry_date': pos.entry_date,
                            'exit_date': date,
                            'entry_price': pos.entry_price,
                            'exit_price': pos.stop_loss,
                            'shares': pos.shares,
                            'pnl': pnl,
                            'return_pct': pnl / (pos.entry_price * pos.shares) * 100,
                            'exit_reason': 'stop_loss'
                        })
                        del open_positions[ticker]
                        continue
                    
                    # Check target
                    if pos.check_target(current_bar['high']):
                        # Exit at target
                        pnl = (pos.target_price - pos.entry_price) * pos.shares
                        equity += pnl
                        day_trades.append({
                            'ticker': ticker,
                            'entry_date': pos.entry_date,
                            'exit_date': date,
                            'entry_price': pos.entry_price,
                            'exit_price': pos.target_price,
                            'shares': pos.shares,
                            'pnl': pnl,
                            'return_pct': pnl / (pos.entry_price * pos.shares) * 100,
                            'exit_reason': 'target'
                        })
                        del open_positions[ticker]
                        continue
                    
                    # Check for time-based exit (end of data or max hold)
                    # For simplicity, we'll hold until stop loss, target, or end
                    # In production, add max holding period
                
                # Check for new entry signal
                # Only if no open position for this ticker
                if ticker not in open_positions:
                    signal = self.strategy.check_entry_signal(hist_df, ticker, capital)
                    if signal:
                        # Open new position
                        pos = Position(
                            signal=signal,
                            entry_date=date,
                            shares=signal.position_size,
                            entry_price=signal.entry_price,
                            stop_loss=signal.stop_loss,
                            target_price=signal.target_price
                        )
                        open_positions[ticker] = pos
            
            # Calculate daily equity
            unrealized_pnl = sum(p.unrealized_pnl for p in open_positions.values())
            equity = capital + sum(t['pnl'] for t in all_trades) + sum(t['pnl'] for t in day_trades) + unrealized_pnl
            equity_curve.append(equity)
            all_trades.extend(day_trades)
        
        # Close any remaining positions at last price
        for ticker, pos in open_positions.items():
            if ticker in data_dict:
                last_price = data_dict[ticker].iloc[-1]['close']
                pnl = (last_price - pos.entry_price) * pos.shares
                all_trades.append({
                    'ticker': ticker,
                    'entry_date': pos.entry_date,
                    'exit_date': data_dict[ticker].index[-1],
                    'entry_price': pos.entry_price,
                    'exit_price': last_price,
                    'shares': pos.shares,
                    'pnl': pnl,
                    'return_pct': pnl / (pos.entry_price * pos.shares) * 100,
                    'exit_reason': 'end_of_data'
                })
        
        # Ensure equity_curve matches dates length
        # If we have fewer equity points than dates, pad with last value
        while len(equity_curve) < len(all_dates):
            equity_curve.append(equity_curve[-1] if equity_curve else capital)
        
        # Calculate metrics
        return self._calculate_metrics(all_trades, equity_curve, capital, all_dates)
    
    def _add_indicators_cached(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add indicators with caching to avoid recalculation."""
        from indicators import add_indicators
        return add_indicators(df, self.config)
    
    def _calculate_metrics(
        self,
        trades: List[Dict],
        equity_curve: List[float],
        initial_capital: float,
        dates: List[pd.Timestamp]
    ) -> BacktestResult:
        """Calculate performance metrics from trades and equity curve."""
        if not trades:
            # Create equity series with initial capital for each date
            equity_series = pd.Series([initial_capital] * len(dates), index=dates)
            return BacktestResult(
                total_return=0.0,
                annualized_return=0.0,
                max_drawdown=0.0,
                sharpe_ratio=0.0,
                win_rate=0.0,
                profit_factor=0.0,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                avg_win=0.0,
                avg_loss=0.0,
                equity_curve=equity_series,
                trades=trades,
                metrics={}
            )
        
        trades_df = pd.DataFrame(trades)
        
        # Basic metrics
        total_trades = len(trades_df)
        winning_trades = len(trades_df[trades_df['pnl'] > 0])
        losing_trades = len(trades_df[trades_df['pnl'] < 0])
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        avg_win = trades_df[trades_df['pnl'] > 0]['pnl'].mean() if winning_trades > 0 else 0
        avg_loss = trades_df[trades_df['pnl'] < 0]['pnl'].mean() if losing_trades > 0 else 0
        
        gross_profit = trades_df[trades_df['pnl'] > 0]['pnl'].sum()
        gross_loss = abs(trades_df[trades_df['pnl'] < 0]['pnl'].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # Equity curve metrics - align with dates
        equity_series = pd.Series(equity_curve, index=dates[:len(equity_curve)])
        total_return = (equity_series.iloc[-1] - initial_capital) / initial_capital * 100
        
        # Annualized return
        years = len(dates) / 252
        annualized_return = (1 + total_return / 100) ** (1 / years) - 1 if years > 0 else 0
        annualized_return *= 100
        
        # Max drawdown
        rolling_max = equity_series.expanding().max()
        drawdown = (equity_series - rolling_max) / rolling_max * 100
        max_drawdown = drawdown.min()
        
        # Sharpe ratio (assuming risk-free rate = 0 for simplicity)
        daily_returns = equity_series.pct_change().dropna()
        if len(daily_returns) > 1 and daily_returns.std() > 0:
            sharpe_ratio = daily_returns.mean() / daily_returns.std() * np.sqrt(252)
        else:
            sharpe_ratio = 0.0
        
        return BacktestResult(
            total_return=total_return,
            annualized_return=annualized_return,
            max_drawdown=max_drawdown,
            sharpe_ratio=sharpe_ratio,
            win_rate=win_rate * 100,
            profit_factor=profit_factor,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            avg_win=avg_win,
            avg_loss=avg_loss,
            equity_curve=equity_series,
            trades=trades,
            metrics={
                'gross_profit': gross_profit,
                'gross_loss': gross_loss,
                'avg_trade': trades_df['pnl'].mean(),
                'max_consecutive_wins': self._max_consecutive(trades_df['pnl'] > 0),
                'max_consecutive_losses': self._max_consecutive(trades_df['pnl'] < 0),
            }
        )
    
    def _max_consecutive(self, series: pd.Series) -> int:
        """Calculate maximum consecutive True values."""
        if series.empty:
            return 0
        groups = (series != series.shift()).cumsum()
        return series.groupby(groups).sum().max()


def run_backtest(
    data_dict: Dict[str, pd.DataFrame],
    config: Config = DEFAULT_CONFIG
) -> BacktestResult:
    """Convenience function to run backtest."""
    backtester = VectorizedBacktester(config)
    return backtester.run_backtest(data_dict, config.INITIAL_CAPITAL)