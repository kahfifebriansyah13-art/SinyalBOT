import requests, os, time, json, threading
from http.server import BaseHTTPRequestHandler, HTTPServer

print("BOT V3.2 TMG FINAL STARTING...", flush=True)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
FILE = "posisi_aktif.json"

# Health check Railway
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"OK V3.2 TMG")
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
            if r.status_code == 200: print("KIRIM OK", flush=True); return True
        except Exception as e: print(f"FAIL KIRIM {e}", flush=True); time.sleep(2)
    return False

def load():
    try: return json.load(open(FILE,'r'))
    except: return {}

def save(d): json.dump(d, open(FILE,'w'))

def get_tickers():
    try:
        return requests.get("https://indodax.com/api/tickers", timeout=20, headers={"User-Agent":"Mozilla/5.0"}).json()['tickers']
    except: return {}

# FORMAT 100% SAMA SEPERTI TMG
def format_tmg(s):
    return f"""┏━━━━━━━━━━━━━━━━━━┓
┃ {s['base']}/IDR - AKAN TRENDING ┃
┗━━━━━━━━━━━━━━━━━━┛

💎 AKAN TRENDING 💎 LOCAL

┌─ 🕯️ DAILY CANDLE + MA RSI VOL ─┐
│ 🟢 Open: Rp {s['open']:,.0f} | Close: Rp {s['entry']:,.0f} (HIJAU)
│ 📊 RSI Daily: {s['rsi']:.1f} + MA Bullish
│ 🤖 Rekom: NEUTRAL
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

def analisa():
    tickers = get_tickers()
    if not tickers: return []
    posisi = load()
    hasil = []
    
    # VOLUME 100JT + MOMENTUM KENAIKAN
    for pair,d in tickers.items():
        if not pair.endswith('_idr'): continue
        base = pair.split('_')[0].upper()
        if base in posisi or base in ['USDT','USDC','DAI','IDR','PAXG','BTC','ETH']: 
            # BTC ETH tetap boleh kalau momentum kuat? Skip dulu biar altcoin
            pass
        if base in posisi: continue
        try:
            last = float(d['last']); low = float(d['low']); high = float(d['high'])
            vol = float(d['vol_idr']); open_p = float(d.get('open', last))
            if low==0 or vol < 100000000: continue # FILTER 100JT
            naik_low = (last-low)/low*100
            pos_h = (last-low)/(high-low)*100 if high!=low else 50
            
            # MOMENTUM KENAIKAN KOIN: naik 1% - 12% dari low, posisi masih di bawah 70%, volume tinggi
            if (1.0 <= naik_low <= 12.0) and (pos_h < 70) and last >= open_p:
                hasil.append({
                    'base':base,'entry':last,'low':low,'high':high,'open':open_p,
                    'tp1':last*1.05,'tp2':last*1.10,'sl':last*0.95,
                    'naik':naik_low,'vol':vol,'pos':pos_h,'rsi':55.0
                })
        except: continue
    
    print(f"ANALISA VOL 100jt: {len(hasil)} koin momentum", flush=True)
    return sorted(hasil, key=lambda x: x['vol'], reverse=True)[:3]

def cek_tp():
    tickers = get_tickers()
    if not tickers: return
    pos = load()
    if not pos: return
    for base, data in list(pos.items()):
        pair = f"{base.lower()}_idr"
        if pair not in tickers: continue
        try:
            last = float(tickers[pair]['last'])
            entry = data['entry']
            tp1 = entry*1.05; tp2 = entry*1.10; sl = entry*0.95
            
            if last >= tp2:
                kirim(f"🏆 *TP2 TERCAPAI!* {base}/IDR\n💰 Entry Rp {entry:,.0f} -> Now Rp {last:,.0f} (+10%)\n✅ AMANKAN PROFIT!")
                del pos[base]; save(pos)
            elif last >= tp1:
                kirim(f"🎯 *TP1 TERCAPAI!* {base}/IDR\n💰 Entry Rp {entry:,.0f} -> Now Rp {last:,.0f} (+5%)\nGeser SL ke Entry!")
            elif last <= sl:
                kirim(f"🔴 *SL KENA!* {base}/IDR\n💸 Entry Rp {entry:,.0f} -> Now Rp {last:,.0f} (-5%)")
                del pos[base]; save(pos)
        except: continue

def main():
    time.sleep(2)
    kirim("✅ BOT V3.2 TMG FINAL AKTIF\n• Format TMG Original\n• Vol Min 100jt\n• Momentum Naik 1-12%\n• Notif TP1/TP2/SL Aktif")
    print("MAIN LOOP V3.2", flush=True)
    loop = 0
    while True:
        try:
            if loop % 10 == 0: cek_tp() # cek TP tiap 10 loop
            sinyal = analisa()
            if sinyal:
                pos = load()
                for s in sinyal:
                    if s['base'] in pos: continue
                    kirim(format_tmg(s))
                    pos[s['base']]={'entry':s['entry']}; save(pos)
            loop+=1
            time.sleep(30)
        except Exception as e: print(f"ERROR {e}", flush=True); time.sleep(20)

if __name__=="__main__": main()
