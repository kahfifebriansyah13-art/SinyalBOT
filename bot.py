import requests, os, time, json
from datetime import datetime, timedelta

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
FILE = "posisi_aktif.json"
FILE_STAT = "statistik.json"

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

def load_stat():
    try:
        with open(FILE_STAT,'r') as f: return json.load(f)
    except: return {"total":0,"tp1":0,"tp2":0,"sl":0,"winrate":0}
def save_stat(s):
    with open(FILE_STAT,'w') as f: json.dump(s,f)

def update_stat(hasil):
    stat = load_stat()
    stat["total"] += 1
    if hasil == "TP1": stat["tp1"] += 1
    if hasil == "TP2": stat["tp2"] += 1
    if hasil == "SL": stat["sl"] += 1
    win = stat["tp1"] + stat["tp2"]
    stat["winrate"] = round(win / stat["total"] * 100, 2) if stat["total"]>0 else 0
    save_stat(stat)
    return stat

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

# === FILTER EARLY GAINER DETECTOR ===
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
            last=float(d['last']); low=float(d['low']); high=float(d['high']); vol=float(d['vol_idr']); open_price=float(d.get('open',last))
            if vol < 300000000: continue
            if low==0: continue
            naik_low=(last-low)/low*100
            naik_24 = (last-open_price)/open_price*100 if open_price>0 else 0
            if naik_low < 2.0 or naik_low > 8.0: continue
            if naik_24 < 0.5: continue
            
            if TV_AVAILABLE:
                ind_daily, sum_daily = get_tv_daily(f"{base}IDR")
                if not ind_daily: continue
                rsi_daily = ind_daily.get('RSI',50)
                ema9 = ind_daily.get('EMA9',0)
                ema21 = ind_daily.get('EMA21',0)
                sma20 = ind_daily.get('SMA20',0)
                macd_m = ind_daily.get('MACD.macd',-999)
                macd_s = ind_daily.get('MACD.signal',-999)
                macd_hist = ind_daily.get('MACD.histogram',0)
                open_d = ind_daily.get('open',low)
                close_d = ind_daily.get('close',last)
                
                cond1 = close_d > open_d
                cond2 = 45 < rsi_daily < 62
                cond3 = last > sma20
                cond4 = ema9 > ema21 * 0.998
                cond5 = macd_hist > -0.2 or macd_m > macd_s
                cond6 = last < high * 0.93
                
                if not (cond1 and cond2 and cond3 and cond4 and cond5 and cond6):
                    continue
                    
                score = naik_low + (vol/1e9) + (rsi_daily-45)
                calon_trending.append((base, naik_low, vol, last, low, high, vol>=800000000, rsi_daily, sum_daily.get('RECOMMENDATION',''), open_d, close_d, score, naik_24))
            time.sleep(0.35)
        except: continue
        
    calon_trending=sorted(calon_trending, key=lambda x: x[11], reverse=True)
    for base, naik_low, vol, last, low, high, is_bandar, rsi_daily, rekom, open_d, close_d, score, naik_24 in calon_trending[:5]:
        entry=last
        tipe = "POTENSI GAINER" if not is_bandar else "EARLY BANDAR"
        hasil.append({'base':base,'entry':entry,'tipe':tipe,'vol':vol,'bandar':is_bandar,'global': base in trending_global,'tp1':entry*1.05,'tp2':entry*1.10,'sl':entry*0.95,'naik':naik_low,'low':low,'high':high,'rsi':rsi_daily,'rekom':rekom,'open':open_d,'close':close_d,'naik24':naik_24})
    return hasil, len(tickers), trending_global, calon_trending

# === CEK TP - WINRATE CUMA PAS CLOSING ===
def cek_tp():
    posisi=load()
    if not posisi: return
    tickers=get_tickers()
    for base,data in list(posisi.items()):
        try:
            now=float(tickers[f"{base.lower()}_idr"]['last'])
            entry=data['entry_idr']
            
            # TP1 = cuma info TP1, tanpa winrate
            if now >= entry*1.05 and not data.get('tp1'):
                update_stat("TP1")
                kirim(f"✅ *TP1 +5% KENA*\n💰 {base}/IDR\nEntry: Rp {entry:,.0f}\nNow: Rp {now:,.0f}\nTahan untuk TP2 +10%")
                data['tp1']=True; save(posisi)
                
            # TP2 = CLOSING + KIRIM WINRATE
            if now >= entry*1.10:
                stat = update_stat("TP2")
                kirim(f"╔══════════════════╗\n║ 🏆 TP2 +10% CLOSING ║\n╚══════════════════╝\n💎 *{base}/IDR JACKPOT*\nEntry: Rp {entry:,.0f}\nNow: Rp {now:,.0f}\n\n📊 *STATISTIK CLOSING*\n🎯 Winrate: {stat['winrate']}% ({stat['tp1']+stat['tp2']}/{stat['total']})\n✅ TP1: {stat['tp1']} | 🏆 TP2: {stat['tp2']} | ❌ SL: {stat['sl']}")
                del posisi[base]; save(posisi)
                
            # SL = CLOSING + KIRIM WINRATE
            if now <= entry*0.95:
                stat = update_stat("SL")
                kirim(f"╔══════════════════╗\n║ 🛑 SL -5% CLOSING  ║\n╚══════════════════╝\n🔻 *{base}/IDR*\nEntry: Rp {entry:,.0f}\nNow: Rp {now:,.0f}\n\n📊 *STATISTIK CLOSING*\n🎯 Winrate: {stat['winrate']}% ({stat['tp1']+stat['tp2']}/{stat['total']})\n✅ TP1: {stat['tp1']} | 🏆 TP2: {stat['tp2']} | ❌ SL: {stat['sl']}")
                del posisi[base]; save(posisi)
                
        except: continue

def cek_perintah_stat():
    try:
        r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?limit=5", timeout=5).json()
        for upd in r.get('result',[]):
            txt = upd.get('message',{}).get('text','')
            chat = str(upd.get('message',{}).get('chat',{}).get('id',''))
            if chat == str(CHAT_ID) and '/stat' in txt.lower():
                stat = load_stat()
                kirim(f"📊 *STATISTIK AKURASI BOT*\n\n📈 Total Sinyal: {stat['total']}\n✅ TP1 +5%: {stat['tp1']}\n🏆 TP2 +10%: {stat['tp2']}\n❌ SL -5%: {stat['sl']}\n\n🎯 *WINRATE: {stat['winrate']}%*")
    except: pass

def main():
    stat = load_stat()
    kirim(f"🚀 *BOT EARLY GAINER AKTIF*\n🔍 Deteksi koin MAU trending (2-8% dari low)\n📈 RSI 45-62 | Break SMA20 | EMA9 nempel 21 | Vol 300jt\n✅ TP1 +5% (tanpa winrate) | 🏆 TP2 +10% & SL -5% (closing + winrate)\n📊 Winrate saat ini: {stat['winrate']}% | Ketik /stat cek manual")
    last_stat_check = time.time()
    while True:
        try:
            cek_tp()
            if time.time() - last_stat_check > 30:
                cek_perintah_stat()
                last_stat_check = time.time()
            sinyal,total,trend_global,detail=analisa()
            if sinyal:
                posisi=load()
                for s in sinyal:
                    if s['base'] in posisi: continue
                    gtag="🔥 GLOBAL" if s['global'] else "💎 LOCAL"
                    judul = f"🐋 EARLY BANDAR {s['base']}/IDR" if s['bandar'] else f"{s['base']}/IDR POTENSI GAINER"
                    kirim(f"╔════════════════════════╗\n║ {judul} ║\n╚════════════════════════╝\n\n{'🐋 BANDAR AWAL' if s['bandar'] else '🚀 MAU TRENDING'} {gtag}\n\n┏━ 🔍 EARLY DETECTION ━┓\n┃ 🟢 Open: Rp {s['open']:,.0f} -> Close: Rp {s['close']:,.0f} (HIJAU AWAL)\n┃ 📊 RSI: {s['rsi']:.1f} (baru lewat 50) | Break SMA20\n┃ 📈 Naik dari Low: +{s['naik']:.2f}% | Hari ini: +{s['naik24']:.2f}%\n┃ 💧 High: Rp {s['high']:,.0f} (masih jauh, ruang naik besar)\n┃ 💰 Vol: Rp {s['vol']/1e9:.2f} M\n┗━━━━━━━━━━━━━━━┛\n\n┏━ 🎯 TRADING PLAN ━┓\n┃ 🟢 ENTRY: Rp {s['entry']:,.0f}\n┃ 🎯 TP1: Rp {s['tp1']:,.0f} (+5%)\n┃ 🏆 TP2: Rp {s['tp2']:,.0f} (+10%)\n┃ 🛑 SL: Rp {s['sl']:,.0f} (-5%)\n┗━━━━━━━━━━━━━━━┛\n\n⚡ *ENTRY AWAL SEBELUM JADI GAINER!*")
                    posisi[s['base']]={'entry_idr':s['entry'],'tipe':s['tipe']}; save(posisi)
            time.sleep(45)
        except Exception as e:
            print(e); time.sleep(30)

if __name__=="__main__":
    main()
