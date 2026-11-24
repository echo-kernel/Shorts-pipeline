
import os
import re
import json
import time
import asyncio
import subprocess
import math
import random
import wave
from array import array
from pathlib import Path

import requests
import edge_tts

from ai_video import generate_video


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
        self.current_stage = None
        self.active_model = "Not selected"

    def enabled(self):
        return bool(self.bot and self.chat)

    def send(self, message):
        if not self.enabled():
            return

        try:
            response = requests.post(
                f"https://api.telegram.org/bot{self.bot}/sendMessage",
                json={
                    "chat_id": self.chat,
                    "text": message
                },
                timeout=20
            )

            response.raise_for_status()
            data = response.json()

            if data.get("ok"):
                self.message_id = data["result"]["message_id"]

        except Exception as exc:
            print(f"Telegram send error: {exc}")

    def update(self, percent, stage, detail=""):
        elapsed = int(time.monotonic() - self.started)
        stage_elapsed = int(time.monotonic() - self.stage_started)

        message = (
            "🎬 AI HISTORICAL SHORTS\n\n"
            f"Progress: {percent}%\n"
            f"Stage: {stage}\n"
            f"{detail}\n\n"
            f"Gemini model: {self.active_model}\n"
            f"Stage time: {stage_elapsed}s\n"
            f"Total time: {elapsed}s\n"
            f"Retries: {self.retries}"
        )

        print(message)

        if not self.enabled():
            return

        try:
            if self.message_id is None:
                self.send(message)
            else:
                response = requests.post(
                    f"https://api.telegram.org/bot{self.bot}/editMessageText",
                    json={
                        "chat_id": self.chat,
                        "message_id": self.message_id,
                        "text": message
                    },
                    timeout=20
                )

                response.raise_for_status()

        except Exception as exc:
            print(f"Telegram update error: {exc}")

    def start_stage(self, percent, stage, detail=""):
        now = time.monotonic()

        if self.current_stage:
            self.stage_times[self.current_stage] = (
                self.stage_times.get(self.current_stage, 0)
                + now - self.stage_started
            )

        self.current_stage = stage
        self.stage_started = now

        self.update(percent, stage, detail)

    def finish(self, success, title="", error=""):
        now = time.monotonic()

        if self.current_stage:
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
                f"Gemini model: {self.active_model}\n"
                f"Total time: {total}s\n"
                f"Retries: {self.retries}\n\n"
                f"Stage timings:\n{timings}"
            )
        else:
            message = (
                "❌ AI HISTORICAL SHORTS: FAILED\n\n"
                f"Error: {error}\n"
                f"Last Gemini model: {self.active_model}\n"
                f"Total time: {total}s\n"
                f"Retries: {self.retries}\n\n"
                f"Stage timings:\n{timings}"
            )

        print(message)

        if self.enabled():
            try:
                requests.post(
                    f"https://api.telegram.org/bot{self.bot}/sendMessage",
                    json={
                        "chat_id": self.chat,
                        "text": message
                    },
                    timeout=20
                ).raise_for_status()

            except Exception as exc:
                print(f"Telegram final report error: {exc}")


tracker = TelegramProgress()


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
    if not text:
        raise RuntimeError("Gemini returned an empty response.")

    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text)
    text = re.sub(r"```$", "", text)

    return json.loads(text.strip())


def is_temporary_error(error):
    message = str(error).lower()

    terms = [
        "429",
        "500",
        "502",
        "503",
        "504",
        "resource exhausted",
        "rate limit",
        "overloaded",
        "temporarily unavailable",
        "deadline exceeded",
        "timeout"
    ]

    return any(term in message for term in terms)


def create_story():
    """Load the story generated securely by GitHub Actions."""
    raw = os.getenv("VIDEO_STORY_JSON", "").strip()
    if not raw:
        raise RuntimeError(
            "VIDEO_STORY_JSON is missing. GitHub Actions must generate "
            "the story before submitting this Kaggle kernel."
        )

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("GitHub-generated story JSON is invalid.") from exc

    if not isinstance(data, dict):
        raise RuntimeError("Story payload must be a JSON object.")
    if not data.get("title") or not data.get("voiceover"):
        raise RuntimeError("Story payload is missing title or Hindi narration.")
    scenes = data.get("scenes")
    if not isinstance(scenes, list) or len(scenes) != 7 or not all(
        isinstance(scene, str) and scene.strip() for scene in scenes
    ):
        raise RuntimeError("Story payload must contain exactly seven non-empty scene prompts.")

    tracker.active_model = data.get("gemini_model", "GitHub Actions")
    print("Story received from GitHub Actions.")
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

    asyncio.run(
        create_voice(text, voice_file)
    )

    if not voice_file.exists() or voice_file.stat().st_size < 1000:
        raise RuntimeError("Voice generation failed.")

    return voice_file


def make_srt(text, duration, filename):
    # Attach punctuation to the preceding word so punctuation cannot become
    # a standalone subtitle cue (for example, a floating comma).
    text = re.sub(r"\s+([,.;:!?।])", r"\1", text)
    words = [word for word in text.split() if not re.fullmatch(r"[,.;:!?।]+", word)]

    if not words:
        raise RuntimeError("Narration has no words.")

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

            end = min(
                duration,
                (index + 1) * segment_duration
            )

            file.write(f"{index + 1}\n")
            file.write(
                f"{stamp(start)} --> {stamp(end)}\n"
            )

            file.write(" ".join(group) + "\n\n")


def create_clips(scenes, total_duration, character_bible=""):
    clips = []
    scene_duration = float(total_duration) / len(scenes)

    for index, scene in enumerate(scenes, start=1):

        output = WORK_DIR / f"scene_{index}.mp4"

        percent = 25 + index * 9

        tracker.start_stage(
            percent,
            f"Generating scene {index}/{len(scenes)}",
            f"Completed scenes: {index - 1}/{len(scenes)}"
        )

        def retry_callback(
            attempt,
            maximum,
            error,
            wait
        ):
            tracker.retries += 1

            tracker.update(
                percent,
                f"Retrying scene {index}/{len(scenes)}",
                f"Attempt {attempt}/{maximum} failed.\n"
                f"Reason: {error[:300]}\n"
                f"Retrying in {wait}s"
            )

        generate_video(
            prompt=(character_bible + ". " if character_bible else "") + scene,
            output_path=output,
            duration=scene_duration,
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

    with open(
        concat_file,
        "w",
        encoding="utf-8"
    ) as file:

        for clip in clips:
            file.write(
                f"file '{clip.resolve()}'\n"
            )

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


def create_background_music(duration, filename):
    """Create a very quiet, original cinematic ambient drone without external assets."""
    sample_rate = 24000
    total_samples = max(1, int(sample_rate * duration))
    rng = random.Random(1829)
    samples = array("h")
    noise_state = 0.0

    # Soft D-minor-inspired sustained tones; deliberately restrained under narration.
    tones = [
        (73.42, 0.045),
        (110.00, 0.026),
        (146.83, 0.018),
        (220.00, 0.012),
        (293.66, 0.006),
    ]

    for i in range(total_samples):
        t = i / sample_rate
        fade_in = min(1.0, t / 2.5)
        fade_out = min(1.0, max(0.0, (duration - t) / 3.0))
        swell = 0.82 + 0.18 * math.sin(2 * math.pi * 0.035 * t)
        value = 0.0

        for frequency, amplitude in tones:
            vibrato = 1.0 + 0.0015 * math.sin(2 * math.pi * 0.12 * t)
            value += amplitude * math.sin(2 * math.pi * frequency * vibrato * t)

        # A very faint filtered-air texture gives the bed a little atmosphere.
        noise_state = 0.985 * noise_state + 0.015 * rng.uniform(-1.0, 1.0)
        value += 0.003 * noise_state

        value *= fade_in * fade_out * swell
        samples.append(max(-32767, min(32767, int(value * 32767))))

    with wave.open(str(filename), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes(samples.tobytes())

    return filename


def assemble_final_video(joined, voice, narration, era_label="1829"):

    voice_duration = get_duration(voice)

    subtitles = WORK_DIR / "captions.srt"

    make_srt(
        narration,
        voice_duration,
        subtitles
    )

    # Keep the opening year as a proper five-second overlay, not generated text.
    # IMPORTANT FIX:
    # FFmpeg must use the actual subtitle file path.
    subtitle_path = subtitles.resolve().as_posix()

    if not subtitles.exists():
        raise RuntimeError(
            f"Subtitle file missing: {subtitle_path}"
        )

    print("Subtitle file:", subtitle_path)

    final_video = OUTPUT_DIR / "historical_short.mp4"

    subtitle_filter = (
        f"subtitles='{subtitle_path}':"
        "force_style='FontName=DejaVu Sans,"
        "FontSize=18,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,BorderStyle=1,"
        "Outline=2,Shadow=1,Alignment=2,MarginV=120'"
    )
    if era_label:
        safe_label = era_label.replace("'", "")
        subtitle_filter = (
            f"drawtext=text='{safe_label}':font='DejaVu Sans':"
            "fontsize=76:fontcolor=white:borderw=3:bordercolor=black:"
            "x=(w-text_w)/2:y=170:enable='between(t,0,5)',"
            + subtitle_filter
        )

    video_duration = get_duration(joined)
    if video_duration + 0.5 < voice_duration:
        raise RuntimeError(
            f"Unique footage is too short ({video_duration:.1f}s) for narration "
            f"({voice_duration:.1f}s); refusing to loop or repeat scenes."
        )

    music_file = WORK_DIR / "cinematic_ambient.wav"
    create_background_music(voice_duration, music_file)

    run_command([
        "ffmpeg", "-y",
        "-i", str(joined.resolve()),
        "-i", str(voice.resolve()),
        "-i", str(music_file.resolve()),
        "-filter_complex",
        "[1:a]volume=1.0[voice];"
        "[2:a]volume=0.18[music];"
        "[voice][music]amix=inputs=2:duration=first:dropout_transition=3[aout]",
        "-vf", subtitle_filter,
        "-map", "0:v:0",
        "-map", "[aout]",
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

    if (
        not final_video.exists()
        or final_video.stat().st_size < 10000
    ):
        raise RuntimeError(
            "Final video was not created correctly."
        )

    return final_video


def send_telegram(video, title):

    bot = os.getenv("TELEGRAM_BOT_TOKEN")
    chat = os.getenv("TELEGRAM_CHAT_ID")

    if not bot or not chat:
        print(
            "Telegram video upload skipped: secrets missing."
        )
        return

    with open(video, "rb") as file:

        response = requests.post(
            f"https://api.telegram.org/bot{bot}/sendVideo",
            data={
                "chat_id": chat,
                "caption": (
                    f"🎬 {title}\n"
                    "Your AI historical Short is ready!"
                )
            },
            files={
                "video": file
            },
            timeout=(30, 600)
        )

    response.raise_for_status()

    if not response.json().get("ok"):
        raise RuntimeError(
            f"Telegram upload failed: {response.text}"
        )


def main():

    try:

        tracker.start_stage(
            2,
            "Starting pipeline"
        )

        tracker.start_stage(
            5,
            "Creating historical story",
            "Story prepared in GitHub Actions"
        )

        story = create_story()

        print("Title:", story["title"])
        print("Gemini model:", story["gemini_model"])
        print("Narration:", story["voiceover"])

        with open(
            OUTPUT_DIR / "story.json",
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(
                story,
                file,
                ensure_ascii=False,
                indent=2
            )

        tracker.start_stage(
            18,
            "Generating Hindi narration"
        )

        voice = generate_voice(
            story["voiceover"]
        )

        tracker.start_stage(
            25,
            "Preparing seven AI scenes",
            f"Target unique footage: {get_duration(voice):.1f}s"
        )

        clips = create_clips(
            story["scenes"],
            total_duration=get_duration(voice),
            character_bible=story.get("character_bible", "")
        )

        tracker.start_stage(
            65,
            "Normalizing video clips"
        )

        normalized = normalize_clips(clips)

        tracker.start_stage(
            78,
            "Joining scenes"
        )

        joined = join_clips(normalized)

        tracker.start_stage(
            85,
            "Adding narration and subtitles"
        )

        final_video = assemble_final_video(
            joined,
            voice,
            story["voiceover"],
            era_label=story.get("era_label", "1829")
        )

        tracker.start_stage(
            94,
            "Uploading final video to Telegram"
        )

        send_telegram(
            final_video,
            story["title"]
        )

        tracker.finish(
            True,
            title=story["title"]
        )

        print("SUCCESS!")
        print("Final video:", final_video)

    except Exception as exc:

        tracker.finish(
            False,
            error=f"{type(exc).__name__}: {exc}"
        )

        raise


if __name__ == "__main__":
    main()
        
