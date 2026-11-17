
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
    # First try Kaggle's encrypted Secrets feature.
    try:
        from kaggle_secrets import UserSecretsClient
        value = UserSecretsClient().get_secret(name)
        if value:
            return str(value).strip()
    except Exception as exc:
        print(f"Kaggle Secrets lookup unavailable for {name}: {type(exc).__name__}")

    input_dir = Path("/kaggle/input")
    if not input_dir.exists():
        print("No Kaggle input dataset is mounted.")
        return ""

    # Support individual secret files, .env files, JSON files and key=value files.
    text_files = []
    for path in input_dir.rglob("*"):
        if not path.is_file():
            continue
        if path.stat().st_size > 1024 * 1024:
            continue
        text_files.append(path)

    # Prefer a file whose name exactly matches the requested secret.
    for path in text_files:
        if path.name != name:
            continue
        try:
            value = path.read_bytes().decode("utf-8-sig").strip()
            if value and "=" not in value.splitlines()[0]:
                print(f"Loaded {name} from individual secret file.")
                return value
        except (UnicodeDecodeError, OSError):
            print(f"Skipped binary/non-UTF-8 file for {name}: {path.name}")

    # Parse structured or key=value text files without printing secret values.
    for path in text_files:
        if path.suffix.lower() not in {".json", ".env", ".txt", ".cfg", ".ini"} and path.name not in {".env", "secrets"}:
            continue
        try:
            raw = path.read_bytes().decode("utf-8-sig")
        except (UnicodeDecodeError, OSError):
            continue

        try:
            data = json.loads(raw)
            if isinstance(data, dict) and data.get(name):
                print(f"Loaded {name} from structured secrets file: {path.name}")
                return str(data[name]).strip()
        except json.JSONDecodeError:
            pass

        for line in raw.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip().removeprefix("export ").strip() == name:
                value = value.strip().strip('"').strip("'")
                if value:
                    print(f"Loaded {name} from key=value file: {path.name}")
                    return value

    available = sorted({p.name for p in text_files})
    print("Credential files found (names only):", available[:30])
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
        
