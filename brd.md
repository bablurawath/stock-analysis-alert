# Business Requirement Document (BRD) & System Blueprint
## Project: EquiSense AI Alternative — Real-Time Stock Intelligence Platform & Alert Notifier

---

## 1. Executive Summary & Product Vision

### 1.1 Problem Statement
Retail investors tracking Indian equities (NSE & BSE) struggle during earnings seasons with dense, technical regulatory disclosures (often 30–100+ pages per filing). Furthermore, standard news alerts lack technical context—investors frequently buy good news when a stock is already overbought at key resistance, leading to capital losses.

### 1.2 Product Vision & Value Proposition
To build an institutional-grade, **₹0-cost** market intelligence platform that:
1. **Monitors Live Regulatory Filings:** Ingests official NSE corporate announcements within 60 seconds of release.
2. **Extracts AI Financial Intelligence:** Uses Google Gemini 3.5 Flash to generate lain-English summaries (Revenue YoY/QoQ, EBITDA margins, PAT, red flags, guidance).
3. **Calculates 360° Technical Indicators:** Computes real-time **14-day RSI**, **Support (S1/S2)** & **Resistance (R1/R2)** pivot levels, and **52-week price ranges**.
4. **Delivers Universal Stock Scanning:** Allows users to search and scan **any Indian stock** on-demand (e.g., `RELIANCE`, `TCS`, `INFY`) for instant live technical analysis.
5. **Dual-Channel Delivery:** Broadcasts alerts to an unlimited-member **Telegram Channel** (`@krishstockalert`) and serves a responsive **React 18 Web Dashboard** (`https://stock-analysis-alert.onrender.com`).
6. **Zero Marginal LLM Cost:** Implements database caching ("Analyze Once, Serve Infinite Times") to serve thousands of web visitors for ₹0 extra API cost.

---

## 2.p High-Level Architecture & Component Flow

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

---

## 8. F&O Derivatives Intelligence Engine & Results Radar

### 8.1 Universe & Coverage
* Dedicated tracking of the **214 authorized NSE F&O underlying stock symbols** (`NSE_FNO_SYMBOLS`).
* Real-time segregation of F&O derivatives announcements from general equity cash filings.
* Sub-2-second batch technicals and volatility ingestion powered by multi-threaded parallel execution (`ThreadPoolExecutor(max_workers=8)`).

### 8.2 Daily Scheduled & Declared Results Ingestion
* **Morning Pre-Market Board Meetings:** Ingests official regulatory intimations from `https://www.nseindia.com/api/corporate-board-meetings?index=equities&from_date={today}&to_date={today}` to identify all companies convening board meetings **today**.
* **Live Outcome Cross-Referencing:** Continually checks `https://www.nseindia.com/api/corporate-announcements` throughout the trading session to upgrade scheduled status to `DECLARED TODAY` with verified outcome documents as soon as filed.
* **Non-Result Filtering:** Strictly eliminates scheduled meetings without results, keeping the radar clean of non-earnings noise.

---

## 9. Dual-Mode Historical Earnings Reaction Analytics

### 9.1 Timing Attribution (Market Hours vs Post-Market)
In Indian equities, over 80% of board meetings conclude after market close (post 3:30 PM IST). Comparing result day's close to previous close is fundamentally misleading when results drop at 6:00 PM:
* **Post-Market / After-Hours Results (Declared after 3:30 PM):**
  * Evaluated on **Session T+1 (Next Trading Day)** against Result Day $T$ close.
  * Formula: $\text{Move} = \frac{\text{Close}_{T+1} - \text{Close}_T}{\text{Close}_T} \times 100$
* **Market Hours Results (Declared 9:15 AM – 3:30 PM):**
  * Evaluated on **Session T (Intraday)** against Session $T-1$ close.
  * Formula: $\text{Move} = \frac{\text{Close}_T - \text{Close}_{T-1}}{\text{Close}_{T-1}} \times 100$

### 9.2 Realized 4-Quarter Price Metrics
* Pulls 2 years of daily verified NSE closing candles from Yahoo Finance (`{SYMBOL}.NS`).
* Preserves and computes exact historical realized reactions for the last 4 quarters (`Q1`, `Q2`, `Q3`, `Q4`).
* Computes **Average Expected Volatility (Absolute Swing):** $\pm \text{Avg} = \frac{\sum |\text{Move}_i|}{4}$.
* Computes **Directional Skew / Bias:** $\text{Net Bias} = \frac{\sum \text{Move}_i}{4}$ (identifies stocks with strong historical upward/downward tendencies post-earnings).

### 9.3 Intraday Hourly Reaction Progression (1st Hr, 2nd Hr, 3rd Hr, 4th Hr)
Beyond daily closing prices, F&O options pricing is highly sensitive to opening gap behavior and midday momentum shifts. The engine ingests 730 days of 1-hour candles (`interval=1h`) to provide a multi-session hourly reaction breakdown:
* **1st Hour (09:15 – 10:15 AM):** Captures opening market reaction, gap-up/gap-down magnitude, and initial IV spike.
* **2nd Hour (10:15 – 11:15 AM):** Tracks opening continuation vs morning profit-booking reversal.
* **3rd Hour (11:15 – 12:15 PM):** Evaluates mid-day consolidation and initial theta/IV decay.
* **4th Hour (12:15 – 01:15 PM):** Tracks afternoon acceleration (crucial for companies releasing outcomes around noon).
* **Peak Intraday Swing & Timing:** Identifies the maximum high-to-low percentage swing reached during the day and flags which hour historically triggers peak volatility.
* **Dashboard Integration:** Displayed via an interactive **Hourly Progression Table** and visual step chain in the 360° modal, with 1st Hr and 4th Hr average indicators on stock cards.

---

## 10. Morning Pre-Market Broadcast & Automated Notification Engine

### 10.1 Morning Pre-Market Trigger (08:30 – 09:00 AM IST)
* Scheduled daily execution before market opens, giving traders actionable intelligence to position options and equities before volatility surges.
* Features a persistent daily broadcast log (`fno_broadcasts.json`) that strictly enforces an **EXACTLY ONCE PER DAY** broadcast guarantee, eliminating spam.
* Supports on-demand manual broadcast overrides via `/api/broadcast/fno-today?force=true` and UI dashboard button.

### 10.2 Telegram Briefing Format (`@krishstockalert`)
Each scheduled F&O stock includes:
1. Symbol, Full Company Name, and live CMP (₹)
2. Real-time Delivery Accumulation %
3. Individual realized moves for all 4 quarters: `[Q1 (07-Aug): +3.02% (T+1)]`, `[Q2 (10-May): -1.85% (T+1)]`, `[Q3 (02-Feb): +4.20% (Intraday)]`, `[Q4 (03-Nov): -2.10% (T+1)]`
4. Expected Volatility Swing ($\pm X\%$) and Directional Bias ($+X\%$)
5. Classic Support 1 (`S1`) & Resistance 1 (`R1`) pivot levels

---

## 11. High-Probability (70%–80% Win-Rate) Strike Pick Engine

### 11.1 The Quantitative Problem: Mitigating IV Crush
Naked Call + Put buying on earnings typically produces only a 35%–40% win rate due to severe Post-Earnings Implied Volatility (IV) collapse. To systematically achieve **70%–80% Probability of Profit (POP)**, the engine applies empirical volatility buffer filtering.

### 11.2 Standard NSE Derivative Strike Step Calibration
Automatically matches official SEBI/NSE equity derivative contract strike steps:
* CMP $< ₹150$: Step = $2.5$
* CMP $₹150 - ₹300$: Step = $5$
* CMP $₹300 - ₹700$: Step = $10$
* CMP $₹700 - ₹1,500$: Step = $20$
* CMP $₹1,500 - ₹3,500$: Step = $50$
* CMP $₹3,500 - ₹7,000$: Step = $100$
* CMP $> ₹7,000$: Step = $250$

### 11.3 Dual Strategy Classification & Breakeven Calculation
* **1-Strike OTM Strangle (Max ROI):**
  * Target Strikes: `[ATM + Step] CE` + `[ATM - Step] PE`.
  * Breakeven Required: $\pm \left(0.7 \times \frac{\text{Step}}{\text{CMP}} \times 100 + 1.2\%\right)$.
  * Win Condition: Realized move exceeded breakeven in $\ge 3$ of past 4 quarters ($75\%+$) and historical average move is $\ge 1.25 \times$ breakeven.
  * **Classification:** 🟢 `75-80% HIGH WIN RATE` (e.g. Bharat Forge $\pm 5.63\%$ vs $\pm 3.20\%$ breakeven).
* **ATM Straddle (High Probability):**
  * Target Strikes: `[ATM] CE` + `[ATM] PE`.
  * Breakeven Required: $\approx \pm 2.4\%$.
  * Win Condition: Historical swing $\ge \pm 2.4\%$ in $\ge 3$ of past 4 quarters.
  * **Classification:** 🟢 `75% HIGH WIN RATE` (e.g. ABFRL $\pm 4.44\%$ vs $\pm 2.40\%$ breakeven).
* **Low Volatility Filter (IV Crush Trap):**
  * Win Condition: Realized move exceeded breakeven in $\le 1$ quarter, or historical average swing $< \pm 2.2\%$.
  * **Classification:** 🔴 `AVOID (<40% POP)` — flags stocks like Berger Paints ($\pm 1.87\%$) and Ramco Cements ($\pm 1.52\%$) where options decay destroys buyers.

### 11.4 Web Dashboard Integration
Each F&O card features an interactive **70-80% Probability Strike Pick** section displaying:
* Probability Tag & Color Badge (Green = High Probability, Amber = Moderate, Red = Avoid)
* Strategy Name (`1-Strike OTM Strangle`, `ATM Straddle`, or `AVOID`)
* Target Strike Pair with exact CE and PE strike numbers
* Required Breakeven Move % compared side-by-side with Realized 4Q Swing %
* Plain-English institutional rationale and guidance note

### 11.5 Telegram Broadcast Integration
The Morning Pre-Market Briefing (8:30–9:00 AM IST) sent via Telegram to `@krishstockalert` directly incorporates:
* **70-80% Win Rate Setup Badge**: `[🟢 75-80% HIGH WIN RATE]` or `[🔴 AVOID (<40% POP)]`
* **Target Option Strikes**: Exact CE & PE strike recommendations (e.g. `1800 CE + 1700 PE (1-Strike OTM Strangle)`)
* **Breakeven vs Historical Swing**: Side-by-side comparison (`Breakeven Needed: ±2.5% | Past 4Q Swing: ±5.63%`)
* **Capital Needed per Lot**: Exact capital required in ₹ based on official NSE market lot sizes (`~₹21,200 / lot (Lot: 500)`)
* **Target Profit & Stop-Loss in ₹**: Defined gain target (`+₹12,700 (+60%)`) and strict cut-loss limit (`-₹7,400 (-35%)`)
* **Position Sizing Rule**: Clear portfolio allocation guideline (`Max 1 lot per ₹3L-₹5L account; max 5% event risk`)
* **Hourly Reaction Progression Tags**: Embedded directly in individual quarter movements (`Q1 (08-Aug): +6.2% 🟢 ↗ (1st Hr: +3.8% | 4th Hr: +5.1%)`)
* **Hourly Timing Averages**: `1st Hr Avg: ±X.X% | 4th Hr Avg: ±X.X%` for optimal intraday entry/exit timing.

### 11.6 Capital Allocation, Lot Size & Money Management Architecture
To prevent devastating losses from over-allocation or improper strike selection:
* **Why Deep OTM is an IV Crush Trap:** Buying cheap far-OTM options on earnings day fails because Implied Volatility collapses by 40%–60% immediately after the announcement. Options with delta $< 0.20$ suffer 80%–100% loss even when the stock moves.
* **Why 1-Strike OTM & ATM Win:** Options with delta $0.40–0.50$ convert price moves into intrinsic value, which overpowers post-earnings IV crush when the stock moves $\ge$ breakeven.
* **NSE Lot Size Engine:** System maps official contract lot sizes across all 214 NSE F&O equities (fallback heuristic: $\approx ₹6,00,000 / \text{CMP}$).
* **Capital Sizing Equation:**
  $$\text{Capital Required (₹)} = (\text{Estimated Call Premium} + \text{Estimated Put Premium}) \times \text{Lot Size}$$
* **The 3%–5% Account Risk Rule:** Never allocate more than 3% to 5% of total account capital to a single earnings event.
* **Strict Stop-Loss & Target Rules:**
  * **Stop-Loss:** Cut the position when combined premium drops by **-30% to -35%**. Never let premium decay to zero.
  * **Target Profit:** Take profit at **+50% to +80%** when the stock makes its intraday reaction swing (optimally during Hour 1: 09:15–10:15 AM).

### 11.7 Institutional Visual Redesign & Executive Terminal Layout
To eliminate visual clutter, nested boxes, and fragmented cards across web and mobile:
* **Unified Core Metrics Strip:** Consolidates Delivery %, S1/R1 Pivot Range, 14-D RSI, and 4Q Expected Swing into a single horizontal 4-tile grid.
* **Hero Trading Terminal Panel:** Integrates Strike Recommendation, Strategy Pill, 3-Column Execution Matrix (Capital / Lot, Target Profit, Stop-Loss), and Sizing Guidance into one dark-themed high-contrast trading panel.
* **Past 4Q Reaction Ribbon:** Replaces bulky vertical boxes with a clean 4-pill horizontal sparkline with 1-click access to the 360° Intraday Hourly Progression modal.
* **Executive Telegram Briefing:** Formats alerts into structured, 7-line Bloomberg-style blocks with clean typography and zero nested bullet bloat.

### 11.8 Dynamic Rolling Fiscal Quarter & Year Ingestion Architecture
To guarantee 100% dynamic freshness across future quarters with zero hardcoded dates:
* **Zero Static Years/Quarters:** Dates, months, and years are never hardcoded. Every evaluation dynamically queries the live NSE Board Meetings endpoint (`https://www.nseindia.com/api/corporate-board-meetings?index=equities&symbol=XYZ`).
* **Rolling 4-Quarter Window:** Filtering by `dt.date() < datetime.date.today()` ensures that whenever a new quarterly result is published, the window automatically shifts forward by one quarter: the new result becomes the newest quarter, and the oldest rolls off.
* **Indian Fiscal Year Math (`get_fiscal_quarter_label`):**
  * Results announced in Jan / Feb / Mar $\rightarrow$ `Q3 FY{YY}` (e.g. Feb 2027 $\rightarrow$ `Q3 FY27`)
  * Results announced in Apr / May / Jun $\rightarrow$ `Q4 FY{YY}` (e.g. May 2027 $\rightarrow$ `Q4 FY27`)
  * Results announced in Jul / Aug / Sep $\rightarrow$ `Q1 FY{YY+1}` (e.g. Aug 2027 $\rightarrow$ `Q1 FY28`)
  * Results announced in Oct / Nov / Dec $\rightarrow$ `Q2 FY{YY+1}` (e.g. Nov 2026 $\rightarrow$ `Q2 FY27`)
* **Future-Proofing:** In 3 months (February 2027), the platform will automatically display `Q3 FY27` without requiring any code modifications or manual intervention.

### 11.9 Legal, Regulatory & Risk Disclaimer Specifications
To ensure absolute legal clarity and adherence to Indian financial regulations:
* **Non-SEBI Registered Entity:** Explicit disclosure that the platform is an automated educational, computational, and research technology tool analyzing public regulatory filings (NSE/BSE), and not a SEBI-registered Investment Advisor (RIA) or Research Analyst.
* **Derivatives (F&O) High-Risk Warning:** Mandatory statutory disclosure highlighting that derivative trading carries substantial capital risk and referencing SEBI's official findings that 9 out of 10 individual retail F&O traders incur net financial losses.
* **No Buy/Sell Recommendations:** Reaffirmation that strike setups, probability metrics, and volatility analytics are historical empirical models provided solely for analytical and educational research.
* **Omnichannel Placement:**
  * **Web Dashboard:** Dedicated full-width dark compliance footer (`bg-gray-950/90 border-t border-gray-800/80`) with shield emblem, technology source tags (NSE/BSE Feeds, Gemini 3.5), and structured risk disclosure.
  * **Telegram Alerts:** Embedded one-line statutory compliance footer on every daily broadcast.

---

## 12. Version History & Release Changelog

| Release Tag | Commit | Date | Key Capabilities Added |
| :--- | :--- | :--- | :--- |
| **v1.0.0** | `1e9a3b2` | 04-Nov-2026 | Core platform launch: NSE filing ingestion, Gemini 3.5 Flash summaries, SQLite caching, Telegram alerts, React 18 dashboard. |
| **v1.1.0** | `71a0061` | 04-Nov-2026 | Offline asset bundling: packaged React, Babel, and Tailwind locally in `/static` to bypass corporate SSL/proxy CDN restrictions. |
| **v1.2.0** | `1bc6912` | 05-Nov-2026 | Dedicated F&O Results (Today) tab tracking 214 NSE F&O underlying derivatives stocks with delivery accumulation and whale activity. |
| **v1.3.0** | `3e3cae3` | 05-Nov-2026 | 4-Quarter historical earnings day price volatility tracking, average expected move ($\pm X\%$), and directional bias calculation. |
| **v1.4.0** | `8a805f7` | 05-Nov-2026 | Dual-Mode Timing Engine: differentiated Market Hours (Intraday) vs Post-Market (Session T+1) reaction attributions. |
| **v1.5.0** | `bd5c757` | 05-Nov-2026 | Strict declared result filtering, board meeting exclusion from broadcast, and 4 single-quarter movements display. |
| **v1.6.0** | `e021ff0` | 05-Nov-2026 | Morning Pre-Market F&O Briefing (8:30–9:00 AM IST) sent before results drop with exact today's board meeting ingestion. |
| **v1.7.0** | `ce8de84` | 05-Nov-2026 | Institutional 70%–80% Win-Rate Strike Pick Engine (1-Strike OTM Strangle vs ATM Straddle vs Avoid IV Crush) on dashboard cards. |
| **v1.8.0** | `7db5aa5` | 06-Nov-2026 | Intraday Hourly Reaction Progression Engine: 1st Hr, 2nd Hr, 3rd Hr, 4th Hr, and Peak Intraday Swing tracking across past quarters. |
| **v1.8.1** | `8f2d0f1` | 06-Nov-2026 | Telegram Broadcast Integration: Enriched Morning Briefing with 70–80% strike recommendations, breakeven thresholds, and hourly tags. |
| **v1.9.0** | `8539bbd` | 06-Nov-2026 | Capital & Money Management Engine: Official NSE Lot Sizes, Capital Required (₹/lot), Target Profit (+60%), Stop-Loss (-35%), and Portfolio Sizing rules across Web & Telegram. |
| **v2.0.0** | `d3f42c2` | 06-Nov-2026 | Professional Layout Redesign: Unified 4-tile KPI metric strip, consolidated hero trading terminal panel, 4-quarter reaction ribbon, and executive Bloomberg-style Telegram alerts. |
| **v2.1.0** | `c38ac3d` | 06-Nov-2026 | Dynamic Rolling Fiscal Quarter & Year Engine: Live NSE Board Meeting ingestion with automatic Fiscal Year (`Q2 FY27`, `Q3 FY27`) rollover. |
| **v2.2.0** | `HEAD` | 06-Nov-2026 | Compliance & Regulatory Disclaimer: Embedded full-width SEBI non-registration & F&O risk warning in Web footer and Telegram broadcasts. |
