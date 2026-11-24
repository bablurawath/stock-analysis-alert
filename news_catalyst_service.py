import time
import requests
import json
import re
import urllib3
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path
from technicals import get_stock_technicals
from telegram_client import send_telegram_alert
from fno_service import NSE_FNO_SYMBOLS, get_fno_lot_size, get_strike_step

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_DIR = Path(__file__).resolve().parent
NEWS_CACHE_FILE = BASE_DIR / "high_impact_news.json"
NEWS_BROADCAST_LOG = BASE_DIR / "news_broadcasts.json"

NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/"
}

# Mapping common company names and media aliases to official NSE F&O symbols
COMPANY_ALIASES = {
    "RELIANCE": "RELIANCE", "TATA MOTORS": "TATAMOTORS", "TATA STEEL": "TATASTEEL", "TCS": "TCS",
    "TATA CONSULTANCY": "TCS", "INFOSYS": "INFY", "HDFC BANK": "HDFCBANK", "ICICI BANK": "ICICIBANK",
    "STATE BANK OF INDIA": "SBIN", "SBI ": "SBIN", "BHARTI AIRTEL": "BHARTIARTL", "AIRTEL": "BHARTIARTL",
    "LARSEN & TOUBRO": "LT", "LARSEN": "LT", "L&T": "LT", "ITC ": "ITC", "AXIS BANK": "AXISBANK",
    "KOTAK": "KOTAKBANK", "MARUTI": "MARUTI", "BAJAJ FINANCE": "BAJFINANCE", "ASIAN PAINTS": "ASIANPAINT",
    "HCL TECH": "HCLTECH", "SUN PHARMA": "SUNPHARMA", "TITAN": "TITAN", "ADANI": "ADANIENT",
    "ADANI ENTERPRISES": "ADANIENT", "ADANI PORTS": "ADANIPORTS", "APL APOLLO": "APLAPOLLO",
    "ZEE ": "ZEEL", "VEDANTA": "VEDL", "WIPRO": "WIPRO", "NTPC": "NTPC", "POWER GRID": "POWERGRID",
    "COAL INDIA": "COALINDIA", "TATA POWER": "TATAPOWER", "BHEL": "BHEL", "SAIL": "SAIL",
    "JINDAL STEEL": "JINDALSTEL", "JSW STEEL": "JSWSTEEL", "HINDALCO": "HINDALCO", "DLF": "DLF",
    "INDUSIND": "INDUSINDBK", "PNB": "PNB", "PUNJAB NATIONAL BANK": "PNB", "BANK OF BARODA": "BANKBARODA",
    "CANARA BANK": "CANBK", "LUPIN": "LUPIN", "DR REDDY": "DRREDDY", "CIPLA": "CIPLA",
    "AUROBINDO": "AUROPHARMA", "BIOCON": "BIOCON", "DIVIS": "DIVISLAB", "PERSISTENT": "PERSISTENT",
    "COFORGE": "COFORGE", "MPHASIS": "MPHASIS", "TECH MAHINDRA": "TECHM", "ZOMATO": "ZOMATO",
    "DIXON": "DIXON", "POLYCAB": "POLYCAB", "VOLTAS": "VOLTAS", "HAVELLS": "HAVELLS", "HAL ": "HAL",
    "BEL ": "BEL", "MAZAGON": "MAZDOCK", "IRCTC": "IRCTC", "RVNL": "RVNL", "IRFC": "IRFC",
    "PAYTM": "PAYTM", "SWIGGY": "SWIGGY", "GRASIM": "GRASIM", "HEROMOTOCO": "HEROMOTOCO",
    "EICHER": "EICHERMOT", "BAJAJ AUTO": "BAJAJ-AUTO", "MUTHOOT": "MUTHOOTFIN", "CHOLAFIN": "CHOLAFIN"
}

# High-impact catalyst trigger keywords
BEARISH_SHOCK_KEYWORDS = [
    # M&A, Dilution & Stake Selloffs
    "acquisition", "stake sale", "dilution", "offer for sale", "ofs at discount",
    "promoter selling", "block deal discount", "business transfer", "merger ratio",
    # Regulatory & Law Enforcement
    "it raid", "income tax raid", "ed search", "enforcement directorate", "cbi",
    "investigation", "fraud", "sfio", "show cause notice", "summons", "penalty",
    "sebi order", "debarred", "forensic audit", "auditor resigned", "resignation of statutory auditor",
    # Pharma & Industrial
    "warning letter", "import alert", "form 483", "oai", "official action indicated",
    "data integrity", "plant shut", "fire incident", "suspension of operations",
    # Debt & Defaults
    "default", "insolvency", "nclt", "rating downgraded", "downgrade to d",
    "contract cancelled", "termination of contract", "loss of order", "profit drops", "loss"
]

BULLISH_RUNNER_KEYWORDS = [
    # Massive Wins & Commercials
    "mega order", "bags order", "contract award", "awarded contract", "l1 bidder",
    "commercial production", "joint venture", "strategic alliance", "raises", "funding", "equity infusion",
    # Corporate Actions & Buybacks
    "buyback at premium", "bonus issue", "special dividend", "demerger value unlocking",
    # Regulatory Clearances
    "usfda eir", "clean clearance", "zero 483", "vld", "inspection closed",
    "pli scheme", "patent grant", "anti-dumping duty", "environmental clearance",
    # Ownership & Rating Upgrades
    "global giant acquiring", "open offer at premium", "rating upgraded", "debt free", "jumps", "surges"
]

def get_ist_now() -> datetime:
    ist = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(ist)

def classify_catalyst(text: str) -> Dict[str, Any]:
    """
    Classifies corporate announcement or news text into:
    - Direction: SEVERE_BEARISH, EXPLOSIVE_BULLISH, MODERATE_BEARISH, MODERATE_BULLISH, or NEUTRAL
    - Impact Severity: CRITICAL, HIGH, MODERATE
    - Trigger keyword & category
    """
    t_lower = text.lower()

    # Check Bearish Shocks first
    matched_bearish = [kw for kw in BEARISH_SHOCK_KEYWORDS if kw in t_lower]
    if matched_bearish:
        kw = matched_bearish[0]
        is_critical = any(k in t_lower for k in [
            "acquisition", "stake sale", "it raid", "ed search", "warning letter",
            "import alert", "auditor resigned", "forensic audit", "insolvency", "nclt", "cbi"
        ])
        severity = "CRITICAL_SHOCK" if is_critical else "HIGH_IMPACT"
        expected_move = "15% to 25%+ Downside Crash" if is_critical else "5% to 10% Gap-Down"

        return {
            "is_catalyst": True,
            "direction": "SEVERE_BEARISH" if is_critical else "MODERATE_BEARISH",
            "direction_label": "🔻 SEVERE BEARISH SHOCK (PUT SURGE RISK)" if is_critical else "⚠️ MODERATE BEARISH SLUMP",
            "severity": severity,
            "severity_badge": "🚨 CRITICAL RISK" if is_critical else "⚠️ BEARISH IMPACT",
            "expected_move": expected_move,
            "trigger_keyword": kw.upper(),
            "option_focus": "PUT (PE) Spikes",
            "sentiment_color": "rose"
        }

    # Check Bullish Runners
    matched_bullish = [kw for kw in BULLISH_RUNNER_KEYWORDS if kw in t_lower]
    if matched_bullish:
        kw = matched_bullish[0]
        is_critical = any(k in t_lower for k in [
            "buyback at premium", "usfda eir", "clean clearance", "global giant", "demerger", "mega order"
        ])
        severity = "CRITICAL_RALLY" if is_critical else "HIGH_IMPACT"
        expected_move = "10% to 20%+ Upside Rally" if is_critical else "4% to 8% Gap-Up"

        return {
            "is_catalyst": True,
            "direction": "EXPLOSIVE_BULLISH" if is_critical else "MODERATE_BULLISH",
            "direction_label": "🚀 EXPLOSIVE BULLISH (CALL RUNNER)" if is_critical else "⚡ BULLISH MOMENTUM",
            "severity": severity,
            "severity_badge": "🔥 EXPLOSIVE RALLY" if is_critical else "⚡ BULLISH IMPACT",
            "expected_move": expected_move,
            "trigger_keyword": kw.upper(),
            "option_focus": "CALL (CE) Runners",
            "sentiment_color": "emerald"
        }

    return {
        "is_catalyst": False,
        "direction": "NEUTRAL",
        "direction_label": "Routine Corporate Update",
        "severity": "NORMAL",
        "severity_badge": "Routine",
        "expected_move": "Within daily ATR (±1.5%)",
        "trigger_keyword": "GENERAL UPDATE",
        "option_focus": "None",
        "sentiment_color": "gray"
    }

def analyze_catalyst_deep(
    symbol: str,
    company_name: str,
    headline: str,
    details: str,
    source: str,
    announced_at: str,
    url: str,
    cmp: float,
    pivots: Dict[str, float],
    rsi: float,
    delivery_pct: float,
    clf: Dict[str, Any],
    is_case_study: bool = False
) -> Dict[str, Any]:
    """
    Synthesizes:
    1. News Summary (Summary-Wise: Key Event, Financial Scope, Strategic Context)
    2. Detailed Sentiment Analysis (Score -10 to +10, Rating, Driver, Institutional Rationale)
    3. How It Can Affect Price (Direction, Projected Target Range, Mechanism, Session Dynamics, Derivatives/Options Impact)
    4. Actionable Options Strike Setup (Primary & Deep OTM strikes, lot size, capital, warnings)
    """
    direction = clf.get("direction", "NEUTRAL")
    kw = clf.get("trigger_keyword", "NEWS")
    is_critical = clf.get("severity") in ["CRITICAL_SHOCK", "CRITICAL_RALLY"]
    s1 = pivots.get("s1", round(cmp * 0.95, 1)) if cmp > 0 else 0.0
    r1 = pivots.get("r1", round(cmp * 1.05, 1)) if cmp > 0 else 0.0

    # 1. News Summary
    # Extract financial amounts if mentioned in text (e.g. ₹15,510 Cr, $300 mn, 26.6%)
    amounts = re.findall(r'(?:₹|\$|Rs\.?|USD)?\s?\d+(?:,\d+)*(?:\.\d+)?\s?(?:crore|cr|million|mn|billion|bn|%)', headline + " " + details, re.IGNORECASE)
    fin_scope = ", ".join(amounts[:2]) if amounts else "Detailed in official corporate disclosure"

    clean_headline = headline.replace("Share Price Highlights:", "").replace("Share Price Live Updates:", "").strip()

    if direction in ["SEVERE_BEARISH", "MODERATE_BEARISH"]:
        summary_points = {
            "key_event": f"Adverse catalyst reported: {clean_headline[:140]}.",
            "financial_quantum": f"Financial scope / quantum involved: {fin_scope}.",
            "strategic_context": f"Potential risk to operating cash flows, corporate governance overhang, or earnings re-rating."
        }
    elif direction in ["EXPLOSIVE_BULLISH", "MODERATE_BULLISH"]:
        summary_points = {
            "key_event": f"Positive market trigger: {clean_headline[:140]}.",
            "financial_quantum": f"Commercial value / capital addition: {fin_scope}.",
            "strategic_context": f"Order pipeline accretion, balance sheet de-leveraging, or institutional accumulation catalyst."
        }
    else:
        summary_points = {
            "key_event": f"Corporate announcement: {clean_headline[:140]}.",
            "financial_quantum": f"Quantum: {fin_scope}.",
            "strategic_context": "Routine exchange disclosure within standard operating parameters."
        }

    # 2. Detailed Sentiment Analysis
    if direction == "SEVERE_BEARISH":
        score = -9
        rating = "🔻 SEVERELY BEARISH (-9/10)"
        driver = f"Regulatory / Dilution Shock ({kw})"
        rationale = (
            "Institutional risk models trigger automatic derating on regulatory enforcement, forensic audits, "
            "or large equity dilutions at discounts. Massive supply overhang expected from institutional desks, "
            "triggering margin unwinding and panic liquidation."
        )
        color = "rose"
    elif direction == "MODERATE_BEARISH":
        score = -5
        rating = "⚠️ BEARISH DRAG (-5/10)"
        driver = f"Operational / Margin Headwind ({kw})"
        rationale = (
            "Near-term margin compression or temporary operational disruption. Short-term sentiment turns cautious, "
            "favoring protective Put hedging and capping immediate upside rallies."
        )
        color = "orange"
    elif direction == "EXPLOSIVE_BULLISH":
        score = +8
        rating = "🚀 EXPLOSIVELY BULLISH (+8/10)"
        driver = f"Mega Order / Value Unlocking ({kw})"
        rationale = (
            "Substantial multi-year revenue accretion, regulatory clearance, or capital infusion. "
            "Short-covering combined with fresh institutional long accumulation triggers aggressive upward multiple expansion."
        )
        color = "emerald"
    elif direction == "MODERATE_BULLISH":
        score = +5
        rating = "⚡ BULLISH MOMENTUM (+5/10)"
        driver = f"Commercial Expansion / Demand Growth ({kw})"
        rationale = (
            "Healthy operational progress and positive order inflow. Market participants likely to accumulate on dips, "
            "providing strong base support above S1."
        )
        color = "teal"
    else:
        score = 0
        rating = "⚖️ NEUTRAL (0/10)"
        driver = "Routine Business Update"
        rationale = "Announcement does not alter medium-term discounted cash flows or earnings consensus estimates."
        color = "gray"

    sentiment_analysis = {
        "score": score,
        "rating": rating,
        "driver": driver,
        "rationale": rationale,
        "color": color
    }

    # 3. How It Can Affect Price (Price Impact Analysis)
    step = get_strike_step(cmp) if cmp > 0 else 50
    atm = int(round(cmp / step) * step) if (cmp > 0 and step >= 1) else round(cmp / step) * step
    lot_sz = get_fno_lot_size(symbol, cmp) if cmp > 0 else 0

    if direction == "SEVERE_BEARISH":
        move_pct = "-15% to -22% Downside Collapse"
        target_low = round(cmp * 0.78, 1) if cmp > 0 else 0.0
        target_high = round(cmp * 0.85, 1) if cmp > 0 else 0.0
        target_range = f"₹{target_low:,.0f} – ₹{target_high:,.0f} (Deep breach below S1: ₹{s1:,.0f})"
        mechanism = (
            "Immediate gap-down driven by opening block sales and margin call liquidations. "
            "Spot price penetrates key support S1 rapidly. Arbitrageurs selling spot shares against derivative hedges "
            "create sustained selling waves across the morning session."
        )
        session_behavior = (
            "09:15–09:25 AM: Extreme volatility with wide bid-ask spreads. Do NOT chase at 09:15 open! "
            "09:25–09:35 AM: If price holds below VWAP with >2x 15-min volume, downside trend confirms."
        )
        derivatives_impact = (
            "Put (PE) options experience explosive Implied Volatility (IV) surges (+50% to +100%+). "
            "Deep OTM Puts (3-4 strikes away) benefit from violent delta acceleration, turning from ₹0.30–₹2.00 into deep ITM runners."
        )
        pe_primary = int(atm - step) if step >= 1 else (atm - step)
        pe_deep = int(atm - (step * 3)) if step >= 1 else (atm - (step * 3))
        est_prem = round(cmp * 0.012, 1) if cmp >= 100 else 1.0
        est_cap = int(round((est_prem * lot_sz) / 100.0) * 100) if lot_sz > 0 else 0

        option_setup = {
            "recommended_action": "WATCH PUTS (PE) FOR ASYMMETRIC SURGE",
            "primary_strike": f"{pe_primary} PE (1-Strike OTM)",
            "extreme_strike": f"{pe_deep} PE (Deep OTM Shocker)",
            "atm_strike": f"{atm} PE",
            "strikes_display": f"{pe_primary} PE & {pe_deep} PE",
            "lot_size": lot_sz,
            "est_premium": est_prem,
            "est_capital_required": est_cap,
            "execution_warning": (
                "⚠️ TIMING DISCIPLINE: Bid-ask spreads widen drastically at 09:15 AM. "
                "Wait for 09:25–09:35 AM once opening 15-min volume stabilizes below VWAP."
            )
        }
    elif direction == "MODERATE_BEARISH":
        move_pct = "-4% to -8% Pullback"
        target_low = round(cmp * 0.92, 1) if cmp > 0 else 0.0
        target_high = round(cmp * 0.96, 1) if cmp > 0 else 0.0
        target_range = f"₹{target_low:,.0f} – ₹{target_high:,.0f} (Testing S1: ₹{s1:,.0f})"
        mechanism = "Intraday profit booking and selective short buildup. S1 is tested as key support."
        session_behavior = "Gap down likely to face dip-buying near S1 if broader Nifty index is positive."
        derivatives_impact = "Mild IV uptick; Bear Put spreads or ATM Put scalps offer defined risk."
        pe_primary = int(atm - step) if step >= 1 else (atm - step)
        est_prem = round(cmp * 0.010, 1) if cmp >= 100 else 1.0
        est_cap = int(round((est_prem * lot_sz) / 100.0) * 100) if lot_sz > 0 else 0

        option_setup = {
            "recommended_action": "WATCH S1 SUPPORT / BEAR SPREADS",
            "primary_strike": f"{pe_primary} PE",
            "extreme_strike": f"{pe_primary} PE",
            "atm_strike": f"{atm} PE",
            "strikes_display": f"{pe_primary} PE",
            "lot_size": lot_sz,
            "est_premium": est_prem,
            "est_capital_required": est_cap,
            "execution_warning": "Watch for reversal wick near S1 before entering fresh short positions."
        }
    elif direction == "EXPLOSIVE_BULLISH":
        move_pct = "+10% to +18%+ Breakout Rally"
        target_low = round(cmp * 1.10, 1) if cmp > 0 else 0.0
        target_high = round(cmp * 1.18, 1) if cmp > 0 else 0.0
        target_range = f"₹{target_low:,.0f} – ₹{target_high:,.0f} (Decisive breakout above R1: ₹{r1:,.0f})"
        mechanism = (
            "Aggressive institutional pre-market bidding forces gap-up open. Trapped short sellers face forced margin square-offs, "
            "triggering cascading buy-market orders and volume breakout above resistance R1."
        )
        session_behavior = (
            "09:15–09:20 AM: Opening surge tests R1. "
            "09:25–09:35 AM: If 15-min candle closes firmly above R1 with volume > 2x average, momentum continuation is confirmed."
        )
        derivatives_impact = (
            "Call (CE) option premiums surge rapidly as Call writers scramble to cover short positions. "
            "1-2 strike OTM Calls offer high-velocity percentage gains."
        )
        ce_primary = int(atm + step) if step >= 1 else (atm + step)
        ce_runner = int(atm + (step * 2)) if step >= 1 else (atm + (step * 2))
        est_prem = round(cmp * 0.014, 1) if cmp >= 100 else 1.0
        est_cap = int(round((est_prem * lot_sz) / 100.0) * 100) if lot_sz > 0 else 0

        option_setup = {
            "recommended_action": "WATCH CALLS (CE) FOR MOMENTUM BREAKOUT",
            "primary_strike": f"{ce_primary} CE (1-Strike OTM)",
            "extreme_strike": f"{ce_runner} CE (Runner)",
            "atm_strike": f"{atm} CE",
            "strikes_display": f"{ce_primary} CE & {ce_runner} CE",
            "lot_size": lot_sz,
            "est_premium": est_prem,
            "est_capital_required": est_cap,
            "execution_warning": (
                "⚡ MOMENTUM RULE: Enter only on 15-min candle confirmation above R1 with VWAP support. "
                "Trail stop-loss aggressively."
            )
        }
    elif direction == "MODERATE_BULLISH":
        move_pct = "+4% to +8% Bullish Push"
        target_low = round(cmp * 1.04, 1) if cmp > 0 else 0.0
        target_high = round(cmp * 1.08, 1) if cmp > 0 else 0.0
        target_range = f"₹{target_low:,.0f} – ₹{target_high:,.0f} (Testing Ceiling R1: ₹{r1:,.0f})"
        mechanism = "Positive news sentiment attracts steady retail and DII demand. Controlled accumulation above VWAP."
        session_behavior = "Watch for continuation above yesterday's high with sustained buy volume."
        derivatives_impact = "ATM Call options or Bull Call spreads offer attractive reward:risk."
        ce_primary = int(atm + step) if step >= 1 else (atm + step)
        est_prem = round(cmp * 0.012, 1) if cmp >= 100 else 1.0
        est_cap = int(round((est_prem * lot_sz) / 100.0) * 100) if lot_sz > 0 else 0

        option_setup = {
            "recommended_action": "WATCH CALLS (CE) ON DIPS",
            "primary_strike": f"{ce_primary} CE",
            "extreme_strike": f"{ce_primary} CE",
            "atm_strike": f"{atm} CE",
            "strikes_display": f"{ce_primary} CE",
            "lot_size": lot_sz,
            "est_premium": est_prem,
            "est_capital_required": est_cap,
            "execution_warning": "Avoid chasing morning gap-up; wait for pullback to 5-min VWAP."
        }
    else:
        move_pct = "±1% to ±2% Routine Range"
        target_range = f"₹{round(s1, 0)} – ₹{round(r1, 0)}"
        mechanism = "Price remains within normal daily liquidity and ATR bands."
        session_behavior = "Standard range-bound trading."
        derivatives_impact = "Options volatility crush (theta decay) favors option sellers or neutral strategies."
        option_setup = {
            "recommended_action": "NO DERIVATIVES PLAY",
            "strikes_display": "Routine Disclosure",
            "execution_warning": "No extraordinary price volatility expected."
        }

    price_impact = {
        "direction": direction,
        "expected_move_pct": move_pct,
        "target_range": target_range,
        "mechanism": mechanism,
        "session_behavior": session_behavior,
        "derivatives_impact": derivatives_impact
    }

    return {
        "id": f"catalyst_{symbol}_{abs(hash(headline)) % 1000000}",
        "symbol": symbol,
        "company_name": company_name,
        "is_case_study": is_case_study,
        "source": source,
        "headline": clean_headline,
        "details": details[:350],
        "pdf_url": url,
        "announced_at": announced_at,
        "is_fno": symbol in NSE_FNO_SYMBOLS,
        "current_price": cmp,
        "rsi": rsi,
        "support_1": s1,
        "resistance_1": r1,
        "delivery_pct": delivery_pct,
        "classification": clf,
        "news_summary": summary_points,
        "sentiment_analysis": sentiment_analysis,
        "price_impact": price_impact,
        "option_setup": option_setup,
        "timestamp": int(time.time())
    }

# ====================================================================
# HISTORICAL REFERENCE BLUEPRINTS & CASE STUDIES
# These are kept strictly separate from live news and flagged is_case_study: True
# ====================================================================
HISTORICAL_BLUEPRINTS: List[Dict[str, Any]] = [
    {
        "id": "blueprint_aplapollo_tata_steel",
        "symbol": "APLAPOLLO",
        "company_name": "APL Apollo Tubes Limited",
        "is_case_study": True,
        "case_study_title": "🏛️ Benchmark Case Study: Tata Steel 26.6% Stake Dilution (-20% Crash / 1800 PE +72,400% Surge)",
        "source": "NSE Corporate Disclosure & Historical Case Study",
        "headline": "Strategic agreement with Tata Steel for 26.6% stake acquisition and tubes business transfer",
        "details": "Tata Steel acquired 26.6% promoter stake for ₹15,510 Cr @ ₹2,100 per share with transfer of pipes business. Market feared severe minority shareholder dilution and loss of premium valuation, triggering a 20% crash to ₹1,655; 1800 PE surged +72,400% from ₹0.20 to ₹145.",
        "pdf_url": "https://www.nseindia.com",
        "announced_at": "Benchmark Case Study",
        "is_fno": True,
        "current_price": 1680.0,
        "rsi": 28.5,
        "support_1": 1610.0,
        "resistance_1": 1820.0,
        "delivery_pct": 68.4,
        "classification": {
            "is_catalyst": True,
            "direction": "SEVERE_BEARISH",
            "direction_label": "🔻 SEVERE BEARISH SHOCK (PUT SURGE BLUEPRINT)",
            "severity": "CRITICAL_SHOCK",
            "severity_badge": "🚨 70,000% PE SURGE BLUEPRINT",
            "expected_move": "19% to 22% Downside Collapse",
            "trigger_keyword": "STAKE ACQUISITION & DILUTION",
            "option_focus": "PUT (PE) 70,000% Surge",
            "sentiment_color": "rose"
        },
        "news_summary": {
            "key_event": "Tata Steel acquired 26.6% promoter stake in APL Apollo Tubes with corporate restructuring of tubes business.",
            "financial_quantum": "₹15,510 crore at ₹2,100 per share; 26.6% equity dilution for existing shareholders.",
            "strategic_context": "Market perceived loss of standalone agility, minority shareholder dilution, and valuation de-rating."
        },
        "sentiment_analysis": {
            "score": -9,
            "rating": "🔻 SEVERELY BEARISH (-9/10)",
            "driver": "Equity Dilution & Promoter Stake Sale",
            "rationale": "High-growth premium multiple collapsed as market repriced APL Apollo from an agile consumer brand to a conglomerate subsidiary with dilution overhang.",
            "color": "rose"
        },
        "price_impact": {
            "direction": "CRASH (-20.5% in 2 Sessions)",
            "expected_move_pct": "-20% Single-Session Fall",
            "target_range": "Collapsed from ₹2,120 to ₹1,655",
            "mechanism": "Institutional block selling and retail panic liquidation completely overwhelmed buy orders, breaking all support levels.",
            "session_behavior": "Stock opened gap-down and was offered down through the day without finding support until ₹1,655.",
            "derivatives_impact": "1800 PE traded at ₹0.20–₹0.60 before news; surged to ₹145+ when spot touched ₹1,655 (+72,400% gain, ₹70,000+ profit per ₹100 invested)."
        },
        "option_setup": {
            "recommended_action": "WATCH 3-4 STRIKES DEEP OTM PUTS",
            "primary_strike": "1800 PE (Penny Option Shock)",
            "extreme_strike": "1700 PE (Deep Crash Run)",
            "atm_strike": "2100 PE",
            "strikes_display": "1800 PE (+72,400%) & 1700 PE",
            "lot_size": 350,
            "est_premium": 0.40,
            "est_capital_required": 140,
            "execution_warning": "Historical Blueprint: 3-4 strikes deep OTM puts cost negligible capital (₹140/lot) but yield life-changing 700x returns when black-swan events unfold."
        },
        "timestamp": int(time.time())
    },
    {
        "id": "blueprint_zeel_sony_merger",
        "symbol": "ZEEL",
        "company_name": "Zee Entertainment Enterprises Limited",
        "is_case_study": True,
        "case_study_title": "🏛️ Benchmark Case Study: Sony Merger Termination (-33% Single-Day Crash / 160 PE +1,850% Surge)",
        "source": "NSE Corporate Disclosure & Historical Case Study",
        "headline": "Sony officially calls off $10 Billion merger with Zee Entertainment",
        "details": "Sony Group issued termination letter for the $10 billion mega-merger citing non-fulfillment of closing conditions and initiated arbitration seeking $90M termination fee. ZEEL stock crashed 33% in a single session from ₹245 to ₹152; 160 PE surged from ₹2.50 to ₹48.80 (+1,852%).",
        "pdf_url": "https://www.nseindia.com",
        "announced_at": "Benchmark Case Study",
        "is_fno": True,
        "current_price": 125.0,
        "rsi": 32.0,
        "support_1": 115.0,
        "resistance_1": 135.0,
        "delivery_pct": 52.0,
        "classification": {
            "is_catalyst": True,
            "direction": "SEVERE_BEARISH",
            "direction_label": "🔻 SEVERE BEARISH SHOCK (DEAL CANCELLATION)",
            "severity": "CRITICAL_SHOCK",
            "severity_badge": "🚨 33% CRASH CASE STUDY",
            "expected_move": "30% to 35% Downside Collapse",
            "trigger_keyword": "MERGER TERMINATION & ARBITRATION",
            "option_focus": "PUT (PE) 1,850% Surge",
            "sentiment_color": "rose"
        },
        "news_summary": {
            "key_event": "Sony cancelled the 2-year-long $10B merger deal with Zee and demanded $90M in arbitration damages.",
            "financial_quantum": "$10 Billion merger cancelled; $90M termination damages claimed by Sony.",
            "strategic_context": "Loss of global distribution scale, leaving Zee vulnerable to intense domestic OTT streaming competition."
        },
        "sentiment_analysis": {
            "score": -10,
            "rating": "🔻 CRITICALLY BEARISH (-10/10)",
            "driver": "Merger Cancellation & Litigation Shock",
            "rationale": "Entire 2-year institutional investment thesis was predicated on Sony taking management control; termination triggered complete institutional exit.",
            "color": "rose"
        },
        "price_impact": {
            "direction": "CRASH (-33% Single Session)",
            "expected_move_pct": "-33% Downside Collapse",
            "target_range": "Crashed from ₹245 to ₹152",
            "mechanism": "Foreign portfolio investors and domestic mutual funds dumped shares unconditionally from the 09:00 AM pre-open session.",
            "session_behavior": "Severe lower circuit halts throughout the day; bids disappeared across cash and futures.",
            "derivatives_impact": "160 PE spiked from ₹2.50 to ₹48.80 (+1,850%), delivering nearly 20x return on Put buyer capital."
        },
        "option_setup": {
            "recommended_action": "WATCH DEEP OTM PUTS ON DEAL CANCELLATION",
            "primary_strike": "160 PE (Crash Runner)",
            "extreme_strike": "150 PE",
            "atm_strike": "240 PE",
            "strikes_display": "160 PE (+1,850%) & 150 PE",
            "lot_size": 3000,
            "est_premium": 2.50,
            "est_capital_required": 7500,
            "execution_warning": "When mega M&A deals collapse over weekend/pre-market, OTM Puts 3-4 strikes below spot explode exponentially."
        },
        "timestamp": int(time.time())
    }
]

def fetch_exchange_announcements_raw() -> List[Dict[str, Any]]:
    """Fetches real-time corporate announcements from NSE India."""
    session = requests.Session()
    session.headers.update(NSE_HEADERS)
    try:
        session.get("https://www.nseindia.com", verify=False, timeout=8)
    except Exception:
        pass

    try:
        url = "https://www.nseindia.com/api/corporate-announcements?index=equities"
        res = session.get(url, verify=False, timeout=12)
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        print(f"[News Service] Error fetching NSE announcements: {e}")
    return []

def fetch_financial_news_rss() -> List[Dict[str, Any]]:
    """
    Fetches breaking financial news from multi-source institutional RSS feeds:
    1. Economic Times Stock News
    2. LiveMint Markets
    3. Google News India Financial search (with recency when:1d)
    """
    sources = [
        ("Economic Times", "https://economictimes.indiatimes.com/markets/stocks/rssfeeds/2146842.cms"),
        ("LiveMint Markets", "https://www.livemint.com/rss/markets"),
        ("Google Financial News", "https://news.google.com/rss/search?q=NSE+stocks+OR+shares+OR+results+OR+order+OR+SEBI+OR+acquisition+when:1d&hl=en-IN&gl=IN&ceid=IN:en")
    ]

    news_items = []
    seen_titles = set()

    for sname, url in sources:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                xml_data = resp.read()
            root = ET.fromstring(xml_data)

            for item in root.findall(".//item")[:50]:
                title = (item.find("title").text or "").strip()
                desc = (item.find("description").text or "").strip()
                link = (item.find("link").text or "").strip()
                pub_date = (item.find("pubDate").text or "").strip()

                if not title or title in seen_titles:
                    continue

                # Match with F&O and company aliases
                title_upper = title.upper()
                matched_sym = None

                # 1. Alias lookup
                for alias, sym in COMPANY_ALIASES.items():
                    if alias in title_upper:
                        matched_sym = sym
                        break

                # 2. Direct symbol match
                if not matched_sym:
                    for sym in NSE_FNO_SYMBOLS:
                        if len(sym) >= 3 and (f" {sym} " in f" {title_upper} " or f"({sym})" in title_upper or f"{sym}:" in title_upper):
                            matched_sym = sym
                            break

                if matched_sym:
                    seen_titles.add(title)
                    news_items.append({
                        "source": f"{sname} (Breaking)",
                        "symbol": matched_sym,
                        "title": title,
                        "desc": desc,
                        "url": link,
                        "time_str": pub_date
                    })
        except Exception as e:
            print(f"[News Service] Error reading {sname}: {e}")

    return news_items

def get_high_impact_news_catalysts(force_refresh: bool = False, include_case_studies: bool = True) -> List[Dict[str, Any]]:
    """
    Scans real-time exchange announcements and breaking financial media for TODAY's high-impact catalysts.
    Enriches with:
    1. News in Summary-Wise (Key Event, Financial Quantum, Strategic Context)
    2. Detailed Sentiment Analysis (Score -10 to +10, Rating, Driver, Institutional Rationale)
    3. How It Can Affect Price (Direction, Projected Target Range, Mechanism, Session Dynamics, Derivatives/Options Impact)
    4. Actionable Options Setup (Strikes, Lot size, Capital)
    
    IMPORTANT: Historical Case Studies (APL Apollo 70,000% PE, ZEEL 33% crash) are kept flagged with is_case_study: True,
    so live news of the day is never confused with historical benchmarks!
    """
    global NEWS_CACHE_FILE
    now_ts = time.time()

    # Use disk cache if fresh (< 2 minutes)
    if not force_refresh and NEWS_CACHE_FILE.exists():
        try:
            mtime = NEWS_CACHE_FILE.stat().st_mtime
            if now_ts - mtime < 120:
                with open(NEWS_CACHE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass

    live_catalysts: List[Dict[str, Any]] = []
    seen_symbols = set()

    # 1. Scan NSE Corporate Announcements
    raw_nse = fetch_exchange_announcements_raw()
    for item in raw_nse:
        sym = (item.get("symbol") or "").strip().upper()
        if not sym:
            continue
        comp = item.get("sm_name") or sym
        desc = (item.get("desc") or "") + " " + (item.get("attchmntText") or "")
        pdf = item.get("attchmntFile") or ""
        t_str = item.get("an_dt") or item.get("dt") or "Today"

        if not desc:
            continue

        clf = classify_catalyst(desc)
        # Include if catalyst, or if major F&O stock with official filing
        if clf["is_catalyst"] and sym not in seen_symbols:
            seen_symbols.add(sym)
            tech = get_stock_technicals(sym)
            cmp = tech.get("current_price", 0.0) if tech else 0.0
            rsi = tech.get("rsi", 50.0) if tech else 50.0
            pivots = tech.get("pivots", {}) if tech else {}
            del_pct = tech.get("delivery_pct", 50.0) if tech else 50.0

            card = analyze_catalyst_deep(
                symbol=sym,
                company_name=comp,
                headline=item.get("desc", ""),
                details=item.get("attchmntText", "")[:350],
                source="NSE Corporate Filing (Official)",
                announced_at=t_str,
                url=pdf or "https://www.nseindia.com",
                cmp=cmp,
                pivots=pivots,
                rsi=rsi,
                delivery_pct=del_pct,
                clf=clf,
                is_case_study=False
            )
            live_catalysts.append(card)

    # 2. Scan Breaking Financial Media RSS
    rss_items = fetch_financial_news_rss()
    for it in rss_items:
        sym = it["symbol"]
        title = it["title"]
        desc = it["desc"]

        clf = classify_catalyst(title + " " + desc)
        # Even if classification is routine, if it contains fund-raise, jump, result, award, order, penalty, classify it
        if clf["is_catalyst"] and sym not in seen_symbols:
            seen_symbols.add(sym)
            tech = get_stock_technicals(sym)
            cmp = tech.get("current_price", 0.0) if tech else 0.0
            rsi = tech.get("rsi", 50.0) if tech else 50.0
            pivots = tech.get("pivots", {}) if tech else {}
            del_pct = tech.get("delivery_pct", 50.0) if tech else 50.0

            card = analyze_catalyst_deep(
                symbol=sym,
                company_name=tech.get("company_name", sym) if tech else sym,
                headline=title,
                details=desc or f"Breaking market report on {sym}.",
                source=it["source"],
                announced_at=it["time_str"] or "Today Breaking",
                url=it["url"],
                cmp=cmp,
                pivots=pivots,
                rsi=rsi,
                delivery_pct=del_pct,
                clf=clf,
                is_case_study=False
            )
            live_catalysts.append(card)

    # 3. Combine live catalysts + historical blueprints (clearly flagged)
    all_catalysts = []
    # Live catalysts come first
    all_catalysts.extend(live_catalysts)

    # Blueprint case studies come after (or can be filtered via is_case_study)
    if include_case_studies:
        all_catalysts.extend(HISTORICAL_BLUEPRINTS)

    # Cache to disk
    try:
        with open(NEWS_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(all_catalysts, f, indent=2)
    except Exception as e:
        print(f"[News Service] Error saving cache: {e}")

    return all_catalysts

def broadcast_morning_high_impact_news(force: bool = False) -> Dict[str, Any]:
    """
    Broadcasts the Morning Pre-Market High-Impact News Radar to Telegram:
    - Scans live news before market opens (08:30 - 09:15 AM)
    - Alerts on both SEVERE BEARISH (PE Surge Risk) and EXPLOSIVE BULLISH (CE Runners)
    - Summarizes what happened, the sentiment score, and how it will affect price
    """
    now_ist = get_ist_now()
    today_str = now_ist.strftime("%d-%m-%Y")

    if not force and NEWS_BROADCAST_LOG.exists():
        try:
            with open(NEWS_BROADCAST_LOG, "r") as f:
                log_data = json.load(f)
                if log_data.get(today_str):
                    return {"status": "SKIPPED", "message": f"Morning news radar already broadcasted for {today_str}"}
        except Exception:
            pass

    catalysts = get_high_impact_news_catalysts(force_refresh=True)
    live_items = [c for c in catalysts if not c.get("is_case_study")]

    lines = [
        f"🚨 *MORNING HIGH-IMPACT NEWS & OPTIONS RADAR ({today_str})*",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"📡 *Pre-Market Catalyst Alert: Asymmetric Volatility Radar*",
        f"⏱️ _Scanned: Real-Time Corporate Filings, Regulatory Actions, Stake Deals & Commercials_\n"
    ]

    items_to_broadcast = live_items if live_items else catalysts[:3]

    for item in items_to_broadcast[:6]:
        sym = item["symbol"]
        comp = item["company_name"]
        clf = item.get("classification", {})
        setup = item.get("option_setup", {})
        summary = item.get("news_summary", {})
        sentiment = item.get("sentiment_analysis", {})
        impact = item.get("price_impact", {})

        cmp = item.get("current_price", 0.0)
        s1 = item.get("support_1", 0.0)
        r1 = item.get("resistance_1", 0.0)
        del_pct = item.get("delivery_pct", 50.0)
        strikes = setup.get("strikes_display", "N/A")
        lot_sz = setup.get("lot_size", 0)

        is_bearish = "BEARISH" in clf.get("direction", "")
        dir_icon = "💥" if is_bearish else "🚀"
        is_cs = "🏛️ [CASE STUDY]" if item.get("is_case_study") else "🔥 [TODAY'S RADAR]"

        lines.append(f"{dir_icon} *{sym}* ({comp[:24]}) — {is_cs}")
        lines.append(f"   ├ 📋 *Summary*: _{summary.get('key_event', item['headline'])[:100]}_")
        lines.append(f"   ├ 🧠 *Sentiment*: *{sentiment.get('rating', 'Active')}* | Driver: _{sentiment.get('driver', 'Corporate Action')}_")
        lines.append(f"   ├ 🎯 *Price Impact*: *{impact.get('expected_move_pct', 'High Volatility')}* ➔ Target: *{impact.get('target_range', 'S1/R1')}*")
        lines.append(f"   ├ 📊 *Current Levels*: CMP *₹{cmp:,.1f}* | S1 ₹{s1:,.0f} | R1 ₹{r1:,.0f} (Del {del_pct}%)")
        lines.append(f"   ├ ⚡ *Options Setup*: *{strikes}* (Lot: {lot_sz})")
        lines.append(f"   └ 🛡️ *Timing & Caution*: _{setup.get('execution_warning', '')[:100]}..._\n")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🎯 *Live Web Dashboard & 360° Catalyst Tracker:*")
    lines.append("👉 https://stock-analysis-alert.onrender.com\n")
    lines.append("⚠️ _Disclaimer: For institutional market intelligence and derivatives research only. Not investment advice._")

    msg = "\n".join(lines)
    sent = send_telegram_alert(msg)

    if sent:
        log_data = {}
        if NEWS_BROADCAST_LOG.exists():
            try:
                with open(NEWS_BROADCAST_LOG, "r") as f:
                    log_data = json.load(f)
            except Exception:
                pass
        log_data[today_str] = {"timestamp": now_ist.isoformat(), "count": len(items_to_broadcast)}
        try:
            with open(NEWS_BROADCAST_LOG, "w") as f:
                json.dump(log_data, f, indent=2)
        except Exception:
            pass
        return {"status": "SUCCESS", "message": f"Successfully broadcasted morning high-impact catalysts to Telegram"}
    else:
        return {"status": "FAILED", "message": "Failed to send Telegram alert"}
