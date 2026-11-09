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
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": pesan, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def load():
    try:
        with open(FILE,'r') as f: return json.load(f)
    except: return {}
def save(d):
    with open(FILE,'w') as f: json.dump(d,f)

def get_tickers():
    try: return requests.get("https://indodax.com/api/tickers", timeout=10).json()['tickers']
    except: return {}

def get_tv(symbol, interval):
    try:
        h = TA_Handler(symbol=symbol, screener="indonesia", exchange="INDODAX", interval=interval)
        a = h.get_analysis()
        return a.indicators, a.summary
    except: return None, None

def get_trending_global():
    global TRENDING_CACHE, LAST_TREND_UPDATE
    if datetime.now() - LAST_TREND_UPDATE > timedelta(minutes=20):
        try:
            r=requests.get("https://api.coingecko.com/api/v3/search/trending", timeout=6).json()
            TRENDING_CACHE=[x['item']['symbol'].upper() for x in r['coins'][:10]]
            LAST_TREND_UPDATE=datetime.now()
        except: pass
    return TRENDING_CACHE

def analisa():
    tickers=get_tickers()
    if not tickers: return [],0,[],[]
    trending_global=get_trending_global()
    posisi=load()
    calon_trending=[]
    hasil=[]
    
    for pair,d in tickers.items():
        if not pair.endswith('_idr'): continue
        base=pair.split('_')[0].upper()
        if base in posisi or base in ['USDT','USDC','BTC','ETH']: continue
        try:
            last=float(d['last']); low=float(d['low']); high=float(d['high']); vol=float(d['vol_idr'])
            if vol < 500000000: continue
            if low==0 or high==0: continue
            
            naik_low=(last-low)/low*100
            dekat_high=last/high*100
            
            if naik_low < 3.0 or dekat_high < 75:
                continue

            tv_symbol=f"{base}IDR"
            ind1h, sum1h = get_tv(tv_symbol, Interval.INTERVAL_1_HOUR)
            ind15m, _ = get_tv(tv_symbol, Interval.INTERVAL_15_MINUTES)
            if not ind1h: 
                time.sleep(0.2)
                continue
            
            rsi = ind1h.get('RSI',50)
            ema9 = ind1h.get('EMA9',0)
            ema20 = ind1h.get('EMA20',0)
            macd = ind1h.get('MACD.macd',0)
            macd_sig = ind1h.get('MACD.signal',0)
            rekom = sum1h.get('RECOMMENDATION','NEUTRAL')
            rsi15 = ind15m.get('RSI',50) if ind15m else 50
            
            teknikal_valid = (
                35 < rsi < 70 and
                ema9 > ema20 and
                macd > macd_sig and
                rsi15 > 55 and
                ("BUY" in rekom or rekom == "NEUTRAL")
            )
            
            if not teknikal_valid:
                time.sleep(0.3)
                continue

            calon_trending.append((base, naik_low, vol, last, low, high, rsi, ema9, ema20, macd, rekom, rsi15))
            time.sleep(0.3)
            
        except: continue
    
    calon_trending=sorted(calon_trending, key=lambda x: x[1] + x[6], reverse=True)
    
    for base, naik_low, vol, last, low, high, rsi, ema9, ema20, macd, rekom, rsi15 in calon_trending[:3]:
        entry=last
        hasil.append({
            'base':base,'entry':entry,'tipe':'VALID AKAN NAIK',
            'vol':vol,'will':True,'global': base in trending_global,
            'tp1':entry*1.10,'tp2':entry*1.20,'sl':entry*0.95,
            'naik':naik_low,'low':low,'high':high,'rsi':rsi,'ema9':ema9,'ema20':ema20,'macd':macd,'rekom':rekom,'rsi15':rsi15
        })
    
    return hasil, len(tickers), trending_global, calon_trending

def cek_tp():
    posisi=load()
    if not posisi: return
    tickers=get_tickers()
    for base,data in list(posisi.items()):
        try:
            now=float(tickers[f"{base.lower()}_idr"]['last'])
            entry=data['entry_idr']
            if now >= entry*1.10 and not data.get('tp1'):
                kirim(f"╔══════════════════╗\n║  ✅ TP1 +10% KENA  ║\n╚══════════════════╝\n💰 *{base}/IDR*\n📈 Entry: Rp {entry:,.0f}\n🚀 Now: Rp {now:,.0f}\n💹 Profit: +10%")
                data['tp1']=True; save(posisi)
            if now >= entry*1.20:
                kirim(f"╔══════════════════╗\n║ 🏆 TP2 +20% KENA  ║\n╚══════════════════╝\n💎 *{base}/IDR JACKPOT!*\n📈 Entry: Rp {entry:,.0f}\n🚀 Now: Rp {now:,.0f}\n💹 Profit: +20% 🎉")
                del posisi[base]; save(posisi)
            if now <= entry*0.95:
                kirim(f"╔══════════════════╗\n║  ⚠️ SL -5% KENA   ║\n╚══════════════════╝\n🔻 *{base}/IDR*\n📉 Entry: Rp {entry:,.0f}\n💔 Now: Rp {now:,.0f}")
                del posisi[base]; save(posisi)
        except: continue

def main():
    kirim("🚀 *BOT SELEKSI KETAT AKTIF*\n✅ Vol 500jt | TP1 +10% TP2 +20%\n✅ Filter: EMA9>EMA20 + MACD Hijau + RSI 35-70 + RSI15>55")
    while True:
        try:
            cek_tp()
            sinyal,total,trend_global,detail=analisa()
            if sinyal:
                posisi=load()
                for
