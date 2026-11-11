import os, time, json, requests, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timedelta, timezone
print("BOT V6.9.5 FIX POSISI SAMA INDODAX...", flush=True)
TOKEN=os.getenv("BOT_TOKEN"); CHAT_ID=os.getenv("CHAT_ID")
FILE_POS="posisi.json"; FILE_COOLDOWN="cooldown.json"; FILE_HISTORY="history.json"; FILE_LAST="last_update.json"; FILE_STATS="stats.json"

def now(): return datetime.now(timezone.utc)+timedelta(hours=7)
def jam(): return now().strftime("%H:%M WIB")

class H(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK V6.9.5")
    def log_message(self,*a): return
threading.Thread(target=lambda: HTTPServer(("0.0.0.0",int(os.getenv("PORT",8080))),H).serve_forever(),daemon=True).start()

def send(txt):
    try: requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",data={"chat_id":CHAT_ID,"text":txt,"parse_mode":"Markdown"},timeout=20)
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
    if m>=1_000_000: return f"{m/1e6:.1f}M"
    if m>=1000: return f"{m/1000:.0f}K"
    return f"{m:.0f}"

HEADERS={"User-Agent":"Mozilla/5.0"}

def get_data():
    try:
        r=requests.get("https://indodax.com/api/summaries",timeout=15,headers=HEADERS).json()
        return r.get('tickers',{}), r.get('prices_24h',{})
    except:
        try:
            t=requests.get("https://indodax.com/api/tickers",timeout=10,headers=HEADERS).json()['tickers']
            return t, {}
        except: return {}, {}

def get_ob(base):
    try:
        rr=requests.get(f"https://indodax.com/api/{base.lower()}_idr/depth",timeout=8,headers=HEADERS)
        data=rr.json(); bids=data.get('buy',[]); asks=data.get('sell',[])
        tb=sum(float(p)*float(q) for p,q in bids[:15]); ts=sum(float(p)*float(q) for p,q in asks[:15])
        spread=(float(asks[0][0])-float(bids[0][0]))/float(bids[0][0])*100
        return {'buy':tb,'sell':ts,'buy_m':tb,'sell_m':ts,'spread':spread,'ratio':tb/ts if ts else 2,'fallback':False}
    except:
        return {'buy':100,'sell':10,'buy_m':100,'sell_m':10,'spread':0.5,'ratio':1.2,'fallback':True}

def get_candle(base):
    try:
        tr=requests.get(f"https://indodax.com/api/{base.lower()}_idr/trades",timeout=8,headers=HEADERS).json().get('trades',[])[:10]
        last=float(tr[0]['price']); avg=sum(float(x['price']) for x in tr)/len(tr)
        return {'bull':last>=avg,'note':'Candle Bull ✅' if last>=avg else 'Candle Bear ❌'}
    except: return {'bull':True,'note':'Candle Bull ✅'}

def analisa():
    tickers, prices24h=get_data()
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
            if low==0 or high==0 or vol<40_000_000: continue
            
            # RUMUS POS - SAMA DENGAN INDODAX HIGH LOW
            pos_p=(last-low)/(high-low)*100 if high!=low else 50
            gain_low=(last-low)/low*100
            
            # RUMUS 24H - SAMA DENGAN SEARCH INDODAX
            p24_raw=prices24h.get(pid)
            if p24_raw is None or p24_raw==0:
                change24=gain_low
            else:
                try:
                    prev=float(p24_raw)
                    change24=(last-prev)/prev*100 if prev!=0 else gain_low
                except:
                    change24=gain_low
            
            # FILTER TETAP SAMA SEPERTI V6.9.3 - TIDAK DIUBAH
            if pos_p < 45: continue
            if change24 < 0.5: continue
            
            cands.append((base,last,low,high,gain_low,pos_p,vol,change24))
        except: continue

    cands=sorted(cands,key=lambda x:x[5],reverse=True)[:25]
    print(f"SCAN V6.9.5 {jam()}: {len(cands)} kandidat Pos>45%",flush=True)
    scored=[]
    for base,last,low,high,gain_low,pos_p,vol,change24 in cands:
        ob=get_ob(base); candle=get_candle(base)
        if ob['buy']<ob['sell'] and not ob['fallback']: continue
        if not candle['bull'] and pos_p<55: continue
        mode="🚀 BREAKOUT" if pos_p>=75 else "🩹 KOREKSI SEHAT" if pos_p>=55 else "🔄 REVERSAL AWAL"
        scored.append({'base':base,'mode':mode,'trend':"Bullish",'entry':last,'gain':gain_low,'pos':pos_p,'vol':vol,'tp':last*1.05,'sl':last*0.95,'ob':ob,'candle':candle,'score':75,'change24':change24})
        if len(scored)>=5: break
    return scored

def fmt_tmg(s,r):
    ob=s['ob']; est=" EST" if ob['fallback'] else ""
    return f"""╔═══ #{r} {s['mode']} {s['base']}/IDR SCORE {s['score']} ═══╗
║ 🔥 {s['trend']} | {s['candle']['note']} - Pos {s['pos']:.0f}%
║ 📈 24h {s['change24']:.2f}% | Low {s['gain']:.2f}% | Vol Rp {s['vol']/1e6:.0f}M
╠═══════════════════════════╣
║ 💰 OB BUY>SELL{est} ✅
║ 💵 Buy Rp {fmt_money(ob['buy_m'])} vs Sell Rp {fmt_money(ob['sell_m'])}
║ 📊 Ratio {ob['ratio']:.2f}x Spread {ob['spread']:.2f}%
╠═══════════════════════════╣
║ 🎯 TP +5% - {jam()}
║ 🟢 ENTRY {fmt_price(s['entry'])}
║ 🎯 TP {fmt_price(s['tp'])} (+5%)
║ 🔴 SL {fmt_price(s['sl'])} (-5%)
╚═══════════════════════════╝"""

def cek_tp():
    tickers,_=get_data()
    if not tickers: return
    pos=load(FILE_POS,{}); stats=load(FILE_STATS,{"win":0,"loss":0,"tp_list":[]}); hist=load(FILE_HISTORY,[])
    ch=False
    for base,entry in list(pos.items()):
        try:
            last=float(tickers[f"{base.lower()}_idr"]['last'])
            if last>=entry*1.05:
                send(f"🏆 *TP1 HIT {base} +5%!* {fmt_price(entry)} → {fmt_price(last)} - {jam()}")
                stats["win"]+=1; stats["tp_list"].append({"base":base,"time":jam()}); pos.pop(base); hist.append({"base":base,"pnl":"WIN"}); ch=True
            elif last<=entry*0.95:
                send(f"🔴 *SL {base} -5%* {fmt_price(entry)} → {fmt_price(last)} - {jam()}")
                stats["loss"]+=1; pos.pop(base); hist.append({"base":base,"pnl":"LOSS"}); ch=True
        except: continue
    if ch: save(FILE_POS,pos); save(FILE_STATS,stats); save(FILE_HISTORY,hist)

def handle():
    try:
        last_id=load(FILE_LAST,{"id":0})["id"]
        r=requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={last_id+1}&timeout=5",timeout=10).json()
        for u in r.get('result',[]):
            save(FILE_LAST,{"id":u['update_id']})
            txt=u.get('message',{}).get('text','').lower().strip()
            if txt=='/clear': save(FILE_POS,{}); save(FILE_COOLDOWN,{}); send(f"✅ Reset - {jam()}")
            if txt in ['/winrate','/tp','/tp1','/profit','/stats']:
                stats=load(FILE_STATS,{"win":0,"loss":0,"tp_list":[]}); pos=load(FILE_POS,{})
                total=stats["win"]+stats["loss"]; wr=stats["win"]/total*100 if total else 0
                daftar="\n".join([f"- {x['base']} {x['time']}" for x in stats["tp_list"][-10:]]) or "Belum ada TP1"
                send(f"""📊 *STAT TP1 - {jam()}*
🏆 TP1 HIT: {stats['win']}
🔴 SL: {stats['loss']}
Total: {total} | WR: {wr:.1f}%
Aktif: {len(pos)}

*10 TP Terakhir:*
{daftar}""")
    except: pass

def main():
    time.sleep(1); send(f"✅ *BOT V6.9.5 AKTIF - {jam()}*\nPOS & 24h sama Indodax\nFormat & Filter tetap")
    loop=0
    while True:
        try:
            if loop%2==0: handle()
            if loop%4==0: cek_tp()
            if loop%12==0:
                sig=analisa()
                if sig:
                    msg=f"🏆 *{len(sig)} SINYAL TMG - {jam()}*\n"
                    for i,s in enumerate(sig,1): msg+=f"#{i} {s['base']} 24h {s['change24']:.2f}% Pos {s['pos']:.0f}% {s['mode']}\n"
                    send(msg); time.sleep(1)
                    pos=load(FILE_POS,{}); cooldown=load(FILE_COOLDOWN,{})
                    for i,s in enumerate(sig,1):
                        if s['base'] in pos: continue
                        send(fmt_tmg(s,i)); pos[s['base']]=s['entry']; save(FILE_POS,pos); cooldown[s['base']]=now().isoformat(); save(FILE_COOLDOWN,cooldown); time.sleep(1)
            loop+=1; time.sleep(30)
        except Exception as e:
            print(f"ERR {e}",flush=True); time.sleep(15)

if __name__=="__main__": main()
