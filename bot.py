import requests, os, time, json
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
FILE = "posisi_aktif.json"
FILE_STAT = "statistik.json"

try:
    from tradingview_ta import TA_Handler, Interval
    TV_AVAILABLE = True
except:
    TV_AVAILABLE = False

def kirim(pesan):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": pesan, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e: print(e)

def load():
    try: return json.load(open(FILE,'r'))
    except: return {}
def save(d): json.dump(d, open(FILE,'w'))
def load_stat():
    try: return json.load(open(FILE_STAT,'r'))
    except: return {"total":0,"tp1":0,"tp2":0,"sl":0,"winrate":0}
def save_stat(s): json.dump(s, open(FILE_STAT,'w'))
def update_stat(h):
    s=load_stat(); s["total"]+=1
    if h=="TP1": s["tp1"]+=1
    if h=="TP2": s["tp2"]+=1
    if h=="SL": s["sl"]+=1
    s["winrate"]=round((s["tp1"]+s["tp2"])/s["total"]*100,2) if s["total"]>0 else 0
    save_stat(s); return s

def get_tickers():
    try: return requests.get("https://indodax.com/api/tickers", timeout=15).json()['tickers']
    except: return {}

def get_tv(symbol, tf="1d"):
    if not TV_AVAILABLE: return None,None
    try:
        interval = Interval.INTERVAL_1_HOUR if tf=="1h" else Interval.INTERVAL_1_DAY
        h = TA_Handler(symbol=symbol, screener="indonesia", exchange="INDODAX", interval=interval)
        a = h.get_analysis()
        return a.indicators, a.summary
    except: return None,None

# === V2.2 FINAL - VOLUME SPIKE + CANDLE KUAT + TEKNIKAL EARLY ===
def analisa():
    tickers=get_tickers()
    if not tickers: return []
    posisi=load()
    hasil=[]

    for pair,d in tickers.items():
        if not pair.endswith('_idr'): continue
        base=pair.split('_')[0].upper()
        if base in posisi or base in ['USDT','USDC','DAI']: continue
        try:
            last=float(d['last']); low=float(d['low']); high=float(d['high'])
            vol=float(d['vol_idr']); open_price=float(d.get('open',last))
            if low==0 or high==0: continue

            naik_low=(last-low)/low*100
            # FINAL: 0.5% - 6% = MASIH DI BAWAH, BELUM DIPOMPA
            if naik_low < 0.5 or naik_low > 6.0: continue
            if vol < 150000000: continue  # 150jt minimal

            ind_d,_ = get_tv(f"{base}IDR","1d")
            ind_1h,_ = get_tv(f"{base}IDR","1h")
            if not ind_d or not ind_1h: continue

            # --- TEKNIKAL DAILY ---
            rsi_d = ind_d.get('RSI',50)
            sma20_d = ind_d.get('SMA20',0)
            sma50_d = ind_d.get('SMA50',0)

            # --- TEKNIKAL 1H (KUNCI EARLY) ---
            rsi_1h = ind_1h.get('RSI',50)
            ema9_1h = ind_1h.get('EMA9',0)
            ema21_1h = ind_1h.get('EMA21',0)
            macd_1h = ind_1h.get('MACD.macd',-999)
            macd_sig_1h = ind_1h.get('MACD.signal',-999)
            macd_hist_1h = ind_1h.get('MACD.histogram',0)
            open_1h = ind_1h.get('open',last)
            close_1h = ind_1h.get('close',last)
            bb_upper_1h = ind_1h.get('BB.upper',0)
            bb_lower_1h = ind_1h.get('BB.lower',0)
            bb_basis_1h = ind_1h.get('BB.basis',0)

            # === 1. CANDLE ===
            # Candle 1H harus hijau dan body kuat >30% dari range
            candle_body = abs(close_1h - open_1h)
            candle_range = abs(bb_upper_1h - bb_lower_1h) if bb_upper_1h and bb_lower_1h else (high-low)
            is_bullish_candle = close_1h > open_1h
            is_strong_body = (candle_body / candle_range > 0.25) if candle_range>0 else True

            # === 2. VOLUME SPIKE ===
            # Vol 150jt + harga naik = bandar mulai masuk
            is_volume_ok = vol >= 150000000
            # Jauh dari high = masih ada ruang 8-15%
            is_far_from_high = last < high * 0.92

            # === 3. TEKNIKAL EARLY ===
            cond_daily = rsi_d > 40 and rsi_d < 63 and last > sma20_d * 0.98 and last > sma50_d * 0.97
            cond_rsi_1h = rsi_1h > 46 and rsi_1h < 61  # baru cross 50
            cond_ema_1h = ema9_1h > ema21_1h * 0.997 and ema9_1h < ema21_1h * 1.025 # baru golden cross
            cond_macd_1h = macd_1h > macd_sig_1h and macd_hist_1h > -0.05 # MACD baru hijau

            if not (is_bullish_candle and is_strong_body and is_volume_ok and is_far_from_high and cond_daily and cond_rsi_1h and cond_ema_1h and cond_macd_1h):
                continue

            hasil.append({
                'base':base,'entry':last,'tp1':last*1.05,'tp2':last*1.10,'sl':last*0.95,
                'naik':naik_low,'vol':vol,'rsi_d':rsi_d,'rsi_1h':rsi_1h,
                'open_1h':open_1h,'close_1h':close_1h,'low':low,'high':high,
                'ema9':ema9_1h,'ema21':ema21_1h,'macd_hist':macd_hist_1h
            })
            time.sleep(0.5)
        except: continue

    return sorted(hasil, key=lambda x: x['vol'], reverse=True)[:5]

def cek_tp():
    posisi=load()
    if not posisi: return
    tickers=get_tickers()
    for base,data in list(posisi.items()):
        try:
            now=float(tickers[f"{base.lower()}_idr"]['last'])
            entry=data['entry']
            if now >= entry*1.05 and not data.get('tp1'):
                update_stat("TP1")
                kirim(f"✅ *TP1 +5% KENA*\n💰 {base}/IDR\nEntry Rp {entry:,.0f} -> Now Rp {now:,.0f}\nTahan ke TP2")
                data['tp1']=True; save(posisi)
            if now >= entry*1.10:
                stat=update_stat("TP2")
                kirim(f"╔══════════════════╗\n║ 🏆 TP2 +10% CLOSING ║\n╚══════════════════╝\n💎 *{base}/IDR*\nEntry Rp {entry:,.0f} -> Rp {now:,.0f}\n\n📊 *WINRATE CLOSING*\n🎯 {stat['winrate']}% ({stat['tp1']+stat['tp2']}/{stat['total']})\n✅ TP1:{stat['tp1']} 🏆 TP2:{stat['tp2']} ❌ SL:{stat['sl']}")
                del posisi[base]; save(posisi)
            if now <= entry*0.95:
                stat=update_stat("SL")
                kirim(f"╔══════════════════╗\n║ 🛑 SL -5% CLOSING  ║\n╚══════════════════╝\n🔻 *{base}/IDR*\nEntry Rp {entry:,.0f} -> Rp {now:,.0f}\n\n📊 *WINRATE CLOSING*\n🎯 {stat['winrate']}% ({stat['tp1']+stat['tp2']}/{stat['total']})\n✅ TP1:{stat['tp1']} 🏆 TP2:{stat['tp2']} ❌ SL:{stat['sl']}")
                del posisi[base]; save(posisi)
        except: continue

def main():
    kirim("🚀 *BOT EARLY GAINER V2.2 FINAL AKTIF*\n✅ Candle: 1H Hijau + Body Kuat >25%\n✅ Volume: >150jt + Jauh 8% dari High\n✅ Teknikal: RSI D 40-63 + RSI 1H 46-61 + EMA9 Cross 1H + MACD Hijau\n💡 Masuk 0.5-6% dari Low - SEBELUM PUMP\n📈 TP1 tanpa winrate | TP2/SL closing + winrate")
    while True:
        try:
            cek_tp()
            sinyal=analisa()
            if sinyal:
                pos=load()
                for s in sinyal:
                    if s['base'] in pos: continue
                    kirim(f"╔════════════════════════╗\n║ 🚀 EARLY {s['base']}/IDR SEBELUM PUMP ║\n╚════════════════════════╝\n\n📊 *CANDLE & VOLUME*\n🕯️ 1H: Rp {s['open_1h']:,.0f} -> Rp {s['close_1h']:,.0f} 🟢 Body Kuat\n💰 Vol: Rp {s['vol']/1e9:.2f} M (Bandar Mulai Masuk)\n📈 Naik dari Low: +{s['naik']:.2f}% (Masih di Bawah)\n💧 High: Rp {s['high']:,.0f} | Low: Rp {s['low']:,.0f} (Ruang +8%)\n\n┏━ 📈 TEKNIKAL EARLY ━┓\n┃ Daily RSI: {s['rsi_d']:.1f} (Sehat 40-63)\n┃ 1H RSI: {s['rsi_1h']:.1f} (Baru Cross 50)\n┃ EMA9 1H: {s['ema9']:,.0f} > EMA21 1H: {s['ema21']:,.0f} (Golden Cross Baru)\n┃ MACD 1H Hist: {s['macd_hist']:.4f} (Baru Hijau)\n┗━━━━━━━━━━━━━━━┛\n\n┏━ 🎯 ENTRY AWAL ━┓\n┃ 🟢 ENTRY: Rp {s['entry']:,.0f}\n┃ 🎯 TP1: Rp {s['tp1']:,.0f} (+5%)\n┃ 🏆 TP2: Rp {s['tp2']:,.0f} (+10%)\n┃ 🛑 SL: Rp {s['sl']:,.0f} (-5%)\n┗━━━━━━━━━━━━━━━┛\n\n⚡ *MASUK SEKARANG SEBELUM JADI TOP GAINER INDODAX!*")
                    pos[s['base']]={'entry':s['entry']}; save(pos)
            time.sleep(55)
        except Exception as e:
            print(e); time.sleep(20)

if __name__=="__main__":
    main()
