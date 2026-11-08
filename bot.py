import requests, os, time, json
from datetime import datetime, timedelta

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

def get_klines(sym, interval="1h", limit=100):
    try:
        data = requests.get(f"https://api.binance.com/api/v3/klines?symbol={sym}&interval={interval}&limit={limit}", timeout=10).json()
        closes=[float(c[4]) for c in data]
        vols=[float(c[5]) for c in data]
        return closes, vols
    except: return None,None

def calc_rsi(c,p=14):
    if len(c)<p+1: return 50
    g=[max(c[i]-c[i-1],0) for i in range(1,len(c))]
    l=[max(c[i-1]-c[i],0) for i in range(1,len(c))]
    ag=sum(g[-p:])/p; al=sum(l[-p:])/p
    if al==0: return 70
    return 100 - (100/(1+ag/al))

def calc_ema(c,p):
    k=2/(p+1); ema=c[0]
    for pr in c[1:]: ema=pr*k+ema*(1-k)
    return ema

def calc_macd(c):
    return calc_ema(c,12) - calc_ema(c,26)

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
            # TP beda untuk scalping
            tp1_persen = 1.02 if tipe=='SCALP' else 1.05
            tp2_persen = 1.035 if tipe=='SCALP' else 1.10
            sl_persen = 0.99 if tipe=='SCALP' else 0.95
            
            if now >= entry*tp1_persen and not data.get('tp1'):
                kirim(f"✅ *TP1 KENA {base} [{tipe}]*\nEntry Rp {entry:,.0f} -> Now Rp {now:,.0f}")
                data['tp1']=True
                save(posisi)
                if tipe=='SCALP':
                    del posisi[base]
                    save(posisi)
            if now >= entry*tp2_persen and not data.get('tp2'):
                kirim(f"🏆 *TP2 KENA {base} [{tipe}]* PROFIT!")
                del posisi[base]
                save(posisi)
            if now <= entry*sl_persen and not data.get('sl'):
                kirim(f"⚠️ *SL {base} [{tipe}]*")
                del posisi[base]
                save(posisi)
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
            if vol_idr < 1000000000: continue # VOL MIN 1M TETAP
            
            closes_1h, vols_1h = get_klines(f"{base}USDT","1h",100)
            if closes_1h is None: continue
            rsi=calc_rsi(closes_1h)
            ema9=calc_ema(closes_1h,9)
            ema21=calc_ema(closes_1h,21)
            ema50=calc_ema(closes_1h,50)
            macd=calc_macd(closes_1h)
            price_1h=closes_1h[-1]
            vol_spike_1h=vols_1h[-1]/(sum(vols_1h[-20:])/20)
            
            # FILTER LAMA KAMU TETAP - TIDAK DIKURANGI
            trend_ok = (ema9>ema21) and (price_1h>ema50) and (45<rsi<72) and (macd>0) and (vol_spike_1h>1.2)
            
            # TAMBAHAN MOMENTUM SCALPING - CEK 5 MENIT
            closes_5m, vols_5m = get_klines(f"{base}USDT","5m",50)
            momentum_scalp=False
            if closes_5m:
                # Momentum: 3 candle terakhir naik terus + volume meledak di 5m
                naik_3_candle = closes_5m[-1]>closes_5m[-2]>closes_5m[-3]
                vol_spike_5m = vols_5m[-1]/(sum(vols_5m[-20:])/20) if sum(vols_5m[-20:])>0 else 1
                momentum_scalp = naik_3_candle and vol_spike_5m > 2.0
            
            if trend_ok:
                entry_idr=float(d['last'])
                tipe = "SCALP MOMENTUM" if momentum_scalp else "SWING"
                # Scalping dapat bonus score kalau momentum ada
                score = vol_spike_1h*20 + rsi + (30 if momentum_scalp else 0) + (50 if base in trending else 0)
                hasil.append({
                    'base':base,'entry_idr':entry_idr,'tipe':tipe,
                    'rsi':round(rsi,1),'macd':round(macd,4),
                    'vol_spike':round(vol_spike_1h,2),'vol_spike_5m': round(vol_spike_5m,2) if closes_5m else 0,
                    'trending': base in trending,
                    'score':score,
                    'tp1': entry_idr*1.02 if momentum_scalp else entry_idr*1.05,
                    'tp2': entry_idr*1.035 if momentum_scalp else entry_idr*1.10,
                    'sl': entry_idr*0.99 if momentum_scalp else entry_idr*0.95,
                })
        except: continue
    return sorted(hasil, key=lambda x:x['score'], reverse=True)[:3], len(tickers), trending

def main():
    kirim("🏆 *BOT LENGKAP + SCALP MOMENTUM AKTIF*\n✅ Filter lama TETAP\n✅ + Deteksi momentum 5M\n✅ SWING TP 5%/10% & SCALP TP 2%/3.5%")
    while True:
        try:
            cek_tp()
            sinyal,total,trending=analisa()
            if sinyal:
                posisi=load()
                for s in sinyal:
                    icon = "⚡" if "SCALP" in s['tipe'] else "🚀"
                    kirim(f"{icon} *{s['tipe']} {s['base']}/IDR*\nRSI:{s['rsi']} MACD:{s['macd']}\nVol 1H:{s['vol_spike']}x Vol 5M:{s['vol_spike_5m']}x\nTrending: {','.join(trending[:3])}\n\nEntry Rp {s['entry_idr']:,.0f}\nTP1 Rp {s['tp1']:,.0f}\nTP2 Rp {s['tp2']:,.0f}\nSL Rp {s['sl']:,.0f}")
                    posisi[s['base']]={'entry_idr':s['entry_idr'],'tipe':'SCALP' if 'SCALP' in s['tipe'] else 'SWING'}
                    save(posisi)
            else:
                kirim(f"⏳ Scan {total} koin | Trending {','.join(trending[:3])} | Belum ada - Filter lengkap + momentum aktif")
            time.sleep(180)
        except Exception as e:
            print(e)
            time.sleep(60)

if __name__=="__main__":
    main()
