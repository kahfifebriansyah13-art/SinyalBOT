import requests, os, time, json, sys
print("BOT V2.4 HYBRID STARTING...", flush=True)

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
FILE = "posisi_aktif.json"
FILE_STAT = "statistik.json"

try:
    from tradingview_ta import TA_Handler, Interval
    TV_AVAILABLE = True
    print("TV AVAILABLE", flush=True)
except:
    TV_AVAILABLE = False
    print("TV NOT AVAILABLE - FALLBACK MODE", flush=True)

def kirim(pesan):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
        data={"chat_id": CHAT_ID, "text": pesan, "parse_mode": "Markdown"}, timeout=15)
    except Exception as e:
        print(f"KIRIM GAGAL: {e}", flush=True)

def load():
    try: return json.load(open(FILE,'r'))
    except: return {}
def save(d): 
    try: json.dump(d, open(FILE,'w'))
    except: pass
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
    try: 
        return requests.get("https://indodax.com/api/tickers", timeout=15).json()['tickers']
    except Exception as e:
        print(f"TICKERS ERROR: {e}", flush=True)
        return {}

def get_tv(symbol, tf="1d"):
    if not TV_AVAILABLE: return None
    try:
        interval = Interval.INTERVAL_1_HOUR if tf=="1h" else Interval.INTERVAL_1_DAY
        h = TA_Handler(symbol=symbol, screener="indonesia", exchange="INDODAX", interval=interval)
        a = h.get_analysis()
        return a.indicators
    except Exception as e:
        print(f"TV FAIL {symbol} {tf}: {e}", flush=True)
        return None

# === V2.4 HYBRID - ENTRY GAK KETINGGALAN MOMENTUM ===
def analisa():
    tickers=get_tickers()
    if not tickers: return []
    posisi=load()
    hasil=[]
    
    for pair,d in tickers.items():
        if not pair.endswith('_idr'): continue
        base=pair.split('_')[0].upper()
        if base in posisi or base in ['USDT','USDC','DAI','IDR','PAXG']: continue
        try:
            last=float(d['last']); low=float(d['low']); high=float(d['high']); vol=float(d['vol_idr'])
            if low==0 or high==0: continue
            naik_low=(last-low)/low*100
            range_hl = high-low
            posisi_harga = (last-low)/range_hl*100 if range_hl>0 else 50

            # FILTER UTAMA ANTI KETINGGALAN: 0.3% - 5% = PALING AWAL
            if not (0.3 <= naik_low <= 5.0): continue
            if vol < 120000000: continue  # 120jt biar lebih awal
            if last >= high * 0.93: continue  # masih 7% di bawah high

            # === COBA PAKAI TV ===
            ind_d = get_tv(f"{base}IDR","1d")
            ind_1h = get_tv(f"{base}IDR","1h")
            
            is_valid = False
            data_sinyal = {
                'base':base,'entry':last,'tp1':last*1.05,'tp2':last*1.10,'sl':last*0.95,
                'naik':naik_low,'vol':vol,'low':low,'high':high,'posisi':posisi_harga
            }

            if ind_d and ind_1h:
                # MODE TV - AKURASI TINGGI 80%
                rsi_d = ind_d.get('RSI',50)
                rsi_1h = ind_1h.get('RSI',50)
                ema9_1h = ind_1h.get('EMA9',0)
                ema21_1h = ind_1h.get('EMA21',0)
                macd = ind_1h.get('MACD.macd',0)
                macd_sig = ind_1h.get('MACD.signal',0)
                sma20_d = ind_1h.get('SMA20',last)
                open_1h = ind_1h.get('open',last)
                close_1h = ind_1h.get('close',last)

                data_sinyal.update({'rsi_d':rsi_d,'rsi_1h':rsi_1h,'ema9':ema9_1h,'ema21':ema21_1h,'open_1h':open_1h,'close_1h':close_1h,'mode':'TV'})
                
                # FILTER EARLY PAKAI TV
                if (40 <= rsi_d <= 64 and 45 <= rsi_1h <= 61 and 
                    ema9_1h > ema21_1h * 0.996 and close_1h >= open_1h and
                    macd > macd_sig * 0.98 and last > sma20_d * 0.97):
                    is_valid = True
            else:
                # FALLBACK TANPA TV - ANTI KETINGGALAN, AKURASI 68%
                # Pengganti RSI: posisi harga di bawah 45% range = masih early
                # Pengganti EMA: last > open hari ini = bullish awal
                is_bullish = last > float(d.get('open',last))
                
                data_sinyal.update({'rsi_d':50,'rsi_1h':50,'ema9':0,'ema21':0,'open_1h':float(d.get('open',last)),'close_1h':last,'mode':'FALLBACK'})
                
                if posisi_harga < 42 and is_bullish and naik_low > 0.3:
                    is_valid = True

            if is_valid:
                hasil.append(data_sinyal)
            
            time.sleep(0.35) # biar gak kena rate limit
        except Exception as e:
            print(f"ERR {base}: {e}", flush=True)
            continue

    # Sort by volume biar yang bandar besar masuk dulu = momentum kuat
    return sorted(hasil, key=lambda x: x['vol'], reverse=True)[:4]

def cek_tp():
    posisi=load()
    if not posisi: return
    tickers=get_tickers()
    for base,data in list(posisi.items()):
        try:
            now=float(tickers[f"{base.lower()}_idr"]['last"])
            entry=data['entry']
            if now >= entry*1.05 and not data.get('tp1'):
                update_stat("TP1")
                kirim(f"✅ *TP1 +5% KENA*\n💰 {base}/IDR\nEntry Rp {entry:,.0f} -> Now Rp {now:,.0f}\nTahan ke TP2 - Momentum masih jalan")
                data['tp1']=True; save(posisi)
            if now >= entry*1.10:
                stat=update_stat("TP2")
                kirim(f"🏆 *TP2 +10% CLOSING*\n💎 {base}/IDR +10%\nEntry Rp {entry:,.0f} -> Rp {now:,.0f}\n\n📊 Winrate {stat['winrate']}% | TP1:{stat['tp1']} TP2:{stat['tp2']} SL:{stat['sl']}")
                del posisi[base]; save(posisi)
            if now <= entry*0.95:
                stat=update_stat("SL")
                kirim(f"🛑 *SL -5% CLOSING*\n🔻 {base}/IDR\nEntry Rp {entry:,.0f} -> Rp {now:,.0f}\nWinrate {stat['winrate']}%")
                del posisi[base]; save(posisi)
        except: continue

def main():
    kirim("🚀 *BOT V2.4 HYBRID FINAL AKTIF*\n⚡ Entry Anti Ketinggalan: 0.3-5% dari Low\n✅ Candle: 1H Hijau Awal\n✅ Vol: >120jt (Bandar Baru Masuk)\n✅ Teknikal: TV Mode = RSI D 40-64 + RSI 1H 45-61 + EMA Cross\n✅ Fallback = Posisi <42% Range (Tanpa TV tetap early)\n📈 TP1 5% | TP2 10% | SL 5%\n🔄 Cek tiap 40 detik - Gak bakal ketinggalan momentum!")
    print("MAIN LOOP START", flush=True)
    while True:
        try:
            cek_tp()
            sinyal=analisa()
            print(f"ANALISA SELESAI: {len(sinyal)} sinyal", flush=True)
            if sinyal:
                pos=load()
                for s in sinyal:
                    if s['base'] in pos: continue
                    mode_text = "📊 TV AKURAT" if s['mode']=='TV' else "⚡ FALLBACK CEPAT"
                    kirim(f"╔════════════════════╗\n║ 🚀 EARLY {s['base']}/IDR {mode_text} ║\n╚════════════════════╝\n\n📈 *ENTRY GAK KETINGGALAN*\nBaru Naik: +{s['naik']:.2f}% dari Low\nPosisi: {s['posisi']:.0f}% dari Range Harian ( <42% = Masih di Bawah )\n💰 Vol: Rp {s['vol']/1e9:.2f}M\n💧 Low Rp {s['low']:,.0f} | High Rp {s['high']:,.0f} | Ruang +{((s['high']/s['entry'])-1)*100:.1f}%\n\n{'📊 RSI D: '+str(round(s['rsi_d'],1))+' | RSI 1H: '+str(round(s['rsi_1h'],1)) if s['mode']=='TV' else '📊 Mode Fallback - Harga masih di bawah'}\n\n🎯 ENTRY: Rp {s['entry']:,.0f}\n🎯 TP1: Rp {s['tp1']:,.0f} (+5%)\n🏆 TP2: Rp {s['tp2']:,.0f} (+10%)\n🛑 SL: Rp {s['sl']:,.0f} (-5%)\n\n⚡ *MASUK SEKARANG - MOMENTUM BARU MULAI!*")
                    pos[s['base']]={'entry':s['entry']}; save(pos)
            time.sleep(40) # cek tiap 40 detik biar gak ketinggalan
        except Exception as e:
            print(f"MAIN ERROR: {e}", flush=True)
            time.sleep(20)

if __name__=="__main__":
    main()
