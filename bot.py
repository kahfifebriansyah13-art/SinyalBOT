import os, time, json, requests, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timedelta, timezone

print("BOT V8.4-DUAL-OB10-FIX...", flush=True)
TOKEN=os.getenv("BOT_TOKEN")
CHAT_ID=os.getenv("CHAT_ID")

FILE_POS="posisi.json"; FILE_COOLDOWN="cooldown.json"; FILE_HISTORY="history.json"; FILE_LAST="last_update.json"; FILE_STATS="stats.json"

def now(): return datetime.now(timezone.utc)+timedelta(hours=7)
def jam(): return now().strftime("%H:%M WIB")

class H(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK FIX")
    def log_message(self,*a): return

threading.Thread(target=lambda: HTTPServer(("0.0.0.0",int(os.getenv("PORT",8080))),H).serve_forever(),daemon=True).start()

def send(txt):
    try:
        requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",data={"chat_id":CHAT_ID,"text":txt,"parse_mode":"Markdown"},timeout=15)
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
    return f"{m:.0f}"

HEADERS={"User-Agent":"Mozilla/5.0"}

def get_data():
    try:
        r=requests.get("https://indodax.com/api/summaries",timeout=15,headers=HEADERS).json()
        return r.get('tickers',{}), {}
    except: return {}, {}

def get_12h(last, low):
    try:
        gain=(last-low)/low*100 if low else 0
        return gain*0.6
    except: return 0

def get_ob(base):
    try:
        rr=requests.get(f"https://indodax.com/api/{base.lower()}_idr/depth",timeout=8,headers=HEADERS).json()
        bids=rr.get('buy',[]); asks=rr.get('sell',[])
        if not bids or not asks: return None
        tb=0; ts=0
        for p,q in bids[:10]: tb+=float(p)*float(q)
        for p,q in asks[:10]: ts+=float(p)*float(q)
        spread=(float(asks[0][0])-float(bids[0][0]))/float(bids[0][0])*100
        ratio=tb/ts if ts>0 else 0
        return {'buy':tb,'sell':ts,'buy_m':tb,'sell_m':ts,'spread':spread,'ratio':ratio}
    except:
        return None

def get_candle(base):
    try:
        tr=requests.get(f"https://indodax.com/api/{base.lower()}_idr/trades",timeout=8,headers=HEADERS).json().get('trades',[])[:20]
        last=float(tr[0]['price'])
        avg=sum(float(x['price']) for x in tr)/len(tr)
        bull=last>=avg
        ch=(last-avg)/avg*100 if avg else 0
        return {'bull':bull,'note':'Candle Bull' if bull else 'Candle Bear','change':ch}
    except:
        return {'bull':True,'note':'Candle Bull','change':0}

def analisa():
    tickers,_=get_data()
    if not tickers: return []
    pos=load(FILE_POS,{}); cooldown=load(FILE_COOLDOWN,{})
    for k in list(cooldown.keys()):
        try:
            if now()-datetime.fromisoformat(cooldown[k])>timedelta(hours=3): del cooldown[k]
        except: del cooldown[k]
    save(FILE_COOLDOWN,cooldown)

    cands_aman=[]; cands_high=[]
    log_total=0; log_vol=0; log_pos=0; log_gain=0; log_12h=0; log_ob=0; log_candle=0

    for pid,d in tickers.items():
        if not pid.endswith('_idr'): continue
        base=pid.split('_')[0].upper()
        if base in pos or base in cooldown or base in ['USDT','USDC','IDR','DAI']: continue
        try:
            last=float(d['last']); low=float(d['low']); high=float(d['high']); vol=float(d['vol_idr'])
            log_total+=1
            if vol<100_000_000: log_vol+=1; continue
            pos_p=(last-low)/(high-low)*100 if high!=low else 0
            is_aman=65<=pos_p<=85
            is_high=85<pos_p<=100
            if not (is_aman or is_high): log_pos+=1; continue
            gain_low=(last-low)/low*100 if low else 0
            if gain_low<1 or gain_low>15: log_gain+=1; continue
            ch12=get_12h(last,low)
            if ch12<0.5 or ch12>10: log_12h+=1; continue
            ob=get_ob(base)
            if ob is None: log_ob+=1; continue
            if ob['buy'] < ob['sell']*0.8: log_ob+=1; continue
            candle=get_candle(base)
            if not candle['bull']: log_candle+=1; continue
            data=(base,last,low,high,gain_low,pos_p,vol,ch12,ob,candle)
            if is_aman: cands_aman.append(data)
            else: cands_high.append(data)
        except: continue

    print(f"SCAN FIX OB10 {jam()}: Total {log_total} | Vol {log_vol} | Pos {log_pos} | Gain {log_gain} | 12H {log_12h} | OB10 {log_ob} | Candle {log_candle} | AMAN {len(cands_aman)} HIGH {len(cands_high)}",flush=True)
    scored=[]
    for base,last,low,high,gain_low,pos_p,vol,ch12,ob,candle in sorted(cands_aman,key=lambda x:x[5],reverse=True)[:3]:
        scored.append({'base':base,'mode_label':'🛡️ MODE AMAN','mode':'KOREKSI','trend':'Bullish','entry':last,'gain':gain_low,'pos':pos_p,'vol':vol,'tp':last*1.05,'sl':last*0.95,'ob':ob,'candle':candle,'score':80,'change12':ch12})
    for base,last,low,high,gain_low,pos_p,vol,ch12,ob,candle in sorted(cands_high,key=lambda x:x[5],reverse=True)[:3]:
        scored.append({'base':base,'mode_label':'🚀 MODE HIGH','mode':'Pucuk','trend':'Bullish High','entry':last,'gain':gain_low,'pos':pos_p,'vol':vol,'tp':last*1.05,'sl':last*0.95,'ob':ob,'candle':candle,'score':90,'change12':ch12})
    return scored

def fmt_tmg(s,r):
    ob=s['ob']
    return f"#{r} {s['mode_label']} {s['base']}/IDR | {s['mode']} Pos {s['pos']:.0f}% | 12H {s['change12']:.2f}% | OB10 Buy {fmt_money(ob['buy_m'])} vs {fmt_money(ob['sell_m'])} R {ob['ratio']:.2f}x | ENTRY {fmt_price(s['entry'])} TP {fmt_price(s['tp'])}"

def cek_tp():
    tickers,_=get_data()
   
