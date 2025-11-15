import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise SystemExit("Set GEMINI_API_KEY or GOOGLE_API_KEY in your environment or .env")

try:
    from google import genai
except Exception as e:
    raise SystemExit(
        "google-genai package missing or import failed.\n"
        "Install it using: pip install google-genai\n"
        f"Error details: {e}"
    )

def main():
    """Simple connectivity test for Gemini 2.5 Flash Lite"""
  
    client = genai.Client(api_key=API_KEY)

  
    try:
        resp = client.models.generate_content(
            model="gemini-2.5-flash-lite",  
            contents="Hello from aria-nlp test. Please respond with the word 'connected' only.",
        )
    except Exception as e:
        print("Model request failed:", e)
        return

    text = getattr(resp, "text", None) or str(resp)

    print("\n✅ Model response:")
    print(text)

if __name__ == "__main__":
    main()
