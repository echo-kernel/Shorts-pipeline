import os
import json
import time
import random
import asyncio
import requests
import edge_tts
from google import genai
from moviepy import VideoFileClip, AudioFileClip

# 1. Load Environment Secrets
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "").strip()
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

print("1. Generating script...")

# Fallback facts in case Google Cloud servers are under heavy load (503)
FALLBACK_FACTS = [
    {
        "title": "A Day on Venus is Longer Than Its Year",
        "voiceover": "Did you know that Venus spins so slowly that a single day on Venus lasts longer than its entire year around the Sun?",
        "keyword": "space"
    },
    {
        "title": "The Quantum Computer Superpower",
        "voiceover": "Quantum computers can perform calculations in seconds that would take the fastest modern supercomputers thousands of years.",
        "keyword": "computer"
    },
    {
        "title": "Neutron Stars Are Incredibly Dense",
        "voiceover": "Neutron stars are so dense that just a single sugar cube of their material would weigh about one billion tons on Earth.",
        "keyword": "galaxy"
    },
    {
        "title": "Ocean Depths Are Unexplored",
        "voiceover": "More than eighty percent of Earth's oceans remain unmapped and unexplored, holding mysteries we have yet to discover.",
        "keyword": "ocean"
    }
]

prompt = (
    "Create a compelling, punchy 15-second tech, astronomy, or science fact for a YouTube Short. "
    "Return strictly JSON with keys: 'title', 'voiceover', and 'keyword'. "
    "'keyword' must be one single word describing the background visual (e.g., galaxy, computer, robot, ocean)."
)

client = genai.Client(api_key=GEMINI_API_KEY)
models_to_try = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3.5-flash-lite", "gemini-3.8-flash"]
data = None

for model_name in models_to_try:
    try:
        print(f"Trying model: {model_name}...")
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config={"response_mime_type": "application/json"}
        )
        if response and response.text:
            clean_text = response.text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
            data = json.loads(clean_text)
            print(f"Success with {model_name}!")
            break
    except Exception as e:
        print(f"Model {model_name} busy or unavailable. Trying next...")
        time.sleep(1)

# If Google API is under a 503 spike, pick from the backup library
if not data:
    print("Google API busy; using curated high-engagement script backup.")
    data = random.choice(FALLBACK_FACTS)

title = data.get("
