
import os
import urllib.parse
import urllib.request
from pathlib import Path

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
JOB_RESULT = os.environ.get("JOB_RESULT", "unknown")
RUN_URL = os.environ.get("RUN_URL", "")


def send_telegram(message):
    if not BOT_TOKEN or not CHAT_ID:
        print("ERROR: Telegram secrets are missing.")
        return False

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    data = urllib.parse.urlencode({
        "chat_id": CHAT_ID,
        "text": message,
        "disable_web_page_preview": "true"
    }).encode()

    request = urllib.request.Request(url, data=data)

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = response.read().decode()
            print("Telegram response:", result)
            return response.status == 200
    except Exception as error:
        print("Telegram notification failed:", error)
        return False


def get_error_log():
    possible_files = [
        Path("diagnostic/generation.log"),
        Path("generation.log")
    ]

    for file in possible_files:
        if file.exists():
            try:
                content = file.read_text(
                    encoding="utf-8",
                    errors="replace"
                )
                return content[-2500:] or "Log file is empty."
            except Exception as error:
                return f"Could not read log: {error}"

    return "Diagnostic log was not available. Open the GitHub Actions run for details."


def main():
    if JOB_RESULT == "success":
        message = (
            "✅ AI HISTORICAL SHORTS: SUCCESS\n\n"
            "Your video-generation workflow completed successfully.\n"
            "Check the generated-historical-short artifact in GitHub Actions.\n\n"
            f"Workflow: {RUN_URL}"
        )
    else:
        error_log = get_error_log()

        message = (
            "❌ AI HISTORICAL SHORTS: FAILED\n\n"
            f"Workflow result: {JOB_RESULT}\n\n"
            "LAST DIAGNOSTIC LOG:\n"
            f"{error_log}\n\n"
            f"Full GitHub Actions logs: {RUN_URL}"
        )

    if not send_telegram(message):
        raise SystemExit("Could not send Telegram notification.")


if __name__ == "__main__":
    main()
      
