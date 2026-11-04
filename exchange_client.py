import requests
import urllib3
from pathlib import Path
from config import TEMP_DIR

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

NSE_ANNOUNCEMENTS_URL = "https://www.nseindia.com/api/corporate-announcements?index=equities"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/"
}

def fetch_latest_announcements():
    """
    Fetches the latest corporate announcements from NSE India.
    Returns a list of standardized announcement dictionaries.
    """
    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        res = session.get(NSE_ANNOUNCEMENTS_URL, timeout=15, verify=False)
        res.raise_for_status()
        raw_items = res.json()

        standardized = []
        for item in raw_items:
            standardized.append({
                "id": str(item.get("seq_id") or item.get("dt")),
                "symbol": item.get("symbol", "").strip().upper(),
                "company_name": item.get("sm_name", "").strip(),
                "subject": item.get("desc", "").strip(),
                "details": item.get("attchmntText", "").strip(),
                "pdf_url": item.get("attchmntFile", "").strip(),
                "timestamp": item.get("an_dt", "").strip()
            })
        return standardized

    except Exception as e:
        print(f"[Exchange Client] Error fetching announcements: {e}")
        return []

def is_in_watchlist(symbol: str, company_name: str, watchlist: list) -> bool:
    """
    Checks if a stock symbol or company name matches the user's watchlist.
    """
    if "*" in watchlist:
        return True

    symbol_upper = (symbol or "").upper()
    comp_upper = (company_name or "").upper()

    for item in watchlist:
        item_upper = str(item).upper().strip()
        # Direct symbol match (e.g. TCS == TCS)
        if item_upper == symbol_upper:
            return True
        # Keyword match in company name (e.g. "TATA" in "TATA CONSULTANCY SERVICES")
        if item_upper in comp_upper:
            return True

    return False

def download_attachment(pdf_url: str, filename_hint: str = "filing.pdf") -> Path:
    """
    Downloads the PDF attachment from NSE archives.
    Returns local Path if successful, None otherwise.
    """
    if not pdf_url or not pdf_url.lower().endswith(".pdf"):
        return None

    session = requests.Session()
    session.headers.update(HEADERS)

    # Extract filename from url
    clean_name = pdf_url.split("/")[-1].split("?")[0]
    if not clean_name.endswith(".pdf"):
        clean_name = filename_hint
    local_path = TEMP_DIR / clean_name

    try:
        res = session.get(pdf_url, timeout=30, verify=False)
        res.raise_for_status()
        with open(local_path, "wb") as f:
            f.write(res.content)
        return local_path
    except Exception as e:
        print(f"[Exchange Client] Failed to download PDF {pdf_url}: {e}")
        return None

