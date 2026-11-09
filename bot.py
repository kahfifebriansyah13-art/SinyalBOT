import requests, os, time, json, sys, traceback
from datetime import datetime, timedelta

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
if not BOT_TOKEN or not CHAT_ID:
    print("ERROR: BOT_TOKEN atau CHAT_ID kosong!")
    time.sleep(10)
    sys.exit(1)

FILE = "posisi_aktif.json"

try:
    from tradingview_ta import TA_Handler, Interval
    TV_AVAILABLE = True
except:
    TV_AVAILABLE = False

TRENDING_CACHE = ["BTC","ETH","SOL","PEPE","DOGE"]
LAST_TREND_UPDATE = datetime.now() - timedelta(hours=1)

def kirim(pesan):
    try: requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": pesan, "parse_mode": "Markdown"}, timeout=15)
    except: pass

def load():
    try:
        if not os.path.exists(FILE):
            with open(FILE,'w') as f: json.dump({},f)
            return {}
        with open(FILE,'r') as f: return json.load(f)
    except: return {}
def save(d):
    try:
        with open(FILE,'w') as f: json.dump(d,f)
    except: pass

def get_tickers():
    try: return requests.get("https://indodax.com/api/tickers", timeout=15).json().get('tickers',{})
    except: return {}

def get_tv_safe(symbol):
    if not TV_AVAILABLE: return None, None
    try:
        h = TA_Handler(symbol=symbol, screener="indonesia", exchange="INDODAX", interval=Interval.INTERVAL_1_HOUR)
        return h.get_analysis().indicators, h.get_analysis().summary
    except: return None, None

def get_trending_global():
    global TRENDING_CACHE, LAST_TREND_UPDATE
    if datetime.now() - LAST_TREND_UPDATE > timedelta(minutes=20):
        try:
            r=requests.get("https://api.coingecko.com/api/v3/search/trending", timeout=10).json()
            TRENDING_CACHE=[x['item']['symbol'].upper() for x in r['coins'][:10]]
            LAST_TREND_UPDATE=datetime.now()
        except: pass
    return TRENDING_CACHE

def analisa():
    tickers=get_tickers()
    if not tickers: return [],0,[],[]
    trending_global=get_trending_global()
    posisi=load()
    hasil=[]
    calon=[]
    count=0
    for pair,d in tickers.items():
        if count>35: break
        if not pair.endswith('_idr'): continue
        base=pair.split('_')[0].upper()
        if base in posisi or base in ['USDT','USDC']: continue
        try:
            last=float(d['last']); low=float(d['low']); high=float(d['high']); vol=float(d['vol_idr'])
            if vol < 500000000: continue
            if low==0 or high==0: continue
            naik_low=(last-low)/low*100
            dekat_high=last/high*100 if high>0 else 0
            
            # SETTING 23% IKUT BANDAR - SUPER AWAL
            if naik_low < 2.0 or dekat_high < 23: continue
            if dekat_high > 70: continue # Kalau udah 70% ke atas = udah telat, skip (biar ikut bandar bawah)

            if TV_AVAILABLE:
                ind1h, sum1h = get_tv_safe(f"{base}IDR")
                if not ind1h: 
                    time.sleep(0.5)
                    continue
                rsi = ind1h.get('RSI',50)
                ema9 = ind1h.get('EMA9',0)
                ema20 = ind1h.get('EMA20',0)
                # Filter bandar: RSI masih dingin 30-65 (bandar baru akumulasi), EMA mulai golden cross
                if not (30 < rsi < 68):
                    time.sleep(0.5)
                    continue
            else:
                rsi, ema9, ema20 = 50, 0, 0
                sum1h = {"RECOMMENDATION":"NEUTRAL"}

            calon.append((base, naik_low, vol, last, low, high, rsi, ema9, ema20, sum1h.get('RECOMMENDATION','NEUTRAL'), dekat_high))
            count+=1
            time.sleep(0.8)
        except: continue
    
    calon=sorted(calon, key=lambda x: x[1], reverse=True)
    for base, naik_low, vol, last, low, high, rsi, ema9, ema20, rekom, dekat_high in calon[:5]:
        entry=last
        hasil.append({'base':base,'entry':entry,'tipe':'BANDAR MASUK 23%','vol':vol,'global': base in trending_global,'tp1':entry*1.10,'tp2':entry*1.20,'sl':entry*0.95,'naik':naik_low,'low':low,'high':high,'rsi':rsi,'dekat':dekat_high,'rekom':rekom})
    return hasil, len(tickers), trending_global, calon

def main():
    kirim("🚀 *BOT BANDAR 23% AKTIF*\n✅ Dekat High >=23% (super awal)\n✅ Naik dari Low >=2%\n✅ Vol 500jt | TP1 10% TP2 20%\n⚡ Mode ikut bandar bawah")
    while True:
        try:
            sinyal,total,trend_global,detail=analisa()
            if sinyal:
                posisi=load()
                for s in sinyal:
                    if s['base'] in posisi: continue
                    kirim(f"╔════════════════════════╗\n║ {s['base']}/IDR - {s['tipe']} ║\n╚════════════════════════╝\n\n🐋 *BANDAR MASUK DETECTED* 💎 LOCAL\n\n┏━ 📊 MARKET DATA ━┓\n┃ 📈 Naik dari Low: +{s['naik']:.2f}%\n┃ 📍 Posisi: {s['dekat']:.0f}% dari High (23% = bawah)\n┃ 💧 Low: Rp {s['low']:,.0f}\n┃ 🔝 High: Rp {s['high']:,.0f}\n┃ 💰 Vol: Rp {s['vol']/1e9:.2f} M (Bandar)\n┃ 📊 RSI: {s['rsi']:.1f}\n┗━━━━━━━━━━━━━━━┛\n\n┏━ 🎯 PLAN IKUT BANDAR ━┓\n┃ 🟢 ENTRY: Rp {s['entry']:,.0f} (BAWAH)\n┃ 🎯 TP1: Rp {s['tp1']:,.0f} (+10%)\n┃ 🏆 TP2: Rp {s['tp2']:,.0f} (+20%)\n┃ 🛑 SL: Rp {s['sl']:,.0f}\n┗━━━━━━━━━━━━━━━┛\n\n⚡ *MASUK SEKARANG IKUT BANDAR!*")
                    posisi[s['base']]={'entry_idr':s['entry'],'tipe':s['tipe']}; save(posisi)
            else:
                print(f"Scan {total} koin - 0 bandar 23%")
            time.sleep(50)
        except Exception as e:
            print(f"Error: {e}"); time.sleep(30)

if __name__=="__main__":
    main()
