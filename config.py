import os
from pathlib import Path
from dotenv import load_dotenv

# Base directory
BASE_DIR = Path(__file__).resolve().parent

# Load .env file
load_dotenv(BASE_DIR / ".env")

# API Keys & Secrets
GEMINI_RAW_KEYS = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_API_KEYS = [k.strip() for k in GEMINI_RAW_KEYS.split(",") if k.strip()]
GEMINI_API_KEY = GEMINI_API_KEYS[0] if GEMINI_API_KEYS else ""
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

# App Branding / Notification Header Title
APP_TITLE = os.getenv("APP_TITLE", "STOCK MARKET ALERT").strip()

# Polling Interval (in seconds)
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "60"))

# Your Personal Stock Watchlist
# You can add NSE Symbols (e.g., 'TCS', 'RELIANCE') or Company Names (case-insensitive)
# Set to ["*"] if you want to track ALL major corporate announcements
DEFAULT_WATCHLIST = [
    "RELIANCE",
    "TCS",
    "INFY",
    "HDFCBANK",
    "ICICIBANK",
    "SBIN",
    "BHARTIARTL",
    "ITC",
    "LT",
    "TATAMOTORS"
]

# Path to store seen announcements to prevent duplicates
SEEN_FILE = BASE_DIR / "seen_announcements.json"
TEMP_DIR = BASE_DIR / "temp_pdfs"
TEMP_DIR.mkdir(exist_ok=True)
