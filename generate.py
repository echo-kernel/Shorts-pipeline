
import os
import re
import json
import subprocess
import requests
from pathlib import Path

import edge_tts
from google import genai

from ai_video import generate_video


# ---------------- CONFIGURATION ----------------

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
TOPIC = os.getenv(
    "VIDEO_TOPIC",
    "U Tirot Sing and the Khasi resistance against British expansion in 1829"
)

VOICE = os.getenv("TTS_VOICE", "hi-IN-MadhurNeural")
OUTPUT_DIR = Path("output")
WORK_DIR = OUTPUT_DIR / "work"

OUTPUT_DIR.mkdir(exist_ok=True)
WORK_DIR.mkdir(exist_ok=True)


# ---------------- UTILITIES ----------------

def run_command(command):
    print("Running:", " ".join(map(str, command)))
    subprocess.run(command, check=True)


def get_duration(filename):
    result = subprocess.check_output([
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(filename)
    ])
    return float(result.decode().strip())


def clean_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text)
    text = re.sub(r"```$", "", text)
    return json.loads(text.strip())


# ---------------- GEMINI SCRIPT ----------------

def create_story():
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError("GEMINI_API_KEY secret is missing.")

    client = genai.Client(api_key=api_key)

    prompt = f"""
Create a historically responsible YouTube Short about:

{TOPIC}

Return ONLY valid JSON with this structure:
{{
  "title": "Short engaging title",
  "voiceover": "Hindi narration, approximately 105 to 120 words",
  "scenes": [
    "Detailed English cinematic video prompt for scene 1",
    "Detailed English cinematic video prompt for scene 2",
    "Detailed English cinematic video prompt for scene 3",
    "Detailed English cinematic video prompt for scene 4"
  ]
}}

Requirements:
- Narration must be natural Hindi.
- Use a powerful documentary storytelling style.
- Keep historical details accurate.
- Do not invent quotations, dates, battles, or events.
- If a detail is uncertain, avoid presenting it as fact.
- Each scene prompt must describe a realistic cinematic historical scene.
- Specify clothing, architecture, environment, lighting and camera movement.
- No modern objects, text, logos, watermarks or fantasy elements.
- Each scene should be visually different.
- Vertical 9:16 composition.
"""

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config={"response_mime_type": "application/json"}
    )

    data = clean_json(response.text)

    if len(data.get("scenes", [])) != 4:
        raise RuntimeError("Gemini did not return exactly four scene prompts.")

    if not data.get("voiceover"):
        raise RuntimeError("Gemini returned an empty narration.")

    return data


# ---------------- HINDI NARRATION ----------------

async def create_voice(text, filename):
    communicate = edge_tts.Communicate(
        text=text,
        voice=VOICE,
        rate="-5%",
        volume="+0%"
    )
    await communicate.save(str(filename))


def generate_voice(text):
    import asyncio

    voice_file = WORK_DIR / "narration.mp3"
    asyncio.run(create_voice(text, voice_file))

    if not voice_file.exists() or voice_file.stat().st_size < 1000:
        raise RuntimeError("Voice generation failed.")

    return voice_file


# ---------------- SUBTITLES ----------------

def make_srt(text, duration, filename):
    words = text.split()

    if not words:
        raise RuntimeError("Narration has no words.")

    # Display approximately five words at a time.
    groups = [
        words[i:i + 5]
        for i in range(0, len(words), 5)
    ]

    segment_duration = duration / len(groups)

    def stamp(seconds):
        milliseconds = int(seconds * 1000)
        hours = milliseconds // 3600000
        minutes = (milliseconds % 3600000) // 60000
        seconds_part = (milliseconds % 60000) // 1000
        millis = milliseconds % 1000

        return (
            f"{hours:02}:{minutes:02}:"
            f"{seconds_part:02},{millis:03}"
        )

    with open(filename, "w", encoding="utf-8") as file:
        for index, group in enumerate(groups):
            start = index * segment_duration
            end = min(duration, (index + 1) * segment_duration)

            file.write(f"{index + 1}\n")
            file.write(f"{stamp(start)} --> {stamp(end)}\n")
            file.write(" ".join(group) + "\n\n")


# ---------------- VIDEO GENERATION ----------------

def create_clips(scenes):
    clips = []

    for index, scene in enumerate(scenes, start=1):
        output = WORK_DIR / f"scene_{index}.mp4"

        print(f"\nGenerating AI scene {index}/4")

        generate_video(
            prompt=scene,
            output_path=output,
            duration=5
        )

        clips.append(output)

    return clips


# ---------------- VIDEO ASSEMBLY ----------------

def normalize_clips(clips):
    normalized = []

    for index, clip in enumerate(clips, start=1):
        output = WORK_DIR / f"normalized_{index}.mp4"

        run_command([
            "ffmpeg", "-y",
            "-i", str(clip),
            "-an",
            "-vf",
            "scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,fps=24,setsar=1",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(output)
        ])

        normalized.append(output)

    return normalized


def join_clips(clips):
    concat_file = WORK_DIR / "clips.txt"

    with open(concat_file, "w", encoding="utf-8") as file:
        for clip in clips:
            file.write(f"file '{clip.resolve()}'\n")

    joined = WORK_DIR / "joined.mp4"

    run_command([
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        "-c", "copy",
        str(joined)
    ])

    return joined


def assemble_final_video(joined, voice, narration):
    voice_duration = get_duration(voice)

    subtitles = WORK_DIR / "captions.srt"
    make_srt(narration, voice_duration, subtitles)

    final_video = OUTPUT_DIR / "historical_short.mp4"

    subtitle_filter = (
        "subtitles=captions.srt:"
        "force_style='FontName=DejaVu Sans,"
        "FontSize=18,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,BorderStyle=1,"
        "Outline=2,Shadow=1,Alignment=2,MarginV=120'"
    )

    # Run FFmpeg from WORK_DIR so the subtitle filename is simple.
    run_command([
        "ffmpeg", "-y",
        "-stream_loop", "-1",
        "-i", str(joined.resolve()),
        "-i", str(voice.resolve()),
        "-vf", subtitle_filter,
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-t", str(voice_duration),
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        str(final_video.resolve())
    ])

    if not final_video.exists() or final_video.stat().st_size < 10000:
        raise RuntimeError("Final video was not created correctly.")

    return final_video


# ---------------- TELEGRAM DELIVERY ----------------

def send_telegram(video):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:
        print("Telegram secrets not configured. Skipping upload.")
        return

    url = f"https://api.telegram.org/bot{token}/sendVideo"

    with open(video, "rb") as file:
        response = requests.post(
            url,
            data={
                "chat_id": chat_id,
                "caption": "Your AI historical YouTube Short is ready!"
            },
            files={"video": file},
            timeout=(30, 600)
        )

    response.raise_for_status()

    if not response.json().get("ok"):
        raise RuntimeError(f"Telegram upload failed: {response.text}")

    print("Telegram upload completed.")


# ---------------- MAIN ----------------

def main():
    print("\n========== AI HISTORICAL SHORTS ==========\n")

    print("1. Creating historical story...")
    story = create_story()

    print("Title:", story["title"])
    print("Narration:", story["voiceover"])

    with open(OUTPUT_DIR / "story.json", "w", encoding="utf-8") as file:
        json.dump(story, file, ensure_ascii=False, indent=2)

    print("\n2. Generating Hindi voice...")
    voice = generate_voice(story["voiceover"])

    print("\n3. Generating four AI video scenes...")
    clips = create_clips(story["scenes"])

    print("\n4. Preparing vertical video...")
    normalized = normalize_clips(clips)
    joined = join_clips(normalized)

    print("\n5. Adding narration and subtitles...")
    final_video = assemble_final_video(
        joined,
        voice,
        story["voiceover"]
    )

    print("\n6. Sending to Telegram...")
    send_telegram(final_video)

    print("\nSUCCESS!")
    print("Final video:", final_video)
    print("Title:", story["title"])


if __name__ == "__main__":
    main()
        
