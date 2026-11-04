# Business Requirement Document (BRD) & System Blueprint
## Project: EquiSense AI Alternative — Real-Time Stock Intelligence Notifier

---

## 1. Executive Summary & Project Overview

### 1.1 Background & Context
In the Indian stock market (NSE & BSE), publicly listed companies submit regulatory filings—including quarterly financial results, earnings conference call transcripts, board meeting outcomes, and insider trades—throughout market hours. These disclosures are usually uploaded as dense, multi-page (often 30–100+ pages) PDF documents.

Platforms like **EquiSense AI (`equisense.ai`)** have emerged to address this by automatically parsing filings using large language models (LLMs) and sending simplified, plain-English executive summaries and key financial metrics to retail investors via instant messaging (WhatsApp/Telegram).

### 1.2 Project Objective
To build and deploy a self-hosted, **₹0-cost** (free-tier) intelligence notification system that:
1. Continuously monitors live regulatory disclosures from Indian stock exchanges.
2. Identifies announcements related to a user-defined watchlist.
3. Downloads the official attached filing PDF.
4. Uses Google Gemini LLM to extract financial metrics (Revenue, EBITDA margins, PAT, red flags, guidance, sentiment).
5. Delivers structured, actionable alerts directly to the user's **Telegram** within seconds of release.

---

## 2. Step-by-Step Credential Generation Guide

### 2.1 Google Gemini API Key
Google provides free access to Gemini Flash models via **Google AI Studio** with up to 15 requests/minute and 1,500 requests/day (more than sufficient for personal stock tracking).

1. Visit [Google AI Studio](https://aistudio.google.com/).
2. Sign in with your standard Google account.
3. Click on the blue button labeled **"Get API key"** (or navigate to API keys in the sidebar).
4. Click **"Create API key"** (choose "Create in new project" or select an existing Google Cloud project).
5. Copy the generated key (starts with `AIzaSy...` or `AQ...`).
6. Paste this value into your `.env` file:
   ```env
   GEMINI_API_KEY=your_copied_key_here
   ```

---

### 2.2 Telegram Bot Token
Telegram bots are created and managed through Telegram's official bot creator, `@BotFather`.

1. Open your Telegram app on mobile, desktop, or web.
2. In the top search bar, search for **`@BotFather`** (ensure it has the verified blue checkmark).
3. Click **Start** (or type `/start`).
4. Type `/newbot` and send.
5. Provide a display name for your bot when prompted (e.g. `My Stock Notifier`).
6. Provide a unique username ending in `bot` (e.g. `john_stock_alerts_bot`).
7. BotFather will reply with your HTTP API Token:
   > *Use this token to access the HTTP API:*  
   > `9069413515:AAEprQcsikvJQ...`
8. Copy this entire string and paste it into your `.env` file:
   ```env
   TELEGRAM_BOT_TOKEN=9069413515:AAEprQcsikvJQ...
   ```

---

### 2.3 Telegram Chat ID
The Chat ID is your personal numeric identifier on Telegram so the bot knows where to send alerts.

1. **Important First Step:** Search for your newly created bot in Telegram (by its username, e.g. `@john_stock_alerts_bot`), open the chat, and press **Start** (or send "Hi"). The bot cannot send messages to you until you initiate contact.
2. In Telegram's search bar, search for **`@userinfobot`** (or open [https://t.me/userinfobot](https://t.me/userinfobot) in your browser).
3. Click **Start**.
4. The bot will immediately reply with your details:
   ```text
   Id: 6620251205
   First: Bablu
   ...
   ```
5. Copy the numeric **Id** value and paste it into your `.env` file:
   ```env
   TELEGRAM_CHAT_ID=6620251205
   ```

---

## 3. High-Level Architecture & Data Flow

```
┌────────────────────────────────────────────────────────┐
│             NSE India Corporate Feed                   │
│   (https://www.nseindia.com/api/corporate-announcements)│
└──────────────────────────┬─────────────────────────────┘
                           │ Poll every 60s
                           ▼
┌────────────────────────────────────────────────────────┐
│             1. Ingestion & Watchlist Filter            │
│                 (exchange_client.py)                   │
│  - Filters by Symbol / Name against Watchlist          │
│  - Checks seen_announcements.json (Prevents duplicates)│
└──────────────────────────┬─────────────────────────────┘
                           │ If Watchlist Match
                           ▼
┌────────────────────────────────────────────────────────┐
│             2. PDF Downloader & Storage                │
│    - Fetches filing PDF from NSE archives              │
│    - Temporarily stores in /temp_pdfs/                 │
└──────────────────────────┬─────────────────────────────┘
                           │ Pass to LLM
                           ▼
┌────────────────────────────────────────────────────────┐
│             3. AI Engine (ai_engine.py)                │
│    - Google Gemini Flash (Multimodal Document Ingest)  │
│    - Auto-Fallback (gemini-3.5-flash / 3.1-flash-lite) │
│    - Extracts Revenue, Margins, PAT, Red Flags, Sentiment
└──────────────────────────┬─────────────────────────────┘
                           │ Structured Markdown
                           ▼
┌────────────────────────────────────────────────────────┐
│          4. Dispatcher (telegram_client.py)            │
│    - Formats alert with timestamps and PDF link        │
│    - Sends push notification to user's Telegram chat   │
└────────────────────────────────────────────────────────┘
```

---

## 4. Component Deep Dive

| Component | File Path | Function & Role |
| :--- | :--- | :--- |
| **Config & Secrets** | `config.py`, `.env` | Holds API keys, polling intervals, directories, and the user's active watchlist. |
| **Exchange Ingestion** | `exchange_client.py` | Connects directly to exchange feeds with browser session simulation; parses JSON payload; downloads PDF attachments. |
| **AI Intelligence** | `ai_engine.py` | Sends PDFs directly to Google Gemini. Features multi-model failover (`gemini-3.5-flash` → `gemini-3.1-flash-lite` → `gemini-3.8-flash`) to eliminate 503 capacity errors. Also includes fallback text-extraction via PyMuPDF. |
| **Messaging Dispatcher** | `telegram_client.py` | Dispatches Markdown notifications via Telegram Bot API with automatic message splitting for payloads > 4000 characters and plain-text fallback on parse errors. |
| **Orchestrator Daemon** | `main.py` | Background loop that triggers polling, deduplicates via `seen_announcements.json`, cleans up temporary PDFs, and handles graceful exits. |
| **System Diagnostics** | `test_setup.py` | 1-click test suite that verifies exchange feed connectivity, sends a live ping to Telegram, and runs a Gemini inference test. |

---

## 5. Sample Output: Delivered Telegram Alert

When an earnings report is filed, the user receives an alert structured like this:

```markdown
⚡ EQUISENSE AI ALERT: TCS
🏢 TATA CONSULTANCY SERVICES LIMITED
📋 Subject: Financial Results For The Quarter Ended September 30, 2026
🕒 03-Nov-2026 07:45 PM

───────────────────
🎯 Executive Summary:
TCS reports steady Q2 performance led by banking & manufacturing deal ramp-ups, declaring an interim dividend of ₹10 per share.

📊 Key Financial Highlights:
• Revenue: ₹64,259 Cr (Up 7.6% YoY, 2.6% QoQ)
• EBITDA Margin: 24.1% (Expanded by 40 bps YoY)
• Net Profit (PAT): ₹11,909 Cr (Up 5.0% YoY)

💡 Key Business Updates & Highlights:
• Total Contract Value (TCV) bookings reached $8.6 Billion.
• Strong net additions with voluntary attrition dropping to 12.3%.
• Interim dividend announced: Record date set for next week.

⚠️ Red Flags / Cautionary Points:
• Subdued demand continues in communications and media vertical.

📈 Sentiment: Bullish 🟢
───────────────────
📄 [Open Original Exchange Filing](https://nsearchives.nseindia.com/corporate/...)
```

---

## 6. Functional & Non-Functional Requirements

### 6.1 Functional Requirements
- **FR-1:** Filter announcements against custom ticker symbols (`TCS`, `RELIANCE`, `INFY`) or company names.
- **FR-2:** Support a wildcard watchlist (`["*"]`) to monitor all corporate actions across the entire exchange.
- **FR-3:** Deduplication memory (`seen_announcements.json`) to guarantee no filing is alerted more than once.
- **FR-4:** Automated disk cleanup: PDF files downloaded during processing are deleted once the AI analysis finishes.

### 6.2 Non-Functional Requirements
- **NFR-1 (Zero Running Cost):** Runs within free tiers of Google AI Studio and Telegram Bot API.
- **NFR-2 (Low Latency):** Delivers alerts within 30 to 60 seconds of exchange submission.
- **NFR-3 (High Availability):** Model fallback strategy ensures server spikes on one model switch to secondary models without crashing.
- **NFR-4 (Security & Privacy):** Credentials remain strictly local in `.env`; no third-party data broker is utilized.

---

## 7. Operational Runbook

### 7.1 Running System Verification
Whenever credentials or settings change, run the test script:
```powershell
cd D:\wampgc\www\stock-ai-notifier
python test_setup.py
```

### 7.2 Starting the Live Bot
```powershell
cd D:\wampgc\www\stock-ai-notifier
python main.py
```

### 7.3 Modifying the Stock Watchlist
Edit [`config.py`](file:///d:/wampgc/www/stock-ai-notifier/config.py):
```python
DEFAULT_WATCHLIST = [
    "RELIANCE",
    "TCS",
    "INFY",
    "HDFCBANK",
    "TATAMOTORS"
]
```

---

## 8. Roadmap & Future Scope
1. **Multi-Language Summaries:** Allow prompting Gemini to output in Hindi or Gujarati for regional investors.
2. **Concall Audio Processing:** Ingest audio recording links from investor conference calls and extract CEO guidance highlights.
3. **Sentiment Dashboard:** Build a lightweight local web UI (e.g. Streamlit or PHP dashboard in WAMP) visualizing quarterly YoY profit trajectory.

