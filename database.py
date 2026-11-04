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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        conn.commit()

def save_announcement(data: Dict[str, Any]):
    """Saves or updates an announcement breakdown."""
    with get_connection() as conn:
        conn.execute("""
        INSERT OR REPLACE INTO announcements (
            id, symbol, company_name, subject, details, pdf_url,
            announced_at, ai_summary, sentiment, current_price,
            rsi, support_1, resistance_1, smart_money_note, created_at
        ) VALUES (
            :id, :symbol, :company_name, :subject, :details, :pdf_url,
            :announced_at, :ai_summary, :sentiment, :current_price,
            :rsi, :support_1, :resistance_1, :smart_money_note, CURRENT_TIMESTAMP
        )
        """, data)
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

