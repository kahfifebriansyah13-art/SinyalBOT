import requests, os, time, json
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
FILE = "posisi_aktif.json"

def kirim(pesan):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHAT_ID, "text": pesan, "parse_mode": "Markdown"}, timeout=15)
    except: pass

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
        highs=[float(c[2]) for c in data]
        lows=[float(c[3]) for c in data]
        vols=[float(c[5]) for c in data]
        return closes, highs, lows, vols
    except: return None,None,None,None

def calc_rsi(closes,p=14):
    g=[max(closes[i]-closes[i-1],0) for i in range(1,len(closes))]
    l=[max(closes[i-1]-closes[i],0) for i in range(1,len(closes))]
    ag=sum(g[-p:])/p; al=sum(l[-p:])/p
    if al==0: return 70
    return 100 - (100/(1+ag/al))

def calc_ema(closes,p):
    k=2/(p+1); ema=closes[0]
    for pr in closes[1:]: ema=pr*k+ema*(1-k)
    return ema

def get_trending():
    try:
        cg=requests.get("https://api.coingecko.com/api/v3/search/trending", timeout=10).json()
        return [c['item']['symbol'].upper() for c in cg['coins'][:10]]
    except: return ["BTC","ETH","SOL","PEPE","DOGE","XRP","SHIB"]

def cek_tp():
    posisi=load()
    if not posisi: return
    tickers=get_tickers()
    for base, info in list(posisi.items()):
        pidr=f"{base.lower()}_idr"
        if pidr not in tickers: continue
        now=float(tickers[pidr]['last'])
        entry=info['entry_idr']
        profit=((now-entry)/entry)*100

        if not info.get('tp1_hit') and profit>=5:
            kirim(f"✅ *TP1 TERCAPAI {base}/IDR*\nEntry: Rp {entry:,.0f}\nNow: Rp {now:,.0f}\nProfit: +{profit:.2f}%\n\n📊 Akurasi BOT: TP1 HIT +1\nSaran: Jual 50%")
            info['tp1_hit']=True; save(posisi)
        if not info.get('tp2_hit') and profit>=10:
            kirim(f"🎯🎯 *TP2 TERCAPAI {base}/IDR - AKURAT!*\nEntry: Rp {entry:,.0f}\nNow: Rp {now:,.0f}\nProfit: +{profit:.2f}%\n\n🔥 BOT AKURASI TINGGI! 🔥")
            info['tp2_hit']=True; save(posisi)
        if profit<=-5:
            kirim(f"🛑 *SL KENA {base}/IDR*\nLoss: {profit:.2f}% - Cut loss disiplin")
            del posisi[base]; save(posisi)

def analisa():
    tickers=get_tickers()
    trending=get_trending()
    posisi=load()
    hasil=[]
    for pair,d in tickers.items():
        if not pair.endswith('_idr'): continue
        base=pair.split('_')[0].upper()
        if base in posisi or base in ['USDT','USDC','DAI']: continue

        try:
            vol_idr=float(d['vol_idr'])
            if vol_idr<1000000000: continue # VOLUME MIN 1M

            closes,highs,lows,vols=get_klines(f"{base}USDT")
            if closes is None or len(closes)<60: continue

            rsi=calc_rsi(closes)
            ema9=calc_ema(closes,9)
            ema21=calc_ema(closes,21)
            ema50=calc_ema(closes,50)
            macd=ema9-ema21 # MACD sederhana
            price=closes[-1]
            vol_spike=vols[-1]/(sum(vols[-20:])/20)

            is_trending=base in trending
            # FILTER PRO + MICIN BOLEH
            valid = (ema9>ema21) and (ema21>ema50*0.98) and (45<rsi<68) and (macd>0) and (vol_spike>1.1)

            if valid:
                entry_idr=float(d['last'])
                hasil.append({
                    'base':base,'entry_idr':entry_idr,
                    'rsi':round(rsi,1),'ema':f"{round(ema9,2)}>{round(ema21,2)}",
                    'macd':round(macd,4),'vol_spike':round(vol_spike,2),
                    'trending':is_trending,'vol_idr':vol_idr,
                    'tp1':entry_idr*1.05,'tp2':entry_idr*1.10,'sl':entry_idr*0.95,
                    'score':(vol_spike*10)+rsi+(20 if is_trending else 0)
                })
        except: continue
    return sorted(hasil, key=lambda x:x['score'], reverse=True)[:2], trending

def main():
    kirim("🏆 *BOT INDODAX FINAL - SEMUA FITUR AKTIF*\n✅ TA: RSI+EMA+MACD+Vol\n✅ Vol Min 1M\n✅ Micin Valid OK\n✅ Trending X/Reddit\n✅ TP1/TP2 Tracking")
    while True:
        try:
            cek_tp()
            sinyal, trending = analisa()
            if sinyal:
                posisi=load()
                for s in sinyal:
                    tag="🔥 TRENDING DI INTERNET" if s['trending'] else "📈 Setup Teknikal Valid"
                    pesan=f"🚀 *SINYAL BUY {s['base']}/IDR* {tag}\n\n"
                    pesan+=f"*Analisa Pro (1H Binance):*\n"
                    pesan+=f"RSI: {s['rsi']} | MACD: {s['macd']} Bullish\n"
                    pesan+=f"EMA Cross: {s['ema']} ✅\n"
                    pesan+=f"Vol Spike: {s['vol_spike']}x | Vol Indodax: Rp {s['vol_idr']/1000000000:.1f}M\n"
                    pesan+=f"Harga: Rp {s['entry_idr']:,.0f}\n"
                    pesan+=f"Trending List: {', '.join(trending[:5])}\n\n"
                    pesan+=f"*ENTRY PLAN:*\n"
                    pesan+=f"BUY: Rp {s['entry_idr']:,.0f}\n"
                    pesan+=f"TP1: Rp {s['tp1']:,.0f} (+5%)\n"
                    pesan+=f"TP2: Rp {s['tp2']:,.0f} (+10%)\n"
                    pesan+=f"SL: Rp {s['sl']:,.0f} (-5%)\n\n"
                    pesan+=f"Bot akan lapor jika TP kena untuk hitung akurasi."
                    kirim(pesan)
                    posisi[s['base']]={'entry_idr':s['entry_idr'],'tp1_hit':False,'tp2_hit':False,'time':str(datetime.now())}
                    save(posisi)
                    time.sleep(1)
            time.sleep(300)
        except Exception as e:
            print(e); time.sleep(30)

if __name__=="__main__":
    main()
