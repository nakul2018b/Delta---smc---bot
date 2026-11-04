
import requests
import pandas as pd
from datetime import datetime
import time
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
BASE_URLS = [
    "https://api.india.delta.exchange",
    "https://api.delta.exchange"
]

def send_telegram(msg):
    if not BOT_TOKEN or not CHAT_ID:
        print("BOT_TOKEN/CHAT_ID missing, skipping telegram")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

def get_candles(symbol, resolution, days=10):
    for base in BASE_URLS:
        try:
            url = f"{base}/v2/chart/history"
            params = {
                "symbol": symbol,
                "resolution": resolution,
                "start": int(time.time()) - 86400*days,
                "end": int(time.time())
            }
            r = requests.get(url, params=params, timeout=20)
            # print(f"Trying {base} status {r.status_code}")
            data = r.json()
            # Delta API returns {"success": True, "result": [...]} or direct list
            result = None
            if isinstance(data, dict):
                if 'result' in data:
                    result = data['result']
                elif 'data' in data:
                    result = data['data']
                else:
                    # Sometimes result is inside success
                    print(f"No result key for {symbol} {resolution} from {base}: keys={list(data.keys())[:5]}")
                    continue
            elif isinstance(data, list):
                result = data
            else:
                print(f"Unknown response type for {symbol} {resolution}: {type(data)}")
                continue
            
            if not result:
                print(f"Empty result for {symbol} {resolution} from {base}")
                continue
            
            df = pd.DataFrame(result)
            # Normalize columns
            # Delta returns keys like open, high, low, close, volume, time
            for c in ['open','high','low','close']:
                if c in df.columns:
                    df[c] = pd.to_numeric(df[c], errors='coerce')
            # Drop NaN
            df = df.dropna(subset=['open','high','low','close'])
            if len(df) < 5:
                print(f"Too few candles for {symbol} {resolution}: {len(df)}")
                continue
            return df
        except Exception as e:
            print(f"Candle fetch error {symbol} {resolution} from {base}: {e}")
            continue
    print(f"All bases failed for {symbol} {resolution}")
    return None

def get_daily_weekly_levels():
    levels = []
    for symbol in ["BTCUSD", "ETHUSD"]:
        for tf, days in [("1d", 20), ("1w", 60)]:
            df = get_candles(symbol, tf, days)
            if df is None or len(df) < 5:
                continue
            last = df.iloc[-1]
            levels.append({'symbol': symbol, 'lvl': float(last['high']), 'type': f'{tf.upper()}_OB_HIGH', 'tf': tf})
            levels.append({'symbol': symbol, 'lvl': float(last['low']), 'type': f'{tf.upper()}_OB_LOW', 'tf': tf})
    return levels

def check_tap_and_sweep(levels, df_4h):
    if df_4h is None or len(df_4h) == 0:
        return False, None, None
    last_4h = df_4h.iloc[-1]
    for lvl in levels:
        try:
            is_tap = (last_4h['low'] <= lvl['lvl'] <= last_4h['high'])
            if is_tap:
                if lvl['type'].endswith("HIGH"):
                    sweep = last_4h['high'] > lvl['lvl']
                    if sweep:
                        return True, lvl, "HIGH_SWEEP"
                else:
                    sweep = last_4h['low'] < lvl['lvl']
                    if sweep:
                        return True, lvl, "LOW_SWEEP"
        except Exception as e:
            continue
    return False, None, None

def check_mss_fvg(df_15m):
    if df_15m is None or len(df_15m) < 25:
        return False, False, False
    recent_high = df_15m.tail(20)['high'].max()
    recent_low = df_15m.tail(20)['low'].min()
    close = df_15m.iloc[-1]['close']
    mss_bull = close > recent_high
    mss_bear = close < recent_low
    fvg = False
    if len(df_15m) >= 3:
        c1 = df_15m.iloc[-3]
        c3 = df_15m.iloc[-1]
        if c1['high'] < c3['low'] or c1['low'] > c3['high']:
            fvg = True
    return mss_bull, mss_bear, fvg

def main():
    print(f"Checking at {datetime.now()}")
    all_levels = get_daily_weekly_levels()
    print(f"Loaded {len(all_levels)} HTF levels: {[l['type'] for l in all_levels[:4]]}")
    
    for coin in ["BTCUSD", "ETHUSD"]:
        df_4h = get_candles(coin, "4h", 10)
        df_15m = get_candles(coin, "15m", 2)
        
        if df_4h is None or df_15m is None:
            print(f"{coin}: Data not available, skipping")
            continue
        
        coin_levels = [l for l in all_levels if l['symbol'] == coin]
        is_tap_sweep, lvl, sweep_type = check_tap_and_sweep(coin_levels, df_4h)
        mss_bull, mss_bear, fvg = check_mss_fvg(df_15m)
        
        price = float(df_15m.iloc[-1]['close'])
        print(f"{coin} | Tap/Sweep: {is_tap_sweep} {sweep_type} Lvl: {lvl['type'] if lvl else None} | MSS B:{mss_bull} S:{mss_bear} FVG:{fvg} | Price: {price}")
        
        if is_tap_sweep and fvg:
            if mss_bull and lvl and "LOW" in lvl['type']:
                msg = f"🟢 BUY SIGNAL - {coin}\nHTF: {lvl['type']} {lvl['tf']}\nSweep: {sweep_type}\nPrice: {price}\n15m: MSS Bull + FVG\nTime: {datetime.now()}"
                send_telegram(msg)
                print(f"BUY Alert sent for {coin}")
            elif mss_bear and lvl and "HIGH" in lvl['type']:
                msg = f"🔴 SELL SIGNAL - {coin}\nHTF: {lvl['type']} {lvl['tf']}\nSweep: {sweep_type}\nPrice: {price}\n15m: MSS Bear + FVG\nTime: {datetime.now()}"
                send_telegram(msg)
                print(f"SELL Alert sent for {coin}")
    
    print("Done")

if __name__ == "__main__":
    main()


    

    
