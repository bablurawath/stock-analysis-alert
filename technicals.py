import urllib.request
import json
import urllib3
from typing import Dict, Any, Optional

urllib3.disable_warnings()

def calculate_rsi(prices: list, period: int = 14) -> float:
    """
    Calculates the 14-period Relative Strength Index (RSI).
    """
    if len(prices) < period + 1:
        return 50.0  # Default neutral if insufficient data

    deltas = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains = [d if d > 0 else 0.0 for d in deltas]
    losses = [-d if d < 0 else 0.0 for d in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return round(rsi, 2)

def calculate_pivots(high: float, low: float, close: float) -> Dict[str, float]:
    """
    Calculates Classic Pivot Points (Support & Resistance).
    """
    pivot = (high + low + close) / 3.0
    r1 = (2 * pivot) - low
    s1 = (2 * pivot) - high
    r2 = pivot + (high - low)
    s2 = pivot - (high - low)

    return {
        "pivot": round(pivot, 2),
        "r1": round(r1, 2),
        "s1": round(s1, 2),
        "r2": round(r2, 2),
        "s2": round(s2, 2)
    }

def get_stock_technicals(symbol: str) -> Optional[Dict[str, Any]]:
    """
    Fetches daily price data from free market endpoints and computes:
    - Current Price & 52-Week Range
    - 14-day RSI (Oversold / Neutral / Overbought)
    - Pivot Points (Support 1, 2 & Resistance 1, 2)
    """
    clean_symbol = symbol.strip().upper().replace("&", "_")
    yahoo_ticker = f"{clean_symbol}.NS"
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{yahoo_ticker}?interval=1d&range=3mo"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0"
    }

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        result = data.get("chart", {}).get("result", [])[0]
        meta = result.get("meta", {})
        indicators = result.get("indicators", {}).get("quote", [])[0]

        closes = [c for c in indicators.get("close", []) if c is not None]
        highs = [h for h in indicators.get("high", []) if h is not None]
        lows = [l for l in indicators.get("low", []) if l is not None]

        if not closes:
            return None

        current_price = round(meta.get("regularMarketPrice", closes[-1]), 2)
        high52 = round(meta.get("fiftyTwoWeekHigh", max(highs)), 2)
        low52 = round(meta.get("fiftyTwoWeekLow", min(lows)), 2)

        # Calculate RSI
        rsi_val = calculate_rsi(closes, period=14)
        if rsi_val >= 70:
            rsi_badge = "Overbought 🔴"
        elif rsi_val <= 35:
            rsi_badge = "Oversold 🟢"
        else:
            rsi_badge = "Neutral 🟡"

        # Calculate Support & Resistance from last closed daily candle
        last_high = highs[-2] if len(highs) >= 2 else highs[-1]
        last_low = lows[-2] if len(lows) >= 2 else lows[-1]
        last_close = closes[-2] if len(closes) >= 2 else closes[-1]
        pivots = calculate_pivots(last_high, last_low, last_close)

        return {
            "symbol": clean_symbol,
            "current_price": current_price,
            "52w_high": high52,
            "52w_low": low52,
            "rsi": rsi_val,
            "rsi_badge": rsi_badge,
            "pivots": pivots
        }
    except Exception as e:
        print(f"[Technicals] Error fetching data for {symbol}: {e}")
        return None
