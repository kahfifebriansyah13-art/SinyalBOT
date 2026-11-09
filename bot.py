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
    except: pass

def load():
    try:
        with open(FILE,'r') as f: return json.load(f)
    except: return {}

def save(d): 
    with open(FILE,'w') as f: json.dump(d,f)

def get_tickers():
    try: return requests.get("https://indodax.com/api/tickers", timeout=15).json()['tickers']
    except: return {}

def get_tv(symbol, interval):
    try:
        h = TA_Handler(symbol=symbol, screener="indonesia", exchange="INDODAX", interval=interval)
        a = h.get_analysis()
        return a.indicators, a.summary
    except: return None, None

def get_trending():
    global TRENDING_CACHE, LAST_TREND_UPDATE
    if datetime.now() - LAST_TREND_UPDATE > timedelta(minutes=30):
        try:
            r=requests.get("https://api.coingecko.com/api/v3/search/trending", timeout=8).json()
            TRENDING_CACHE=[x['item']['symbol'].upper() for x in r['coins'][:5]]
            LAST_TREND_UPDATE=datetime.now()
        except: pass
    return TRENDING_CACHE

def cek_tp():
    posisi=load()
    if not posisi: return
    tickers=get_tickers()
    for base,data in list(posisi.items()):
        try:
            now=float(tickers[f"{base.lower()}_idr"]['last'])
            entry=data['entry_idr']
            tipe=data.get('tipe','SWING')
            tp1 = 1.02 if 'SCALP' in tipe else 1.04
            tp2 = 1.035 if 'SCALP' in tipe else 1.08
            if now >= entry*tp1 and not data.get('tp1'):
                kirim(f"✅ *TP1 KENA {base} [{tipe}]*\nEntry Rp {entry:,.0f} -> Now Rp {now:,.0f}")
                data['tp1']=True; save(posisi)
                if 'SCALP' in tipe: del posisi[base]; save(posisi)
            if now >= entry*tp2:
                kirim(f"🏆 *TP2 KENA {base} [{tipe}]* PROFIT!\nRp {entry:,.0f} -> Rp {now:,.0f}")
                del posisi[base]; save(posisi)
            if now <= entry*0.97:
                kirim(f"⚠️ *SL {base} [{tipe}]*\nRp {entry:,.0f} -> Rp {now:,.0f}")
                del posisi[base]; save(posisi)
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
            vol=float(d['vol_idr'])
            if vol < 200000000: continue
            tv_symbol=f"{base}IDR"
            ind1h, sum1h = get_tv(tv_symbol, Interval.INTERVAL_1_HOUR)
            ind5m, sum5m = get_tv(tv_symbol, Interval.INTERVAL_5_MINUTES)
            if not ind1h: continue
            rsi = ind1h.get('RSI',50)
            ema9 = ind1h.get('EMA9',0)
            ema20 = ind1h.get('EMA20',0)
            macd = ind1h.get('MACD.macd',0)
            macd_sig = ind1h.get('MACD.signal',0)
            rekom = sum1h.get('RECOMMENDATION','NEUTRAL')
            rsi5 = ind5m.get('RSI',50) if ind5m else 50
            longgar = (25 < rsi < 85) and (ema9 > ema20 or macd > macd_sig or "BUY" in rekom or rekom=="NEUTRAL")
            momentum = (rsi5 > 60) if ind5m else False
            if longgar:
                entry=float(d['last'])
                tipe = "SCALP AGRESIF TV" if momentum else "SWING AGRESIF TV"
                hasil.append({
                    'base':base,'entry':entry,'tipe':tipe,
                    'rsi':round(rsi,1),'rsi5':round(rsi5,1),
                    'rekom':rekom,'vol':vol,'ema9':ema9,'ema20':ema20,'macd':round(macd,4),
                    'trending': base in trending,'score': rsi + vol/1e9 + (20 if momentum else 0),
                    'tp1': entry*1.02 if momentum else entry*1.04,
                    'tp2': entry*1.035 if momentum else entry*1.08,
                    'sl': entry*0.97
                })
            time.sleep(0.6)
        except: continue
    if not hasil:
        sorted_vol = sorted([(k,v) for k,v in tickers.items() if k.endswith('_idr') and float(v['vol_idr'])>200000000], key=lambda x: float(x[1]['vol_idr']), reverse=True)[:3]
        for pair,v in sorted_vol:
            base=pair.split('_')[0].upper()
            if base in posisi: continue
            last=float(v['last'])
            hasil.append({'base':base,'entry':last,'tipe':'SWING TOP VOL (JAMINAN)','rsi':60,'rsi5':60,'rekom':'NEUTRAL','vol':float(v['vol_idr']),'ema9':0,'ema20':0,'macd':0,'trending': base in trending,'score':0,'tp1':last*1.04,'tp2':last*1.08,'sl':last*0.97})
    return sorted(hasil, key=lambda x:x['score'], reverse=True)[:3], len(tickers), trending

def main():
    kirim("🔥 *BOT AGRESIF TRADINGVIEW FINAL AKTIF*\n✅ Vol 200jt | RSI 25-85 | EMA/MACD/BUY\n✅ Scalp Momentum 5M | Trending | Micin Valid\n✅ TP1/TP2/SL Notif Tetap Aktif Seperti Sekarang\n✅ Jaminan Sinyal")
    while True:
        try:
            cek_tp()
            sinyal,total,trending=analisa()
            if sinyal:
                posisi=load()
                for s in sinyal:
                    icon="⚡" if "SCALP" in s['tipe'] else "🚀"
                    kirim(f"{icon} *{s['tipe']} {s['base']}/IDR* {'🔥 TRENDING' if s['trending'] else '💎 VALID'}\nTV RSI 1H:{s['rsi']} 5M:{s['rsi5']} Rekom:{s['rekom']}\nEMA9>EMA20:{s['ema9']>s['ema20']} MACD:{s['macd']}\nVol: Rp {s['vol']/1e9:.2f}M | Trend: {','.join(trending[:3])}\n\nEntry Rp {s['entry']:,.0f}\nTP1 Rp {s['tp1']:,.0f}\nTP2 Rp {s['tp2']:,.0f}\nSL Rp {s['sl']:,.0f}")
                    posisi[s['base']]={'entry_idr':s['entry'],'tipe':s['tipe']}
                    save(posisi)
            else:
                kirim(f"⏳ Scan {total} koin via TV | Trending {','.join(trending[:3])}")
            time.sleep(90)
        except Exception as e:
            print(e); time.sleep(60)

if __name__=="__main__":
    main()
