import requests
import urllib3
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

def send_telegram_alert(message: str) -> bool:
    """
    Sends a formatted alert to your personal Telegram chat or channel.
    Handles long messages and Markdown fallbacks.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[Telegram] Bot Token or Chat ID is missing in .env.")
        return False

    max_length = 4000
    chunks = [message[i:i + max_length] for i in range(0, len(message), max_length)]

    success = True
    for chunk in chunks:
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": chunk,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False
        }

        try:
            res = requests.post(TELEGRAM_API_URL, json=payload, timeout=15, verify=False)
            data = res.json()
            
            # If Markdown parsing fails due to unescaped characters, retry as plain text
            if not data.get("ok"):
                payload.pop("parse_mode", None)
                res = requests.post(TELEGRAM_API_URL, json=payload, timeout=15, verify=False)
                data = res.json()

            if not data.get("ok"):
                print(f"[Telegram Error] {data.get('description')}")
                success = False
        except Exception as e:
            print(f"[Telegram Client] Request failed: {e}")
            success = False

    return success

