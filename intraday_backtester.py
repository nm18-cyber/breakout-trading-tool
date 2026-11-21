"""
Intraday Backtester for Opening Level Breakout + Retest Strategy
Optimized: processes each ticker independently for speed
"""
from dataclasses import dataclass
from typing import Dict, List, Optional
import pandas as pd
import numpy as np
from config import DEFAULT_CONFIG, Config
from opening_level_strategy import OpeningLevelStrategy, RetestSignal, TradeDirection, create_opening_level_strategy


@dataclass
class IntradayBacktestResult:
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
    avg_r_multiple: float
    equity_curve: pd.Series
    trades: List[Dict]
    metrics: Dict


class IntradayBacktester:
    """Event-driven backtester for intraday opening level strategy"""
    
    def __init__(self, config: Config = DEFAULT_CONFIG):
        self.config = config
        self.session_start = getattr(config, 'SESSION_START', '09:15')
        self.session_end = getattr(config, 'SESSION_END', '15:30')
        self.square_off_time = getattr(config, 'SQUARE_OFF_TIME', '15:15')
        self.max_holding_bars = getattr(config, 'MAX_HOLDING_BARS', 100)
    
    def _is_session_time(self, timestamp: pd.Timestamp) -> bool:
        time = timestamp.time()
        start = pd.Timestamp(self.session_start).time()
        end = pd.Timestamp(self.session_end).time()
        return start <= time <= end
    
    def _is_square_off_time(self, timestamp: pd.Timestamp) -> bool:
        time = timestamp.time()
        sq_time = pd.Timestamp(self.square_off_time).time()
        return time >= sq_time
    
    def run_backtest(
        self,
        data_dict: Dict[str, pd.DataFrame],
        capital: float = None
    ) -> IntradayBacktestResult:
        """Run intraday backtest across all tickers - processes each independently"""
        if capital is None:
            capital = self.config.INITIAL_CAPITAL
        
        all_trades = []
        equity = capital
        
        # Process each ticker independently
        for ticker, df_raw in data_dict.items():
            df = df_raw.copy()
            df.attrs['ticker'] = ticker
            
            # Add indicators
            from indicators import add_indicators
            df = add_indicators(df, self.config)
            
            # Filter to session hours only
            df = df[df.index.map(self._is_session_time)]
            
            if len(df) < 100:
                continue
            
            strategy = create_opening_level_strategy(self.config)
            
            # Track open position for this ticker
            position = None
            
            for i in range(len(df)):
                current_bar = df.iloc[i]
                ts = current_bar.name
                
                # Check existing position for exit
                if position is not None:
                    position['bars_held'] += 1
                    
                    if position['direction'] == TradeDirection.LONG:
                        position['unrealized_pnl'] = (current_bar['close'] - position['entry_price']) * position['quantity']
                        
                        # Stop loss
                        if current_bar['low'] <= position['stop_loss']:
                            pnl = (position['stop_loss'] - position['entry_price']) * position['quantity']
                            equity += pnl
                            all_trades.append(self._make_trade_record(position, ts, position['stop_loss'], pnl, 'stop_loss'))
                            position = None
                            continue
                        
                        # Target
                        if current_bar['high'] >= position['target_price']:
                            pnl = (position['target_price'] - position['entry_price']) * position['quantity']
                            equity += pnl
                            all_trades.append(self._make_trade_record(position, ts, position['target_price'], pnl, 'target'))
                            position = None
                            continue
                    
                    else:  # SHORT
                        position['unrealized_pnl'] = (position['entry_price'] - current_bar['close']) * position['quantity']
                        
                        # Stop loss
                        if current_bar['high'] >= position['stop_loss']:
                            pnl = (position['entry_price'] - position['stop_loss']) * position['quantity']
                            equity += pnl
                            all_trades.append(self._make_trade_record(position, ts, position['stop_loss'], pnl, 'stop_loss'))
                            position = None
                            continue
                        
                        # Target
                        if current_bar['low'] <= position['target_price']:
                            pnl = (position['entry_price'] - position['target_price']) * position['quantity']
                            equity += pnl
                            all_trades.append(self._make_trade_record(position, ts, position['target_price'], pnl, 'target'))
                            position = None
                            continue
                    
                    # Max holding bars
                    if position['bars_held'] >= self.max_holding_bars:
                        pnl = (current_bar['close'] - position['entry_price']) * position['quantity'] * (1 if position['direction'] == TradeDirection.LONG else -1)
                        equity += pnl
                        all_trades.append(self._make_trade_record(position, ts, current_bar['close'], pnl, 'time_exit'))
                        position = None
                        continue
                    
                    # Square off time
                    if self._is_square_off_time(ts):
                        pnl = (current_bar['close'] - position['entry_price']) * position['quantity'] * (1 if position['direction'] == TradeDirection.LONG else -1)
                        equity += pnl
                        all_trades.append(self._make_trade_record(position, ts, current_bar['close'], pnl, 'square_off'))
                        position = None
                        continue
                
                # Check for new signals (only if no open position)
                if position is None:
                    # Update support/resistance levels from current bar
                    strategy.update_levels(df, i)
                    
                    signals = []
                    long_sig = strategy.check_long_setup(df, i, capital)
                    if long_sig:
                        signals.append(long_sig)
                    short_sig = strategy.check_short_setup(df, i, capital)
                    if short_sig:
                        signals.append(short_sig)
                    bounce_sig = strategy.check_direct_support_bounce(df, i, capital)
                    if bounce_sig:
                        signals.append(bounce_sig)
                    
                    for signal in signals:
                        risk_per_share = abs(signal.entry_price - signal.stop_loss)
                        if risk_per_share <= 0:
                            continue
                        
                        risk_amount = capital * self.config.RISK_PER_TRADE_PCT
                        quantity = int(risk_amount / risk_per_share)
                        if quantity <= 0:
                            continue
                        
                        # Max 50% capital per trade
                        cost = signal.entry_price * quantity
                        if cost > capital * 0.5:
                            quantity = int(capital * 0.5 / signal.entry_price)
                            if quantity <= 0:
                                continue
                        
                        position = {
                            'ticker': ticker,
                            'direction': signal.direction,
                            'entry_price': signal.entry_price,
                            'stop_loss': signal.stop_loss,
                            'target_price': signal.target_price,
                            'quantity': quantity,
                            'entry_time': signal.entry_time,
                            'entry_bar_idx': i,
                            'bars_held': 0,
                            'unrealized_pnl': 0,
                            'signal_details': signal.signal_details,
                            'level_price': signal.level_price,
                            'level_type': signal.level_type
                        }
            
            # Close any remaining position at end of data
            if position is not None:
                last_price = df.iloc[-1]['close']
                if position['direction'] == TradeDirection.LONG:
                    pnl = (last_price - position['entry_price']) * position['quantity']
                else:
                    pnl = (position['entry_price'] - last_price) * position['quantity']
                equity += pnl
                all_trades.append(self._make_trade_record(position, df.index[-1], last_price, pnl, 'end_of_data'))
        
        # Calculate metrics
        return self._calculate_metrics(all_trades, capital, len(all_trades))
    
    def _make_trade_record(self, pos: Dict, exit_time: pd.Timestamp, exit_price: float, pnl: float, exit_reason: str) -> Dict:
        return {
            'ticker': pos['ticker'],
            'direction': pos['direction'].value,
            'entry_time': pos['entry_time'],
            'exit_time': exit_time,
            'entry_price': pos['entry_price'],
            'exit_price': exit_price,
            'stop_loss': pos['stop_loss'],
            'target_price': pos['target_price'],
            'quantity': pos['quantity'],
            'pnl': pnl,
            'return_pct': pnl / (pos['entry_price'] * pos['quantity']) * 100,
            'exit_reason': exit_reason,
            'bars_held': pos['bars_held'],
            'signal_details': pos['signal_details'],
            'level_price': pos['level_price'],
            'level_type': pos['level_type']
        }
    
    def _calculate_metrics(self, trades: List[Dict], initial_capital: float, total_data_points: int) -> IntradayBacktestResult:
        if not trades:
            return IntradayBacktestResult(
                total_return=0, annualized_return=0, max_drawdown=0, sharpe_ratio=0,
                win_rate=0, profit_factor=0, total_trades=0, winning_trades=0,
                losing_trades=0, avg_win=0, avg_loss=0, avg_r_multiple=0,
                equity_curve=pd.Series([initial_capital]),
                trades=[], metrics={}
            )
        
        trades_df = pd.DataFrame(trades)
        
        total_trades = len(trades_df)
        winning = len(trades_df[trades_df['pnl'] > 0])
        losing = len(trades_df[trades_df['pnl'] < 0])
        win_rate = winning / total_trades if total_trades > 0 else 0
        
        avg_win = trades_df[trades_df['pnl'] > 0]['pnl'].mean() if winning > 0 else 0
        avg_loss = trades_df[trades_df['pnl'] < 0]['pnl'].mean() if losing > 0 else 0
        
        gross_profit = trades_df[trades_df['pnl'] > 0]['pnl'].sum()
        gross_loss = abs(trades_df[trades_df['pnl'] < 0]['pnl'].sum())
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')
        
        # R-multiple: P&L / (risk_per_share * quantity)
        risk_per_share = (trades_df['entry_price'] - trades_df['stop_loss']).abs()
        trades_df['r_multiple'] = trades_df['pnl'] / (risk_per_share * trades_df['quantity'])
        avg_r = trades_df['r_multiple'].mean()
        
        # Total return
        final_equity = initial_capital + trades_df['pnl'].sum()
        total_return = (final_equity - initial_capital) / initial_capital * 100
        
        # Build daily equity curve for Sharpe/DD
        trades_df['exit_time'] = pd.to_datetime(trades_df['exit_time'])
        daily_pnl = trades_df.groupby(trades_df['exit_time'].dt.date)['pnl'].sum()
        daily_equity = initial_capital + daily_pnl.cumsum()
        
        # Max DD from daily equity
        rolling_max = daily_equity.expanding().max()
        dd = (daily_equity - rolling_max) / rolling_max * 100
        max_dd = dd.min()
        
        # Sharpe (daily returns)
        daily_ret = daily_equity.pct_change().dropna()
        sharpe = daily_ret.mean() / daily_ret.std() * np.sqrt(252) if len(daily_ret) > 1 and daily_ret.std() > 0 else 0
        
        # Annualized
        days = (trades_df['exit_time'].max() - trades_df['entry_time'].min()).days
        years = days / 365 if days > 0 else 0
        annualized = (1 + total_return/100) ** (1/years) - 1 if years > 0 else 0
        
        return IntradayBacktestResult(
            total_return=total_return,
            annualized_return=annualized * 100,
            max_drawdown=max_dd,
            sharpe_ratio=sharpe,
            win_rate=win_rate * 100,
            profit_factor=profit_factor,
            total_trades=total_trades,
            winning_trades=winning,
            losing_trades=losing,
            avg_win=avg_win,
            avg_loss=avg_loss,
            avg_r_multiple=avg_r,
            equity_curve=daily_equity,
            trades=trades,
            metrics={
                'gross_profit': gross_profit,
                'gross_loss': gross_loss,
                'avg_r_multiple': avg_r,
                'by_exit_reason': trades_df['exit_reason'].value_counts().to_dict(),
                'by_level_type': trades_df['level_type'].value_counts().to_dict(),
                'by_direction': trades_df['direction'].value_counts().to_dict(),
            }
        )


def run_intraday_backtest(
    data_dict: Dict[str, pd.DataFrame],
    config: Config = DEFAULT_CONFIG
) -> IntradayBacktestResult:
    backtester = IntradayBacktester(config)
    return backtester.run_backtest(data_dict, config.INITIAL_CAPITAL)