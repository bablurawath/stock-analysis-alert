import os
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

from config import (
    POLL_INTERVAL,
    DEFAULT_WATCHLIST,
    APP_TITLE
)
from main import load_seen_ids, process_cycle
from database import get_recent_announcements
from technicals import get_stock_technicals

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_FILE = BASE_DIR / "templates" / "index.html"

app = FastAPI(title=APP_TITLE)

def background_worker():
    """Continuous poller for live exchange announcements."""
    print("=" * 60)
    print(f"🚀 [React Server] {APP_TITLE} Background Engine Online")
    print(f"📡 Watchlist: {', '.join(DEFAULT_WATCHLIST)}")
    print(f"⏱️ Polling Interval: {POLL_INTERVAL}s")
    print("=" * 60)

    seen_ids = load_seen_ids()

    while True:
        try:
            process_cycle(seen_ids)
        except Exception as e:
            print(f"[Worker Error] {e}")

        time.sleep(POLL_INTERVAL)

@app.on_event("startup")
def on_startup():
    worker_thread = threading.Thread(target=background_worker, daemon=True)
    worker_thread.start()

# API Endpoints for React Frontend
@app.get("/api/announcements")
def api_announcements(search: Optional[str] = "", limit: int = 50):
    data = get_recent_announcements(limit=limit, search=search)
    return JSONResponse(content={"count": len(data), "announcements": data})

@app.get("/api/technicals/{symbol}")
def api_technicals(symbol: str):
    tech = get_stock_technicals(symbol)
    if not tech:
        return JSONResponse(status_code=404, content={"error": "Symbol not found or data unavailable"})
    return JSONResponse(content=tech)

@app.get("/health")
def health():
    return {"status": "ok", "app": APP_TITLE, "timestamp": datetime.now().isoformat()}

# Serve React 18 SPA
@app.get("/")
def serve_react_app():
    return FileResponse(TEMPLATE_FILE)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("server:app", host="0.0.0.0", port=port)
