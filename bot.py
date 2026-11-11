import os, time, json, requests, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timedelta, timezone

print("BOT V6.3 3 MODE STARTING...", flush=True)
TOKEN=os.getenv("BOT_TOKEN"); CHAT_ID=os.getenv("CHAT_ID")
FILE_POS="posisi.json"; FILE_COOLDOWN="cooldown.json"; FILE_HISTORY="history.json"; FILE_LAST="last_update.json"

def now(): return datetime.now(timezone.utc)+timedelta(hours=7)
def jam(): return now().strftime("%H:%M WIB")

class H(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK V6.3 3 MODE")
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
        return {'ratio':tb/ts,'spread':(float(asks[0][0])-float(bids[0][0]))/float(bids[0][0])*100,'buy_m':tb,'sell_m':ts}
    except: return None

def get_trending():
    try:
        r=requests.get("https://api.coingecko.com/api/v3/search/trending",timeout=10).json()
        return set(c['item']['symbol'].upper() for c in r.get('coins',[]))
    except: return set()

def get_ta(base):
    try:
        to_ts=int(datetime.now().timestamp()); from_ts=to_ts-40*24*3600
        url=f"https://indodax.com/tradingview/history?symbol={base}IDR&resolution=D&from={from_ts}&to={to_ts}"
        r=requests.get(url,timeout=10).json()
        closes=r.get('c',[]); opens=r.get('o',[])
        if len(closes)<22: return {'rsi':55,'ema_bull':True,'last_c':closes[-1] if closes else 0,'prev_c':closes[-2] if len(closes)>1 else 0,'note':"TA Default",'score':8}
        def ema(arr,n):
            k=2/(n+1); e=arr[0]
            for x in arr[1:]: e=x*k+e*(1-k)
            return e
        ema9=ema(closes[-9:],9); ema21=ema(closes[-21:],21)
        ema_bull=closes[-1]>ema9 and ema9>ema21
        deltas=[closes[i]-closes[i-1] for i in range(1,len(closes))]
        gains=[d if d>0 else 0 for d in deltas[-14:]]; losses=[-d if d<0 else 0 for d in deltas[-14:]]
        avg_g=sum(gains)/14; avg_l=sum(losses)/14 if sum(losses)!=0 else 0.01
        rsi=100-(100/(1+avg_g/avg_l))
        score=0
        if ema_bull: score+=10
        if 40<=rsi<=68: score+=8
        return {'rsi':rsi,'ema_bull':ema_bull,'last_c':closes[-1],'prev_c':closes[-2],'open_c':opens[-1] if opens else closes[-1],'note':f"{'Bull' if ema_bull else 'Bear'} RSI {rsi:.0f}",'score':score}
    except: return {'rsi':55,'ema_bull':True,'last_c':0,'prev_c':0,'open_c':0,'note':"TA OK",'score':8}

def analisa():
    tickers=get_tickers()
    if not tickers: return []
    pos=load(FILE_POS,{}); cooldown=load(FILE_COOLDOWN,{})
    trending=get_trending()
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
            last=float(d['last']); low=float(d['low']); high=float(d['high']); vol=float(d['vol_idr'])
            if vol<150_000_000 or low==0 or high==low: continue
            naik=(last-low)/low*100
            pos_p=(last-low)/(high-low)*100
            drop_from_high=(high-last)/high*100
            cands.append((base,last,low,high,naik,pos_p,drop_from_high,vol))
        except: continue

    cands=sorted(cands,key=lambda x:x[7],reverse=True)[:40]
    print(f"SCAN V6.3 {jam()}: {len(cands)} kandidat awal",flush=True)

    scored=[]
    for base,last,low,high,naik,pos_p,drop_high,vol in cands:
        ob=get_ob(base)
        if not ob or ob['ratio']<1.1 or ob['spread']>2.5: continue
        ta=get_ta(base)

        mode=None; mode_score=0

        # MODE A: BREAKOUT - profit paling cepat
        if 35<=pos_p<=60 and 3<=naik<=9 and drop_high<5:
            if ta['ema_bull'] and 48<=ta['rsi']<=70:
                mode="BREAKOUT"; mode_score=30

        # MODE B: KOREKSI SEHAT - beli saat turun dikit lalu mantul
        elif 25<=pos_p<=45 and 2<=drop_high<=7 and naik>=2:
            if 40<=ta['rsi']<=58 and ta['ema_bull']:
                mode="KOREKSI SEHAT"; mode_score=28

        # MODE C: REVERSAL AWAL - beli di bawah mau balik arah
        elif 10<=pos_p<=30 and 1<=naik<=5 and ta['rsi']>=38 and ta['rsi']<=55:
            if last > low*1.015:
                mode="REVERSAL AWAL"; mode_score=26

        if not mode: continue

        score=40 + mode_score
        if vol>=500_000_000: score+=15
        elif vol>=200_000_000: score+=10
        else: score+=5
        if ob['ratio']>=1.8: score+=15
        elif ob['ratio']>=1.3: score+=10
        else: score+=5
        score+=ta['score']
        if base in trending: score+=12; sos=True
        else: sos=False

        print(f"{mode} {base} POS {pos_p:.0f}% NAIK {naik:.1f}% DROP {drop_high:.1f}% RSI {ta['rsi']:.0f} SCORE {score}",flush=True)

        if score>=70:
            scored.append({'base':base,'mode':mode,'entry':last,'low':low,'high':high,'naik':naik,'pos':pos_p,'drop':drop_high,'vol':vol,'tp':last*1.05,'sl':last*0.95,'score':min(score,99),'ob':ob,'ta':ta,'trending':sos})

    return sorted(scored,key=lambda x:x['score'],reverse=True)[:10]

def fmt(s,r):
    ob=s['ob']; ta=s['ta']; trend="🔥 TRENDING" if s['trending'] else "Normal"
    icon="🚀" if s['mode']=="BREAKOUT" else "🩹" if s['mode']=="KOREKSI SEHAT" else "🔄"
    return f"""╔═══ #{r} {icon} {s['mode']} {s['base']}/IDR SCORE {s['score']} ═══╗
║ 🌐 {trend} | {ta['note']}
║ 📍 Pos {s['pos']:.0f}% Drop {s['drop']:.1f}% Naik {s['naik']:.1f}%
╠═══════════════════════════╣
║ 📚 OB {ob['ratio']:.2f}x | Spread {ob['spread']:.2f}%
║ 💰 Buy Rp {ob['buy_m']/1e6:.0f}M vs Sell Rp {ob['sell_m']/1e6:.0f}M
║ 💧 Vol Rp {s['vol']/1e6:.0f}M
╠═══════════════════════════╣
║ 🎯 TP +5% - {jam()}
║ 🟢 ENTRY Rp {s['entry']:,.0f}
║ 🎯 TP Rp {s['tp']:,.0f}
║ 🔴 SL Rp {s['sl']:,.0f}
╚═══════════════════════════╝"""

def cek_tp():
    tickers=get_tickers(); pos=load(FILE_POS,{}); hist=load(FILE_HISTORY,[])
    for base,entry in list(pos.items()):
        try:
            last=float(tickers[f"{base.lower()}_idr"]['last'])
            if last>=entry*1.05:
                send(f"🏆 *TP {base} +5% HIT! {jam()}*"); pos.pop(base); save(FILE_POS,pos)
                for h in hist:
                    if h['base']==base and h['status']=='active': h['status']='WIN'; h['exit']=last
                save(FILE_HISTORY,hist)
            elif last<=entry*0.95:
                send(f"🔴 *SL {base} -5% {jam()}*"); pos.pop(base); save(FILE_POS,pos)
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
                send(f"📊 *WINRATE V6.3 - {jam()}*\nWIN {wins} LOSS {loss} Total {total}\nWR {wr:.1f}% P/L {profit:+.1f}%")
    except: pass

def main():
    time.sleep(2); send(f"✅ *BOT V6.3 3 MODE AKTIF - {jam()}*\n🚀 Breakout | 🩹 Koreksi Sehat | 🔄 Reversal Awal\nTarget TP +5% Cepat")
    loop=0
    while True:
        try:
            if loop%4==0: cek_tp()
            if loop%2==0: handle()
            if loop%6==0:
                sig=analisa()
                if sig:
                    msg=f"🏆 *{len(sig)} SINYAL 3 MODE - {jam()}*\n"
                    for i,s in enumerate(sig,1): msg+=f"{'🚀' if s['mode']=='BREAKOUT' else '🩹' if s['mode']=='KOREKSI SEHAT' else '🔄'} #{i} {s['base']} {s['mode']} SCORE {s['score']}\n"
                    send(msg); time.sleep(2)
                    pos=load(FILE_POS,{}); cooldown=load(FILE_COOLDOWN,{}); hist=load(FILE_HISTORY,[])
                    for rank,s in enumerate(sig,1):
                        if s['base'] in pos: continue
                        send(fmt(s,rank)); pos[s['base']]=s['entry']; save(FILE_POS,pos)
                        cooldown[s['base']]=now().isoformat(); save(FILE_COOLDOWN,cooldown)
                        hist.append({'base':s['base'],'entry':s['entry'],'time':now().isoformat(),'score':s['score'],'status':'active','exit':0,'mode':s['mode']}); save(FILE_HISTORY,hist)
                        time.sleep(1.2)
            loop+=1; time.sleep(30)
        except Exception as e:
            print(f"ERR {e}",flush=True); time.sleep(20)

if __name__=="__main__": main()
