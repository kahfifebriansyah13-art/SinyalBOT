import requests, os, time, json, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
print("BOT V3.1 ADAPTIVE STARTING...", flush=True)
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
FILE = "posisi_aktif.json"
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b"OK V3.1 ADAPTIVE")
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
            if r.status_code == 200: print("KIRIM OK", flush=True); return
        except Exception as e: print(f"KIRIM FAIL {e}", flush=True); time.sleep(2)
def load():
    try: return json.load(open(FILE,'r'))
    except: return {}
def save(d): json.dump(d, open(FILE,'w'))
def get_tickers():
    try: return requests.get("https://indodax.com/api/tickers", timeout=20, headers={"User-Agent":"Mozilla/5.0"}).json()['tickers']
    except: return {}
def analisa():
    tickers = get_tickers()
    if not tickers: return []
    posisi = load()
    for vol_min in [50000000, 30000000, 15000000]:
        early = []; momentum = []
        for pair,d in tickers.items():
            if not pair.endswith('_idr'): continue
            base = pair.split('_')[0].upper()
            if base in posisi or base in ['USDT','USDC','DAI','IDR','PAXG']: continue
            try:
                last = float(d['last']); low = float(d['low']); high = float(d['high']); vol = float(d['vol_idr']); open_p = float(d.get('open', last))
                if low==0 or high==0: continue
                naik_low = (last-low)/low*100; pos_harga = (last-low)/(high-low)*100 if high!=low else 50
                if (0.2 <= naik_low <= 6.0) and vol >= vol_min and pos_harga < 55 and last >= open_p:
                    early.append({'base':base,'entry':last,'tp1':last*1.05,'tp2':last*1.10,'sl':last*0.95,'naik':naik_low,'vol':vol,'pos':pos_harga,'tipe':f'EARLY BAWAH {vol_min/1e6:.0f}jt'})
                elif (0.5 <= naik_low <= 18.0) and vol >= vol_min and 20 <= pos_harga <= 85:
                    momentum.append({'base':base,'entry':last,'tp1':last*1.05,'tp2':last*1.10,'sl':last*0.95,'naik':naik_low,'vol':vol,'pos':pos_harga,'tipe':f'MOMENTUM {vol_min/1e6:.0f}jt'})
            except: continue
        if early:
            print(f"ANALISA: {len(early)} EARLY di VOL {vol_min/1e6:.0f}jt -> KIRIM", flush=True)
            return sorted(early, key=lambda x: x['vol'], reverse=True)[:3]
        if momentum:
            print(f"ANALISA: {len
