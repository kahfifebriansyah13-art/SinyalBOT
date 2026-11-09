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
            if naik_low >= 3.0 and dekat_high >= 75:
                calon_trending.append((base, naik_low, vol, last, low, high))
        except: continue
    calon_trending=sorted(calon_trending, key=lambda x: x[1], reverse=True)
    for base, naik_low, vol, last, low, high in calon_trending[:5]:
        entry=last
        hasil.append({'base':base,'entry':entry,'tipe':'AKAN TRENDING','vol':vol,'will':True,'global': base in trending_global,'score':200+naik_low,'tp1':entry*1.10,'tp2':entry*1.20,'sl':entry*0.95,'naik':naik_low,'low':low,'high':high})
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
    kirim("🚀 *BOT FINAL 500JT TP 10% AKTIF*\n✅ Vol 500jt | Anti Telat 45 detik\n✅ TP1 +10% | TP2 +20% | SL -5%")
    while True:
        try:
            cek_tp()
            sinyal,total,trend_global,detail=analisa()
            if sinyal:
                posisi=load()
                for s in sinyal:
                    if s['base'] in posisi: continue
                    gtag="🔥 GLOBAL VIRAL" if s['global'] else "💎 LOCAL INDODAX"
                    kirim(f"╔════════════════════════╗\n║ {s['base']}/IDR - {s['tipe']} ║\n╚════════════════════════╝\n\n🚀 AKAN TRENDING {gtag}\n\n┏━ 📊 MARKET DATA ━┓\n┃ 📈 Naik: +{s['naik']:.2f}% dari Low\n┃ 💧 Low: Rp {s['low']:,.0f}\n┃ 🔝 High: Rp {s['high']:,.0f}\n┃ 💰 Vol: Rp {s['vol']/1e9:.2f} Miliar\n┃ 🌍 Trend: {','.join(trend_global[:3])}\n┗━━━━━━━━━━━━━━━┛\n\n┏━ 🎯 TRADING PLAN ━┓\n┃ 🟢 ENTRY: Rp {s['entry']:,.0f}\n┃ 🎯 TP1: Rp {s['tp1']:,.0f} (+10%)\n┃ 🏆 TP2: Rp {s['tp2']:,.0f} (+20%)\n┃ 🛑 SL: Rp {s['sl']:,.0f} (-5%)\n┗━━━━━━━━━━━━━━━┛\n\n⚡ *ENTRY SEKARANG ANTI TELAT!*")
                    posisi[s['base']]={'entry_idr':s['entry'],'tipe':s['tipe']}; save(posisi)
            time.sleep(45)
        except Exception as e:
            print(e); time.sleep(30)

if __name__=="__main__":
    main()
