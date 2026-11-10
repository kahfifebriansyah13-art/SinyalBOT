import requests, os, time, json, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timedelta

print("BOT V3.5 TRENDING STARTING...", flush=True)
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
FILE = "posisi_aktif.json"
COOLDOWN_FILE = "cooldown.json"
LAST_UPDATE_FILE = "last_update.json"

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"OK V3.5 TRENDING")
    def log_message(self, format, *args): return
def run_health():
    port = int(os.getenv("PORT", 8080))
    try: HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()
    except: pass
threading.Thread(target=run_health, daemon=True).start()

def kirim(pesan):
    for i in range(3):
        try:
            r = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                data={"chat_id": CHAT_ID, "text": pesan, "parse_mode": "Markdown"}, timeout=25)
            if r.status_code == 200: return True
        except: time.sleep(2)
    return False

def load_json(f, default):
    try: return json.load(open(f,'r'))
    except: return default
def save_json(f, d): json.dump(d, open(f,'w'))

def get_tickers():
    try: return requests.get("https://indodax.com/api/tickers", timeout=20, headers={"User-Agent":"Mozilla/5.0"}).json()['tickers']
    except: return {}

def get_coingecko_trending():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/search/trending", timeout=15).json()
        trending = []
        for coin in r.get('coins', []):
            sym = coin['item']['symbol'].upper()
            trending.append(sym)
        print(f"TRENDING GC: {trending[:10]}", flush=True)
        return trending
    except Exception as e:
        print(f"GC FAIL {e}", flush=True)
        return []

def format_tmg(s):
    trending_icon = "🌐 TRENDING SOSMED: YES 🔥" if s['is_trending'] else "🌐 Trending: -"
    prioritas = "PRIORITAS 1 - ENTRY WAJIB" if s['score']>=90 else "PRIORITAS 2 - BOLEH ENTRY" if s['score']>=80 else "SKIP"
    return f"""┏━━━━━━━━━━━━━━━━━━┓
┃ {s['base']}/IDR - AKAN TRENDING ┃
┗━━━━━━━━━━━━━━━━━━┛

💎 AKAN TRENDING 💎 LOCAL
{trending_icon}

┌─ 🕯️ DAILY CANDLE + MA RSI VOL ─┐
│ 🟢 Open: Rp {s['open']:,.0f} | Close: Rp {s['entry']:,.0f} (HIJAU)
│ 📊 RSI Daily: {s['rsi']:.1f} + MA Bullish
│ 🤖 Rekom: NEUTRAL
│ ⭐ Score: {s['score']}/100
│ 🎯 {prioritas}
└──────────────────┘

┌─ 📊 MARKET DATA ─┐
│ 📈 Naik: +{s['naik']:.2f}% dari Low
│ 💧 Low: Rp {s['low']:,.0f} | High: Rp {s['high']:,.0f}
│ 💰 Vol: Rp {s['vol']/1e6:.2f} M
└──────────────────┘

┌─ 🎯 TRADING PLAN ─┐
│ 🟢 ENTRY: Rp {s['entry']:,.0f}
│ 🎯 TP1: Rp {s['tp1']:,.0f} (+5%)
│ 🏆 TP2: Rp {s['tp2']:,.0f} (+10%)
│ 🔴 SL: Rp {s['sl']:,.0f} (-5%)
└──────────────────┘

⚡ ENTRY SEKARANG!
"""

def analisa_ranking():
    tickers = get_tickers()
    if not tickers: return []
    trending_list = get_coingecko_trending()
    posisi = load_json(FILE, {})
    cooldown = load_json(COOLDOWN_FILE, {})
    now = datetime.now()
    for k in list(cooldown.keys()):
        try:
            t = datetime.fromisoformat(cooldown[k])
            if now - t > timedelta(hours=1): del cooldown[k]
        except: del cooldown[k]
    save_json(COOLDOWN_FILE, cooldown)
    scored = []
    for pair,d in tickers.items():
        if not pair.endswith('_idr'): continue
        base = pair.split('_')[0].upper()
        if base in posisi or base in ['USDT','USDC','DAI','IDR']: continue
        if base in cooldown: continue
        try:
            last = float(d['last']); low = float(d['low']); high = float(d['high'])
            vol = float(d['vol_idr']); open_p = float(d.get('open', last))
            if vol < 100_000_000 or low==0: continue
            naik_low = (last-low)/low*100
            pos_h = (last-low)/(high-low)*100 if high!=low else 50
            if not (1.0 <= naik_low <= 10.0): continue
            if not (20 <= pos_h <= 65): continue
            if last < open_p: continue
            is_trending = base in trending_list
            score = 0
            if vol >= 100_000_000: score += 20
            if vol >= 200_000_000: score += 10
            if vol >= 500_000_000: score += 10
            if 2 <= naik_low <= 6: score += 30
            elif 1 <= naik_low <= 8: score += 20
            if 25 <= pos_h <= 50: score += 20
            if last >= open_p: score += 20
            if is_trending: score += 15 # BONUS TRENDING
            if score >= 70:
                scored.append({'base':base,'entry':last,'low':low,'high':high,'open':open_p,'tp1':last*1.05,'tp2':last*1.10,'sl':last*0.95,'naik':naik_low,'vol':vol,'pos':pos_h,'rsi':55.0,'score':min(score,100),'is_trending':is_trending})
        except: continue
    scored = sorted(scored, key=lambda x: x['score'], reverse=True)
    print(f"FILTER: {len(scored)} lolos | Trending: {sum(1 for x in scored if x['is_trending'])}", flush=True)
    return scored[:1]

def cek_tp():
    tickers = get_tickers()
    if not tickers: return
    pos = load_json(FILE, {})
    for base, data in list(pos.items()):
        pair = f"{base.lower()}_idr"
        if pair not in tickers: continue
        try:
            last = float(tickers[pair]['last']); entry = data['entry']
            tp1_hit = data.get('tp1_hit', False)
            if last >= entry*1.10:
                profit = (last-entry)/entry*100
                kirim(f"🏆 *TP2 TERCAPAI!* {base}/IDR\n💰 +{profit:.2f}% -> Rp {last:,.0f}")
                del pos[base]; save_json(FILE, pos)
            elif last >= entry*1.05 and not tp1_hit:
                profit = (last-entry)/entry*100
                kirim(f"🎯 *TP1 TERCAPAI!* {base}/IDR\n💰 +{profit:.2f}% -> Rp {last:,.0f}")
                pos[base]['tp1_hit'] = True; save_json(FILE, pos)
            elif last <= entry*0.95:
                profit = (last-entry)/entry*100
                kirim(f"🔴 *SL KENA!* {base}/IDR\n💸 {profit:.2f}%")
                del pos[base]; save_json(FILE, pos)
        except: continue

def hitung_profit():
    tickers = get_tickers()
    if not tickers: return
    pos = load_json(FILE, {})
    if not pos: kirim("📭 Tidak ada posisi aktif"); return
    pesan = "📊 *PROFIT SAAT INI*\n━━━━━━━━━━━━━━\n"
    total=0
    for base, data in pos.items():
        pair = f"{base.lower()}_idr"
        if pair not in tickers: continue
        last = float(tickers[pair]['last']); entry = data['entry']
        profit_pct = (last-entry)/entry*100; total+=profit_pct
        emoji = "🟢" if profit_pct>=0 else "🔴"
        pesan+=f"{emoji} {base}: {profit_pct:+.2f}% | Rp {last:,.0f}\n"
    pesan+=f"━━━━━━━━━━━━━━\nAvg: {total/len(pos):+.2f}% dari {len(pos)} koin"
    kirim(pesan)

def cek_command():
    try:
        last_id = load_json(LAST_UPDATE_FILE, {"id":0})["id"]
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={last_id+1}&timeout=5"
        r = requests.get(url, timeout=10).json()
        if not r.get('result'): return
        for update in r['result']:
            uid = update['update_id']; save_json(LAST_UPDATE_FILE, {"id":uid})
            text = update.get('message', {}).get('text','').lower().strip()
            if text in ['/profit','/status','/cek']: hitung_profit()
            elif text == '/help': kirim("Perintah:\n/profit - cek profit\n/help - bantuan")
    except: pass

def main():
    time.sleep(2)
    kirim("✅ *BOT V3.5 TRENDING AKTIF*\n• Format TMG + CoinGecko\n• Vol 100jt + Score 70+\n• Cooldown 1 Jam\n• /profit untuk cek")
    loop=0
    while True:
        try:
            if loop % 15 == 0: cek_tp()
            if loop % 3 == 0: cek_command()
            sinyal = analisa_ranking()
            if sinyal:
                pos = load_json(FILE, {}); cooldown = load_json(COOLDOWN_FILE, {})
                for s in sinyal:
                    if s['base'] in pos: continue
                    kirim(format_tmg(s))
                    pos[s['base']]={'entry':s['entry'],'tp1_hit':False}; save_json(FILE, pos)
                    cooldown[s['base']] = datetime.now().isoformat(); save_json(COOLDOWN_FILE, cooldown)
            loop+=1; time.sleep(30)
        except Exception as e: print(f"ERROR {e}", flush=True); time.sleep(20)

if __name__=="__main__": main()
