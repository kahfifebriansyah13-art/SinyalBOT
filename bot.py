def format_tmg(s):
    if s['score'] >= 92 and s['is_trending']:
        prioritas = "🔥 PRIORITAS 1 - ENTRY WAJIB (Trending + Vol Besar)"
    elif s['score'] >= 85:
        prioritas = "⭐ PRIORITAS 2 - BOLEH ENTRY (Bagus)"
    elif s['score'] >= 75:
        prioritas = "⚠️ PRIORITAS 3 - WATCHLIST (Ragu)"
    else:
        prioritas = "❌ SKIP"
    
    trending_icon = "🌐 TRENDING SOSMED: YES 🔥🔥" if s['is_trending'] else "🌐 Trending: -"
    
    return f"""┏━━━━━━━━━━━━━━━━━━┓
┃ {s['base']}/IDR - AKAN TRENDING ┃
┗━━━━━━━━━━━━━━━━━━┛

💎 AKAN TRENDING 💎 LOCAL
{trending_icon}

┌─ 🕯️ DAILY CANDLE ─┐
│ 🟢 Open: Rp {s['open']:,.0f} | Close: Rp {s['entry']:,.0f}
│ 📊 RSI: {s['rsi']:.1f} | Pos: {s['pos']:.0f}% dari Low-High
│ ⭐ Score: {s['score']}/100
│ {prioritas}
└──────────────────┘

┌─ 📊 MARKET DATA ─┐
│ 📈 Naik: +{s['naik']:.2f}% dari Low
│ 💧 Low: Rp {s['low']:,.0f} | High: Rp {s['high']:,.0f}
│ 💰 Vol: Rp {s['vol']/1e6:.2f} M
└──────────────────┘

┌─ 🎯 TRADING PLAN ─┐
│ 🟢 ENTRY: Rp {s['entry']:,.0f}
│ 🎯 TP1: Rp {s['tp1']:,.0f} (+5%)
│ 🏆 TP2: Rp {s['tp2']:,.0f} (+10%)
│ 🔴 SL: Rp {s['sl']:,.0f} (-5%)
└──────────────────┘

⚡ {prioritas}
"""

def analisa_ranking():
    tickers = get_tickers()
    if not tickers: return []
    trending_list = get_coingecko_trending()
    posisi = load_json(FILE, {})
    cooldown = load_json(COOLDOWN_FILE, {})
    now = datetime.now()
    for k in list(cooldown.keys()):
        try:
            t = datetime.fromisoformat(cooldown[k])
            if now - t > timedelta(hours=1): del cooldown[k]
        except: del cooldown[k]
    save_json(COOLDOWN_FILE, cooldown)
    
    scored = []
    for pair,d in tickers.items():
        if not pair.endswith('_idr'): continue
        base = pair.split('_')[0].upper()
        if base in posisi or base in ['USDT','USDC','DAI','IDR']: continue
        if base in cooldown: continue
        try:
            last = float(d['last']); low = float(d['low']); high = float(d['high'])
            vol = float(d['vol_idr']); open_p = float(d.get('open', last))
            if vol < 100_000_000 or low==0: continue
            naik_low = (last-low)/low*100
            pos_h = (last-low)/(high-low)*100 if high!=low else 50
            if not (1.0 <= naik_low <= 10.0): continue
            if not (20 <= pos_h <= 65): continue
            if last < open_p: continue
            
            is_trending = base in trending_list
            
            # SCORING BARU - TIDAK LAGI 100 SEMUA
            score = 50 # base score
            if vol >= 500_000_000: score += 20
            elif vol >= 200_000_000: score += 12
            elif vol >= 100_000_000: score += 5
            
            if 2 <= naik_low <= 4: score += 15 # ideal
            elif 1 <= naik_low <= 2: score += 8
            elif 4 < naik_low <= 6: score += 10
            else: score += 3
            
            if 30 <= pos_h <= 45: score += 15 # paling bawah
            elif 25 <= pos_h <= 55: score += 8
            else: score += 2
            
            if is_trending: score += 12
            
            if score >= 70:
                scored.append({'base':base,'entry':last,'low':low,'high':high,'open':open_p,'tp1':last*1.05,'tp2':last*1.10,'sl':last*0.95,'naik':naik_low,'vol':vol,'pos':pos_h,'rsi':55.0,'score':min(score,100),'is_trending':is_trending})
        except: continue
    
    scored = sorted(scored, key=lambda x: x['score'], reverse=True)
    print(f"FILTER: {len(scored)} lolos", flush=True)
    # HANYA KIRIM TOP 1 SCORE TERTINGGI
    return scored[:1]
