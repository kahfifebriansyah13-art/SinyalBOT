import requests, os, time, json, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timedelta

print("BOT V3.9 SCALPING TP5% STARTING...", flush=True)
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
FILE = "posisi_aktif.json"
COOLDOWN_FILE = "cooldown.json"
LAST_UPDATE_FILE = "last_update.json"

def now_wib(): return datetime.utcnow() + timedelta(hours=7)
def format_wib(): return now_wib().strftime("%H:%M WIB")

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK V3.9 TP5 SCALP")
    def log_message(self, format, *args): return
def run_health():
    port = int(os.getenv("PORT", 8080))
    try: HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()
    except: pass
threading.Thread(target=run_health, daemon=True).start()

def kirim(pesan):
    for i in range(3):
        try:
            r = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": pesan, "parse_mode": "Markdown"}, timeout=25)
            if r.status_code == 200: return True
        except: time.sleep(2)
    return False

def load_json(f, d):
    try: return json.load(open(f,'r'))
    except: return d
def save_json(f, d): json.dump(d, open(f,'w'))
def get_tickers():
    try: return requests.get("https://indodax.com/api/tickers", timeout=20, headers={"User-Agent":"Mozilla/5.0"}).json()['tickers']
    except: return {}
def get_coingecko_trending():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/search/trending", timeout=15).json()
        return [c['item']['symbol'].upper() for c in r.get('coins', [])]
    except: return []

def format_tmg(s, rank):
    if rank==1: prioritas="🔥 SCALP No.1 - PALING CEPAT TP1"
    elif rank<=3: prioritas=f"⭐ SCALP No.{rank} - CEPAT"
    else: prioritas=f"⚡ SCALP No.{rank}"
    trending = "🔥 TRENDING" if s['is_trending'] else ""
    return f"""┏━━━━━━━━━━━━━━━━━━┓
┃ #{rank} {s['base']}/IDR - {format_wib()} ┃
┗━━━━━━━━━━━━━━━━━━┛

{prioritas} ⭐{s['score']} {trending}

┌─ 📊 ANALISA SCALP ─┐
│ 🚀 Naik: +{s['naik']:.2f}% dari Low
│ 📍 Pos: {s['pos']:.0f}% (Masih bawah)
│ 💰 Vol: Rp {s['vol']/1e6:.0f} M
│ 🕯️ Open: Rp {s['open']:,.0f} -> Rp {s['entry']:,.0f}
└──────────────────┘

┌─ 🎯 TRADING PLAN - FEE AMAN ─┐
│ 🟢 ENTRY: Rp {s['entry']:,.0f}
│ 🎯 TP1: Rp {s['tp1']:,.0f} (+5% - fee aman)
│ 🏆 TP2: Rp {s['tp2']:,.0f} (+10%)
│ 🔴 SL: Rp {s['sl']:,.0f} (-5%)
└──────────────────┘

⏰ {format_wib()}
"""

def analisa_ranking():
    tickers = get_tickers()
    if not tickers: return []
    trending = get_coingecko_trending()
    posisi = load_json(FILE, {}); cooldown = load_json(COOLDOWN_FILE, {}); now = now_wib()
    for k in list(cooldown.keys()):
        try:
            if now - datetime.fromisoformat(cooldown[k]) > timedelta(hours=1): del cooldown[k]
        except: del cooldown[k]
    save_json(COOLDOWN_FILE, cooldown)
    scored=[]
    for pair,d in tickers.items():
        if not pair.endswith('_idr'): continue
        base=pair.split('_')[0].upper()
        if base in posisi or base in ['USDT','USDC','DAI','IDR']: continue
        if base in cooldown: continue
        try:
            last=float(d['last']); low=float(d['low']); high=float(d['high']); vol=float(d['vol_idr']); open_p=float(d.get('open',last))
            if vol < 100_000_000 or low==0: continue
            naik=(last-low)/low*100; pos_h=(last-low)/(high-low)*100 if high!=low else 50
            if not (1.5 <= naik <= 9.0): continue
            if not (15 <= pos_h <= 55): continue
            if last < open_p: continue
            is_trend = base in trending
            
            # SCORING SCALPING TP5% - PRIORITAS KECEPATAN
            score=50
            # 1. Kecepatan naik paling penting untuk scalping
            if 4.0 <= naik <= 7.0: score+=25 # sweet spot scalping cepat ke 5%
            elif 3.0 <= naik < 4.0: score+=18
            elif 7.0 < naik <= 9.0: score+=12
            else: score+=5
            
            # 2. Posisi masih bawah
            if 20 <= pos_h <= 35: score+=20 # masih sangat bawah, ruang naik banyak ke TP1
            elif 35 < pos_h <= 50: score+=10
            else: score+=3
            
            # 3. Volume ideal scalping (jangan terlalu besar biar cepat)
            if 100_000_000 <= vol <= 400_000_000: score+=15 # vol sedang = gerak cepat
            elif 400_000_000 < vol <= 800_000_000: score+=8
            else: score+=3
            
            if is_trend: score+=10
            
            if score>=75:
                scored.append({'base':base,'entry':last,'low':low,'high':high,'open':open_p,'tp1':last*1.05,'tp2':last*1.10,'sl':last*0.95,'naik':naik,'vol':vol,'pos':pos_h,'score':min(score,100),'is_trending':is_trend})
        except: continue
    # Sort by naik cepat dulu, baru score
    scored=sorted(scored, key=lambda x: (x['naik'], x['score']), reverse=True)
    print(f"SCALP TP5 FILTER {format_wib()}: {len(scored)} lolos", flush=True)
    return scored[:10]

def cek_tp():
    tickers=get_tickers()
    if not tickers: return
    pos=load_json(FILE,{})
    for base,data in list(pos.items()):
        pair=f"{base.lower()}_idr"
        if pair not in tickers: continue
        try:
            last=float(tickers[pair]['last']); entry=data['entry']; tp1=data.get('tp1_hit',False)
            if last >= entry*1.10:
                kirim(f"🏆 *TP2 +10% KENA!* {base}/IDR - {format_wib()}\n💰 +{((last-entry)/entry*100):.2f}% | Rp {entry:,.0f} -> Rp {last:,.0f}\n✅ AMANKAN!")
                del pos[base]; save_json(FILE,pos)
            elif last >= entry*1.05 and not tp1:
                kirim(f"🎯 *TP1 +5% KENA!* {base}/IDR - {format_wib()}\n💰 +{((last-entry)/entry*100):.2f}% | Rp {entry:,.0f} -> Rp {last:,.0f}\n✍️ Fee aman, geser SL ke entry!")
                pos[base]['tp1_hit']=True; save_json(FILE,pos)
            elif last <= entry*0.95:
                kirim(f"🔴 *SL -5% KENA!* {base}/IDR - {format_wib()}\n💸 {((last-entry)/entry*100):.2f}%")
                del pos[base]; save_json(FILE,pos)
        except: continue

def hitung_profit():
    tickers=get_tickers()
    pos=load_json(FILE,{})
    if not pos: kirim(f"📭 Tidak ada posisi - {format_wib()}"); return
    pesan=f"📊 *PROFIT SCALPING 5% - {format_wib()}*\n━━━━━━━━━━━━━━\n"
    total=0; win=0
    for base,data in pos.items():
        pair=f"{base.lower()}_idr"
        if pair not in tickers: continue
        last=float(tickers[pair]['last']); entry=data['entry']; pct=(last-entry)/entry*100; total+=pct
        if pct>0: win+=1
        emoji="🟢" if pct>=0 else "🔴"; tp="✅ TP1" if data.get('tp1_hit') else "⏳"
        pesan+=f"{emoji} {base}: {pct:+.2f}% {tp}\n   Rp {entry:,.0f} -> Rp {last:,.0f}\n"
    pesan+=f"━━━━━━━━━━━━━━\nWin: {win}/{len(pos)} | Avg: {total/len(pos):+.2f}%\nFee: 0.6% | TP1 +5% aman"
    kirim(pesan)

def cek_command():
    try:
        last_id=load_json(LAST_UPDATE_FILE,{"id":0})["id"]
        r=requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={last_id+1}&timeout=5", timeout=10).json()
        if not r.get('result'): return
        for u in r['result']:
            save_json(LAST_UPDATE_FILE,{"id":u['update_id']})
            txt=u.get('message',{}).get('text','').lower().strip()
            if txt in ['/profit','/status','/cek']: hitung_profit()
    except: pass

def main():
    time.sleep(2)
    kirim(f"✅ *BOT V3.9 SCALPING TP5% AKTIF - {format_wib()}*\n• 10 sinyal scalping\n• TP1 +5% (fee aman)\n• Ranking = paling cepat TP1\n• Jam WIB\n• /profit")
    print(f"MAIN LOOP SCALP TP5 {format_wib()}", flush=True)
    loop=0
    while True:
        try:
            if loop % 8 == 0: cek_tp()
            if loop % 3 == 0: cek_command()
            if loop % 18 == 0: # 9 menit
                sigs=analisa_ranking()
                if sigs:
                    jam=format_wib()
                    pesan=f"🏆 *RANKING SCALPING +5% - {jam}*\n━━━━━━━━━━━━━━\nPaling cepat ke TP1 +5%:\n\n"
                    for i,s in enumerate(sigs,1):
                        if i==1: pesan+=f"*{i}. {s['base']}/IDR - WAJIB SCALP DULU* 🚀+{s['naik']:.1f}% Pos {s['pos']:.0f}% ⭐{s['score']}\n   Vol {s['vol']/1e6:.0f}M\n\n"
                        else: pesan+=f"{i}. {s['base']} +{s['naik']:.1f}% Pos {s['pos']:.0f}% ⭐{s['score']} Vol {s['vol']/1e6:.0f}M\n"
                    pesan+=f"━━━━━━━━━━━━━━\n⏰ {jam} | TP1 +5% fee aman"
                    kirim(pesan); time.sleep(3)
                    pos=load_json(FILE,{}); cool=load_json(COOLDOWN_FILE,{})
                    for rank,s in enumerate(sigs,1):
                        if s['base'] in pos: continue
                        kirim(format_tmg(s,rank))
                        pos[s['base']]={'entry':s['entry'],'tp1_hit':False}
                        save_json(FILE,pos); cool[s['base']]=now_wib().isoformat(); save_json(COOLDOWN_FILE,cool)
                        time.sleep(2)
            loop+=1; time.sleep(30)
        except Exception as e: print(f"ERR {e}", flush=True); time.sleep(20)
if __name__=="__main__": main()
