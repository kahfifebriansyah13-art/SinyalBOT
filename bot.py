import os, time, json, requests, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timedelta, timezone
print("BOT V6.6 TMG FORMAT START...", flush=True)
TOKEN=os.getenv("BOT_TOKEN"); CHAT_ID=os.getenv("CHAT_ID")
FILE_POS="posisi.json"; FILE_COOLDOWN="cooldown.json"; FILE_HISTORY="history.json"; FILE_LAST="last_update.json"

def now(): return datetime.now(timezone.utc)+timedelta(hours=7)
def jam(): return now().strftime("%H:%M WIB")

class H(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK V6.6 TMG")
    def log_message(self,*a): return
threading.Thread(target=lambda: HTTPServer(("0.0.0.0",int(os.getenv("PORT",8080))),H).serve_forever(),daemon=True).start()

def send(txt):
    try: 
        r=requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",data={"chat_id":CHAT_ID,"text":txt,"parse_mode":"Markdown"},timeout=20)
        print(f"SEND {r.status_code}",flush=True); return True
    except Exception as e: print(f"SEND ERR {e}",flush=True); return False

def load(f,d):
    try: return json.load(open(f,'r'))
    except: return d
def save(f,d):
    try: json.dump(d,open(f,'w'))
    except: pass

def fmt_price(p):
    p=float(p)
    if p>=1000: return f"Rp {p:,.0f}"
    if p>=1: return f"Rp {p:,.2f}"
    if p>=0.01: return f"Rp {p:,.4f}"
    return f"Rp {p:.8f}".rstrip('0')

def get_tickers():
    try: return requests.get("https://indodax.com/api/tickers",timeout=20).json()['tickers']
    except: return {}

def get_ob(base):
    try:
        data=requests.get(f"https://indodax.com/api/{base.lower()}_idr/depth",timeout=10).json()
        bids=data.get('buy',[]); asks=data.get('sell',[])
        if not bids or not asks: return {'buy':0,'sell':0,'buy_m':0,'sell_m':0,'spread':99,'ratio':0}
        tb=sum(float(p)*float(q) for p,q in bids[:20]); ts=sum(float(p)*float(q) for p,q in asks[:20])
        spread=(float(asks[0][0])-float(bids[0][0]))/float(bids[0][0])*100
        return {'buy':tb,'sell':ts,'buy_m':tb,'sell_m':ts,'spread':spread,'ratio':tb/ts if ts else 9}
    except Exception as e:
        print(f"OB ERR {base} {e}",flush=True)
        return {'buy':0,'sell':0,'buy_m':0,'sell_m':0,'spread':0,'ratio':0}

def get_candle(base):
    try:
        tr=requests.get(f"https://indodax.com/api/{base.lower()}_idr/trades",timeout=8).json().get('trades',[])[:10]
        if not tr: return {'bull':True,'note':'Candle Bull'}
        last=float(tr[0]['price']); avg=sum(float(x['price']) for x in tr)/len(tr)
        bull=last>=avg
        return {'bull':bull,'note':'Candle Bull ✅' if bull else 'Candle Bear'}
    except: return {'bull':True,'note':'Candle Bull ✅'}

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
            gain=(last-low)/low*100; pos_p=(last-low)/(high-low)*100 if high!=low else 50
            if gain<1: continue
            cands.append((base,last,low,high,gain,pos_p,vol))
        except: continue

    cands=sorted(cands,key=lambda x:x[4],reverse=True)[:30]
    print(f"SCAN TMG {jam()}: {len(cands)} kandidat",flush=True)
    scored=[]
    for base,last,low,high,gain,pos_p,vol in cands:
        ob=get_ob(base); candle=get_candle(base)
        if ob['buy']==0 and ob['sell']==0: 
            print(f"SKIP {base} OB 0",flush=True); continue
        buy_ok=ob['buy']>ob['sell']
        if not (buy_ok and candle['bull']): 
            if not buy_ok: continue # WAJIB BUY>SELL sesuai maumu
        # MODE TMG
        if pos_p>=60: mode="🚀 BREAKOUT"; trend="Bullish Kuat"
        elif pos_p>=35: mode="🩹 KOREKSI SEHAT"; trend="Bullish"
        else: mode="🔄 REVERSAL AWAL"; trend="Mulai Rebound"
        score=75 if buy_ok and candle['bull'] else 65
        print(f"OK {base} {mode} +{gain:.1f}% Buy {ob['buy_m']/1e6:.1f}M",flush=True)
        scored.append({'base':base,'mode':mode,'trend':trend,'entry':last,'gain':gain,'pos':pos_p,'vol':vol,'tp':last*1.05,'sl':last*0.95,'ob':ob,'candle':candle,'score':score})
        if len(scored)>=5: break
    return scored

def fmt_tmg(s,r):
    ob=s['ob']; candle=s['candle']
    return f"""╔═══ #{r} {s['mode']} {s['base']}/IDR SCORE {s['score']} ═══╗
║ 🔥 {s['trend']} | {candle['note']} - Pos {s['pos']:.0f}%
║ 📈 Naik {s['gain']:.2f}% Vol Rp {s['vol']/1e6:.0f}M
╠═══════════════════════════╣
║ 💰 OB {s['score']>=70 and 'BUY>SELL ✅' or 'BUY>SELL'}
║ 💵 Buy Rp {ob['buy_m']/1e6:.1f}M vs Sell Rp {ob['sell_m']/1e6:.1f}M
║ 📊 Ratio {ob['ratio']:.2f}x Spread {ob['spread']:.2f}%
╠═══════════════════════════╣
║ 🎯 TP +5% - {jam()}
║ 🟢 ENTRY {fmt_price(s['entry'])}
║ 🎯 TP {fmt_price(s['tp'])} (+5%)
║ 🔴 SL {fmt_price(s['sl'])} (-5%)
╚═══════════════════════════╝"""

def handle():
    try:
        last_id=load(FILE_LAST,{"id":0})["id"]
        r=requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={last_id+1}&timeout=5",timeout=10).json()
        for u in r.get('result',[]):
            save(FILE_LAST,{"id":u['update_id']})
            txt=u.get('message',{}).get('text','').lower().strip()
            if txt=='/clear': save(FILE_POS,{}); save(FILE_COOLDOWN,{}); send(f"✅ Reset - {jam()}")
            if txt in ['/winrate','/profit','/stats']:
                hist=load(FILE_HISTORY,[]); pos=load(FILE_POS,{})
                win=sum(1 for h in hist if h.get('pnl','')=='WIN'); loss=sum(1 for h in hist if h.get('pnl','')=='LOSS')
                total=win+loss; wr=win/total*100 if total else 0
                send(f"📊 *WINRATE {jam()}*\nWIN {win} LOSS {loss} Total {total}\nWR {wr:.1f}%\nPosisi aktif: {len(pos)}")
    except: pass

def main():
    time.sleep(1); send(f"✅ *BOT V6.6 TMG FORMAT AKTIF - {jam()}*\nFormat TMG + OB Buy>Sell + Candle Bull")
    loop=0
    while True:
        try:
            if loop%2==0: handle()
            if loop%3==0:
                sig=analisa()
                if sig:
                    msg=f"🏆 *{len(sig)} SINYAL TMG - {jam()}*\n"
                    for i,s in enumerate(sig,1): msg+=f"#{i} {s['base']} +{s['gain']:.1f}% {s['mode']}\n"
                    send(msg); time.sleep(1)
                    pos=load(FILE_POS,{}); cooldown=load(FILE_COOLDOWN,{}); hist=load(FILE_HISTORY,[])
                    for i,s in enumerate(sig,1):
                        if s['base'] in pos: continue
                        send(fmt_tmg(s,i))
                        pos[s['base']]=s['entry']; save(FILE_POS,pos)
                        cooldown[s['base']]=now().isoformat(); save(FILE_COOLDOWN,cooldown)
                        hist.append({'base':s['base'],'entry':s['entry'],'time':now().isoformat()}); save(FILE_HISTORY,hist)
                        time.sleep(1)
            loop+=1; time.sleep(30)
        except Exception as e:
            print(f"ERR {e}",flush=True); time.sleep(15)

if __name__=="__main__": main()
