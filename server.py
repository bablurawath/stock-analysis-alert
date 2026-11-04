import os
import sys
import threading
import time
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

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

app = FastAPI(title=APP_TITLE)

# Background bot runner thread
def background_worker():
    print("=" * 60)
    print(f"🚀 [Render Cloud] {APP_TITLE} Worker Started")
    print(f"📡 Watchlist: {', '.join(DEFAULT_WATCHLIST)}")
    print(f"⏱️ Interval: {POLL_INTERVAL}s")
    print("=" * 60)

    seen_ids = load_seen_ids()

    while True:
        try:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{now_str}] Polling live exchange feed...")
            process_cycle(seen_ids)
        except Exception as e:
            print(f"[Worker Error] {e}")

        time.sleep(POLL_INTERVAL)

@app.on_event("startup")
def on_startup():
    # Start bot loop in separate thread so it doesn't block web server
    bot_thread = threading.Thread(target=background_worker, daemon=True)
    bot_thread.start()

@app.get("/", response_class=HTMLResponse)
def home():
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>{APP_TITLE} - Status</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #f8fafc; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
            .card {{ background: #1e293b; padding: 2.5rem; border-radius: 1rem; border: 1px solid #334155; text-align: center; max-width: 480px; box-shadow: 0 10px 25px rgba(0,0,0,0.5); }}
            .badge {{ display: inline-block; background: #10b981; color: #022c22; font-weight: bold; padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.875rem; margin-bottom: 1rem; }}
            h1 {{ margin: 0 0 0.5rem 0; font-size: 1.5rem; }}
            p {{ color: #94a3b8; font-size: 0.95rem; line-height: 1.5; }}
            .btn {{ display: inline-block; margin-top: 1.5rem; background: #2563eb; color: #fff; text-decoration: none; padding: 0.75rem 1.5rem; border-radius: 0.5rem; font-weight: 600; transition: background 0.2s; }}
            .btn:hover {{ background: #1d4ed8; }}
        </style>
    </head>
    <body>
        <div class="card">
            <span class="badge">● SYSTEM ACTIVE</span>
            <h1>{APP_TITLE}</h1>
            <p>Real-time corporate earnings, financial filing summaries, and market intelligence powered by Google Gemini AI.</p>
            <p><strong>Status:</strong> Monitoring NSE/BSE corporate filings every {POLL_INTERVAL}s.</p>
            <a href="https://t.me/krishstockalert" target="_blank" class="btn">Join Telegram Channel</a>
        </div>
    </body>
    </html>
    """

@app.get("/health")
def health():
    return {"status": "ok", "app": APP_TITLE, "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("server:app", host="0.0.0.0", port=port)
