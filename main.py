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
from fno_service import NSE_FNO_SYMBOLS, get_historical_earnings_moves, get_fno_strike_setup

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

        # Check if matched with user watchlist OR if it's an F&O stock result
        is_matched = is_in_watchlist(symbol, company, DEFAULT_WATCHLIST)
        is_fno = symbol.strip().upper() in NSE_FNO_SYMBOLS
        is_fno_result = is_fno and any(w in headline.lower() for w in [
            "financial result", "financial results", "outcome of board meeting",
            "un-audited", "unaudited", "audited financial", "quarterly result", "dividend",
            "board meeting outcome"
        ])

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

        # Send Telegram alert if matched to watchlist OR if an F&O stock result/action
        if is_matched or is_fno_result:
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

            # If F&O stock, append quantitative options trade decision & volatility setup
            if is_fno:
                try:
                    vol = get_historical_earnings_moves(symbol) or {}
                    setup = get_fno_strike_setup(current_price, vol, symbol, tech) or {}
                    dec_tag = setup.get("decision_tag", "NEUTRAL")
                    dec_badge = setup.get("decision_badge", "🟡 NEUTRAL")
                    dec_action = setup.get("decision_action", "")
                    edge_x = setup.get("edge_ratio", 1.0)
                    be_pct = setup.get("breakeven_pct", 2.5)
                    serial_str = f" • {setup.get('serial_badge')}" if setup.get('is_serial_mover') else ""

                    mis = setup.get("mispricing_meter", {})
                    mis_badge = mis.get("badge", "FAIR VALUE")
                    mis_ratio = mis.get("ratio", 1.0)
                    mis_expected = mis.get("market_expected_move_pct", be_pct)
                    mis_realized = mis.get("historical_realized_move_pct", vol.get("avg_abs_move", 2.0))

                    pcr_data = setup.get("institutional_pcr", {})
                    pcr_badge = pcr_data.get("badge", "1.00 (Neutral)")
                    floor_st = pcr_data.get("floor_strike", 0)
                    ceil_st = pcr_data.get("ceiling_strike", 0)
                    corridor = pcr_data.get("expected_corridor", "")
                    iv_data = setup.get("iv_analytics", {})

                    message_lines.extend([
                        "🎯 *2. QUANTITATIVE OPTIONS RADAR (TRADE DECISION):*",
                        f"🚦 *Trade Signal*: [{dec_badge}]{serial_str}",
                        f"• 📉 *IV & IVBP*: *IV {iv_data.get('iv_pct', 30.0)}%* (HV30 {iv_data.get('hv30_pct', 25.0)}%) | *IVP {iv_data.get('ivp_pct', 50)}%* | *IVBP ±{iv_data.get('ivbp_pct', be_pct)}%*",
                        f"• 🏛️ Institutional PCR: *{pcr_badge}*",
                        f"• 🛡️ Smart Money Floor: *₹{floor_st:,.0f}* (Max Put OI — Won't drop below)",
                        f"• 🧱 Smart Money Ceiling: *₹{ceil_st:,.0f}* (Max Call OI — Won't cross above)",
                        f"• 📍 Institutional Corridor: *{corridor}* (Max Pain: *₹{pcr_data.get('max_pain_strike', 0):,.0f}*)",
                        f"• 💎 Volatility Pricing: *{mis_badge}* (Ratio: *{mis_ratio}x*)",
                        f"• 📊 Straddle Expectation: *±{mis_expected}%* vs Realized Swing: *±{mis_realized}%*",
                        f"• Volatility Edge: *{edge_x}x {'Positive' if edge_x >= 1.0 else 'Negative'} Edge* (Avg Swing ±{vol.get('avg_abs_move', 2.0)}% vs Req ±{be_pct}%)",
                        f"• 💡 Action: {dec_action}"
                    ])

                    if dec_tag != "SKIP" and setup.get("strikes_label"):
                        lbc = setup.get("live_broker_check", {})
                        message_lines.extend([
                            f"• Setup: *{setup.get('strikes_label')}* ({setup.get('strategy')})",
                            f"• 🧮 *15-Sec Broker Check*: TAKE if live CE+PE ≤ *₹{lbc.get('safe_edge_prem', 0)}* | SKIP if > *₹{lbc.get('max_parity_prem', 0)}*",
                            f"• ⏰ Filing Habit (5Q Verified): *{setup.get('typical_filing_time')}* ({setup.get('timing_consistency_label')})",
                            f"• 📅 5Q Filing Tape: _{setup.get('q_filing_summary')}_",
                            f"• 🛒 *Optimal Buy Time*: *{setup.get('optimal_buy_window')}*",
                            f"• Capital / Lot: *~₹{setup.get('capital_required', 0):,}* (Lot {setup.get('lot_size', 0)})",
                            f"• Target (+60%): *+₹{setup.get('target_profit_amount', 0):,}* | SL (-35%): *-₹{setup.get('stop_loss_amount', 0):,}*",
                            f"• Timing Rule: _{setup.get('timing_rule')}_"
                        ])
                    message_lines.append("")
                except Exception as e:
                    print(f"[FNO Alert Warning] Error computing F&O strike setup for {symbol}: {e}")

            if tech:
                message_lines.extend([
                    "📈 *3. TECHNICAL SETUP:*",
                    f"• RSI (14): *{rsi_val}* ({rsi_badge})",
                    f"• Key Support (S1): ₹{s1:,.2f} | Resistance (R1): ₹{r1:,.2f}",
                    "",
                    "🏦 *4. SMART MONEY INSIGHT:*",
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
    print(f"🚀 {APP_TITLE}")
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
