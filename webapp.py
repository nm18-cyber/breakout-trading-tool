"""
Streamlit web interface for the Breakout Trading Tool.
Run with: streamlit run webapp.py
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import sys
import os

# Add the project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import DEFAULT_CONFIG, Config
from data_loader import create_data_loader
from strategy import create_strategy
from backtester import run_backtest
from opening_level_strategy import create_opening_level_strategy
from intraday_backtester import run_intraday_backtest, IntradayBacktester
from indicators import add_indicators
from paper_trading import create_paper_engine, PaperTradingEngine, OrderSide

st.set_page_config(
    page_title="Breakout Trading Tool",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
    }
    .signal-buy { border-left-color: #28a745; }
    .signal-sell { border-left-color: #dc3545; }
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
    }
    .paper-trade-open { background-color: #e8f5e9; }
    .paper-trade-closed { background-color: #fce4ec; }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_paper_engine(capital):
    """Get or create paper trading engine (cached across runs)."""
    config = Config(INITIAL_CAPITAL=capital)
    return create_paper_engine(config)


@st.cache_data(ttl=3600)
def load_data(tickers, years=3):
    """Load and cache market data."""
    config = Config(
        BACKTEST_YEARS=years,
        INITIAL_CAPITAL=10_00_000,
        NIFTY_100_TICKERS=tickers
    )
    loader = create_data_loader(config)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=years * 365)
    data_dict = loader.fetch_multiple(tickers, start_date, end_date, use_cache=True)
    
    # Add indicators
    for ticker, df in data_dict.items():
        if len(df) >= 260:
            data_dict[ticker] = add_indicators(df, config)
    return data_dict, config


@st.cache_data(ttl=300)
def run_screening(data_dict, capital):
    """Run screening and cache results."""
    config = Config(INITIAL_CAPITAL=capital)
    strategy = create_strategy(config)
    signals = strategy.scan_universe(data_dict, capital)
    return signals


@st.cache_data(ttl=3600)
def run_backtest_cached(data_dict, capital, years):
    """Run backtest and cache results."""
    config = Config(BACKTEST_YEARS=years, INITIAL_CAPITAL=capital)
    return run_backtest(data_dict, config)


@st.cache_data(ttl=3600)
def load_intraday_data(tickers, interval, days):
    """Load intraday data for Opening Level Strategy."""
    config = Config(
        DATA_INTERVAL=interval,
        INITIAL_CAPITAL=10_00_000,
        NIFTY_50_TICKERS=tickers
    )
    loader = create_data_loader(config)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    data_dict = loader.fetch_multiple(tickers, start_date, end_date, use_cache=True, interval=interval)
    
    # Add indicators
    for ticker, df in data_dict.items():
        if len(df) >= 50:
            data_dict[ticker] = add_indicators(df, config)
    return data_dict, config


@st.cache_data(ttl=3600)
def run_intraday_backtest_cached(data_dict, capital, interval):
    """Run intraday backtest and cache results."""
    config = Config(
        DATA_INTERVAL=interval,
        INITIAL_CAPITAL=capital
    )
    return run_intraday_backtest(data_dict, config)


def plot_equity_curve(equity_curve):
    """Plot equity curve using Plotly."""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=equity_curve.index,
        y=equity_curve.values,
        mode='lines',
        name='Equity',
        line=dict(color='#1f77b4', width=2)
    ))
    fig.update_layout(
        title="Equity Curve",
        xaxis_title="Date",
        yaxis_title="Equity (₹)",
        template="plotly_white",
        height=400,
        margin=dict(l=0, r=0, t=40, b=0)
    )
    return fig


def plot_drawdown(equity_curve):
    """Plot drawdown chart."""
    rolling_max = equity_curve.expanding().max()
    drawdown = (equity_curve - rolling_max) / rolling_max * 100
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=drawdown.index,
        y=drawdown.values,
        mode='lines',
        name='Drawdown %',
        fill='tozeroy',
        line=dict(color='#dc3545', width=1),
        fillcolor='rgba(220, 53, 69, 0.1)'
    ))
    fig.update_layout(
        title="Drawdown",
        xaxis_title="Date",
        yaxis_title="Drawdown (%)",
        template="plotly_white",
        height=300,
        margin=dict(l=0, r=0, t=40, b=0)
    )
    return fig


def plot_price_with_signals(df, ticker, signals):
    """Plot price chart with indicators and signals."""
    fig = go.Figure()
    
    # Candlestick
    fig.add_trace(go.Candlestick(
        x=df.index[-200:],
        open=df['open'][-200:],
        high=df['high'][-200:],
        low=df['low'][-200:],
        close=df['close'][-200:],
        name='Price'
    ))
    
    # 200 SMA
    if '200_sma' in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index[-200:],
            y=df['200_sma'][-200:],
            mode='lines',
            name='200 SMA',
            line=dict(color='orange', width=1)
        ))
    
    # 20-day High
    if '20_day_high' in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index[-200:],
            y=df['20_day_high'][-200:],
            mode='lines',
            name='20D High',
            line=dict(color='green', width=1, dash='dash')
        ))
    
    # 52-week High
    if '52w_high' in df.columns:
        fig.add_trace(go.Scatter(
            x=df.index[-200:],
            y=df['52w_high'][-200:],
            mode='lines',
            name='52W High',
            line=dict(color='red', width=1, dash='dot')
        ))
    
    fig.update_layout(
        title=f"{ticker} - Price & Breakout Levels (Last 200 Days)",
        xaxis_title="Date",
        yaxis_title="Price (₹)",
        template="plotly_white",
        height=500,
        margin=dict(l=0, r=0, t=40, b=0),
        xaxis_rangeslider_visible=False
    )
    return fig


def plot_paper_equity(engine: PaperTradingEngine):
    """Plot paper trading equity curve."""
    # Get historical portfolio values from closed trades
    # For now, show current snapshot
    portfolio = engine.get_portfolio_value()
    
    fig = go.Figure()
    fig.add_trace(go.Indicator(
        mode="number+delta",
        value=portfolio['total_value'],
        delta={'reference': portfolio['initial_capital'] if 'initial_capital' in portfolio else engine.initial_capital,
               'relative': True, 'valueformat': '.2%'},
        title={'text': "Portfolio Value (₹)"},
        number={'prefix': "₹", 'valueformat': ',.0f'}
    ))
    fig.update_layout(height=200, margin=dict(l=0, r=0, t=20, b=0))
    return fig


# Sidebar
st.sidebar.title("📈 Breakout Trading Tool")
st.sidebar.markdown("Nifty 50/100 Systematic Breakout Strategy")

# Configuration
st.sidebar.header("Configuration")
capital = st.sidebar.number_input(
    "Capital (₹)", 
    min_value=100000, 
    max_value=10_00_00_000, 
    value=10_00_000, 
    step=100000,
    format="%d"
)

years = st.sidebar.slider("Backtest Years", 1, 5, 3)

# Intraday interval selection
intraday_mode = st.sidebar.checkbox("Intraday Mode (Opening Level Strategy)", value=False)
interval = None
if intraday_mode:
    interval = st.sidebar.selectbox(
        "Timeframe",
        ["5m", "15m", "30m", "1h"],
        index=1,
        help="5m/15m/30m: max 60 days, 1h: max 730 days"
    )

# Universe selection
universe = st.sidebar.selectbox(
    "Universe",
    ["Nifty 50", "Nifty 100", "Custom"],
    index=0
)

# Ticker selection
if universe == "Nifty 50":
    default_tickers = DEFAULT_CONFIG.NIFTY_50_TICKERS
elif universe == "Nifty 100":
    default_tickers = DEFAULT_CONFIG.NIFTY_100_TICKERS
else:
    default_tickers = [
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
        "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS"
    ]

ticker_input = st.sidebar.text_area(
    "Tickers (one per line, .NS suffix)",
    value="\n".join(default_tickers),
    height=300
)
tickers = [t.strip() for t in ticker_input.split("\n") if t.strip()]

# Initialize paper trading engine
paper_engine = get_paper_engine(capital)

# Paper trading controls in sidebar
st.sidebar.markdown("---")
st.sidebar.header("📝 Paper Trading")

if st.sidebar.button("🔄 Scan & Auto-Enter Signals"):
    with st.spinner("Scanning for breakout signals and entering..."):
        executed = paper_engine.check_signals_and_enter()
    if executed:
        st.sidebar.success(f"Entered {len(executed)} positions!")
        for o in executed:
            st.sidebar.write(f"✅ {o.ticker.replace('.NS','')} - {o.quantity} @ ₹{o.filled_price:,.2f}")
    else:
        st.sidebar.info("No new signals to enter")

if st.sidebar.button("🛑 Check Stop Losses"):
    with st.spinner("Checking stop losses..."):
        executed = paper_engine.check_stop_losses()
    if executed:
        st.sidebar.warning(f"Stop losses hit: {len(executed)}")
        for o in executed:
            st.sidebar.write(f"🛑 {o.ticker.replace('.NS','')} - {o.quantity} @ ₹{o.filled_price:,.2f}")
    else:
        st.sidebar.info("No stop losses triggered")

if st.sidebar.button("🔄 Refresh Portfolio"):
    st.rerun()

if st.sidebar.button("🗑️ Reset Account"):
    paper_engine.reset()
    st.sidebar.success("Paper trading account reset!")
    st.rerun()

# Main tabs
tab1, tab2, tab3, tab4, tab5 = st.tabs(["🔍 Screening", "📊 Backtest", "⚡ Intraday", "📈 Charts", "📝 Paper Trading"])

# Load data (skip daily load in intraday mode)
if not intraday_mode:
    with st.spinner("Loading market data..."):
        data_dict, config = load_data(tickers, years)
else:
    data_dict, config = {}, None

# Tab 1: Screening
with tab1:
    st.header("🔍 Live Breakout Screening")
    
    if st.button("Run Screening", type="primary"):
        with st.spinner("Scanning for breakout signals..."):
            signals = run_screening(data_dict, capital)
        
        if signals:
            st.success(f"Found {len(signals)} breakout signals!")
            
            # Display signals table
            signal_data = []
            for s in signals:
                signal_data.append({
                    "Ticker": s.ticker.replace(".NS", ""),
                    "Signal Type": s.signal_type.replace("_", " ").title(),
                    "Entry Price": f"₹{s.entry_price:,.2f}",
                    "Stop Loss": f"₹{s.stop_loss:,.2f}",
                    "Position Size": f"{s.position_size:,}",
                    "Risk/Share": f"₹{s.risk_per_share:,.2f}",
                    "Volume Ratio": f"{s.volume_ratio:.2f}x",
                    "ATR (14)": f"₹{s.atr:,.2f}",
                    "Capital at Risk": f"₹{s.risk_per_share * s.position_size:,.2f}"
                })
            
            df_signals = pd.DataFrame(signal_data)
            st.dataframe(df_signals, use_container_width=True, hide_index=True)
            
            # Summary metrics
            total_risk = sum(s.risk_per_share * s.position_size for s in signals)
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Signals", len(signals))
            col2.metric("Capital at Risk", f"₹{total_risk:,.0f}")
            col3.metric("Risk %", f"{total_risk/capital*100:.2f}%")
            
            # Signal details
            st.subheader("Signal Details")
            for s in signals:
                with st.expander(f"{s.ticker.replace('.NS', '')} - {s.signal_type}"):
                    col1, col2 = st.columns(2)
                    col1.write(f"**Entry:** ₹{s.entry_price:,.2f}")
                    col1.write(f"**Stop Loss:** ₹{s.stop_loss:,.2f}")
                    col1.write(f"**Position:** {s.position_size:,} shares")
                    col2.write(f"**Risk/Share:** ₹{s.risk_per_share:,.2f}")
                    col2.write(f"**Volume Ratio:** {s.volume_ratio:.2f}x")
                    col2.write(f"**ATR(14):** ₹{s.atr:,.2f}")
        else:
            st.info("No breakout signals found in current market data.")
            st.caption("Criteria: Close > 20D High OR 52W High OR Cross > 200 SMA, AND Volume ≥ 1.5x Avg Volume")

# Tab 2: Backtest
with tab2:
    st.header("📊 Historical Backtest")
    
    if st.button("Run Backtest", type="primary"):
        with st.spinner(f"Running {years}-year backtest on {len(data_dict)} tickers..."):
            result = run_backtest_cached(data_dict, capital, years)
        
        if result.total_trades > 0:
            # Key metrics row
            col1, col2, col3, col4, col5 = st.columns(5)
            col1.metric("Total Return", f"{result.total_return:.2f}%")
            col2.metric("Annualized Return", f"{result.annualized_return:.2f}%")
            col3.metric("Max Drawdown", f"{result.max_drawdown:.2f}%")
            col4.metric("Sharpe Ratio", f"{result.sharpe_ratio:.2f}")
            col5.metric("Win Rate", f"{result.win_rate:.2f}%")
            
            # Second row
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Profit Factor", f"{result.profit_factor:.2f}")
            col2.metric("Total Trades", result.total_trades)
            col3.metric("Avg Win", f"₹{result.avg_win:,.0f}")
            col4.metric("Avg Loss", f"₹{result.avg_loss:,.0f}")
            
            # Equity curve
            st.plotly_chart(plot_equity_curve(result.equity_curve), use_container_width=True)
            
            # Drawdown
            st.plotly_chart(plot_drawdown(result.equity_curve), use_container_width=True)
            
            # Trades table
            if result.trades:
                st.subheader("Trade History")
                trades_df = pd.DataFrame(result.trades)
                trades_df['entry_date'] = trades_df['entry_date'].dt.strftime('%Y-%m-%d')
                trades_df['exit_date'] = trades_df['exit_date'].dt.strftime('%Y-%m-%d')
                trades_df['pnl'] = trades_df['pnl'].apply(lambda x: f"₹{x:,.0f}")
                trades_df['return_pct'] = trades_df['return_pct'].apply(lambda x: f"{x:.2f}%")
                st.dataframe(trades_df, use_container_width=True, hide_index=True)
            
            # Exit reasons
            if result.trades:
                st.subheader("Exit Analysis")
                trades_df = pd.DataFrame(result.trades)
                exit_counts = trades_df['exit_reason'].value_counts()
                exit_pnl = trades_df.groupby('exit_reason')['pnl'].mean()
                exit_df = pd.DataFrame({
                    'Count': exit_counts,
                    'Avg P&L': exit_pnl.apply(lambda x: f"₹{x:,.0f}")
                })
                st.dataframe(exit_df, use_container_width=True)
        else:
            st.warning("No trades generated in backtest period. Try different tickers or longer period.")

# Tab 3: Intraday Opening Level Strategy
with tab3:
    st.header("⚡ Intraday Opening Level Strategy")
    st.caption("Breakout + Retest using Open==Low (Support) and Open==High (Resistance) candles")
    
    if not intraday_mode:
        st.info("Enable 'Intraday Mode' in the sidebar to configure timeframe and run intraday backtest.")
    else:
        # Intraday settings
        col1, col2 = st.columns(2)
        with col1:
            intraday_days = st.number_input(
                "Days of Data", 
                min_value=1, 
                max_value=60 if interval in ['5m', '15m', '30m'] else 730,
                value=30 if interval in ['5m', '15m', '30m'] else 60,
                help="5m/15m/30m limited to 60 days by yfinance, 1h up to 730 days"
            )
        with col2:
            st.metric("Timeframe", interval)
        
        if st.button("Load Intraday Data & Run Backtest", type="primary"):
            max_days = 60 if interval in ['5m', '15m', '30m'] else 730
            days = min(intraday_days, max_days)
            
            with st.spinner(f"Loading {interval} data for {len(tickers)} tickers ({days} days)..."):
                idata_dict, iconfig = load_intraday_data(tickers, interval, days)
            
            if idata_dict:
                st.success(f"Loaded data for {len(idata_dict)} tickers")
                
                with st.spinner(f"Running Opening Level Strategy backtest on {interval}..."):
                    iresult = run_intraday_backtest_cached(idata_dict, capital, interval)
                
                if iresult.total_trades > 0:
                    # Key metrics
                    m1, m2, m3, m4, m5 = st.columns(5)
                    m1.metric("Total Return", f"{iresult.total_return:.2f}%")
                    m2.metric("Annualized Return", f"{iresult.annualized_return:.2f}%")
                    m3.metric("Max Drawdown", f"{iresult.max_drawdown:.2f}%")
                    m4.metric("Sharpe Ratio", f"{iresult.sharpe_ratio:.2f}")
                    m5.metric("Win Rate", f"{iresult.win_rate:.2f}%")
                    
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Profit Factor", f"{iresult.profit_factor:.2f}")
                    m2.metric("Total Trades", iresult.total_trades)
                    m3.metric("Avg Win", f"₹{iresult.avg_win:,.0f}")
                    m4.metric("Avg Loss", f"₹{iresult.avg_loss:,.0f}")
                    
                    # Equity curve
                    st.plotly_chart(plot_equity_curve(iresult.equity_curve), use_container_width=True)
                    st.plotly_chart(plot_drawdown(iresult.equity_curve), use_container_width=True)
                    
                    # Trade breakdown
                    st.subheader("Trade Analysis")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write("**By Exit Reason:**")
                        for reason, count in iresult.metrics.get('by_exit_reason', {}).items():
                            st.write(f"  {reason}: {count}")
                    with col2:
                        st.write("**By Level Type:**")
                        for level_type, count in iresult.metrics.get('by_level_type', {}).items():
                            st.write(f"  {level_type}: {count}")
                    
                    # Per-ticker summary
                    st.subheader("Per-Ticker Results")
                    trades_df = pd.DataFrame(iresult.trades)
                    ticker_summary = trades_df.groupby('ticker').agg(
                        trades=('pnl', 'count'),
                        total_pnl=('pnl', 'sum'),
                        win_rate=('pnl', lambda x: (x > 0).mean() * 100)
                    ).round(2)
                    ticker_summary['ticker'] = ticker_summary.index.str.replace('.NS', '')
                    st.dataframe(ticker_summary.reset_index(drop=True), use_container_width=True, hide_index=True)
                    
                    # Trades table
                    st.subheader("Trade History")
                    display_trades = trades_df.copy()
                    display_trades['entry_time'] = pd.to_datetime(display_trades['entry_time']).dt.strftime('%Y-%m-%d %H:%M')
                    display_trades['exit_time'] = pd.to_datetime(display_trades['exit_time']).dt.strftime('%Y-%m-%d %H:%M')
                    display_trades['entry_price'] = display_trades['entry_price'].apply(lambda x: f"₹{x:,.2f}")
                    display_trades['exit_price'] = display_trades['exit_price'].apply(lambda x: f"₹{x:,.2f}")
                    display_trades['pnl'] = display_trades['pnl'].apply(lambda x: f"₹{x:,.0f}")
                    display_trades['return_pct'] = display_trades['return_pct'].apply(lambda x: f"{x:.2f}%")
                    st.dataframe(
                        display_trades[['ticker', 'direction', 'entry_time', 'exit_time', 
                                        'entry_price', 'exit_price', 'pnl', 'return_pct', 
                                        'exit_reason', 'level_type']],
                        use_container_width=True, hide_index=True
                    )
                else:
                    st.warning("No trades generated. Try different parameters or longer period.")
            else:
                st.error("No data fetched. Check ticker symbols and try again.")

# Tab 4: Charts (was tab3)
with tab4:
    st.header("📈 Price Charts with Indicators")
    
    selected_ticker = st.selectbox("Select Ticker", list(data_dict.keys()))
    
    if selected_ticker and selected_ticker in data_dict:
        df = data_dict[selected_ticker]
        
        # Run screening to get signals for this ticker
        signals = run_screening({selected_ticker: df}, capital)
        ticker_signals = [s for s in signals if s.ticker == selected_ticker]
        
        # Plot
        fig = plot_price_with_signals(df, selected_ticker, ticker_signals)
        st.plotly_chart(fig, use_container_width=True)
        
        # Latest indicators
        st.subheader("Latest Indicators")
        latest = df.iloc[-1]
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Close", f"₹{latest['close']:,.2f}")
        col2.metric("200 SMA", f"₹{latest.get('200_sma', 0):,.2f}")
        col3.metric("20D High", f"₹{latest.get('20_day_high', 0):,.2f}")
        col4.metric("52W High", f"₹{latest.get('52w_high', 0):,.2f}")
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("14 ATR", f"₹{latest.get('14_atr', 0):,.2f}")
        col2.metric("Vol Ratio", f"{latest.get('vol_ratio', 0):.2f}x")
        col3.metric("Dist from 200SMA", f"{latest.get('dist_from_200sma', 0):.2f}%")
        col4.metric("Dist from 52W High", f"{latest.get('dist_from_52w_high', 0):.2f}%")
        
        # Signal status
        if ticker_signals:
            st.success(f"🟢 **ACTIVE SIGNAL**: {ticker_signals[0].signal_type}")
            s = ticker_signals[0]
            st.write(f"Entry: ₹{s.entry_price:,.2f} | Stop: ₹{s.stop_loss:,.2f} | Size: {s.position_size:,}")
        else:
            st.info("No active signal for this ticker")

# Tab 5: Paper Trading (was tab4)
with tab5:
    st.header("📝 Paper Trading Dashboard")
    
    # Get portfolio value
    portfolio = paper_engine.get_portfolio_value()
    
    # Portfolio summary
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Value", f"₹{portfolio['total_value']:,.0f}", 
                delta=f"{portfolio['total_return_pct']:.2f}%")
    col2.metric("Cash", f"₹{portfolio['cash']:,.0f}")
    col3.metric("Positions Value", f"₹{portfolio['positions_value']:,.0f}")
    col4.metric("Open Positions", portfolio['open_positions_count'])
    col5.metric("Total P&L", f"₹{portfolio['total_pnl']:,.0f}", 
                delta=f"{portfolio['total_return_pct']:.2f}%")
    
    # Open Positions
    st.subheader("📂 Open Positions")
    if portfolio['positions']:
        pos_df = pd.DataFrame(portfolio['positions'])
        # Format for display
        display_df = pos_df.copy()
        display_df['entry_price'] = display_df['entry_price'].apply(lambda x: f"₹{x:,.2f}")
        display_df['current_price'] = display_df['current_price'].apply(lambda x: f"₹{x:,.2f}")
        display_df['market_value'] = display_df['market_value'].apply(lambda x: f"₹{x:,.0f}")
        display_df['unrealized_pnl'] = display_df['unrealized_pnl'].apply(lambda x: f"₹{x:,.0f}")
        display_df['unrealized_pct'] = display_df['unrealized_pct'].apply(lambda x: f"{x:.2f}%")
        
        st.dataframe(display_df[['ticker', 'quantity', 'entry_price', 'current_price', 
                                  'market_value', 'unrealized_pnl', 'unrealized_pct', 
                                  'entry_date', 'signal']], 
                     use_container_width=True, hide_index=True)
        
        # Manual exit buttons
        st.write("**Manual Exit:**")
        cols = st.columns(min(len(portfolio['positions']), 5))
        for idx, pos in enumerate(portfolio['positions']):
            with cols[idx % 5]:
                if st.button(f"Sell {pos['ticker']}", key=f"sell_{pos['ticker']}"):
                    try:
                        order = paper_engine.place_market_order(
                            pos['ticker'] + ".NS", OrderSide.SELL, pos['quantity'], "manual_exit"
                        )
                        st.success(f"Sold {pos['ticker']} @ ₹{order.filled_price:,.2f}")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to sell: {e}")
    else:
        st.info("No open positions. Click 'Scan & Auto-Enter Signals' in sidebar to enter trades.")
    
    # Trade History
    st.subheader("📋 Closed Trades")
    trades = paper_engine.get_trade_history()
    if trades:
        trades_df = pd.DataFrame(trades)
        trades_df['entry_date'] = pd.to_datetime(trades_df['entry_date']).dt.strftime('%Y-%m-%d')
        trades_df['exit_date'] = pd.to_datetime(trades_df['exit_date']).dt.strftime('%Y-%m-%d')
        trades_df['entry_price'] = trades_df['entry_price'].apply(lambda x: f"₹{x:,.2f}")
        trades_df['exit_price'] = trades_df['exit_price'].apply(lambda x: f"₹{x:,.2f}")
        trades_df['pnl'] = trades_df['pnl'].apply(lambda x: f"₹{x:,.0f}")
        trades_df['return_pct'] = trades_df['return_pct'].apply(lambda x: f"{x:.2f}%")
        
        st.dataframe(trades_df[['ticker', 'side', 'quantity', 'entry_date', 'exit_date',
                                 'entry_price', 'exit_price', 'pnl', 'return_pct', 
                                 'entry_signal', 'exit_reason']], 
                     use_container_width=True, hide_index=True)
        
        # Trade stats
        total_trades = len(trades)
        winning = len([t for t in trades if t['pnl'] > 0])
        losing = total_trades - winning
        win_rate = (winning / total_trades * 100) if total_trades > 0 else 0
        total_pnl = sum(t['pnl'] for t in trades)
        
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Trades", total_trades)
        col2.metric("Win Rate", f"{win_rate:.1f}%")
        col3.metric("Winning", winning)
        col4.metric("Losing", losing)
    else:
        st.info("No closed trades yet.")
    
    # Manual Order Entry
    st.subheader("📝 Manual Order")
    with st.form("manual_order"):
        col1, col2, col3 = st.columns(3)
        with col1:
            manual_ticker = st.selectbox("Ticker", [""] + [t.replace(".NS", "") for t in tickers])
        with col2:
            manual_side = st.selectbox("Side", ["BUY", "SELL"])
        with col3:
            manual_qty = st.number_input("Quantity", min_value=1, value=1)
        
        submitted = st.form_submit_button("Place Order")
        if submitted and manual_ticker:
            try:
                side = OrderSide.BUY if manual_side == "BUY" else OrderSide.SELL
                order = paper_engine.place_market_order(
                    manual_ticker + ".NS", side, manual_qty, "manual"
                )
                st.success(f"Order filled: {manual_side} {manual_qty} {manual_ticker} @ ₹{order.filled_price:,.2f}")
                st.rerun()
            except Exception as e:
                st.error(f"Order failed: {e}")

# Footer
st.sidebar.markdown("---")
st.sidebar.caption("Breakout Trading Tool v1.0")
st.sidebar.caption("Educational/Research purposes only. Not financial advice.")