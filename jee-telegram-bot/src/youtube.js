const TG = "https://api.telegram.org";

async function telegram(env, method, body) {
  const response = await fetch(TG + "/bot" + env.TELEGRAM_TOKEN + "/" + method, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body)
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok || !data.ok) {
    throw new Error("Telegram API failed: " + method + " " + (data.description || response.status));
  }
  return data;
}

export async function showYouTubeUploads(env, chatId) {
  const videos = await env.QUIZ_STATE.get("youtube-videos:" + chatId, "json") || [];
  const recent = videos.filter(v => v && /^\d+$/.test(String(v.run_id))).slice(0, 10);
  if (!recent.length) {
    return telegram(env, "sendMessage", {
      chat_id: chatId,
      text: "📁 No saved videos are available yet. New generated videos will appear here for 7 days. You can then choose one to upload to YouTube."
    });
  }
  return telegram(env, "sendMessage", {
    chat_id: chatId,
    text: "📁 PREVIOUS GENERATED VIDEOS\nChoose a video to upload. Saved videos are available for 7 days:",
    reply_markup: {
      inline_keyboard: recent.map(v => [{
        text: "🎬 " + String(v.title || "Untitled video").slice(0, 48),
        callback_data: "ytpick:" + v.run_id
      }])
    }
  });
}

export async function handleYouTubeCallback(env, callback) {
  const data = String(callback.data || "");
  if (!data.startsWith("ytpick:") && !data.startsWith("ytupload:")) return false;

  const chatId = callback.message?.chat?.id;
  const videos = await env.QUIZ_STATE.get("youtube-videos:" + chatId, "json") || [];

  if (data.startsWith("ytpick:")) {
    const runId = data.slice("ytpick:".length);
    const video = videos.find(v => String(v.run_id) === runId);
    if (!video) {
      await telegram(env, "sendMessage", { chat_id: chatId, text: "That saved video is no longer available. Videos are retained for 7 days." });
      return true;
    }
    await telegram(env, "sendMessage", {
      chat_id: chatId,
      text: "📤 YouTube upload\n\n" + String(video.title || "Untitled video") + "\n\nChoose what should happen:",
      reply_markup: { inline_keyboard: [
        [{ text: "🌍 Publish Public", callback_data: "ytupload:" + runId + ":public" }],
        [{ text: "🔒 Upload Private", callback_data: "ytupload:" + runId + ":private" }],
        [{ text: "🚫 Don't Publish", callback_data: "ytupload:" + runId + ":cancel" }]
      ]}
    });
    return true;
  }

  const [, runId, privacy] = data.split(":");
  const video = videos.find(v => String(v.run_id) === runId);
  if (!video) {
    await telegram(env, "sendMessage", { chat_id: chatId, text: "This saved video has expired. Please generate another video." });
    return true;
  }
  if (privacy === "cancel") {
    await telegram(env, "sendMessage", { chat_id: chatId, text: "🚫 YouTube upload cancelled. The video remains in Telegram." });
    return true;
  }
  if (!["public", "private"].includes(privacy)) return true;
  if (!env.GITHUB_TOKEN) {
    await telegram(env, "sendMessage", { chat_id: chatId, text: "YouTube upload is not connected yet. The GitHub token is missing from the Worker." });
    return true;
  }

  const response = await fetch("https://api.github.com/repos/echo-kernel/Shorts-pipeline/actions/workflows/upload-youtube.yml/dispatches", {
    method: "POST",
    headers: {
      "Accept": "application/vnd.github+json",
      "User-Agent": "Shorts-Pipeline-YouTube-Uploader",
      "Authorization": "Bearer " + env.GITHUB_TOKEN,
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      ref: "jee-telegram-quiz",
      inputs: {
        run_id: runId,
        privacy_status: privacy,
        chat_id: String(chatId),
        title: String(video.title || "AI Educational Short").slice(0, 100)
      }
    })
  });
  if (response.status !== 204) {
    const detail = (await response.text()).slice(0, 500);
    throw new Error("GitHub rejected YouTube upload (HTTP " + response.status + "): " + detail);
  }
  await telegram(env, "sendMessage", {
    chat_id: chatId,
    text: (privacy === "public" ? "🌍 Public" : "🔒 Private") + " YouTube upload started for:\n" + String(video.title || "Untitled video") + "\n\nI'll message you when the upload finishes."
  });
  return true;
}

export async function registerGeneratedVideo(env, body) {
  const chatId = String(body.chat_id || "");
  const runId = String(body.run_id || "");
  const title = String(body.title || "").trim().slice(0, 180);
  if (!/^\d+$/.test(chatId) || !/^\d+$/.test(runId) || !title) {
    throw new Error("Invalid video registration payload.");
  }
  const key = "youtube-videos:" + chatId;
  const videos = await env.QUIZ_STATE.get(key, "json") || [];
  const next = [{
    run_id: runId,
    title,
    created_at: new Date().toISOString()
  }, ...videos.filter(v => String(v.run_id) !== runId)].slice(0, 20);
  await env.QUIZ_STATE.put(key, JSON.stringify(next), { expirationTtl: 60 * 60 * 24 * 8 });
}
