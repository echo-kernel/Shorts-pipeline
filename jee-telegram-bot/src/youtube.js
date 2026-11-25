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
  const rows = recent.map(v => [{
    text: "🎬 " + String(v.title || "Untitled video").slice(0, 48),
    callback_data: "ytpick:" + v.run_id
  }]);
  rows.push([{ text: "📎 Forward an older video", callback_data: "ytforward" }]);
  return telegram(env, "sendMessage", {
    chat_id: chatId,
    text: recent.length
      ? "📁 PREVIOUS GENERATED VIDEOS\nChoose a saved video, or forward an older MP4 below. Generated videos remain available for 7 days:"
      : "📁 No recent generated videos are saved yet. You can forward an older video here:",
    reply_markup: { inline_keyboard: rows }
  });
}

export async function handleYouTubeCallback(env, callback) {
  const data = String(callback.data || "");
  const chatId = callback.message?.chat?.id;
  if (data === "ytforward") {
    await env.QUIZ_STATE.put("youtube-waiting-video:" + chatId, "1", { expirationTtl: 900 });
    await telegram(env, "sendMessage", {
      chat_id: chatId,
      text: "📎 Forward the older generated video to this chat now. The Telegram Bot API download limit is 20 MB per file for this workflow."
    });
    return true;
  }
  if (!data.startsWith("ytpick:") && !data.startsWith("ytupload:") && !data.startsWith("ytfile:")) return false;

  const videos = await env.QUIZ_STATE.get("youtube-videos:" + chatId, "json") || [];
  if (data.startsWith("ytfile:")) {
    const [, uploadId, privacy] = data.split(":");
    const item = await env.QUIZ_STATE.get("youtube-file:" + chatId + ":" + uploadId, "json");
    if (!item) {
      await telegram(env, "sendMessage", { chat_id: chatId, text: "This forwarded-video selection expired. Please forward it again." });
      return true;
    }
    if (privacy === "cancel") {
      await env.QUIZ_STATE.delete("youtube-file:" + chatId + ":" + uploadId);
      await telegram(env, "sendMessage", { chat_id: chatId, text: "🚫 Cancelled. No YouTube upload was made." });
      return true;
    }
    if (!["public", "private"].includes(privacy)) return true;
    if (!env.GITHUB_TOKEN) {
      await telegram(env, "sendMessage", { chat_id: chatId, text: "YouTube upload is not configured yet. The GitHub token is missing from the Worker." });
      return true;
    }
    if (Number(item.file_size || 0) > 20 * 1024 * 1024) {
      await telegram(env, "sendMessage", { chat_id: chatId, text: "This forwarded file is larger than 20 MB, so Telegram's Bot API cannot download it for the YouTube upload. Choose a saved generated video from the last 7 days instead." });
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
          source: "telegram",
          file_id: item.file_id,
          run_id: "0",
          privacy_status: privacy,
          chat_id: String(chatId),
          title: String(item.title || "AI Educational Short").slice(0, 100)
        }
      })
    });
    if (response.status !== 204) {
      throw new Error("GitHub rejected the forwarded-video upload (HTTP " + response.status + "): " + (await response.text()).slice(0, 400));
    }
    await env.QUIZ_STATE.delete("youtube-file:" + chatId + ":" + uploadId);
    await telegram(env, "sendMessage", {
      chat_id: chatId,
      text: (privacy === "public" ? "🌍 Public" : "🔒 Private") + " YouTube upload started for the forwarded video. I'll notify you when it finishes."
    });
    return true;
  }

  if (data.startsWith("ytpick:")) {
    const runId = data.slice("ytpick:".length);
    const video = videos.find(v => String(v.run_id) === runId);
    if (!video) {
      await telegram(env, "sendMessage", { chat_id: chatId, text: "That saved video is no longer available. GitHub keeps generated videos for 7 days." });
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
    await telegram(env, "sendMessage", { chat_id: chatId, text: "YouTube upload is not configured yet. The GitHub token is missing from the Worker." });
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
        source: "artifact",
        run_id: runId,
        privacy_status: privacy,
        chat_id: String(chatId),
        title: String(video.title || "AI Educational Short").slice(0, 100)
      }
    })
  });
  if (response.status !== 204) {
    throw new Error("GitHub rejected YouTube upload (HTTP " + response.status + "): " + (await response.text()).slice(0, 400));
  }
  await telegram(env, "sendMessage", {
    chat_id: chatId,
    text: (privacy === "public" ? "🌍 Public" : "🔒 Private") + " YouTube upload started for:\n" + String(video.title || "Untitled video") + "\n\nI'll message you when the upload finishes."
  });
  return true;
}

export async function handleYouTubeMessage(env, message) {
  const chatId = message.chat.id;
  const waiting = await env.QUIZ_STATE.get("youtube-waiting-video:" + chatId);
  if (!waiting) return false;
  const file = message.video || (message.document && String(message.document.mime_type || "").startsWith("video/") ? message.document : null);
  if (!file) return false;
  await env.QUIZ_STATE.delete("youtube-waiting-video:" + chatId);
  const uploadId = String(Date.now());
  const title = String(message.caption || "Previously generated AI Short").replace(/^🎬\s*/, "").slice(0, 100);
  await env.QUIZ_STATE.put("youtube-file:" + chatId + ":" + uploadId, JSON.stringify({
    file_id: file.file_id,
    file_size: Number(file.file_size || 0),
    title
  }), { expirationTtl: 900 });
  await telegram(env, "sendMessage", {
    chat_id: chatId,
    text: "Video received: " + title + "\nChoose the YouTube visibility:",
    reply_markup: { inline_keyboard: [
      [{ text: "🌍 Publish Public", callback_data: "ytfile:" + uploadId + ":public" }],
      [{ text: "🔒 Upload Private", callback_data: "ytfile:" + uploadId + ":private" }],
      [{ text: "🚫 Don't Publish", callback_data: "ytfile:" + uploadId + ":cancel" }]
    ]}
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
