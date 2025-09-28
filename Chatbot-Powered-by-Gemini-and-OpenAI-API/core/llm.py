import os
from dotenv import load_dotenv
import google.generativeai as genai

def ensure_genai():
    load_dotenv()
    api = os.getenv("GOOGLE_API_KEY")
    if not api:
        raise RuntimeError("GOOGLE_API_KEY not found in .env")
    genai.configure(api_key=api)

def pick_models():
    try:
        avail = [m.name for m in genai.list_models()
            if "generateContent" in getattr(m, "supported_generation_methods", [])]
        preferred = ["gemini-2.5-flash-preview-09-2025", "gemini-2.5-flash-lite-preview-09-2025"]
        plan = [m for m in preferred if m in avail]
        return plan or avail or ["gemma-3-27b-it"]
    except Exception:
        return ["gemma-3n-e4b-it"]

def gcall(prompt_text: str, models=None, max_tokens=450, temperature=0.6):
    """Minimal Gemini call with graceful fallback."""
    ensure_genai()
    if models is None:
        models = pick_models()
    last_err = None
    for m in models:
        try:
            model = genai.GenerativeModel(m)
            resp = model.generate_content(
                prompt_text,
                generation_config={"max_output_tokens": max_tokens, "temperature": temperature}
            )
            txt = getattr(resp, "text", None)
            if not txt and getattr(resp, "candidates", None):
                parts = getattr(resp.candidates[0].content, "parts", [])
                if parts and hasattr(parts[0], "text"):
                    txt = parts[0].text
            return (txt or "").strip(), m
        except Exception as e:
            last_err = e
            continue
    raise last_err