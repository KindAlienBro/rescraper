import google.generativeai as genai
from dotenv import load_dotenv
import os

# Load API key from .env file
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

if not api_key:
    print("Error: GOOGLE_API_KEY not found in .env file.")
else:
    genai.configure(api_key=api_key)

    print("="*30)
    print("Available Gemini Models")
    print("="*30)

    for m in genai.list_models():
      # We only care about models that support the 'generateContent' method
      if 'generateContent' in m.supported_generation_methods:
        print(f"- {m.name}")
        
    print("\nRecommendation: Use 'gemini-1.5-pro-latest' for the best results.")