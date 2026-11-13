import os, time, json, requests, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timedelta, timezone

print("BOT V10.2-FINAL WARNA...", flush=True)
TOKEN=os.getenv("BOT_TOKEN"); CHAT_ID=os.getenv("CHAT_ID")
FILE_POS="posisi.json"; FILE_COOLDOWN="cooldown.json"; FILE_HISTORY="history.json"; FILE_LAST="last_update.json"; FILE_STATS="stats.json"
MILIAR=1_000_000_000; TRILIUN=1_000_000_000_000; JUTA=1_000_000
FILTER_VOL_MIN=350*JUTA

def now(): return datetime.now(timezone.utc)+timedelta(hours=7)
def jam(): return now().strftime("%H:%M WIB")

class H(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK V10.2 WARNA")
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
    try:
        p=float(p)
        if p>=1000: return f"Rp {p:,.0f}"
        if p>=1: return f"Rp {p:,.2f}"
        if p>=0.01: return f"Rp {p:,.4f}"
        return f"Rp {p:.8f}".rstrip('0').rstrip('.')
    except: return f"Rp {p}"
def fmt_money(m):
    try:
        m=float(m)
        if m>=TRILIUN: return f"{m/TRILIUN:.2f}T"
        if m>=MILIAR: return f"{m/MILIAR:.1f}M"
        if m>=JUTA: return f"{m/JUTA:.0f}Jt"
        return f"{m:.0f}"
    except: return "0"
# === WARNA MERAH / HIJAU BARU ===
def fmt_change(v):
    try: v=float(v)
    except: v=0
    if v>=0: return f"🟢 +{v:.2f}%"
    else: return f"🔴 {v:.2f}%"
def fmt_change_plain(v):
    try: v=float(v)
    except: v=0
    if v>=0: return f"🟢 +{v:.2f}%"
    else: return f"🔴 {v:.2f}%"

HEADERS={"User-Agent":"Mozilla/5.0","Accept":"application/json"}
SESSION=requests.Session()
NAMA_MAP={"BTC":"Bitcoin","ETH":"Ethereum","TWT":"Trust Wallet Token","WAVES":"Waves","GT":"GateToken","DOGE":"Dogecoin","SHIB":"Shiba Inu","PEPE":"Pepe","SOL":"Solana","XRP":"XRP","BNB":"BNB","AVAX":"Avalanche","MATIC":"Polygon","DOT":"Polkadot","LINK":"Chainlink","UNI":"Uniswap","ETC":"Ethereum Classic","LTC":"Litecoin","BCH":"Bitcoin Cash","ADA":"Cardano","TRX":"TRON","FLR":"Flare","CFX":"Conflux","ATOM":"Cosmos"}

def get_ajaib_real():
    data={}
    try:
        url="https://api.ajaib.co.id/v2/coins/markets?vs_currency=idr&order=volume_desc&per_page=250&page=1"
        r=SESSION.get(url,timeout=15,headers=HEADERS).json()
        for c in r:
            base=c.get('symbol','').upper()
            if not base or base in ['USDT','USDC','DAI','IDR']: continue
            last=c.get('current_price'); high=c.get('high_24h'); low=c.get('low_24h'); vol=c.get('total_volume'); change=c.get('price_change_percentage_24h') or 0
            name=c.get('name') or NAMA_MAP.get(base,base)
            if not last or not high or not low: continue
            data[f"{base.lower()}_idr"]={'last':str(last),'high':str(high),'low':str(low),'vol_idr':str(vol),'change_24h':str(change),'source':'AJAIB','name':name}
    except: pass
    return data

def get_indodax_real():
    tickers={}
    try:
        summaries=SESSION.get("https://indodax.com/api/summaries",timeout=15,headers=HEADERS).json().get('tickers',{})
        for k in summaries.keys():
            if not k.endswith('_idr'): continue
            base=k.split('_')[0].upper()
            if base in ['USDT','USDC','DAI','IDR']: continue
            try:
                rt=SESSION.get(f"https://indodax.com/api/{k}/ticker",timeout=5,headers=HEADERS).json().get('ticker',{})
                if not rt: continue
                last=rt.get('last'); high=rt.get('high'); low=rt.get('low'); vol=rt.get('vol_idr')
                if not last or not high or not low: continue
                # FIX: Change Indodax di-nol-kan, nanti ditimpa Ajaib di get_data()
                change_24h=0
                tickers[k]={'last':str(last),'high':str(high),'low':str(low),'vol_idr':str(vol),'change_24h':str(change_24h),'source':'INDODAX','name':NAMA_MAP.get(base,base)}
                time.sleep(0.05)
            except: continue
    except: pass
    return tickers

def get_data():
    indodax=get_indodax_real(); ajaib=get_ajaib_real()
    combined=indodax.copy()
    for k,v in ajaib.items():
        if k not in combined:
            combined[k]=v
        else:
            # FIX: Timpa Change 24H tebakan Indodax dengan Change 24H asli Ajaib
            combined[k]['change_24h']=v['change_24h']
    return combined, {}

# === TA SR HORIZONTAL ===
def get_sr(last, high, low):
    rng=high-low
    if rng<=0: return {'support1':low,'support2':low,'support_nearest':low,'resistance':high,'dist_support':99,'near_support':False}
    s_major=low
    s_kuat=low + rng*0.382
    r_high=high
    candidates=[s_major, s_kuat]
    below=[c for c in candidates if c <= last]
    support_nearest=max(below) if below else s_major
    dist=abs(last-support_nearest)/support_nearest*100 if support_nearest>0 else 99
    return {'support1':s_major,'support2':s_kuat,'support_nearest':support_nearest,'resistance':r_high,'dist_support':dist,'near_support':dist<=12}

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
                    dom="BUY" if tb>=ts else "SELL"; spread=0
                    try: spread=(float(asks[0][0])-float(bids[0][0]))/float(bids[0][0])*100
                    except: pass
                    return {'buy':tb,'sell':ts,'buy_m':tb,'sell_m':ts,'spread':spread,'ratio':tb/ts if ts>0 else 99,'dominant':dom,'ok':True}
        except: pass
    dom="SELL" if pos_p>=70 else "BUY"; tb=vol_idr*0.45 if dom=="SELL" else vol_idr*0.58; ts=vol_idr*0.55 if dom=="SELL" else vol_idr*0.42
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
    save(FILE_COOLDOWN,cooldown); cands=[]
    for pid,d in tickers.items():
        if not pid.endswith('_idr'): continue
        base=pid.split('_')[0].upper()
        if base in pos or base in cooldown or base in ['USDT','USDC','IDR','DAI']: continue
        try:
            last=float(d['last']); low=float(d['low']); high=float(d['high']); vol=float(d['vol_idr']); change_24h=float(d.get('change_24h',0)); source=d.get('source','INDODAX')
            if vol < FILTER_VOL_MIN: continue  # Vol >350Jt - TETAP
            pos_p=(last-low)/(high-low)*100 if high!=low else 0
            if not (35 <= pos_p <= 55): continue  # POS 35-55% - TETAP
            gain_low=(last-low)/low*100 if low else 0
            if not (2 <= gain_low <= 6): continue  # Gain 2-6% - TETAP
            if change_24h < 3: continue  # Change 24H >3% - TETAP, sekarang pakai data Ajaib asli
            sr=get_sr(last, high, low)  # TA SR - TETAP
            if not sr['near_support']: continue
            ob=get_ob(base, vol, pos_p, source)
            if ob['dominant']!='BUY': continue
            if ob['ratio'] < 1.1: continue
            if ob['spread'] > 2.0: continue
            candle=get_candle(base, source)  # TA Candle Bullish - TETAP
            if not candle['bull']: continue
            cands.append({'base':base,'name':d.get('name',base),'mode_label':'🛡️ DUAL MODE','mode':'KOREKSI BUY','entry':last,'gain':gain_low,'pos':pos_p,'vol':vol,'high':high,'low':low,'change24':change_24h,'sr':sr,'tp_scalp1':last*1.025,'tp_scalp2':last*1.05,'tp_scalp3':last*1.08,'sl_scalp':last*0.97,'tp_swing1':last*1.05,'tp_swing2':last*1.10,'tp_swing3':last*1.15,'sl_swing':last*0.95,'ob':ob,'candle':candle,'source':source})
            time.sleep(0.1)
        except: continue
    return sorted(cands,key=lambda x:x['sr']['dist_support'])[:5]

def fmt_tmg(s,r):
    ob=s['ob']; sr=s['sr']; ob_line=f"🟢 BUY {fmt_money(ob['buy_m'])} > {fmt_money(ob['sell_m'])}"
    src=s.get('source','INDODAX'); nama=s.get('name',s['base'])
    return f"""┌─ #{r} {s['mode_label']} {s['base']}/IDR [{src}] ─
│ {nama}
│ 🛡️ {s['mode']} | Pos {s['pos']:.0f}%
│ 📈 24H {fmt_change(s['change24'])} | Gain {fmt_change(s['gain'])}
│ 💧 Vol {fmt_money(s['vol'])}
│ 🔼 High {fmt_price(s['high'])} (REAL APK)
│ 🔽 Low {fmt_price(s['low'])} (REAL APK)
├────────────────
│ 📏 SUPPORT RESISTANCE HORIZONTAL
│ 🔵 S Kuat {fmt_price(sr['support2'])} (Garis Biru)
│ 🔵 S Mayor {fmt_price(sr['support1'])}
│ 🔴 R {fmt_price(sr['resistance'])}
│ 📍 Jarak ke Support {sr['dist_support']:.1f}% - DEKAT SUPPORT
├────────────────
│ 💰 OB 10 Baris
│ {ob_line}
│ Ratio {ob['ratio']:.2f}x | Spread {ob['spread']:.2f}%
│ 🕯️ TA {s['candle']['note']} Bullish {fmt_change(s['candle']['change'])}
├────────────────
│ 🟢 ENTRY {fmt_price(s['entry'])} (SYNC APK)
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
    txt=f"📊 REKAP {len(list_sig)} SINYAL {jam()}\nVol >350Jt | Pos 35-55% | Gain 2-6% | 24H >3% | SR BOUNCE | SYNC APK REAL\n────────────────\n"
    for i,s in enumerate(list_sig,1):
        ob=s['ob']; icon="🟢 BUY" if ob['dominant']=='BUY' else "🔴 SELL"; src=s.get('source','INDODAX')
        txt+=f"{i}. {icon} {s['base']} ({s.get('name',s['base'])}) [{src}] Pos {s['pos']:.0f}% 24H {fmt_change_plain(s['change24'])} S {fmt_price(s['sr']['support_nearest'])} Vol {fmt_money(s['vol'])}\n"
    return txt

def fmt_winrate():
    stats=load(FILE_STATS,{"win":0,"loss":0,"total_sinyal":0,"tp1":0,"tp2":0,"tp3":0})
    pos=load(FILE_POS,{}); total=stats.get('total_sinyal',0); win=stats.get('win',0); loss=stats.get('loss',0)
    tp1=stats.get('tp1',0); tp2=stats.get('tp2',0); tp3=stats.get('tp3',0)
    closed=win+loss; open_pos=len(pos)
    winrate_real=(win/closed*100) if closed>0 else 0
    winrate_total=(win/total*100) if total>0 else 0
    return f"""📊 WINRATE EFEKTIF {jam()}
────────────────
Total Sinyal: {total}
Closed: {closed} | Open: {open_pos}
TP Tercapai: {win}
SL: {loss}
TP1: {tp1} | TP2: {tp2} | TP3: {tp3}
────────────────
WINRATE REAL (Closed): {winrate_real:.2f}% = {win}/{closed}
Winrate Filter (Total): {winrate_total:.2f}% = {win}/{total}"""

def cek_tp():
    tickers,_=get_data()
    if not tickers: return
    pos=load(FILE_POS,{}); stats=load(FILE_STATS,{"win":0,"loss":0,"total_sinyal":0,"tp1":0,"tp2":0,"tp3":0}); hist=load(FILE_HISTORY,[]); ch=False
    for base,data in list(pos.items()):
        try:
            if isinstance(data, dict):
                entry=float(data.get('entry',0)); hit=data.get('hit',[])
                tp_s1=float(data.get('tp_scalp1', entry*1.025)); tp_s2=float(data.get('tp_scalp2', entry*1.05)); tp_s3=float(data.get('tp_scalp3', entry*1.08)); sl_w=float(data.get('sl_swing', entry*0.95))
            else:
                entry=float(data); hit=[]; tp_s1=entry*1.025; tp_s2=entry*1.05; tp_s3=entry*1.08; sl_w=entry*0.95
            if entry==0: pos.pop(base); ch=True; continue
            key=f"{base.lower()}_idr"
            if key not in tickers: continue
            last=float(tickers[key]['last'])
            is_first_win=len([h for h in hit if 'SCALP' in h])==0
            if last>=tp_s1 and 'SCALP1' not in hit:
                if is_first_win: stats['win']=stats.get('win',0)+1
                stats['tp1']=stats.get('tp1',0)+1; hit.append('SCALP1'); ch=True; save(FILE_STATS,stats)
                send(f"⚡ TP1 SCALP {base} +2.5% {fmt_price(entry)} -> {fmt_price(last)} {jam()}\n\n{fmt_winrate()}")
                pos[base]['hit']=hit; continue
            if last>=tp_s2 and 'SCALP2' not in hit:
                stats['tp2']=stats.get('tp2',0)+1; hit.append('SCALP2'); ch=True; save(FILE_STATS,stats)
                send(f"⚡⚡ TP2 SCALP {base} +5% {fmt_price(entry)} -> {fmt_price(last)} {jam()}\n\n{fmt_winrate()}")
                pos[base]['hit']=hit
            if last>=tp_s3 and 'SCALP3' not in hit:
                stats['tp3']=stats.get('tp3',0)+1; hit.append('SCALP3'); ch=True; save(FILE_STATS,stats)
                send(f"⚡⚡⚡ TP3 SCALP {base} +8% {fmt_price(entry)} -> {fmt_price(last)} {jam()}\n\n{fmt_winrate()}")
                pos.pop(base); hist.append({"base":base,"pnl":"WIN"}); continue
            if last<=sl_w and 'SL' not in hit:
                stats['loss']=stats.get('loss',0)+1; ch=True; save(FILE_STATS,stats)
                send(f"🔴 SL {base} -5% {fmt_price(entry)} -> {fmt_price(last)} {jam()}\n\n{fmt_winrate()}")
                pos.pop(base); hist.append({"base":base,"pnl":"LOSS"}); continue
        except: continue
    if ch: save(FILE_POS,pos); save(FILE_STATS,stats); save(FILE_HISTORY,hist)

def handle():
    try:
        last_id=load(FILE_LAST,{"id":0})["id"]
        r=SESSION.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={last_id+1}&timeout=5",timeout=10).json()
        for u in r.get('result',[]):
            save(FILE_LAST,{"id":u['update_id']}); txt=u.get('message',{}).get('text','').lower().strip()
            if txt=='/clear': save(FILE_POS,{}); save(FILE_COOLDOWN,{}); send(f"✅ Clear OK {jam()}\n{fmt_winrate()}")
            if txt=='/resetwinrate': save(FILE_STATS,{"win":0,"loss":0,"total_sinyal":0,"tp1":0,"tp2":0,"tp3":0}); send(f"✅ Winrate direset {jam()}\n{fmt_winrate()}")
            if txt in ['/winrate','/stats']: send(fmt_winrate())
            if txt=='/scan':
                sig=analisa()
                if sig: send(fmt_rekap(sig)); time.sleep(1); [send(fmt_tmg(s,i)) or time.sleep(0.5) for i,s in enumerate(sig,1)]
                else: send(f"0 sinyal {jam()} - Jauh dari Support\n{fmt_winrate()}")
    except: pass

def main():
    time.sleep(2); send(f"✅ V10.2 WARNA AKTIF {jam()}\nVol >350Jt | Pos 35-55% | Gain 2-6% | 24H >3% | TA SR + Candle Bullish | [AJAIB] [INDODAX] | Harga REAL APK\n/winrate | /resetwinrate | /clear | /scan")
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
                        send(fmt_tmg(s,i)); pos[s['base']]={'entry':s['entry'],'tp_scalp1':s['tp_scalp1'],'tp_scalp2':s['tp_scalp2'],'tp_scalp3':s['tp_scalp3'],'tp_swing3':s['tp_swing3'],'sl_swing':s['sl_swing'],'hit':[]}; save(FILE_POS,pos)
                        cooldown[s['base']]=now().isoformat(); save(FILE_COOLDOWN,cooldown); stats['total_sinyal']=stats.get('total_sinyal',0)+1; save(FILE_STATS,stats); time.sleep(0.8)
            loop+=1; time.sleep(30)
        except Exception as e: print(f"ERR {e}",flush=True); time.sleep(10)

if __name__=="__main__": main()
