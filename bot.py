
import requests
import time
from datetime import datetime

BOT_TOKEN = __import__('os').environ.get('BOT_TOKEN')
CHAT_ID = __import__('os').environ.get('CHAT_ID')

SYMBOLS = ['BTCUSDT', 'ETHUSDT']
SYMBOL_NAMES = {'BTCUSDT': 'BTCUSD', 'ETHUSDT': 'ETHUSD'}

def send_tg(msg):
    if not BOT_TOKEN or not CHAT_ID:
        print("Missing BOT_TOKEN/CHAT_ID")
        return
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"TG Error: {e}")

def get_candles_binance(symbol, interval, limit=200):
    """Binance free API - no key needed"""
    try:
        url = "https://api.binance.com/api/v3/klines"
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if not isinstance(data, list):
            print(f"Binance error for {symbol} {interval}: {data}")
            return []
        candles = []
        for k in data:
            candles.append({
                "time": int(k[0]/1000),
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4])
            })
        return candles
    except Exception as e:
        print(f"Binance fetch failed {symbol} {interval}: {e}")
        return []

def is_bullish_ob(c): return c["close"] > c["open"]
def is_bearish_ob(c): return c["close"] < c["open"]

def check_smc():
    print(f"Checking at {datetime.utcnow()}")
    
    # HTF levels - simple Daily/Weekly high/low as order blocks
    htf_levels = []
    for sym in SYMBOLS:
        daily = get_candles_binance(sym, "1d", 10)
        weekly = get_candles_binance(sym, "1w", 10)
        if daily:
            htf_levels.append(f"{sym} D High {daily[-1]['high']}")
            htf_levels.append(f"{sym} D Low {daily[-1]['low']}")
        if weekly:
            htf_levels.append(f"{sym} W High {weekly[-1]['high']}")
        time.sleep(0.3)
    
    print(f"Loaded {len(htf_levels)} HTF levels")
    
    signals_found = 0
    for sym in SYMBOLS:
        c_4h = get_candles_binance(sym, "4h", 100)
        c_15m = get_candles_binance(sym, "15m", 100)
        
        if not c_4h or not c_15m:
            print(f"{SYMBOL_NAMES[sym]} | No data | Skipping")
            continue
        
        last_price = c_15m[-1]["close"]
        
        # Simple sweep detection - 4h high/low broken
        recent_high = max([c["high"] for c in c_4h[-10:-1]])
        recent_low = min([c["low"] for c in c_4h[-10:-1]])
        sweep_up = last_price > recent_high
        sweep_down = last_price < recent_low
        
        # MSS - market structure shift on 15m
        highs_15 = [c["high"] for c in c_15m[-20:]]
        lows_15 = [c["low"] for c in c_15m[-20:]]
        mss_bull = last_price > max(highs_15[:-1])
        mss_bear = last_price < min(lows_15[:-1])
        
        # FVG check - last 3 candles
        fvg_bull = False
        fvg_bear = False
        if len(c_15m) >= 3:
            c1, c2, c3 = c_15m[-3], c_15m[-2], c_15m[-1]
            if c1["high"] < c3["low"]:
                fvg_bull = True
            if c1["low"] > c3["high"]:
                fvg_bear = True
        
        tap_status = f"SweepUp:{sweep_up} SweepDown:{sweep_down}"
        
        print(f"{SYMBOL_NAMES[sym]} | {tap_status} | MSS B:{mss_bull} S:{mss_bear} FVG B:{fvg_bull} S:{fvg_bear} | Price: {last_price}")
        
        # Signal logic
        if sweep_down and mss_bull and fvg_bull:
            msg = f"🟢 *BUY {SYMBOL_NAMES[sym]}*\nPrice: {last_price}\nSweep: Low Sweep + MSS Bull + FVG\nTime: {datetime.utcnow()} UTC"
            send_tg(msg)
            signals_found += 1
            print(f"SIGNAL BUY {sym}")
        elif sweep_up and mss_bear and fvg_bear:
            msg = f"🔴 *SELL {SYMBOL_NAMES[sym]}*\nPrice: {last_price}\nSweep: High Sweep + MSS Bear + FVG\nTime: {datetime.utcnow()} UTC"
            send_tg(msg)
            signals_found += 1
            print(f"SIGNAL SELL {sym}")
    
    if signals_found == 0:
        print("No signal - normal, market has no setup now")
    
    print("Done - Bot OK - Using Binance Free API")

if __name__ == "__main__":
    check_smc()


    
            
    
    
        
        
