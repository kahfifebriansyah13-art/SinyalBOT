import requests, os, time, json, threading
from http.server import BaseHTTPRequestHandler, HTTPServer

print("BOT V2.5 RAILWAY FIX STARTING...", flush=True)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
FILE = "posisi_aktif.json"

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK BOT V2.5 ACTIVE")
    def log_message(self, format, *args):
        return

def run_health():
    port = int(os.getenv("PORT", 8080))
    try:
        HTTPServer(("0.0.0.0", port), HealthHandler).serve_forever()
    except:
        pass

threading.Thread(target=run_health, daemon=True).start()

def kirim(pesan):
    for i in range(3):
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                data={"chat_id": CHAT_ID, "text": pesan, "parse_mode": "Markdown"},
                timeout=25
            )
            if r.status_code == 200:
                print("KIRIM OK", flush=True)
                return
        except Exception as e:
            print(f"KIRIM TRY {i+1} FAIL: {e}", flush=True)
            time.sleep(3)

def load():
    try:
        return json.load(open(FILE,'r'))
    except:
        return {}

def save(d):
    json.dump(d, open(FILE,'w'))

def get_tickers():
    for i in range(3):
        try:
            r = requests.get("https://indodax.com/api/tickers", timeout=20, headers={"User-Agent":"Mozilla/5.0"})
            if r.status_code == 200:
                return r.json()['tickers']
        except Exception as e:
            print(f"TICKERS TRY {i+1}: {e}", flush=True)
            time.sleep(2)
    return {}

def analisa():
    tickers = get_tickers()
    if not tickers:
        print("TICKERS KOSONG - RAILWAY BLOCK", flush=True)
        return []
    posisi = load()
    hasil = []
    for pair,d in tickers.items():
        if not pair.endswith('_idr'):
            continue
        base = pair.split('_')[0].upper()
        if base in posisi or base in ['USDT','USDC','DAI','IDR','PAXG']:
            continue
        try:
            last = float(d['last'])
            low = float(d['low'])
            high = float(d['high'])
            vol = float(d['vol_idr'])
            open_p = float(d.get('open', last))
            if low == 0 or high == 0:
                continue
            naik_low = (last-low)/low*100
            range_hl = high-low
            pos_harga = (last-low)/range_hl*100 if range_hl>0 else 50

            if not (0.3 <= naik_low <= 5.0):
                continue
            if vol < 120000000:
                continue
            if last >= high * 0.93:
                continue
            if last <= open_p:
                continue

            if pos_harga < 42:
                hasil.append({
                    'base':base,'entry':last,'tp1':last*1.05,'tp2':last*1.10,'sl':last*0.95,
                    'naik':naik_low,'vol':vol,'low':low,'high':high,'posisi':pos_harga,'open':open_p
                })
        except:
            continue
    return sorted(hasil, key=lambda x: x['vol'], reverse=True)[:4]

def cek_tp():
    posisi = load()
    if not posisi:
        return
    tickers = get_tickers()
    if not tickers:
        return
    for base,data in list(posisi.items()):
        try:
            key = base.lower() + '_idr'
            if key not in tickers:
                continue
            now = float(tickers[key]['last'])
            entry = data['entry']
            if now >= entry*1.05 and not data.get('tp1'):
                kirim(f"TP1 +5% KENA\n{base}/IDR\nEntry Rp {entry:,.0f} -> Now Rp {now:,.0f}")
                data['tp1']=True
                save(posisi)
            if now >= entry*1.10:
                kirim(f"TP2 +10% CLOSING\n{base}/IDR\nEntry Rp {entry:,.0f} -> Rp {now:,.0f}")
                del posisi[base]
                save(posisi)
            if now <= entry*0.95:
                kirim(f"SL -5%\n{base}/IDR\nEntry Rp {entry:,.0f} -> Rp {now:,.0f}")
                del posisi[base]
                save(posisi)
        except:
            continue

def main():
    time.sleep(3)
    kirim("BOT V2.5 RAILWAY FIX AKTIF\nEntry 0.3-5% dari Low\nVol >120jt | Masih di bawah 42%\nCek 40 detik - Anti ketinggalan")
    print("MAIN LOOP START", flush=True)
    while True:
        try:
            cek_tp()
            sinyal = analisa()
            print(f"ANALISA: {len(sinyal)} sinyal", flush=True)
            if sinyal:
                pos = load()
                for s in sinyal:
                    if s['base'] in pos:
                        continue
                    kirim(f"EARLY {s['base']}/IDR\nNaik +{s['naik']:.2f}% dari Low\nPosisi {s['posisi']:.0f}% Range\nVol Rp {s['vol']/1e9:.2f}M\nENTRY Rp {s['entry']:,.0f}\nTP1 Rp {s['tp1']:,.0f} (+5%)\nTP2 Rp {s['tp2']:,.0f} (+10%)\nSL Rp {s['sl']:,.0f} (-5%)")
                    pos[s['base']]={'entry':s['entry']}
                    save(pos)
            time.sleep(40)
        except Exception as e:
            print(f"MAIN ERROR: {e}", flush=True)
            time.sleep(20)

if __name__=="__main__":
    main()
