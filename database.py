import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

DB_PATH = Path(__file__).resolve().parent / "stock_alerts.db"

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the SQLite schema."""
    with get_connection() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS announcements (
            id TEXT PRIMARY KEY,
            symbol TEXT,
            company_name TEXT,
            subject TEXT,
            details TEXT,
            pdf_url TEXT,
            announced_at TEXT,
            ai_summary TEXT,
            sentiment TEXT,
            current_price REAL,
            rsi REAL,
            support_1 REAL,
            resistance_1 REAL,
            smart_money_note TEXT,
            delivery_pct REAL DEFAULT 50.0,
            whale_note TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        # Safe migration if columns don't exist
        try:
            conn.execute("ALTER TABLE announcements ADD COLUMN delivery_pct REAL DEFAULT 50.0")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE announcements ADD COLUMN whale_note TEXT DEFAULT ''")
        except Exception:
            pass

        # Dedicated Persistent Table for Quality Accumulation Stocks
        conn.execute("""
        CREATE TABLE IF NOT EXISTS accumulation_stocks (
            symbol TEXT PRIMARY KEY,
            category TEXT,
            exchange TEXT,
            name TEXT,
            sector TEXT,
            current_price REAL,
            high52 REAL,
            low52 REAL,
            discount_from_peak REAL,
            range_pct REAL,
            rsi REAL,
            rsi_badge TEXT,
            accumulation_score INTEGER,
            grade TEXT,
            verdict TEXT,
            delivery_pct REAL,
            pivots_json TEXT,
            tranches_json TEXT,
            upside_json TEXT,
            moat TEXT,
            sentiment_catalyst TEXT,
            promoter_status TEXT,
            institution_status TEXT,
            roce TEXT,
            debt_equity TEXT,
            sales_growth_yoy TEXT,
            pat_growth_yoy TEXT,
            recent_quarters_trend TEXT,
            divergence_note TEXT,
            promoter_integrity_note TEXT,
            whale_note TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        conn.commit()

def save_accumulation_stock(stock: Dict[str, Any]):
    """Saves or updates an accumulation stock record on disk in SQLite."""
    import json
    with get_connection() as conn:
        conn.execute("""
        INSERT OR REPLACE INTO accumulation_stocks (
            symbol, category, exchange, name, sector, current_price,
            high52, low52, discount_from_peak, range_pct, rsi, rsi_badge,
            accumulation_score, grade, verdict, delivery_pct,
            pivots_json, tranches_json, upside_json, moat, sentiment_catalyst,
            promoter_status, institution_status, roce, debt_equity,
            sales_growth_yoy, pat_growth_yoy, recent_quarters_trend,
            divergence_note, promoter_integrity_note, whale_note, updated_at
        ) VALUES (
            :symbol, :category, :exchange, :name, :sector, :current_price,
            :high52, :low52, :discount_from_peak, :range_pct, :rsi, :rsi_badge,
            :accumulation_score, :grade, :verdict, :delivery_pct,
            :pivots_json, :tranches_json, :upside_json, :moat, :sentiment_catalyst,
            :promoter_status, :institution_status, :roce, :debt_equity,
            :sales_growth_yoy, :pat_growth_yoy, :recent_quarters_trend,
            :divergence_note, :promoter_integrity_note, :whale_note, CURRENT_TIMESTAMP
        )
        """, {
            "symbol": stock.get("symbol"),
            "category": stock.get("category"),
            "exchange": stock.get("exchange"),
            "name": stock.get("name"),
            "sector": stock.get("sector"),
            "current_price": stock.get("current_price"),
            "high52": stock.get("52w_high"),
            "low52": stock.get("52w_low"),
            "discount_from_peak": stock.get("discount_from_peak"),
            "range_pct": stock.get("range_pct"),
            "rsi": stock.get("rsi"),
            "rsi_badge": stock.get("rsi_badge"),
            "accumulation_score": stock.get("accumulation_score"),
            "grade": stock.get("grade"),
            "verdict": stock.get("verdict"),
            "delivery_pct": stock.get("delivery_pct"),
            "pivots_json": json.dumps(stock.get("pivots", {})),
            "tranches_json": json.dumps(stock.get("tranches", {})),
            "upside_json": json.dumps(stock.get("upside", {})),
            "moat": stock.get("moat", ""),
            "sentiment_catalyst": stock.get("sentiment_catalyst", ""),
            "promoter_status": stock.get("promoter_status", ""),
            "institution_status": stock.get("institution_status", ""),
            "roce": stock.get("roce", ""),
            "debt_equity": stock.get("debt_equity", ""),
            "sales_growth_yoy": stock.get("sales_growth_yoy", ""),
            "pat_growth_yoy": stock.get("pat_growth_yoy", ""),
            "recent_quarters_trend": stock.get("recent_quarters_trend", ""),
            "divergence_note": stock.get("divergence_note", ""),
            "promoter_integrity_note": stock.get("promoter_integrity_note", ""),
            "whale_note": stock.get("whale_note", "")
        })
        conn.commit()

def get_saved_accumulation_stocks(category: str = "ALL") -> List[Dict[str, Any]]:
    """Loads cached accumulation stocks from SQLite database on disk."""
    import json
    init_db()
    with get_connection() as conn:
        if category and category.upper() != "ALL":
            rows = conn.execute(
                "SELECT * FROM accumulation_stocks WHERE category = ? ORDER BY accumulation_score DESC",
                (category.upper(),)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM accumulation_stocks ORDER BY accumulation_score DESC"
            ).fetchall()

        results = []
        for r in rows:
            try:
                pivots = json.loads(r["pivots_json"]) if r["pivots_json"] else {}
                tranches = json.loads(r["tranches_json"]) if r["tranches_json"] else {}
                upside = json.loads(r["upside_json"]) if r["upside_json"] else {}
            except Exception:
                pivots, tranches, upside = {}, {}, {}

            results.append({
                "symbol": r["symbol"],
                "category": r["category"],
                "exchange": r["exchange"],
                "name": r["name"],
                "sector": r["sector"],
                "current_price": r["current_price"],
                "52w_high": r["high52"],
                "52w_low": r["low52"],
                "discount_from_peak": r["discount_from_peak"],
                "range_pct": r["range_pct"],
                "rsi": r["rsi"],
                "rsi_badge": r["rsi_badge"],
                "accumulation_score": r["accumulation_score"],
                "grade": r["grade"],
                "verdict": r["verdict"],
                "delivery_pct": r["delivery_pct"],
                "pivots": pivots,
                "tranches": tranches,
                "upside": upside,
                "moat": r["moat"],
                "sentiment_catalyst": r["sentiment_catalyst"],
                "promoter_status": r["promoter_status"],
                "institution_status": r["institution_status"],
                "roce": r["roce"],
                "debt_equity": r["debt_equity"],
                "sales_growth_yoy": r["sales_growth_yoy"],
                "pat_growth_yoy": r["pat_growth_yoy"],
                "recent_quarters_trend": r["recent_quarters_trend"],
                "divergence_note": r["divergence_note"],
                "promoter_integrity_note": r["promoter_integrity_note"],
                "whale_note": r["whale_note"],
                "updated_at": r["updated_at"]
            })
        return results

def save_announcement(data: Dict[str, Any]):
    """Saves or updates an announcement breakdown."""
    payload = {
        "id": data.get("id"),
        "symbol": data.get("symbol"),
        "company_name": data.get("company_name"),
        "subject": data.get("subject"),
        "details": data.get("details", ""),
        "pdf_url": data.get("pdf_url", ""),
        "announced_at": data.get("announced_at", "Recently"),
        "ai_summary": data.get("ai_summary", ""),
        "sentiment": data.get("sentiment", "NEUTRAL"),
        "current_price": data.get("current_price", 0.0),
        "rsi": data.get("rsi", 50.0),
        "support_1": data.get("support_1", 0.0),
        "resistance_1": data.get("resistance_1", 0.0),
        "smart_money_note": data.get("smart_money_note", ""),
        "delivery_pct": data.get("delivery_pct", 50.0),
        "whale_note": data.get("whale_note", "")
    }

    with get_connection() as conn:
        conn.execute("""
        INSERT OR REPLACE INTO announcements (
            id, symbol, company_name, subject, details, pdf_url,
            announced_at, ai_summary, sentiment, current_price,
            rsi, support_1, resistance_1, smart_money_note,
            delivery_pct, whale_note, created_at
        ) VALUES (
            :id, :symbol, :company_name, :subject, :details, :pdf_url,
            :announced_at, :ai_summary, :sentiment, :current_price,
            :rsi, :support_1, :resistance_1, :smart_money_note,
            :delivery_pct, :whale_note, CURRENT_TIMESTAMP
        )
        """, payload)
        conn.commit()

def get_recent_announcements(limit: int = 50, search: str = "") -> List[Dict[str, Any]]:
    """Retrieves cached announcements for the website frontend."""
    with get_connection() as conn:
        if search:
            query = """
            SELECT * FROM announcements 
            WHERE symbol LIKE ? OR company_name LIKE ? OR subject LIKE ?
            ORDER BY created_at DESC LIMIT ?
            """
            pattern = f"%{search.strip().upper()}%"
            rows = conn.execute(query, (pattern, pattern, pattern, limit)).fetchall()
        else:
            query = "SELECT * FROM announcements ORDER BY created_at DESC LIMIT ?"
            rows = conn.execute(query, (limit,)).fetchall()

        return [dict(row) for row in rows]

# Auto-initialize on import
init_db()
