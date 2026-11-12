import os, time, json, requests, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timedelta, timezone

print("BOT V8.5-OB-INFO...", flush=True)
TOKEN=os.getenv("BOT_TOKEN")
CHAT_ID=os.getenv("CHAT_ID")

FILE_POS="posisi.json"; FILE_COOLDOWN="cooldown.json"; FILE_HISTORY="history.json"; FILE_LAST="last_update.json"; FILE_STATS="stats.json"

def now(): return datetime.now(timezone.utc)+timedelta(hours=7)
def jam(): return now().strftime("%H:%M WIB")

class H(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK OB-INFO")
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
    return f"{m:.0f}"

HEADERS={"User-Agent":"Mozilla/5.0"}

def get_data():
    try:
        r=requests.get("https://indodax.com/api/summaries",timeout=15,headers=HEADERS).json()
        return r.get('tickers',{}), {}
    except: return {}, {}
def get_12h(last, low):
    try: gain=(last-low)/low*100 if low else 0; return gain*0.6
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
        dom="BUY" if tb>ts else "SELL"
        return {'buy':tb,'sell':ts,'buy_m':tb,'sell_m':ts,'spread':spread,'ratio':tb/ts if ts else 0,'dominant':dom}
    except: return None

def get_candle(base):
    try:
        tr=requests.get(f"https://indodax.com/api/{base.lower()}_idr/trades",timeout=8,headers=HEADERS).json().get('trades',[])[:20]
        last=float(tr[0]['price']); avg=sum(float(x['price']) for x in tr)/len(tr)
        bull=last>=avg; ch=(last-avg)/avg*100 if avg else 0
        return {'bull':bull,'note':'Candle Bull' if bull else 'Candle Bear','change':ch}
    except: return {'bull':True,'note':'Candle Bull','change':0}

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
    log_total=0; log_vol=0; log_pos=0; log_gain=0; log_12h=0; log_candle=0
    for pid,d in tickers.items():
        if not pid.endswith('_idr'): continue
        base=pid.split('_')[0].upper()
        if base in pos or base in cooldown or base in ['USDT','USDC','IDR','DAI']: continue
        try:
            last=float(d['last']); low=float(d['low']); high=float(d['high']); vol=float(d['vol_idr'])
            log_total+=1
            if vol<100_000_000: log_vol+=1; continue
            pos_p=(last-low)/(high-low)*100 if high!=low else 0
            is_aman=65<=pos_p<=85; is_high=85<pos_p<=100
            if not (is_aman or is_high): log_pos+=1; continue
            gain_low=(last-low)/low*100 if low else 0
            if gain_low<1 or gain_low>15: log_gain+=1; continue
            ch12=get_12h(last,low)
            if ch12<0.5 or ch12>10: log_12h+=1; continue
            ob=get_ob(base)
            if ob is None: ob={'buy':0,'sell':0,'buy_m':0,'sell_m':0,'spread':0,'ratio':0,'dominant':'UNKNOWN'}
            candle=get_candle(base)
            if not candle['bull']: log_candle+=1; continue
            data=(base,last,low,high,gain_low,pos_p,vol,ch12,ob,candle)
            if is_aman: cands_aman.append(data)
            else: cands_high.append(data)
        except: continue
    print(f"SCAN OB-INFO {jam()}: Total {log_total} | Vol {log_vol} | Pos {log_pos} | Gain {log_gain} | 12H {log_12h} | Candle {log_candle} | AMAN {len(cands_aman)} HIGH {len(cands_high)} LULUS {len(cands_aman)+len(cands_high)}",flush=True)
    scored=[]
    for base,last,low,high,gain_low,pos_p,vol,ch12,ob,candle in sorted(cands_aman,key=lambda x:x[5],reverse=True)[:3]:
        scored.append({'base':base,'mode_label':'🛡️ MODE AMAN','mode':'KOREKSI','trend':'Bullish','entry':last,'gain':gain_low,'pos':pos_p,'vol':vol,'tp':last*1.05,'sl':last*0.95,'ob':ob,'candle':candle,'score':80,'change12':ch12})
    for base,last,low,high,gain_low,pos_p,vol,ch12,ob,candle in sorted(cands_high,key=lambda x:x[5],reverse=True)[:3]:
        scored.append({'base':base,'mode_label':'🚀 MODE HIGH','mode':'PUCUK','trend':'Bullish High','entry':last,'gain':gain_low,'pos':pos_p,'vol':vol,'tp':last*1.05,'sl':last*0.95,'ob':ob,'candle':candle,'score':90,'change12':ch12})
    return scored

def fmt_tmg(s,r):
    ob=s['ob']
    dom_text = f"🟢 BUY Dominan {fmt_money(ob['buy_m'])} > {fmt_money(ob['sell_m'])}" if ob['dominant']=="BUY" else f"🔴 SELL Dominan {fmt_money(ob['sell_m'])} > {fmt_money(ob['buy_m'])}"
    return f"""╔═══ #{r} {s['mode_label']} {s['base']}/IDR ═══╗
║ {s['mode_label']} | {s['mode']} Pos {s['pos']:.0f}%
║ 📈 12H {s['change12']:.2f}% | Gain Low {s['gain']:.2f}% | Vol {s['vol']/1e6:.0f}M
╠═══════════════════════════╣
║ 💰 OB 10baris: {dom_text}
║ Ratio {ob['ratio']:.2f}x | Spread {ob['spread']:.2f}%
║ 🕯️ {s['candle']['note']} {s['candle']['change']:+.2f}%
╠═══════════════════════════╣
║ 🟢 ENTRY {fmt_price(s['entry'])}
║ 🎯 TP {fmt_price(s['tp'])} (+5%)
║ 🔴 SL {fmt_price(s['sl'])} (-5%) {jam()}
╚═══════════════════════════╝"""

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
        r=requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={last_id+1}&timeout=5",timeout=10).json()
        for u in r.get('result',[]):
            save(FILE_LAST,{"id":u['update_id']})
            txt=u.get('message',{}).get('text','').lower().strip()
            if txt=='/clear': save(FILE_POS,{}); save(FILE_COOLDOWN,{}); send(f"Clear OK {jam()}")
            if txt=='/scan':
                sig=analisa()
                if sig:
                    for i,s in enumerate(sig,1): send(fmt_tmg(s,i))
                else: send(f"0 sinyal {jam()}")
    except: pass

def main():
    time.sleep(2); send(f"✅ V8.5-OB-INFO AKTIF {jam()}\nOB tidak filter, cuma info BUY/SELL Dominan\nVol100 Gain1-15% Pos65-85 & 85-100% 12H0.5-10%")
    loop=0
    while True:
        try:
            if loop%2==0: handle()
            if loop%4==0: cek_tp()
            if loop%10==0:
                sig=analisa()
                if sig:
                    pos=load(FILE_POS,{}); cooldown=load(FILE_COOLDOWN,{})
                    for i,s in enumerate(sig,1):
                        if s['base'] in pos: continue
                        send(fmt_tmg(s,i)); pos[s['base']]=s['entry']; save(FILE_POS,pos); cooldown[s['base']]=now().isoformat(); save(FILE_COOLDOWN,cooldown); time.sleep(1)
            loop+=1; time.sleep(30)
        except Exception as e:
            print(f"ERR {e}",flush=True); time.sleep(10)

if __name__=="__main__": main()
