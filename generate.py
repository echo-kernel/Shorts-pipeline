import os
import json
import time
import random
import asyncio
import subprocess
import requests
import edge_tts
from google import genai
from moviepy import VideoFileClip, AudioFileClip

# 1. Load Secrets
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
PEXELS_API_KEY = os.environ.get("PEXELS_API_KEY", "").strip()
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

FALLBACK_FACTS = [
    {
        "title": "A Day on Venus is Longer Than Its Year",
        "voiceover": "Venus spins so slowly that one single day on Venus lasts longer than its entire year around the Sun.",
        "keyword": "space"
    },
    {
        "title": "The Quantum Computer Superpower",
        "voiceover": "Quantum computers can calculate in seconds what would take modern supercomputers thousands of years.",
        "keyword": "computer"
    },
    {
        "title": "Neutron Stars Are Incredibly Dense",
        "voiceover": "A single sugar cube of a neutron star would weigh about one billion tons on Earth.",
        "keyword": "galaxy"
    }
]

prompt = (
    "Create a punchy 10-15 second mindblowing tech, physics, or science fact for YouTube Shorts. "
    "Return strictly JSON with keys: 'title', 'voiceover', and 'keyword'. "
    "'keyword' must be one visual noun (e.g., galaxy, robotics, technology, ocean)."
)

client = genai.Client(api_key=GEMINI_API_KEY)
models_to_try = ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-3.5-flash-lite", "gemini-3.8-flash"]
data = None

for model_name in models_to_try:
    try:
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
            break
    except Exception:
        time.sleep(1)

if not data:
    data = random.choice(FALLBACK_FACTS)

title = data.get("title", "Amazing Science Fact")
voiceover = data.get("voiceover", "")
keyword = data.get("keyword", "space")

print(f"Title: {title}")
print(f"Voiceover: {voiceover}")

# 2. TTS Voiceover
async def generate_voice():
    communicate = edge_tts.Communicate(voiceover, "en-US-ChristopherNeural", rate="+10%")
    await communicate.save("audio.mp3")

asyncio.run(generate_voice())

# 3. Pexels HD Portrait Footage
headers = {"Authorization": PEXELS_API_KEY}
pexels_url = f"https://api.pexels.com/videos/search?query={keyword}&orientation=portrait&per_page=10"
res = requests.get(pexels_url, headers=headers).json()

download_url = None
for video in res.get("videos", []):
    for f in video.get("video_files", []):
        if f.get("width") and f.get("height") and f["height"] > f["width"]:
            download_url = f["link"]
            break
    if download_url:
        break

if not download_url:
    download_url = "https://images.pexels.com/videos/854671/free-video-854671.mp4"

with open("raw_video.mp4", "wb") as f:
    f.write(requests.get(download_url).content)

# 4. Trim and scale to crisp 1080x1920 9:16
audio_clip = AudioFileClip("audio.mp3")
raw_clip = VideoFileClip("raw_video.mp4")

duration = audio_clip.duration
raw_clip = raw_clip.subclipped(0, min(raw_clip.duration, duration))
raw_clip = raw_clip.with_audio(audio_clip)
raw_clip.write_videofile("temp_stitched.mp4", codec="libx264", audio_codec="aac", fps=24)

raw_clip.close()
audio_clip.close()

# 5. Burn high-contrast bold centered captions using FFmpeg
words = voiceover.replace("'", "").split()
chunk_size = 4
formatted_lines = [" ".join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]
caption_display = "\\n".join(formatted_lines[:3])

ffmpeg_cmd = [
    "ffmpeg", "-y", "-i", "temp_stitched.mp4",
    "-vf", (
        f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
        f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
        f"text='{caption_display}':fontcolor=yellow:fontsize=52:line_spacing=24:"
        f"borderw=6:bordercolor=black:x=(w-text_w)/2:y=(h-text_h)/2"
    ),
    "-c:v", "libx264", "-c:a", "copy", "final.mp4"
]

subprocess.run(ffmpeg_cmd, check=True)

# 6. Send to Telegram
tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
caption_text = f"🔥 {title}\n\n🎙️ {voiceover}"

with open("final.mp4", "rb") as video_file:
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "caption": caption_text[:1024]
    }
    r = requests.post(tg_url, data=payload, files={"video": video_file})
    print(f"Telegram status: {r.status_code}")

print("Shorts generation complete.")
        
