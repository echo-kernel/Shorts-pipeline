
import os
import sys
import subprocess
import shutil
import json
import traceback
from pathlib import Path

REPO = "https://github.com/echo-kernel/Shorts-pipeline.git"
BRANCH = "wan-kaggle-test"
ROOT = Path("/kaggle/working/Shorts-pipeline")

print("AI HISTORICAL SHORTS - KAGGLE RUNNER")

# Telegram credentials are stored in Kaggle Secrets, never embedded in GitHub code.
def kaggle_secret(name):
    try:
        from kaggle_secrets import UserSecretsClient
        return UserSecretsClient().get_secret(name) or ""
    except Exception:
        return ""

TELEGRAM_TOKEN = kaggle_secret("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT = str(globals().get("VIDEO_CHAT_ID", "") or kaggle_secret("TELEGRAM_CHAT_ID")).strip()

def telegram_message(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        print("Telegram notification skipped: Kaggle Telegram secrets are unavailable.")
        return
    import requests
    response = requests.post(
        "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendMessage",
        data={"chat_id": TELEGRAM_CHAT, "text": str(message)[:3900]},
        timeout=30
    )
    response.raise_for_status()
    result = response.json()
    if not result.get("ok"):
        raise RuntimeError("Telegram sendMessage failed: " + str(result))

def report_uncaught_exception(exc_type, exc_value, exc_tb):
    details = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))[-2600:]
    try:
        telegram_message("❌ AI explainer generation failed on Kaggle.\n\n" + details)
    except Exception as notify_error:
        print("Could not send Kaggle failure notification:", type(notify_error).__name__, str(notify_error))
    sys.__excepthook__(exc_type, exc_value, exc_tb)

sys.excepthook = report_uncaught_exception

# 1. Download project from GitHub
if not ROOT.exists():
    subprocess.run([
        "git", "clone", "--depth", "1",
        "--branch", BRANCH, REPO, str(ROOT)
    ], check=True)

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

# Keep a local copy in Kaggle output for manual download as well.
download_video = Path("/kaggle/working/historical_short.mp4")
shutil.copy2(video, download_video)

print("SUCCESS! Video:", video)
print("Kaggle output copy:", download_video)

print("Size:", round(video.stat().st_size / 1024**2, 2), "MB")

# 8. Push the completed MP4 to GitHub. A push event starts the YouTube
# uploader workflow automatically; Telegram is not used as the upload source.
GITHUB_TOKEN = kaggle_secret("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    raise RuntimeError("Missing Kaggle Secret GITHUB_TOKEN. Add a fine-grained token with Contents: Read and write for echo-kernel/Shorts-pipeline.")

import base64
import re
from datetime import datetime, timezone

if video.stat().st_size > 95 * 1024 * 1024:
    raise RuntimeError("MP4 exceeds the safe GitHub Contents API limit (95 MB).")

safe_topic = re.sub(r"[^A-Za-z0-9_-]+", "-", str(json.loads(story_payload).get("topic") or "educational-short")).strip("-")[:55]
filename = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + (safe_topic or "educational-short") + ".mp4"
github_path = "videos/" + filename
with video.open("rb") as handle:
    encoded_video = base64.b64encode(handle.read()).decode("ascii")

github_response = requests.put(
    "https://api.github.com/repos/echo-kernel/Shorts-pipeline/contents/" + github_path,
    headers={
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + GITHUB_TOKEN,
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "CurioMotion-Auto-Publisher"
    },
    json={
        "message": "Auto-publish: " + str(json.loads(story_payload).get("title") or "AI Educational Short")[:100],
        "content": encoded_video,
        "branch": "jee-telegram-quiz"
    },
    timeout=(30, 300)
)
if github_response.status_code not in (200, 201):
    raise RuntimeError("GitHub video transfer failed: HTTP " + str(github_response.status_code) + " " + github_response.text[:700])
print("GitHub received MP4:", github_path)
print("GitHub push will trigger automatic public YouTube upload.")


# Deliver the finished video directly from Kaggle. GitHub Actions has already exited.
if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
    raise RuntimeError("Video generated, but TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID is missing from Kaggle Secrets.")

story = json.loads(story_payload)
topic = str(story.get("topic") or "AI Educational Short")
keyboard = {
    "inline_keyboard": [
        [
            {"text": "👍 Good video", "callback_data": "video_feedback:good"},
            {"text": "👎 Poor video", "callback_data": "video_feedback:poor"}
        ],
        [{"text": "📝 Report a problem", "callback_data": "video_feedback:report"}],
        [{"text": "📤 YouTube upload options", "callback_data": "ytcurrent"}]
    ]
}
caption = ("🎬 Your AI educational explainer Short is ready!\n" + topic)[:1000]

import requests
with video.open("rb") as handle:
    response = requests.post(
        "https://api.telegram.org/bot" + TELEGRAM_TOKEN + "/sendVideo",
        data={
            "chat_id": TELEGRAM_CHAT,
            "caption": caption,
            "reply_markup": json.dumps(keyboard, ensure_ascii=False)
        },
        files={"video": ("historical_short.mp4", handle, "video/mp4")},
        timeout=(30, 600)
    )
response.raise_for_status()
result = response.json()
if not result.get("ok"):
    raise RuntimeError("Telegram rejected the generated MP4: " + str(result))

print("SUCCESS: Final MP4 sent directly from Kaggle to Telegram.")
        
