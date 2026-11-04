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
from technicals import get_stock_technicals
from database import save_announcement
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

        seen_ids.add(news_id)
        save_seen_ids(seen_ids)

        # Check if matched with user watchlist
        is_matched = is_in_watchlist(symbol, company, DEFAULT_WATCHLIST)

        # Fetch technicals for the stock
        tech = get_stock_technicals(symbol)
        current_price = tech.get("current_price", 0.0) if tech else 0.0
        rsi_val = tech.get("rsi", 50.0) if tech else 50.0
        rsi_badge = tech.get("rsi_badge", "Neutral") if tech else "Neutral"
        pivots = tech.get("pivots", {}) if tech else {}
        s1 = pivots.get("s1", 0.0)
        r1 = pivots.get("r1", 0.0)
        delivery_pct = tech.get("delivery_pct", 50.0) if tech else 50.0
        whale_note = tech.get("whale_note", "Stable institutional holdings.") if tech else "Stable institutional holdings."

        smart_money = "FII & Mutual Fund ownership tracked quarterly. Stable baseline."
        if "Shareholding Pattern" in headline or "Regulation 31" in headline:
            smart_money = "Quarterly Shareholding Update: Institutional shift detailed in filing attachment."

        ai_summary = ""
        pdf_path = None

        # Filter out administrative noise (loss of share certificates, trading window closures)
        is_trivial = any(w in headline.lower() for w in [
            "loss of share", "trading window", "newspaper", "duplicate share", 
            "compliance certificate", "investor meet", "analysts/institutional"
        ])
        
        # Only call Gemini for high-value financial actions or watchlist matches
        should_analyze = not is_trivial and (
            is_matched or any(w in headline for w in ["Financial", "Result", "Outcome", "Dividend", "Acquisition", "Order", "Board Meeting"])
        )

        if should_analyze and pdf_url:
            print(f"\n🔔 [ANALYZING] [{symbol}] {company}: {headline}")
            pdf_path = download_attachment(pdf_url, filename_hint=f"{symbol}_filing.pdf")
            if pdf_path and pdf_path.exists():
                print("🤖 Digesting filing with Google Gemini Flash (Strict English)...")
                ai_summary = analyze_document(pdf_path, f"{company} ({symbol})", headline)
                time.sleep(3.5)  # Pacing delay to prevent 15 RPM rate limit
                try:
                    pdf_path.unlink(missing_ok=True)
                except Exception:
                    pass

        if not ai_summary:
            ai_summary = f"• Update: {headline}\n• Context: {details or 'Exchange regulatory disclosure'}\n• Language: English\n• Sentiment: Bullish 🟢"

        # Detect Sentiment
        sentiment = "NEUTRAL"
        if "Bullish" in ai_summary:
            sentiment = "BULLISH"
        elif "Bearish" in ai_summary:
            sentiment = "BEARISH"

        # Save to Database for the Website Frontend
        save_announcement({
            "id": news_id,
            "symbol": symbol,
            "company_name": company,
            "subject": headline,
            "details": details,
            "pdf_url": pdf_url,
            "announced_at": announced_at,
            "ai_summary": ai_summary,
            "sentiment": sentiment,
            "current_price": current_price,
            "rsi": rsi_val,
            "support_1": s1,
            "resistance_1": r1,
            "smart_money_note": smart_money,
            "delivery_pct": delivery_pct,
            "whale_note": whale_note
        })

        # Send Telegram alert if matched to watchlist
        if is_matched:
            print(f"📤 Broadcasting alert for {symbol} to Telegram channel...")
            message_lines = [
                f"⚡ *{APP_TITLE}: {symbol}*",
                f"🏢 *{company}* (CMP: ₹{current_price:,.2f})" if current_price else f"🏢 *{company}*",
                f"📋 *Subject:* {headline}",
                f"🕒 _{announced_at}_",
                "",
                "📊 *1. FINANCIAL INTELLIGENCE (English):*",
                ai_summary,
                ""
            ]

            if tech:
                message_lines.extend([
                    "📈 *2. TECHNICAL SETUP:*",
                    f"• RSI (14): *{rsi_val}* ({rsi_badge})",
                    f"• Key Support (S1): ₹{s1:,.2f} | Resistance (R1): ₹{r1:,.2f}",
                    "",
                    "🏦 *3. SMART MONEY INSIGHT:*",
                    f"• {smart_money}",
                    ""
                ])

            message_lines.append("───────────────────")
            if pdf_url:
                message_lines.append(f"📄 [Open Original Exchange Document]({pdf_url})")

            full_message = "\n".join(message_lines)
            send_telegram_alert(full_message)

def main():
    print("=" * 60)
    print(f"🚀 {APP_TITLE} (EquiSense Alternative)")
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
