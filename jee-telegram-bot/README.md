# JEE Main Telegram PYQ Quiz Bot

This bot runs as a Cloudflare Worker, receives Telegram updates through a webhook, stores quiz state in Cloudflare KV, and uses Gemini only to explain the verified answer.

## Telegram commands

- `/start` or `/help` — show help
- `start quiz question` or `/quiz` — mixed quiz
- `/physics` — Physics quiz
- `/chemistry` — Chemistry quiz
- `/maths` — Mathematics quiz
- `/topics` — list subject/topic combinations present in the verified bank
- `/topic physics rotational-motion` — quiz a specific topic (use subject followed by the topic slug)
- `/stop` — stop the current quiz

Topic-wise questions must include a `topic` or `chapter` string, for example `"topic": "Rotational Motion"`. The `/topics` command is generated from topics that actually have verified questions in the bank; it does not advertise empty chapters.

## Required GitHub Actions repository secrets

Add these under **Settings → Secrets and variables → Actions**:

- `TELEGRAM_TOKEN` — token from @BotFather
- `GEMINI_API_KEY` — Gemini API key
- `CLOUDFLARE_API_TOKEN` — Cloudflare API token with Account: Workers Scripts Edit and Workers KV Storage Edit
- `CLOUDFLARE_ACCOUNT_ID` — Cloudflare account ID

The deployment workflow creates or reuses the KV namespace and deploys the Worker. It then configures the Telegram webhook.

## AI video generation

The Telegram menu includes **🎬 Generate AI Video**. Send a topic, choose photorealistic cinematic quality, and the Worker dispatches the existing Kaggle GPU video pipeline. The finished MP4 is sent to the requesting Telegram chat.

To enable the trigger:

1. Create a GitHub fine-grained personal access token for this repository with **Actions: Read and write** permission.
2. Save it in repository **Settings → Secrets and variables → Actions** as `VIDEO_GITHUB_TOKEN`.
3. Run **Actions → Deploy JEE Telegram Quiz Bot → Run workflow** on `jee-telegram-quiz` so the Worker receives it as its `GITHUB_TOKEN` secret.
4. Keep the existing `KAGGLE_API_TOKEN`, Kaggle secret dataset, Gemini key, and Telegram bot/chat credentials configured for the video pipeline.

The video request starts a Kaggle kernel submission; the GitHub workflow reporting a successful submission does not itself guarantee that Kaggle has finished rendering. GPU availability, Kaggle quota, and model access can affect completion.

## Question bank

The bank must contain only questions checked against an official NTA question paper and its final answer key. Each entry must include:

- `id`, `verified: true`, `source_url`, `year`, `shift`
- `subject`: `physics`, `chemistry`, or `maths`
- `topic` or `chapter`: a chapter/topic label
- `question`, exactly four `options`, zero-based `answer` (0–3), and an `explanation`

Example structure (placeholder only; not a real PYQ):

```js
{
  id: "2025-jan-shift-1-physics-q1",
  verified: true,
  source_url: "https://jeemain.nta.nic.in/",
  year: "2025",
  shift: "January Shift 1",
  subject: "physics",
  topic: "Rotational Motion",
  question: "Exact question text from the verified paper",
  options: ["Option A", "Option B", "Option C", "Option D"],
  answer: 0,
  explanation: "Verified solution or concise derivation"
}
```

The `answer` value is zero-based: 0 means A, 1 means B, 2 means C, 3 means D. Gemini may explain the stored correct answer, but it must not decide or overwrite the answer key. The question bank is initially empty; do not label AI-generated or unverified content as a JEE Main PYQ.

## Official sources

Use the [official JEE Main website](https://jeemain.nta.nic.in/) and NTA's official notices/answer keys. Some historical question papers and recorded responses were available only through candidate login or temporary challenge windows. Add only source-backed questions for which the exact paper and final answer key can be verified.

## Deployment

Run **Actions → Deploy JEE Telegram Quiz Bot → Run workflow** on branch `jee-telegram-quiz`.


## YouTube uploads

The same Telegram bot can upload a newly generated Short or select one of the previous generated videos.

- Each new video message includes **YouTube upload options**.
- Use `/youtube` or **📤 YouTube Uploads** to select a previous generated video.
- Choose **Public**, **Private**, or **Don't Publish** before any upload starts.
- Generated MP4 artifacts are retained by GitHub Actions for 7 days and appear in `/youtube` history during that period.\n- For videos older than 7 days, choose **Forward an older video** and forward the MP4 to the bot. This Telegram Bot API route supports files up to 20 MB. Larger old videos need to be re-generated or uploaded through a larger-file storage route.

### One-time YouTube connection

Create a Google OAuth client for the YouTube Data API v3 and obtain an OAuth refresh token with the `https://www.googleapis.com/auth/youtube.upload` scope. Add these repository Actions secrets:

- `YOUTUBE_CLIENT_ID`
- `YOUTUBE_CLIENT_SECRET`
- `YOUTUBE_REFRESH_TOKEN`

Also keep the existing `VIDEO_GITHUB_TOKEN` secret configured. YouTube upload actions are restricted to the chat ID in the existing `TELEGRAM_CHAT_ID` repository secret. It must be a fine-grained or classic token that can dispatch repository workflows and read Actions artifacts. The existing Cloudflare secrets `CLOUDFLARE_API_TOKEN` and `CLOUDFLARE_ACCOUNT_ID` are used to register completed videos in the bot's history.

YouTube upload runs in a separate GitHub Actions workflow, not inside the Cloudflare Worker. This avoids trying to transfer large MP4 files through Telegram or the Worker. The selected privacy setting is applied when the video is uploaded; **Public** publishes immediately, while **Private** stays private. **Don't Publish** cancels without uploading.
