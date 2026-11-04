import requests
import pandas as pd
from datetime import datetime
import time
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

SYMBOLS = ["BTCUSD", "ETHUSD"]
BINANCE_MAP = {"BTCUSD": "BTCUSDT", "ETHUSD": "ETHUSDT"}

TF_MAP_BINANCE = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
    "1W": "1w"
}

def send_telegram(msg):
    if not BOT_TOKEN or not CHAT_ID:
        print("Telegram secrets missing")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
        print(f"Telegram sent: {r.status_code}")
    except Exception as e:
        print(f"Telegram error: {e}")

def get_candles(symbol, tf, limit=100):
    bin_sym = BINANCE_MAP.get(symbol, "BTCUSDT")
    b_tf = TF_MAP_BINANCE.get(tf, "15m")
    url = "https://api.binance.com/api/v3/klines"
    params = {"symbol": bin_sym, "interval": b_tf, "limit": limit}
    try:
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        if not isinstance(data, list) or len(data) == 0:
            print(f"No data for {symbol} {tf}: {str(data)[:200]}")
            return None
        df = pd.DataFrame(data, columns=["open_time","open","high","low","close","volume","close_time","qav","trades","taker_base","taker_quote","ignore"])
        df["open"] = df["open"].astype(float)
        df["high"] = df["high"].astype(float)
        df["low"] = df["low"].astype(float)
        df["close"] = df["close"].astype(float)
        df["volume"] = df["volume"].astype(float)
        return df
    except Exception as e:
        print(f"Error {symbol} {tf}: {e}")
        return None

def find_order_blocks(df):
    if df is None or len(df) < 10:
        return []
    obs = []
    for i in range(2, len(df)-2):
        if df.iloc[i]["close"] > df.iloc[i]["open"] and df.iloc[i+1]["close"] > df.iloc[i]["high"]:
            obs.append({"type":"bullish","low":df.iloc[i]["low"],"high":df.iloc[i]["high"],"idx":i})
        if df.iloc[i]["close"] < df.iloc[i]["open"] and df.iloc[i+1]["close"] < df.iloc[i]["low"]:
            obs.append({"type":"bearish","low":df.iloc[i]["low"],"high":df.iloc[i]["high"],"idx":i})
    return obs[-5:]

def detect_mss(df):
    if df is None or len(df) < 20:
        return {"bull_mss":False,"bear_mss":False}
    highs = df["high"].rolling(5).max()
    lows = df["low"].rolling(5).min()
    last_close = df.iloc[-1]["close"]
    prev_high = highs.iloc[-6:-1].max() if len(highs) > 6 else 0
    prev_low = lows.iloc[-6:-1].min() if len(lows) > 6 else 999999
    bull = last_close > prev_high if prev_high else False
    bear = last_close < prev_low if prev_low else False
    return {"bull_mss":bull,"bear_mss":bear}

def detect_fvg(df):
    if df is None or len(df) < 5:
        return False
    for i in range(1, len(df)-1):
        prev_high = df.iloc[i-1]["high"]
        prev_low = df.iloc[i-1]["low"]
        curr_high = df.iloc[i]["high"]
        curr_low = df.iloc[i]["low"]
        next_low = df.iloc[i+1]["low"]
        next_high = df.iloc[i+1]["high"]
        # bullish FVG: low of next > high of prev
        if next_low > prev_high:
            if abs(i - (len(df)-1)) <= 3:
                return True
        if next_high < prev_low:
            if abs(i - (len(df)-1)) <= 3:
                return True
    return False

def check_htf_levels():
    levels = []
    for sym in SYMBOLS:
        for tf in ["1d","1W","4h"]:
            df = get_candles(sym, tf, 50)
            if df is None:
                continue
            obs = find_order_blocks(df)
            for ob in obs:
                levels.append({"symbol":sym,"tf":tf,"type":ob["type"],"low":ob["low"],"high":ob["high"]})
            time.sleep(0.2)
    return levels

def main():
    print(f"Checking at {datetime.utcnow()} UTC")
    try:
        htf_levels = check_htf_levels()
        print(f"Loaded {len(htf_levels)} HTF levels")
        
        for symbol in SYMBOLS:
            df_15 = get_candles(symbol, "15m", 100)
            df_4h = get_candles(symbol, "4h", 100)
            
            if df_15 is None or df_4h is None:
                print(f"{symbol}: Data not available, skipping")
                continue
            
            price = df_15.iloc[-1]["close"]
            mss = detect_mss(df_15)
            fvg = detect_fvg(df_15)
            
            # Check if price near HTF level
            near_bull = False
            near_bear = False
            lvl_info = "None"
            for lvl in htf_levels:
                if lvl["symbol"] != symbol:
                    continue
                if lvl["low"] <= price <= lvl["high"]*1.005 or abs(price-lvl["low"])/price < 0.005 or abs(price-lvl["high"])/price < 0.005:
                    if lvl["type"] == "bullish":
                        near_bull = True
                        lvl_info = f"{lvl['tf']} Bull OB {lvl['low']:.1f}-{lvl['high']:.1f}"
                    else:
                        near_bear = True
                        lvl_info = f"{lvl['tf']} Bear OB {lvl['low']:.1f}-{lvl['high']:.1f}"
            
            tap = near_bull or near_bear
            sweep = mss["bull_mss"] or mss["bear_mss"]
            
            print(f"{symbol} | Tap/Sweep: {tap} {lvl_info} | MSS B:{mss['bull_mss']} S:{mss['bear_mss']} FVG:{fvg} | Price: {price:.2f}")
            
            signal = None
            if tap and mss["bull_mss"] and fvg and near_bull:
                signal = f"\U0001f7e2 BUY {symbol}\nPrice: {price:.2f}\nLevel: {lvl_info}\nMSS: Bullish + FVG\nTime: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
            elif tap and mss["bear_mss"] and fvg and near_bear:
                signal = f"\U0001f534 SELL {symbol}\nPrice: {price:.2f}\nLevel: {lvl_info}\nMSS: Bearish + FVG\nTime: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
            
            if signal:
                print(f"SIGNAL FOUND: {signal}")
                send_telegram(signal)
            time.sleep(0.5)
        print("Done")
    except Exception as e:
        print(f"Main error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()



    

    

            
    
    
        
        
