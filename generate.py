import os
import json
import asyncio
import requests
import edge_tts
from google import genai
from moviepy import VideoFileClip, AudioFileClip

# Read keys from GitHub secrets
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
PEXELS_API_KEY = os.environ["PEXELS_API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

print("1. Generating script with Gemini...")
client = genai.Client(api_key=GEMINI_API_KEY)
prompt = (
    "Create a compelling, punchy 15-second tech, astronomy, or science fact for a YouTube Short. "
    "Return strictly JSON with keys: 'title', 'voiceover', and 'keyword'. "
    "'keyword' must be one single word describing the background visual (e.g., galaxy, computer, robot, ocean)."
)

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=prompt,
    config={"response_mime_type": "application/json"}
)
data = json.loads(response.text)
title = data.get("title", "Daily Short Fact")
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

# Grab the first valid vertical download link
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

with open("raw_video.mp4", "wb") as f:
    f.write(requests.get(download_url).content)

print("4. Stitched video with MoviePy & FFmpeg...")
audio_clip = AudioFileClip("audio.mp3")
video_clip = VideoFileClip("raw_video.mp4")

# Trim or loop video to match voice length
target_duration = audio_clip.duration
if video_clip.duration < target_duration:
    video_clip = video_clip.with_effects([])  # Keep native duration
video_clip = video_clip.subclipped(0, min(video_clip.duration, target_duration))
final_video = video_clip.with_audio(audio_clip)

final_video.write_videofile("final.mp4", codec="libx264", audio_codec="aac", fps=24)

# Close clips to free memory
audio_clip.close()
video_clip.close()
final_video.close()

print("5. Sending video preview to Telegram...")
tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
caption_text = f"🎬 *{title}*\n\n📝 _{voiceover}_"

with open("final.mp4", "rb") as video_file:
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "caption": caption_text,
        "parse_mode": "Markdown"
    }
    r = requests.post(tg_url, data=payload, files={"video": video_file})
    print(f"Telegram status: {r.status_code}")

print("Done! Video successfully sent to Telegram.")
