import requests, os, time, json
from datetime import datetime, timedelta

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
FILE = "posisi_aktif.json"
FILE_STAT = "statistik.json"

try:
    from tradingview_ta import TA_Handler, Interval
    TV_AVAILABLE = True
except:
    TV_AVAILABLE = False

def kirim(pesan):
    requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
    data={"chat_id": CHAT_ID, "text": pesan, "parse_mode": "Markdown"}, timeout=10)

def load(): 
    try: return json.load(open(FILE))
    except: return {}
def save(d): json.dump(d, open(FILE,'w'))
def load_stat():
    try: return json.load(open(FILE_STAT))
    except: return {"total":0,"tp1":0,"tp2":0,"sl":0,"winrate":0}
def save_stat(s): json.dump(s, open(FILE_STAT,'w'))
def update_stat(h):
    s=load_stat(); s["total"]+=1
    if h=="TP1": s["tp1"]+=1
    if h=="TP2": s["tp2"]+=1
    if h=="SL": s["sl"]+=1
    s["winrate"]=round((s["tp1"]+s["tp2"])/s["total"]*100,2) if s["total"]>0 else 0
    save_stat(s); return s

def get_tickers():
    try: return requests.get("https://indodax.com/api/tickers", timeout=10).json()['tickers']
    except: return {}

def get_tv(s):
    if not TV_AVAILABLE: return None,None
    try:
        h=TA_Handler(symbol=s, screener="indonesia", exchange="INDODAX", interval=Interval.INTERVAL_1_DAY)
        a=h.get_analysis(); return a.indicators, a.summary
    except: return None,None

def analisa():
    tickers=get_tickers(); hasil=[]; posisi=load()
    for pair,d in tickers.items():
        if not pair.endswith('_idr'): continue
        base=pair.split('_')[0].upper()
        if base in posisi or base in ['USDT','USDC']: continue
        try:
            last=float(d['last']); low=float(d['low']); high=float(d['high']); vol=float(d['vol_idr']); open_p=float(d.get('open',last))
            if vol<300000000: continue
            naik_low=(last-low)/low*100
            naik_24=(last-open_p)/open_p*100 if open_p>0 else 0
            if naik_low<2 or naik_low>8: continue
            if naik_24<0.5: continue
            ind,sumd=get_tv(f"{base}IDR")
            if not ind: continue
            rsi=ind.get('RSI',50); ema9=ind.get('EMA9',0); ema21=ind.get('EMA21',0); sma20=ind.get('SMA20',0)
            macd_m=ind.get('MACD.macd',0); macd_s=ind.get('MACD.signal',0); open_d=ind.get('open',low); close_d=ind.get('close',last)
            if not (close_d>open_d and 45<rsi<62 and last>sma20 and ema9>ema21*0.998 and last<high*0.93): continue
            hasil.append((base,last,entry:=last, last*1.05, last*1.10, last*0.95, naik_low, vol, rsi, open_d, close_d, naik_24))
            time.sleep(0.3)
        except: continue
    return sorted(hasil, key=lambda x:x[6], reverse=True)[:5]

def cek_tp():
    posisi=load(); tickers=get_tickers()
    for base,data in list(posisi.items()):
        try:
            now=float(tickers[f"{base.lower()}_idr"]['last']); entry=data['entry']
            if now>=entry*1.05 and not data.get('tp1'):
                update_stat("TP1")
                kirim(f"✅ TP1 +5% {base}/IDR\nEntry Rp {entry:,.0f} -> Rp {now:,.0f}")
                data['tp1']=True; save(posisi)
            if now>=entry*1.10:
                stat=update_stat("TP2")
                kirim(f"🏆 TP2 +10% CLOSING {base}/IDR\nEntry Rp {entry:,.0f} -> Rp {now:,.0f}\n\n📊 WINRATE: {stat['winrate']}% ({stat['tp1']+stat['tp2']}/{stat['total']})")
                del posisi[base]; save(posisi)
            if now<=entry*0.95:
                stat=update_stat("SL")
                kirim(f"🛑 SL -5% CLOSING {base}/IDR\nEntry Rp {entry:,.0f} -> Rp {now:,.0f}\n\n📊 WINRATE: {stat['winrate']}% ({stat['tp1']+stat['tp2']}/{stat['total']})")
                del posisi[base]; save(posisi)
        except: continue

def main():
    kirim("🚀 BOT EARLY GAINER AKTIF\nDeteksi 2-8% dari Low, RSI 45-62, Break SMA20\nTP1 tanpa winrate, TP2/SL closing + winrate")
    while True:
        try:
            cek_tp()
            for base,last,entry,tp1,tp2,sl,naik_low,vol,rsi,open_d,close_d,naik_24 in analisa():
                pos=load()
                if base in pos: continue
                kirim(f"🚀 POTENSI GAINER {base}/IDR\n📈 Naik Low +{naik_low:.1f}% | Hari ini +{naik_24:.1f}%\n💰 Vol {vol/1e9:.2f}M | RSI {rsi:.1f}\n🟢 ENTRY Rp {entry:,.0f}\n🎯 TP1 Rp {tp1:,.0f} | TP2 Rp {tp2:,.0f}\n🛑 SL Rp {sl:,.0f}")
                pos[base]={'entry':entry}; save(pos)
            time.sleep(45)
        except Exception as e:
            print(e); time.sleep(20)

if __name__=="__main__": main()
