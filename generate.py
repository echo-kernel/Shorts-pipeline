
import os
import re
import json
import asyncio
import subprocess
from pathlib import Path

import requests
import edge_tts
from google import genai

# ---------------- CONFIGURATION ----------------

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

MODEL = "gemini-2.5-flash"
VOICE = "en-US-ChristopherNeural"

# ---------------- CHECK DEPENDENCIES ----------------

for command in ["ffmpeg", "ffprobe"]:
    subprocess.run(
        ["which", command],
        check=True,
        capture_output=True
    )

# ---------------- GEMINI SCRIPT ----------------

def create_script():
    client = genai.Client(api_key=GEMINI_API_KEY)

    prompt = """
    Create a compelling YouTube Shorts script about a lesser-known
    historical event or hero from Indian history.

    Requirements:
    - 105 to 120 spoken words.
    - Start with a powerful hook.
    - Use accurate historical information.
    - Make it dramatic and interesting.
    - Write natural spoken English.
    - Do not invent historical facts.

    Return only valid JSON in this format:
    {
      "title": "Short video title",
      "voiceover": "Complete narration",
      "visual_story": "Brief visual description of the story"
    }
    """

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config={
            "response_mime_type": "application/json"
        }
    )

    data = json.loads(response.text)

    title = data["title"].strip()
    voiceover = data["voiceover"].strip()
    visual_story = data.get("visual_story", "").strip()

    if not title or not voiceover:
        raise ValueError("Gemini returned an empty script.")

    print("Title:", title)
    print("Voiceover:", voiceover)

    return title, voiceover, visual_story


# ---------------- TEXT TO SPEECH ----------------

async def create_voice(text):
    communicate = edge_tts.Communicate(
        text,
        VOICE,
        rate="+10%"
    )

    await communicate.save("voice.mp3")


# ---------------- AUDIO DURATION ----------------

def get_audio_duration():
    result = subprocess.run(
        [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            "voice.mp3"
        ],
        capture_output=True,
        text=True,
        check=True
    )

    return float(result.stdout.strip())


# ---------------- SUBTITLES ----------------

def create_subtitles(text, duration):
    words = text.split()
    chunks = [
        " ".join(words[i:i + 4])
        for i in range(0, len(words), 4)
    ]

    chunk_duration = duration / max(len(chunks), 1)

    def timestamp(seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        seconds = seconds % 60

        return (
            f"{hours:02}:"
            f"{minutes:02}:"
            f"{seconds:06.3f}".replace(".", ",")
        )

    with open("subtitles.srt", "w", encoding="utf-8") as file:
        for index, chunk in enumerate(chunks):
            start = index * chunk_duration
            end = min((index + 1) * chunk_duration, duration)

            file.write(
                f"{index + 1}\n"
                f"{timestamp(start)} --> {timestamp(end)}\n"
                f"{chunk}\n\n"
            )


# ---------------- AI VIDEO ----------------

def generate_video(story, duration):
    subprocess.run(
        [
            "python",
            "ai_video.py",
            story,
            str(duration)
        ],
        check=True
    )


# ---------------- FINAL VIDEO ----------------

def create_final_video(title, duration):
    subtitle_filter = (
        "subtitles=subtitles.srt:"
        "force_style='FontName=DejaVu Sans,"
        "FontSize=18,"
        "Bold=1,"
        "PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,"
        "BorderStyle=1,"
        "Outline=3,"
        "Shadow=1,"
        "Alignment=2,"
        "MarginV=130'"
    )

    subprocess.run([
        "ffmpeg", "-y",
        "-i", "ai_video.mp4",
        "-i", "voice.mp3",
        "-vf", subtitle_filter,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-t", str(duration),
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-shortest",
        "-pix_fmt", "yuv420p",
        "final.mp4"
    ], check=True)

    print("Final video created successfully!")


# ---------------- TELEGRAM UPLOAD ----------------

def send_telegram(title):
    url = (
        f"https://api.telegram.org/"
        f"bot{TELEGRAM_BOT_TOKEN}/sendVideo"
    )

    with open("final.mp4", "rb") as video:
        response = requests.post(
            url,
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "caption": title
            },
            files={
                "video": (
                    "final.mp4",
                    video,
                    "video/mp4"
                )
            },
            timeout=300
        )

    response.raise_for_status()

    result = response.json()

    if not result.get("ok"):
        raise RuntimeError(f"Telegram upload failed: {result}")

    print("Video sent successfully to Telegram!")


# ---------------- MAIN ----------------

def main():
    print("Creating historical script...")

    title, voiceover, visual_story = create_script()

    print("Creating narration...")

    asyncio.run(create_voice(voiceover))

    duration = min(
        59.0,
        get_audio_duration() + 0.5
    )

    print(f"Audio duration: {duration:.2f} seconds")

    create_subtitles(voiceover, duration)

    story_for_video = (
        f"{title}. {visual_story}. {voiceover}"
    )

    print("Generating AI video...")

    generate_video(story_for_video, duration)

    print("Combining video, voice and subtitles...")

    create_final_video(title, duration)

    print("Sending video to Telegram...")

    send_telegram(title)


if __name__ == "__main__":
    main()
        
