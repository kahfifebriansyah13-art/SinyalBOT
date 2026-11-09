import requests, os, time, json
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def kirim(pesan):
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", data={"chat_id": CHAT_ID, "text": pesan, "parse_mode": "Markdown"}, timeout=15)
    except Exception as e: print(e)

def get_tickers():
    try: return requests.get("https://indodax.com/api/tickers", timeout=15).json()['tickers']
    except: return {}

def get_tv_debug(symbol):
    try:
        from tradingview_ta import TA_Handler, Interval
        handler = TA_Handler(symbol=symbol, screener="indonesia", exchange="INDODAX", interval=Interval.INTERVAL_1_HOUR)
        a = handler.get_analysis()
        return a.indicators, a.summary, "OK"
    except Exception as e:
        return None, None, str(e)[:100]

def main():
    kirim("🔍 *MODE DEBUG TRADINGVIEW AKTIF*\nAku akan cek kenapa gak ada sinyal...")
    while True:
        try:
            tickers = get_tickers()
            if not tickers:
                kirim("❌ Gagal ambil ticker Indodax"); time.sleep(60); continue
            
            total = len([k for k in tickers if k.endswith('_idr')])
            debug_log = []
            hasil = []
            
            count = 0
            for pair,d in tickers.items():
                if not pair.endswith('_idr'): continue
                if count > 20: break # Cek 20 koin aja biar cepat
                base=pair.split('_')[0].upper()
                vol=float(d['vol_idr'])
                if vol < 500000000: continue
                
                tv_symbol=f"{base}IDR"
                ind, summ, status = get_tv_debug(tv_symbol)
                count+=1
                
                if not ind:
                    debug_log.append(f"{base}: TV Error {status}")
                    continue
                
                rsi=ind.get('RSI',0)
                ema9=ind.get('EMA9',0)
                ema20=ind.get('EMA20',0)
                rekom=summ.get('RECOMMENDATION','NEUTRAL')
                
                alasan = []
                if rsi < 35 or rsi > 78: alasan.append(f"RSI {rsi:.1f}")
                if ema9 <= ema20: alasan.append(f"EMA9 {ema9:.0f} <= EMA20 {ema20:.0f}")
                if "BUY" not in rekom: alasan.append(f"Rekom {rekom}")
                
                if not alasan:
                    hasil.append(base)
                else:
                    debug_log.append(f"{base}: Gagal karena {', '.join(alasan)} | RSI {rsi:.1f} Rekom {rekom}")
                
                time.sleep(1)

            if hasil:
                kirim(f"✅ *DAPAT SINYAL DEBUG:* {', '.join(hasil)}")
            else:
                # JAMINAN DAPAT SINYAL - AMBIL 3 KOIN VOLUME TERBESAR NAIK HARI INI
                sorted_by_vol = sorted([(k,v) for k,v in tickers.items() if k.endswith('_idr')], key=lambda x: float(x[1]['vol_idr']), reverse=True)[:5]
                top = []
                for pair,v in sorted_by_vol:
                    last=float(v['last']); low=float(v['low'])
                    naik = ((last-low)/low*100) if low>0 else 0
                    if naik > 0.5:
                        top.append(f"{pair.split('_')[0].upper()} +{naik:.2f}% Vol {float(v['vol_idr'])/1e9:.1f}M")
                
                pesan_debug = "\n".join(debug_log[:10])
                kirim(f"📉 *DEBUG 20 KOIN:*\n{pesan_debug}\n\n⚠️ *Filter Medium TV terlalu ketat, jadi gak ada lolos*\n\n🔥 *TOP VOLUME HARI INI (JAMINAN SINYAL):*\n" + "\n".join(top) + "\n\nSaran: Ketik 'ganti agresif' biar lolos lebih banyak.")
            
            time.sleep(120)
        except Exception as e:
            kirim(f"Error debug: {e}"); time.sleep(60)

if __name__=="__main__":
    main()
