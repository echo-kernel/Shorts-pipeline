
import os
import re
import json
import time
import asyncio
import subprocess
from pathlib import Path

import requests
import edge_tts
from google import genai

from ai_video import generate_video

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
TOPIC = os.getenv(
    "VIDEO_TOPIC",
    "U Tirot Sing and the Khasi resistance against British expansion in 1829"
)
VOICE = os.getenv("TTS_VOICE", "hi-IN-MadhurNeural")

OUTPUT_DIR = Path("output")
WORK_DIR = OUTPUT_DIR / "work"
OUTPUT_DIR.mkdir(exist_ok=True)
WORK_DIR.mkdir(exist_ok=True)


class TelegramProgress:
    def __init__(self):
        self.bot = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat = os.getenv("TELEGRAM_CHAT_ID", "")
        self.message_id = None
        self.started = time.monotonic()
        self.stage_started = self.started
        self.stage_times = {}
        self.retries = 0

    def enabled(self):
        return bool(self.bot and self.chat)

    def send(self, text):
        if not self.enabled():
            print("Telegram progress disabled: missing Telegram secrets.")
            return

        try:
            response = requests.post(
                f"https://api.telegram.org/bot{self.bot}/sendMessage",
                json={"chat_id": self.chat, "text": text},
                timeout=20
            )
            response.raise_for_status()
            data = response.json()

            if data.get("ok"):
                self.message_id = data["result"]["message_id"]
        except Exception as exc:
            print(f"Telegram progress send failed: {exc}")

    def update(self, percent, stage, detail=""):
        elapsed = int(time.monotonic() - self.started)
        stage_elapsed = int(time.monotonic() - self.stage_started)

        text = (
            f"🎬 AI HISTORICAL SHORTS\n\n"
            f"Progress: {percent}%\n"
            f"Stage: {stage}\n"
            f"{detail}\n\n"
            f"Current stage time: {stage_elapsed}s\n"
            f"Total elapsed: {elapsed}s\n"
            f"Retries: {self.retries}"
        )

        print(text)

        if not self.enabled():
            return

        try:
            if self.message_id is None:
                self.send(text)
            else:
                response = requests.post(
                    f"https://api.telegram.org/bot{self.bot}/editMessageText",
                    json={
                        "chat_id": self.chat,
                        "message_id": self.message_id,
                        "text": text
                    },
                    timeout=20
                )
                response.raise_for_status()
        except Exception as exc:
            print(f"Telegram progress update failed: {exc}")

    def start_stage(self, percent, stage, detail=""):
        now = time.monotonic()

        if hasattr(self, "current_stage"):
            self.stage_times[self.current_stage] = (
                self.stage_times.get(self.current_stage, 0)
                + now - self.stage_started
            )

        self.current_stage = stage
        self.stage_started = now
        self.update(percent, stage, detail)

    def finish(self, success, title="", error=""):
        now = time.monotonic()

        if hasattr(self, "current_stage"):
            self.stage_times[self.current_stage] = (
                self.stage_times.get(self.current_stage, 0)
                + now - self.stage_started
            )

        total = int(now - self.started)
        timings = "\n".join(
            f"• {name}: {int(seconds)}s"
            for name, seconds in self.stage_times.items()
        )

        if success:
            message = (
                "✅ AI HISTORICAL SHORTS: COMPLETE\n\n"
                f"Title: {title}\n"
                f"Total time: {total}s\n"
                f"Retries: {self.retries}\n\n"
                f"Stage timings:\n{timings}"
            )
            self.update(100, "Completed", f"Title: {title}")
        else:
            message = (
                "❌ AI HISTORICAL SHORTS: FAILED\n\n"
                f"Error: {error}\n"
                f"Total time: {total}s\n"
                f"Retries: {self.retries}\n\n"
                f"Stage timings:\n{timings}"
            )

        print(message)

        if self.enabled():
            try:
                requests.post(
                    f"https://api.telegram.org/bot{self.bot}/sendMessage",
                    json={"chat_id": self.chat, "text": message},
                    timeout=20
                ).raise_for_status()
            except Exception as exc:
                print(f"Telegram final report failed: {exc}")


tracker = TelegramProgress()


def run_command(command):
    print("Running:", " ".join(map(str, command)))
    subprocess.run(command, check=True)


def get_duration(filename):
    result = subprocess.check_output([
        "ffprobe", "-v", "error",
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


def create_story():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY secret is missing.")

    client = genai.Client(api_key=api_key)

    prompt = f"""
Create a historically responsible YouTube Short about:
{TOPIC}

Return ONLY valid JSON:
{{
  "title": "Short engaging title",
  "voiceover": "Hindi narration, approximately 105 to 120 words",
  "scenes": [
    "Cinematic English video prompt 1",
    "Cinematic English video prompt 2",
    "Cinematic English video prompt 3",
    "Cinematic English video prompt 4"
  ]
}}

Requirements:
- Natural Hindi documentary narration.
- Historically accurate; do not invent quotations or events.
- Four visually different realistic cinematic scenes.
- Describe clothing, architecture, environment, lighting and camera movement.
- No modern objects, text, logos, watermarks or fantasy elements.
- Vertical 9:16 composition.
"""

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config={"response_mime_type": "application/json"}
    )

    data = clean_json(response.text)

    if len(data.get("scenes", [])) != 4:
        raise RuntimeError("Gemini did not return exactly four scenes.")

    if not data.get("voiceover"):
        raise RuntimeError("Gemini returned an empty narration.")

    return data


async def create_voice(text, filename):
    communicate = edge_tts.Communicate(
        text=text,
        voice=VOICE,
        rate="-5%",
        volume="+0%"
    )
    await communicate.save(str(filename))


def generate_voice(text):
    voice_file = WORK_DIR / "narration.mp3"
    asyncio.run(create_voice(text, voice_file))

    if not voice_file.exists() or voice_file.stat().st_size < 1000:
        raise RuntimeError("Voice generation failed.")

    return voice_file


def make_srt(text, duration, filename):
    words = text.split()
    if not words:
        raise RuntimeError("Narration has no words.")

    groups = [words[i:i + 5] for i in range(0, len(words), 5)]
    segment_duration = duration / len(groups)

    def stamp(seconds):
        milliseconds = int(seconds * 1000)
        hours = milliseconds // 3600000
        minutes = (milliseconds % 3600000) // 60000
        seconds_part = (milliseconds % 60000) // 1000
        millis = milliseconds % 1000
        return f"{hours:02}:{minutes:02}:{seconds_part:02},{millis:03}"

    with open(filename, "w", encoding="utf-8") as file:
        for index, group in enumerate(groups):
            start = index * segment_duration
            end = min(duration, (index + 1) * segment_duration)
            file.write(f"{index + 1}\n")
            file.write(f"{stamp(start)} --> {stamp(end)}\n")
            file.write(" ".join(group) + "\n\n")


def create_clips(scenes):
    clips = []

    for index, scene in enumerate(scenes, start=1):
        output = WORK_DIR / f"scene_{index}.mp4"
        percent = 25 + index * 9

        tracker.start_stage(
            percent,
            f"Generating scene {index}/4",
            f"Completed scenes: {index - 1}/4"
        )

        def retry_callback(attempt, maximum, error, wait):
            tracker.retries += 1
            tracker.update(
                percent,
                f"Retrying scene {index}/4",
                f"Attempt {attempt}/{maximum} failed.\n"
                f"Reason: {error[:300]}\n"
                f"Retrying in {wait}s"
            )

        generate_video(
            prompt=scene,
            output_path=output,
            duration=5,
            on_retry=retry_callback
        )

        clips.append(output)

    return clips


def normalize_clips(clips):
    normalized = []

    for index, clip in enumerate(clips, start=1):
        tracker.update(
            65 + index * 3,
            "Normalizing clips",
            f"Processing clip {index}/4"
        )

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


def send_telegram(video, title):
    bot = os.getenv("TELEGRAM_BOT_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID")

    if not bot or not chat:
        print("Telegram video upload skipped: Telegram secrets missing.")
        return

    with open(video, "rb") as file:
        response = requests.post(
            f"https://api.telegram.org/bot{bot}/sendVideo",
            data={
                "chat_id": chat,
                "caption": f"🎬 {title}\nYour AI historical Short is ready!"
            },
            files={"video": file},
            timeout=(30, 600)
        )

    response.raise_for_status()

    if not response.json().get("ok"):
        raise RuntimeError(f"Telegram upload failed: {response.text}")


def main():
    try:
        tracker.start_stage(2, "Starting pipeline")

        tracker.start_stage(5, "Creating historical story")
        story = create_story()

        print("Title:", story["title"])
        print("Narration:", story["voiceover"])

        with open(OUTPUT_DIR / "story.json", "w", encoding="utf-8") as file:
            json.dump(story, file, ensure_ascii=False, indent=2)

        tracker.start_stage(18, "Generating Hindi narration")
        voice = generate_voice(story["voiceover"])

        tracker.start_stage(25, "Preparing four AI scenes")
        clips = create_clips(story["scenes"])

        tracker.start_stage(65, "Normalizing video clips")
        normalized = normalize_clips(clips)

        tracker.start_stage(78, "Joining scenes")
        joined = join_clips(normalized)

        tracker.start_stage(85, "Adding narration and subtitles")
        final_video = assemble_final_video(
            joined, voice, story["voiceover"]
        )

        tracker.start_stage(94, "Uploading final video to Telegram")
        send_telegram(final_video, story["title"])

        tracker.finish(True, title=story["title"])

        print("SUCCESS!")
        print("Final video:", final_video)

    except Exception as exc:
        tracker.finish(False, error=f"{type(exc).__name__}: {exc}")
        raise


if __name__ == "__main__":
    main()
                                     
