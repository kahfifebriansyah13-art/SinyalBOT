import requests, os, time, json
from datetime import datetime, timedelta
from tradingview_ta import TA_Handler, Interval

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
FILE = "posisi_aktif.json"

TRENDING_CACHE = ["BTC","ETH","SOL","PEPE","DOGE"]
LAST_TREND_UPDATE = datetime.now() - timedelta(hours=1)

def kirim(pesan):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": pesan, "parse_mode": "Markdown"}, timeout=15)
    except Exception as e: print(e)

def load():
    try:
        with open(FILE,'r') as f: return json.load(f)
    except: return {}

def save(d):
    with open(FILE,'w') as f: json.dump(d,f)

def get_tickers():
    try: return requests.get("https://indodax.com/api/tickers", timeout=15).json()['tickers']
    except: return {}

def get_tv(symbol):
    try:
        handler = TA_Handler(symbol=symbol, screener="indonesia", exchange="INDODAX", interval=Interval.INTERVAL_1_HOUR)
        a = handler.get_analysis()
        ind = a.indicators
        summ = a.summary
        # 5M untuk momentum scalping
        handler5 = TA_Handler(symbol=symbol, screener="indonesia", exchange="INDODAX", interval=Interval.INTERVAL_5_MINUTES)
        a5 = handler5.get_analysis()
        return ind, summ, a5.indicators
    except:
        return None, None, None

def get_trending():
    global TRENDING_CACHE, LAST_TREND_UPDATE
    if datetime.now() - LAST_TREND_UPDATE > timedelta(minutes=30):
        try:
            r=requests.get("https://api.coingecko.com/api/v3/search/trending", timeout=8).json()
            trending=[x['item']['symbol'].upper() for x in r['coins'][:5]]
            if trending:
                TRENDING_CACHE=trending
                LAST_TREND_UPDATE=datetime.now()
        except: pass
    return TRENDING_CACHE

def cek_tp():
    posisi=load()
    if not posisi: return
    tickers=get_tickers()
    for base,data in list(posisi.items()):
        try:
            pair=f"{base.lower()}_idr"
            if pair not in tickers: continue
            now=float(tickers[pair]['last'])
            entry=data['entry_idr']
            tipe=data.get('tipe','SWING')
            tp1_p = 1.02 if 'SCALP' in tipe else 1.05
            tp2_p = 1.035 if 'SCALP' in tipe else 1.10
            sl_p = 0.99 if 'SCALP' in tipe else 0.95
            if now >= entry*tp1_p and not data.get('tp1'):
                kirim(f"✅ *TP1 KENA {base} [{tipe}]* +{'2%' if 'SCALP' in tipe else '5%'}\nRp {entry:,.0f} -> Rp {now:,.0f}")
                data['tp1']=True; save(posisi)
                if 'SCALP' in tipe: del posisi[base]; save(posisi)
            if now >= entry*tp2_p:
                kirim(f"🏆 *TP2 KENA {base} [{tipe}]* PROFIT!")
                del posisi[base]; save(posisi)
            if now <= entry*sl_p:
                kirim(f"⚠️ *SL {base} [{tipe}]*"); del posisi[base]; save(posisi)
        except: continue

def analisa():
    tickers=get_tickers()
    trending=get_trending()
    if not tickers: return [],0,trending
    posisi=load()
    hasil=[]
    for pair,d in tickers.items():
        if not pair.endswith('_idr'): continue
        base=pair.split('_')[0].upper()
        if base in posisi or base in ['USDT','USDC']: continue
        try:
            vol_idr=float(d['vol_idr'])
            if vol_idr < 1000000000: continue # VOL MIN 1M SESUAI KEINGINAN KAMU
            
            tv_symbol=f"{base}IDR"
            ind, summ, ind5 = get_tv(tv_symbol)
            if not ind: continue
            
            rsi = ind.get('RSI',50)
            ema9 = ind.get('EMA9',0)
            ema20 = ind.get('EMA20',0)
            ema50 = ind.get('EMA50',0)
            macd = ind.get('MACD.macd',0)
            macd_signal = ind.get('MACD.signal',0)
            rekom = summ.get('RECOMMENDATION','NEUTRAL')
            
            # Momentum 5M dari TradingView
            rsi5 = ind5.get('RSI',50) if ind5 else 50
            momentum_scalp = rsi5 > 65 and ind5.get('EMA9',0) > ind5.get('EMA20',0) if ind5 else False
            
            # FILTER MEDIUM VERSI TRADINGVIEW - SESUAI FORMAT KAMU
            trend_ok = (ema9 > ema20) and (35 < rsi < 78) and (macd > macd_signal) and ("BUY" in rekom)
            
            if trend_ok:
                entry_idr=float(d['last'])
                tipe = "SCALP MOMENTUM TV" if momentum_scalp else "SWING TV"
                score = rsi + (30 if momentum_scalp else 0) + (50 if base in trending else 0)
                hasil.append({
                    'base':base,'entry_idr':entry_idr,'tipe':tipe,
                    'rsi':round(rsi,1),'macd':round(macd,4),
                    'ema9':ema9,'ema20':ema20,'rekom':rekom,
                    'rsi5':round(rsi5,1) if ind5 else 0,
                    'trending': base in trending,
                    'vol_idr':vol_idr,
                    'score':score,
                    'tp1': entry_idr*1.02 if momentum_scalp else entry_idr*1.05,
                    'tp2': entry_idr*1.035 if momentum_scalp else entry_idr*1.10,
                    'sl': entry_idr*0.99 if momentum_scalp else entry_idr*0.95,
                })
            time.sleep(0.5) # Biar gak kena limit TradingView
        except Exception as e:
            print(f"Skip {base}: {e}")
            continue
    return sorted(hasil, key=lambda x:x['score'], reverse=True)[:3], len(tickers), trending

def main():
    kirim("📊 *BOT TRADINGVIEW FINAL AKTIF*\n✅ Data: TradingView INDODAX\n✅ RSI+EMA+MACD dari TV\n✅ Vol Min 1M\n✅ Micin Valid OK + Trending\n✅ Scalp Momentum TV + TP Tracking")
    while True:
        try:
            cek_tp()
            sinyal,total,trending=analisa()
            if sinyal:
                posisi=load()
                for s in sinyal:
                    icon = "⚡" if "SCALP" in s['tipe'] else "🚀"
                    kirim(f"{icon} *{s['tipe']} {s['base']}/IDR* { '🔥 TRENDING' if s['trending'] else '💎 MICIN VALID'}\n\n*DATA TRADINGVIEW:*\nRSI 1H: {s['rsi']} | RSI 5M: {s['rsi5']}\nEMA9: {s['ema9']:.0f} > EMA20: {s['ema20']:.0f}\nMACD: {s['macd']} | Rekom TV: {s['rekom']}\nVol: Rp {s['vol_idr']/1000000000:.1f} M\nTrending Global: {','.join(trending[:3])}\n\n*PLAN:*\nEntry: Rp {s['entry_idr']:,.0f}\nTP1: Rp {s['tp1']:,.0f}\nTP2: Rp {s['tp2']:,.0f}\nSL: Rp {s['sl']:,.0f}")
                    posisi[s['base']]={'entry_idr':s['entry_idr'],'tipe':s['tipe']}
                    save(posisi)
            else:
                kirim(f"⏳ Scan {total} koin via TradingView | Trending: {','.join(trending[:3])} | Filter Medium TV aktif")
            time.sleep(180)
        except Exception as e:
            print(e); time.sleep(60)

if __name__=="__main__":
    main()
