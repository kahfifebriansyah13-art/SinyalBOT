import requests, os, time, json, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime, timedelta

print("BOT V4.1 ORDERBOOK STARTING...", flush=True)
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
FILE = "posisi_aktif.json"
COOLDOWN_FILE = "cooldown.json"
LAST_UPDATE_FILE = "last_update.json"

def now_wib(): return datetime.utcnow() + timedelta(hours=7)
def format_wib(): return now_wib().strftime("%H:%M WIB")

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self): self.send_response(200); self.end_headers(); self.wfile.write(b"OK V4.1 ORDERBOOK")
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

def get_orderbook_analysis(base):
    """ANALISA ORDER BOOK - TEKANAN BELI VS JUAL"""
    try:
        pair = f"{base.lower()}_idr"
        r = requests.get(f"https://indodax.com/api/{pair}/depth", timeout=10).json()
        bids = r.get('buy', [])[:20] # 20 bid teratas
        asks = r.get('sell', [])[:20] # 20 ask teratas
        if not bids or not asks: return None
        
        # Hitung total volume buy vs sell (dalam IDR)
        total_buy_idr = sum(float(price)*float(vol) for price, vol in bids)
        total_sell_idr = sum(float(price)*float(vol) for price, vol in asks)
        
        if total_sell_idr == 0: return None
        
        ratio = total_buy_idr / total_sell_idr # >1 = buy pressure kuat
        
        # Cek spread
        best_bid = float(bids[0][0])
        best_ask = float(asks[0][0])
        spread_pct = (best_ask - best_bid) / best_bid * 100
        
        # Cek big wall di buy side (support kuat)
        big_bid_walls = sum(1 for price, vol in bids if float(price)*float(vol) > 10_000_000) # wall >10jt
        
        return {
            'ratio': ratio,
            'buy_idr': total_buy_idr,
            'sell_idr': total_sell_idr,
            'spread': spread_pct,
            'big_walls': big_bid_walls,
            'best_bid': best_bid,
            'best_ask': best_ask
        }
    except:
        return None

def get_coingecko_trending():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/search/trending", timeout=15).json()
        return [c['item']['symbol'].upper() for c in r.get('coins', [])]
    except: return []

def format_tmg(s, rank):
    if rank == 1: prioritas = "🔥 PRIORITAS 1 - ENTRY UTAMA"
    elif rank <= 3: prioritas = f"⭐ PRIORITAS {rank} - BOLEH ENTRY"
    else: prioritas = f"⚠️ PRIORITAS {rank} - WATCHLIST"
    
    ob = s.get('orderbook', {})
    ob_text = f"📚 OB: Buy/Sell {ob.get('ratio',0):.2f}x | Wall: {ob.get('big_walls',0)}" if ob else "📚 OB: -"
    
    trending_icon = "🌐 TRENDING: YES 🔥" if s['is_trending'] else "🌐 Trending: -"
    jam = format_wib()
    return f"""┏━━━━━━━━━━━━━━━━━━┓
┃ #{rank} {s['base']}/IDR - SCORE {s['score']} ┃
┗━━━━━━━━━━━━━━━━━━┛

💎 AKAN TRENDING 💎 LOCAL
{trending_icon}
{ob_text}

┌─ 🕯️ DAILY CANDLE ─┐
│ 🟢 Open: Rp {s['open']:,.0f} | Close: Rp {s['entry']:,.0f}
│ 📊 Pos: {s['pos']:.0f}% dari Low-High | Naik: +{s['naik']:.2f}%
│ ⭐ Score: {s['score']}/100
│ {prioritas}
└──────────────────┘

┌─ 📊 MARKET DATA ─┐
│ 💧 Low: Rp {s['low']:,.0f} | High: Rp {s['high']:,.0f}
│ 💰 Vol: Rp {s['vol']/1e6:.2f} M
│ 📈 Buy Press: {ob.get('ratio',0):.2f}x | Spread: {ob.get('spread',0):.2f}%
└──────────────────┘

┌─ 🎯 TRADING PLAN ─┐
│ 🟢 ENTRY: Rp {s['entry']:,.0f}
│ 🎯 TP1: Rp {s['tp1']:,.0f} (+5%)
│ 🏆 TP2: Rp {s['tp2']:,.0f} (+10%)
│ 🔴 SL: Rp {s['sl']:,.0f} (-5%)
└──────────────────┘

⏰ {format_wib()} - Order book valid
"""

def analisa_ranking():
    tickers = get_tickers()
    if not tickers: return []
    trending_list = get_coingecko_trending()
    posisi = load_json(FILE, {})
    cooldown = load_json(COOLDOWN_FILE, {})
    now = now_wib()
    
    for k in list(cooldown.keys()):
        try:
            t = datetime.fromisoformat(cooldown[k])
            if now - t > timedelta(hours=6): del cooldown[k]
        except: del cooldown[k]
    save_json(COOLDOWN_FILE, cooldown)
    
    scored = []
    candidates = []
    
    # TAHAP 1: FILTER AWAL CEPAT
    for pair,d in tickers.items():
        if not pair.endswith('_idr'): continue
        base = pair.split('_')[0].upper()
        if base in posisi or base in cooldown or base in ['USDT','USDC','DAI','IDR']: continue
        try:
            last = float(d['last']); low = float(d['low']); high = float(d['high'])
            vol = float(d['vol_idr']); open_p = float(d.get('open', last))
            if vol < 150_000_000 or low==0: continue
            naik_low = (last-low)/low*100
            pos_h = (last-low)/(high-low)*100 if high!=low else 50
            if not (3.0 <= naik_low <= 7.0): continue
            if not (20 <= pos_h <= 45): continue
            if last < open_p: continue
            candidates.append((base, d, naik_low, pos_h, vol, last, low, high, open_p))
        except: continue
    
    # Sort kandidat awal by vol biar cek order book yang paling potensial dulu
    candidates = sorted(candidates, key=lambda x: x[4], reverse=True)[:20] # ambil 20 teratas saja biar tidak lambat
    
    print(f"ORDERBOOK CHECK {format_wib()}: Cek {len(candidates)} kandidat", flush=True)
    
    # TAHAP 2: ANALISA ORDER BOOK (YANG PALING PENTING)
    for base, d, naik_low, pos_h, vol, last, low, high, open_p in candidates:
        try:
            ob = get_orderbook_analysis(base)
            if not ob: continue
            
            # FILTER ORDER BOOK KETAT - HARUS NAIK
            if ob['ratio'] < 1.3: continue # Buy harus 1.3x lebih besar dari Sell
            if ob['spread'] > 1.0: continue # Spread harus <1% (likuid)
            if ob['big_walls'] < 2: continue # Harus ada minimal 2 big wall support
            
            is_trending = base in trending_list
            
            # SCORE DENGAN ORDER BOOK
            score = 50
            if vol >= 500_000_000: score += 15
            elif vol >= 150_000_000: score += 10
            
            if 4.0 <= naik_low <= 6.0: score += 15
            elif 3.0 <= naik_low < 4.0: score += 10
            
            if 25 <= pos_h <= 35: score += 10
            
            # ORDER BOOK SCORE - PALING BERAT
            if ob['ratio'] >= 2.0: score += 20 # Buy 2x Sell = sangat bullish
            elif ob['ratio'] >= 1.5: score += 12
            elif ob['ratio'] >= 1.3: score += 6
            
            if ob['big_walls'] >= 4: score += 10
            elif ob['big_walls'] >= 2: score += 5
            
            if is_trending: score += 8
            
            if score >= 85: # MINIMAL 85 - SUPER KETAT
                scored.append({
                    'base':base,'entry':last,'low':low,'high':high,'open':open_p,
                    'tp1':last*1.05,'tp2':last*1.10,'sl':last*0.95,
                    'naik':naik_low,'vol':vol,'pos':pos_h,'score':min(score,100),
                    'is_trending':is_trending,'orderbook':ob
                })
                time.sleep(0.5) # jeda biar tidak kena rate limit
            
            if len(scored) >= 10: break # sudah dapat 10, stop
            
        except: continue
    
    scored = sorted(scored, key=lambda x: (x['orderbook']['ratio'], x['score']), reverse=True)
    print(f"ORDERBOOK RESULT {format_wib()}: {len(scored)} lolos OB ratio >1.3", flush=True)
    return scored[:10]

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
                kirim(f"🏆 *TP2 +10% TERCAPAI!* {base}/IDR - {format_wib()}\n💰 +{((last-entry)/entry*100):.2f}% | Rp {entry:,.0f} -> Rp {last:,.0f}\n✅ Order book valid, target tercapai!")
                del pos[base]; save_json(FILE, pos)
            elif last >= entry*1.05 and not tp1_hit:
                kirim(f"🎯 *TP1 +5% TERCAPAI!* {base}/IDR - {format_wib()}\n💰 +{((last-entry)/entry*100):.2f}% | Rp {entry:,.0f} -> Rp {last:,.0f}\n✍️ Geser SL ke Entry!")
                pos[base]['tp1_hit'] = True; save_json(FILE, pos)
            elif last <= entry*0.95:
                kirim(f"🔴 *SL -5% KENA!* {base}/IDR - {format_wib()}\n💸 {((last-entry)/entry*100):.2f}%")
                del pos[base]; save_json(FILE, pos)
        except: continue

def hitung_profit():
    tickers = get_tickers()
    if not tickers: return
    pos = load_json(FILE, {})
    if not pos: 
        kirim(f"📭 *FOCUS MODE* - {format_wib()}\nTidak ada posisi aktif.\nBot akan cari 10 sinyal baru dengan analisa order book")
        return
    pesan = f"📊 *PROFIT FOCUS OB - {format_wib()}*\n━━━━━━━━━━━━━━━━━━━━\nFokus {len(pos)} koin (OB valid) sampai TP:\n\n"
    total=0
    for base, data in pos.items():
        pair = f"{base.lower()}_idr"
        if pair not in tickers: continue
        last = float(tickers[pair]['last']); entry = data['entry']
        pct = (last-entry)/entry*100; total+=pct
        emoji = "🟢" if pct>=0 else "🔴"; tp="✅" if data.get('tp1_hit') else "⏳"
        pesan+=f"{emoji} {base}: {pct:+.2f}% {tp} | Rp {entry:,.0f}->{last:,.0f}\n"
    pesan+=f"━━━━━━━━━━━━━━\nAvg: {total/len(pos):+.2f}% | Mode: OB Ratio >1.3"
    kirim(pesan)

def cek_command():
    try:
        last_id = load_json(LAST_UPDATE_FILE, {"id":0})["id"]
        r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={last_id+1}&timeout=5", timeout=10).json()
        if not r.get('result'): return
        for u in r['result']:
            save_json(LAST_UPDATE_FILE,{"id":u['update_id']})
            txt = u.get('message',{}).get('text','').lower().strip()
            if txt in ['/profit','/status','/cek']: hitung_profit()
            elif txt == '/clear': save_json(FILE, {}); save_json(COOLDOWN_FILE, {}); kirim(f"✅ Reset - {format_wib()}")
    except: pass

def main():
    time.sleep(2)
    kirim(f"✅ *BOT V4.1 ORDER BOOK AKTIF - {format_wib()}*\n• Analisa order book buy/sell ratio\n• Filter: Buy 1.3x > Sell | Spread <1% | Wall >=2\n• Score minimal 85+ | Vol 150M+ | Pos 20-45%\n• Format sama | Fokus TP | Anti spam 6 jam\n• /profit")
    print(f"MAIN LOOP OB {format_wib()}", flush=True)
    loop=0
    while True:
        try:
            if loop % 6 == 0: cek_tp()
            if loop % 3 == 0: cek_command()
            pos = load_json(FILE, {})
            if len(pos) == 0 and loop % 25 == 0:
                sinyal_list = analisa_ranking()
                if sinyal_list:
                    jam = format_wib()
                    pesan = f"🏆 *10 SINYAL VALID OB - {jam}*\n━━━━━━━━━━━━━━━━━━━━\nOrder book bullish, potensi naik tinggi ke TP1 5%:\n\n"
                    for i,s in enumerate(sinyal_list,1):
                        ob = s['orderbook']
                        pesan+=f"{i}. {s['base']}/IDR ⭐{s['score']} | OB {ob['ratio']:.2f}x Wall {ob['big_walls']} | +{s['naik']:.1f}% Pos {s['pos']:.0f}%\n"
                    pesan+=f"━━━━━━━━━━━━━━\n⏰ {jam}\n🔒 Fokus sampai TP, tidak kirim baru"
                    kirim(pesan); time.sleep(3)
                    cooldown = load_json(COOLDOWN_FILE, {})
                    for rank,s in enumerate(sinyal_list,1):
                        if s['base'] in pos: continue
                        kirim(format_tmg(s,rank))
                        pos[s['base']]={'entry':s['entry'],'tp1_hit':False}
                        save_json(FILE, pos)
                        cooldown[s['base']] = now_wib().isoformat()
                        save_json(COOLDOWN_FILE, cooldown)
                        time.sleep(2)
            loop+=1; time.sleep(30)
        except Exception as e: print(f"ERR {e}", flush=True); time.sleep(20)

if __name__=="__main__": main()
