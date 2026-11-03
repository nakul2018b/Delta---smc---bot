
import requests, time, pandas as pd
from datetime import datetime
import os

BASE_URL = "https://api.india.delta.exchange"
TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN", "TOMAR_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("CHAT_ID", "TOMAR_CHAT_ID")
COINS = ["BTCUSD", "ETHUSD"]

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"Telegram error: {e}")

def get_candles(symbol, resolution, days):
    url = f"{BASE_URL}/v2/chart/history"
    params = {"symbol": symbol, "resolution": resolution, "start": int(time.time())-86400*days, "end": int(time.time())}
    r = requests.get(url, params=params, timeout=15)
    df = pd.DataFrame(r.json()['result'])
    for c in ['open','high','low','close']: df[c]=df[c].astype(float)
    return df

def get_all_levels(df_daily, df_weekly, df_4h):
    levels = []
    def extract(df, tf_name):
        for i in range(2, len(df)-2):
            body = abs(df.iloc[i]['close'] - df.iloc[i]['open'])
            wick_up = df.iloc[i]['high'] - max(df.iloc[i]['close'], df.iloc[i]['open'])
            wick_down = min(df.iloc[i]['close'], df.iloc[i]['open']) - df.iloc[i]['low']
            if df.iloc[i]['close'] > df.iloc[i]['open'] and df.iloc[i+1]['close'] < df.iloc[i]['open']:
                levels.append({"type": "BEARISH_OB", "tf": tf_name, "high": df.iloc[i]['high'], "low": df.iloc[i]['low']})
            if df.iloc[i]['close'] < df.iloc[i]['open'] and df.iloc[i+1]['close'] > df.iloc[i]['open']:
                levels.append({"type": "BULLISH_OB", "tf": tf_name, "high": df.iloc[i]['high'], "low": df.iloc[i]['low']})
            if wick_up > body*2:
                levels.append({"type": "BEARISH_REJECTION", "tf": tf_name, "high": df.iloc[i]['high'], "low": max(df.iloc[i]['open'], df.iloc[i]['close'])})
            if wick_down > body*2:
                levels.append({"type": "BULLISH_REJECTION", "tf": tf_name, "high": min(df.iloc[i]['open'], df.iloc[i]['close']), "low": df.iloc[i]['low']})
    extract(df_daily, "DAILY")
    extract(df_weekly, "WEEKLY")
    extract(df_4h, "4H")
    if len(df_4h)>0:
        levels.append({"type": "BEARISH_OB", "tf": "SWING_HIGH", "high": df_4h['high'].max(), "low": df_4h['high'].max()*0.998})
        levels.append({"type": "BULLISH_OB", "tf": "SWING_LOW", "high": df_4h['low'].min()*1.002, "low": df_4h['low'].min()})
    return levels[-15:]

def check_tap_and_sweep(levels, df_4h):
    last_4h = df_4h.iloc[-1]
    for lvl in levels:
        is_tap = (last_4h['low'] <= lvl['high'] and last_4h['high'] >= lvl['low'])
        if is_tap:
            if lvl['type'].startswith("BEARISH"):
                sweep = last_4h['high'] > lvl['high'] and last_4h['close'] < lvl['high']
                if sweep: return True, lvl, "HIGH_SWEEP"
            else:
                sweep = last_4h['low'] < lvl['low'] and last_4h['close'] > lvl['low']
                if sweep: return True, lvl, "LOW_SWEEP"
    return False, None, None

def check_mss_fvg(df_15m):
    recent_high = df_15m.tail(20)['high'].max()
    recent_low = df_15m.tail(20)['low'].min()
    close = df_15m.iloc[-1]['close']
    mss_bull = close > recent_high
    mss_bear = close < recent_low
    fvg_bull = any(df_15m.iloc[i-1]['high'] < df_15m.iloc[i+1]['low'] for i in range(1,len(df_15m)-1))
    fvg_bear = any(df_15m.iloc[i-1]['low'] > df_15m.iloc[i+1]['high'] for i in range(1,len(df_15m)-1))
    return mss_bull, mss_bear, fvg_bull, fvg_bear

print("Final SMC Bot Started")
send_telegram("✅ *Final SMC Bot Chalu!*\nDaily/Weekly/4H OB + Rejection Block + Swing Tap -> 4H Sweep -> 15m MSS -> FVG+OB\nMode: Notification Only")

while True:
    for coin in COINS:
        try:
            df_4h = get_candles(coin, "4h", 40)
            df_15m = get_candles(coin, "15m", 5)
            df_daily = get_candles(coin, "1d", 100)
            df_weekly = get_candles(coin, "1w", 200)
            levels = get_all_levels(df_daily, df_weekly, df_4h)
            swept, lvl, sweep_type = check_tap_and_sweep(levels, df_4h)
            mss_bull, mss_bear, fvg_bull, fvg_bear = check_mss_fvg(df_15m)
            price = df_15m.iloc[-1]['close']
            print(f"{coin} | Sweep:{swept} {sweep_type} | MSS B:{mss_bull} S:{mss_bear}")
            if swept and sweep_type=="HIGH_SWEEP" and mss_bear and fvg_bear:
                send_telegram(f"🔴 *SELL - {coin}*\n\n✅ Tap: {lvl['tf']} {lvl['type']}\n✅ Level: {lvl['high']:.2f}\n✅ 4H High Sweep Done\n✅ 15m Bearish MSS\n✅ FVG+OB Valid\n\nPrice: {price}")
            if swept and sweep_type=="LOW_SWEEP" and mss_bull and fvg_bull:
                send_telegram(f"🟢 *BUY - {coin}*\n\n✅ Tap: {lvl['tf']} {lvl['type']}\n✅ Level: {lvl['low']:.2f}\n✅ 4H Low Sweep Done\n✅ 15m Bullish MSS\n✅ FVG+OB Valid\n\nPrice: {price}")
        except Exception as e:
            print(f"Error {coin}: {e}")
    time.sleep(900)
