import os, time, json, requests, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timedelta, timezone
print("BOT V8.0 FINAL WINRATE 80%...", flush=True)
TOKEN=os.getenv("BOT_TOKEN"); CHAT_ID=os.getenv("CHAT_ID")
FILE_POS="posisi.json"; FILE_COOLDOWN="cooldown.json"; FILE_HISTORY="history.json"; FILE_LAST="last_update.json"; FILE_STATS="stats.json"

def now(): return datetime.now(timezone.utc)+timedelta(hours=7)
def jam(): return now().strftime("%H:%M WIB")

class H(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK V8.0 FINAL")
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

def get_24h(last,price_raw,low):
    try:
        if price_raw:
            prev=float(price_raw)
            if prev>0:
                ch=(last-prev)/prev*100
                gain_low=(last-low)/low*100 if low else 0
                # FIX UCJL 41.97% == Low 41.97% = FAKE
                if abs(ch - gain_low) < 0.2 and abs(ch)>12:
                    return None
                return ch
    except: pass
    return None

def get_ob(base):
    try:
        rr=requests.get(f"https://indodax.com/api/{base.lower()}_idr/depth",timeout=8,headers=HEADERS)
        data=rr.json(); bids=data.get('buy',[]); asks=data.get('sell',[])
        if not bids or not asks: raise Exception()
        tb=sum(float(p)*float(q) for p,q in bids[:25]); ts=sum(float(p)*float(q) for p,q in asks[:25])
        spread=(float(asks[0][0])-float(bids[0][0]))/float(bids[0][0])*100
        return {'buy':tb,'sell':ts,'buy_m':tb,'sell_m':ts,'spread':spread,'ratio':tb/ts if ts else 0,'fallback':False}
    except:
        return None

def get_candle(base):
    try:
        tr=requests.get(f"https://indodax.com/api/{base.lower()}_idr/trades",timeout=8,headers=HEADERS).json().get('trades',[])[:20]
        last=float(tr[0]['price']); avg=sum(float(x['price']) for x in tr)/len(tr)
        bull=last>=avg; ch=(last-avg)/avg*100 if avg else 0
        return {'bull':bull,'note':'Candle Bull ✅' if bull else 'Candle Bear ❌','change':ch}
    except: return {'bull':False,'note':'Candle Bear ❌','change':-1}

def analisa():
    tickers, prices24h=get_data()
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
        if base in pos or base in cooldown or base in ['USDT','USDC','IDR','DAI','USDE','USD1']: continue
        try:
            last=float(d['last']); low=float(d['low']); high=float(d['high']); vol=float(d['vol_idr'])
            if low==0 or high==0: continue
            # FILTER KETAT WINRATE 80%
            if vol < 100_000_000: continue  # Vol minimal 100M
            pos_p=(last-low)/(high-low)*100 if high!=low else 0
            if pos_p < 70 or pos_p > 96: continue  # Hanya 70-96%
            gain_low=(last-low)/low*100 if low else 0
            if gain_low < 1 or gain_low > 15: continue

            ch=get_24h(last,prices24h.get(pid),low)
            if ch is None: continue
            if ch < 0.8 or ch > 8: continue  # 24h 0.8-8% saja, skip pump 40%

            ob=get_ob(base)
            if ob is None: continue
            if ob['buy'] < 200_000_000: continue
            if ob['ratio'] < 2.0: continue  # Buy harus 2x Sell
            if ob['spread'] > 1.0: continue

            candle=get_candle(base)
            if not candle['bull']: continue

            cands.append((base,last,low,high,gain_low,pos_p,vol,ch,ob,candle))
        except: continue

    cands=sorted(cands,key=lambda x:(x[5],x[7]),reverse=True)
    print(f"SCAN V8.0 {jam()}: {len(cands)} kandidat LULUS FILTER 80%",flush=True)

    scored=[]
    for base,last,low,high,gain_low,pos_p,vol,change24,ob,candle in cands[:5]:
        if pos_p>=85: mode="🚀 BREAKOUT"; score=90
        elif pos_p>=75: mode="🩹 KOREKSI SEHAT"; score=75
        else: mode="🔄 REVERSAL AWAL"; score=60
        scored.append({'base':base,'mode':mode,'trend':"Bullish Kuat",'entry':last,'gain':gain_low,'pos':pos_p,'vol':vol,'tp':last*1.05,'sl':last*0.95,'ob':ob,'candle':candle,'score':score,'change24':change24})
    return scored

def fmt_tmg(s,r):
    ob=s['ob']
    return f"""╔═══ #{r} {s['mode']} {s['base']}/IDR SCORE {s['score']} ═══╗
║ 🔥 {s['trend']} | {s['candle']['note']} - Pos {s['pos']:.0f}%
║ 📈 24h {s['change24']:.2f}% (Indodax) | Low {s['gain']:.2f}% | Vol Rp {s['vol']/1e6:.0f}M
╠═══════════════════════════╣
║ 💰 OB BUY>SELL ✅
║ 💵 Buy Rp {fmt_money(ob['buy_m'])} vs Sell Rp {fmt_money(ob['sell_m'])}
║ 📊 Ratio {ob['ratio']:.2f}x Spread {ob['spread']:.2f}%
║ 🕯️ {s['candle']['note']} {s['candle']['change']:+.2f}%
╠═══════════════════════════╣
║ 🎯 TP +5% - {jam()}
║ 🟢 ENTRY {fmt_price(s['entry'])}
║ 🎯 TP {fmt_price(s['tp'])} (+5%)
║ 🔴 SL {fmt_price(s['sl'])} (-5%)
╚═══════════════════════════╝"""

def cek_tp():
    tickers,_=get_data()
    if not tickers: return
    pos=load(FILE_POS,{}); stats=load(FILE_STATS,{"win":0,"loss":0,"total_sinyal":0,"tp_list":[]}); hist=load(FILE_HISTORY,[])
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
            if txt=='/resetstats': save(FILE_STATS,{"win":0,"loss":0,"total_sinyal":0,"tp_list":[]}); send(f"✅ Stats reset - {jam()}")
            if txt=='/scan':
                send(f"🔍 Scan V8.0 Filter 80% - {jam()}")
                sig=analisa()
                if sig:
                    stats=load(FILE_STATS,{"win":0,"loss":0,"total_sinyal":0,"tp_list":[]}); stats["total_sinyal"]+=len(sig); save(FILE_STATS,stats)
                    for i,s in enumerate(sig,1): send(fmt_tmg(s,i)); time.sleep(0.8)
                else: send(f"📭 0 sinyal lulus filter ketat 80% - market belum ideal - {jam()}\nCoba lagi nanti, ini yang bikin winrate tinggi")
            if txt in ['/winrate','/stats']:
                stats=load(FILE_STATS,{"win":0,"loss":0,"total_sinyal":0,"tp_list":[]}); pos=load(FILE_POS,{})
                total=stats["total_sinyal"]; wr=stats["win"]/total*100 if total>0 else 0
                daftar="\n".join([f"- {x['base']} {x['time']}" for x in stats["tp_list"][-10:]]) or "Belum ada TP"
                send(f"""📊 *WINRATE FILTER V8.0 - {jam()}*

📤 Total Sinyal Dikirim: {total}
🏆 TP Tercapai: {stats['win']}
🔴 SL: {stats['loss']}
⏳ Aktif: {len(pos)}

*WINRATE = TP / Total Sinyal*
✅ {wr:.1f}% (Target >80%)

*10 TP Terakhir:*
{daftar}

Filter ketat = sinyal sedikit tapi akurat. Ketik /resetstats untuk mulai hitung baru.""")
    except: pass

def main():
    time.sleep(1); send(f"✅ *V8.0 FINAL AKTIF - {jam()}*\n✔️ Filter ketat target WR 80%\n✔️ 24h 100% sama Indodax\n✔️ Score 90/75/60 + OB + Candle\nKetik /winrate untuk cek")
    loop=0
    while True:
        try:
            if loop%2==0: handle()
            if loop%4==0: cek_tp()
            if loop%18==0:  # scan tiap 9 menit biar tidak spam
                sig=analisa()
                if sig:
                    stats=load(FILE_STATS,{"win":0,"loss":0,"total_sinyal":0,"tp_list":[]}); stats["total_sinyal"]+=len(sig); save(FILE_STATS,stats)
                    msg=f"🏆 *{len(sig)} SINYAL V8.0 - {jam()}*\nFilter 80% | Total: {stats['total_sinyal']} | TP: {stats['win']}\n"
                    for i,s in enumerate(sig,1): msg+=f"#{i} {s['base']} 24h {s['change24']:.2f}% Pos {s['pos']:.0f}% {s['mode']} SCORE {s['score']}\n"
                    send(msg); time.sleep(1)
                    pos=load(FILE_POS,{}); cooldown=load(FILE_COOLDOWN,{})
                    for i,s in enumerate(sig,1):
                        if s['base'] in pos: continue
                        send(fmt_tmg(s,i)); pos[s['base']]=s['entry']; save(FILE_POS,pos); cooldown[s['base']]=now().isoformat(); save(FILE_COOLDOWN,cooldown); time.sleep(1)
            loop+=1; time.sleep(30)
        except Exception as e:
            print(f"ERR {e}",flush=True); time.sleep(15)

if __name__=="__main__": main()
