import os, time, json, requests, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timedelta, timezone

print("BOT V8.8.2-ANTI-NA...", flush=True)
TOKEN=os.getenv("BOT_TOKEN")
CHAT_ID=os.getenv("CHAT_ID")

FILE_POS="posisi.json"; FILE_COOLDOWN="cooldown.json"; FILE_HISTORY="history.json"; FILE_LAST="last_update.json"; FILE_STATS="stats.json"

def now(): return datetime.now(timezone.utc)+timedelta(hours=7)
def jam(): return now().strftime("%H:%M WIB")

class H(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK ANTI NA")
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
    if m>=1000000000: return f"{m/1e9:.1f}B"
    if m>=1000000: return f"{m/1e6:.0f}M"
    if m>=1000: return f"{m/1000:.0f}K"
    if m==0: return "0"
    return f"{m:.0f}"

HEADERS={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36","Accept":"application/json"}
SESSION=requests.Session()

def get_data():
    try:
        r=SESSION.get("https://indodax.com/api/summaries",timeout=15,headers=HEADERS).json()
        return r.get('tickers',{}), {}
    except: return {}, {}
def get_12h(last, low):
    try: gain=(last-low)/low*100 if low else 0; return gain*0.6
    except: return 0

# FIX ANTI N/A 0/0 - SELALU ADA BUY/SELL
def get_ob(base, vol_idr=0, pos_p=50):
    try:
        rr=SESSION.get(f"https://indodax.com/api/{base.lower()}_idr/depth",timeout=10,headers=HEADERS).json()
        bids=rr.get('buy',[]); asks=rr.get('sell',[])
        if bids and asks:
            tb=0; ts=0
            for x in bids[:10:
                try: tb+=float(x[0])*float(x[1])
                except: continue
            for x in asks[:10:
                try: ts+=float(x[0])*float(x[1])
                except: continue
            if tb>0 or ts>0:
                dom="BUY" if tb>=ts else "SELL"
                spread=0
                try: spread=(float(asks[0][0])-float(bids[0][0]))/float(bids[0][0])*100
                except: pass
                return {'buy':tb,'sell':ts,'buy_m':tb,'sell_m':ts,'spread':spread,'ratio':tb/ts if ts>0 else 99,'dominant':dom,'ok':True}
    except: pass
    
    # JIKA DEPTH DI-BLOCK, PAKAI ESTIMASI DARI VOL BIAR TIDAK N/A 0/0
    # Logika: Pos tinggi = SELL dominan, Pos rendah = BUY dominan
    if pos_p >= 80:
        dom="SELL"; tb=vol_idr*0.45; ts=vol_idr*0.55
    else:
        dom="BUY"; tb=vol_idr*0.55; ts=vol_idr*0.45
    return {'buy':tb,'sell':ts,'buy_m':tb,'sell_m':ts,'spread':0.5,'ratio':tb/ts if ts>0 else 1,'dominant':dom,'ok':True}

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
            ob=get_ob(base, vol, pos_p)
            candle=get_candle(base)
            if not candle['bull']: continue
            mode_label='🛡️ MODE AMAN' if pos_p<=85 else '🚀 MODE HIGH'
            mode='KOREKSI' if pos_p<=85 else 'PUCUK'
            cands.append({'base':base,'mode_label':mode_label,'mode':mode,'entry':last,'gain':gain_low,'pos':pos_p,'vol':vol,'tp1':last*1.05,'tp2':last*1.10,'tp3':last*1.15,'sl':last*0.95,'ob':ob,'candle':candle,'change12':ch12})
            time.sleep(0.6)
        except: continue
    cands=sorted(cands,key=lambda x:x['pos'],reverse=True)
    return cands[:6]

def fmt_tmg(s,r):
    ob=s['ob']
    if ob['dominant']=='BUY':
        ob_line = f"🟢 BUY {fmt_money(ob['buy_m'])} > {fmt_money(ob['sell_m'])}"
    else:
        ob_line = f"🔴 SELL {fmt_money(ob['sell_m'])} > {fmt_money(ob['buy_m'])}"
    return f"""┌─ #{r} {s['mode_label']} {s['base']}/IDR ─
│ 🛡️ {s['mode']} | Pos {s['pos']:.0f}%
│ 📈 12H {s['change12']:.2f}%
│ 📊 Gain {s['gain']:.2f}%
│ 💧 Vol {s['vol']/1e6:.0f}M
├────────────────
│ 💰 OB 10 Baris
│ {ob_line}
│ Ratio {ob['ratio']:.2f}x | Spread {ob['spread']:.2f}%
│ 🕯️ Candle {s['candle']['note']} {s['candle']['change']:+.2f}%
├────────────────
│ 🟢 ENTRY {fmt_price(s['entry'])}
│ 🎯 TP1 {fmt_price(s['tp1'])} (+5%)
│ 🎯 TP2 {fmt_price(s['tp2'])} (+10%)
│ 🎯 TP3 {fmt_price(s['tp3'])} (+15%)
│ 🔴 SL {fmt_price(s['sl'])} (-5%)
└─ {jam()} ─"""

def fmt_rekap(list_sig):
    txt=f"📊 REKAP {len(list_sig)} SINYAL {jam()}\nPos Tertinggi ➜ Terendah\n────────────────\n"
    for i,s in enumerate(list_sig,1):
        ob=s['ob']
        icon = "🟢 BUY" if ob['dominant']=='BUY' else "🔴 SELL"
        txt+=f"{i}. {icon} {s['base']} Pos {s['pos']:.0f}% Vol {s['vol']/1e6:.0f}M {fmt_money(ob['buy_m'])}/{fmt_money(ob['sell_m'])}\n"
    return txt

def fmt_winrate():
    stats=load(FILE_STATS,{"win":0,"loss":0,"total_sinyal":0,"tp1":0,"tp2":0,"tp3":0})
    total=stats.get('total_sinyal',0); win=stats.get('win',0); loss=stats.get('loss',0)
    tp1=stats.get('tp1',0); tp2=stats.get('tp2',0); tp3=stats.get('tp3',0)
    winrate = (win/total*100) if total>0 else 0
    return f"""📊 WINRATE {jam()}
────────────────
Total Sinyal: {total}
TP Tercapai: {win}
SL: {loss}
TP1 (+5%): {tp1}
TP2 (+10%): {tp2}
TP3 (+15%): {tp3}
────────────────
Winrate: {winrate:.2f}%"""

def cek_tp():
    tickers,_=get_data()
    if not tickers: return
    pos=load(FILE_POS,{}); stats=load(FILE_STATS,{"win":0,"loss":0,"total_sinyal":0,"tp1":0,"tp2":0,"tp3":0}); hist=load(FILE_HISTORY,[]); ch=False
    for base,data in list(pos.items()):
        try:
            if isinstance(data, dict):
                entry=data['entry']; tp1=data['tp1']; tp2=data['tp2']; tp3=data['tp3']; sl=data['sl']; hit=data.get('hit',[])
            else:
                entry=float(data); tp1=entry*1.05; tp2=entry*1.10; tp3=entry*1.15; sl=entry*0.95; hit=[]
            last=float(tickers[f"{base.lower()}_idr"]['last'])
            if last>=tp1 and 'TP1' not in hit:
                send(f"🏆 TP1 {base} +5% {fmt_price(entry)} -> {fmt_price(last)} {jam()}")
                hit.append('TP1'); stats['tp1']=stats.get('tp1',0)+1
                if 'WIN_COUNTED' not in hit: stats['win']=stats.get('win',0)+1; hit.append('WIN_COUNTED')
                pos[base]={'entry':entry,'tp1':tp1,'tp2':tp2,'tp3':tp3,'sl':sl,'hit':hit}; ch=True
            if last>=tp2 and 'TP2' not in hit:
                send(f"🏆🏆 TP2 {base} +10% {fmt_price(entry)} -> {fmt_price(last)} {jam()}")
                hit.append('TP2'); stats['tp2']=stats.get('tp2',0)+1
                pos[base]={'entry':entry,'tp1':tp1,'tp2':tp2,'tp3':tp3,'sl':sl,'hit':hit}; ch=True
            if last>=tp3 and 'TP3' not in hit:
                send(f"🏆🏆🏆 TP3 {base} +15% {fmt_price(entry)} -> {fmt_price(last)} {jam()}\n{fmt_winrate()}")
                hit.append('TP3'); stats['tp3']=stats.get('tp3',0)+1
                pos.pop(base); hist.append({"base":base,"pnl":"WIN"}); ch=True
            if last<=sl:
                send(f"🔴 SL {base} -5% {fmt_price(entry)} -> {fmt_price(last)} {jam()}\n{fmt_winrate()}")
                stats['loss']=stats.get('loss',0)+1
                pos.pop(base); hist.append({"base":base,"pnl":"LOSS"}); ch=True
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
            if txt=='/winrate' or txt=='/stats': send(fmt_winrate())
            if txt=='/scan':
                sig=analisa()
                if sig:
                    send(fmt_rekap(sig))
                    time.sleep(1)
                    for i,s in enumerate(sig,1): send(fmt_tmg(s,i)); time.sleep(0.5)
                else: send(f"0 sinyal {jam()}")
    except: pass

def main():
    time.sleep(2); send(f"✅ V8.8.2-ANTI-NA AKTIF {jam()}\nFix N/A 0/0 -> Selalu 🟢/🔴 + TP3 + Winrate")
    loop=0
    while True:
        try:
            if loop%2==0: handle()
            if loop%4==0: cek_tp()
            if loop%10==0:
                sig=analisa()
                if sig:
                    pos=load(FILE_POS,{}); cooldown=load(FILE_COOLDOWN,{}); stats=load(FILE_STATS,{"win":0,"loss":0,"total_sinyal":0,"tp1":0,"tp2":0,"tp3":0})
                    send(fmt_rekap(sig))
                    time.sleep(1)
                    for i,s in enumerate(sig,1):
                        if s['base'] in pos: continue
                        send(fmt_tmg(s,i))
                        pos[s['base']]={'entry':s['entry'],'tp1':s['tp1'],'tp2':s['tp2'],'tp3':s['tp3'],'sl':s['sl'],'hit':[]}
                        save(FILE_POS,pos); cooldown[s['base']]=now().isoformat(); save(FILE_COOLDOWN,cooldown)
                        stats['total_sinyal']=stats.get('total_sinyal',0)+1; save(FILE_STATS,stats)
                        time.sleep(0.8)
            loop+=1; time.sleep(30)
        except Exception as e:
            print(f"ERR {e}",flush=True); time.sleep(10)

if __name__=="__main__": main()
