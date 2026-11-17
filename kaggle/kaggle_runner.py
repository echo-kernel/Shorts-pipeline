
import os
import json
import sys
import subprocess
from pathlib import Path

REPO = "https://github.com/stonecrusher1india/Shorts-pipeline.git"
BRANCH = "wan-kaggle-test"
ROOT = Path("/kaggle/working/Shorts-pipeline")

print("AI HISTORICAL SHORTS - KAGGLE RUNNER")

# 1. Download project from GitHub
if not ROOT.exists():
    subprocess.run([
        "git", "clone", "--depth", "1",
        "--branch", BRANCH, REPO, str(ROOT)
    ], check=True)

os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

# 2. Load private credentials
def load_secret(name):
    # Prefer Kaggle's encrypted Secrets feature.
    try:
        from kaggle_secrets import UserSecretsClient
        value = UserSecretsClient().get_secret(name)
        if value:
            return value.strip()
    except Exception as exc:
        print(f"Kaggle Secrets lookup unavailable for {name}: {type(exc).__name__}")

    # Fallback: accept plain UTF-8 files or a UTF-8 secrets.json file.
    input_dir = Path("/kaggle/input")
    if input_dir.exists():
        candidates = list(input_dir.rglob(name))
        for path in candidates:
            if not path.is_file():
                continue
            try:
                value = path.read_bytes().decode("utf-8-sig").strip()
                if value:
                    print(f"Loaded {name} from readable file: {path}")
                    return value
            except UnicodeDecodeError:
                print(f"Skipping non-UTF-8 credential candidate: {path}")

        for path in input_dir.rglob("*.json"):
            if not path.is_file():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8-sig"))
                if isinstance(data, dict) and data.get(name):
                    print(f"Loaded {name} from JSON file: {path}")
                    return str(data[name]).strip()
            except (UnicodeDecodeError, json.JSONDecodeError, OSError):
                continue

    return ""

for name in [
    "GEMINI_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID"
]:
    value = load_secret(name)
    if name == "TELEGRAM_CHAT_ID" and os.getenv("VIDEO_CHAT_ID"):
        value = os.environ["VIDEO_CHAT_ID"]
    if not value:
        raise RuntimeError("Missing credential file: " + name)
    os.environ[name] = value
    print("Loaded:", name)

# 3. Install dependencies without replacing Kaggle's Torch
subprocess.run([
    sys.executable, "-m", "pip", "install", "-q",
    "diffusers==0.43.0",
    "accelerate",
    "google-genai",
    "edge-tts",
    "requests"
], check=True)

# 4. Check GPU
import torch

if not torch.cuda.is_available():
    raise RuntimeError("GPU is unavailable. Enable GPU in Kaggle.")

print("GPU:", torch.cuda.get_device_name(0))
print("VRAM:",
      round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 2),
      "GB")

# 5. Check FFmpeg
subprocess.run(["ffmpeg", "-version"],
               check=True, stdout=subprocess.DEVNULL)
subprocess.run(["ffprobe", "-version"],
               check=True, stdout=subprocess.DEVNULL)

print("FFmpeg ready.")

# 6. Generate video
import generate

generate.main()

# 7. Verify final MP4
video = ROOT / "output" / "historical_short.mp4"

if not video.exists() or video.stat().st_size < 10000:
    raise RuntimeError("Final MP4 was not created correctly.")

print("SUCCESS! Video:", video)
print("Size:", round(video.stat().st_size / 1024**2, 2), "MB")
        
