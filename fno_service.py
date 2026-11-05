import time
import requests
import urllib3
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from technicals import get_stock_technicals

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Authoritative set of NSE F&O underlying stock symbols
NSE_FNO_SYMBOLS = {
    "AARTIIND", "ABB", "ABBOTINDIA", "ABCAPITAL", "ABFRL", "ACC", "ADANIENT",
    "ADANIPORTS", "ALKEM", "AMBUJACEM", "APOLLOHOSP", "APOLLOTYRE", "ASHOKLEY",
    "ASIANPAINT", "ASTRAL", "ATUL", "AUBANK", "AUROPHARMA", "AXISBANK",
    "BAJAJ-AUTO", "BAJAJFINSV", "BAJFINANCE", "BALKRISIND", "BALRAMCHIN",
    "BANDHANBNK", "BANKBARODA", "BATAINDIA", "BEL", "BERGEPAINT", "BHARATFORG",
    "BHEL", "BHARTIARTL", "BIOCON", "BOSCHLTD", "BPCL", "BRITANNIA", "BSOFT",
    "CANBK", "CANFINHOME", "CHAMBLFERT", "CHOLAFIN", "CIPLA", "COALINDIA",
    "COFORGE", "COLPAL", "CONCOR", "COROMANDEL", "CROMPTON", "CUMMINSIND",
    "DABUR", "DALBHARAT", "DEEPAKNTR", "DELHIVERY", "DIVISLAB", "DIXON", "DLF",
    "DRREDDY", "EICHERMOT", "ESCORTS", "EXIDEIND", "FEDERALBNK", "GAIL",
    "GLENMARK", "GMRINFRA", "GNFC", "GODREJCP", "GODREJPROP", "GRANULES",
    "GRASIM", "GUJGASLTD", "HAL", "HAVELLS", "HCLTECH", "HDFCAMC", "HDFCBANK",
    "HDFCLIFE", "HEROMOTOCO", "HINDALCO", "HINDCOPPER", "HINDPETRO", "HINDUNILVR",
    "HUDCO", "ICICIBANK", "ICICIGI", "ICICIPRULI", "IDEA", "IDFCFIRSTB", "IEX",
    "IGL", "INDHOTEL", "INDIACEM", "INDIAMART", "INDIANB", "INDIGO", "INDUSINDBK",
    "INDUSTOWER", "INFY", "IOC", "IPCALAB", "IRCTC", "IREDA", "IRFC", "ITC",
    "JINDALSTEL", "JIOFIN", "JKCEMENT", "JSWENERGY", "JSWSTEEL", "JUBLFOOD",
    "KALYANKJIL", "KEI", "KOTAKBANK", "LALPATHLAB", "LAURUSLABS", "LICHSGFIN",
    "LICI", "LT", "LTIM", "LTTS", "LUPIN", "M&M", "M&MFIN", "MANAPPURAM",
    "MARICO", "MARUTI", "MAXHEALTH", "MCDOWELL-N", "MCX", "METROPOLIS",
    "MFSL", "MGL", "MOTHERSON", "MPHASIS", "MRF", "MUTHOOTFIN", "NATIONALUM",
    "NAUKRI", "NAVINFLUOR", "NESTLEIND", "NHPC", "NMDC", "NTPC", "NYKAA",
    "OBEROIRLTY", "OFSS", "ONGC", "PAGEIND", "PAYTM", "PEL", "PERSISTENT",
    "PETRONET", "PFC", "PHOENIXLTD", "PIDILITIND", "PIIND", "PNB", "POLICYBZR",
    "POLYCAB", "POONAWALLA", "POWERGRID", "PRESTIGE", "PVRINOX", "RAMCOCEM",
    "RBLBANK", "RECLTD", "RELIANCE", "SAIL", "SBICARD", "SBILIFE", "SBIN",
    "SHREECEM", "SHRIRAMFIN", "SIEMENS", "SOLARINDS", "SONACOMS", "SRF",
    "SUNPHARMA", "SUNTV", "SUPREMEIND", "SYNGENE", "TATACHEM", "TATACOMM",
    "TATACONSUM", "TATAELXSI", "TATAMOTORS", "TATAPOWER", "TATASTEEL",
    "TCS", "TECHM", "TIINDIA", "TITAN", "TORNTPHARM", "TORNTPOWER", "TRENT",
    "TVSMOTOR", "UBL", "ULTRACEMCO", "UNIONBANK", "UPL", "VBL", "VEDL",
    "VOLTAS", "WIPRO", "YESBANK", "ZEEL", "ZOMATO", "ZYDUSLIFE"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/"
}

# In-memory cache for today's F&O results
_CACHE_DATA = None
_CACHE_TIMESTAMP = 0
CACHE_TTL = 300  # 5 minutes

def get_ist_today_str() -> str:
    """Returns today's date formatted as DD-MM-YYYY in Indian Standard Time."""
    ist = timezone(timedelta(hours=5, minutes=30))
    now = datetime.now(ist)
    return now.strftime("%d-%m-%Y")

def get_technicals_map(symbols: List[str]) -> Dict[str, Any]:
    """Fetches technicals for a list of symbols in parallel."""
    tech_map = {}
    if not symbols:
        return tech_map
    
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_to_sym = {executor.submit(get_stock_technicals, sym): sym for sym in symbols}
        for future in future_to_sym:
            sym = future_to_sym[future]
            try:
                tech_map[sym] = future.result()
            except Exception:
                tech_map[sym] = None
    return tech_map

def fetch_today_fno_results() -> List[Dict[str, Any]]:
    """
    Fetches real-time F&O stocks that have Financial Results declared today from NSE.
    Also supplements with scheduled results from NSE event calendar.
    """
    global _CACHE_DATA, _CACHE_TIMESTAMP

    # Return cached data if fresh
    if _CACHE_DATA and (time.time() - _CACHE_TIMESTAMP < CACHE_TTL):
        return _CACHE_DATA

    today_str = get_ist_today_str()
    session = requests.Session()
    session.headers.update(HEADERS)

    raw_candidates = []
    seen_symbols = set()

    # Step 1: Prime NSE cookie session
    try:
        session.get("https://www.nseindia.com", verify=False, timeout=10)
    except Exception as e:
        print(f"[FNO Results] Error initializing NSE session: {e}")

    # Step 2: Fetch today's corporate announcements
    ann_url = f"https://www.nseindia.com/api/corporate-announcements?index=equities&from_date={today_str}&to_date={today_str}"
    try:
        r = session.get(ann_url, verify=False, timeout=15)
        if r.status_code == 200:
            items = r.json()
            for item in items:
                sym = item.get("symbol", "").strip().upper()
                desc = (item.get("desc", "") + " " + item.get("attmntText", "")).lower()
                
                # Check if it's an F&O stock and relates to Financial Results / Outcome of Board Meeting
                if sym in NSE_FNO_SYMBOLS and sym not in seen_symbols:
                    is_result = any(keyword in desc for keyword in [
                        "financial result", "financial results", "outcome of board meeting",
                        "un-audited financial", "unaudited financial", "audited financial",
                        "quarterly result", "interim dividend", "q2", "q3", "q4", "q1"
                    ])

                    if is_result:
                        seen_symbols.add(sym)
                        raw_candidates.append({
                            "type": "declared",
                            "symbol": sym,
                            "company_name": item.get("sm_name") or sym,
                            "subject": item.get("desc") or "Financial Results & Board Outcome",
                            "details": item.get("attmntText", ""),
                            "pdf_url": item.get("attmntFile") or "",
                            "time_str": item.get("an_dt") or item.get("dt") or "Today",
                            "seq_id": item.get("seq_id", int(time.time()))
                        })
    except Exception as e:
        print(f"[FNO Results] Error fetching today announcements: {e}")

    # Step 3: Check Event Calendar for upcoming/scheduled F&O board meetings
    try:
        cal_r = session.get("https://www.nseindia.com/api/event-calendar?index=equities", verify=False, timeout=15)
        if cal_r.status_code == 200:
            cal_items = cal_r.json()
            for c in cal_items:
                sym = c.get("symbol", "").strip().upper()
                purpose = c.get("purpose", "").lower()
                c_date = c.get("date", "").strip()

                if sym in NSE_FNO_SYMBOLS and sym not in seen_symbols and "financial result" in purpose:
                    seen_symbols.add(sym)
                    raw_candidates.append({
                        "type": "scheduled",
                        "symbol": sym,
                        "company_name": c.get("company") or sym,
                        "subject": f"Board Meeting for Financial Results ({c_date})",
                        "details": c.get("bm_desc", ""),
                        "pdf_url": "",
                        "time_str": f"Scheduled: {c_date}",
                        "seq_id": int(time.time()),
                        "c_date": c_date
                    })
    except Exception as e:
        print(f"[FNO Results] Error fetching event calendar: {e}")

    # Step 4: Batch fetch technicals in parallel for speed
    all_symbols = [c["symbol"] for c in raw_candidates]
    tech_map = get_technicals_map(all_symbols)

    results = []
    for c in raw_candidates:
        sym = c["symbol"]
        comp_name = c["company_name"]
        tech = tech_map.get(sym) or {}

        price = tech.get("current_price", 0.0)
        rsi = tech.get("rsi", 50.0)
        pivots = tech.get("pivots", {})
        del_pct = tech.get("delivery_pct", 55.0)
        whale_note = tech.get("whale_note", "Active F&O derivatives volume")

        is_declared = (c["type"] == "declared")
        status_label = "DECLARED TODAY" if is_declared else f"BOARD MEETING ({c.get('c_date', 'Upcoming')})"

        if is_declared:
            summary = (
                f"📌 *F&O Quarterly Earnings Released*:\n"
                f"{comp_name} ({sym}) officially submitted its financial results to the exchange today.\n\n"
                f"📊 *Actionable Signal*:\n"
                f"• Status: {status_label}\n"
                f"• CMP: ₹{price:,.2f} | 14-D RSI: {rsi} ({'Bullish Momentum' if rsi <= 40 else ('Overbought' if rsi >= 70 else 'Neutral')})\n"
                f"• Pivot Levels: Floor (S1) ₹{pivots.get('s1', 0):,.2f} | Ceiling (R1) ₹{pivots.get('r1', 0):,.2f}\n"
                f"• Delivery Accumulation: {del_pct}% ({'Whale Accumulation' if del_pct >= 60 else 'Routine Flow'})\n\n"
                f"🎯 *Takeaway*: Watch for post-result continuation or open-interest shift."
            )
        else:
            summary = (
                f"⏱️ *F&O Result Board Meeting Scheduled*:\n"
                f"{comp_name} ({sym}) has convened a Board Meeting on {c.get('c_date', 'Today')} to consider Quarterly Financial Results.\n\n"
                f"📊 *Pre-Result Positioning*:\n"
                f"• CMP: ₹{price:,.2f} | 14-D RSI: {rsi}\n"
                f"• Pivot Levels: S1 ₹{pivots.get('s1', 0):,.2f} | R1 ₹{pivots.get('r1', 0):,.2f}\n"
                f"• Delivery Absorption: {del_pct}% ({'High Delivery Inflow' if del_pct >= 60 else 'Standard Churn'})\n\n"
                f"🎯 *Pre-Result Stance*: Watch for post-announcement IV crush & breakout above R1."
            )

        results.append({
            "id": f"fno_{sym}_{c['seq_id']}",
            "symbol": sym,
            "company_name": comp_name,
            "subject": c["subject"],
            "details": c["details"],
            "pdf_url": c["pdf_url"],
            "announced_at": c["time_str"],
            "ai_summary": summary,
            "sentiment": "BULLISH" if (rsi <= 40 or del_pct >= 60) else "NEUTRAL",
            "current_price": price,
            "rsi": rsi,
            "support_1": pivots.get("s1", 0.0),
            "resistance_1": pivots.get("r1", 0.0),
            "delivery_pct": del_pct,
            "whale_note": whale_note,
            "is_fno": True,
            "result_status": status_label
        })

    _CACHE_DATA = results
    _CACHE_TIMESTAMP = time.time()
    return results
