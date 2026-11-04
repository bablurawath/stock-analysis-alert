import sys
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from pathlib import Path
from config import GEMINI_API_KEY, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from exchange_client import fetch_latest_announcements
from telegram_client import send_telegram_alert
from google import genai

def test_feed():
    print("\n[1/3] Testing Live Exchange Announcement Feed...")
    announcements = fetch_latest_announcements()
    if announcements:
        latest = announcements[0]
        print(f"✅ Success! Connected to Exchange Feed.")
        print(f"   Latest filing: [{latest.get('symbol')}] {latest.get('company_name')} - {latest.get('subject')[:50]}...")
        if latest.get('pdf_url'):
            print(f"   PDF Attached: {latest.get('pdf_url')[:60]}...")
        return True
    else:
        print("❌ Failed to fetch announcements. Check your internet connection.")
        return False

def test_telegram():
    print("\n[2/3] Testing Telegram Connection...")
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram credentials not found in .env.")
        print("   Please set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in d:\\wampgc\\www\\stock-ai-notifier\\.env")
        return False

    test_msg = (
        "🎉 *Stock Market Alert Connected!*\n\n"
        "Your AI stock alerting bot is now active.\n"
        "You will receive live corporate result summaries here."
    )
    success = send_telegram_alert(test_msg)
    if success:
        print("✅ Success! Test message sent to your Telegram.")
        return True
    else:
        print("❌ Failed to send Telegram message. Please check your BOT_TOKEN and CHAT_ID.")
        return False

def test_gemini():
    print("\n[3/3] Testing Google Gemini AI...")
    if not GEMINI_API_KEY:
        print("⚠️ GEMINI_API_KEY not found in .env.")
        print("   Please get a free key from https://aistudio.google.com/ and set it in .env")
        return False

    try:
        from ai_engine import generate_with_fallback
        response = generate_with_fallback("Say 'Gemini is ready for financial analysis!' in 1 line.")
        print(f"✅ Success! Gemini replied: {response.text.strip()}")
        return True
    except Exception as e:
        print(f"❌ Gemini connection failed: {e}")
        return False

def main():
    print("=" * 55)
    print("🛠️ Stock AI Notifier - System Diagnostics")
    print("=" * 55)

    feed_ok = test_feed()
    tg_ok = test_telegram()
    gemini_ok = test_gemini()

    print("\n" + "=" * 55)
    print("DIAGNOSTIC SUMMARY:")
    print(f"• Exchange Data Feed: {'✅ OK' if feed_ok else '❌ Failed'}")
    print(f"• Telegram Alerts:    {'✅ OK' if tg_ok else '⚠️ Needs Config'}")
    print(f"• Google Gemini:      {'✅ OK' if gemini_ok else '⚠️ Needs Config'}")
    print("=" * 55)

    if feed_ok and tg_ok and gemini_ok:
        print("\n🚀 Everything is configured! You can now start the bot using:")
        print("   python main.py")
    else:
        print("\n👉 Please fill in your keys in .env, then re-run test_setup.py")

if __name__ == "__main__":
    main()
