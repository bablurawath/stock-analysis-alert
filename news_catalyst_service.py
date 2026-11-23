import time
import requests
import json
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
    "contract cancelled", "termination of contract", "loss of order"
]

BULLISH_RUNNER_KEYWORDS = [
    # Massive Wins & Commercials
    "mega order", "bags order", "contract award", "awarded contract", "l1 bidder",
    "commercial production", "joint venture", "strategic alliance",
    # Corporate Actions & Buybacks
    "buyback at premium", "bonus issue", "special dividend", "demerger value unlocking",
    # Regulatory Clearances
    "usfda eir", "clean clearance", "zero 483", "vld", "inspection closed",
    "pli scheme", "patent grant", "anti-dumping duty", "environmental clearance",
    # Ownership & Rating Upgrades
    "global giant acquiring", "open offer at premium", "rating upgraded", "debt free"
]

def get_ist_now() -> datetime:
    ist = timezone(timedelta(hours=5, minutes=30))
    return datetime.now(ist)

def classify_catalyst(text: str) -> Dict[str, Any]:
    """
    Classifies a corporate announcement / news headline into:
    - Direction: SEVERE_BEARISH, EXPLOSIVE_BULLISH, or NEUTRAL
    - Impact Severity: CRITICAL (15-25%+ swing risk), HIGH (6-12%), MODERATE (3-5%)
    - Trigger keyword & category
    """
    t_lower = text.lower()
    
    # Check Bearish Shocks first
    matched_bearish = [kw for kw in BEARISH_SHOCK_KEYWORDS if kw in t_lower]
    if matched_bearish:
        kw = matched_bearish[0]
        # Critical severity check
        is_critical = any(k in t_lower for k in [
            "acquisition", "stake sale", "it raid", "ed search", "warning letter",
            "import alert", "auditor resigned", "forensic audit", "insolvency", "nclt"
        ])
        severity = "CRITICAL_SHOCK" if is_critical else "HIGH_IMPACT"
        expected_move = "15% to 25%+ Downside Crash" if is_critical else "6% to 12% Gap-Down"
        
        return {
            "is_catalyst": True,
            "direction": "SEVERE_BEARISH",
            "direction_label": "🔻 SEVERE BEARISH SHOCK (PUT SURGE RISK)",
            "severity": severity,
            "severity_badge": "🚨 CRITICAL RISK" if is_critical else "⚠️ HIGH IMPACT",
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
            "buyback at premium", "usfda eir", "clean clearance", "global giant", "demerger"
        ])
        severity = "CRITICAL_RALLY" if is_critical else "HIGH_IMPACT"
        expected_move = "12% to 20%+ Upside Rally" if is_critical else "5% to 10% Gap-Up"

        return {
            "is_catalyst": True,
            "direction": "EXPLOSIVE_BULLISH",
            "direction_label": "🚀 EXPLOSIVE BULLISH (CALL RUNNER)",
            "severity": severity,
            "severity_badge": "🔥 EXPLOSIVE RALLY" if is_critical else "⚡ HIGH MOMENTUM",
            "expected_move": expected_move,
            "trigger_keyword": kw.upper(),
            "option_focus": "CALL (CE) Runners",
            "sentiment_color": "emerald"
        }

    return {
        "is_catalyst": False,
        "direction": "NEUTRAL",
        "direction_label": "Routine Disclosure",
        "severity": "NORMAL",
        "severity_badge": "Routine",
        "expected_move": "Within daily ATR",
        "trigger_keyword": "GENERAL",
        "option_focus": "None",
        "sentiment_color": "gray"
    }

def build_option_catalyst_setup(symbol: str, cmp: float, classification: Dict[str, Any]) -> Dict[str, Any]:
    """
    Computes actionable option strikes for high-impact catalysts:
    - Downside shock (e.g. APL Apollo style): Highlights 1-3 strike OTM Puts that explode into deep ITM.
    - Upside rally: Highlights 1-2 strike OTM Calls.
    - Provides official lot size, estimated entry capital, and strict execution timing warnings.
    """
    if not cmp or cmp <= 0:
        return {}

    step = get_strike_step(cmp)
    atm = int(round(cmp / step) * step) if step >= 1 else round(cmp / step) * step
    lot_sz = get_fno_lot_size(symbol, cmp)

    direction = classification.get("direction", "NEUTRAL")

    if direction == "SEVERE_BEARISH":
        # For severe downside, watch ATM, 1-Strike OTM, and Deep OTM Put (which explodes if stock crashes 15-20%)
        pe_primary = int(atm - step) if step >= 1 else (atm - step)
        pe_deep = int(atm - (step * 3)) if step >= 1 else (atm - (step * 3))
        est_pe_prem = round(cmp * 0.012, 1) if cmp >= 100 else round(cmp * 0.015, 2)
        est_cap = int(round((est_pe_prem * lot_sz) / 100.0) * 100)

        return {
            "recommended_action": "WATCH PUTS (PE) FOR ASYMMETRIC SURGE",
            "primary_strike": f"{pe_primary} PE (1-Strike OTM)",
            "extreme_strike": f"{pe_deep} PE (Deep OTM Shocker)",
            "atm_strike": f"{atm} PE",
            "strikes_display": f"{pe_primary} PE & {pe_deep} PE",
            "lot_size": lot_sz,
            "est_premium": est_pe_prem,
            "est_capital_required": est_cap,
            "execution_warning": (
                "⚠️ CRITICAL TIMING: DO NOT market-order at 09:15 AM! Bid-ask spreads widen drastically on news shock. "
                "Wait for 09:25–09:35 AM once the opening 15-min volume stabilizes below VWAP."
            ),
            "apl_apollo_reference": (
                "Historical Blueprint: On Tata Steel 26.6% acquisition/dilution news, APLAPOLLO fell 20% from ₹2,120 to ₹1,655, "
                "catapulting the 1800 PE from ₹0.20 to ₹145+ (+72,000%)."
            )
        }
    elif direction == "EXPLOSIVE_BULLISH":
        ce_primary = int(atm + step) if step >= 1 else (atm + step)
        ce_runner = int(atm + (step * 2)) if step >= 1 else (atm + (step * 2))
        est_ce_prem = round(cmp * 0.014, 1) if cmp >= 100 else round(cmp * 0.016, 2)
        est_cap = int(round((est_ce_prem * lot_sz) / 100.0) * 100)

        return {
            "recommended_action": "WATCH CALLS (CE) FOR EXPLOSIVE BREAKOUT",
            "primary_strike": f"{ce_primary} CE (1-Strike OTM)",
            "extreme_strike": f"{ce_runner} CE (Momentum Runner)",
            "atm_strike": f"{atm} CE",
            "strikes_display": f"{ce_primary} CE & {ce_runner} CE",
            "lot_size": lot_sz,
            "est_premium": est_ce_prem,
            "est_capital_required": est_cap,
            "execution_warning": (
                "⚡ MOMENTUM RULE: Look for opening gap continuation above R1. "
                "Enter on 15-min candle confirmation with 2x average volume."
            ),
            "apl_apollo_reference": "Upside counterpart: Major buyback or USFDA clean clearance triggers 1000%+ Call surges."
        }
    else:
        return {
            "recommended_action": "NO DERIVATIVES PLAY",
            "strikes_display": "Routine Disclosure",
            "execution_warning": "No extraordinary volatility expected."
        }

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
    Fetches breaking Google News India financial/stock news RSS feed
    to capture news breaking in the media before or alongside exchange filings.
    """
    url = "https://news.google.com/rss/search?q=NSE+stocks+OR+shares+OR+acquisition+OR+SEBI+OR+USFDA+OR+investigation&hl=en-IN&gl=IN&ceid=IN:en"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    news_items = []

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            xml_data = resp.read()
        root = ET.fromstring(xml_data)
        for item in root.findall(".//item")[:40]:
            title = item.find("title").text if item.find("title") is not None else ""
            link = item.find("link").text if item.find("link") is not None else ""
            pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
            
            # Extract possible symbol from title
            title_upper = title.upper()
            matched_sym = ""
            for sym in sorted(list(NSE_FNO_SYMBOLS), key=len, reverse=True):
                # Word boundary check
                if f" {sym} " in f" {title_upper} " or f"({sym})" in title_upper or f"{sym}:" in title_upper:
                    matched_sym = sym
                    break

            if matched_sym:
                news_items.append({
                    "source": "Financial Media (Breaking)",
                    "symbol": matched_sym,
                    "title": title,
                    "url": link,
                    "time_str": pub_date
                })
    except Exception as e:
        print(f"[News Service] RSS News fetch error: {e}")

    return news_items

def get_high_impact_news_catalysts(force_refresh: bool = False) -> List[Dict[str, Any]]:
    """
    Scans exchange corporate announcements and financial news for HIGH-IMPACT market catalysts:
    - Mergers, Acquisitions, Demergers, Stake Sales (like APL Apollo & Tata Steel)
    - USFDA Warning Letters / Clean EIRs
    - IT Raids, ED Investigations, CBI, SEBI Orders
    - Mega Order Wins, Share Buybacks, Insolvency/Defaults
    Enriches with Technical Levels (CMP, RSI, S1, R1) and exact Strike Price setups (CE / PE).
    """
    global NEWS_CACHE_FILE
    now_ts = time.time()

    # Use disk cache if fresh (< 3 minutes)
    if not force_refresh and NEWS_CACHE_FILE.exists():
        try:
            mtime = NEWS_CACHE_FILE.stat().st_mtime
            if now_ts - mtime < 180:
                with open(NEWS_CACHE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass

    catalysts: List[Dict[str, Any]] = []
    seen_keys = set()

    # 1. Fetch NSE Corporate Announcements
    raw_nse = fetch_exchange_announcements_raw()
    for item in raw_nse:
        sym = (item.get("symbol") or "").strip().upper()
        comp = item.get("sm_name") or sym
        desc = (item.get("desc") or "") + " " + (item.get("attchmntText") or "")
        pdf = item.get("attchmntFile") or ""
        t_str = item.get("an_dt") or item.get("dt") or "Today"
        key = f"{sym}_{item.get('seq_id') or item.get('dt')}"

        if not desc or key in seen_keys:
            continue

        clf = classify_catalyst(desc)
        if clf["is_catalyst"]:
            seen_keys.add(key)
            # Fetch technicals for underlying
            tech = get_stock_technicals(sym)
            cmp = tech.get("current_price", 0.0) if tech else 0.0
            rsi = tech.get("rsi", 50.0) if tech else 50.0
            pivots = tech.get("pivots", {}) if tech else {}
            del_pct = tech.get("delivery_pct", 50.0) if tech else 50.0

            option_setup = build_option_catalyst_setup(sym, cmp, clf)

            catalysts.append({
                "id": f"catalyst_{key}",
                "symbol": sym,
                "company_name": comp,
                "source": "NSE Corporate Filing (Official)",
                "headline": item.get("desc", ""),
                "details": item.get("attchmntText", "")[:400],
                "pdf_url": pdf,
                "announced_at": t_str,
                "is_fno": sym in NSE_FNO_SYMBOLS,
                "current_price": cmp,
                "rsi": rsi,
                "support_1": pivots.get("s1", 0.0),
                "resistance_1": pivots.get("r1", 0.0),
                "delivery_pct": del_pct,
                "classification": clf,
                "option_setup": option_setup,
                "timestamp": int(now_ts)
            })

    # 2. Fetch Breaking Financial Media Catalysts
    rss_items = fetch_financial_news_rss()
    for it in rss_items:
        sym = it["symbol"]
        title = it["title"]
        key = f"rss_{sym}_{title[:30]}"
        if key in seen_keys:
            continue

        clf = classify_catalyst(title)
        if clf["is_catalyst"]:
            seen_keys.add(key)
            tech = get_stock_technicals(sym)
            cmp = tech.get("current_price", 0.0) if tech else 0.0
            rsi = tech.get("rsi", 50.0) if tech else 50.0
            pivots = tech.get("pivots", {}) if tech else {}
            del_pct = tech.get("delivery_pct", 50.0) if tech else 50.0
            option_setup = build_option_catalyst_setup(sym, cmp, clf)

            catalysts.append({
                "id": f"catalyst_{key}",
                "symbol": sym,
                "company_name": tech.get("company_name", sym) if tech else sym,
                "source": "Breaking Financial Media (Pre-Filing)",
                "headline": title,
                "details": f"Market intelligence reported: {title}",
                "pdf_url": it["url"],
                "announced_at": it["time_str"] or "Morning Breaking",
                "is_fno": sym in NSE_FNO_SYMBOLS,
                "current_price": cmp,
                "rsi": rsi,
                "support_1": pivots.get("s1", 0.0),
                "resistance_1": pivots.get("r1", 0.0),
                "delivery_pct": del_pct,
                "classification": clf,
                "option_setup": option_setup,
                "timestamp": int(now_ts)
            })

    # 3. Always include authoritative reference blueprints (such as APL Apollo & Tata Steel Acquisition)
    # so users can visually verify how the 70,000% PE spike catalyst works
    has_apl = any(c["symbol"] == "APLAPOLLO" for c in catalysts)
    if not has_apl:
        tech_apl = get_stock_technicals("APLAPOLLO")
        cmp_apl = tech_apl.get("current_price", 1680.0) if tech_apl else 1680.0
        pivots_apl = tech_apl.get("pivots", {}) if tech_apl else {"s1": 1610, "r1": 1820}
        clf_apl = {
            "is_catalyst": True,
            "direction": "SEVERE_BEARISH",
            "direction_label": "🔻 SEVERE BEARISH SHOCK (PUT SURGE RISK)",
            "severity": "CRITICAL_SHOCK",
            "severity_badge": "🚨 70,000% PE SURGE CASE STUDY",
            "expected_move": "19% to 22% Downside Collapse",
            "trigger_keyword": "ACQUISITION & STAKE SALE",
            "option_focus": "PUT (PE) Spikes",
            "sentiment_color": "rose"
        }
        setup_apl = {
            "recommended_action": "WATCH PUTS (PE) FOR ASYMMETRIC SURGE",
            "primary_strike": "1800 PE (Shock Spike)",
            "extreme_strike": "1700 PE (Deep Crash Run)",
            "atm_strike": "2100 PE (Pre-crash ATM)",
            "strikes_display": "1800 PE & 1700 PE",
            "lot_size": 350,
            "est_premium": 0.50,
            "est_capital_required": 175,
            "execution_warning": "On 20% crash from ₹2,120 to ₹1,655, 1800 PE rocketed from ₹0.20 to ₹145+ (+72,400% ROI).",
            "apl_apollo_reference": "Tata Steel acquired 26.6% promoter stake for ₹15,510 Cr @ ₹2,100 + business restructuring."
        }
        catalysts.insert(0, {
            "id": "catalyst_aplapollo_case_study",
            "symbol": "APLAPOLLO",
            "company_name": "APL Apollo Tubes Limited",
            "source": "NSE Corporate Disclosure & Case Study",
            "headline": "Strategic agreement with Tata Steel for 26.6% stake acquisition and business restructuring",
            "details": "Tata Steel entered strategic agreement to acquire 26.6% promoter stake in APL Apollo Tubes for ₹15,510 crore at ₹2,100 per share, transferring tubes & colour coated business. Triggered 20% crash to ₹1,655; 1800 PE surged +70,000%.",
            "pdf_url": "https://www.nseindia.com",
            "announced_at": "High-Impact Benchmark",
            "is_fno": True,
            "current_price": cmp_apl,
            "rsi": tech_apl.get("rsi", 28.5) if tech_apl else 28.5,
            "support_1": pivots_apl.get("s1", 1610.0),
            "resistance_1": pivots_apl.get("r1", 1820.0),
            "delivery_pct": tech_apl.get("delivery_pct", 68.0) if tech_apl else 68.0,
            "classification": clf_apl,
            "option_setup": setup_apl,
            "timestamp": int(now_ts)
        })

    # Cache to disk
    try:
        with open(NEWS_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(catalysts, f, indent=2)
    except Exception as e:
        print(f"[News Service] Error saving cache: {e}")

    return catalysts

def broadcast_morning_high_impact_news(force: bool = False) -> Dict[str, Any]:
    """
    Broadcasts the Morning Pre-Market High-Impact News Radar to Telegram:
    - Scans before market opens (e.g. 08:30 - 09:15 AM)
    - Alerts on both SEVERE BEARISH (PE Surge Risk) and EXPLOSIVE BULLISH (CE Runners)
    - Highlights Strike Prices to monitor, Lot sizes, and Capital requirements
    """
    now_ist = get_ist_now()
    today_str = now_ist.strftime("%d-%m-%Y")

    # Prevent spamming multiple times on same day unless forced
    if not force and NEWS_BROADCAST_LOG.exists():
        try:
            with open(NEWS_BROADCAST_LOG, "r") as f:
                log_data = json.load(f)
                if log_data.get(today_str):
                    return {"status": "SKIPPED", "message": f"Morning news radar already broadcasted for {today_str}"}
        except Exception:
            pass

    catalysts = get_high_impact_news_catalysts(force_refresh=True)
    if not catalysts:
        return {"status": "NO_DATA", "message": "No high-impact market catalysts found for today"}

    lines = [
        f"🚨 *MORNING HIGH-IMPACT NEWS & OPTIONS RADAR ({today_str})*",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"📡 *Pre-Market Catalyst Alert: Asymmetric Volatility Radar*",
        f"⏱️ _Scanned: Corporate Filings, Regulatory Actions, Stake Deals & Raids_\n"
    ]

    for item in catalysts[:8]:
        sym = item["symbol"]
        comp = item["company_name"]
        clf = item.get("classification", {})
        setup = item.get("option_setup", {})
        dir_lbl = clf.get("direction_label", "Market Catalyst")
        badge = clf.get("severity_badge", "HIGH IMPACT")
        cmp = item.get("current_price", 0.0)
        s1 = item.get("support_1", 0.0)
        r1 = item.get("resistance_1", 0.0)
        del_pct = item.get("delivery_pct", 50.0)
        strikes = setup.get("strikes_display", "N/A")
        lot_sz = setup.get("lot_size", 0)
        warn = setup.get("execution_warning", "")

        is_bearish = "BEARISH" in clf.get("direction", "")
        dir_icon = "💥" if is_bearish else "🚀"

        lines.append(f"{dir_icon} *{sym}* ({comp[:28]}) — [{badge}]")
        lines.append(f"   ├ Catalyst: *{clf.get('trigger_keyword', 'HIGH-IMPACT NEWS')}*")
        lines.append(f"   ├ Headline: _{item['headline'][:90]}..._")
        lines.append(f"   ├ Price & Levels: CMP *₹{cmp:,.1f}* | S1 ₹{s1:,.0f} | R1 ₹{r1:,.0f} (Del {del_pct}%)")
        lines.append(f"   ├ 🎯 *Options Radar*: *{strikes}* (Lot: {lot_sz})")
        if is_bearish:
            lines.append(f"   ├ ⚡ Setup: *{clf.get('expected_move', 'Heavy Gap-Down')}* ➔ Watch Put (PE) spike")
        else:
            lines.append(f"   ├ ⚡ Setup: *{clf.get('expected_move', 'Breakout Rally')}* ➔ Watch Call (CE) runner")
        lines.append(f"   └ 🛡️ *Timing*: {warn[:100]}...\n")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🎯 *Live Web Dashboard & 360° Catalyst Tracker:*")
    lines.append("👉 https://stock-analysis-alert.onrender.com\n")
    lines.append("⚠️ _Disclaimer: For institutional market intelligence and derivatives research only. Not SEBI registered investment advice._")

    msg = "\n".join(lines)
    sent = send_telegram_alert(msg)

    if sent:
        # Mark as broadcasted
        log_data = {}
        if NEWS_BROADCAST_LOG.exists():
            try:
                with open(NEWS_BROADCAST_LOG, "r") as f:
                    log_data = json.load(f)
            except Exception:
                pass
        log_data[today_str] = {"timestamp": now_ist.isoformat(), "count": len(catalysts)}
        try:
            with open(NEWS_BROADCAST_LOG, "w") as f:
                json.dump(log_data, f, indent=2)
        except Exception:
            pass
        return {"status": "SUCCESS", "message": f"Successfully broadcasted {len(catalysts)} morning high-impact catalysts to Telegram"}
    else:
        return {"status": "FAILED", "message": "Failed to send Telegram alert"}
