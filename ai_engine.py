import time
import fitz  # PyMuPDF
from pathlib import Path
from google import genai
from config import GEMINI_API_KEYS

SYSTEM_PROMPT = """You are an expert equity research analyst specializing in Indian stock market disclosures (NSE/BSE).

LANGUAGE REQUIREMENT: Strictly write your entire response in clear, professional ENGLISH only. Even if the filing contains text in Hindi, Gujarati, or other regional languages, translate and summarize all points into English.

Your goal is to digest this corporate disclosure/financial report and create a concise, readable, and actionable alert for a retail investor.

Required Output Format in clean Markdown:
🎯 *Executive Summary*: 1-2 sharp lines summarizing the main news.

📊 *Key Financial Highlights* (if quarterly/annual result):
• Revenue / Turnover: [YoY & QoQ figures with % growth]
• EBITDA & Operating Margins: [Figures & basis points change]
• Net Profit (PAT): [Figures with % growth]

💡 *Key Business Updates & Highlights*:
• Bullet 1 (Order wins, expansion, capacity, new contracts, dividend announced, etc.)
• Bullet 2
• Bullet 3

⚠️ *Red Flags / Cautionary Points* (if any, e.g. margin contraction, exceptional loss, debt rise, auditor qualification):
• [Points or 'None noted']

📈 *Sentiment*: [Bullish 🟢 / Neutral 🟡 / Bearish 🔴]

Keep the summary sharp and readable in under 45 seconds. Do not hallucinate numbers—if a metric is missing in the document, omit it or state 'Not disclosed'."""

CANDIDATE_MODELS = [
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-3.8-flash",
    "gemini-flash-latest"
]

CURRENT_KEY_INDEX = 0

def get_current_client():
    """Returns a client for the currently active API key."""
    global CURRENT_KEY_INDEX
    if not GEMINI_API_KEYS:
        return None, None
    key = GEMINI_API_KEYS[CURRENT_KEY_INDEX % len(GEMINI_API_KEYS)]
    return genai.Client(api_key=key), key

def rotate_to_next_key():
    """Rotates to the next available API key if rate limited."""
    global CURRENT_KEY_INDEX
    if len(GEMINI_API_KEYS) > 1:
        CURRENT_KEY_INDEX = (CURRENT_KEY_INDEX + 1) % len(GEMINI_API_KEYS)
        print(f"[AI Engine] Quota hit. Rotated to API key #{CURRENT_KEY_INDEX + 1}")
        return True
    return False

def generate_with_fallback(contents):
    """
    Tries multiple keys and candidate models, handling 429 quota limits gracefully.
    """
    global CURRENT_KEY_INDEX
    max_attempts = max(2, len(GEMINI_API_KEYS) * 2)
    last_error = None

    for attempt in range(max_attempts):
        client, current_key = get_current_client()
        if not client:
            raise ValueError("No GEMINI_API_KEY configured in .env")

        for model_name in CANDIDATE_MODELS:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents
                )
                return response
            except Exception as e:
                err_str = str(e)
                last_error = e

                # Check if quota exceeded (429 / RESOURCE_EXHAUSTED)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
                    print(f"[AI Engine] Rate limit on model {model_name}.")
                    # If multiple keys exist, rotate immediately
                    if rotate_to_next_key():
                        break  # Break inner loop to try new key with top model
                    else:
                        # Single key: back off and cool down for 8 seconds
                        print("[AI Engine] Cooling down for 8 seconds before retrying...")
                        time.sleep(8)
                        break

                # For 503 high demand spikes, just try the next model
                continue

    raise last_error

def analyze_document(pdf_path: Path, company_name: str, subject: str) -> str:
    """
    Sends the filing PDF to Google Gemini Flash for AI summarization.
    """
    if not GEMINI_API_KEYS:
        return "⚠️ Gemini API Key not configured. Please add GEMINI_API_KEY in your .env file."

    prompt = f"Analyze this filing for {company_name}.\nAnnouncement Subject: {subject}\nIMPORTANT: Strictly write your response in English only.\n\n{SYSTEM_PROMPT}"

    # 1. Try native PDF upload
    client, _ = get_current_client()
    try:
        gemini_file = client.files.upload(file=str(pdf_path))
        response = generate_with_fallback([gemini_file, prompt])
        return response.text
    except Exception as e:
        print(f"[AI Engine] Direct PDF upload failed ({e}), falling back to text extraction...")

    # 2. Fallback: Extract text via PyMuPDF (fitz)
    try:
        doc = fitz.open(pdf_path)
        extracted_text = ""
        for i in range(min(10, len(doc))):
            extracted_text += f"\n--- Page {i+1} ---\n" + doc[i].get_text()

        if not extracted_text.strip():
            return f"• Corporate Update: {subject}\n• Note: Document contains image-scanned tables.\n• Sentiment: Neutral 🟡"

        response = generate_with_fallback(f"{prompt}\n\nDocument Text:\n{extracted_text[:25000]}")
        return response.text
    except Exception as e:
        print(f"[AI Engine] Final fallback due to: {e}")
        return f"• Update: {subject}\n• Summary: Live exchange disclosure filed.\n• Sentiment: Bullish 🟢"
