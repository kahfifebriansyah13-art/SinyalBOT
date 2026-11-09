import requests, os, time, json
from datetime import datetime, timedelta
from tradingview_ta import TA_Handler, Interval

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
FILE = "posisi_aktif.json"

TRENDING_CACHE = ["BTC","ETH","SOL","PEPE","DOGE"]
LAST_TREND_UPDATE = datetime.now() - timedelta(hours=1)

# SETTING DAILY CANDLE PROFIT
DEKAT_HIGH_MIN = 55  # Minimal 55% biar gak terlalu bawah
DEKAT_HIGH_MAX = 80  # Maksimal 80% biar gak telat

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
    try:
        h = TA_Handler(symbol=symbol, screener="indonesia", exchange="INDODAX", interval=Interval.INTERVAL_1_DAY)
        return h.get_analysis().indicators, h.get_analysis().summary
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
            if low==0 or high==0: continue
            
            naik_low=(last-low)/low*100
            dekat_high=last/high*100
            
            # FILTER AWAL ANTI TELAT
            if not (naik_low >= 3.0 and DEKAT_HIGH_MIN <= dekat_high <= DEKAT_HIGH_MAX):
                continue
            
            # CEK GRAFIK CANDLE HARIAN (INI KUNCINYA)
            ind_daily, sum_daily = get_tv_daily(f"{base}IDR")
            if not ind_daily: 
                time.sleep(0.5)
                continue
            
            # Data daily candle
            rsi_daily = ind_daily.get('RSI',50)
            ema9_daily = ind_daily.get('EMA9',0)
            ema21_daily = ind_daily.get('EMA21',0)
            ema20_daily = ind_daily.get('EMA20',0)
            open_daily = ind_daily.get('open',0)
            close_daily = ind_daily.get('close',last)
            sma20_daily = ind_daily.get('SMA20',0)
            macd_daily = ind_daily.get('MACD.macd',0)
            macd_sig_daily = ind_daily.get('MACD.signal',0)
            rekom_daily = sum_daily.get('RECOMMENDATION','NEUTRAL')
            
            # SYARAT DAILY CANDLE AKAN TERUS NAIK & PROFIT OPTIMAL
            candle_hijau = close_daily > open_daily  # Candle hari ini bullish
            ema_bullish = ema9_daily > ema21_daily and last > sma20_daily
            rsi_optimal = 48 < rsi_daily < 68  # RSI daily ideal 48-68 (ada tenaga naik)
            macd_bullish = macd_daily > macd_sig_daily
            
            if not (candle_hijau and ema_bullish and rsi_optimal and macd_bullish):
                time.sleep(0.6)
                continue

            is_bandar = vol >= 1000000000 or naik_low >= 5.5
            
            calon_trending.append((base, naik_low, vol, last, low, high, is_bandar, dekat_high, rsi_daily, ema9_daily, ema21_daily, rekom_daily, open_daily, close_daily))
            time.sleep(0.8)
            
        except: continue
        
    calon_trending=sorted(calon_trending, key=lambda x: x[1] + x[8], reverse=True) # Sort by naik + rsi daily
    
    for base, naik_low, vol, last, low, high, is_bandar, dekat_high, rsi_daily, ema9_daily, ema21_daily, rekom_daily, open_daily, close_daily in calon_trending[:5]:
        entry=last
        tipe = "BANDAR MASUK DAILY" if is_bandar else "DAILY BULLISH"
        hasil.append({
            'base':base,'entry':entry,'tipe':tipe,'vol':vol,'bandar':is_bandar,
            'global': base in trending_global,'tp1':entry*1.10,'tp2':entry*1.20,'sl':entry*0.95,
            'naik':naik_low,'low':low,'high':high,'dekat':dekat_high,
            'rsi_daily':rsi_daily,'ema9':ema9_daily,'ema21':ema21_daily,'rekom':rekom_daily,
            'open':open_daily,'close':close_daily
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
                kirim(f"╔══════════════════╗\n║  ✅ TP1 +10% KENA  ║\n╚══════════════════╝\n💰 *{base}/IDR*")
                data['tp1']=True; save(posisi)
            if now >= entry*1.20:
                kirim(f"╔══════════════════╗\n║ 🏆 TP2 +20% KENA  ║\n╚══════════════════╝\n💎 *{base}/IDR JACKPOT +20%!*")
                del posisi[base]; save(posisi)
            if now <= entry*0.95:
                kirim(f"╔══════════════════╗\n║  ⚠️ SL -5% KENA   ║\n╚══════════════════╝\n🔻 *{base}/IDR*")
                del posisi[base]; save(posisi)
        except: continue

def main():
    kirim(f"🚀 *BOT DAILY CANDLE PROFIT AKTIF*\n✅ Daily Hijau + EMA9>EMA21 + RSI 48-68\n✅ Dekat High {DEKAT_HIGH_MIN}%-{DEKAT_HIGH_MAX}%\n✅ Vol 500jt | TP1 10% TP2 20%")
    while True:
        try:
            cek_tp()
            sinyal,total,trend_global,detail=analisa()
            if sinyal:
                posisi=load()
                for s in sinyal:
                    if s['base'] in posisi: continue
                    gtag="🔥 GLOBAL VIRAL" if s['global'] else "💎 LOCAL INDODAX"
                    judul = f"🐋 {s['base']}/IDR - {s['tipe']}" if s['bandar'] else f"{s['base']}/IDR - {s['tipe']}"
                    
                    kirim(f"╔════════════════════════╗\n║ {judul} ║\n╚════════════════════════╝\n\n{'🐋 BANDAR DAILY' if s['bandar'] else '📈 DAILY BULLISH'} {gtag}\n\n┏━ 🕯️ DAILY CANDLE ━┓\n┃ 🟢 Open: Rp {s['open']:,.0f} | Close: Rp {s['close']:,.0f} (HIJAU)\n┃ 📊 RSI Daily: {s['rsi_daily']:.1f} (Optimal 48-68)\n┃ 🔀 EMA9 {s['ema9']:.0f} > EMA21 {s['ema21']:.0f} (Bullish)\n┃ 🤖 Rekom Daily: {s['rekom']}\n┗━━━━━━━━━━━━━━━┛\n\n┏━ 📊 MARKET DATA ━┓\n┃ 📈 Naik: +{s['naik']:.2f}% dari Low\n┃ 📍 Posisi: {s['dekat']:.0f}% dari High\n┃ 💧 Low: Rp {s['low']:,.0f} | High: Rp {s['high']:,.0f}\n┃ 💰 Vol: Rp {s['vol']/1e9:.2f} M\n┗━━━━━━━━━━━━━━━┛\n\n┏━ 🎯 TRADING PLAN ━┓\n┃ 🟢 ENTRY: Rp {s['entry']:,.0f}\n┃ 🎯 TP1: Rp {s['tp1']:,.0f} (+10%)\n┃ 🏆 TP2: Rp {s['tp2']:,.0f} (+20%)\n┃ 🛑 SL: Rp {s['sl']:,.0f}\n┗━━━━━━━━━━━━━━━┛\n\n⚡ *DAILY CANDLE VALID AKAN TERUS NAIK!*")
                    posisi[s['base']]={'entry_idr':s['entry'],'tipe':s['tipe']}; save(posisi)
            time.sleep(60)
        except Exception as e:
            print(e); time.sleep(30)

if __name__=="__main__":
    main()
