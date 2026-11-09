import requests, os, time, json, sys, traceback
from datetime import datetime, timedelta

# Cek ENV dulu biar gak crashed diam2
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
if not BOT_TOKEN or not CHAT_ID:
    print("ERROR: BOT_TOKEN atau CHAT_ID kosong di Variables!")
    time.sleep(10)
    sys.exit(1)

FILE = "posisi_aktif.json"

try:
    from tradingview_ta import TA_Handler, Interval
    TV_AVAILABLE = True
except:
    print("tradingview-ta tidak ada, pakai mode volume only")
    TV_AVAILABLE = False

TRENDING_CACHE = ["BTC","ETH","SOL","PEPE","DOGE"]
LAST_TREND_UPDATE = datetime.now() - timedelta(hours=1)

def kirim(pesan):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": pesan, "parse_mode": "Markdown"}, timeout=15)
    except Exception as e:
        print(f"Gagal kirim telegram: {e}")

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
    except Exception as e: print(f"Save error: {e}")

def get_tickers():
    try:
        r=requests.get("https://indodax.com/api/tickers", timeout=15).json()
        return r.get('tickers',{})
    except Exception as e:
        print(f"Ticker error: {e}")
        return {}

def get_tv_safe(symbol):
    if not TV_AVAILABLE: return None, None
    try:
        h = TA_Handler(symbol=symbol, screener="indonesia", exchange="INDODAX", interval=Interval.INTERVAL_1_HOUR)
        a = h.get_analysis()
        return a.indicators, a.summary
    except Exception as e:
        print(f"TV error {symbol}: {e}")
        return None, None

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
    if not tickers: 
        print("Ticker kosong")
        return [],0,[],[]
    trending_global=get_trending_global()
    posisi=load()
    hasil=[]
    calon=[]
    count=0
    for pair,d in tickers.items():
        if count>30: break # BATASI 30 KOIN SAJA BIAR GAK CRASHED LIMIT TV
        if not pair.endswith('_idr'): continue
        base=pair.split('_')[0].upper()
        if base in posisi or base in ['USDT','USDC','BTC','ETH']: continue
        try:
            last=float(d['last']); low=float(d['low']); high=float(d['high']); vol=float(d['vol_idr'])
            if vol < 500000000: continue
            if low==0 or high==0: continue
            naik_low=(last-low)/low*100
            dekat_high=last/high*100
            if naik_low < 3.0 or dekat_high < 75: continue

            # Jika TV tidak tersedia, langsung lolos dengan filter volume saja
            if not TV_AVAILABLE:
                calon.append((base, naik_low, vol, last, low, high, 50, 0, 0, 0, "NEUTRAL", 60))
                count+=1
                continue

            ind1h, sum1h = get_tv_safe(f"{base}IDR")
            if not ind1h: 
                time.sleep(0.5)
                continue
            
            rsi = ind1h.get('RSI',50)
            ema9 = ind1h.get('EMA9',0)
            ema20 = ind1h.get('EMA20',0)
            macd = ind1h.get('MACD.macd',0)
            macd_sig = ind1h.get('MACD.signal',0)
            rekom = sum1h.get('RECOMMENDATION','NEUTRAL')
            
            # Filter lebih longgar biar gak selalu 0
            if not (35 < rsi < 75 and ema9 > ema20):
                time.sleep(0.5)
                continue

            calon.append((base, naik_low, vol, last, low, high, rsi, ema9, ema20, macd, rekom, 60))
            count+=1
            time.sleep(1) # Delay 1 detik biar gak di block TV
            
        except Exception as e:
            print(f"Error analisa {pair}: {e}")
            continue
    
    calon=sorted(calon, key=lambda x: x[1], reverse=True)
    for base, naik_low, vol, last, low, high, rsi, ema9, ema20, macd, rekom, rsi15 in calon[:3]:
        entry=last
        hasil.append({'base':base,'entry':entry,'tipe':'VALID AKAN NAIK','vol':vol,'global': base in trending_global,'tp1':entry*1.10,'tp2':entry*1.20,'sl':entry*0.95,'naik':naik_low,'low':low,'high':high,'rsi':rsi,'ema9':ema9,'ema20':ema20,'macd':macd,'rekom':rekom,'rsi15':rsi15})
    
    return hasil, len(tickers), trending_global, calon

def main():
    print("BOT START ANTI CRASHED...")
    kirim("✅ *BOT ANTI CRASHED AKTIF*\nVol 500jt | TP1 10% TP2 20%\nFilter TV aman (delay 1 detik)")
    while True:
        try:
            tickers=get_tickers()
            # Cek TP simpel
            posisi=load()
            if posisi and tickers:
                for base,data in list(posisi.items()):
                    try:
                        now=float(tickers[f"{base.lower()}_idr"]['last'])
                        entry=data['entry_idr']
                        if now >= entry*1.10 and not data.get('tp1'):
                            kirim(f"╔══════════════════╗\n║  ✅ TP1 +10% KENA  ║\n╚══════════════════╝\n💰 *{base}/IDR*")
                            data['tp1']=True; save(posisi)
                        if now >= entry*1.20:
                            kirim(f"╔══════════════════╗\n║ 🏆 TP2 +20% KENA  ║\n╚══════════════════╝\n💎 *{base}*")
                            del posisi[base]; save(posisi)
                        if now <= entry*0.95:
                            kirim(f"╔══════════════════╗\n║  ⚠️ SL -5% KENA   ║\n╚══════════════════╝\n🔻 *{base}*")
                            del posisi[base]; save(posisi)
                    except: continue

            sinyal,total,trend_global,detail=analisa()
            if sinyal:
                posisi=load()
                for s in sinyal:
                    if s['base'] in posisi: continue
                    gtag="🔥 GLOBAL VIRAL" if s['global'] else "💎 LOCAL"
                    kirim(f"╔════════════════════════╗\n║ {s['base']}/IDR - {s['tipe']} ║\n╚════════════════════════╝\n\n🚀 VALID AKAN NAIK {gtag}\n\n┏━ 📊 MARKET DATA ━┓\n┃ 📈 Naik: +{s['naik']:.2f}% dari Low\n┃ 💧 Low: Rp {s['low']:,.0f}\n┃ 🔝 High: Rp {s['high']:,.0f}\n┃ 💰 Vol: Rp {s['vol']/1e9:.2f} M\n┗━━━━━━━━━━━━━━━┛\n\n┏━ 📈 TEKNIKAL VALID ━┓\n┃ 📊 RSI: {s['rsi']:.1f}\n┃ 🔀 EMA9 {s['ema9']:.0f} > EMA20 {s['ema20']:.0f}\n┃ 🤖 Rekom: {s['rekom']}\n┗━━━━━━━━━━━━━━━┛\n\n┏━ 🎯 PLAN ━┓\n┃ 🟢 ENTRY: Rp {s['entry']:,.0f}\n┃ 🎯 TP1: Rp {s['tp1']:,.0f} (+10%)\n┃ 🏆 TP2: Rp {s['tp2']:,.0f} (+20%)\n┃ 🛑 SL: Rp {s['sl']:,.0f}\n┗━━━━━━━━━━━━━━━┛")
                    posisi[s['base']]={'entry_idr':s['entry'],'tipe':s['tipe']}; save(posisi)
            else:
                print(f"Scan {total} koin - 0 valid")
            time.sleep(60)
        except Exception as e:
            print(f"LOOP ERROR: {e}")
            traceback.print_exc()
            time.sleep(30) # Jangan exit, retry lagi

if __name__=="__main__":
    main()
