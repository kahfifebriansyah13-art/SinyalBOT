import requests, json, os, time, threading
from datetime import datetime, timedelta

# ===== CONFIG =====
TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
FILE_POS = "pos_v123.json"
FILE_STATS = "stats_v123.json"
FILE_COOLDOWN = "cooldown_v123.json"

# Kolam koin naik - Indodax + Ajaib, tidak ada koin besar
KOLAM_RISING = ["show","sqr","night","neon","pepe","shib","floki","bonk","wif","meme","turbo","brett","mog","pnut","goat","act","babydoge","doge","trx","xlm"]

def jam(): return datetime.now().strftime("%H:%M:%S")
def now(): return datetime.now()
def load(f, d):
    try:
        with open(f) as x: return json.load(x)
    except: return d
def save(f, d):
    with open(f, "w") as x: json.dump(d, x)

def send(msg):
    try: requests.post(f"https://api.telegram.org/bot{TOKEN}/sendMessage", json={"chat_id": CHAT_ID, "text": msg}, timeout=10)
    except: pass

# ===== WINRATE =====
def catat_sinyal(sym, entry, mode):
    stats = load(FILE_STATS, {"total":0, "win":0, "lose":0, "history":[]})
    stats["total"] += 1
    stats["history"].append({"sym":sym, "entry":entry, "mode":mode, "hasil":"OPEN", "tgl": now().isoformat(), "profit":0})
    save(FILE_STATS, stats)

def catat_hasil(sym, hasil, profit_pct):
    stats = load(FILE_STATS, {"total":0, "win":0, "lose":0, "history":[]})
    # Cari yang masih OPEN untuk koin ini
    for h in reversed(stats["history"]):
        if h["sym"]==sym and h["hasil"]=="OPEN":
            h["hasil"]=hasil; h["profit"]=profit_pct
            if hasil=="WIN": stats["win"]+=1
            else: stats["lose"]+=1
            break
    save(FILE_STATS, stats)

def hitung_winrate(hari=7):
    stats = load(FILE_STATS, {"total":0, "win":0, "lose":0, "history":[]})
    batas = now() - timedelta(days=hari)
    h = [x for x in stats["history"] if datetime.fromisoformat(x["tgl"]) > batas and x["hasil"]!="OPEN"]
    if not h: return "Belum ada data"
    win = len([x for x in h if x["hasil"]=="WIN"])
    total = len(h)
    wr = win/total*100
    profit = sum([x["profit"] for x in h])
    return f"📊 WINRATE {hari} HARI\nWIN: {win} / Total: {total}\nWinrate: {wr:.1f}%\nTotal Profit: +{profit:.1f}%\nPer Koin Paling WIN: {koin_terbaik(h)}"

def koin_terbaik(h):
    from collections import Counter
    c = Counter([x["sym"] for x in h if x["hasil"]=="WIN"])
    if not c: return "-"
    return c.most_common(1)[0][0]

# ===== SCAN GAINERS REAL-TIME =====
def get_data_indodax(sym):
    try:
        r = requests.get(f"https://indodax.com/api/{sym}_idr/ticker", timeout=8).json()["ticker"]
        return {
            "last": float(r["last"]), "vol": float(r["vol_idr"]),
            "high": float(r["high"]), "low": float(r["low"]),
            "buy": float(r["buy"]), "sell": float(r["sell"])
        }
    except: return None

def get_orderbook(sym):
    try:
        r = requests.get(f"https://indodax.com/api/{sym}_idr/depth", timeout=8).json()
        buy = sum([float(x[1]) for x in r["buy"][:10]])
        sell = sum([float(x[1]) for x in r["sell"][:10]])
        return buy, sell
    except: return 0, 0

def scan_rising():
    pos = load(FILE_POS, {})
    cooldown = load(FILE_COOLDOWN, {})
    hasil_scan = []

    for sym in KOLAM_RISING:
        if sym in pos: continue
        # Cooldown 2 jam setelah SL / TP habis
        if sym in cooldown:
            if now() - datetime.fromisoformat(cooldown[sym]) < timedelta(hours=2): continue
        data = get_data_indodax(sym)
        if not data: continue
        # Hitung naik 1 jam dari high-low (proxy karena Indodax tidak ada API 1h)
        # Kita pakai posisi harga dalam range 24h + volume sebagai proxy momentum
        last = data["last"]; low = data["low"]; high = data["high"]
        if high == low: continue
        pos_pct = (last - low) / (high - low) * 100
        # Proxy naik 1 jam: jika pos 35-85% dan vol besar, anggap sedang naik
        # Kita simpan harga untuk hitung naik 1h di scan berikutnya
        hasil_scan.append((sym, data, pos_pct))

    # Urutkan berdasarkan volume terbesar = paling ramai
    hasil_scan.sort(key=lambda x: x[1]["vol"], reverse=True)

    for sym, data, pos_pct in hasil_scan[:20]:
        last = data["last"]; vol = data["vol"]
        # Filter dasar V12.1
        if vol < 350_000_000: continue
        if not (35 <= pos_pct <= 85): continue
        buy_ob, sell_ob = get_orderbook(sym)
        if sell_ob == 0: continue
        ob_ratio = buy_ob / sell_ob
        if ob_ratio < 1.5: continue

        # Hitung naik 1h dari file harga sebelumnya (sederhana)
        harga_lama = load("harga_lama.json", {})
        naik_1h = 0
        if sym in harga_lama:
            naik_1h = (last - harga_lama[sym]["harga"]) / harga_lama[sym]["harga"] * 100
        # Simpan harga sekarang untuk scan berikutnya
        harga_lama[sym] = {"harga": last, "vol": vol, "waktu": now().isoformat()}
        save("harga_lama.json", harga_lama)

        # Hitung TP / SL
        entry = last
        tp1 = entry * 1.05; tp2 = entry * 1.10; tp3 = entry * 1.15
        sl_normal = entry * 0.96; sl_high = entry * 0.97

        # === MODE NORMAL: Naik 5% - 15% ===
        if 5 <= naik_1h <= 15 or naik_1h == 0: # naik_1h 0 = scan pertama, anggap NORMAL
            if pos.get(sym): continue
            pos[sym] = {"entry": entry, "tp1": tp1, "tp2": tp2, "tp3": tp3, "sl": sl_normal,
                        "hit": [], "trail_sl": sl_normal, "best": entry, "trailing_active": False, "last_trail_sent": 0, "mode": "NORMAL"}
            save(FILE_POS, pos)
            catat_sinyal(sym, entry, "NORMAL")
            send(f"🔥 RISING ONLY V12.3 {sym.upper()} {jam()}\nHarga: {entry:.0f} | Naik 1H: +{naik_1h:.1f}%\nVol: Rp {vol/1e9:.2f}M | Pos: {pos_pct:.0f}% | OB BUY {ob_ratio:.1f}x\nBisa beli di Indodax & Ajaib\n\nTP1 +5% = {tp1:.0f} (Jual 50%)\nTP2 +10% = {tp2:.0f} (Jual 30%)\nTP3 +15% = {tp3:.0f} (Jual 10%, sisa Trailing)\nSL -4% = {sl_normal:.0f}\nModal: Rp 20rb")

        # === MODE HIGH MOMENTUM: Naik >15% tapi masih Bullish ===
        elif naik_1h > 15:
            # Cek 4 indikator Bullish
            vol_naik = vol > harga_lama.get(sym, {}).get("vol", 0) if sym in harga_lama else True
            ob_bullish = ob_ratio >= 1.5
            diatas_support = last > entry * 0.98 # Masih di atas support baru
            candle_bullish = pos_pct > 50 # Harga masih di atas tengah range
            skor = sum([vol_naik, ob_bullish, diatas_support, candle_bullish])
            if skor >= 3:
                if pos.get(sym): continue
                pos[sym] = {"entry": entry, "tp1": tp1, "tp2": tp2, "tp3": tp3, "sl": sl_high,
                            "hit": [], "trail_sl": sl_high, "best": entry, "trailing_active": False, "last_trail_sent": 0, "mode": "HIGH"}
                save(FILE_POS, pos)
                catat_sinyal(sym, entry, "HIGH")
                send(f"🔥🔥 HIGH MOMENTUM {sym.upper()} {jam()}\nSudah naik +{naik_1h:.1f}% dalam 1 Jam, TAPI masih Bullish (Skor {skor}/4)\nVol masih naik, OB BUY {ob_ratio:.1f}x, Harga di atas Support\n\nEntry: {entry:.0f}\nTP1 +5% = {tp1:.0f} | TP2 +10% = {tp2:.0f} | TP3 +15% = {tp3:.0f}\nSL KETAT -3% = {sl_high:.0f}\n⚠️ Modal KECIL saja: Rp 10rb (Resiko 2x lipat)\nBisa beli di Indodax & Ajaib")
            else:
                send(f"⛔ TOLAK {sym.upper()} {jam()} Naik +{naik_1h:.1f}% tapi sudah TIDAK Bullish (Skor {skor}/4). Sudah pucuk, jangan beli.")

# ===== CEK TP + TRAILING OPSI C =====
def cek_tp():
    pos = load(FILE_POS, {})
    if not pos: return
    for sym, data in list(pos.items()):
        try:
            d = get_data_indodax(sym)
            if not d: continue
            last = d["last"]; entry = data["entry"]; tp1 = data["tp1"]; tp2 = data["tp2"]; tp3 = data["tp3"]
            sl = data["sl"]; hit = data.get("hit", [])
            trail_sl = data.get("trail_sl", sl); best = data.get("best", entry)
            if last > best: best = last; data["best"] = best

            if last >= tp1 and "TP1" not in hit:
                send(f"⚡ TP1 {sym.upper()} +5% {entry:.0f} -> {last:.0f} {jam()}\nJual 50%. Geser SL ke Modal.")
                data["hit"] = hit + ["TP1"]; data["trail_sl"] = entry; save(FILE_POS, pos)
            if last >= tp2 and "TP2" not in hit:
                send(f"⚡⚡ TP2 {sym.upper()} {entry:.0f} -> {last:.0f} {jam()}\nJual 30%. Geser SL ke TP1.")
                data["hit"] = hit + ["TP2"]; data["trail_sl"] = tp1; save(FILE_POS, pos)
            if last >= tp3 and "TP3" not in hit:
                send(f"⚡⚡⚡ TP3 {sym.upper()} {entry:.0f} -> {last:.0f} {jam()}\nJual 10%. Sisa 10% TRAILING.")
                data["hit"] = hit + ["TP3"]; data["trail_sl"] = tp2; data["trailing_active"] = True; save(FILE_POS, pos)

            # TRAILING
            if data.get("trailing_active"):
                new_trail = best * 0.95
                if new_trail > trail_sl and new_trail > tp3:
                    last_sent = float(data.get("last_trail_sent", 0))
                    if new_trail >= last_sent * 1.05 or last_sent == 0:
                        profit = (new_trail - entry)/entry*100
                        send(f"🔒 TRAILING {sym.upper()} {jam()}\nTertinggi {best:.0f}\nGESER SL ke {new_trail:.0f} (Profit terkunci +{profit:.1f}%)")
                        data["trail_sl"] = new_trail; data["last_trail_sent"] = new_trail; save(FILE_POS, pos)
                if last <= trail_sl:
                    profit = (last - entry)/entry*100
                    send(f"🔴 TRAILING SL Kena {sym.upper()} {jam()}\nEntry {entry:.0f} -> Keluar {last:.0f} (+{profit:.1f}%)\nJual Habis.")
                    catat_hasil(sym, "WIN" if profit>0 else "LOSE", profit)
                    pos.pop(sym); save(FILE_POS, pos)
                    cd = load(FILE_COOLDOWN, {}); cd[sym]=now().isoformat(); save(FILE_COOLDOWN, cd)
                    continue

            if "TP1" not in hit and last <= sl:
                profit = (last - entry)/entry*100
                send(f"🔴 SL {sym.upper()} {entry:.0f} -> {last:.0f} {jam()}\nJual Habis.")
                catat_hasil(sym, "LOSE", profit)
                pos.pop(sym); save(FILE_POS, pos)
                cd = load(FILE_COOLDOWN, {}); cd[sym]=now().isoformat(); save(FILE_COOLDOWN, cd)
        except: continue

# ===== TELEGRAM COMMAND =====
def cek_command():
    try:
        r = requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates", timeout=10).json()
        for u in r.get("result", [])[-5:]:
            if "message" not in u: continue
            txt = u["message"].get("text","").strip().lower()
            if txt == "/winrate":
                send(hitung_winrate(7))
            if txt == "/stats":
                send(hitung_winrate(30))
            if txt == "/clear":
                save(FILE_POS, {}); send("Posisi di-clear.")
    except: pass

# ===== MAIN LOOP =====
if __name__ == "__main__":
    send("✅ Bot V12.3 FINAL RISING ONLY Aktif\nHanya koin naik. Tidak ada koin besar.\nKetik /winrate untuk cek winrate.")
    while True:
        try:
            scan_rising(); cek_tp(); cek_command()
        except Exception as e: print(e)
        time.sleep(60) # Scan tiap 1 menit = Real-time
