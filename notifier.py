import requests
import json
import config

def send_telegram_alert(message: str):
    """Gửi thông báo định dạng Markdown qua Telegram"""
    token = config.TELEGRAM_BOT_TOKEN
    chat_id = config.TELEGRAM_CHAT_ID
    
    if not token or token == "YOUR_TELEGRAM_BOT_TOKEN" or not chat_id:
        # In ra màn hình console nếu chưa điền token
        print("\n[TELEGRAM PREVIEW]:")
        print(message)
        print("-" * 50)
        return
        
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if not resp.json().get("ok"):
            print(f"Telegram API Error: {resp.text}")
    except Exception as e:
        print(f"Lỗi gửi Telegram: {e}")
