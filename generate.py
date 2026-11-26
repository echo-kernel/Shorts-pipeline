
import os
import re
import json
import time
import asyncio
import math
import subprocess
from pathlib import Path

import requests
import edge_tts
from google import genai

from ai_video import generate_video


# Gemini automatic fallback
GEMINI_MODELS = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3-flash-preview",
]

PREFERRED_MODEL = os.getenv("GEMINI_MODEL", "").strip()

if PREFERRED_MODEL:
    GEMINI_MODELS = [
        PREFERRED_MODEL
    ] + [
        model for model in GEMINI_MODELS
        if model != PREFERRED_MODEL
    ]

TOPIC = os.getenv(
    "VIDEO_TOPIC",
    "U Tirot Sing and the Khasi resistance against British expansion in 1829"
)

PRIMARY_TTS_VOICE = "en-US-AndrewMultilingualNeural"
TTS_RATE = "+10%"
TTS_PITCH = "-2Hz"

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
    # GitHub Actions normally generates and fact-checks the story before
    # submitting the Kaggle kernel. Use that payload directly; Kaggle does
    # not need a separate Gemini API key for this path.
    supplied_story = os.getenv("VIDEO_STORY_JSON", "").strip()
    if supplied_story:
        try:
            story = json.loads(supplied_story)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "VIDEO_STORY_JSON is not valid JSON: " + str(exc)
            ) from exc

        if not isinstance(story, dict):
            raise RuntimeError("VIDEO_STORY_JSON must contain a JSON object.")
        if not story.get("title") or not story.get("voiceover"):
            raise RuntimeError(
                "VIDEO_STORY_JSON is missing title or voiceover."
            )
        scenes = story.get("scenes")
        if not isinstance(scenes, list) or not scenes:
            raise RuntimeError("VIDEO_STORY_JSON must contain scene objects.")
        for i, scene in enumerate(scenes, 1):
            if not isinstance(scene, dict):
                raise RuntimeError(f"Scene {i} must be an object.")
            for key in ("mode", "visual_prompt", "tts_text", "caption_text"):
                if not isinstance(scene.get(key), str) or not scene[key].strip():
                    raise RuntimeError(f"Scene {i} missing {key}.")
            if scene["mode"] not in ("render", "map"):
                raise RuntimeError(f"Scene {i} has invalid mode.")
            if scene["mode"] == "map" and not isinstance(scene.get("map_center"), list):
                raise RuntimeError(f"Map scene {i} requires map_center.")
        story["voiceover"] = " ".join(scene["tts_text"] for scene in scenes)

        story.setdefault("topic", TOPIC)
        story.setdefault("gemini_model", "Pre-generated by GitHub Actions")
        tracker.active_model = story["gemini_model"]
        print("Using pre-generated story from GitHub Actions; no Kaggle Gemini API key required.")
        return story

    # Standalone Kaggle runs without a supplied story still use Gemini.
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
- Historically accurate.
- Do not invent quotations or events.
- Four visually different realistic cinematic scenes.
- Describe clothing, architecture, environment, lighting and camera movement.
- No modern objects, text, logos, watermarks or fantasy elements.
- Vertical 9:16 composition.
- Return JSON only, without Markdown fences.
"""

    failures = []

    for model in GEMINI_MODELS:

        tracker.active_model = model

        tracker.update(
            8,
            "Trying Gemini model",
            f"Testing: {model}"
        )

        for attempt in range(1, 3):

            try:
                print(
                    f"Trying Gemini model {model}, "
                    f"attempt {attempt}/2"
                )

                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config={
                        "response_mime_type": "application/json"
                    }
                )

                data = clean_json(response.text)

                if len(data.get("scenes", [])) != 4:
                    raise RuntimeError(
                        "Gemini did not return exactly four scenes."
                    )

                if not data.get("voiceover"):
                    raise RuntimeError(
                        "Gemini returned empty narration."
                    )

                data["gemini_model"] = model

                tracker.active_model = model

                print(f"Gemini success: {model}")

                return data

            except Exception as exc:

                error_text = f"{type(exc).__name__}: {exc}"

                print(
                    f"Gemini {model} failed: {error_text}"
                )

                failures.append(
                    f"{model}: {error_text[:250]}"
                )

                tracker.retries += 1

                if is_temporary_error(exc) and attempt == 1:

                    wait = 15

                    tracker.update(
                        8,
                        "Gemini temporary error",
                        f"{model} failed. Retrying in {wait}s"
                    )

                    time.sleep(wait)
                    continue

                break

    summary = "\n".join(failures[-7:])

    raise RuntimeError(
        "All configured Gemini models failed. "
        "Check API access, quota and API key.\n"
        + summary
    )


async def create_voice(text, filename, voice):
    communicate = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate=TTS_RATE,
        pitch=TTS_PITCH,
        volume="+0%"
    )

    await communicate.save(str(filename))


def generate_voice(text):
    voice_file = WORK_DIR / 'narration_raw.mp3'
    output = OUTPUT_DIR / 'narration.mp3'
    asyncio.run(create_voice(text, voice_file, PRIMARY_TTS_VOICE))
    run_command(['ffmpeg','-y','-i',str(voice_file),'-af','silenceremove=start_periods=1:start_duration=0.08:start_threshold=-45dB:stop_periods=-1:stop_duration=0.08:stop_threshold=-45dB','-ar','48000','-ac','2','-c:a','libmp3lame','-q:a','2',str(output)])
    if not output.exists() or output.stat().st_size < 1000: raise RuntimeError('Andrew Hindi voice audio is empty after silence trimming.')
    (OUTPUT_DIR / 'voice_used.txt').write_text(PRIMARY_TTS_VOICE + chr(10), encoding='utf-8')
    print('VOICE_USED=' + PRIMARY_TTS_VOICE)
    return output

def make_srt(text, duration, filename):
    # Keep caption chunks aligned to sentence boundaries where possible.
    # Allocate display time in proportion to each chunk's word count instead
    # of giving a short final chunk the same duration as a long one.
    sentences = re.split(r"(?<=[.!?।])\s+", text.strip())
    groups = []

    for sentence in sentences:
        remaining = sentence.split()
        while remaining:
            groups.append(remaining[:2])
            remaining = remaining[2:]

    if not groups:
        raise RuntimeError("Narration has no words.")

    total_words = sum(len(group) for group in groups)

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

    cursor = 0.0
    with open(filename, "w", encoding="utf-8") as file:
        for index, group in enumerate(groups):
            start = cursor
            if index == len(groups) - 1:
                end = duration
            else:
                end = cursor + duration * len(group) / total_words
            file.write(f"{index + 1}\\n")
            file.write(f"{stamp(start)} --> {stamp(end)}\\n")
            file.write(" ".join(group) + "\\n\\n")
            cursor = end


def create_clips(scenes, target_duration):
    clips = []
    if not scenes:
        raise RuntimeError("No scenes supplied.")
    scene_duration = math.ceil(float(target_duration) / len(scenes))
    if scene_duration > 14:
        raise RuntimeError("Narration too long for scene count; add scenes or shorten narration.")
    for index, scene in enumerate(scenes, start=1):
        if isinstance(scene, str):
            scene = {"mode": "render", "visual_prompt": scene}
        output = WORK_DIR / f"scene_{index}.mp4"
        if scene.get("mode", "render") == "map":
            from visual_engine import render_map_scene
            render_map_scene(scene, output, scene_duration)
        else:
            generate_video(prompt=scene["visual_prompt"], output_path=output, duration=scene_duration)
            from visual_engine import apply_cinematic_camera
            apply_cinematic_camera(output, scene_duration)
        clips.append(output)
    return clips


def normalize_clips(clips):
    normalized = []

    for index, clip in enumerate(clips, start=1):

        tracker.update(
            65 + int(index * 12 / len(clips)),
            "Normalizing clips",
            f"Processing clip {index}/{len(clips)}"
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


def assemble_final_video(joined, voice, narration):
    voice_duration = get_duration(voice)
    visual_duration = get_duration(joined)
    if visual_duration + 0.25 < voice_duration:
        raise RuntimeError(f'Visual footage ({visual_duration:.1f}s) is shorter than narration ({voice_duration:.1f}s).')
    subtitles = WORK_DIR / 'captions.srt'
    make_srt(narration, voice_duration, subtitles)
    subtitle_path = subtitles.resolve().as_posix().replace(':', '\\\\:')
    music = WORK_DIR / 'documentary_bed.wav'
    whoosh = WORK_DIR / 'transition_whoosh.wav'
    cut = max(1.0, visual_duration / max(1, len(json.loads((OUTPUT_DIR / 'story.json').read_text(encoding='utf-8')).get('scenes', []))))
    run_command(['ffmpeg','-y','-f','lavfi','-i',f'anoisesrc=color=pink:duration={voice_duration}:amplitude=0.018','-af',f'lowpass=f=180,afade=t=in:st=0:d=2,afade=t=out:st={max(0,voice_duration-3)}:d=3',str(music)])
    run_command(['ffmpeg','-y','-f','lavfi','-i',f'anoisesrc=color=white:duration={voice_duration}:amplitude=0.05','-af',f'highpass=f=700,lowpass=f=4500,volume=\'if(lt(mod(t,{cut}),0.24),0.14,0)\'',str(whoosh)])
    final_video = OUTPUT_DIR / 'historical_short.mp4'
    filters = '[2:a]volume=0.10[bed];[3:a]volume=0.6[fx];[1:a][bed][fx]amix=inputs=3:duration=first:dropout_transition=1[aout]'
    subtitle_filter = f"subtitles='{subtitle_path}':force_style='FontName=DejaVu Sans,FontSize=27,Bold=1,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=5,Shadow=3,Alignment=5,MarginV=0'"
    run_command(['ffmpeg','-y','-i',str(joined.resolve()),'-i',str(voice.resolve()),'-i',str(music),'-i',str(whoosh),'-filter_complex',filters,'-vf',subtitle_filter,'-map','0:v:0','-map','[aout]','-t',str(voice_duration),'-c:v','libx264','-preset','veryfast','-crf','21','-pix_fmt','yuv420p','-c:a','aac','-b:a','192k','-shortest','-movflags','+faststart',str(final_video.resolve())])
    if not final_video.exists() or final_video.stat().st_size < 10000: raise RuntimeError('Final MP4 was not created correctly.')
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
            "Automatic Gemini fallback enabled"
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

        voice = generate_voice(" ".join(scene.get("tts_text", "") for scene in story["scenes"]) or story["voiceover"])

        tracker.start_stage(
            25,
            "Preparing topic-adaptive scenes"
        )

        narration_duration = get_duration(voice)
        print(f"Narration duration: {narration_duration:.2f}s")

        clips = create_clips(story["scenes"], narration_duration)

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
            " ".join(scene["caption_text"] for scene in story["scenes"])
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
        
