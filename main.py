import time
import json
import os
import sys
from pathlib import Path
from datetime import datetime

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from config import (
    POLL_INTERVAL,
    DEFAULT_WATCHLIST,
    SEEN_FILE,
    TEMP_DIR,
    APP_TITLE
)
from exchange_client import (
    fetch_latest_announcements,
    is_in_watchlist,
    download_attachment
)
from ai_engine import analyze_document
from telegram_client import send_telegram_alert

def load_seen_ids() -> set:
    if SEEN_FILE.exists():
        try:
            with open(SEEN_FILE, "r") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_seen_ids(seen_ids: set):
    try:
        items = list(seen_ids)[-1000:]
        with open(SEEN_FILE, "w") as f:
            json.dump(items, f, indent=2)
    except Exception as e:
        print(f"[Storage Error] Failed to save seen announcements: {e}")

def process_cycle(seen_ids: set):
    announcements = fetch_latest_announcements()
    if not announcements:
        return

    for item in announcements:
        news_id = item["id"]
        if not news_id or news_id in seen_ids:
            continue

        symbol = item["symbol"]
        company = item["company_name"]
        headline = item["subject"]
        details = item["details"]
        pdf_url = item["pdf_url"]
        announced_at = item["timestamp"]

        # Check against watchlist
        if not is_in_watchlist(symbol, company, DEFAULT_WATCHLIST):
            seen_ids.add(news_id)
            continue

        print(f"\n🔔 [MATCH FOUND] [{symbol}] {company}: {headline}")

        seen_ids.add(news_id)
        save_seen_ids(seen_ids)

        pdf_path = None
        if pdf_url:
            print(f"📥 Downloading PDF from: {pdf_url}...")
            pdf_path = download_attachment(pdf_url, filename_hint=f"{symbol}_filing.pdf")

        # AI Analysis
        ai_summary = ""
        if pdf_path and pdf_path.exists():
            print("🤖 Analyzing document with Google Gemini Flash...")
            ai_summary = analyze_document(pdf_path, f"{company} ({symbol})", headline)
            try:
                pdf_path.unlink(missing_ok=True)
            except Exception:
                pass
        else:
            ai_summary = f"*{details or 'No attachment provided'}*"

        # Format Telegram Message
        message_lines = [
            f"⚡ *{APP_TITLE}: {symbol}*",
            f"🏢 *{company}*",
            f"📋 *Subject:* {headline}",
            f"🕒 _{announced_at}_",
            "",
            "───────────────────",
            ai_summary,
            "───────────────────"
        ]

        if pdf_url:
            message_lines.append(f"📄 [Open Original Exchange Filing]({pdf_url})")

        full_message = "\n".join(message_lines)
        print("📤 Sending alert to Telegram...")
        send_telegram_alert(full_message)

def main():
    print("=" * 60)
    print("🚀 Stock AI Announcement Notifier (EquiSense Alternative)")
    print(f"📡 Watchlist: {', '.join(DEFAULT_WATCHLIST)}")
    print(f"⏱️ Poll Interval: {POLL_INTERVAL} seconds")
    print("=" * 60)

    seen_ids = load_seen_ids()
    print(f"Loaded {len(seen_ids)} previously processed announcements.")

    while True:
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Checking Exchange for new announcements...")
            process_cycle(seen_ids)
        except Exception as e:
            print(f"[Main Error] Unexpected error in polling cycle: {e}")

        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Stopped by user. Exiting cleanly.")
