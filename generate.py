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
        print(f"Model {model_name} busy. Trying next...")
        time.sleep(1)

if not data:
    print("Google API busy; using curated high-engagement script backup.")
    data = random.choice(FALLBACK_FACTS)

title = data.get("title", "Amazing Science Fact")
voiceover = data.get("voiceover", "")
keyword = data.get("keyword", "technology")

print(f"Title: {title}")
print(f"Keyword: {keyword}")

print("2. Generating neural voiceover...")
async def generate_voice():
    communicate = edge_tts.Communicate(voiceover, "en-US-ChristopherNeural")
    await communicate.save("audio.mp3")

asyncio.run(generate_voice())

print("3. Fetching vertical video from Pexels...")
headers = {"Authorization": PEXELS_API_KEY}
pexels_url = f"https://api.pexels.com/videos/search?query={keyword}&orientation=portrait&per_page=5"
res = requests.get(pexels_url, headers=headers).json()

download_url = None
for video in res.get("videos", []):
    for f in video.get("video_files", []):
        if f.get("width") and f.get("height") and f["height"] > f["width"]:
            download_url = f["link"]
            break
    if download_url:
        break

if not download_url and res.get("videos"):
    download_url = res["videos"][0]["video_files"][0]["link"]

if not download_url:
    download_url = "https://images.pexels.com/videos/854671/free-video-854671.mp4"

with open("raw_video.mp4", "wb") as f:
    f.write(requests.get(download_url).content)

print("4. Stitching video with MoviePy & FFmpeg...")
audio_clip = AudioFileClip("audio.mp3")
video_clip = VideoFileClip("raw_video.mp4")

target_duration = audio_clip.duration
video_clip = video_clip.subclipped(0, min(video_clip.duration, target_duration))
final_video = video_clip.with_audio(audio_clip)

final_video.write_videofile("final.mp4", codec="libx264", audio_codec="aac", fps=24)

audio_clip.close()
video_clip.close()
final_video.close()

print("5. Sending video preview to Telegram...")
tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
caption_text = f"🎬 {title}\n\n📝 {voiceover}"

with open("final.mp4", "rb") as video_file:
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "caption": caption_text[:1024]
    }
    r = requests.post(tg_url, data=payload, files={"video": video_file})
    print(f"Telegram status: {r.status_code}")
    print(f"Telegram response: {r.text}")

print("Execution completed successfully.")
        
