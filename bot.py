import requests
import pandas as pd
import time
import os
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def kirim_pesan(pesan):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": pesan, "parse_mode": "Markdown"}
    try:
        requests.post(url, data=data, timeout=10)
    except:
        pass

def main():
    kirim_pesan("✅ Bot Sinyal AKTIF 24 Jam di Railway!")
    while True:
        try:
            now = datetime.now().strftime("%H:%M:%S")
            print(f"Bot jalan {now}")
            time.sleep(60)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()
