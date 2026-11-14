
import os
import time
import random
import shutil
from pathlib import Path

import requests
from gradio_client import Client


SPACE = "innoai/minimax-h3-flashgen-4step"
CANVAS = "544x960 · 9:16 fast"
MAX_ATTEMPTS = 4


def get_video_path(result):
    # This Space returns multiple outputs; the first is the video.
    if isinstance(result, (tuple, list)):
        result = result[0]

    if isinstance(result, dict):
        result = result.get("path") or result.get("video") or result.get("url")

    if not result:
        raise RuntimeError("Hugging Face returned no video.")

    return result


def generate_video(prompt, output_path, duration=5):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not prompt or not prompt.strip():
        raise ValueError("Empty scene prompt.")

    duration = max(2, min(14, int(duration)))
    token = os.getenv("HF_TOKEN")

    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            print(f"Connecting to Hugging Face: attempt {attempt}/{MAX_ATTEMPTS}")

            client_args = {"verbose": False}
            if token:
                client_args["hf_token"] = token

            client = Client(SPACE, **client_args)

            result = client.predict(
                prompt,
                None,                       # First frame image
                None,                       # Last frame image
                CANVAS,
                duration,
                random.randint(1, 999999),
                False,                      # Prompt enhancement
                api_name="/generate"
            )

            video = get_video_path(result)

            # Gradio normally returns a downloaded local file path.
            if isinstance(video, str) and video.startswith(("http://", "https://")):
                response = requests.get(video, timeout=(30, 300))
                response.raise_for_status()
                with open(output_path, "wb") as f:
                    f.write(response.content)

            elif isinstance(video, str) and os.path.isfile(video):
                shutil.copy2(video, output_path)

            else:
                raise RuntimeError(f"Unexpected video result: {video}")

            if not output_path.exists() or output_path.stat().st_size < 1000:
                raise RuntimeError("Video file is missing or too small.")

            print(f"Saved video: {output_path}")
            return str(output_path)

        except Exception as exc:
            print(f"Attempt {attempt} failed: {type(exc).__name__}: {exc}")

            if attempt == MAX_ATTEMPTS:
                raise RuntimeError(
                    "Hugging Face generation failed after all retries."
                ) from exc

            wait = 20 * attempt
            print(f"Waiting {wait} seconds before retry...")
            time.sleep(wait)

    raise RuntimeError("Video generation failed.")
            
