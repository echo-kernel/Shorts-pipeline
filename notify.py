
import os
import io
import zipfile
import urllib.request
import urllib.parse
from pathlib import Path

BOT = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT = os.getenv("TELEGRAM_CHAT_ID", "")
TOKEN = os.getenv("GITHUB_TOKEN", "")
REPO = os.getenv("GITHUB_REPOSITORY", "")
RUN_ID = os.getenv("RUN_ID", "")
RESULT = os.getenv("JOB_RESULT", "unknown")
RUN_URL = os.getenv("RUN_URL", "")


def get_github_logs():
    url = (
        f"https://api.github.com/repos/{REPO}"
        f"/actions/runs/{RUN_ID}/logs"
    )

    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
    )

    with urllib.request.urlopen(request, timeout=45) as response:
        archive = zipfile.ZipFile(io.BytesIO(response.read()))

    logs = []
    for name in archive.namelist():
        if name.endswith(".txt"):
            content = archive.read(name).decode(
                "utf-8", errors="replace"
            )
            logs.append(f"\n--- {name} ---\n{content}")

    return "\n".join(logs)[-2500:]


def get_diagnostics():
    path = Path("diagnostic/generation.log")

    if path.exists():
        content = path.read_text(
            encoding="utf-8", errors="replace"
        )
        if content.strip():
            return content[-2500:]

    try:
        return get_github_logs()
    except Exception as error:
        return f"Could not retrieve GitHub logs: {error}"


def send(message):
    if not BOT or not CHAT:
        raise RuntimeError("Telegram secrets are missing")

    url = f"https://api.telegram.org/bot{BOT}/sendMessage"

    data = urllib.parse.urlencode({
        "chat_id": CHAT,
        "text": message,
        "disable_web_page_preview": "true"
    }).encode()

    request = urllib.request.Request(url, data=data)

    with urllib.request.urlopen(request, timeout=30) as response:
        print(response.read().decode())


def main():
    if RESULT == "success":
        message = (
            "✅ AI HISTORICAL SHORTS: SUCCESS\n\n"
            "Video generation completed.\n"
            "Check the generated video artifact in GitHub Actions.\n\n"
            f"Workflow logs: {RUN_URL}"
        )
    else:
        log = get_diagnostics()

        message = (
            "❌ AI HISTORICAL SHORTS: FAILED\n\n"
            f"Result: {RESULT}\n\n"
            "DIAGNOSTIC DETAILS:\n"
            f"{log}\n\n"
            f"Full logs: {RUN_URL}"
        )

    send(message)


if __name__ == "__main__":
    main()
    
