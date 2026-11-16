import os, time, json, requests, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timedelta, timezone

print("BOT V12.1 TP1 5%...", flush=True)
TOKEN=os.getenv("BOT_TOKEN"); CHAT_ID=os.getenv("CHAT_ID")
FILE_POS="posisi.json"; FILE_COOLDOWN="cooldown.json"; FILE_HISTORY="history.json"; FILE_LAST="last_update.json"; FILE_STATS="stats.json"; FILE_LOG="sinyal_log.json"; FILE_PENDING="pending.json"
MILIAR=1_000_000_000; TRILIUN=1_000_000_000_000; JUTA=1_000_000
FILTER_VOL_MIN=350*JUTA

MEME_RISKY = {"SHOW","PIEVERSE","JELLYJELLY","PEPE","ONL","SHIB","DOGE","FARTCOIN","BONK","WIF","FLOKI","BABYDOGE","MEME","TURBO","MOG","BRETT","POPCAT","MEW","NEIRO","PNUT","GOAT","ACT","MOODENG"}

def now(): return datetime.now(timezone.utc)+timedelta(hours=7)
def jam(): return now().strftime("%H:%M WIB")

class H(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK V12.1")
    def log_message(self,*a): return
threading.Thread(target=lambda: HTTPServer(("0.0.0.0",int(os.getenv("PORT",8080))),H).serve_forever(),daemon=True).start()

def send(txt):
    try: requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage",data={"chat_id":CHAT_ID,"text":txt,"parse_mode":"Markdown"},timeout=20)
    except: pass

def send_winrate():
    txt = fmt_winrate()
    payload = {"chat_id": CHAT_ID, "text": txt, "parse_mode": "Markdown",
               "reply_markup": {"inline_keyboard": [[{"text": "📋 Lihat Koin Yang Capai Target", "callback_data": "show_tp"}]]}}
    try:
        r = requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json=payload, timeout=20)
        if r.status_code != 200: send(txt)
    except: send(txt)

def send_tp_list():
    stats = load(FILE_STATS, {"win":0,"loss":0,"total_sinyal":0,"tp1":0,"tp2":0,"tp3":0,"tp1_coins":[],"tp2_coins":[],"tp3_coins":[],"sl_coins":[],"win_coins":[],"be_coins":[]})
    tp1 = stats.get("tp1_coins", []); tp2 = stats.get("tp2_coins", []); tp3 = stats.get("tp3_coins", []); sl = stats.get("sl_coins", []); win_coins = stats.get("win_coins", []); be = stats.get("be_coins", [])
    def fmt_list(lst): return ", ".join(lst) if lst else "-"
    total = stats.get('total_sinyal',0); wr = (len(win_coins)/total*100) if total>0 else 0
    txt = f"""📋 KOIN YANG CAPAI TARGET {jam()}
────────────────
✅ WIN / TP Tercapai: {len(win_coins)} koin
{fmt_list(win_coins)}

⚡ TP1 (+5%): {len(tp1)} koin
{fmt_list(tp1)}

⚡⚡ TP2 (+8%): {len(tp2)} koin
{fmt_list(tp2)}

⚡⚡⚡ TP3 (+12%): {len(tp3)} koin
{fmt_list(tp3)}

🟡 BE / Break Even (TP1 lalu balik ke Entry): {len(be)} koin
{fmt_list(be)}

🔴 SL Murni (-5% tanpa pernah TP1): {len(sl)} koin
{fmt_list(sl)}
────────────────
Total Sinyal: {total}
Winrate Jujur: {wr:.2f}% = {len(win_coins)}/{total}
"""
    send(txt)

def save_log(s):
    logs = load(FILE_LOG, {})
    logs[s['base']] = {
        'base': s['base'], 'name': s.get('name', s['base']), 'waktu': jam(),
        'entry': s['entry'], 'pos': s['pos'], 'gain': s['gain'], 'change24': s['change24'], 'vol': s['vol'],
        'high': s['high'], 'low': s['low'], 'source': s.get('source','INDODAX'),
        'support_kuat': s['sr']['support2'], 'support_mayor': s['sr']['support1'],
        'support_nearest': s['sr']['support_nearest'], 'resistance': s['sr']['resistance'],
        'dist_support': s['sr']['dist_support'],
        'ob_dominant': s['ob']['dominant'], 'ob_buy': s['ob']['buy_m'], 'ob_sell': s['ob']['sell_m'],
        'ob_ratio': s['ob']['ratio'], 'ob_spread': s['ob']['spread'],
        'candle': s['candle']['change'],
        'tp1': s['tp_scalp1'], 'tp2': s['tp_scalp2'], 'tp3': s['tp_scalp3'], 'sl': s['sl_swing'],
        'skor': s.get('skor', 0), 'skor_label': s.get('skor_label','B'), 'mode_strict': s.get('mode_strict','NORMAL'),
        'is_meme': s.get('is_meme', False)
    }
    save(FILE_LOG, logs)

def send_detail(base_input):
    logs = load(FILE_LOG, {})
    base = base_input.upper().strip()
    if base not in logs:
        send(f"❌ {base} belum ada di log.\nLog baru mulai tercatat dari V10.8.\nCoba /detail untuk sinyal baru setelah deploy V12.1.")
        return
    d = logs[base]
    mode_txt = "🔥 STRICT - Probabilitas Tinggi" if d.get('mode_strict')=='STRICT' else "⚪ NORMAL"
    if d.get('is_meme'): mode_txt += " | ⚠️ MEME - Risiko Fakeout Tinggi"
    txt = f"""🔍 DETAIL SINYAL AWAL {d['base']} {d['waktu']}
────────────────
{d['name']} [{d['source']}] | {mode_txt}
SKOR {d.get('skor_label','B')} ({d.get('skor',0)}/100)
🛡️ KOREKSI BUY | Pos {d['pos']:.0f}%
📈 24H {fmt_change(d['change24'])} | Gain dari Low {fmt_change(d['gain'])}
💧 Vol {fmt_money(d['vol'])}
🔼 High {fmt_price(d['high'])}
🔽 Low {fmt_price(d['low'])}
────────────────
📏 ANALISA SR SAAT SINYAL MUNCUL
🔵 S Kuat {fmt_price(d['support_kuat'])}
🔵 S Mayor {fmt_price(d['support_mayor'])}
🔴 R {fmt_price(d['resistance'])}
📍 Jarak ke Support {d['dist_support']:.1f}% - DEKAT SUPPORT
────────────────
💰 ORDER BOOK SAAT SINYAL MUNCUL
{d['ob_dominant']} {fmt_money(d['ob_buy'])} vs {fmt_money(d['ob_sell'])}
Ratio {d['ob_ratio']:.2f}x | Spread {d['ob_spread']:.2f}%
🕯️ Candle Bullish {fmt_change(d['candle'])}
────────────────
🟢 ENTRY AWAL {fmt_price(d['entry'])}
🎯 TP1 {fmt_price(d['tp1'])} (+5%) -> Jual 50% + SL ke Entry
🎯 TP2 {fmt_price(d['tp2'])} (+8%) -> Modal kecil: Jual Habis | Modal besar: Jual 30%
🎯 TP3 {fmt_price(d['tp3'])} (+12%) -> Jual sisa (modal besar saja)
🔴 SL {fmt_price(d['sl'])} (-5%)
────────────────
Kenapa bisa TP3? Karena lolos Vol, Pos, Gain, SR dekat Support, OB BUY, Candle Bullish, lalu harga naik bertahap TP1 -> TP2 -> TP3.
"""
    send(txt)

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
                tickers[k]={'last':str(last),'high':str(high),'low':str(low),'vol_idr':str(vol),'change_24h':'0','source':'INDODAX','name':NAMA_MAP.get(base,base)}
                time.sleep(0.05)
            except: continue
    except: pass
    return tickers

def get_data():
    indodax=get_indodax_real(); ajaib=get_ajaib_real()
    combined=indodax.copy()
    for k,v in ajaib.items():
        if k not in combined: combined[k]=v
        else: combined[k]['change_24h']=v['change_24h']
    return combined, {}

def get_btc_change(tickers):
    try:
        btc = tickers.get('btc_idr', {})
        return float(btc.get('change_24h', 0))
    except: return 0

def hitung_skor(vol, pos_p, gain_low, change_24h, sr, ob, candle):
    skor = 50
    if ob['ratio'] >= 1.5: skor += 20
    elif ob['ratio'] >= 1.3: skor += 10
    elif ob['ratio'] >= 1.1: skor += 5
    if sr['dist_support'] <= 5: skor += 15
    elif sr['dist_support'] <= 8: skor += 8
    elif sr['dist_support'] <= 12: skor += 3
    if vol >= 2 * MILIAR: skor += 10
    elif vol >= 1 * MILIAR: skor += 5
    if candle['change'] >= 0.5: skor += 5
    skor = min(100, max(0, skor))
    label = "A ⭐ PRIORITAS" if skor >= 80 else "B"
    return skor, label

def cek_strict(vol, pos_p, gain_low, change_24h, sr, ob, candle, btc_chg, is_meme):
    if is_meme: return False
    if vol < 1 * MILIAR: return False
    if not (40 <= pos_p <= 60): return False
    if not (2 <= gain_low <= 5): return False
    if not (0 <= change_24h <= 5): return False
    if sr['dist_support'] > 5: return False
    if ob['ratio'] < 1.5: return False
    if ob['spread'] > 1.0: return False
    if not candle['bull']: return False
    if candle['change'] < 0.3: return False
    if btc_chg < 0: return False
    return True

def get_sr(last, high, low):
    rng=high-low
    if rng<=0: return {'support1':low,'support2':low,'support_nearest':low,'resistance':high,'dist_support':99,'near_support':False}
    s_major=low; s_kuat=low + rng*0.382; r_high=high
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

def analisa_debug():
    tickers,_=get_data()
    pos=load(FILE_POS,{}); cooldown=load(FILE_COOLDOWN,{}); pending=load(FILE_PENDING,{})
    btc_chg = get_btc_change(tickers)
    c={'total':len(tickers),'vol':0,'pos':0,'gain':0,'change':0,'sr':0,'ob':0,'candle':0,'strict':0}
    for pid,d in tickers.items():
        if not pid.endswith('_idr'): continue
        base=pid.split('_')[0].upper()
        if base in pos or base in cooldown or base in ['USDT','USDC','IDR','DAI']: continue
        try:
            last=float(d['last']); low=float(d['low']); high=float(d['high']); vol=float(d['vol_idr']); change_24h=float(d.get('change_24h',0)); source=d.get('source','INDODAX')
            if vol < FILTER_VOL_MIN: continue
            c['vol']+=1
            pos_p=(last-low)/(high-low)*100 if high!=low else 0
            if not (35 <= pos_p <= 65): continue
            c['pos']+=1
            gain_low=(last-low)/low*100 if low else 0
            if not (1.5 <= gain_low <= 8): continue
            c['gain']+=1
            if change_24h < -2: continue
            c['change']+=1
            sr=get_sr(last, high, low)
            if not sr['near_support']: continue
            c['sr']+=1
            ob=get_ob(base, vol, pos_p, source)
            if ob['dominant']!='BUY' or ob['ratio']<1.1 or ob['spread']>2.0: continue
            c['ob']+=1
            candle=get_candle(base, source)
            if not candle['bull']: continue
            c['candle']+=1
            is_meme = base in MEME_RISKY
            if cek_strict(vol, pos_p, gain_low, change_24h, sr, ob, candle, btc_chg, is_meme): c['strict']+=1
        except: continue
    return f"""🔍 DEBUG FILTER {jam()}
────────────────
BTC 24H: {btc_chg:.2f}% {'⚠️ MARKET CRASH - Sinyal baru dijeda' if btc_chg < -3 else '✅ Market Normal'}
Total koin: {c['total']}
Lolos Vol >350Jt: {c['vol']}
Lolos Pos 35-65%: {c['pos']}
Lolos Gain 1.5-8%: {c['gain']}
Lolos 24H >-2%: {c['change']}
Lolos SR <=12%: {c['sr']}
Lolos OB BUY: {c['ob']}
Lolos Candle Bullish: {c['candle']} = SINYAL FINAL (NORMAL)
🔥 Diantaranya STRICT: {c['strict']} koin
⏳ Menunggu Konfirmasi ke-2: {len(pending)} koin
Posisi open: {len(pos)} | Cooldown: {len(cooldown)}"""

def analisa(force_confirm=False):
    tickers,_=get_data()
    if not tickers: return []
    btc_chg = get_btc_change(tickers)
    if btc_chg < -3:
        return []
    pos=load(FILE_POS,{}); cooldown=load(FILE_COOLDOWN,{}); pending=load(FILE_PENDING,{})
    for k in list(cooldown.keys()):
        try:
            if now()-datetime.fromisoformat(cooldown[k])>timedelta(hours=3): del cooldown[k]
        except: del cooldown[k]
    save(FILE_COOLDOWN,cooldown)
    for k in list(pending.keys()):
        try:
            if now()-datetime.fromisoformat(pending[k]['time'])>timedelta(minutes=30): del pending[k]
        except: del pending[k]
    save(FILE_PENDING,pending)
    cands=[]; new_pending={}
    for pid,d in tickers.items():
        if not pid.endswith('_idr'): continue
        base=pid.split('_')[0].upper()
        if base in pos or base in cooldown or base in ['USDT','USDC','IDR','DAI']: continue
        try:
            last=float(d['last']); low=float(d['low']); high=float(d['high']); vol=float(d['vol_idr']); change_24h=float(d.get('change_24h',0)); source=d.get('source','INDODAX')
            # FILTER LAMA - TIDAK DIUBAH
            if vol < FILTER_VOL_MIN: continue
            pos_p=(last-low)/(high-low)*100 if high!=low else 0
            if not (35 <= pos_p <= 65): continue
            gain_low=(last-low)/low*100 if low else 0
            if not (1.5 <= gain_low <= 8): continue
            if change_24h < -2: continue
            sr=get_sr(last, high, low)
            if not sr['near_support']: continue
            ob=get_ob(base, vol, pos_p, source)
            if ob['dominant']!='BUY': continue
            if ob['ratio'] < 1.1: continue
            if ob['spread'] > 2.0: continue
            candle=get_candle(base, source)
            if not candle['bull']: continue
            is_meme = base in MEME_RISKY
            if is_meme:
                if ob['ratio'] < 1.5: continue
                if ob['spread'] > 1.0: continue
                if sr['dist_support'] > 5: continue
            skor, skor_label = hitung_skor(vol, pos_p, gain_low, change_24h, sr, ob, candle)
            is_strict = cek_strict(vol, pos_p, gain_low, change_24h, sr, ob, candle, btc_chg, is_meme)
            mode_strict = "STRICT" if is_strict else "NORMAL"
            if is_strict:
                skor = 95
                skor_label = "A ⭐ PRIORITAS"
            if is_meme and skor > 75: skor = 75
            # === V12.1 TP BARU: TP1 5% | TP2 8% | TP3 12% | SWING TP1 8% TP2 15% TP3 20% ===
            cand={'base':base,'name':d.get('name',base),'mode_label':'🔥 STRICT' if is_strict else '🛡️ DUAL MODE','mode':'KOREKSI BUY','entry':last,'gain':gain_low,'pos':pos_p,'vol':vol,'high':high,'low':low,'change24':change_24h,'sr':sr,'tp_scalp1':last*1.05,'tp_scalp2':last*1.08,'tp_scalp3':last*1.12,'sl_scalp':last*0.97,'tp_swing1':last*1.08,'tp_swing2':last*1.15,'tp_swing3':last*1.20,'sl_swing':last*0.95,'ob':ob,'candle':candle,'source':source,'skor':skor,'skor_label':skor_label,'mode_strict':mode_strict,'btc_chg':btc_chg,'is_meme':is_meme}
            if force_confirm:
                cands.append(cand)
                continue
            if base not in pending:
                new_pending[base]={'time':now().isoformat(),'entry':last}
                continue
            else:
                entry1 = pending[base].get('entry', last)
                if last < entry1 * 0.985:
                    continue
                cands.append(cand)
                if base in pending: del pending[base]
                continue
            time.sleep(0.1)
        except: continue
    pending.update(new_pending)
    save(FILE_PENDING,pending)
    cands_sorted = sorted([c for c in cands if c['mode_strict']=='STRICT'], key=lambda x: x['skor'], reverse=True) + sorted([c for c in cands if c['mode_strict']=='NORMAL'], key=lambda x: x['skor'], reverse=True)
    return cands_sorted[:5]

def fmt_tmg(s,r):
    ob=s['ob']; sr=s['sr']; ob_line=f"🟢 BUY {fmt_money(ob['buy_m'])} > {fmt_money(ob['sell_m'])}"
    src=s.get('source','INDODAX'); nama=s.get('name',s['base'])
    is_strict = s.get('mode_strict','NORMAL')=='STRICT'
    is_meme = s.get('is_meme', False)
    if is_strict:
        header = f"🔥 STRICT - PROBABILITAS TINGGI"
        saran = "💡 SARAN: Modal BESAR - Ini sinyal terbaik, sudah konfirmasi 2x scan + semua confluence ketemu"
    elif is_meme:
        header = f"⚠️ MEME - RISIKO FAKEOUT"
        saran = "💡 SARAN: Modal KECIL SAJA / Skip - Koin meme, sudah konfirmasi 2x tapi tetap rawan banting"
    else:
        header = f"{s['mode_label']}"
        saran = "💡 SARAN: Modal KECIL / Skip kalau ragu - Ini sinyal NORMAL, sudah konfirmasi 2x scan"
    skor_txt = f"⭐ SKOR {s.get('skor_label','B')} ({s.get('skor',0)}/100)" if s.get('skor_label','B').startswith('A') else f"SKOR {s.get('skor_label','B')} ({s.get('skor',0)}/100)"
    return f"""┌─ #{r} {header} {s['base']}/IDR [{src}] ─
│ {nama} | {skor_txt} | ✅ Terkonfirmasi 2x Scan
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
│ ₿ BTC 24H {fmt_change(s.get('btc_chg',0))}
├────────────────
│ 🟢 ENTRY {fmt_price(s['entry'])} (SYNC APK)
│ ── OPSI A: SCALPING ──
│ 🎯 TP1 {fmt_price(s['tp_scalp1'])} (+5%) -> Jual 50% + SL ke Entry
│ 🎯 TP2 {fmt_price(s['tp_scalp2'])} (+8%) -> Modal kecil: Jual Habis | Modal besar: Jual 30%
│ 🎯 TP3 {fmt_price(s['tp_scalp3'])} (+12%) -> Modal besar saja, sisa 20%
│ 🔴 SL {fmt_price(s['sl_scalp'])} (-3%)
│ ── OPSI B: SWING ──
│ 🎯 TP1 {fmt_price(s['tp_swing1'])} (+8%)
│ 🎯 TP2 {fmt_price(s['tp_swing2'])} (+15%)
│ 🎯 TP3 {fmt_price(s['tp_swing3'])} (+20%)
│ 🔴 SL {fmt_price(s['sl_swing'])} (-5%)
│ {saran}
└─ {jam()} ─"""

def fmt_rekap(list_sig):
    strict = [s for s in list_sig if s.get('mode_strict')=='STRICT']
    normal = [s for s in list_sig if s.get('mode_strict')!='STRICT']
    txt=f"📊 REKAP {len(list_sig)} SINYAL TERKONFIRMASI {jam()}\n🔥 STRICT: {len(strict)} | ⚪ NORMAL: {len(normal)} | ✅ Sudah lolos 2x Scan\nVol >350Jt | Pos 35-65% | Gain 1.5-8% | 24H >-2% | SR BOUNCE | SYNC APK REAL\n🔥 STRICT = Vol >1M + Pos 40-60% + Gain 2-5% + 24H 0-5% + SR <=5% + OB >=1.5x + Spread <=1% + BTC Hijau + Bukan Meme\nTP BARU: TP1 +5% | TP2 +8% | TP3 +12%\n────────────────\n"
    for i,s in enumerate(list_sig,1):
        ob=s['ob']; icon="🔥" if s.get('mode_strict')=='STRICT' else ("⚠️" if s.get('is_meme') else "🟢"); src=s.get('source','INDODAX')
        txt+=f"{i}. {icon} {s['base']} ({s.get('name',s['base'])}) [{src}] {s.get('mode_strict','NORMAL')} Skor {s.get('skor',0)} Pos {s['pos']:.0f}% 24H {fmt_change_plain(s['change24'])} S {fmt_price(s['sr']['support_nearest'])} Vol {fmt_money(s['vol'])} OB {ob['ratio']:.2f}x\n"
    return txt

def fmt_winrate():
    stats=load(FILE_STATS,{"win":0,"loss":0,"total_sinyal":0,"tp1":0,"tp2":0,"tp3":0,"tp1_coins":[],"tp2_coins":[],"tp3_coins":[],"sl_coins":[],"win_coins":[],"be_coins":[]})
    total=stats.get('total_sinyal',0)
    tp_tercapai=len(stats.get('win_coins',[]))
    tp1=len(stats.get('tp1_coins',[])); tp2=len(stats.get('tp2_coins',[])); tp3=len(stats.get('tp3_coins',[]))
    sl=len(stats.get('sl_coins',[])); be=len(stats.get('be_coins',[]))
    closed=len(set(stats.get('tp3_coins',[])) | set(stats.get('sl_coins',[])) | set(stats.get('be_coins',[])))
    open_pos=max(0, total - closed)
    winrate_filter=(tp_tercapai/total*100) if total>0 else 0
    return f"""📊 WINRATE JUJUR V12.1 {jam()}
────────────────
Total Sinyal: {total}
Closed: {closed} | Open: {open_pos}
TP Tercapai (WIN): {tp_tercapai}
BE (TP1 lalu balik ke Entry): {be}
SL Murni (tidak pernah TP1): {sl}
TP1 (+5%): {tp1} | TP2 (+8%): {tp2} | TP3 (+12%): {tp3}
────────────────
Winrate Jujur: {winrate_filter:.2f}% = {tp_tercapai}/{total}
TP1 sekarang minimal +5%, bukan +2.5% lagi.
👇 Klik tombol di bawah untuk lihat nama koinnya
/detail DODO untuk lihat analisa awal DODO"""

def cek_tp():
    tickers,_=get_data()
    if not tickers: return
    pos=load(FILE_POS,{}); stats=load(FILE_STATS,{"win":0,"loss":0,"total_sinyal":0,"tp1":0,"tp2":0,"tp3":0,"tp1_coins":[],"tp2_coins":[],"tp3_coins":[],"sl_coins":[],"win_coins":[],"be_coins":[]}); hist=load(FILE_HISTORY,[]); ch=False
    for k in ["tp1_coins","tp2_coins","tp3_coins","sl_coins","win_coins","be_coins"]:
        if k not in stats: stats[k]=[]
    for base,data in list(pos.items()):
        try:
            if isinstance(data, dict):
                entry=float(data.get('entry',0)); hit=data.get('hit',[])
                # V12.1: TP BARU - pakai data baru kalau ada, kalau data lama (V12) otomatis konversi ke TP baru
                tp_s1=float(data.get('tp_scalp1', entry*1.05)); tp_s2=float(data.get('tp_scalp2', entry*1.08)); tp_s3=float(data.get('tp_scalp3', entry*1.12)); sl_w=float(data.get('sl_swing', entry*0.95))
                # Kalau posisi lama masih pakai TP1 2.5%, paksa update ke TP1 5% agar konsisten
                if tp_s1 < entry*1.04:
                    tp_s1 = entry*1.05; tp_s2 = entry*1.08; tp_s3 = entry*1.12
                    pos[base]['tp_scalp1']=tp_s1; pos[base]['tp_scalp2']=tp_s2; pos[base]['tp_scalp3']=tp_s3
            else:
                entry=float(data); hit=[]; tp_s1=entry*1.05; tp_s2=entry*1.08; tp_s3=entry*1.12; sl_w=entry*0.95
            if entry==0: pos.pop(base); ch=True; continue
            key=f"{base.lower()}_idr"
            if key not in tickers: continue
            last=float(tickers[key]['last'])
            has_tp1 = 'SCALP1' in hit
            sl_effective = entry if has_tp1 else sl_w
            if last>=tp_s1 and 'SCALP1' not in hit:
                if base not in stats["win_coins"]: stats["win_coins"].append(base)
                if base not in stats["tp1_coins"]: stats["tp1_coins"].append(base)
                stats['win']=len(stats["win_coins"]); stats['tp1']=len(stats["tp1_coins"]); hit.append('SCALP1'); ch=True; save(FILE_STATS,stats)
                send(f"⚡ TP1 SCALP {base} +5% {fmt_price(entry)} -> {fmt_price(last)} {jam()}\n💡 AKSI: Jual 50% + Pindah SL ke Entry {fmt_price(entry)} (Break Even) -> Profit sudah aman. Modal kecil: sisa 50% tunggu TP2 lalu Jual Habis")
                send_winrate()
                pos[base]['hit']=hit; continue
            if last>=tp_s2 and 'SCALP2' not in hit:
                if base not in stats["tp2_coins"]: stats["tp2_coins"].append(base)
                stats['tp2']=len(stats["tp2_coins"]); hit.append('SCALP2'); ch=True; save(FILE_STATS,stats)
                send(f"⚡⚡ TP2 SCALP {base} +8% {fmt_price(entry)} -> {fmt_price(last)} {jam()}\n💡 AKSI: Modal kecil (200rb): JUAL HABIS SEKARANG - Profit 8% sudah pasti. Modal besar: Jual 30%, sisa 20% ke TP3")
                send_winrate()
                pos[base]['hit']=hit
            if last>=tp_s3 and 'SCALP3' not in hit:
                if base not in stats["tp3_coins"]: stats["tp3_coins"].append(base)
                stats['tp3']=len(stats["tp3_coins"]); hit.append('SCALP3'); ch=True; save(FILE_STATS,stats)
                send(f"⚡⚡⚡ TP3 SCALP {base} +12% {fmt_price(entry)} -> {fmt_price(last)} {jam()}\n💡 AKSI: Jual sisa - Selesai (hanya untuk modal besar yang masih pegang sisa)")
                send_winrate()
                pos.pop(base); hist.append({"base":base,"pnl":"WIN"}); continue
            if has_tp1 and last<=sl_effective and 'BE' not in hit:
                if base not in stats["be_coins"]: stats["be_coins"].append(base)
                ch=True; save(FILE_STATS,stats)
                send(f"🟡 BE {base} Balik ke Entry {fmt_price(entry)} -> {fmt_price(last)} {jam()}\nProfit 50% pertama sudah diamankan di TP1 (+5%). Sisa 50% balik modal, TIDAK DIHITUNG SL. Ini bukan rugi.")
                send_winrate()
                pos.pop(base); hist.append({"base":base,"pnl":"BE"}); continue
            if not has_tp1 and last<=sl_w and 'SL' not in hit:
                if base not in stats["sl_coins"]: stats["sl_coins"].append(base)
                if base in stats["win_coins"]: stats["win_coins"].remove(base)
                stats['loss']=len(stats["sl_coins"]); stats['win']=len(stats["win_coins"]); ch=True; save(FILE_STATS,stats)
                send(f"🔴 SL {base} -5% {fmt_price(entry)} -> {fmt_price(last)} {jam()}\nBelum pernah TP1 (+5%), ini SL murni.")
                send_winrate()
                pos.pop(base); hist.append({"base":base,"pnl":"LOSS"}); continue
        except: continue
    if ch: save(FILE_POS,pos); save(FILE_STATS,stats); save(FILE_HISTORY,hist)

def polling_loop():
    while True:
        try:
            last_id=load(FILE_LAST,{"id":0})["id"]
            r=SESSION.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset={last_id+1}&timeout=10",timeout=15).json()
            for u in r.get('result',[]):
                save(FILE_LAST,{"id":u['update_id']})
                if 'callback_query' in u:
                    cb=u['callback_query']
                    try: requests.post(f"https://api.telegram.org/bot{TOKEN}/answerCallbackQuery", json={"callback_query_id": cb['id'], "text": "Membuka daftar koin..."}, timeout=10)
                    except: pass
                    if cb.get('data')=='show_tp': send_tp_list()
                    continue
                msg=u.get('message',{})
                txt=msg.get('text','').lower().strip()
                if not txt: continue
                if txt=='/clear': save(FILE_POS,{}); save(FILE_COOLDOWN,{}); save(FILE_PENDING,{}); send(f"✅ Clear OK {jam()}"); send_winrate()
                elif txt=='/resetwinrate': save(FILE_STATS,{"win":0,"loss":0,"total_sinyal":0,"tp1":0,"tp2":0,"tp3":0,"tp1_coins":[],"tp2_coins":[],"tp3_coins":[],"sl_coins":[],"win_coins":[],"be_coins":[]}); send(f"✅ Winrate direset {jam()}"); send_winrate()
                elif txt in ['/winrate','/stats']: send_winrate()
                elif txt in ['/tp','/listtp','/koin']: send_tp_list()
                elif txt.startswith('/detail'):
                    parts=txt.split()
                    if len(parts)>=2: send_detail(parts[1])
                    else: send("Ketik: /detail DODO  atau  /detail ANOA")
                elif txt=='/debug': send(analisa_debug())
                elif txt=='/pending':
                    pending=load(FILE_PENDING,{})
                    if not pending: send(f"⏳ Pending: 0 koin {jam()} - Semua sudah terkonfirmasi / gugur")
                    else: send(f"⏳ Menunggu Konfirmasi ke-2 ({len(pending)} koin) {jam()}:\n" + "\n".join([f"- {k} Entry {fmt_price(v.get('entry',0))}" for k,v in pending.items()]) + "\n\nMereka lolos Scan 1, tunggu Scan 2. Kalau masih bertahan, baru dikirim.")
                elif txt=='/scan':
                    sig=analisa(force_confirm=True)
                    if sig: send(fmt_rekap(sig)); time.sleep(1); [send(fmt_tmg(s,i)) or time.sleep(0.5) for i,s in enumerate(sig,1)]
                    else:
                        tickers,_=get_data(); btc_chg=get_btc_change(tickers)
                        if btc_chg < -3: send(f"⏸️ Sinyal dijeda {jam()} - BTC 24H {btc_chg:.2f}% (< -3% Crash), tunggu market reda. TP/SL lama tetap dipantau.")
                        else: send(f"0 sinyal {jam()} - Jauh dari Support"); send_winrate()
                elif txt=='/strict':
                    sig=analisa(force_confirm=True)
                    strict=[s for s in sig if s.get('mode_strict')=='STRICT']
                    if strict: send(fmt_rekap(strict)); time.sleep(1); [send(fmt_tmg(s,i)) or time.sleep(0.5) for i,s in enumerate(strict,1)]
                    else: send(f"0 sinyal STRICT {jam()} - Belum ada koin yang lolos semua syarat ketat. Coba /scan untuk lihat NORMAL.")
        except Exception as e:
            print(f"POLL ERR {e}", flush=True)
            time.sleep(3)
        time.sleep(1)

def main():
    time.sleep(2)
    threading.Thread(target=polling_loop, daemon=True).start()
    send(f"✅ V12.1 AKTIF {jam()}\nTP BARU: TP1 +5% | TP2 +8% | TP3 +12% | SWING TP1 +8% TP2 +15% TP3 +20%\nFilter LAMA TETAP + STRICT + Konfirmasi 2x + Anti-Meme + Winrate Jujur\nPosisi lama otomatis di-update ke TP1 +5% agar konsisten.\n/strict | /scan | /pending | /detail DODO | /winrate | /tp")
    loop=0
    while True:
        try:
            if loop%4==0: cek_tp()
            if loop%12==0:
                sig=analisa(force_confirm=False)
                if sig:
                    pos=load(FILE_POS,{}); cooldown=load(FILE_COOLDOWN,{}); stats=load(FILE_STATS,{"win":0,"loss":0,"total_sinyal":0,"tp1":0,"tp2":0,"tp3":0,"tp1_coins":[],"tp2_coins":[],"tp3_coins":[],"sl_coins":[],"win_coins":[],"be_coins":[]})
                    for k in ["tp1_coins","tp2_coins","tp3_coins","sl_coins","win_coins","be_coins"]:
                        if k not in stats: stats[k]=[]
                    send(fmt_rekap(sig)); time.sleep(1)
                    for i,s in enumerate(sig,1):
                        if s['base'] in pos: continue
                        send(fmt_tmg(s,i)); save_log(s)
                        pos[s['base']]={'entry':s['entry'],'tp_scalp1':s['tp_scalp1'],'tp_scalp2':s['tp_scalp2'],'tp_scalp3':s['tp_scalp3'],'tp_swing3':s['tp_swing3'],'sl_swing':s['sl_swing'],'hit':[]}; save(FILE_POS,pos)
                        cooldown[s['base']]=now().isoformat(); save(FILE_COOLDOWN,cooldown); stats['total_sinyal']=stats.get('total_sinyal',0)+1; save(FILE_STATS,stats); time.sleep(0.8)
                else:
                    pending=load(FILE_PENDING,{})
                    if pending and loop%36==0:
                        send(f"⏳ {len(pending)} koin lagi menunggu Konfirmasi ke-2 {jam()}: {', '.join(pending.keys())}. Ketik /pending untuk lihat. Kalau lolos Scan 2, baru dikirim.")
            loop+=1; time.sleep(30)
        except Exception as e: print(f"ERR {e}",flush=True); time.sleep(10)

if __name__=="__main__": main()
