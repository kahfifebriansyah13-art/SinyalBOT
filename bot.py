import requests, os, time, json
from datetime import datetime, timedelta

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
    except: pass

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
    try: return requests.get("https://indodax.com/api/tickers", timeout=10).json()['tickers']
    except: return {}

def get_tv(symbol, tf="1d"):
    if not TV_AVAILABLE: return None,None
    try:
        interval = Interval.INTERVAL_1_HOUR if tf=="1h" else Interval.INTERVAL_1_DAY
        h = TA_Handler(symbol=symbol, screener="indonesia", exchange="INDODAX", interval=interval)
        a = h.get_analysis()
        return a.indicators, a.summary
    except: return None,None

# === EARLY GAINER V2 - MASUK SEBELUM NAIK TINGGI ===
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
            last=float(d['last']); low=float(d['low']); high=float(d['high']); vol=float(d['vol_idr'])
            if vol < 200000000: continue
            if low==0: continue
            naik_low=(last-low)/low*100
            # V2: 0.8% - 4.5% = MASIH DI BAWAH BANGET
            if naik_low < 0.8 or naik_low > 4.5: continue
            
            ind_d,_ = get_tv(f"{base}IDR","1d")
            ind_1h,_ = get_tv(f"{base}IDR","1h")
            if not ind_d or not ind_1h: continue

            rsi_d = ind_d.get('RSI',50)
            sma20_d = ind_d.get('SMA20',0)
            ema21_d = ind_d.get('EMA21',0)

            rsi_1h = ind_1h.get('RSI',50)
            ema9_1h = ind_1h.get('EMA9',0)
            ema21_1h = ind_1h.get('EMA21',0)
            macd_1h = ind_1h.get('MACD.macd',-999)
            macd_sig_1h = ind_1h.get('MACD.signal',-999)
            open_1h = ind_1h.get('open',last)
            close_1h = ind_1h.get('close',last)
            bb_low_1h = ind_1h.get('BB.lower',0)

            # FILTER V2 - MASUK AWAL
            cond_d = rsi_d > 42 and rsi_d < 60 and last > sma20_d * 0.99
            cond_1 = rsi_1h > 48 and rsi_1h < 58
            cond_2 = ema9_1h > ema21_1h * 0.998 and ema9_1h < ema21_1h * 1.02
            cond_3 = macd_1h > macd_sig_1h
            cond_4 = close_1h > open_1h
            cond_5 = last < high * 0.90
            cond_6 = bb_low_1h==0 or last < bb_low_1h * 1.12

            if not (cond_d and cond_1 and cond_2 and cond_3 and cond_4 and cond_5):
                continue

            hasil.append({
                'base':base,'entry':last,'tp1':last*1.05,'tp2':last*1.10,'sl':last*0.95,
                'naik':naik_low,'vol':vol,'rsi_d':rsi_d,'rsi_1h':rsi_1h,
                'open_1h':open_1h,'close_1h':close_1h,'low':low,'high':high,
                'ema9_1h':ema9_1h,'ema21_1h':ema21_1h
            })
            time.sleep(0.45)
        except: continue
    return sorted(hasil, key=lambda x: x['naik'], reverse=True)[:5]

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
    kirim("🚀 *BOT EARLY GAINER V2 AKTIF*\n🔍 Filter: Naik 0.8-4.5% dari Low\n📊 Daily RSI 42-60 + SMA20 | 1H RSI 48-58 + EMA9 Cross + MACD Hijau\n💡 Masuk SEBELUM pump, bukan sesudah\n📈 TP1 tanpa winrate | TP2/SL closing + winrate")
    while True:
        try:
            cek_tp()
            sinyal=analisa()
            if sinyal:
                pos=load()
                for s in sinyal:
                    if s['base'] in pos: continue
                    kirim(f"╔════════════════════════╗\n║ 🚀 EARLY {s['base']}/IDR SEBELUM PUMP ║\n╚════════════════════════╝\n\n🔍 *DETEKSI AWAL*\n📈 Baru Naik: +{s['naik']:.2f}% dari Low\n💧 Low: Rp {s['low']:,.0f} | High: Rp {s['high']:,.0f} (masih jauh -10%)\n💰 Vol: Rp {s['vol']/1e9:.2f} M\n\n┏━ 📊 2 TIMEFRAME ━┓\n┃ Daily RSI: {s['rsi_d']:.1f} (42-60 sehat)\n┃ 1H RSI: {s['rsi_1h']:.1f} (48-58 baru cross 50)\n┃ 1H EMA9: {s['ema9_1h']:,.0f} > EMA21: {s['ema21_1h']:,.0f} (baru golden cross)\n┃ 1H Candle: Rp {s['open_1h']:,.0f} -> Rp {s['close_1h']:,.0f} 🟢\n┃ MACD 1H: BARU HIJAU\n┗━━━━━━━━━━━━━━━┛\n\n┏━ 🎯 ENTRY AWAL ━┓\n┃ 🟢 ENTRY: Rp {s['entry']:,.0f}\n┃ 🎯 TP1: Rp {s['tp1']:,.0f} (+5%)\n┃ 🏆 TP2: Rp {s['tp2']:,.0f} (+10%)\n┃ 🛑 SL: Rp {s['sl']:,.0f} (-5%)\n┗━━━━━━━━━━━━━━━┛\n\n⚡ *MASUK SEKARANG SEBELUM JADI TOP GAINER!*")
                    pos[s['base']]={'entry':s['entry']}; save(pos)
            time.sleep(50)
        except Exception as e:
            print(e); time.sleep(20)

if __name__=="__main__":
    main()
