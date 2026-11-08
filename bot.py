 import requests
import pandas as pd
import time
import os
from datetime import datetime

# Ambil dari Variables di Railway (lebih aman)
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Setting coin - bisa multi coin
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"] 
INTERVAL = "15m"

def send_telegram(msg):
    if not BOT_TOKEN or not CHAT_ID:
        print("BOT_TOKEN / CHAT_ID belum di-set!")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"Gagal kirim: {e}")

def hitung_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def cek_symbol(symbol):
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={INTERVAL}&limit=100"
        resp = requests.get(url, timeout=10).json()
        df = pd.DataFrame(resp, columns=['t','o','h','l','c','v','a','b','c','d','e','f'])
        df['c'] = df['c'].astype(float)
        df['v'] = df['v'].astype(float)
        df['MA20'] = df['c'].rolling(20).mean()
        df['MA50'] = df['c'].rolling(50).mean()
        df['RSI'] = hitung_rsi(df['c'])
        df['VAVG'] = df['v'].rolling(20).mean()

        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        cross_up = prev['MA20'] <= prev['MA50'] and last['MA20'] > last['MA50']
        cross_down = prev['MA20'] >= prev['MA50'] and last['MA20'] < last['MA50']
        vol_spike = last['v'] > last['VAVG'] * 1.5

        print(f"[{datetime.now().strftime('%H:%M')}] {symbol}: {last['c']} | RSI:{last['RSI']:.1f}")

        if cross_up and 30 < last['RSI'] < 58 and vol_spike:
            send_telegram(f"🚀 *BUY KUAT {symbol}*\nHarga: `{last['c']}`\nRSI: {last['RSI']:.1f}\nMA20 Cross UP MA50\nVol: TINGGI\nTF: {INTERVAL}")
        elif cross_down and 42 < last['RSI'] < 70:
            send_telegram(f"🔻 *SELL {symbol}*\nHarga: `{last['c']}`\nRSI: {last['RSI']:.1f}\nMA20 Cross DOWN\nTF: {INTERVAL}")

    except Exception as e:
        print(f"Error {symbol}: {e}")

# START
print("Bot Railway AKTIF")
send_telegram(f"✅ Bot Railway AKTIF\nCoin: {', '.join(SYMBOLS)}\nIndikator: RSI + MA20/50 + Volume\nTF: {INTERVAL}")

while True:
    for sym in SYMBOLS:
        cek_symbol(sym)
        time.sleep(2) # jeda biar gak kena limit Binance
    time.sleep(900) # cek tiap 15 menit
