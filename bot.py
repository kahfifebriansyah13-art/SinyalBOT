import os, time, json, requests, threading, math
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timedelta, timezone
from collections import deque

print("BOT V6.1 NEW BUILD STARTING...", flush=True)

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
FILE_POS = "posisi.json"
FILE_COOLDOWN = "cooldown.json"
FILE_HISTORY = "history.json"
FILE_LAST = "last_update.json"

def now(): return datetime.now(timezone.utc) + timedelta(hours=7)
def jam(): return now().strftime("%H:%M WIB")

class H(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK V6.1")
    def log_message(self, *a): return
threading.Thread(target=lambda: HTTPServer(("0.0.0.0", int(os.getenv("PORT",8080))), H).serve_forever(), daemon=True).start()

def send(txt):
    try:
        r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data={"chat_id":CHAT_ID,"text":txt,"parse_mode":"Markdown"}, timeout=20)
        return r.status_code==200
    except: return False

def load_json(f, d):
    try: return json.load(open(f,'r'))
    except: return d

def save_json(f, d):
    try: json.dump(d, open(f,'w'))
    except: pass

def get_tickers():
    try: return requests.get("https://indodax.com/api/tickers", timeout=20, headers={"User-Agent":"Mozilla/5.0"}).json()['tickers']
    except: return {}

def get_ob_top10(base):
    try:
        data = requests.get(f"https://indodax.com/api/{base.lower()}_idr/depth", timeout=12).json()
        bids = data.get('buy',[])[:10]
        asks = data.get('sell',[])[:10]
        if not bids or not asks: return None
        total_b = sum(float(p)*float(v) for p,v in bids)
        total_s = sum(float(p)*float(v) for p,v in asks)
        if total_s==0: return None
        ratio = total_b/total_s
        spread = (float(asks[0][0])-float(bids[0][0]))/float(bids[0][0])*100
        whale = [float(p)*float(v) for p,v in bids if float(p)*float(v)>=50_000_000]
        return {'ratio':ratio,'spread':spread,'whale_count':len(whale),'whale_max':max(whale) if whale else 0,'buy_m':total_b,'sell_m':total_s}
    except: return None

# ========= SOSMED TRENDING =========
TRENDING_CACHE = {'time':None,'cg':set(),'poly':set(),'dex':set()}
def get_trending():
    global TRENDING_CACHE
    try:
        # cache 30 menit
        if TRENDING_CACHE['time'] and (now() - TRENDING_CACHE['time']).seconds < 1800:
            return TRENDING_CACHE
        cg_set=set()
        try:
            r=requests.get("https://api.coingecko.com/api/v3/search/trending", timeout=10).json()
            for c in r.get('coins',[]): cg_set.add(c['item']['symbol'].upper())
        except: pass
        
        poly_set=set()
        try:
            r=requests.get("https://gamma-api.polymarket.com/events?limit=30&order=volume24hr&ascending=false", timeout=10).json()
            txt = json.dumps(r).upper()
            # ambil semua symbol 2-5 huruf yang muncul di judul polymarket crypto
            for sym in ['BTC','ETH','SOL','PEPE','DOGE','SHIB','BONK','WIF','FLOKI','PEPE','ONDO','PUMP','DEGEN','XRP','ADA']:
                if sym in txt: poly_set.add(sym)
        except: pass

        dex_set=set()
        try:
            r=requests.get("https://api.dexscreener.com/token-boosts/top/v1", timeout=10).json()
            for x in r[:50]: dex_set.add(x.get('chainId','').upper())
        except: pass

        TRENDING_CACHE={'time':now(),'cg':cg_set,'poly':poly_set,'dex':dex_set}
        print(f"TRENDING UPDATE CG:{len(cg_set)} POLY:{len(poly_set)}", flush=True)
        return TRENDING_CACHE
    except:
        return TRENDING_CACHE

def check_social(base, trending):
    sources=[]
    if base in trending['cg']: sources.append("CoinGecko 🔥")
    if base in trending['poly']: sources.append("Polymarket 🔥")
    # cek dexscreener via symbol search
    try:
        r=requests.get(f"https://api.dexscreener.com/latest/dex/search/?q={base}", timeout=6).json()
        if r.get('pairs'):
            # jika ada pair dengan volume besar hari ini
            for p in r['pairs'][:3]:
                if float(p.get('volume',{}).get('h24',0))>100000: 
                    sources.append("DEX Ramai")
                    break
    except: pass
    return sources

# ========= TECHNICAL ANALYSIS =========
def get_ta(base):
    try:
        # ambil history 30 hari dari Indodax tradingview
        to_ts = int(datetime.now().timestamp())
        from_ts = to_ts - 40*24*3600
        url = f"https://indodax.com/tradingview/history?symbol={base}IDR&resolution=D&from={from_ts}&to={to_ts}"
        r=requests.get(url, timeout=10).json()
        closes = r.get('c',[])
        vols = r.get('v',[])
        if len(closes)<22: return {'ema_ok':False,'rsi':50,'vol_up':False,'score':0,'note':"Data <22"}
        # EMA 9 & 21
        def ema(arr, n):
            k=2/(n+1)
            e=arr[0]
            for x in arr[1:]: e = x*k + e*(1-k)
            return e
        ema9 = ema(closes[-9:],9)
        ema21 = ema(closes[-21:],21)
        ema_ok = ema9 > ema21
        # RSI 14
        deltas = [closes[i]-closes[i-1] for i in range(1,len(closes))]
        gains = [d if d>0 else 0 for d in deltas[-14:]]
        losses = [-d if d<0 else 0 for d in deltas[-14:]]
        avg_gain = sum(gains)/14
        avg_loss = sum(losses)/14 if sum(losses)!=0 else 0.01
        rs = avg_gain/avg_loss
        rsi = 100 - (100/(1+rs))
        vol_up = vols[-1] > (sum(vols[-7:-1])/6) if len(vols)>=7 else True
        score=0
        if ema_ok: score+=7
        if 40 <= rsi <= 70: score+=5
        if vol_up: score+=3
        note = f"EMA {'Bull' if ema_ok else 'Bear'} | RSI {rsi:.0f} | Vol {'Up' if vol_up else 'Down'}"
        return {'ema_ok':ema_ok,'rsi':rsi,'vol_up':vol_up,'score':score,'note':note}
    except Exception as e:
        return {'ema_ok':True,'rsi':55,'vol_up':True,'score':5,'note':"TA Default"}

def analisa():
    tickers = get_tickers()
    if not tickers: return []
    pos = load_json(FILE_POS,{})
    cooldown = load_json(FILE_COOLDOWN,{})
    trending = get_trending()

    # bersihkan cooldown 6 jam
    for k in list(cooldown.keys()):
        try:
            if now() - datetime.fromisoformat(cooldown[k]) > timedelta(hours=6): del cooldown[k]
        except: del cooldown[k]
    save_json(FILE_COOLDOWN, cooldown)

    cands=[]
    for pid,d in tickers.items():
        if not pid.endswith('_idr'): continue
        base=pid.split('_')[0].upper()
        if base in pos or base in cooldown or base in ['USDT','IDR','USDC']: continue
        try:
            last=float(d['last']); low=float(d['low']); high=float(d['high']); vol=float(d['vol_idr']); open_p=float(d.get('open',last))
            if vol<100_000_000 or low==0: continue
            naik=(last-low)/low*100
            posisi=(last-low)/(high-low)*100 if high!=low else 50
            if not (2 <= naik <= 9): continue
            if not (20 <= posisi <= 50): continue
            if last < open_p: continue
            cands.append((base,last,low,high,open_p,naik,posisi,vol))
        except: continue

    cands = sorted(cands, key=lambda x: x[7], reverse=True)[:30]
    print(f"SCAN {jam()}: {len(cands)} kandidat awal", flush=True)

    scored=[]
    for base,last,low,high,open_p,naik,posisi,vol in cands:
        ob = get_ob_top10(base)
        if not ob: continue
        if ob['ratio']<=1.0 or ob['spread']>1.5 or ob['whale_count']<1: continue

        ta = get_ta(base)
        social = check_social(base, trending)

        score=45
        if vol>=300_000_000: score+=12
        elif vol>=100_000_000: score+=7
        if 3<=naik<=7: score+=10
        else: score+=5
        if 20<=posisi<=35: score+=8
        else: score+=4
        if ob['ratio']>=2.0: score+=15
        elif ob['ratio']>=1.5: score+=8
        else: score+=3
        if ob['whale_count']>=2: score+=7
        else: score+=4

        score+=ta['score']
        if social: score+=15 if len(social)>=1 else 0

        if score>=70:
            scored.append({
                'base':base,'entry':last,'low':low,'high':high,'naik':naik,'pos':posisi,'vol':vol,
                'tp':last*1.05,'sl':last*0.95,'score':min(score,99),'ob':ob,'ta':ta,'social':social
            })
            print(f"LOLOS {base} SCORE {score} OB {ob['ratio']:.2f}x TA {ta['note']} SOS {social}", flush=True)
        if len(scored)>=10: break

    scored=sorted(scored, key=lambda x: (len(x['social']), x['ob']['ratio'], x['score']), reverse=True)
    return scored[:10]

def format_tmg(s, rank):
    ob=s['ob']; ta=s['ta']; social=s['social']
    trending_txt = " + ".join(social) if social else "Normal"
    sosmed_icon = "🔥 VIRAL" if social else "—"
    ta_icon = "✅" if ta['ema_ok'] else "⚠️"

    return f"""╔═══ #{rank} {s['base']}/IDR ✨ SCORE {s['score']} ═══╗
║ {sosmed_icon} TRENDING: {trending_txt}
║ 📊 SOSMED: {'Ramai di X & Reddit' if social else 'Belum ramai'}
║ {ta_icon} TA: {ta['note']}
╠═══════════════════════════╣
║ 📚 ORDER BOOK TOP 10
║ 💰 Buy Rp {ob['buy_m']/1e6:.1f}M vs Sell Rp {ob['sell_m']/1e6:.1f}M
║ 📈 Ratio {ob['ratio']:.2f}x | Spread {ob['spread']:.2f}%
║ 🐋 Whale Wall {ob['whale_count']}x ≥Rp50M Max Rp {ob['whale_max']/1e6:.0f}M
╠═══════════════════════════╣
║ 🕯️ DAILY
║ 📍 Pos {s['pos']:.0f}% dari Low | Naik +{s['naik']:.1f}%
║ 💧 Vol Rp {s['vol']/1e6:.0f}M
╠═══════════════════════════╣
║ 🎯 PLAN - {jam()}
║ 🟢 ENTRY Rp {s['entry']:,.0f}
║ 🎯 TP +5% Rp {s['tp']:,.0f}
║ 🔴 SL -5% Rp {s['sl']:,.0f}
╚═══════════════════════════╝"""

def cek_tp():
    tickers=get_tickers()
    if not tickers: return
    pos=load_json(FILE_POS,{})
    hist=load_json(FILE_HISTORY,[])
    for base,entry in list(pos.items()):
        try:
            last=float(tickers[f"{base.lower()}_idr"]['last'])
            if last>=entry*1.05:
                send(f"🏆 *TP +5% {base} HIT!* {jam()}\nEntry Rp {entry:,.0f} -> Rp {last:,.0f}")
                pos.pop(base); save_json(FILE_POS,pos)
                for h in hist:
                    if h['base']==base and h['status']=='active': h['status']='WIN'; h['exit']=last
                save_json(FILE_HISTORY,hist)
            elif last<=entry*0.95:
                send(f"🔴 *SL -5% {base} HIT* {jam()}\nEntry Rp {entry:,.0f} -> Rp {last:,.0f}")
                pos.pop(base); save_json(FILE_POS,pos)
                for h in hist:
                    if h['base']==base and h['status']=='active': h['status']='LOSS'; h['exit']=last
                save_json(FILE_HISTORY,hist)
        except: continue

def handle_command():
    try:
        last_id=load_json(FILE_LAST,{"id":0})["id"]
        r=requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={last_id+1}&timeout=5", timeout=10).json()
        for u in r.get('result',[]):
            save_json(FILE_LAST,{"id":u['update_id']})
            txt = u.get('message',{}).get('text','').lower().strip()
            if txt in ['/clear','/reset']:
                save_json(FILE_POS,{}); save_json(FILE_COOLDOWN,{}); send(f"✅ Reset posisi & cooldown - {jam()}")
            if txt in ['/winrate','/profit','/stats']:
                hist=load_json(FILE_HISTORY,[])
                wins=sum(1 for h in hist if h['status']=='WIN')
                loss=sum(1 for h in hist if h['status']=='LOSS')
                total=wins+loss
                wr = wins/total*100 if total>0 else 0
                # profit kotor
                profit = sum(((h['exit']/h['entry']-1)*100) for h in hist if h['status'] in ['WIN','LOSS'])
                send(f"""📊 *WINRATE STATS - {jam()}*
━━━━━━━━━━━━━━
🏆 WIN: {wins}
🔴 LOSS: {loss}
📈 Total Closed: {total}
🎯 Winrate: {wr:.1f}%
💰 Total P/L: {profit:+.1f}%
━━━━━━━━━━━━━━
Aktif: {len(load_json(FILE_POS,{}))} posisi""")
    except: pass

def main():
    time.sleep(2)
    send(f"✅ *BOT V6.1 NEW BUILD AKTIF - {jam()}*\n✨ Wall 50M Whale | TA + Sosmed Trending | Winrate Ready")
    loop=0
    while True:
        try:
            if loop%4==0: cek_tp()
            if loop%2==0: handle_command()
            pos=load_json(FILE_POS,{})
            if loop%12==0:
                sinyal=analisa()
                if sinyal:
                    msg=f"🏆 *{len(sinyal)} SINYAL TOP 10 - {jam()}*\n"
                    for i,s in enumerate(sinyal,1):
                        icon="🔥" if s['social'] else "✨"
                        msg+=f"{icon} #{i} {s['base']} SCORE {s['score']} OB {s['ob']['ratio']:.2f}x\n"
                    send(msg)
                    time.sleep(2)
                    cooldown=load_json(FILE_COOLDOWN,{}); hist=load_json(FILE_HISTORY,[])
                    for rank,s in enumerate(sinyal,1):
                        if s['base'] in pos: continue
                        send(format_tmg(s,rank))
                        pos[s['base']]=s['entry']; save_json(FILE_POS,pos)
                        cooldown[s['base']]=now().isoformat(); save_json(FILE_COOLDOWN,cooldown)
                        hist.append({'base':s['base'],'entry':s['entry'],'time':now().isoformat(),'score':s['score'],'status':'active','exit':0})
                        save_json(FILE_HISTORY,hist)
                        time.sleep(1.5)
            loop+=1; time.sleep(30)
        except Exception as e:
            print(f"ERR {e}", flush=True); time.sleep(20)

if __name__=="__main__": main()
