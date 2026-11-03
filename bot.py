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

# Run once (for GitHub Actions)
print(f"Checking at {datetime.now()}")
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

print("Done")



    
