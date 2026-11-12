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
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

FALLBACK_FACTS = [
    {
        "title": "Why Prince Rupert Drops Defy Physics",
        "voiceover": "Hit a Prince Rupert drop with a hydraulic press and it will shatter the steel instead. Shoot it with a bullet and the bullet explodes on impact. Yet snap its tiny glass tail with your fingers and the entire drop disintegrates instantly."
    },
    {
        "title": "A Day on Venus is Longer Than Its Year",
        "voiceover": "Venus spins so slowly on its axis that a single day on Venus lasts longer than an entire year orbiting around the Sun."
    },
    {
        "title": "The Weight of a Neutron Star",
        "voiceover": "Neutron stars are collapsed stellar cores so dense that just one sugar cube of their material would weigh a billion tons on Earth."
    }
]

prompt = (
    "Create a punchy 14-16 second mindblowing physics, astronomy, or science fact for YouTube Shorts. "
    "Use clean, natural English sentences without weird symbols. "
    "Return strictly JSON with keys: 'title' and 'voiceover'."
)

client = genai.Client(api_key=GEMINI_API_KEY)
models_to_try = ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-2.5-flash"]
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

title = data.get("title", "Physics Fact")
voiceover = data.get("voiceover", "").strip()

print(f"Title: {title}")
print(f"Voiceover: {voiceover}")

# 2. Generate Neural Voiceover
async def generate_voice():
    communicate = edge_tts.Communicate(voiceover, "en-US-ChristopherNeural", rate="+10%")
    await communicate.save("audio.mp3")

asyncio.run(generate_voice())

audio_clip = AudioFileClip("audio.mp3")
duration = round(audio_clip.duration, 2)
audio_clip.close()
print(f"Audio duration: {duration} seconds")

# 3. Create Dynamic Timed SRT Subtitles (3 words per popup so nothing gets cut off)
def format_srt_time(seconds):
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hrs:02}:{mins:02}:{secs:02},{millis:03}"

words = voiceover.split()
chunk_size = 3
chunks = [" ".join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]
time_per_chunk = duration / max(1, len(chunks))

with open("subs.srt", "w", encoding="utf-8") as srt_file:
    for idx, chunk in enumerate(chunks):
        start_t = idx * time_per_chunk
        end_t = (idx + 1) * time_per_chunk
        srt_file.write(f"{idx + 1}\n")
        srt_file.write(f"{format_srt_time(start_t)} --> {format_srt_time(end_t)}\n")
        srt_file.write(f"{chunk.upper()}\n\n")

# 4. Render Full 3D Animation via Headless Blender
print("Executing Blender 3D engine...")
subprocess.run(["blender", "-b", "-P", "render_3d.py", "--", str(duration)], check=True)

# 5. Merge Audio + 3D Video
video_clip = VideoFileClip("blender_3d_render.mp4")
audio_clip = AudioFileClip("audio.mp3")
video_clip = video_clip.subclipped(0, min(video_clip.duration, audio_clip.duration)).with_audio(audio_clip)
video_clip.write_videofile("temp_stitched.mp4", codec="libx264", audio_codec="aac", fps=24)

video_clip.close()
audio_clip.close()

# 6. Burn Dynamic Timed Subtitles (Centered, Auto-Wrapped, High-Contrast Yellow)
ffmpeg_cmd = [
    "ffmpeg", "-y", "-i", "temp_stitched.mp4",
    "-vf", (
        "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
        "subtitles=subs.srt:force_style='FontName=DejaVu Sans,FontSize=22,"
        "PrimaryColour=&H0000FFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=3,"
        "Alignment=10,Bold=1'"
    ),
    "-c:v", "libx264", "-crf", "18", "-c:a", "copy", "final.mp4"
]
subprocess.run(ffmpeg_cmd, check=True)

# 7. Send Video Preview to Telegram
tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
caption_text = f"🪐 3D Rendered Short: {title}\n\n🎙️ {voiceover}"

with open("final.mp4", "rb") as video_file:
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "caption": caption_text[:1024]
    }
    r = requests.post(tg_url, data=payload, files={"video": video_file})
    print(f"Telegram status: {r.status_code}")

print("3D Short with dynamic captions completed.")
    
