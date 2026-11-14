
import os
import shutil
import subprocess
from pathlib import Path

from gradio_client import Client

SPACE = "innoai/minimax-h3-flashgen-4step"
OUTPUT = Path("ai_video.mp4")
CLIP_DIR = Path("ai_video_clips")

CANVAS = "544x960 · 9:16 fast"
CLIP_DURATION = 5

def get_video_path(result):
    if not isinstance(result, (tuple, list)) or not result:
        raise RuntimeError(f"Unexpected AI response: {result}")

    video = result[0]

    if isinstance(video, dict):
        video = video.get("path") or video.get("url")

    if not video:
        raise RuntimeError(f"No video returned: {result}")

    path = Path(str(video))

    if not path.is_file():
        raise FileNotFoundError(f"AI video file not found: {video}")

    return path


def generate_ai_video(story, total_duration):
    CLIP_DIR.mkdir(exist_ok=True)

    token = os.getenv("HF_TOKEN")
    if token:
        client = Client(SPACE, token=token)
    else:
        client = Client(SPACE)

    scene_directions = [
        "Establishing shot showing the historical location, landscape and period.",
        "Show the main historical characters and their daily lives.",
        "Show the central historical conflict with realistic action.",
        "Show the aftermath and emotional conclusion of the story."
    ]

    clips = []

    for index, direction in enumerate(scene_directions, start=1):
        print(f"Generating AI scene {index}/4...", flush=True)

        prompt = (
            "Create a photorealistic historical documentary video. "
            "Authentic historical clothing, architecture, weapons and environment. "
            "Natural human movement, realistic faces, cinematic camera movement, "
            "dramatic natural lighting, detailed environment. "
            "No text, no subtitles, no watermark, no logos. "
            f"Historical story: {story}. "
            f"Scene direction: {direction}"
        )

        result = client.predict(
            prompt,
            None,
            None,
            CANVAS,
            CLIP_DURATION,
            1000 + index,
            False,
            api_name="/generate"
        )

        source = get_video_path(result)
        destination = CLIP_DIR / f"scene_{index:02d}.mp4"

        shutil.copy2(source, destination)
        clips.append(destination)

        print(f"Saved {destination}", flush=True)

    # Join the four AI-generated clips.
    concat_file = CLIP_DIR / "concat.txt"

    with concat_file.open("w", encoding="utf-8") as file:
        for clip in clips:
            file.write(f"file '{clip.resolve()}'\n")

    joined = CLIP_DIR / "joined.mp4"

    subprocess.run([
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        "-an",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-pix_fmt", "yuv420p",
        str(joined)
    ], check=True)

    # Repeat the combined scenes to match the narration duration.
    subprocess.run([
        "ffmpeg", "-y",
        "-stream_loop", "-1",
        "-i", str(joined),
        "-t", str(total_duration),
        "-an",
        "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
        "-r", "24",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-pix_fmt", "yuv420p",
        str(OUTPUT)
    ], check=True)

    print(f"AI video ready: {OUTPUT}", flush=True)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        raise SystemExit(
            "Usage: python ai_video.py story_text duration_seconds"
        )

    story = sys.argv[1]
    duration = float(sys.argv[2])

    generate_ai_video(story, duration)
      
