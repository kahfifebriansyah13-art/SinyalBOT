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
            print(f"ANALISA: {len(momentum)} MOMENTUM di VOL {vol_min/1e6:.0f}jt -> KIRIM", flush=True)
            return sorted(momentum, key=lambda x: x['vol'], reverse=True)[:3]
    print("ANALISA: 0 sinyal semua level vol", flush=True)
    return []
def cek_tp():
    posisi = load()
    if not posisi: return
    tickers = get_tickers()
    if not tickers: return
    for base,data in list(posisi.items()):
        try:
            key = base.lower() + '_idr'
            if key not in tickers: continue
            now = float(tickers[key]['last']); entry = data['entry']
            if now >= entry*1.05 and not data.get('tp1'):
                kirim(f"TP1 +5% KENA\n{base}/IDR"); data['tp1']=True; save(posisi)
            if now >= entry*1.10:
                kirim(f"TP2 +10% CLOSE\n{base}/IDR Entry {entry:,.0f} -> {now:,.0f}"); del posisi[base]; save(posisi)
            if now <= entry*0.95:
                kirim(f"SL -5%\n{base}/IDR"); del posisi[base]; save(posisi)
        except: continue
def main():
    time.sleep(2)
    kirim("BOT V3.1 ADAPTIVE AKTIF\nVol 50jt > 30jt > 15jt\nEarly dulu, Momentum cadangan\nCek 40 detik")
    print("MAIN LOOP V3.1 ADAPTIVE", flush=True)
    while True:
        try:
            cek_tp()
            sinyal = analisa()
            if sinyal:
                pos = load()
                for s in sinyal:
                    if s['base'] in pos: continue
                    kirim(f"{s['tipe']} {s['base']}/IDR\nNaik +{s['naik']:.2f}% dari Low\nPos {s['pos']:.0f}% Range\nVol Rp {s['vol']/1e9:.2f}M\nENTRY Rp {s['entry']:,.0f}\nTP1 +5% TP2 +10% SL -5%")
                    pos[s['base']]={'entry':s['entry']}; save(pos)
            time.sleep(40)
        except Exception as e: print(f"ERROR {e}", flush=True); time.sleep(20)
if __name__=="__main__": main()
