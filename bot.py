import requests, os, time, json
from datetime import datetime, timedelta

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
FILE = "posisi_aktif.json"

TRENDING_CACHE = ["BTC","ETH","SOL","PEPE","DOGE"]
LAST_TREND_UPDATE = datetime.now() - timedelta(hours=1)

try:
    from tradingview_ta import TA_Handler, Interval
    TV_AVAILABLE = True
except:
    TV_AVAILABLE = False

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

def get_tv_daily(symbol):
    if not TV_AVAILABLE: return None, None
    try:
        h = TA_Handler(symbol=symbol, screener="indonesia", exchange="INDODAX", interval=Interval.INTERVAL_1_DAY)
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
        if base in posisi or base in ['USDT','USDC']: continue
        try:
            last=float(d['last']); low=float(d['low']); high=float(d['high']); vol=float(d['vol_idr'])
            if vol < 500000000: continue
            if low==0: continue
            naik_low=(last-low)/low*100
            
            # HAPUS DEKAT HIGH - CUMA PAKAI NAIK DARI LOW
            if naik_low < 3.0: continue
            
            # CEK DAILY CANDLE (TANPA DEKAT HIGH)
            if TV_AVAILABLE:
                ind_daily, sum_daily = get_tv_daily(f"{base}IDR")
                if not ind_daily: 
                    # Jika TV error, tetap kasih sinyal biar lancar (tanpa daily)
                    calon_trending.append((base, naik_low, vol, last, low, high, False, 55, 0, 0, "NEUTRAL", low, last))
                    time.sleep(0.3)
                    continue
                
                rsi_daily = ind_daily.get('RSI',55)
                ema9_daily = ind_daily.get('EMA9',0)
                ema21_daily = ind_daily.get('EMA21',0)
                open_daily = ind_daily.get('open',low)
                close_daily = ind_daily.get('close',last)
                
                # Filter daily ringan biar sinyal tetap masuk
                if not (48 < rsi_daily < 72):
                    time.sleep(0.3)
                    continue
                    
                calon_trending.append((base, naik_low, vol, last, low, high, vol>=1000000000, rsi_daily, ema9_daily, ema21_daily, sum_daily.get('RECOMMENDATION','NEUTRAL'), open_daily, close_daily))
            else:
                calon_trending.append((base, naik_low, vol, last, low, high, vol>=1000000000, 55, 0, 0, "NEUTRAL", low, last))
            
            time.sleep(0.4)
        except: continue
        
    calon_trending=sorted(calon_trending, key=lambda x: x[1], reverse=True)
    
    for base, naik_low, vol, last, low, high, is_bandar, rsi_daily, ema9, ema21, rekom, open_d, close_d in calon_trending[:5]:
        entry=last
        tipe = "BANDAR MASUK" if is_bandar else "AKAN TRENDING"
        hasil.append({'base':base,'entry':entry,'tipe':tipe,'vol':vol,'bandar':is_bandar,'global': base in trending_global,'tp1':entry*1.10,'tp2':entry*1.20,'sl':entry*0.95,'naik':naik_low,'low':low,'high':high,'rsi':rsi_daily,'rekom':rekom,'open':open_d,'close':close_d})
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
                kirim(f"╔══════════════════╗\n║  ✅ TP1 +10% KENA  ║\n╚══════════════════╝\n💰 *{base}/IDR*")
                data['tp1']=True; save(posisi)
            if now >= entry*1.20:
                kirim(f"╔══════════════════╗\n║ 🏆 TP2 +20% KENA  ║\n╚══════════════════╝\n💎 *{base}/IDR JACKPOT!*")
                del posisi[base]; save(posisi)
            if now <= entry*0.95:
                kirim(f"╔══════════════════╗\n║  ⚠️ SL -5% KENA   ║\n╚══════════════════╝\n🔻 *{base}/IDR*")
                del posisi[base]; save(posisi)
        except: continue

def main():
    kirim("🚀 *BOT TANPA DEKAT HIGH AKTIF*\n✅ Filter: Vol 500jt + Naik 3% + Daily Candle\n✅ Tanpa dekat high - sinyal lancar\n✅ TP1 +10% TP2 +20% | Deteksi Bandar")
    while True:
        try:
            cek_tp()
            sinyal,total,trend_global,detail=analisa()
            if sinyal:
                posisi=load()
                for s in sinyal:
                    if s['base'] in posisi: continue
                    gtag="🔥 GLOBAL" if s['global'] else "💎 LOCAL"
                    judul = f"🐋 BANDAR - {s['base']}/IDR" if s['bandar'] else f"{s['base']}/IDR - {s['tipe']}"
                    kirim(f"╔════════════════════════╗\n║ {judul} ║\n╚════════════════════════╝\n\n{'🐋 BANDAR MASUK' if s['bandar'] else '🚀 AKAN TRENDING'} {gtag}\n\n┏━ 📊 MARKET DATA ━┓\n┃ 📈 Naik: +{s['naik']:.2f}% dari Low\n┃ 💧 Low: Rp {s['low']:,.0f}\n┃ 🔝 High: Rp {s['high']:,.0f}\n┃ 💰 Vol: Rp {s['vol']/1e9:.2f} M\n┃ 📊 RSI Daily: {s['rsi']:.1f}\n┗━━━━━━━━━━━━━━━┛\n\n┏━ 🎯 TRADING PLAN ━┓\n┃ 🟢 ENTRY: Rp {s['entry']:,.0f}\n┃ 🎯 TP1: Rp {s['tp1']:,.0f} (+10%)\n┃ 🏆 TP2: Rp {s['tp2']:,.0f} (+20%)\n┃ 🛑 SL: Rp {s['sl']:,.0f}\n┗━━━━━━━━━━━━━━━┛\n\n⚡ *ENTRY SEKARANG!*")
                    posisi[s['base']]={'entry_idr':s['entry'],'tipe':s['tipe']}; save(posisi)
            else:
                print(f"Scan {total} koin - 0 sinyal")
            time.sleep(45)
        except Exception as e:
            print(e); time.sleep(30)

if __name__=="__main__":
    main()
