# 📈 Stock AI Notifier

An AI-powered corporate announcement and financial results analyzer that monitors Indian stock market filings (BSE/NSE) in real-time, digests quarterly reports with **Google Gemini Flash**, and sends instant alerts to your **Telegram**.

---

## 📁 Project Location
`D:\wampgc\www\stock-ai-notifier\`

---

## ⚡ 3-Minute Quick Setup

### 1. Get Free Telegram Bot Token & Chat ID
1. Open Telegram, search for `@BotFather`, and send `/newbot`.
2. Copy the **HTTP API Token** (e.g., `123456789:ABCdefGhIJKlmNo...`).
3. Search for `@userinfobot` on Telegram, press Start, and copy your numeric **Id** (e.g., `987654321`).

### 2. Get Free Google Gemini API Key
1. Go to [Google AI Studio](https://aistudio.google.com/).
2. Click **Get API key** -> **Create API Key**.
3. Copy the key.

### 3. Configure Your `.env` File
Open `d:\wampgc\www\stock-ai-notifier\.env` and paste your credentials:
```env
GEMINI_API_KEY=AIzaSy...
TELEGRAM_BOT_TOKEN=123456789:ABC...
TELEGRAM_CHAT_ID=987654321
POLL_INTERVAL=60
```

### 4. Customize Your Stock Watchlist
Open `config.py` and modify `DEFAULT_WATCHLIST` to add any stocks you care about:
```python
DEFAULT_WATCHLIST = [
    "RELIANCE",
    "TATA CONSULTANCY",
    "TCS",
    "INFOSYS",
    "HDFC BANK",
    "ITC"
]
```
*(Tip: Set to `["*"]` if you want alerts for all major earnings announcements).*

---

## 🧪 Test Your Setup
Run the diagnostics script:
```bash
python test_setup.py
```
This will verify your BSE connection, send a test ping to your Telegram bot, and verify the Gemini AI engine.

---

## 🚀 Run the Bot
Start listening for market announcements:
```bash
python main.py
```

It will poll BSE every 60 seconds during market hours, download filings for your watchlist, summarize the financials and risks using Gemini, and send formatted alerts to your Telegram chat.

