import os, time, json, requests, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timedelta, timezone
print("BOT V6.5 HYBRID START...", flush=True)
TOKEN=os.getenv("BOT_TOKEN"); CHAT_ID=os.getenv("CHAT_ID")
FILE_POS="posisi.json"; FILE_COOLDOWN="cooldown.json"; FILE_LAST="last_update.json"

def now(): return datetime.now(timezone.utc)+timedelta(hours=7)
def jam(): return now().strftime("%H:%M WIB")

class H(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK V6.5")
    def log_message(self,*a): return
threading.Thread(target=lambda: HTTPServer(("0.0.0.0",int(os.getenv("PORT",8080))),H).serve_forever(),daemon=True).start()

def send(txt):
    try:
        r=requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",data={"chat_id":CHAT_ID,"text":txt,"parse_mode":"Markdown"},timeout=20)
        print(f"SEND TELE {r.status_code} {r.text[:100]}",flush=True)
        return r.status_code==200
    except Exception as e:
        print(f"SEND ERR {e}",flush=True)
        return False

def load(f,d):
    try: return json.load(open(f,'r'))
    except: return d
def save(f,d):
    try: json.dump(d,open(f,'w'))
    except: pass

def get_tickers():
    try: return requests.get("https://indodax.com/api/tickers",timeout=20).json()['tickers']
    except: return {}

def get_ob(base):
    try:
        d=requests.get(f"https://indodax.com/api/{base.lower()}_idr/depth",timeout=8).json()
        bids=d.get('buy',[])[:15]; asks=d.get('sell',[])[:15]
        if not bids or not asks: return {'buy':1,'sell':0,'buy_m':1,'sell_m':0,'ratio':1}
        tb=sum(float(p)*float(v) for p,v in bids); ts=sum(float(p)*float(v) for p,v in asks)
        return {'buy':tb,'sell':ts,'buy_m':tb,'sell_m':ts,'ratio':tb/ts if ts else 1}
    except: return {'buy':1,'sell':0,'buy_m':1,'sell_m':0,'ratio':1}

def get_candle_confirm(base):
    # Cek konfirmasi candle sebelumnya via trades terakhir
    try:
        # Ambil trades 1 jam terakhir
        tr=requests.get(f"https://indodax.com/api/{base.lower()}_idr/trades",timeout=8).json().get('trades',[])[:20]
        if len(tr)<5: return {'bull':True,'note':'no data'} # anggap bullish kalau data minim
        closes=[float(x['price']) for x in tr]
        # Jika 60% trades terakhir naik = bullish
        naik=sum(1 for i in range(1,len(closes)) if closes[i-1] < closes[0]) # simplifikasi
        # Cek harga terakhir vs rata2
        last=closes[0]; avg=sum(closes)/len(closes)
        bull=last >= avg  # close di atas rata2 = konfirmasi naik
        return {'bull':bull,'note':'BULL' if bull else 'BEAR','last':last,'avg':avg}
    except:
        return {'bull':True,'note':'API ERR - anggap BULL'}

def analisa():
    tickers=get_tickers()
    pos=load(FILE_POS,{}); cooldown=load(FILE_COOLDOWN,{})
    for k in list(cooldown.keys()):
        try:
            if now()-datetime.fromisoformat(cooldown[k])>timedelta(hours=1): del cooldown[k]
        except: del cooldown[k]
    save(FILE_COOLDOWN,cooldown)

    cands=[]
    for pid,d in tickers.items():
        if not pid.endswith('_idr'): continue
        base=pid.split('_')[0].upper()
        if base in pos or base in cooldown or base in ['USDT','USDC','IDR']: continue
        try:
            last=float(d['last']); low=float(d['low']); high=float(d['high']); vol=float(d['vol_idr'])
            if low==0 or vol<50_000_000: continue
            gain=(last-low)/low*100
            pos_p=(last-low)/(high-low)*100 if high!=low else 50
            if gain<0.8: continue # sangat longgar
            cands.append((base,last,low,high,gain,pos_p,vol))
        except: continue

    cands=sorted(cands,key=lambda x:x[4],reverse=True)[:30]
    print(f"SCAN HYBRID {jam()}: {len(cands)} kandidat",flush=True)

    scored=[]
    for base,last,low,high,gain,pos_p,vol in cands:
        ob=get_ob(base)
        candle=get_candle_confirm(base)

        # LOGIKA BARU YANG KAMU MAU
        buy_sell_ok = ob['buy'] > ob['sell']
        candle_ok = candle['bull']

        # LOLOS JIKA: (Buy>Sell) + (Candle Bull) = tidak peduli TA
        # ATAU cuma Buy>Sell saja juga lolos dengan score lebih kecil
        if buy_sell_ok and candle_ok:
            score=75; mode="KONFIRM NAIK"
            status=f"OB BUY>SELL + CANDLE {candle['note']}"
        elif buy_sell_ok:
            score=65; mode="BUY DOMINAN"
            status=f"OB BUY>SELL (candle {candle['note']})"
        else:
            # Kalau Sell>Buy tapi candle bullish kuat, tetap kasih kesempatan
            if candle_ok and gain>3:
                score=60; mode="CANDLE BULL"
                status=f"SELL>BUY tapi CANDLE {candle['note']}"
            else:
                print(f"SKIP {base} Sell>Buy + Bear",flush=True)
                continue

        print(f"OK {base} {mode} +{gain:.1f}% {status} Buy {ob['buy_m']/1e6:.0f}M Sell {ob['sell_m']/1e6:.0f}M",flush=True)
        scored.append({'base':base,'mode':mode,'entry':last,'gain':gain,'pos':pos_p,'vol':vol,'tp':last*1.05,'sl':last*0.95,'ob':ob,'status':status,'score':score})

        if len(scored)>=5: break

    # JIKA MASIH 0 KARENA SEMUA SELL>BUY, PAKSA AMBIL 5 TERATAS TANPA FILTER OB
    if not scored and cands:
        print(f"FORCED: Semua Sell>Buy, paksa ambil 5 gainers teratas",flush=True)
        for base,last,low,high,gain,pos_p,vol in cands[:5]:
            ob=get_ob(base)
            scored.append({'base':base,'mode':'FORCED GAINERS','entry':last,'gain':gain,'pos':pos_p,'vol':vol,'tp':last*1.05,'sl':last*0.95,'ob':ob,'status':'FORCED','score':55})

    return scored

def main():
    time.sleep(1)
    ok=send(f"✅ *BOT V6.5 HYBRID AKTIF - {jam()}*\nLogika: OB Buy>Sell + Candle Bull = Lolos\nWalau TA belum sempurna")
    print(f"INIT SEND {ok}",flush=True)
    while True:
        try:
            sig=analisa()
            if sig:
                msg=f"🏆 *{len(sig)} SINYAL HYBRID - {jam()}*\n"
                for i,s in enumerate(sig,1): msg+=f"#{i} {s['base']} +{s['gain']:.1f}% {s['mode']}\n"
                send(msg); time.sleep(1)
                pos=load(FILE_POS,{}); cooldown=load(FILE_COOLDOWN,{})
                for i,s in enumerate(sig,1):
                    if s['base'] in pos: continue
                    ob=s['ob']
                    txt=f"#{i} *{s['mode']}* {s['base']}/IDR +{s['gain']:.1f}% SCORE {s['score']}\n{s['status']}\nBUY Rp {ob['buy_m']/1e6:.0f}M vs SELL Rp {ob['sell_m']/1e6:.0f}M\nPos {s['pos']:.0f}% Vol {s['vol']/1e6:.0f}M\nENTRY {s['entry']:,.0f}\nTP {s['tp']:,.0f} (+5%) SL {s['sl']:,.0f} - {jam()}"
                    send(txt); pos[s['base']]=s['entry']; save(FILE_POS,pos); cooldown[s['base']]=now().isoformat(); save(FILE_COOLDOWN,cooldown); time.sleep(1)
            time.sleep(90)
        except Exception as e:
            print(f"ERR {e}",flush=True); time.sleep(20)

if __name__=="__main__": main()
