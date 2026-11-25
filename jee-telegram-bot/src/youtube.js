const TG = "https://api.telegram.org";

function isYouTubeOwner(env, chatId) {
  return Boolean(env.OWNER_CHAT_ID && String(env.OWNER_CHAT_ID) === String(chatId));
}

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

async function dispatchUpload(env, { chatId, source, title, runId = "0", fileId = "" }) {
  if (!env.GITHUB_TOKEN) {
    await telegram(env, "sendMessage", { chat_id: chatId, text: "YouTube upload is not configured yet. The GitHub token is missing from the Worker." });
    return false;
  }
  const inputs = {
    source,
    run_id: String(runId),
    privacy_status: "public",
    chat_id: String(chatId),
    title: String(title || "AI Educational Short").slice(0, 100)
  };
  if (fileId) inputs.file_id = fileId;
  const response = await fetch("https://api.github.com/repos/echo-kernel/Shorts-pipeline/actions/workflows/upload-youtube.yml/dispatches", {
    method: "POST",
    headers: {
      "Accept": "application/vnd.github+json",
      "User-Agent": "Shorts-Pipeline-YouTube-Uploader",
      "Authorization": "Bearer " + env.GITHUB_TOKEN,
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ ref: "jee-telegram-quiz", inputs })
  });
  if (response.status !== 204) {
    throw new Error("GitHub rejected YouTube upload (HTTP " + response.status + "): " + (await response.text()).slice(0, 400));
  }
  await telegram(env, "sendMessage", {
    chat_id: chatId,
    text: "🌍 Public YouTube upload started for:\n" + String(title || "AI Educational Short") + "\n\nI'll message you when the upload finishes."
  });
  return true;
}

export async function showYouTubeUploads(env, chatId) {
  if (!isYouTubeOwner(env, chatId)) {
    return telegram(env, "sendMessage", { chat_id: chatId, text: "YouTube uploads are available only to the bot owner." });
  }
  const videos = await env.QUIZ_STATE.get("youtube-videos:" + chatId, "json") || [];
  const recent = videos.filter(v => v && /^\d+$/.test(String(v.run_id))).slice(0, 10);
  const rows = recent.map(v => [{
    text: "🎬 " + String(v.title || "Untitled video").slice(0, 48),
    callback_data: "ytpick:" + v.run_id
  }]);
  rows.push([{ text: "📎 Forward a generated video", callback_data: "ytforward" }]);
  return telegram(env, "sendMessage", {
    chat_id: chatId,
    text: recent.length
      ? "📁 PREVIOUS GENERATED VIDEOS\nTap the YouTube options button on a video in this chat, or forward an older MP4 below:"
      : "📁 Recent generated videos are sent directly to this chat. Tap their YouTube options button, or forward an older video here:",
    reply_markup: { inline_keyboard: rows }
  });
}

export async function handleYouTubeCallback(env, callback) {
  const data = String(callback.data || "");
  const chatId = callback.message?.chat?.id;
  if (data.startsWith("yt") && !isYouTubeOwner(env, chatId)) {
    await telegram(env, "sendMessage", { chat_id: chatId, text: "YouTube uploads are available only to the bot owner." });
    return true;
  }
  if (data === "ytcurrent") {
    const file = callback.message?.video ||
      (callback.message?.document && String(callback.message.document.mime_type || "").startsWith("video/")
        ? callback.message.document : null);
    if (!file) {
      await telegram(env, "sendMessage", { chat_id: chatId, text: "I couldn't read the video attached to that message. Please forward it using /youtube." });
      return true;
    }
    const title = String(callback.message.caption || "AI Educational Short").replace(/^🎬\s*/, "").slice(0, 100);
    if (Number(file.file_size || 0) > 20 * 1024 * 1024) {
      await telegram(env, "sendMessage", { chat_id: chatId, text: "This video is larger than Telegram's 20 MB Bot API download limit. Choose it from saved generated videos instead." });
      return true;
    }
    await dispatchUpload(env, { chatId, source: "telegram", title, fileId: file.file_id });
    return true;
  }
  if (data === "ytforward") {
    await env.QUIZ_STATE.put("youtube-waiting-video:" + chatId, "1", { expirationTtl: 900 });
    await telegram(env, "sendMessage", {
      chat_id: chatId,
      text: "📎 Forward the generated video to this chat now. The Telegram Bot API download limit is 20 MB per file for this YouTube upload route."
    });
    return true;
  }
  if (data.startsWith("ytfile:") || data.startsWith("ytupload:")) {
    await telegram(env, "sendMessage", { chat_id: chatId, text: "This old upload menu has expired. Please tap YouTube Uploads and select the video again; uploads are now Public automatically." });
    return true;
  }
  if (!data.startsWith("ytpick:")) return false;
  const videos = await env.QUIZ_STATE.get("youtube-videos:" + chatId, "json") || [];
  const runId = data.slice("ytpick:".length);
  const video = videos.find(v => String(v.run_id) === runId);
  if (!video) {
    await telegram(env, "sendMessage", { chat_id: chatId, text: "That saved video is no longer available. GitHub keeps generated videos for 7 days." });
    return true;
  }
  await dispatchUpload(env, { chatId, source: "artifact", runId, title: video.title });
  return true;
}

export async function handleYouTubeMessage(env, message) {
  const chatId = message.chat.id;
  if (!isYouTubeOwner(env, chatId)) return false;
  const waiting = await env.QUIZ_STATE.get("youtube-waiting-video:" + chatId);
  if (!waiting) return false;
  const file = message.video || (message.document && String(message.document.mime_type || "").startsWith("video/") ? message.document : null);
  if (!file) return false;
  await env.QUIZ_STATE.delete("youtube-waiting-video:" + chatId);
  const title = String(message.caption || "Previously generated AI Short").replace(/^🎬\s*/, "").slice(0, 100);
  if (Number(file.file_size || 0) > 20 * 1024 * 1024) {
    await telegram(env, "sendMessage", { chat_id: chatId, text: "This video is larger than Telegram's 20 MB Bot API download limit. Choose a saved generated video from the last 7 days instead." });
    return true;
  }
  await dispatchUpload(env, { chatId, source: "telegram", title, fileId: file.file_id });
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
