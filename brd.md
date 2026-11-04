# Business Requirement Document (BRD) & System Blueprint
## Project: EquiSense AI Alternative — Real-Time Stock Intelligence Platform & Alert Notifier

---

## 1. Executive Summary & Product Vision

### 1.1 Problem Statement
Retail investors tracking Indian equities (NSE & BSE) struggle during earnings seasons with dense, technical regulatory disclosures (often 30–100+ pages per filing). Furthermore, standard news alerts lack technical context—investors frequently buy good news when a stock is already overbought at key resistance, leading to capital losses.

### 1.2 Product Vision & Value Proposition
To build an institutional-grade, **₹0-cost** market intelligence platform that:
1. **Monitors Live Regulatory Filings:** Ingests official NSE corporate announcements within 60 seconds of release.
2. **Extracts AI Financial Intelligence:** Uses Google Gemini 3.5 Flash to generate plain-English summaries (Revenue YoY/QoQ, EBITDA margins, PAT, red flags, guidance).
3. **Calculates 360° Technical Indicators:** Computes real-time **14-day RSI**, **Support (S1/S2)** & **Resistance (R1/R2)** pivot levels, and **52-week price ranges**.
4. **Delivers Universal Stock Scanning:** Allows users to search and scan **any Indian stock** on-demand (e.g., `RELIANCE`, `TCS`, `INFY`) for instant live technical analysis.
5. **Dual-Channel Delivery:** Broadcasts alerts to an unlimited-member **Telegram Channel** (`@krishstockalert`) and serves a responsive **React 18 Web Dashboard** (`https://stock-analysis-alert.onrender.com`).
6. **Zero Marginal LLM Cost:** Implements database caching ("Analyze Once, Serve Infinite Times") to serve thousands of web visitors for ₹0 extra API cost.

---

## 2. High-Level Architecture & Component Flow

```
┌────────────────────────────────────────────────────────┐
│             NSE India Corporate Feed                   │
│   (https://www.nseindia.com/api/corporate-announcements)│
└──────────────────────────┬─────────────────────────────┘
                           │ Poll every 60s
                           ▼
┌────────────────────────────────────────────────────────┐
│             1. Ingestion & Pre-Seeding                 │
│                 (exchange_client.py)                   │
│  - Standardizes announcements, captures PDF links      │
│  - Auto-seeds recent disclosures on initial startup    │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│             2. AI Analysis & Technical Engine          │
│    • Google Gemini Flash (ai_engine.py)                │
│      - Strict English translation & structured metrics │
│    • Technicals Calculator (technicals.py)             │
│      - Real-time CMP, 14-day RSI, S1/S2/R1/R2 Pivots   │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│             3. Database Caching Layer                  │
│                    (database.py)                       │
│  - SQLite (stock_alerts.db)                            │
│  - Prevents duplicate Gemini calls; serves web in 2ms  │
└────────────────────┬─────────────────────┬─────────────┘
                     │                     │
                     ▼                     ▼
┌───────────────────────────────┐ ┌───────────────────────────────┐
│     4. Telegram Dispatcher    │ │   5. React 18 Web Platform    │
│      (telegram_client.py)     │ │        (templates/index.html) │
│ - Broadcasts formatted 360°   │ │ - Modular box-wise stock cards│
│   alerts to @krishstockalert  │ │ - Live on-demand stock search │
│ - Clickable official PDF link │ │ - 360° deep-dive modal view   │
└───────────────────────────────┘ └───────────────────────────────┘
```

---

## 3. Technical Component Breakdown

| Component | File Path | Function & Role |
| :--- | :--- | :--- |
| **Web & API Server** | `server.py` | FastAPI application that serves the React 18 frontend, hosts REST endpoints (`/api/announcements`, `/api/technicals/{symbol}`), and runs the background poller thread. |
| **Frontend Platform** | `templates/index.html` | React 18 Single-Page Application (SPA) with Tailwind CSS, dark-mode styling, live search bar, quick-scan chips, and responsive modal dialogs. |
| **Technicals Engine** | `technicals.py` | Fetches historical price candles and computes 14-day RSI, Classic Pivot Points (S1, S2, R1, R2), and 52-week High/Low on-demand. |
| **Database Caching** | `database.py` | SQLite schema and query methods (`save_announcement`, `get_recent_announcements`) ensuring zero repeated LLM costs. |
| **Exchange Ingestion** | `exchange_client.py` | Direct integration with NSE India corporate announcement feeds and automated PDF attachment downloading. |
| **AI Intelligence** | `ai_engine.py` | Google Gemini 3.5 Flash engine with automatic model fallback (`gemini-3.5-flash` → `gemini-3.1-flash-lite`) and strict English output enforcement. |
| **Telegram Dispatcher** | `telegram_client.py` | Message formatter and dispatcher connecting to the Telegram Bot API with markdown error recovery. |
| **Orchestrator Daemon** | `main.py` | Core cycle logic that processes filings, deduplicates announcements, enriches with technicals, caches, and triggers alerts. |
| **Configuration** | `config.py`, `.env` | Environment secrets, polling intervals, custom branding (`APP_TITLE`), and stock watchlist definitions. |

---

## 4. Web Dashboard: Modular Box-Wise Layout

Each stock card in the React interface is organized into **6 modular boxes**:

* **Box 1: Header & Valuation**  
  Ticker symbol badge, Current Market Price (₹), Full Company Name, and Bullish/Bearish tag.
* **Box 2: Technical Indicators**  
  **14-Day RSI** with dynamic color tags (Green for Oversold < 35, Red for Overbought > 70) alongside daily **Support (S1)** and **Resistance (R1)** pivot prices.
* **Box 3: AI Financial Intelligence**  
  Plain-English summary of Revenue YoY/QoQ, EBITDA margins, PAT growth, and key management takeaways.
* **Box 4: Smart Money & Ownership**  
  Quarterly FII, Mutual Fund, and Retail ownership shifts with promoter pledge monitoring.
* **Box 5: Regulatory Verification**  
  Direct download link to the official signed exchange PDF.
* **Box 6: 360° Forensic Modal**  
  Button opening a full-screen interactive deep-dive modal.

---

## 5. Universal On-Demand Stock Scanner

To ensure users can inspect **any company** even if they have not released a filing today:
1. Users enter any NSE symbol into the search bar (e.g. `RELIANCE`, `TCS`, `TATAMOTORS`, `ZOMATO`).
2. Clicking **Scan ⚡** triggers `/api/technicals/{symbol}`.
3. The engine fetches real-time quote data, calculates RSI and Support/Resistance, and dynamically injects a live 360° intelligence card into the view.
4. **Quick-Scan Chips** (`+RELIANCE`, `+TCS`, `+INFY`, `+HDFCBANK`, etc.) allow one-click scanning.

---

## 6. Sample Output: Delivered Telegram Alert

```markdown
⚡ STOCK MARKET ALERT: RELIANCE
🏢 RELIANCE INDUSTRIES LIMITED (CMP: ₹1,311.00)
📋 Subject: Outcome of Board Meeting & Financial Results
🕒 04-Nov-2026, 04:15 PM

📊 1. FINANCIAL INTELLIGENCE (English):
🎯 Executive Summary:
Steady quarterly operational performance driven by consumer businesses (Jio & Retail) offsetting subdued O2C petrochemical margins.

📊 Key Financial Highlights:
• Revenue: ₹2,35,481 Cr (+3.5% YoY)
• EBITDA Margin: 18.2% (-30 bps YoY)
• Net Profit (PAT): ₹19,101 Cr (+4.8% YoY)

💡 Key Business Updates:
• Jio 5G subscriber additions remain strong with ARPU expansion.
• Retail segment footfalls increased 14% YoY across grocery & fashion.

⚠️ Red Flags / Cautionary Points:
• Lower global refining margins (GRMs) continue to moderate O2C earnings.

📈 Sentiment: Bullish 🟢

📈 2. TECHNICAL SETUP:
• RSI (14): 67.14 (Neutral - nearing 70 overbought threshold)
• Key Support (S1): ₹1,290.63 | Resistance (R1): ₹1,316.53
• 52-Week Range: ₹1,152.20 - ₹1,611.80

🏦 3. SMART MONEY INSIGHT:
• FII & Mutual Fund institutional holdings monitored quarterly. Baseline intact.
───────────────────
📄 [Open Original Exchange Document](https://nsearchives.nseindia.com/...)
```

---

## 7. Cloud Deployment & Operational Runbook

### 7.1 Production Environment (Render.com)
* **Hosted URL:** [https://stock-analysis-alert.onrender.com](https://stock-analysis-alert.onrender.com)
* **Telegram Channel:** [@krishstockalert](https://t.me/krishstockalert)
* **Build Command:** `pip install -r requirements.txt`
* **Start Command:** `python server.py`
* **Instance Type:** Free ($0/month, 512 MB RAM)
* **Keep-Alive:** Monitored via UptimeRobot pinging `/health` every 5 minutes.

### 7.2 Local Development Commands
```powershell
# Navigate to project folder
cd D:\wampgc\www\stock-ai-notifier

# Run system verification & diagnostics
python test_setup.py

# Run live React web server & background bot
python server.py
```
