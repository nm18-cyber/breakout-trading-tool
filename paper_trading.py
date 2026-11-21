"""
Paper trading module for tracking simulated trades with NSE data.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum
import pandas as pd
import json
import os
from pathlib import Path

from config import DEFAULT_CONFIG, Config
from strategy import Signal, Position, BreakoutStrategy, create_strategy
from data_loader import create_data_loader
from indicators import add_indicators


class OrderStatus(Enum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass
class PaperOrder:
    """Paper trading order."""
    id: str
    ticker: str
    side: OrderSide
    quantity: int
    price: float
    order_type: str  # market, limit, stop
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    filled_at: Optional[datetime] = None
    filled_price: Optional[float] = None
    signal_type: str = ""
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "ticker": self.ticker,
            "side": self.side.value,
            "quantity": self.quantity,
            "price": self.price,
            "order_type": self.order_type,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "filled_at": self.filled_at.isoformat() if self.filled_at else None,
            "filled_price": self.filled_price,
            "signal_type": self.signal_type
        }


@dataclass
class PaperTrade:
    """Completed paper trade (entry + exit)."""
    ticker: str
    entry_date: datetime
    exit_date: Optional[datetime]
    entry_price: float
    exit_price: Optional[float]
    quantity: int
    side: OrderSide
    pnl: float = 0.0
    return_pct: float = 0.0
    entry_signal: str = ""
    exit_reason: str = ""
    status: str = "open"  # open, closed
    
    def close_trade(self, exit_price: float, exit_date: datetime, exit_reason: str):
        self.exit_price = exit_price
        self.exit_date = exit_date
        self.exit_reason = exit_reason
        self.status = "closed"
        if self.side == OrderSide.BUY:
            self.pnl = (exit_price - self.entry_price) * self.quantity
        else:
            self.pnl = (self.entry_price - exit_price) * self.quantity
        self.return_pct = (self.pnl / (self.entry_price * self.quantity)) * 100
    
    def unrealized_pnl(self, current_price: float) -> float:
        if self.side == OrderSide.BUY:
            return (current_price - self.entry_price) * self.quantity
        else:
            return (self.entry_price - current_price) * self.quantity
    
    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "entry_date": self.entry_date.isoformat(),
            "exit_date": self.exit_date.isoformat() if self.exit_date else None,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "quantity": self.quantity,
            "side": self.side.value,
            "pnl": self.pnl,
            "return_pct": self.return_pct,
            "entry_signal": self.entry_signal,
            "exit_reason": self.exit_reason,
            "status": self.status
        }


class PaperTradingEngine:
    """Paper trading engine for NSE stocks."""
    
    def __init__(self, config: Config = DEFAULT_CONFIG, data_dir: str = "paper_trades"):
        self.config = config
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.orders: Dict[str, PaperOrder] = {}
        self.trades: List[PaperTrade] = []
        self.positions: Dict[str, PaperTrade] = {}  # ticker -> open trade
        self.cash = config.INITIAL_CAPITAL
        self.initial_capital = config.INITIAL_CAPITAL
        
        self.data_loader = create_data_loader(config)
        self.strategy = create_strategy(config)
        
        # Load existing state
        self._load_state()
    
    def _get_order_id(self) -> str:
        return f"ORD_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
    
    def _save_state(self):
        """Save paper trading state to disk."""
        state = {
            "cash": self.cash,
            "initial_capital": self.initial_capital,
            "orders": {k: v.to_dict() for k, v in self.orders.items()},
            "trades": [t.to_dict() for t in self.trades],
            "positions": {k: v.to_dict() for k, v in self.positions.items()}
        }
        with open(self.data_dir / "paper_state.json", "w") as f:
            json.dump(state, f, indent=2, default=str)
    
    def _load_state(self):
        """Load paper trading state from disk."""
        state_file = self.data_dir / "paper_state.json"
        if state_file.exists():
            try:
                with open(state_file, "r") as f:
                    state = json.load(f)
                
                self.cash = state.get("cash", self.initial_capital)
                self.initial_capital = state.get("initial_capital", self.initial_capital)
                
                for k, v in state.get("orders", {}).items():
                    v["created_at"] = datetime.fromisoformat(v["created_at"])
                    if v["filled_at"]:
                        v["filled_at"] = datetime.fromisoformat(v["filled_at"])
                    v["side"] = OrderSide(v["side"])
                    v["status"] = OrderStatus(v["status"])
                    self.orders[k] = PaperOrder(**v)
                
                for t in state.get("trades", []):
                    t["entry_date"] = datetime.fromisoformat(t["entry_date"])
                    if t["exit_date"]:
                        t["exit_date"] = datetime.fromisoformat(t["exit_date"])
                    t["side"] = OrderSide(t["side"])
                    self.trades.append(PaperTrade(**t))
                
                for k, v in state.get("positions", {}).items():
                    v["entry_date"] = datetime.fromisoformat(v["entry_date"])
                    if v["exit_date"]:
                        v["exit_date"] = datetime.fromisoformat(v["exit_date"])
                    v["side"] = OrderSide(v["side"])
                    self.positions[k] = PaperTrade(**v)
                    
            except Exception as e:
                print(f"Failed to load paper trading state: {e}")
    
    def get_latest_price(self, ticker: str) -> Optional[float]:
        """Get latest market price for a ticker."""
        try:
            data = self.data_loader.get_latest_data([ticker])
            if ticker in data and not data[ticker].empty:
                return float(data[ticker].iloc[-1]['close'])
        except Exception:
            pass
        return None
    
    def place_market_order(
        self, 
        ticker: str, 
        side: OrderSide, 
        quantity: int,
        signal_type: str = ""
    ) -> PaperOrder:
        """Place a market order (filled at latest price)."""
        price = self.get_latest_price(ticker)
        if price is None:
            raise ValueError(f"Could not get price for {ticker}")
        
        order = PaperOrder(
            id=self._get_order_id(),
            ticker=ticker,
            side=side,
            quantity=quantity,
            price=price,
            order_type="market",
            status=OrderStatus.FILLED,
            filled_at=datetime.now(),
            filled_price=price,
            signal_type=signal_type
        )
        
        self.orders[order.id] = order
        
        if side == OrderSide.BUY:
            cost = price * quantity
            if cost > self.cash:
                order.status = OrderStatus.REJECTED
                raise ValueError(f"Insufficient cash: need ₹{cost:,.0f}, have ₹{self.cash:,.0f}")
            self.cash -= cost
            
            # Create position
            trade = PaperTrade(
                ticker=ticker,
                entry_date=datetime.now(),
                exit_date=None,
                entry_price=price,
                exit_price=None,
                quantity=quantity,
                side=OrderSide.BUY,
                entry_signal=signal_type,
                status="open"
            )
            self.positions[ticker] = trade
            self.trades.append(trade)
            
        elif side == OrderSide.SELL:
            if ticker not in self.positions:
                order.status = OrderStatus.REJECTED
                raise ValueError(f"No open position in {ticker} to sell")
            
            position = self.positions[ticker]
            if position.quantity < quantity:
                order.status = OrderStatus.REJECTED
                raise ValueError(f"Insufficient quantity: have {position.quantity}, trying to sell {quantity}")
            
            proceeds = price * quantity
            self.cash += proceeds
            
            # Close or reduce position
            position.close_trade(price, datetime.now(), "manual_sell")
            if position.quantity == quantity:
                del self.positions[ticker]
            else:
                position.quantity -= quantity
        
        self._save_state()
        return order
    
    def check_stop_losses(self) -> List[PaperOrder]:
        """Check and execute stop losses for all open positions."""
        executed = []
        for ticker, position in list(self.positions.items()):
            # Get latest data with indicators
            data = self.data_loader.get_latest_data([ticker])
            if ticker not in data or data[ticker].empty:
                continue
            
            df = add_indicators(data[ticker], self.config)
            latest = df.iloc[-1]
            
            # Calculate stop loss based on entry (2 * ATR at entry)
            # For simplicity, use current ATR
            atr = latest.get('14_atr', 0)
            stop_loss = position.entry_price - (2 * atr)
            
            current_price = latest['close']
            low_price = latest['low']
            
            if low_price <= stop_loss:
                # Stop loss hit
                order = self.place_market_order(
                    ticker, OrderSide.SELL, position.quantity, 
                    signal_type=f"stop_loss_{position.entry_signal}"
                )
                executed.append(order)
        
        return executed
    
    def check_signals_and_enter(self, capital_per_trade: float = None) -> List[PaperOrder]:
        """Scan for breakout signals and auto-enter positions."""
        if capital_per_trade is None:
            capital_per_trade = self.cash * 0.1  # Use 10% of available cash per trade
        
        executed = []
        
        # Get data for all Nifty 100 tickers
        data_dict = self.data_loader.get_latest_data(self.config.NIFTY_100_TICKERS)
        
        # Add indicators
        for ticker, df in data_dict.items():
            if len(df) >= 260:
                data_dict[ticker] = add_indicators(df, self.config)
        
        # Scan for signals
        signals = self.strategy.scan_universe(data_dict, self.config.INITIAL_CAPITAL)
        
        for signal in signals:
            ticker = signal.ticker
            
            # Skip if already have position
            if ticker in self.positions:
                continue
            
            # Calculate position size based on available cash
            risk_per_share = signal.risk_per_share
            if risk_per_share <= 0:
                continue
            
            max_shares = int(capital_per_trade / signal.entry_price)
            risk_shares = int((self.cash * 0.01) / risk_per_share)  # 1% risk
            quantity = min(max_shares, risk_shares, signal.position_size)
            
            if quantity <= 0:
                continue
            
            try:
                order = self.place_market_order(
                    ticker, OrderSide.BUY, quantity, signal.signal_type
                )
                executed.append(order)
            except ValueError as e:
                print(f"Failed to enter {ticker}: {e}")
        
        return executed
    
    def get_portfolio_value(self) -> dict:
        """Get current portfolio value."""
        total_value = self.cash
        positions_detail = []
        
        for ticker, position in self.positions.items():
            current_price = self.get_latest_price(ticker)
            if current_price:
                market_value = current_price * position.quantity
                unrealized = position.unrealized_pnl(current_price)
                total_value += market_value
                
                positions_detail.append({
                    "ticker": ticker.replace(".NS", ""),
                    "quantity": position.quantity,
                    "entry_price": position.entry_price,
                    "current_price": current_price,
                    "market_value": market_value,
                    "unrealized_pnl": unrealized,
                    "unrealized_pct": (unrealized / (position.entry_price * position.quantity)) * 100,
                    "entry_date": position.entry_date.strftime("%Y-%m-%d"),
                    "signal": position.entry_signal
                })
        
        total_pnl = total_value - self.initial_capital
        total_return_pct = (total_pnl / self.initial_capital) * 100
        
        return {
            "cash": self.cash,
            "positions_value": total_value - self.cash,
            "total_value": total_value,
            "total_pnl": total_pnl,
            "total_return_pct": total_return_pct,
            "positions": positions_detail,
            "open_positions_count": len(self.positions)
        }
    
    def get_trade_history(self) -> List[dict]:
        """Get closed trade history."""
        return [t.to_dict() for t in self.trades if t.status == "closed"]
    
    def get_open_orders(self) -> List[dict]:
        """Get pending orders."""
        return [o.to_dict() for o in self.orders.values() if o.status == OrderStatus.PENDING]
    
    def reset(self):
        """Reset paper trading account."""
        self.orders.clear()
        self.trades.clear()
        self.positions.clear()
        self.cash = self.initial_capital
        self._save_state()


def create_paper_engine(config: Config = DEFAULT_CONFIG) -> PaperTradingEngine:
    """Factory function to create paper trading engine."""
    return PaperTradingEngine(config)