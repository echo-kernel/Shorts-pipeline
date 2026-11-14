
import os
import json
import asyncio
import subprocess

import requests
import edge_tts
from google import genai

# ==================================================
# CONFIGURATION
# ==================================================

GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

MODEL = "gemini-3.8-flash"
VOICE = "en-US-ChristopherNeural"


# ==================================================
# CHECK REQUIRED PROGRAMS
# ==================================================

def check_dependencies():
    for command in ["ffmpeg", "ffprobe"]:
        subprocess.run(
            ["which", command],
            check=True,
            capture_output=True
        )


# ==================================================
# GEMINI SCRIPT GENERATION
# ==================================================

def create_script():
    client = genai.Client(api_key=GEMINI_API_KEY)

    prompt = """
Create a compelling YouTube Shorts script about a lesser-known
historical event or hero from Indian history.

Requirements:
- 105 to 120 spoken words.
- Start with a powerful hook.
- Use historically accurate information.
- Make the narration dramatic and engaging.
- Do not invent historical facts.
- Write natural spoken English.

Return only valid JSON in this format:

{
  "title": "Short video title",
  "voiceover": "Complete narration",
  "visual_story": "Brief visual description of the story"
}
"""

    print(f"Using Gemini model: {MODEL}")

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
        raise ValueError("Gemini returned an empty title or narration.")

    print("\nTITLE:", title)
    print("\nVOICEOVER:", voiceover)

    return title, voiceover, visual_story


# ==================================================
# TEXT TO SPEECH
# ==================================================

async def create_voice(text):
    print("Generating voice narration...")

    communicate = edge_tts.Communicate(
        text,
        VOICE,
        rate="+10%"
    )

    await communicate.save("voice.mp3")

    if not os.path.exists("voice.mp3"):
        raise FileNotFoundError("Voice generation failed.")


# ==================================================
# AUDIO DURATION
# ==================================================

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


# ==================================================
# SUBTITLE GENERATION
# ==================================================

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

    with open(
        "subtitles.srt",
        "w",
        encoding="utf-8"
    ) as file:

        for index, chunk in enumerate(chunks):
            start = index * chunk_duration
            end = min(
                (index + 1) * chunk_duration,
                duration
            )

            file.write(
                f"{index + 1}\n"
                f"{timestamp(start)} --> {timestamp(end)}\n"
                f"{chunk}\n\n"
            )

    print("Subtitles generated.")


# ==================================================
# AI VIDEO GENERATION
# ==================================================

def generate_video(story, duration):
    print("Starting AI video generation...")

    subprocess.run(
        [
            "python",
            "ai_video.py",
            story,
            str(duration)
        ],
        check=True
    )

    if not os.path.exists("ai_video.mp4"):
        raise FileNotFoundError("AI video was not generated.")


# ==================================================
# FINAL VIDEO ASSEMBLY
# ==================================================

def create_final_video(title, duration):
    print("Combining AI video, narration and subtitles...")

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

    subprocess.run(
        [
            "ffmpeg",
            "-y",
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
        ],
        check=True
    )

    if not os.path.exists("final.mp4"):
        raise FileNotFoundError("Final video was not created.")

    print("Final video created successfully!")


# ==================================================
# TELEGRAM UPLOAD
# ==================================================

def send_telegram(title):
    print("Uploading video to Telegram...")

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
        raise RuntimeError(
            f"Telegram upload failed: {result}"
        )

    print("Video successfully sent to Telegram!")


# ==================================================
# MAIN PIPELINE
# ==================================================

def main():
    print("================================")
    print(" AI HISTORICAL SHORTS GENERATOR")
    print("================================")

    check_dependencies()

    # Step 1: Generate script
    title, voiceover, visual_story = create_script()

    # Step 2: Generate narration
    asyncio.run(create_voice(voiceover))

    # Step 3: Get narration duration
    duration = min(
        59.0,
        get_audio_duration() + 0.5
    )

    print(f"Video duration: {duration:.2f} seconds")

    # Step 4: Generate subtitles
    create_subtitles(voiceover, duration)

    # Step 5: Prepare visual story
    story_for_video = (
        f"{title}. {visual_story}. {voiceover}"
    )

    # Step 6: Generate AI video
    generate_video(
        story_for_video,
        duration
    )

    # Step 7: Combine everything
    create_final_video(
        title,
        duration
    )

    # Step 8: Send to Telegram
    send_telegram(title)

    print("================================")
    print(" PIPELINE COMPLETED SUCCESSFULLY")
    print("================================")


if __name__ == "__main__":
    main()
        
