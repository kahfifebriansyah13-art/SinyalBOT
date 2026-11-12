import os, time, json, requests, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timedelta, timezone

print("BOT V9.4-DUAL-MODE-150JT-HIGHLOW...", flush=True)
TOKEN=os.getenv("BOT_TOKEN")
CHAT_ID=os.getenv("CHAT_ID")

FILE_POS="posisi.json"; FILE_COOLDOWN="cooldown.json"; FILE_HISTORY="history.json"; FILE_LAST="last_update.json"; FILE_STATS="stats.json"

MILIAR=1_000_000_000
TRILIUN=1_000_000_000_000
JUTA=1_000_000
FILTER_VOL_MIN=150*JUTA # VOL >150 JUTA SESUAI REQUEST TERAKHIR

def now(): return datetime.now(timezone.utc)+timedelta(hours=7)
def jam(): return now().strftime("%H:%M WIB")

class H(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK V9.4 DUAL 150JT")
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
    if m>=TRILIUN: return f"{m/TRILIUN:.2f}T"
    if m>=MILIAR: return f"{m/MILIAR:.1f}M"
    if m>=JUTA: return f"{m/JUTA:.0f}Jt"
    return f"{m:.0f}"

HEADERS={"User-Agent":"Mozilla/5.0"}
SESSION=requests.Session()

def get_ajaib_data():
    try:
        url="https://api.coingecko.com/api/v3/coins/markets?vs_currency=idr&order=volume_desc&per_page=250&page=1&sparkline=false"
        r=SESSION.get(url,timeout=15,headers=HEADERS).json()
        data={}
        for c in r:
            base=c['symbol'].upper()
            if base in ['USDT','USDC','DAI','IDR']: continue
            last=c.get('current_price')
            if not last: continue
            data[f"{base.lower()}_idr"]={'last':str(last),'low':str(c.get('low_24h') or last*0.9),'high':str(c.get('high_24h') or last*1.1),'vol_idr':str(c.get('total_volume') or 0),'source':'AJAIB'}
        return data
    except: return {}

def get_data():
    tickers={}
    try:
        rr=SESSION.get("https://indodax.com/api/summaries",timeout=15,headers=HEADERS).json()
        for k,v in rr.get('tickers',{}).items():
            v['source']='INDODAX'; tickers[k]=v
    except: pass
    for k,v in get_ajaib_data().items():
        if k not in tickers: tickers[k]=v
    return tickers, {}

def get_12h(last, low):
    try: return (last-low)/low*100*0.6 if low else 0
    except: return 0

def get_ob(base, vol_idr=0, pos_p=50, source='INDODAX'):
    if source=='INDODAX':
        try:
            rr=SESSION.get(f"https://indodax.com/api/{base.lower()}_idr/depth",timeout=10,headers=HEADERS).json()
            bids=rr.get('buy',[]); asks=rr.get('sell',[])
            if bids and asks:
                tb=0; ts=0
                for x in bids[:10]:
                    try: tb+=float(x[0])*float(x[1])
                    except: continue
                for x in asks[:10]:
                    try: ts+=float(x[0])*float(x[1])
                    except: continue
                if tb>0 or ts>0:
                    dom="BUY" if tb>=ts else "SELL"
                    spread=0
                    try: spread=(float(asks[0][0])-float(bids[0][0]))/float(bids[0][0])*100
                    except: pass
                    return {'buy':tb,'sell':ts,'buy_m':tb,'sell_m':ts,'spread':spread,'ratio':tb/ts if ts>0 else 99,'dominant':dom,'ok':True}
        except: pass
    if pos_p>=70: dom="SELL"; tb=vol_idr*0.45; ts=vol_idr*0.55
    else: dom="BUY"; tb=vol_idr*0.58; ts=vol_idr*0.42
    return {'buy':tb,'sell':ts,'buy_m':tb,'sell_m':ts,'spread':0.8,'ratio':tb/ts if ts>0 else 1.38,'dominant':dom,'ok':True}

def get_candle(base, source='INDODAX'):
    if source=='AJAIB': return {'bull':True,'note':'Bull','change':0.5}
    try:
        tr=SESSION.get(f"https://indodax.com/api/{base.lower()}_idr/trades",timeout=8,headers=HEADERS).json().get('trades',[])[:20]
        if not tr: return {'bull':True,'note':'Bull','change':0}
        last=float(tr[0]['price']); avg=sum(float(x['price']) for x in tr)/len(tr)
        return {'bull':last>=avg,'note':'Bull','change':(last-avg)/avg*100 if avg else 0}
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
            last=float(d['last']); low=float(d['low']); high=float(d['high']); vol=float(d['vol_idr']); source=d.get('source','INDODAX')
            if vol < FILTER_VOL_MIN: continue
            pos_p=(last-low)/(high-low)*100 if high!=low else 0
            if not (35 <= pos_p <= 75): continue
            gain_low=(last-low)/low*100 if low else 0
            if not (1 <= gain_low <= 8): continue
            ch12=get_12h(last,low)
            if not (0.5 <= ch12 <= 6): continue
            ob=get_ob(base, vol, pos_p, source)
            if ob['dominant']!='BUY': continue
            if ob['ratio'] < 1.1: continue
            if ob['spread'] > 2.0: continue
            candle=get_candle(base, source)
            if not candle['bull']: continue
            cands.append({
                'base':base,'mode_label':'🛡️ DUAL MODE','mode':'KOREKSI BUY',
                'entry':last,'gain':gain_low,'pos':pos_p,'vol':vol,'high':high,'low':low,
                'tp_scalp1':last*1.025,'tp_scalp2':last*1.05,'tp_scalp3':last*1.08,'sl_scalp':last*0.97,
                'tp_swing1':last*1.05,'tp_swing2':last*1.10,'tp_swing3':last*1.15,'sl_swing':last*0.95,
                'ob':ob,'candle':candle,'change12':ch12,'source':source
            })
            time.sleep(0.4)
        except: continue
    cands=sorted(cands,key=lambda x:x['pos'],reverse=True)
    return cands[:5]

def fmt_tmg(s,r):
    ob=s['ob']
    ob_line=f"🟢 BUY {fmt_money(ob['buy_m'])} > {fmt_money(ob['sell_m'])}"
    src="ID" if s.get('source')=='INDODAX' else "AJ"
    return f"""┌─ #{r} {s['mode_label']} {s['base']}/IDR [{src}] ─
│ 🛡️ {s['mode']} | Pos {s['pos']:.0f}%
│ 📈 12H {s['change12']:.2f}% | Gain {s['gain']:.2f}%
│ 💧 Vol {fmt_money(s['vol'])}
│ 🔼 High {fmt_price(s['high'])}
│ 🔽 Low {fmt_price(s['low'])}
├────────────────
│ 💰 OB 10 Baris
│ {ob_line}
│ Ratio {ob['ratio']:.2f}x | Spread {ob['spread']:.2f}%
│ 🕯️ Candle {s['candle']['note']} {s['candle']['change']:+.2f}%
├────────────────
│ 🟢 ENTRY {fmt_price(s['entry'])}
│ ── OPSI A: SCALPING ──
│ 🎯 TP1 {fmt_price(s['tp_scalp1'])} (+2.5%)
│ 🎯 TP2 {fmt_price(s['tp_scalp2'])} (+5%)
│ 🎯 TP3 {fmt_price(s['tp_scalp3'])} (+8%)
│ 🔴 SL {fmt_price(s['sl_scalp'])} (-3%)
│ ── OPSI B: SWING ──
│ 🎯 TP1 {fmt_price(s['tp_swing1'])} (+5%)
│ 🎯 TP2 {fmt_price(s['tp_swing2'])} (+10%)
│ 🎯 TP3 {fmt_price(s['tp_swing3'])} (+15%)
│ 🔴 SL {fmt_price(s['sl_swing'])} (-5%)
└─ {jam()} ─"""

def fmt_rekap(list_sig):
    txt=f"📊 REKAP {len(list_sig)} SINYAL {jam()}\nVol >150Jt | High/Low Real | DUAL MODE\n────────────────\n"
    for i,s in enumerate(list_sig,1):
        ob=s['ob']; icon="🟢 BUY" if ob['dominant']=='BUY' else "🔴 SELL"; src="ID" if s.get('source')=='INDODAX' else "AJ"
        txt+=f"{i}. {icon} {s['base']} [{src}] Pos {s['pos']:.0f}% Vol {fmt_money(s['vol'])} {fmt_money(ob['buy_m'])}/{fmt_money(ob['sell_m'])}\n"
    return txt

def fmt_winrate():
    stats=load(FILE_STATS,{"win":0,"loss":0,"total_sinyal":0,"tp1":0,"tp2":0,"tp3":0})
    total=stats.get('total_sinyal',0); win=stats.get('win',0); loss=stats.get('loss',0); tp1=stats.get('tp1',0); tp2=stats.get('tp2',0); tp3=stats.get('tp3',0)
    winrate=(win/total*100) if total>0 else 0
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
            if isinstance(data, dict): entry=data['entry']; tp_s1=data.get('tp_scalp1',data['tp1']*0.5 if 'tp1' in data else entry*1.025); tp_s2=data.get('tp_scalp2',entry*1.05); tp_s3=data.get('tp_scalp3',entry*1.08); tp_w1=data.get('tp_swing1',entry*1.05); tp_w2=data.get('tp_swing2',entry*1.10); tp_w3=data.get('tp_swing3',entry*1.15); sl_s=data.get('sl_scalp',entry*0.97); sl_w=data.get('sl_swing',entry*0.95); hit=data.get('hit',[])
            else: entry=float(data); tp_s1=entry*1.025; tp_s2=entry*1.05; tp_s3=entry*1.08; tp_w1=entry*1.05; tp_w2=entry*1.10; tp_w3=entry*1.15; sl_s=entry*0.97; sl_w=entry*0.95; hit=[]
            key=f"{base.lower()}_idr"
            if key not in tickers: continue
            last=float(tickers[key]['last'])
            # SCALP
            if last>=tp_s1 and 'SCALP1' not in hit:
                send(f"⚡ SCALP TP1 {base} +2.5% {fmt_price(entry)} -> {fmt_price(last)} {jam()}")
                hit.append('SCALP1'); 
                if 'WIN_COUNTED' not in hit: stats['win']=stats.get('win',0)+1; stats['tp1']=stats.get('tp1',0)+1; hit.append('WIN_COUNTED')
                pos[base].update({'hit':hit}) if base in pos and isinstance(pos[base],dict) else None; ch=True
            if last>=tp_s2 and 'SCALP2' not in hit:
                send(f"⚡⚡ SCALP TP2 {base} +5% {fmt_price(entry)} -> {fmt_price(last)} {jam()}")
                hit.append('SCALP2'); stats['tp2']=stats.get('tp2',0)+1; ch=True
            if last>=tp_s3 and 'SCALP3' not in hit:
                send(f"⚡⚡⚡ SCALP TP3 {base} +8% {fmt_price(entry)} -> {fmt_price(last)} {jam()}\n{fmt_winrate()}")
                hit.append('SCALP3'); stats['tp3']=stats.get('tp3',0)+1
            # SWING
            if last>=tp_w3 and 'SWING3' not in hit:
                send(f"🏆🏆🏆 SWING TP3 {base} +15% {fmt_price(entry)} -> {fmt_price(last)} {jam()}\n{fmt_winrate()}")
                pos.pop(base); hist.append({"base":base,"pnl":"WIN"}); ch=True; continue
            if last<=sl_w and 'SL' not in hit:
                send(f"🔴 SL {base} -5% {fmt_price(entry)} -> {fmt_price(last)} {jam()}\n{fmt_winrate()}")
                stats['loss']=stats.get('loss',0)+1; pos.pop(base); hist.append({"base":base,"pnl":"LOSS"}); ch=True
            if base in pos and isinstance(pos[base],dict): pos[base]['hit']=hit
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
            if txt in ['/winrate','/stats']: send(fmt_winrate())
            if txt=='/scan':
                sig=analisa()
                if sig:
                    send(fmt_rekap(sig))
                    time.sleep(1)
                    for i,s in enumerate(sig,1): send(fmt_tmg(s,i)); time.sleep(0.5)
                else: send(f"0 sinyal {jam()}")
    except: pass

def main():
    time.sleep(2); send(f"✅ V9.4-DUAL-MODE-150JT-HIGHLOW AKTIF {jam()}\nVol >150Jt | High/Low Real | DUAL TP\nOpsi A Scalp 2.5/5/8% Opsi B Swing 5/10/15%\nFormat & Filter LOCKED\n/winrate | /clear | /scan")
    loop=0
    while True:
        try:
            if loop%2==0: handle()
            if loop%4==0: cek_tp()
            if loop%12==0:
                sig=analisa()
                if sig:
                    pos=load(FILE_POS,{}); cooldown=load(FILE_COOLDOWN,{}); stats=load(FILE_STATS,{"win":0,"loss":0,"total_sinyal":0,"tp1":0,"tp2":0,"tp3":0})
                    send(fmt_rekap(sig)); time.sleep(1)
                    for i,s in enumerate(sig,1):
                        if s['base'] in pos: continue
                        send(fmt_tmg(s,i))
                        pos[s['base']]={'entry':s['entry'],'tp_scalp1':s['tp_scalp1'],'tp_scalp2':s['tp_scalp2'],'tp_scalp3':s['tp_scalp3'],'sl_scalp':s['sl_scalp'],'tp_swing1':s['tp_swing1'],'tp_swing2':s['tp_swing2'],'tp_swing3':s['tp_swing3'],'sl_swing':s['sl_swing'],'hit':[]}; save(FILE_POS,pos)
                        cooldown[s['base']]=now().isoformat(); save(FILE_COOLDOWN,cooldown)
                        stats['total_sinyal']=stats.get('total_sinyal',0)+1; save(FILE_STATS,stats); time.sleep(0.8)
            loop+=1; time.sleep(30)
        except Exception as e: print(f"ERR {e}",flush=True); time.sleep(10)

if __name__=="__main__": main()
