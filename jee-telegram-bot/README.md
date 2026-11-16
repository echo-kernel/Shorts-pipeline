# JEE Main Telegram PYQ Quiz Bot

This bot runs as a Cloudflare Worker, receives Telegram updates through a webhook, stores quiz state in Cloudflare KV, and uses Gemini only to explain the verified answer.

## Telegram commands

- `/start` or `/help` — show help
- `start quiz question` or `/quiz` — mixed quiz
- `/physics` — Physics quiz
- `/chemistry` — Chemistry quiz
- `/maths` — Mathematics quiz
- `/stop` — stop the current quiz

## Required GitHub Actions repository secrets

Add these under **Settings → Secrets and variables → Actions**:

- `TELEGRAM_TOKEN` — token from @BotFather
- `GEMINI_API_KEY` — Gemini API key
- `CLOUDFLARE_API_TOKEN` — Cloudflare API token with Account: Workers Scripts Edit and Workers KV Storage Edit
- `CLOUDFLARE_ACCOUNT_ID` — Cloudflare account ID

The deployment workflow creates or reuses the KV namespace and deploys the Worker. It then configures the Telegram webhook.

## Question bank

The initial bank is intentionally empty. Do not label AI-generated or unverified content as a JEE Main PYQ.

Add entries to `data/questions.js` only after checking the question against an official paper and its final answer key:

```js
export default [
  {
    id: "2025-jan-shift-1-physics-q1",
    verified: true,
    source_url: "https://jeemain.nta.nic.in/",
    year: "2025",
    shift: "January Shift 1",
    subject: "physics",
    question: "Exact question text from the verified paper",
    options: ["Option A", "Option B", "Option C", "Option D"],
    answer: 0,
    explanation: "Verified solution or concise derivation"
  }
];
```

The `answer` value is zero-based: 0 means A, 1 means B, 2 means C, 3 means D. Each question must include its official paper/source URL and `verified: true`. Gemini may explain the stored correct answer, but it must not decide or overwrite the answer key.

## Deployment

Run **Actions → Deploy JEE Telegram Quiz Bot → Run workflow** on branch `jee-telegram-quiz`.

The workflow creates the Cloudflare KV namespace if it does not already exist. The first successful deployment may need a short time for the workers.dev hostname to become active; if webhook setup fails, rerun the workflow after the Worker is visible in Cloudflare.
