import requests
import time
import os
from datetime import datetime

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def kirim_pesan(pesan):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": pesan}
    try:
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print(e)

def main():
    kirim_pesan("Bot AKTIF - Sudah Fix")
    while True:
        try:
            print("Bot jalan", datetime.now())
            time.sleep(60)
        except Exception as e:
            print(e)
            time.sleep(10)

if __name__ == "__main__":
    main()
