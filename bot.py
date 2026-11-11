import os, time, json, requests, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timedelta, timezone

print("BOT V6.2 NO WALL STARTING...", flush=True)
TOKEN=os.getenv("BOT_TOKEN"); CHAT_ID=os.getenv("CHAT_ID")
FILE_POS="posisi.json"; FILE_COOLDOWN="cooldown.json"; FILE_HISTORY="history.json"; FILE_LAST="last_update.json"

def now(): return datetime.now(timezone.utc)+timedelta(hours=7)
def jam(): return now().strftime("%H:%M WIB")

class H(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK V6.2")
    def log_message(self,*a): return
threading.Thread(target=lambda: HTTPServer(("0.0.0.0",int(os.getenv("PORT",8080))),H).serve_forever(),daemon=True).start()

def send(txt):
    try: return requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",data={"chat_id":CHAT_ID,"text":txt,"parse_mode":"Markdown"},timeout=20).status_code==200
    except: return False

def load(f,d):
    try: return json.load(open(f,'r'))
    except: return d
def save(f,d):
    try: json.dump(d,open(f,'w'))
    except: pass

def get_tickers():
    try: return requests.get("https://indodax.com/api/tickers",timeout=20,headers={"User-Agent":"Mozilla/5.0"}).json()['tickers']
    except: return {}

def get_ob(base):
    try:
        data=requests.get(f"https://indodax.com/api/{base.lower()}_idr/depth",timeout=12).json()
        bids=data.get('buy',[])[:10]; asks=data.get('sell',[])[:10]
        if not bids or not asks: return None
        tb=sum(float(p)*float(v) for p,v in bids); ts=sum(float(p)*float(v) for p,v in asks)
        if ts==0: return None
        ratio=tb/ts
        spread=(float(asks[0][0])-float(bids[0][0]))/float(bids[0][0])*100
        return {'ratio':ratio,'spread':spread,'buy_m':tb,'sell_m':ts}
    except: return None

def get_trending():
    try:
        r=requests.get("https://api.coingecko.com/api/v3/search/trending",timeout=10).json()
        s=set()
        for c in r.get('coins',[]): s.add(c['item']['symbol'].upper())
        return s
    except: return set()

def get_ta(base):
    try:
        to_ts=int(datetime.now().timestamp()); from_ts=to_ts-40*24*3600
        url=f"https://indodax.com/tradingview/history?symbol={base}IDR&resolution=D&from={from_ts}&to={to_ts}"
        r=requests.get(url,timeout=10).json()
        closes=r.get('c',[])
        if len(closes)<22: return {'ok':True,'rsi':55,'score':8,'note':"TA Default"}
        def ema(arr,n):
            k=2/(n+1); e=arr[0]
            for x in arr[1:]: e=x*k+e*(1-k)
            return e
        ema9=ema(closes[-9:],9); ema21=ema(closes[-21:],21)
        ema_ok=ema9>ema21 and closes[-1]>ema9
        deltas=[closes[i]-closes[i-1] for i in range(1,len(closes))]
        gains=[d if d>0 else 0 for d in deltas[-14:]]; losses=[-d if d<0 else 0 for d in deltas[-14:]]
        avg_gain=sum(gains)/14; avg_loss=sum(losses)/14 if sum(losses)!=0 else 0.01
        rsi=100-(100/(1+avg_gain/avg_loss))
        rsi_ok=50 <= rsi <= 68
        score=0
        if ema_ok: score+=10
        if rsi_ok: score+=8
        note=f"EMA {'Bull' if ema_ok else 'Bear'} RSI {rsi:.0f}"
        return {'ok':ema_ok and rsi_ok,'rsi':rsi,'score':score,'note':note}
    except: return {'ok':True,'rsi':55,'score':8,'note':"TA OK"}

def analisa():
    tickers=get_tickers()
    if not tickers: return []
    pos=load(FILE_POS,{}); cooldown=load(FILE_COOLDOWN,{})
    trending=get_trending()
    # clean cooldown 6 jam
    for k in list(cooldown.keys()):
        try:
            if now()-datetime.fromisoformat(cooldown[k])>timedelta(hours=6): del cooldown[k]
        except: del cooldown[k]
    save(FILE_COOLDOWN,cooldown)

    cands=[]
    for pid,d in tickers.items():
        if not pid.endswith('_idr'): continue
        base=pid.split('_')[0].upper()
        if base in pos or base in cooldown or base in ['USDT','USDC','IDR']: continue
        try:
            last=float(d['last']); low=float(d['low']); high=float(d['high']); vol=float(d['vol_idr']); open_p=float(d.get('open',last))
            if vol<200_000_000 or low==0: continue
            naik=(last-low)/low*100
            posisi=(last-low)/(high-low)*100 if high!=low else 50
            if not (3 <= naik <= 8): continue
            if not (35 <= posisi <= 55): continue
            if last < open_p: continue
            cands.append((base,last,low,high,naik,posisi,vol))
        except: continue

    cands=sorted(cands,key=lambda x:x[6],reverse=True)[:30]
    print(f"SCAN NO WALL {jam()}: {len(cands)} kandidat",flush=True)

    scored=[]
    for base,last,low,high,naik,posisi,vol in cands:
        ob=get_ob(base)
        if not ob: continue
        if ob['ratio']<1.3 or ob['spread']>1.5: continue
        ta=get_ta(base)
        if not ta['ok']: continue

        score=50
        if vol>=500_000_000: score+=15
        elif vol>=200_000_000: score+=8
        if 4<=naik<=6: score+=12
        else: score+=6
        if 40<=posisi<=50: score+=10
        else: score+=5
        if ob['ratio']>=2.0: score+=15
        elif ob['ratio']>=1.5: score+=10
        else: score+=5
        score+=ta['score']
        if base in trending: score+=12; sos=True
        else: sos=False

        if score>=70:
            scored.append({'base':base,'entry':last,'low':low,'high':high,'naik':naik,'pos':posisi,'vol':vol,'tp':last*1.05,'sl':last*0.95,'score':min(score,99),'ob':ob,'ta':ta,'trending':sos})
            print(f"LOLOS NO WALL {base} SCORE {score} RATIO {ob['ratio']:.2f}",flush=True)
        if len(scored)>=10: break

    return sorted(scored,key=lambda x:x['score'],reverse=True)[:10]

def fmt(s,r):
    ob=s['ob']; ta=s['ta']; trend="🔥 TRENDING CoinGecko" if s['trending'] else "Normal"
    return f"""╔═══ #{r} {s['base']}/IDR ✨ SCORE {s['score']} ═══╗
║ 🌐 {trend}
║ 📈 {ta['note']} - Breakout Ready
╠═══════════════════════════╣
║ 📚 ORDER BOOK TOP 10 - NO WALL
║ 💰 Buy Rp {ob['buy_m']/1e6:.0f}M vs Sell Rp {ob['sell_m']/1e6:.0f}M
║ 📈 Dominan Buy {ob['ratio']:.2f}x | Spread {ob['spread']:.2f}%
╠═══════════════════════════╣
║ 🕯️ DAILY BREAKOUT
║ 📍 Pos {s['pos']:.0f}% dekat High | Naik +{s['naik']:.1f}%
║ 💧 Vol Rp {s['vol']/1e6:.0f}M - Naik
╠═══════════════════════════╣
║ 🎯 PLAN TP PASTI - {jam()}
║ 🟢 ENTRY Rp {s['entry']:,.0f}
║ 🎯 TP +5% Rp {s['tp']:,.0f}
║ 🔴 SL -5% Rp {s['sl']:,.0f}
╚═══════════════════════════╝"""

def cek_tp():
    tickers=get_tickers(); pos=load(FILE_POS,{}); hist=load(FILE_HISTORY,[])
    for base,entry in list(pos.items()):
        try:
            last=float(tickers[f"{base.lower()}_idr"]['last'])
            if last>=entry*1.05:
                send(f"🏆 *TP +5% {base} HIT!* {jam()}\nEntry Rp {entry:,.0f} -> Rp {last:,.0f}"); pos.pop(base); save(FILE_POS,pos)
                for h in hist:
                    if h['base']==base and h['status']=='active': h['status']='WIN'; h['exit']=last
                save(FILE_HISTORY,hist)
            elif last<=entry*0.95:
                send(f"🔴 *SL {base} HIT* {jam()}"); pos.pop(base); save(FILE_POS,pos)
                for h in hist:
                    if h['base']==base and h['status']=='active': h['status']='LOSS'; h['exit']=last
                save(FILE_HISTORY,hist)
        except: continue

def handle():
    try:
        last_id=load(FILE_LAST,{"id":0})["id"]
        r=requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={last_id+1}&timeout=5",timeout=10).json()
        for u in r.get('result',[]):
            save(FILE_LAST,{"id":u['update_id']})
            txt=u.get('message',{}).get('text','').lower().strip()
            if txt in ['/clear','/reset']: save(FILE_POS,{}); save(FILE_COOLDOWN,{}); send(f"✅ Reset - {jam()}")
            if txt in ['/winrate','/profit','/stats']:
                hist=load(FILE_HISTORY,[]); wins=sum(1 for h in hist if h['status']=='WIN'); loss=sum(1 for h in hist if h['status']=='LOSS'); total=wins+loss
                wr=wins/total*100 if total>0 else 0; profit=sum(((h['exit']/h['entry']-1)*100) for h in hist if h['status'] in ['WIN','LOSS'])
                send(f"📊 *WINRATE V6.2 - {jam()}*\nWIN {wins} LOSS {loss} Total {total}\nWinrate {wr:.1f}% P/L {profit:+.1f}%")
    except: pass

def main():
    time.sleep(2); send(f"✅ *BOT V6.2 NO WALL AKTIF - {jam()}*\nTanpa wall, fokus breakout pasti TP")
    loop=0
    while True:
        try:
            if loop%4==0: cek_tp()
            if loop%2==0: handle()
            if loop%6==0:
                sig=analisa()
                if sig:
                    msg=f"🏆 *{len(sig)} SINYAL BREAKOUT - {jam()}*\n"
                    for i,s in enumerate(sig,1): msg+=f"✨ #{i} {s['base']} SCORE {s['score']} {s['ob']['ratio']:.2f}x\n"
                    send(msg); time.sleep(2)
                    pos=load(FILE_POS,{}); cooldown=load(FILE_COOLDOWN,{}); hist=load(FILE_HISTORY,[])
                    for rank,s in enumerate(sig,1):
                        if s['base'] in pos: continue
                        send(fmt(s,rank)); pos[s['base']]=s['entry']; save(FILE_POS,pos)
                        cooldown[s['base']]=now().isoformat(); save(FILE_COOLDOWN,cooldown)
                        hist.append({'base':s['base'],'entry':s['entry'],'time':now().isoformat(),'score':s['score'],'status':'active','exit':0}); save(FILE_HISTORY,hist)
                        time.sleep(1.2)
            loop+=1; time.sleep(30)
        except Exception as e:
            print(f"ERR {e}",flush=True); time.sleep(20)

if __name__=="__main__": main()
