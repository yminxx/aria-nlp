# test_gemini.py
import os
from dotenv import load_dotenv

# Load your .env file (contains GEMINI_API_KEY)
load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise SystemExit("Set GEMINI_API_KEY or GOOGLE_API_KEY in your environment or .env")

# Import the Google GenAI client
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
    # Initialize the client with your API key
    client = genai.Client(api_key=API_KEY)

    # Call the model (use the new models.generate_content API)
    try:
        resp = client.models.generate_content(
            model="gemini-2.5-flash-lite",  # your selected model
            contents="Hello from aria-nlp test. Please respond with the word 'connected' only.",
            # Optional parameters — uncomment if supported by your SDK version
            # parameters={"max_output_tokens": 64, "temperature": 0.0}
        )
    except Exception as e:
        print("❌ Model request failed:", e)
        return

    # Safely extract the generated text
    text = getattr(resp, "text", None) or str(resp)

    print("\n✅ Model response:")
    print(text)

if __name__ == "__main__":
    main()
