import requests, os, time, json, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timedelta, timezone

print("BOT V5.0 FINAL STARTING...", flush=True)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
FILE = "posisi_aktif.json"
COOLDOWN_FILE = "cooldown.json"
LAST_UPDATE_FILE = "last_update.json"
DELISTED_FILE = "delisted.json"

DELISTED_HARD = {'SKYAI','BCHABC','BCHSV','BTG','ABT','ANON','BIFI','BTT','BCHA','LUNA','LUNC','UST'}

def now_wib(): return datetime.now(timezone.utc) + timedelta(hours=7)
def format_wib(): return now_wib().strftime("%H:%M WIB")

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers()
        self.wfile.write(b"OK V5.0")
    def log_message(self, format, *args): return

def run_health():
    try: HTTPServer(("0.0.0.0", int(os.getenv("PORT", 8080))), HealthHandler).serve_forever()
    except: pass
threading.Thread(target=run_health, daemon=True).start()

def kirim(pesan):
    for _ in range(3):
        try:
            r = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": pesan, "parse_mode": "Markdown"}, timeout=25)
            if r.status_code == 200: return True
        except: time.sleep(2)
    return False

def load_json(f, d):
    try:
        with open(f, 'r') as fp: return json.load(fp)
    except: return d

def save_json(f, d):
    with open(f, 'w') as fp: json.dump(fp, d)

def get_tickers():
    try: return requests.get("https://indodax.com/api/tickers", timeout=20, headers={"User-Agent":"Mozilla/5.0"}).json()['tickers']
    except: return {}

def get_active_pairs():
    try:
        r = requests.get("https://indodax.com/api/pairs", timeout=10, headers={"User-Agent":"Mozilla/5.0"}).json()
        if isinstance(r, dict):
            pairs = set(k.upper() for k in r.keys())
            print(f"PAIRS OK: {len(pairs)} pair", flush=True)
            return pairs
        return None
    except: return None

def get_orderbook_top10(base):
    try:
        resp = requests.get(f"https://indodax.com/api/{base.lower()}_idr/depth", timeout=10, headers={"User-Agent":"Mozilla/5.0"})
        if "html" in resp.headers.get("Content-Type","").lower(): return "DELISTED"
        data = resp.json()
        bids = data.get('buy', [])[:10]; asks = data.get('sell', [])[:10]
        if not bids or not asks: return "DELISTED"
        total_buy = sum(float(p)*float(v) for p,v in bids)
        total_sell = sum(float(p)*float(v) for p,v in asks)
        if total_sell == 0: return None
        ratio = total_buy/total_sell
        spread = (float(asks[0][0])-float(bids[0][0]))/float(bids[0][0])*100
        walls = sum(1 for p,v in bids if float(p)*float(v) > 5_000_000)
        print(f"OB TOP10 {base}: Buy {total_buy/1e6:.1f}M vs Sell {total_sell/1e6:.1f}M = {ratio:.2f}x Wall {walls}", flush=True)
        return {'ratio': ratio, 'buy_idr': total_buy, 'sell_idr': total_sell, 'spread': spread, 'big_walls': walls}
    except: return "DELISTED"

def get_trending():
    try: return [c['item']['symbol'].upper() for c in requests.get("https://api.coingecko.com/api/v3/search/trending", timeout=15).json().get('coins',[])]
    except: return []

def format_sinyal(s, rank):
    ob = s['orderbook']
    prior = "🔥 PRIORITAS 1" if rank==1 else f"⭐ PRIORITAS {rank}" if rank<=3 else f"⚠️ PRIORITAS {rank}"
    trend = "🌐 TRENDING YES 🔥" if s['is_trending'] else "🌐 Trending: -"
    return f"""#{rank} {s['base']}/IDR - SCORE {s['score']}
{trend}
📚 OB TOP10: {ob['ratio']:.2f}x Wall {ob['big_walls']} Spread {ob['spread']:.2f}%
Pos {s['pos']:.0f}% Naik +{s['naik']:.1f}% Vol {s['vol']/1e6:.0f}M
ENTRY Rp {s['entry']:,.0f} | TP1 Rp {s['tp1']:,.0f} (+5%) | SL Rp {s['sl']:,.0f}
{prior} - {format_wib()}"""

def analisa_ranking():
    tickers = get_tickers()
    if not tickers: return []
    now = now_wib()
    delisted_dyn = load_json(DELISTED_FILE, {})
    for k in list(delisted_dyn.keys()):
        try:
            if now - datetime.fromisoformat(delisted_dyn[k]) > timedelta(hours=24): del delisted_dyn[k]
        except: del delisted_dyn[k]
    save_json(DELISTED_FILE, delisted_dyn)
    active_pairs = get_active_pairs()
    posisi = load_json(FILE, {}); cooldown = load_json(COOLDOWN_FILE, {})
    for k in list(cooldown.keys()):
        try:
            if now - datetime.fromisoformat(cooldown[k]) > timedelta(hours=6): del cooldown[k]
        except: del cooldown[k]
    save_json(COOLDOWN_FILE, cooldown)
    trending_list = get_trending()
    cands = []
    for pair_id, d in tickers.items():
        if not pair_id.endswith('_idr'): continue
        base = pair_id.split('_')[0].upper()
        if base in DELISTED_HARD or base in delisted_dyn: continue
        if active_pairs and f"{base}_IDR" not in active_pairs: continue
        if base in posisi or base in cooldown or base in {'USDT','USDC','DAI','IDR'}: continue
        try:
            last=float(d['last']); low=float(d['low']); high=float(d['high']); vol=float(d['vol_idr']); open_p=float(d.get('open',last))
            if vol<100_000_000 or low==0: continue
            naik=(last-low)/low*100; pos=(last-low)/(high-low)*100 if high!=low else 50
            if not (2.0 <= naik <= 9.0): continue
            if not (20 <= pos <= 50): continue
            if last < open_p: continue
            cands.append((base, naik, pos, vol, last, low, high, open_p))
        except: continue
    cands = sorted(cands, key=lambda x: x[3], reverse=True)[:25]
    print(f"CHECK TOP10 {format_wib()}: {len(cands)} kandidat", flush=True)
    scored=[]
    for base, naik, pos, vol, last, low, high, open_p in cands:
        ob = get_orderbook_top10(base)
        if ob == "DELISTED":
            delisted_dyn[base]=now.isoformat(); save_json(DELISTED_FILE, delisted_dyn)
            print(f"AUTO BLACKLIST {base} 24 jam", flush=True); continue
        if not ob or ob['ratio']<=1.0 or ob['spread']>1.5 or ob['big_walls']<1: continue
        is_trending = base in trending_list; score=50
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
        if is_trending: score+=8
        if score>=75:
            print(f"LOLOS {base}:
