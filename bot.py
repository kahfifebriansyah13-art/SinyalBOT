import requests, os, time, json, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timedelta, timezone

print("BOT V4.7 DELISTING FILTER STARTING...", flush=True)
BOT_TOKEN=os.getenv("BOT_TOKEN"); CHAT_ID=os.getenv("CHAT_ID")
FILE="posisi_aktif.json"; COOLDOWN_FILE="cooldown.json"; LAST_UPDATE_FILE="last_update.json"; DELISTED_FILE="delisted.json"

# DAFTAR KOIN YANG SUDAH PASTI DELISTING - TIDAK PERNAH MASUK FILTER
DELISTED_HARD = ['SKYAI','BCHABC','BCHSV','BTG','ABT','ANON','BIFI','BTT','XLM','XRP','BCHA','LUNA','LUNC','UST']

def now_wib(): return datetime.now(timezone.utc) + timedelta(hours=7)
def format_wib(): return now_wib().strftime("%H:%M WIB")

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK V4.7 DELISTING FILTER")
    def log_message(self, format, *args): return
def run_health():
    port=int(os.getenv("PORT",8080))
    try: HTTPServer(("0.0.0.0",port),HealthHandler).serve_forever()
    except: pass
threading.Thread(target=run_health,daemon=True).start()

def kirim(pesan):
    for i in range(3):
        try:
            r=requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",data={"chat_id":CHAT_ID,"text":pesan,"parse_mode":"Markdown"},timeout=25)
            if r.status_code==200: return True
        except: time.sleep(2)
    return False

def load_json(f,d):
    try: return json.load(open(f,'r'))
    except: return d
def save_json(f,d): json.dump(d,open(f,'w'))

def get_tickers():
    try: return requests.get("https://indodax.com/api/tickers",timeout=20,headers={"User-Agent":"Mozilla/5.0"}).json()['tickers']
    except: return {}

def get_active_pairs():
    """Ambil daftar pair yang masih aktif di Indodax"""
    try:
        r=requests.get("https://indodax.com/api/pairs",timeout=10,headers={"User-Agent":"Mozilla/5.0"}).json()
        # pairs format: [{"id":"btc_idr",...},...]
        active = [p['id'].upper() for p in r] if isinstance(r, list) else []
        return set(active)
    except:
        return None # kalau gagal, jangan filter

def get_orderbook_analysis(base):
    try:
        pair=f"{base.lower()}_idr"
        resp=requests.get(f"https://indodax.com/api/{pair}/depth",timeout=10,headers={"User-Agent":"Mozilla/5.0"})
        # FILTER DELISTING: kalau balik HTML atau error
        if "text/html" in resp.headers.get("Content-Type",""):
            print(f"DELISTED DETECT {base}: no depth (HTML)",flush=True)
            return "DELISTED"
        data=resp.json()
        bids=data.get('buy',[])[:10]; asks=data.get('sell',[])[:10]
        if not bids or not asks: 
            print(f"DELISTED DETECT {base}: empty OB",flush=True)
            return "DELISTED"
        total_buy=sum(float(p)*float(v) for p,v in bids); total_sell=sum(float(p)*float(v) for p,v in asks)
        if total_sell==0: return None
        ratio=total_buy/total_sell; spread=(float(asks[0][0])-float(bids[0][0]))/float(bids[0][0])*100; walls=sum(1 for p,v in bids if float(p)*float(v)>5_000_000)
        print(f"OB TOP10 {base}: Buy {total_buy/1e6:.1f}M vs Sell {total_sell/1e6:.1f}M = {ratio:.2f}x Wall {walls}",flush=True)
        return {'ratio':ratio,'buy_idr':total_buy,'sell_idr':total_sell,'spread':spread,'big_walls':walls}
    except Exception as e:
        print(f"DELISTED DETECT {base}: {str(e)[:40]}",flush=True)
        return "DELISTED"

def analisa_ranking():
    tickers=get_tickers()
    if not tickers: return []
    # Load delisted dinamis
    delisted_dynamic = load_json(DELISTED_FILE, {})
    now = now_wib()
    # Hapus delisted yang sudah 24 jam
    for k in list(delisted_dynamic.keys()):
        try:
            t=datetime.fromisoformat(delisted_dynamic[k])
            if now - t > timedelta(hours=24): del delisted_dynamic[k]
        except: del delisted_dynamic[k]
    save_json(DELISTED_FILE, delisted_dynamic)

    active_pairs = get_active_pairs()
    if active_pairs:
        print(f"ACTIVE PAIRS: {len(active_pairs)} pair aktif",flush=True)

    posisi=load_json(FILE,{}); cooldown=load_json(COOLDOWN_FILE,{})
    for k in list(cooldown.keys()):
        try:
            t=datetime.fromisoformat(cooldown[k])
            if now - t > timedelta(hours=6): del cooldown[k]
        except: del cooldown[k]
    save_json(COOLDOWN_FILE,cooldown)

    scored=[]; cands=[]
    for pair,d in tickers.items():
        if not pair.endswith('_idr'): continue
        base=pair.split('_')[0].upper()
        # FILTER 1: Hard blacklist delisting
        if base in DELISTED_HARD: continue
        # FILTER 2: Dynamic blacklist delisting
        if base in delisted_dynamic: continue
        # FILTER 3: Tidak ada di daftar pairs aktif
        if active_pairs and f"{base}_IDR" not in active_pairs: 
            print(f"SKIP DELISTED {base}: tidak ada di pairs aktif",flush=True)
            continue
        if base in posisi or base in cooldown or base in ['USDT','USDC','DAI','IDR']: continue
        try:
            last=float(d['last']); low=float(d['low']); high=float(d['high']); vol=float(d['vol_idr']); open_p=float(d.get('open',last))
            if vol<100_000_000 or low==0: continue
            naik=(last-low)/low*100; pos=(last-low)/(high-low)*100 if high!=low else 50
            if not (2.0 <= naik <= 9.0): continue
            if not (20 <= pos <= 50): continue
            if last < open_p: continue
            cands.append((base,d,naik,pos,vol,last,low,high,open_p))
        except: continue

    cands=sorted(cands,key=lambda x:x[4],reverse=True)[:25]
    print(f"CHECK TOP10 {format_wib()}: {len(cands)} kandidat (sudah filter delisting)",flush=True)

    for base,d,naik,pos,vol,last,low,high,open_p in cands:
        ob=get_orderbook_analysis(base)
        if ob == "DELISTED":
            # Auto-blacklist 24 jam
            delisted_dynamic[base]=now.isoformat()
            save_json(DELISTED_FILE, delisted_dynamic)
            print(f"AUTO BLACKLIST {base} 24 jam",flush=True)
            continue
        if not ob: continue
        if ob['ratio'] <= 1.0: continue
        if ob['spread'] > 1.5: continue
        if ob['big_walls'] < 1: continue
        score=50
        if vol>=300_000_000: score+=15
        elif vol>=100_000_000: score+=8
        if 3.0 <= naik <= 7.0: score+=15
        if 20 <= pos <= 35: score+=12
        else: score+=6
        if ob['ratio']>=2.0: score+=20
        elif ob['ratio']>=1.5: score+=12
        else: score+=6
        if ob['big_walls']>=3: score+=8
        else: score+=4
        if score>=75:
            print(f"LOLOS {base}: Score {score} Ratio {ob['ratio']:.2f}x",flush=True)
            scored.append({'base':base,'entry':last,'low':low,'high':high,'open':open_p,'tp1':last*1.05,'tp2':last*1.10,'sl':last*0.95,'naik':naik,'vol':vol,'pos':pos,'score':min(score,100),'is_trending':False,'orderbook':ob})
        if len(scored)>=10: break

    scored=sorted(scored,key=lambda x:(x['orderbook']['ratio'],x['score']),reverse=True)
    print(f"RESULT TOP10 {format_wib()}: {len(scored)} lolos (delisting sudah dibuang)",flush=True)
    return scored[:10]

# ... (fungsi cek_tp, cek_command, main sama seperti V4.6)
def cek_tp():
    tickers=get_tickers()
    if not tickers: return
    pos=load_json(FILE,{})
    for base,data in list(pos.items()):
        pair=f"{base.lower()}_idr"
        if pair not in tickers: continue
        try:
            last=float(tickers[pair]['last']); entry=data['entry']
            if last>=entry*1.10: kirim(f"🏆 TP2 +10% {base}"); del pos[base]; save_json(FILE,pos)
            elif last>=entry*1.05 and not data.get('tp1_hit'): kirim(f"🎯 TP1 +5% {base}"); pos[base]['tp1_hit']=True; save_json(FILE,pos)
            elif last<=entry*0.95: kirim(f"🔴 SL -5% {base}"); del pos[base]; save_json(FILE,pos)
        except: continue

def cek_command():
    try:
        last_id=load_json(LAST_UPDATE_FILE,{"id":0})["id"]
        r=requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={last_id+1}&timeout=5",timeout=10).json()
        if not r.get('result'): return
        for u in r['result']:
            save_json(LAST_UPDATE_FILE,{"id":u['update_id']})
            txt=u.get('message',{}).get('text','').lower().strip()
            if txt=='/clear': save_json(FILE,{}); save_json(COOLDOWN_FILE,{}); save_json(DELISTED_FILE,{}); kirim(f"✅ Reset semua termasuk delisting - {format_wib()}")
            elif txt in ['/profit','/status']: kirim(f"📊 Cek profit - {format_wib()}")
    except: pass

def format_tmg(s,rank):
    ob=s.get('orderbook',{}); return f"""#{rank} {s['base']}/IDR SCORE {s['score']}
📚 OB TOP10: {ob.get('ratio',0):.2f}x Wall {ob.get('big_walls',0)} Pos {s['pos']:.0f}% Naik +{s['naik']:.1f}%
ENTRY Rp {s['entry']:,.0f} TP1 Rp {s['tp1']:,.0f} (+5%) SL Rp {s['sl']:,.0f}"""

def main():
    time.sleep(2)
    kirim(f"✅ BOT V4.7 DELISTING FILTER AKTIF - {format_wib()}\nFilter delisting 3 lapis aktif")
    print(f"MAIN LOOP V4.7 {format_wib()}",flush=True)
    loop=0
    while True:
        try:
            if loop%6==0: cek_tp()
            if loop%3==0: cek_command()
            pos=load_json(FILE,{})
            if len(pos)==0 and loop%20==0:
                sinyal=analisa_ranking()
                if sinyal:
                    jam=format_wib(); pesan=f"🏆 {len(sinyal)} SINYAL TOP10 - {jam} (tanpa delisting)\n"
                    for i,s in enumerate(sinyal,1): pesan+=f"{i}. {s['base']} {s['score']} OB {s['orderbook']['ratio']:.2f}x\n"
                    kirim(pesan); time.sleep(3)
                    cooldown=load_json(COOLDOWN_FILE,{})
                    for rank,s in enumerate(sinyal,1):
                        if s['base'] in pos: continue
                        kirim(format_tmg(s,rank)); pos[s['base']]={'entry':s['entry'],'tp1_hit':False}; save_json(FILE,pos); cooldown[s['base']]=now_wib().isoformat(); save_json(COOLDOWN_FILE,cooldown); time.sleep(2)
            loop+=1; time.sleep(30)
        except Exception as e: print(f"ERR {e}",flush=True); time.sleep(20)
if __name__=="__main__": main()
