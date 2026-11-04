import time
import requests
import fitz  # PyMuPDF
from pathlib import Path
from typing import Optional
from google import genai
from config import GEMINI_API_KEYS, GROQ_API_KEY

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

def analyze_with_groq(prompt_text: str) -> Optional[str]:
    """
    Ultra-fast fallback using Groq API (Llama 3.3 70B) with 14,400 free requests/day.
    """
    if not GROQ_API_KEY:
        return None
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt_text}
            ],
            "temperature": 0.2,
            "max_tokens": 1024
        }
        print("[AI Engine] ⚡ Generating instant summary via Groq (Llama 3.3 70B)...")
        res = requests.post(url, headers=headers, json=payload, timeout=20)
        if res.status_code == 200:
            return res.json()["choices"][0]["message"]["content"]
        else:
            print(f"[Groq Error] HTTP {res.status_code}: {res.text[:200]}")
    except Exception as e:
        print(f"[Groq Exception] {e}")
    return None

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
                    # If multiple keys exist, try next key
                    if rotate_to_next_key():
                        break
                    else:
                        raise last_error

                # For 503 high demand spikes, try next model
                continue

    raise last_error

def analyze_document(pdf_path: Path, company_name: str, subject: str) -> str:
    """
    Sends the filing PDF to AI for summarization (Gemini with seamless Groq fallback).
    """
    prompt = f"Analyze this filing for {company_name}.\nAnnouncement Subject: {subject}\nIMPORTANT: Strictly write your response in English only.\n\n{SYSTEM_PROMPT}"

    # 1. Try Gemini (Native PDF upload)
    gemini_failed = False
    if GEMINI_API_KEYS:
        client, _ = get_current_client()
        try:
            gemini_file = client.files.upload(file=str(pdf_path))
            response = generate_with_fallback([gemini_file, prompt])
            return response.text
        except Exception as e:
            gemini_failed = True
            print(f"[AI Engine] Gemini unavailable ({e}). Triggering fallback...")

    # 2. Extract text from PDF for Groq / Text-based LLM fallback
    extracted_text = ""
    try:
        doc = fitz.open(pdf_path)
        for i in range(min(8, len(doc))):
            extracted_text += f"\n--- Page {i+1} ---\n" + doc[i].get_text()
    except Exception as e:
        print(f"[PDF Extract Error] {e}")

    # 3. Seamless Groq Fallback (14,400 free requests/day)
    if GROQ_API_KEY and extracted_text:
        groq_prompt = f"Company: {company_name}\nSubject: {subject}\nDocument Excerpts:\n{extracted_text[:18000]}"
        groq_res = analyze_with_groq(groq_prompt)
        if groq_res:
            return groq_res

    # 4. Clean graceful structured fallback if AI quotas are temporarily locked
    return (
        f"🎯 *Executive Summary*:\n"
        f"Official regulatory disclosure submitted by {company_name}.\n\n"
        f"📋 *Subject*: {subject}\n"
        f"💡 *Key Note*: Disclosed in compliance with SEBI listing regulations.\n"
        f"📈 *Sentiment*: Neutral 🟡"
    )
