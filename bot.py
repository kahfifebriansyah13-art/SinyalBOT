import requests, os, time, json
from datetime import datetime, timedelta
from tradingview_ta import TA_Handler, Interval

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
FILE = "posisi_aktif.json"

TRENDING_CACHE = ["BTC","ETH","SOL","PEPE","DOGE"]
LAST_TREND_UPDATE = datetime.now() - timedelta(hours=1)

def kirim(pesan):
    try: requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": pesan, "parse_mode": "Markdown"}, timeout=15)
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

def get_trending_global():
    global TRENDING_CACHE, LAST_TREND_UPDATE
    if datetime.now() - LAST_TREND_UPDATE > timedelta(minutes=30):
        try:
            r=requests.get("https://api.coingecko.com/api/v3/search/trending", timeout=8).json()
            TRENDING_CACHE=[x['item']['symbol'].upper() for x in r['coins'][:5]]
            LAST_TREND_UPDATE=datetime.now()
        except: pass
    return TRENDING_CACHE

def get_indodax_will_trending(tickers):
    calon = []
    for pair,d in tickers.items():
        if not pair.endswith('_idr'): continue
        try:
            last=float(d['last']); low=float(d['low']); high=float(d['high'])
            vol=float(d['vol_idr'])
            if vol < 500000000: continue # VOL 500JT SESUAI REQUEST
            naik_from_low = ((last-low)/low*100) if low>0 else 0
            dekat_high = (last/high*100) if high>0 else 0
            if naik_from_low > 4 and dekat_high > 80:
                calon.append((pair.split('_')[0].upper(), naik_from_low, vol))
        except: continue
    calon = sorted(calon, key=lambda x: x[1]+x[2]/1e9, reverse=True)[:5]
    return [c[0] for c in calon], calon

def cek_tp():
    posisi=load()
    if not posisi: return
    tickers=get_tickers()
    for base,data in list(posisi.items()):
        try:
            now=float(tickers[f"{base.lower()}_idr"]['last'])
            entry=data['entry_idr']; tipe=data.get('tipe','SWING')
            tp1 = 1.02 if 'SCALP' in tipe else 1.04
            tp2 = 1.035 if 'SCALP' in tipe else 1.08
            if now >= entry*tp1 and not data.get('tp1'):
                kirim(f"✅ *TP1 KENA {base} [{tipe}]*\nRp {entry:,.0f} -> Rp {now:,.0f}")
                data['tp1']=True; save(posisi)
                if 'SCALP' in tipe: del posisi[base]; save(posisi)
            if now >= entry*tp2:
                kirim(f"🏆 *TP2 {base} [{tipe}] PROFIT!*"); del posisi[base]; save(posisi)
            if now <= entry*0.97:
                kirim(f"⚠️ *SL {base} [{tipe}]*"); del posisi[base]; save(posisi)
        except: continue

def analisa():
    tickers=get_tickers()
    if not tickers: return [],0,[],[]
    trending_global=get_trending_global()
    will_trending, detail_will = get_indodax_will_trending(tickers)
    
    posisi=load()
    hasil=[]
    for pair,d in tickers.items():
        if not pair.endswith('_idr'): continue
        base=pair.split('_')[0].upper()
        if base in posisi or base in ['USDT','USDC']: continue
        try:
            vol=float(d['vol_idr'])
            if vol < 500000000: continue # VOL 500JT FIX
            tv_symbol=f"{base}IDR"
            ind1h, sum1h = get_tv(tv_symbol, Interval.INTERVAL_1_HOUR)
            ind5m, _ = get_tv(tv_symbol, Interval.INTERVAL_5_MINUTES)
            if not ind1h: continue
            rsi=ind1h.get('RSI',50); ema9=ind1h.get('EMA9',0); ema20=ind1h.get('EMA20',0)
            macd=ind1h.get('MACD.macd',0); sig=ind1h.get('MACD.signal',0)
            rekom=sum1h.get('RECOMMENDATION','NEUTRAL'); rsi5=ind5m.get('RSI',50) if ind5m else 50
            
            is_will_trending = base in will_trending
            is_global_trending = base in trending_global
            longgar = (25 < rsi < 85) and (ema9 > ema20 or macd > sig or "BUY" in rekom or rekom=="NEUTRAL" or is_will_trending)
            momentum = (rsi5 > 60) if ind5m else False
            
            if longgar or is_will_trending:
                entry=float(d['last'])
                tipe = "AKAN TRENDING INDODAX" if is_will_trending else ("SCALP AGRESIF TV" if momentum else "SWING AGRESIF TV")
                score = rsi + (100 if is_will_trending else 0) + (50 if is_global_trending else 0)
                hasil.append({
                    'base':base,'entry':entry,'tipe':tipe,'rsi':round(rsi,1),'rsi5':round(rsi5,1),
                    'rekom':rekom,'vol':vol,'ema9':ema9,'ema20':ema20,'macd':round(macd,4),
                    'will': is_will_trending,'global': is_global_trending,'score':score,
                    'tp1': entry*1.02 if momentum else entry*1.04,
                    'tp2': entry*1.035 if momentum else entry*1.08,'sl': entry*0.97
                })
            time.sleep(0.5)
        except: continue
    
    if not hasil:
        sorted_vol = sorted([(k,v) for k,v in tickers.items() if k.endswith('_idr') and float(v['vol_idr'])>500000000], key=lambda x: float(x[1]['vol_idr']), reverse=True)[:3]
        for pair,v in sorted_vol:
            base=pair.split('_')[0].upper()
            if base in posisi: continue
            last=float(v['last'])
            hasil.append({'base':base,'entry':last,'tipe':'TOP VOL 500JT JAMINAN','rsi':60,'rsi5':60,'rekom':'NEUTRAL','vol':float(v['vol_idr']),'ema9':0,'ema20':0,'macd':0,'will':False,'global':False,'score':0,'tp1':last*1.04,'tp2':last*1.08,'sl':last*0.97})
    return sorted(hasil, key=lambda x:x['score'], reverse=True)[:3], len(tickers), trending_global, detail_will

def main():
    kirim("🔥 *BOT FINAL 500JT + PREDIKSI TRENDING INDODAX AKTIF*\n✅ Vol Min Rp 500jt FIX\n✅ Deteksi AKAN TRENDING INDODAX\n✅ TP1/TP2/SL Tetap Seperti Sekarang")
    while True:
        try:
            cek_tp()
            sinyal,total,trend_global,will_detail=analisa()
            if sinyal:
                posisi=load()
                for s in sinyal:
                    tag = "🚀 *AKAN TRENDING*" if s['will'] else ("🔥 TRENDING GLOBAL" if s['global'] else "💎 VALID")
                    kirim(f"⚡ *{s['tipe']} {s['base']}/IDR* {tag}\nTV RSI:{s['rsi']} 5M:{s['rsi5']} Rekom:{s['rekom']}\nVol Rp {s['vol']/1e9:.2f}M\nAkan Trending: {','.join([f'{x[0]} +{x[1]:.1f}%' for x in will_detail[:3]])}\nGlobal: {','.join(trend_global[:3])}\n\nEntry Rp {s['entry']:,.0f}\nTP1 Rp {s['tp1']:,.0f}\nTP2 Rp {s['tp2']:,.0f}\nSL Rp {s['sl']:,.0f}")
                    posisi[s['base']]={'entry_idr':s['entry'],'tipe':s['tipe']}; save(posisi)
            time.sleep(90)
        except Exception as e:
            print(e); time.sleep(60)

if __name__=="__main__":
    main()
