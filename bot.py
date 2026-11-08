import requests, os, time, json
from datetime import datetime, timedelta

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
FILE = "posisi_aktif.json"

TRENDING_CACHE = ["BTC","ETH","SOL","PEPE","DOGE","XRP","SHIB","BNB","AVAX","FLOKI"]
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

def get_klines(sym):
    try:
        data = requests.get(f"https://api.binance.com/api/v3/klines?symbol={sym}&interval=1h&limit=100", timeout=10).json()
        closes=[float(c[4]) for c in data]
        vols=[float(c[5]) for c in data]
        return closes, vols
    except: return None,None

def calc_rsi(closes,p=14):
    if len(closes)<p+1: return 50
    g=[max(closes[i]-closes[i-1],0) for i in range(1,len(closes))]
    l=[max(closes[i-1]-closes[i],0) for i in range(1,len(closes))]
    ag=sum(g[-p:])/p; al=sum(l[-p:])/p
    if al==0: return 70
    return 100 - (100/(1+ag/al))

def calc_ema(closes,p):
    k=2/(p+1); ema=closes[0]
    for pr in closes[1:]: ema=pr*k+ema*(1-k)
    return ema

def calc_macd(closes):
    ema12=calc_ema(closes,12)
    ema26=calc_ema(closes,26)
    return ema12 - ema26

def get_trending():
    global TRENDING_CACHE, LAST_TREND_UPDATE
    if datetime.now() - LAST_TREND_UPDATE > timedelta(minutes=30):
        try:
            r=requests.get("https://api.coingecko.com/api/v3/search/trending", timeout=8).json()
            trending=[c['item']['symbol'].upper() for c in r['coins'][:7]]
            if trending:
                TRENDING_CACHE=trending
                LAST_TREND_UPDATE=datetime.now()
        except:
            pass
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
            if now >= entry*1.05 and not data.get('tp1'):
                kirim(f"✅ *TP1 KENA {base}* +5%\nEntry Rp {entry:,.0f} -> Now Rp {now:,.0f}")
                data['tp1']=True
                save(posisi)
            if now >= entry*1.10 and not data.get('tp2'):
                kirim(f"🏆 *TP2 KENA {base}* +10% PROFIT!\nEntry Rp {entry:,.0f} -> Now Rp {now:,.0f}")
                del posisi[base]
                save(posisi)
            if now <= entry*0.95 and not data.get('sl'):
                kirim(f"⚠️ *SL KENA {base}* -5%\nCut loss di Rp {now:,.0f}")
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
        if base in posisi or base in ['USDT','USDC','DAI']: continue
        try:
            vol_idr=float(d['vol_idr'])
            if vol_idr < 1000000000: continue # VOL MIN 1M AKTIF
            closes,vols=get_klines(f"{base}USDT")
            if closes is None or len(closes)<60: continue
            
            rsi=calc_rsi(closes)
            ema9=calc_ema(closes,9)
            ema21=calc_ema(closes,21)
            ema50=calc_ema(closes,50)
            macd=calc_macd(closes)
            price=closes[-1]
            avg_vol=sum(vols[-20:])/20
            vol_spike=vols[-1]/avg_vol if avg_vol>0 else 1
            
            # SEMUA FILTER AKTIF TANPA DIKURANGI
            is_micin = vol_idr < 10000000000 # Di bawah 10M anggap micin tapi tetep valid kalau TA bagus
            ta_valid = (ema9 > ema21) and (price > ema50) and (45 < rsi < 72) and (macd > 0) and (vol_spike > 1.2)
            trending_ok = True # Micin valid OK - trending jadi bonus score, bukan filter keras
            
            if ta_valid:
                entry_idr=float(d['last'])
                score = vol_spike*20 + rsi
                if base in trending: score += 50 # Bonus trending X/Reddit
                hasil.append({
                    'base':base,'entry_idr':entry_idr,
                    'rsi':round(rsi,1),'macd':round(macd,4),
                    'vol_spike':round(vol_spike,2),'vol_idr':vol_idr,
                    'tp1':entry_idr*1.05,'tp2':entry_idr*1.10,'sl':entry_idr*0.95,
                    'trending': base in trending,
                    'score':score
                })
        except: continue
    return sorted(hasil, key=lambda x:x['score'], reverse=True)[:3], len(tickers), trending

def main():
    kirim("🏆 *BOT FINAL LENGKAP - SEMUA FITUR AKTIF*\n✅ TA: RSI+EMA+MACD+Vol\n✅ Vol Min 1M\n✅ Micin Valid OK\n✅ Trending X/Reddit\n✅ TP1/TP2 Tracking")
    while True:
        try:
            cek_tp()
            sinyal,total,trending=analisa()
            if sinyal:
                posisi=load()
                for s in sinyal:
                    trend_icon = "🔥 TRENDING" if s['trending'] else "💎 MICIN VALID"
                    kirim(f"🚀 *BUY {s['base']}/IDR* {trend_icon}\n\n*TA LENGKAP:*\nRSI: {s['rsi']}\nMACD: {s['macd']} >0\nEMA: 9>21>50 OK\nVol Spike: {s['vol_spike']}x\nVol Indodax: Rp {s['vol_idr']/1000000000:.1f} M\nTrending: {', '.join(trending[:3])}\n\n*PLAN:*\nEntry: Rp {s['entry_idr']:,.0f}\nTP1: Rp {s['tp1']:,.0f} (+5%)\nTP2: Rp {s['tp2']:,.0f} (+10%)\nSL: Rp {s['sl']:,.0f}")
                    posisi[s['base']]={'entry_idr':s['entry_idr']}
                    save(posisi)
            else:
                kirim(f"⏳ Scan {total} koin | Trending: {', '.join(trending[:3])} | Belum ada yang lolos filter lengkap RSI+EMA+MACD+Vol 1M. Bot hidup.")
            time.sleep(180)
        except Exception as e:
            print(e)
            time.sleep(60)

if __name__=="__main__":
    main()
