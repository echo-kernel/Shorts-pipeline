
import os
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

print("=" * 55)
print("AI HISTORICAL SHORTS - KAGGLE GPU RUNNER")
print("=" * 55)


# --------------------------------------------------
# 1. LOAD PRIVATE CREDENTIALS
# --------------------------------------------------

def load_secret(name):
    # First try Kaggle's built-in secrets.
    try:
        from kaggle_secrets import UserSecretsClient
        value = UserSecretsClient().get_secret(name)
        if value:
            return value.strip()
    except Exception:
        pass

    # Fallback: private Kaggle dataset files.
    possible_paths = [
        Path("/kaggle/input/shorts-pipeline-secrets") / name,
        Path("/kaggle/input/shorts-pipeline-secrets/secrets") / name,
    ]

    for path in possible_paths:
        if path.is_file():
            return path.read_text(encoding="utf-8").strip()

    return ""


secret_names = [
    "GEMINI_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
]

missing = []

for name in secret_names:
    value = load_secret(name)
    if value:
        os.environ[name] = value
        print(f"Loaded credential: {name}")
    else:
        missing.append(name)

if missing:
    raise RuntimeError(
        "Missing credentials: " + ", ".join(missing)
        + ". Add them to the private Kaggle secrets dataset."
    )


# --------------------------------------------------
# 2. CHECK GPU
# --------------------------------------------------

import torch

if not torch.cuda.is_available():
    raise RuntimeError("Kaggle GPU is unavailable.")

print("GPU:", torch.cuda.get_device_name(0))
print("CUDA:", torch.version.cuda)
print(
    "VRAM:",
    round(
        torch.cuda.get_device_properties(0).total_memory
        / 1024**3,
        2
    ),
    "GB"
)


# --------------------------------------------------
# 3. INSTALL REQUIRED PACKAGES
# --------------------------------------------------

packages = [
    "diffusers==0.43.0",
    "accelerate",
    "google-genai",
    "edge-tts",
    "requests",
]

subprocess.run(
    [
        sys.executable,
        "-m",
        "pip",
        "install",
        "-q",
        *packages
    ],
    check=True
)

print("Dependencies installed.")


# --------------------------------------------------
# 4. CHECK FFMPEG
# --------------------------------------------------

subprocess.run(
    ["ffmpeg", "-version"],
    check=True,
    stdout=subprocess.DEVNULL
)

subprocess.run(
    ["ffprobe", "-version"],
    check=True,
    stdout=subprocess.DEVNULL
)

print("FFmpeg and FFprobe ready.")


# --------------------------------------------------
# 5. RUN VIDEO GENERATOR
# --------------------------------------------------

print("\nStarting AI video generation...")

import generate

generate.main()


# --------------------------------------------------
# 6. VERIFY OUTPUT
# --------------------------------------------------

video = ROOT / "output" / "historical_short.mp4"

if not video.exists():
    raise RuntimeError("Final MP4 was not created.")

if video.stat().st_size < 10000:
    raise RuntimeError("Final MP4 is too small.")

print("\n" + "=" * 55)
print("VIDEO GENERATION COMPLETED")
print("File:", video)
print(
    "Size:",
    round(video.stat().st_size / 1024**2, 2),
    "MB"
)
print("=" * 55)

