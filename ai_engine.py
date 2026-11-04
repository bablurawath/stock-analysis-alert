from pathlib import Path
from google import genai
from config import GEMINI_API_KEY
import fitz  # PyMuPDF

SYSTEM_PROMPT = """You are an expert equity research analyst specializing in Indian stock market disclosures (NSE/BSE).
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

def generate_with_fallback(client, contents):
    """
    Tries models sequentially in case of 503 high demand spikes.
    """
    last_error = None
    for model_name in CANDIDATE_MODELS:
        try:
            return client.models.generate_content(
                model=model_name,
                contents=contents
            )
        except Exception as e:
            last_error = e
            print(f"[AI Engine] Model {model_name} busy or unavailable, trying next...")
            continue
    raise last_error

def analyze_document(pdf_path: Path, company_name: str, subject: str) -> str:
    """
    Sends the filing PDF to Google Gemini Flash for AI summarization.
    """
    if not GEMINI_API_KEY:
        return "⚠️ Gemini API Key not configured. Please add GEMINI_API_KEY in your .env file."

    client = genai.Client(api_key=GEMINI_API_KEY)
    prompt = f"Analyze this filing for {company_name}.\nAnnouncement Subject: {subject}\n\n{SYSTEM_PROMPT}"

    # 1. Try native PDF upload (best for scanned tables and complex multi-page filings)
    try:
        gemini_file = client.files.upload(file=str(pdf_path))
        response = generate_with_fallback(client, [gemini_file, prompt])
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
            return "⚠️ The uploaded PDF appears to be a scanned image and text could not be extracted."

        response = generate_with_fallback(client, f"{prompt}\n\nDocument Text:\n{extracted_text[:30000]}")
        return response.text
    except Exception as e:
        return f"⚠️ AI analysis failed: {str(e)}"

