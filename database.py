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

        conn.commit()

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
