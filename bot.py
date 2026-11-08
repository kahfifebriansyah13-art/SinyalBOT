import requests
import time
import os
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def kirim_pesan(pesan):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": pesan, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=data, timeout=15)
    except Exception as e:
        print(e)

def get_indodax_tickers():
    try:
        r = requests.get("https://indodax.com/api/tickers", timeout=15).json()
        return r['tickers']
    except Exception as e:
        print(f"Error Indodax: {e}")
        return {}

def analisa_potensi():
    tickers = get_indodax_tickers()
    potensi = []
    
    blacklist = ['usdt_idr', 'usdc_idr', 'dai_idr'] # jangan scan stablecoin
    
    for pair, data in tickers.items():
        if not pair.endswith('_idr'):
            continue
        if pair in blacklist:
            continue
        
        try:
            last = float(data['last'])
            low = float(data['low'])
            high = float(data['high'])
            vol_idr = float(data['vol_idr'])
            
            if vol_idr < 1000000000: # minimal volume 1 Miliar IDR biar gak koin mati
                continue
            if last == 0 or low == 0:
                continue

            # Rumus potensi: harga masih dekat dengan low 24jam + volume gede = mau naik
            jarak_dari_low = ((last - low) / low) * 100
            jarak_ke_high = ((high - last) / last) * 100
            
            # Koin bagus: masih dekat low ( < 15% ) tapi jarak ke high masih jauh ( > 10% )
            if jarak_dari_low < 15 and jarak_ke_high > 10:
                potensi.append({
                    'pair': pair.upper().replace('_IDR',''),
                    'price': last,
                    'vol': vol_idr,
                    'dari_low': round(jarak_dari_low, 2),
                    'ke_high': round(jarak_ke_high, 2),
                    'score': jarak_ke_high - jarak_dari_low
                })
        except:
            continue
    
    # Urutkan yang paling potensial
    potensi_sorted = sorted(potensi, key=lambda x: x['score'], reverse=True)
    return potensi_sorted[:3] # ambil 3 terbaik

def main():
    kirim_pesan("🔥 *SCANNER INDODAX AKTIF*\nMencari koin potensi NAIK...\nInterval: 10 menit")
    
    while True:
        try:
            hasil = analisa_potensi()
            
            if not hasil:
                kirim_pesan(f"⏳ {datetime.now().strftime('%H:%M')} - Belum ada koin potensial, market lagi sepi.")
            else:
                pesan = f"🚀 *SINYAL BUY INDODAX* {datetime.now().strftime('%H:%M WIB')}\n\n"
                for i, koin in enumerate(hasil, 1):
                    pesan += f"{i}. *{koin['pair']}/IDR*\n"
                    pesan += f"   Harga: Rp {koin['price']:,.0f}\n"
                    pesan += f"   Volume: Rp {koin['vol']/1000000000:.1f} M\n"
                    pesan += f"   Posisi: +{koin['dari_low']}% dari Low, masih bisa naik {koin['ke_high']}%\n"
                    pesan += f"   👉 *POTENSI BUY*\n\n"
                
                pesan += "_DYOR - Bukan ajakan keuangan_"
                kirim_pesan(pesan)
            
            time.sleep(600) # scan tiap 10 menit
        except Exception as e:
            print(e)
            time.sleep(30)

if __name__ == "__main__":
    main()
