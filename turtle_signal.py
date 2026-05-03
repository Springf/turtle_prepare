import sys
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

def calculate_atr(df, period=20):
    """
    Calculate N (ATR) using the Turtle Trading method:
    Initial N is the 20-day SMA of TR.
    Subsequent N = ((19 * Previous N) + Current TR) / 20
    """
    high = df['High']
    low = df['Low']
    prev_close = df['Close'].shift(1)
    
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    atr = [0.0] * len(tr)
    if len(tr) > period:
        initial_n = tr[1:period+1].mean()
        atr[period] = initial_n
        
        for i in range(period + 1, len(tr)):
            atr[i] = ((period - 1) * atr[i-1] + tr.iloc[i]) / period
            
    df['TR'] = tr
    df['ATR'] = atr
    return df

def was_last_s1_winner(df):
    """
    Checks if the last S1 (20-day) breakout would have been a winning trade.
    A winning trade reached a 10-day exit before hitting a 2N stop.
    """
    # Start looking from yesterday backwards
    for i in range(len(df) - 2, 60, -1):
        # Calculate 20-day high/low for that point in time (from previous 20 days)
        prev_20 = df.iloc[i-20:i]
        h20 = prev_20['High'].max()
        l20 = prev_20['Low'].min()
        
        signal = None
        if df.iloc[i]['Close'] > h20:
            signal = "LONG"
        elif df.iloc[i]['Close'] < l20:
            signal = "SHORT"
            
        if signal:
            entry_price = df.iloc[i]['Close']
            entry_atr = df.iloc[i]['ATR']
            stop_dist = 2 * entry_atr
            
            # Trace trade forward to see if it wins or loses
            for j in range(i + 1, len(df)):
                current_high = df.iloc[j]['High']
                current_low = df.iloc[j]['Low']
                current_close = df.iloc[j]['Close']
                
                # 10-day exit levels
                prev_10 = df.iloc[j-10:j]
                exit_10_low = prev_10['Low'].min()
                exit_10_high = prev_10['High'].max()
                
                if signal == "LONG":
                    # Hit 2N stop?
                    if current_low <= (entry_price - stop_dist):
                        return False # Loser
                    # Hit 10-day exit?
                    if current_low <= exit_10_low:
                        return current_close > entry_price # Winner if exit > entry
                else: # SHORT
                    if current_high >= (entry_price + stop_dist):
                        return False
                    if current_high >= exit_10_high:
                        return current_close < entry_price
            
            # If we reached today and still in trade, check current profit
            return df.iloc[-1]['Close'] > entry_price if signal == "LONG" else df.iloc[-1]['Close'] < entry_price
            
    return False # No signal found or inconclusive

def get_turtle_signals(ticker_name):
    # Fetch 1 year of data to have enough history for previous breakout analysis
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    
    try:
        df = yf.download(ticker_name, start=start_date, end=end_date, progress=False)
        if df.empty:
            return None
        
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        if len(df) < 60:
            return {"error": f"Not enough data for {ticker_name}"}

        df = calculate_atr(df)
        
        current_price = df['Close'].iloc[-1]
        current_atr = df['ATR'].iloc[-1]
        
        # S1 (20-day)
        s1_data = df.iloc[-21:-1]
        s1_high = s1_data['High'].max()
        s1_low = s1_data['Low'].min()
        
        # S2 (55-day)
        s2_data = df.iloc[-56:-1]
        s2_high = s2_data['High'].max()
        s2_low = s2_data['Low'].min()
        
        s1_raw_signal = "LONG" if current_price > s1_high else ("SHORT" if current_price < s1_low else "NONE")
        s2_signal = "LONG" if current_price > s2_high else ("SHORT" if current_price < s2_low else "NONE")
        
        # S1 Skip Rule
        is_skip = False
        if s1_raw_signal != "NONE":
            is_skip = was_last_s1_winner(df)
            
        s1_final_signal = s1_raw_signal
        if is_skip and s1_raw_signal != "NONE":
            s1_final_signal = f"SKIP({s1_raw_signal})"
            
        return {
            "ticker": ticker_name,
            "date": df.index[-1].strftime('%Y-%m-%d'),
            "current_price": current_price,
            "atr": current_atr,
            "s1_high": s1_high,
            "s1_low": s1_low,
            "s2_high": s2_high,
            "s2_low": s2_low,
            "s1_signal": s1_final_signal,
            "s2_signal": s2_signal
        }
    except Exception as e:
        return {"error": str(e)}

def main():
    if len(sys.argv) < 2:
        print("Usage: python turtle_signal.py TICKER1,TICKER2,...")
        return

    tickers = [t.strip() for t in sys.argv[1].split(',')]
    
    results = []
    for ticker in tickers:
        signal = get_turtle_signals(ticker)
        if signal:
            results.append(signal)
    
    if not results:
        print("No data found for the provided tickers.")
        return

    # Updated header with 20d and 55d
    header = f"{'Ticker':<10} | {'Date':<10} | {'Price':<10} | {'ATR (N)':<10} | {'S1 (20d)':<12} | {'S1 Levels (H/L)':<20} | {'S2 (55d)':<12} | {'S2 Levels (H/L)':<20}"
    print(header)
    print("-" * len(header))
    
    for r in results:
        if "error" in r:
            print(f"{r.get('ticker', 'UNKNOWN'):<10} | Error: {r['error']}")
            continue
            
        s1_levels = f"{r['s1_high']:.2f}/{r['s1_low']:.2f}"
        s2_levels = f"{r['s2_high']:.2f}/{r['s2_low']:.2f}"
        
        print(f"{r['ticker']:<10} | {r['date']:<10} | {r['current_price']:<10.2f} | {r['atr']:<10.2f} | {r['s1_signal']:<12} | {s1_levels:<20} | {r['s2_signal']:<12} | {s2_levels:<20}")

if __name__ == "__main__":
    main()
