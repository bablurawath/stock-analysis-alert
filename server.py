import os
import sys
import threading
import time
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse

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

app = FastAPI(title=APP_TITLE)

def background_worker():
    """Continuous 60-second poller for live market announcements."""
    print("=" * 60)
    print(f"🚀 [Web Server] {APP_TITLE} Background Engine Online")
    print(f"📡 Watchlist: {', '.join(DEFAULT_WATCHLIST)}")
    print(f"⏱️ Polling Interval: {POLL_INTERVAL} seconds")
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

# API Endpoints for Website Frontend
@app.get("/api/announcements")
def api_announcements(search: Optional[str] = "", limit: int = 50):
    """Returns cached announcements from the database (₹0 extra LLM calls)."""
    data = get_recent_announcements(limit=limit, search=search)
    return JSONResponse(content={"count": len(data), "announcements": data})

@app.get("/api/technicals/{symbol}")
def api_technicals(symbol: str):
    """Fetches real-time RSI, Support, and Resistance for any stock."""
    tech = get_stock_technicals(symbol)
    if not tech:
        return JSONResponse(status_code=404, content={"error": "Symbol not found or data unavailable"})
    return JSONResponse(content=tech)

@app.get("/health")
def health():
    return {"status": "ok", "app": APP_TITLE, "timestamp": datetime.now().isoformat()}

# Main Website Dashboard
@app.get("/", response_class=HTMLResponse)
def dashboard():
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{APP_TITLE} - AI Stock Intelligence</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        body {{ background-color: #0b0f19; color: #f3f4f6; }}
        .glass-card {{ background: rgba(17, 24, 39, 0.7); backdrop-filter: blur(12px); border: 1px solid rgba(255, 255, 255, 0.08); }}
        .glass-card:hover {{ border-color: rgba(59, 130, 246, 0.4); transform: translateY(-2px); transition: all 0.2s ease; }}
    </style>
</head>
<body class="min-h-screen flex flex-col font-sans">

    <!-- Top Navigation Bar -->
    <header class="border-b border-gray-800 bg-gray-900/60 sticky top-0 z-50 backdrop-blur-md">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
            <div class="flex items-center space-x-3">
                <div class="w-9 h-9 rounded-lg bg-blue-600 flex items-center justify-center font-bold text-white shadow-lg shadow-blue-500/30">
                    <i class="fa-solid fa-bolt"></i>
                </div>
                <span class="font-bold text-xl tracking-tight text-white">{APP_TITLE}</span>
                <span class="hidden md:inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    <span class="w-1.5 h-1.5 mr-1.5 rounded-full bg-emerald-400 animate-pulse"></span> Live 60s Stream
                </span>
            </div>
            <div class="flex items-center space-x-4">
                <a href="https://t.me/krishstockalert" target="_blank" class="inline-flex items-center space-x-2 bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg text-sm font-semibold shadow-md transition shadow-blue-600/20">
                    <i class="fa-brands fa-telegram text-base"></i>
                    <span>Join Telegram Alerts</span>
                </a>
            </div>
        </div>
    </header>

    <!-- Hero & Search Header -->
    <section class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-10 pb-6 w-full">
        <div class="text-center max-w-3xl mx-auto mb-8">
            <h1 class="text-3xl sm:text-4xl font-extrabold tracking-tight text-white mb-3">
                Real-Time AI Market Filings & 360° Technicals
            </h1>
            <p class="text-gray-400 text-sm sm:text-base">
                Plain-English corporate earnings breakdowns synthesized with <strong>RSI</strong>, <strong>Support/Resistance</strong>, and <strong>Smart Money Footprints</strong>.
            </p>
        </div>

        <!-- Filter Bar -->
        <div class="glass-card rounded-xl p-3 flex flex-col sm:flex-row items-center gap-3 shadow-xl">
            <div class="relative flex-1 w-full">
                <i class="fa-solid fa-search absolute left-4 top-3.5 text-gray-500 text-sm"></i>
                <input type="text" id="searchInput" placeholder="Search by Stock (e.g., TCS, RELIANCE, INFY) or keyword..." 
                    class="w-full pl-10 pr-4 py-2.5 bg-gray-900/80 border border-gray-700/60 rounded-lg text-sm focus:outline-none focus:border-blue-500 transition text-white placeholder-gray-500">
            </div>
            <button onclick="loadAnnouncements()" class="w-full sm:w-auto px-5 py-2.5 bg-gray-800 hover:bg-gray-700 text-gray-200 rounded-lg text-sm font-medium border border-gray-700 transition flex items-center justify-center space-x-2">
                <i class="fa-solid fa-arrows-rotate"></i>
                <span>Refresh</span>
            </button>
        </div>
    </section>

    <!-- Content Feed -->
    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-16 flex-1 w-full">
        <div id="loading" class="text-center py-16 text-gray-400">
            <i class="fa-solid fa-circle-notch fa-spin text-3xl text-blue-500 mb-3"></i>
            <p class="text-sm">Fetching verified market disclosures...</p>
        </div>

        <div id="cardsGrid" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 hidden">
            <!-- Cards injected via JavaScript -->
        </div>

        <div id="emptyState" class="text-center py-16 text-gray-500 hidden">
            <i class="fa-regular fa-folder-open text-4xl mb-3"></i>
            <p class="text-base font-medium">No announcements match your filter.</p>
        </div>
    </main>

    <!-- Footer -->
    <footer class="border-t border-gray-800/80 py-6 text-center text-xs text-gray-500">
        <p>© 2026 {APP_TITLE}. Educational market analysis powered by Google Gemini AI. Not SEBI registered investment advice.</p>
    </footer>

    <!-- Interactive JavaScript -->
    <script>
        async function loadAnnouncements() {{
            const search = document.getElementById('searchInput').value;
            const grid = document.getElementById('cardsGrid');
            const loading = document.getElementById('loading');
            const empty = document.getElementById('emptyState');

            loading.classList.remove('hidden');
            grid.classList.add('hidden');
            empty.classList.add('hidden');

            try {{
                const res = await fetch(`/api/announcements?search=${{encodeURIComponent(search)}}`);
                const data = await res.json();
                const items = data.announcements || [];

                loading.classList.add('hidden');

                if (items.length === 0) {{
                    empty.classList.remove('hidden');
                    return;
                }}

                grid.innerHTML = items.map(item => {{
                    const sentimentClass = item.sentiment === 'BULLISH' 
                        ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' 
                        : (item.sentiment === 'BEARISH' ? 'bg-rose-500/10 text-rose-400 border-rose-500/20' : 'bg-amber-500/10 text-amber-400 border-amber-500/20');
                    
                    const rsiColor = item.rsi >= 70 ? 'text-rose-400' : (item.rsi <= 35 ? 'text-emerald-400' : 'text-amber-400');

                    // Format AI markdown to HTML breaks
                    const formattedSummary = (item.ai_summary || '')
                        .replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>')
                        .replace(/\\*(.*?)\\*/g, '<strong>$1</strong>')
                        .replace(/\\n/g, '<br>');

                    return `
                        <div class="glass-card rounded-xl p-5 flex flex-col justify-between shadow-lg">
                            <div>
                                <div class="flex items-start justify-between mb-3">
                                    <div>
                                        <div class="flex items-center space-x-2">
                                            <span class="text-xs font-bold px-2 py-0.5 rounded bg-blue-500/20 text-blue-400 border border-blue-500/30">${{item.symbol || 'NSE'}}</span>
                                            ${{item.current_price ? `<span class="text-xs font-mono font-semibold text-gray-300">₹${{Number(item.current_price).toLocaleString('en-IN')}}</span>` : ''}}
                                        </div>
                                        <h2 class="text-base font-bold text-white mt-1.5 leading-snug line-clamp-1">${{item.company_name}}</h2>
                                    </div>
                                    <span class="text-[11px] font-semibold px-2 py-0.5 rounded border ${{sentimentClass}}">
                                        ${{item.sentiment}}
                                    </span>
                                </div>

                                <div class="text-xs font-medium text-gray-400 mb-3 line-clamp-2">
                                    <i class="fa-regular fa-file-lines mr-1 text-gray-500"></i> ${{item.subject}}
                                </div>

                                <!-- Technical Indicators Strip -->
                                ${{item.rsi ? `
                                <div class="grid grid-cols-3 gap-2 py-2.5 px-3 rounded-lg bg-gray-900/60 border border-gray-800/80 text-[11px] mb-3">
                                    <div>
                                        <div class="text-gray-500">RSI (14)</div>
                                        <div class="font-bold ${{rsiColor}}">${{item.rsi}}</div>
                                    </div>
                                    <div>
                                        <div class="text-gray-500">Support (S1)</div>
                                        <div class="font-bold text-gray-200">₹${{Number(item.support_1).toLocaleString('en-IN')}}</div>
                                    </div>
                                    <div>
                                        <div class="text-gray-500">Resistance</div>
                                        <div class="font-bold text-gray-200">₹${{Number(item.resistance_1).toLocaleString('en-IN')}}</div>
                                    </div>
                                </div>` : ''}}

                                <!-- AI Summary Box -->
                                <div class="text-xs text-gray-300 bg-gray-950/40 p-3 rounded-lg border border-gray-800/50 leading-relaxed max-h-48 overflow-y-auto mb-4">
                                    ${{formattedSummary}}
                                </div>
                            </div>

                            <div class="pt-3 border-t border-gray-800/60 flex items-center justify-between text-[11px] text-gray-500">
                                <span>${{item.announced_at || 'Recent'}}</span>
                                ${{item.pdf_url ? `
                                <a href="${{item.pdf_url}}" target="_blank" class="inline-flex items-center text-blue-400 hover:text-blue-300 font-semibold space-x-1">
                                    <span>Original PDF</span>
                                    <i class="fa-solid fa-arrow-up-right-from-square text-[10px]"></i>
                                </a>` : ''}}
                            </div>
                        </div>
                    `;
                }}).join('');

                grid.classList.remove('hidden');

            }} catch (err) {{
                loading.classList.add('hidden');
                grid.innerHTML = `<div class="col-span-3 text-center text-rose-400">Failed to load feed: ${{err.message}}</div>`;
                grid.classList.remove('hidden');
            }}
        }}

        // Trigger search on Enter key
        document.getElementById('searchInput').addEventListener('keyup', (e) => {{
            if (e.key === 'Enter') loadAnnouncements();
        }});

        // Load initially
        loadAnnouncements();
    </script>
</body>
</html>
    """

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("server:app", host="0.0.0.0", port=port)
