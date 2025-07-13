import google.generativeai as genai
from dotenv import load_dotenv
import os
import re

# ✅ Load API key from .env
load_dotenv()
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")

if not GOOGLE_API_KEY:
    raise ValueError("GEMINI_API_KEY not set")

# ✅ Configure Gemini
genai.configure(api_key=GOOGLE_API_KEY)

def clean_markdown(text: str) -> str:
    # ✅ Convert **something:** to <strong>something:</strong>
    text = re.sub(r'\*\*(.+?):\*\*', r'<strong>\1:</strong>', text)

    # ✅ Convert **something** to <strong>something</strong>
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)

    # ✅ Remove stray or unmatched asterisks (like `Bias:**` or `**Text`)
    text = re.sub(r'(?<!\*)\*(?!\*)', '', text)

    return text.strip()

def generate_answer(question: str) -> str:
    try:
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config={
                "temperature": 0.7,
                "max_output_tokens": 1024,
                "top_p": 0.9,
                "top_k": 40,
            } # type: ignore
        )
        response = model.generate_content(question)
        cleaned = clean_markdown(response.text)
        return cleaned
    except Exception as e:
        return f"Error generating response: {str(e)}"
