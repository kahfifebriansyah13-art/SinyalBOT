import requests, os, time, json
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
FILE = "posisi_aktif.json"

def kirim(pesan):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": pesan, "parse_mode": "Markdown"}, timeout=15)
    except Exception as e:
        print(f"Gagal kirim: {e}")

def load():
    try:
        with open(FILE,'r') as f: return json.load(f)
    except: return {}

def save(d):
    try:
        with open(FILE,'w') as f: json.dump(d,f)
    except: pass

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
    if len(closes) < p+1: return 50
    g=[max(closes[i]-closes[i-1],0) for i in range(1,len(closes))]
    l=[max(closes[i-1]-closes[i],0) for i in range(1,len(closes))]
    ag=sum(g[-p:])/p; al=sum(l[-p:])/p
    if al==0: return 70
    return 100 - (100/(1+ag/al))

def calc_ema(closes,p):
    k=2/(p+1); ema=closes[0]
    for pr in closes[1:]: ema=pr*k+ema*(1-k)
    return ema

def analisa():
    tickers=get_tickers()
    if not tickers:
        return [], 0
    posisi=load()
    hasil=[]
    total_scan=0
    for pair,d in tickers.items():
        if not pair.endswith('_idr'): continue
        base=pair.split('_')[0].upper()
        total_scan+=1
        if base in posisi or base in ['USDT','USDC','DAI']: continue
        try:
            vol_idr=float(d['vol_idr'])
            if vol_idr < 1000000000: continue # MIN 1 M

            closes, vols = get_klines(f"{base}USDT")
            if closes is None or len(closes)<60: continue

            rsi=calc_rsi(closes)
            ema9=calc_ema(closes,9)
            ema21=calc_ema(closes,21)
            ema50=calc_ema(closes,50)
            price=closes[-1]
            vol_spike=vols[-1]/(sum(vols[-20:])/20) if sum(vols[-20:])>0 else 1

            # FILTER AKURAT TAPI TIDAK TERLALU KETAT
            valid = (ema9 > ema21) and (price > ema50) and (48 < rsi < 70) and (vol_spike > 1.1)

            if valid:
                entry_idr=float(d['last'])
                hasil.append({
                    'base':base,'entry_idr':entry_idr,
                    'rsi':round(rsi,1),
                    'vol_spike':round(vol_spike,2),
                    'vol_idr':vol_idr,
                    'tp1':entry_idr*1.05,'tp2':entry_idr*1.10,'sl':entry_idr*0.95,
                    'score': vol_spike*10 + rsi
                })
        except: continue
    
    hasil_sorted = sorted(hasil, key=lambda x:x['score'], reverse=True)[:2]
    return hasil_sorted, total_scan

def main():
    kirim("🏆 *BOT FINAL ANTI HANG AKTIF*\n✅ Scan tiap 3 menit\n✅ Laporan masuk terus\n✅ Filter: RSI+EMA+Vol 1M")
    while True:
        try:
            sinyal, total = analisa()
            if sinyal:
                posisi=load()
                for s in sinyal:
                    pesan=f"🚀 *SINYAL BUY {s['base']}/IDR*\n\n"
                    pesan+=f"*TA Pro 1H:*\nRSI: {s['rsi']}\nVol Spike: {s['vol_spike']}x\nVol Indodax: Rp {s['vol_idr']/1000000000:.1f} M\n"
                    pesan+=f"Harga: Rp {s['entry_idr']:,.0f}\n\n"
                    pesan+=f"*PLAN:*\nBUY: {s['entry_idr']:,.0f}\nTP1: {s['tp1']:,.0f} (+5%)\nTP2: {s['tp2']:,.0f} (+10%)\nSL: {s['sl']:,.0f}"
                    kirim(pesan)
                    posisi[s['base']]={'entry_idr':s['entry_idr']}
                    save(posisi)
                    time.sleep(1)
            else:
                kirim(f"⏳ Scan {total} koin Indodax - Belum ada setup PRO valid (RSI+EMA). Bot hidup, market lagi sepi.")
            
            time.sleep(180) # 3 menit
        except Exception as e:
            print(e)
            kirim(f"⚠️ Bot error: {e} - restart 1 menit")
            time.sleep(60)

if __name__=="__main__":
    main()
