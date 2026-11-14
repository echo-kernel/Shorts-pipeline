import os
import json
import time
import math
import wave
import struct
import random
import asyncio
import subprocess
import requests
import edge_tts
from google import genai
from moviepy import AudioFileClip

# 1. Load Secrets
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

FALLBACK_FACTS = [
    {
        "title": "What Happens If You Fall Into a Black Hole",
        "voiceover": (
            "If you ever fell toward a stellar black hole, the first thing you would notice is that the universe above you shrinks into a bright glowing circle. "
            "Because gravity bends light so violently near the event horizon, light from every star in the sky gets focused directly behind your head. "
            "At the same time, gravitational time dilation stretches every second you experience. "
            "To an astronaut watching from a safe distance, you would appear to slow down, turn red, and freeze completely at the edge forever. "
            "Yet from your own perspective, time outside speeds up so fast that you could watch billions of years of cosmic history flash before your eyes in moments. "
            "Finally, tidal forces stretch you atom by atom in a process physicists literally call spaghettification, turning matter into a single stream of particles."
        )
    },
    {
        "title": "Why Neutron Stars Break the Laws of Matter",
        "voiceover": (
            "Imagine taking a star twice as massive as our entire Sun and crushing it down into a spinning sphere no wider than a single city. "
            "That is a neutron star, the collapsed core left behind after a massive supernova explosion. "
            "The gravity is so extreme that electrons are smashed directly into protons, fusing them into pure neutrons packed shoulder to shoulder. "
            "Just one single teaspoon of neutron star material weighs over a billion tons on Earth, roughly the weight of Mount Everest compressed into a sugar cube. "
            "Even wilder, these cosmic monsters can spin up to seven hundred times every second, firing beams of radiation across the galaxy like a lighthouse. "
            "If two of them ever collide, they send ripples through spacetime itself and forge most of the gold and platinum in our universe."
        )
    }
]

prompt = (
    "Write a captivating 45 to 55 second YouTube Shorts script (around 105 to 125 words) about an extraordinary physics, space, or quantum science phenomenon. "
    "Structure it with: "
    "1) An immediate 3-second curiosity hook in the first sentence. "
    "2) Three escalating, mind-blowing explanations that build tension. "
    "3) A memorable final takeaway sentence. "
    "Use clean, natural spoken English with zero emojis, bullet points, or special symbols in the voiceover. "
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

title = data.get("title", "Deep Space Physics")
voiceover = data.get("voiceover", "").strip()

print(f"Title: {title}")
print(f"Word count: {len(voiceover.split())} words")

# 2. Generate Neural Voiceover
async def generate_voice():
    communicate = edge_tts.Communicate(voiceover, "en-US-ChristopherNeural", rate="+10%")
    await communicate.save("voice.mp3")

asyncio.run(generate_voice())

voice_clip = AudioFileClip("voice.mp3")
raw_duration = voice_clip.duration
voice_clip.close()

# Keep total duration cleanly inside 40-60s bounds (max 59.0s so YouTube always treats it as a Short)
duration = round(min(59.0, raw_duration + 0.5), 2)
print(f"Final video duration: {duration} seconds")

# 3. Synthesize Deep Cinematic Sci-Fi Ambient Drone (WAV)
sample_rate = 44100
num_samples = int(duration * sample_rate)
with wave.open("bg_drone.wav", "w") as wav_file:
    wav_file.setnchannels(1)
    wav_file.setsampwidth(2)
    wav_file.setframerate(sample_rate)
    frames_data = bytearray()
    for i in range(num_samples):
        t = i / sample_rate
        lfo = 0.6 + 0.4 * math.sin(2 * math.pi * 0.25 * t)
        val = (
            0.55 * math.sin(2 * math.pi * 55.0 * t) +
            0.30 * math.sin(2 * math.pi * 82.41 * t) +
            0.15 * math.sin(2 * math.pi * 110.0 * t)
        ) * lfo * 0.14
        sample_int = max(-32767, min(32767, int(val * 32767)))
        frames_data.extend(struct.pack("<h", sample_int))
    wav_file.writeframes(frames_data)

# Mix Voiceover + Ambient Sci-Fi Drone via FFmpeg
subprocess.run([
    "ffmpeg", "-y", "-i", "voice.mp3", "-i", "bg_drone.wav",
    "-filter_complex", "[0:a]volume=1.15[v];[1:a]volume=0.85[bg];[v][bg]amix=inputs=2:duration=first[a]",
    "-map", "[a]", "-c:a", "libmp3lame", "-q:a", "2", "audio.mp3"
], check=True)

# 4. Create Dynamic Timed SRT Subtitles (3 bold uppercase words at a time)
def format_srt_time(seconds):
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds - int(seconds)) * 1000)
    return f"{hrs:02}:{mins:02}:{secs:02},{millis:03}"

words = voiceover.split()
chunk_size = 3
chunks = [" ".join(words[i:i+chunk_size]) for i in range(0, len(words), chunk_size)]
speak_duration = min(raw_duration, duration - 0.3)
time_per_chunk = speak_duration / max(1, len(chunks))

with open("subs.srt", "w", encoding="utf-8") as srt_file:
    for idx, chunk in enumerate(chunks):
        start_t = idx * time_per_chunk
        end_t = (idx + 1) * time_per_chunk
        srt_file.write(f"{idx + 1}\n")
        srt_file.write(f"{format_srt_time(start_t)} --> {format_srt_time(end_t)}\n")
        srt_file.write(f"{chunk.upper()}\n\n")

# 5. Render Full 3D Animation via Headless Blender
print("Executing Blender 3D engine...")
subprocess.run(["blender", "-b", "-P", "render_3d.py", "--", str(duration)], check=True)
subprocess.run([
    "ffmpeg", "-y", "-framerate", "24", "-i", "frames/frame_%04d.jpg",
    "-c:v", "libx264", "-pix_fmt", "yuv420p", "blender_3d_render.mp4"
], check=True)

# 6. Merge Audio + 3D Video & Burn High-Contrast Captions
ffmpeg_cmd = [
    "ffmpeg", "-y",
    "-i", "blender_3d_render.mp4",
    "-i", "audio.mp3",
    "-vf", (
        "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
        "subtitles=subs.srt:force_style='FontName=DejaVu Sans,FontSize=23,"
        "PrimaryColour=&H0000FFFF,OutlineColour=&H00000000,BackColour=&H80000000,"
        "BorderStyle=1,Outline=3,Shadow=2,Alignment=10,Bold=1'"
    ),
    "-c:v", "libx264", "-crf", "18", "-preset", "fast",
    "-c:a", "aac", "-b:a", "192k", "-t", str(duration), "final.mp4"
]
subprocess.run(ffmpeg_cmd, check=True)

# 7. Send Video Preview to Telegram
tg_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
caption_text = f"🪐 3D Rendered Short ({int(duration)}s): {title}\n\n🎙️ {voiceover}"

with open("final.mp4", "rb") as video_file:
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "caption": caption_text[:1024]
    }
    r = requests.post(tg_url, data=payload, files={"video": video_file})
    print(f"Telegram status: {r.status_code}")

print("40-60s 3D Short generated and sent successfully.")
