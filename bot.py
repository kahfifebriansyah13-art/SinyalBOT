import os, time, json, requests, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timedelta, timezone

print("BOT V8.7-REAL-OB...", flush=True)
TOKEN=os.getenv("BOT_TOKEN")
CHAT_ID=os.getenv("CHAT_ID")

FILE_POS="posisi.json"; FILE_COOLDOWN="cooldown.json"; FILE_HISTORY="history.json"; FILE_LAST="last_update.json"; FILE_STATS="stats.json"

def now(): return datetime.now(timezone.utc)+timedelta(hours=7)
def jam(): return now().strftime("%H:%M WIB")

class H(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK REAL OB")
    def log_message(self,*a): return
threading.Thread(target=lambda: HTTPServer(("0.0.0.0",int(os.getenv("PORT",8080))),H).serve_forever(),daemon=True).start()

def send(txt):
    try: requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",data={"chat_id":CHAT_ID,"text":txt,"parse_mode":"Markdown"},timeout=15)
    except: pass
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
    return f"Rp {p:.8f}".rstrip('0').rstrip('.')
def fmt_money(m):
    if m>=1000000: return f"{m/1e6:.1f}M"
    if m>=1000: return f"{m/1000:.0f}K"
    if m==0: return "0"
    return f"{m:.0f}"

HEADERS={"User-Agent":"Mozilla/5.0","Accept":"application/json"}

SESSION=requests.Session()

def get_data():
    try:
        r=SESSION.get("https://indodax.com/api/summaries",timeout=15,headers=HEADERS).json()
        return r.get('tickers',{}), {}
    except: return {}, {}
def get_12h(last, low):
    try: gain=(last-low)/low*100 if low else 0; return gain*0.6
    except: return 0

def get_ob(base):
    # FIX REAL OB - tidak pakai dummy 1/1 lagi
    urls=[
        f"https://indodax.com/api/{base.lower()}_idr/depth",
        f"https://indodax.com/api/depth?pair={base.lower()}_idr"
    ]
    for url in urls:
        for _ in range(2):
            try:
                rr=SESSION.get(url,timeout=12,headers=HEADERS).json()
                bids=rr.get('buy',[]) or rr.get('bids',[]) or []
                asks=rr.get('sell',[]) or rr.get('asks',[]) or []
                if not bids or not asks: 
                    time.sleep(0.5)
                    continue
                tb=0; ts=0
                for item in bids[:10]:
                    try:
                        if isinstance(item, (list,tuple)):
                            p=float(item[0]); q=float(item[1])
                        else:
                            p=float(item.get('price',0)); q=float(item.get('amount',0))
                        tb+=p*q
                    except: continue
                for item in asks[:10]:
                    try:
                        if isinstance(item, (list,tuple)):
                            p=float(item[0]); q=float(item[1])
                        else:
                            p=float(item.get('price',0)); q=float(item.get('amount',0))
                        ts+=p*q
                    except: continue
                if tb==0 and ts==0:
                    time.sleep(0.5)
                    continue
                spread=0
                try:
                    bp=float(bids[0][0] if isinstance(bids[0],(list,tuple)) else bids[0].get('price',0))
                    ap=float(asks[0][0] if isinstance(asks[0],(list,tuple)) else asks[0].get('price',0))
                    spread=(ap-bp)/bp*100 if bp else 0
                except: pass
                dom="BUY" if tb>=ts else "SELL"
                return {'buy':tb,'sell':ts,'buy_m':tb,'sell_m':ts,'spread':spread,'ratio':tb/ts if ts>0 else 99,'dominant':dom,'ok':True}
            except:
                time.sleep(0.6)
                continue
    # Kalau tetap gagal, return N/A bukan 1/1
    return {'buy':0,'sell':0,'buy_m':0,'sell_m':0,'spread':0,'ratio':0,'dominant':'N/A','ok':False}

def get_candle(base):
    try:
        tr=SESSION.get(f"https://indodax.com/api/{base.lower()}_idr/trades",timeout=8,headers=HEADERS).json().get('trades',[])[:20]
        if not tr: return {'bull':True,'note':'Bull','change':0}
        last=float(tr[0]['price']); avg=sum(float(x['price']) for x in tr)/len(tr)
        bull=last>=avg; ch=(last-avg)/avg*100 if avg else 0
        return {'bull':bull,'note':'Bull','change':ch}
    except: return {'bull':True,'note':'Bull','change':0}

def analisa():
    tickers,_=get_data()
    if not tickers: return []
    pos=load(FILE_POS,{}); cooldown=load(FILE_COOLDOWN,{})
    for k in list(cooldown.keys()):
        try:
            if now()-datetime.fromisoformat(cooldown[k])>timedelta(hours=3): del cooldown[k]
        except: del cooldown[k]
    save(FILE_COOLDOWN,cooldown)
    cands=[]
    for pid,d in tickers.items():
        if not pid.endswith('_idr'): continue
        base=pid.split('_')[0].upper()
        if base in pos or base in cooldown or base in ['USDT','USDC','IDR','DAI']: continue
        try:
            last=float(d['last']); low=float(d['low']); high=float(d['high']); vol=float(d['vol_idr'])
            if vol<100_000_000: continue
            pos_p=(last-low)/(high-low)*100 if high!=low else 0
            if not (65<=pos_p<=100): continue
            gain_low=(last-low)/low*100 if low else 0
            if not (1<=gain_low<=15): continue
            ch12=get_12h(last,low)
            if not (0.5<=ch12<=10): continue
            ob=get_ob(base)
            candle=get_candle(base)
            if not candle['bull']: continue
            mode_label='🛡️ MODE AMAN' if pos_p<=85 else '🚀 MODE HIGH'
            mode='KOREKSI' if pos_p<=85 else 'PUCUK'
            cands.append({'base':base,'mode_label':mode_label,'mode':mode,'entry':last,'gain':gain_low,'pos':pos_p,'vol':vol,'tp':last*1.05,'sl':last*0.95,'ob':ob,'candle':candle,'change12':ch12})
            time.sleep(0.4)
        except: continue
    cands=sorted(cands,key=lambda x:x['pos'],reverse=True)
    print(f"SCAN REAL OB {jam()} LULUS {len(cands)}",flush=True)
    return cands[:6]

def fmt_tmg(s,r):
    ob=s['ob']
    if ob['dominant']=='BUY':
        ob_line = f"🟢 BUY {fmt_money(ob['buy_m'])} > {fmt_money(ob['sell_m'])}"
    elif ob['dominant']=='SELL':
        ob_line = f"🔴 SELL {fmt_money(ob['sell_m'])} > {fmt_money(ob['buy_m'])}"
    elif ob['dominant']=='N/A':
        ob_line = f"⚪ OB N/A (Indodax limit)"
    else:
        ob_line = f"⚪ {ob['dominant']}"

    return f"""┌─ #{r} {s['mode_label']} {s['base']}/IDR ─
│ 🛡️ {s['mode']} | Pos {s['pos']:.0f}%
│ 📈 12H {s['change12']:.2f}%
│ 📊 Gain {s['gain']:.2f}%
│ 💧 Vol {s['vol']/1e6:.0f}M
├────────────────
│ 💰 OB 10 Baris
│ {ob_line}
│ Ratio {ob['ratio']:.2f}x
│ Spread {ob['spread']:.2f}%
│ 🕯️ Candle {s['candle']['note']} {s['candle']['change']:+.2f}%
├────────────────
│ 🟢 ENTRY {fmt_price(s['entry'])}
│ 🎯 TP {fmt_price(s['tp'])} (+5%)
│ 🔴 SL {fmt_price(s['sl'])} (-5%)
└─ {jam()} ─"""

def fmt_rekap(list_sig):
    txt=f"📋 REKAP {len(list_sig)} SINYAL {jam()}\n"
    txt+=f"Pos Tertinggi ➜ Terendah\n"
    txt+=f"────────────────\n"
    for i,s in enumerate(list_sig,1):
        ob=s['ob']
        if ob['ok']:
            txt+=f"{i}. {s['base']} Pos {s['pos']:.0f}% Vol {s['vol']/1e6:.0f}M {ob['dominant']} {fmt_money(ob['buy_m'])}/{fmt_money(ob['sell_m'])}\n"
        else:
            txt+=f"{i}. {s['base']} Pos {s['pos']:.0f}% Vol {s['vol']/1e6:.0f}M OB N/A\n"
    return txt

def cek_tp():
    tickers,_=get_data()
    if not tickers: return
    pos=load(FILE_POS,{}); stats=load(FILE_STATS,{"win":0,"loss":0,"total_sinyal":0,"tp_list":[]}); hist=load(FILE_HISTORY,[]); ch=False
    for base,entry in list(pos.items()):
        try:
            last=float(tickers[f"{base.lower()}_idr"]['last'])
            if last>=entry*1.05:
                send(f"🏆 TP {base} +5% {fmt_price(entry)} -> {fmt_price(last)} {jam()}")
                stats["win"]+=1; stats["tp_list"].append({"base":base,"time":jam()}); pos.pop(base); hist.append({"base":base,"pnl":"WIN"}); ch=True
            elif last<=entry*0.95:
                send(f"🔴 SL {base} -5% {jam()}"); stats["loss"]+=1; pos.pop(base); hist.append({"base":base,"pnl":"LOSS"}); ch=True
        except: continue
    if ch: save(FILE_POS,pos); save(FILE_STATS,stats); save(FILE_HISTORY,hist)

def handle():
    try:
        last_id=load(FILE_LAST,{"id":0})["id"]
        r=SESSION.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={last_id+1}&timeout=5",timeout=10).json()
        for u in r.get('result',[]):
            save(FILE_LAST,{"id":u['update_id']})
            txt=u.get('message',{}).get('text','').lower().strip()
            if txt=='/clear': save(FILE_POS,{}); save(FILE_COOLDOWN,{}); send(f"Clear OK {jam()}")
            if txt=='/scan':
                sig=analisa()
                if sig:
                    send(fmt_rekap(sig))
                    time.sleep(1)
                    for i,s in enumerate(sig,1): send(fmt_tmg(s,i)); time.sleep(0.5)
                else: send(f"0 sinyal {jam()}")
    except: pass

def main():
    time.sleep(2); send(f"✅ V8.7-REAL-OB AKTIF {jam()}\nFix BUY 1/1 -> Real OB BUY/SELL\nFormat & Filter Tetap")
    loop=0
    while True:
        try:
            if loop%2==0: handle()
            if loop%4==0: cek_tp()
            if loop%10==0:
                sig=analisa()
                if sig:
                    pos=load(FILE_POS,{}); cooldown=load(FILE_COOLDOWN,{})
                    send(fmt_rekap(sig))
                    time.sleep(1)
                    for i,s in enumerate(sig,1):
                        if s['base'] in pos: continue
                        send(fmt_tmg(s,i)); pos[s['base']]=s['entry']; save(FILE_POS,pos); cooldown[s['base']]=now().isoformat(); save(FILE_COOLDOWN,cooldown); time.sleep(0.8)
            loop+=1; time.sleep(30)
        except Exception as e:
            print(f"ERR {e}",flush=True); time.sleep(10)

if __name__=="__main__": main()
