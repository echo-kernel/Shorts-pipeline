
import os
import sys
import subprocess
import shutil
import json
from pathlib import Path

REPO = "https://github.com/echo-kernel/Shorts-pipeline.git"
BRANCH = "jee-telegram-quiz"
ROOT = Path("/kaggle/working/Shorts-pipeline")

print("AI HISTORICAL SHORTS - KAGGLE RUNNER")

# 1. Download the exact project branch from GitHub.
# Refresh an existing checkout too, so reused Kaggle sessions cannot keep stale code.
if not ROOT.exists():
    subprocess.run([
        "git", "clone", "--depth", "1",
        "--branch", BRANCH, REPO, str(ROOT)
    ], check=True)
else:
    subprocess.run([
        "git", "-C", str(ROOT), "fetch", "--depth", "1", "origin", BRANCH
    ], check=True)
    subprocess.run([
        "git", "-C", str(ROOT), "checkout", "-B", BRANCH, "FETCH_HEAD"
    ], check=True)
    subprocess.run([
        "git", "-C", str(ROOT), "reset", "--hard", "FETCH_HEAD"
    ], check=True)

checked_out_branch = subprocess.check_output(
    ["git", "-C", str(ROOT), "branch", "--show-current"],
    text=True
).strip()
checked_out_commit = subprocess.check_output(
    ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
    text=True
).strip()
print("Project branch:", checked_out_branch)
print("Project commit:", checked_out_commit)
if checked_out_branch != BRANCH:
    raise RuntimeError(
        f"Wrong project branch: expected {BRANCH}, got {checked_out_branch}"
    )

os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

# 2. Receive the pre-generated story from GitHub Actions.
story_payload = globals().get("VIDEO_STORY_JSON", "")
if not story_payload:
    raise RuntimeError("Missing story payload from GitHub Actions.")
os.environ["VIDEO_STORY_JSON"] = story_payload

# 3. Install dependencies without replacing Kaggle's Torch
subprocess.run([
    sys.executable, "-m", "pip", "install", "-q",
    "diffusers==0.43.0",
    "accelerate",
    "edge-tts",
    "requests",
    "geopandas",
    "contextily",
    "matplotlib",
    "shapely",
    "pyproj",
    "numpy"
], check=True)

# Update only the Edge TTS client; keep Kaggle Torch and the pinned video stack unchanged.
subprocess.run([
    sys.executable, "-m", "pip", "install", "-q", "--upgrade", "edge-tts"
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

# Keep a local copy in Kaggle output for manual download as well.
download_video = Path("/kaggle/working/historical_short.mp4")
shutil.copy2(video, download_video)

print("SUCCESS! Video:", video)
print("Kaggle output copy:", download_video)

print("Size:", round(video.stat().st_size / 1024**2, 2), "MB")

print("Kaggle output is ready. GitHub Actions will download it using the Kaggle API.")
