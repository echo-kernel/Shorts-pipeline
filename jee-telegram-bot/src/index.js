import questions from "../data/questions.js";

const TG = "https://api.telegram.org";

const MAIN_MENU = {
  keyboard: [
    [{ text: "🎯 Mixed Quiz" }, { text: "📚 Subjects" }],
    [{ text: "📖 Chapter Quiz" }, { text: "📊 Available Topics" }],
    [{ text: "🆘 Help" }, { text: "🛑 Stop Quiz" }]
  ],
  resize_keyboard: true,
  is_persistent: true,
  input_field_placeholder: "Choose a JEE quiz section"
};

async function showMainMenu(env, chatId, message = "Choose a section from the menu below.") {
  await telegram(env, "sendMessage", { chat_id: chatId, text: message, reply_markup: MAIN_MENU });
}

async function showSubjects(env, chatId) {
  await telegram(env, "sendMessage", {
    chat_id: chatId,
    text: "Choose a subject:",
    reply_markup: {
      inline_keyboard: [
        [{ text: "⚡ Physics", callback_data: "subject:physics" }],
        [{ text: "🧪 Chemistry", callback_data: "subject:chemistry" }],
        [{ text: "📐 Mathematics", callback_data: "subject:maths" }],
        [{ text: "🎯 Mixed Quiz", callback_data: "subject:mixed" }]
      ]
    }
  });
}


async function showTopicSubjects(env, chatId) {
  await telegram(env, "sendMessage", {
    chat_id: chatId,
    text: "📖 Choose a subject to browse its available chapters:",
    reply_markup: {
      inline_keyboard: [
        [{ text: "⚡ Physics", callback_data: "topic-subject:physics" }],
        [{ text: "🧪 Chemistry", callback_data: "topic-subject:chemistry" }],
        [{ text: "📐 Mathematics", callback_data: "topic-subject:maths" }]
      ]
    }
  });
}

async function showTopics(env, chatId, subject) {
  const available = [...new Map(questions.filter(validQuestion)
    .filter(q => !subject || q.subject.toLowerCase() === subject)
    .map(q => {
      const topic = q.topic || q.chapter;
      return [normalizeTopic(topic), topic];
    })).values()];
  if (!available.length) {
    await telegram(env, "sendMessage", {
      chat_id: chatId,
      text: subject ? `No verified chapters are available for ${subject} yet.` : "No verified chapters are available yet.",
      reply_markup: MAIN_MENU
    });
    return;
  }
  const buttons = available.map(topic => [{
    text: `📘 ${topic}`.slice(0, 60),
    callback_data: `topic:${subject}:${normalizeTopic(topic)}`.slice(0, 64)
  }]);
  await telegram(env, "sendMessage", {
    chat_id: chatId,
    text: `Choose a chapter/topic in ${subject}:`,
    reply_markup: { inline_keyboard: buttons }
  });
}


async function askQuestionCount(env, chatId, subject = null, topic = null) {
  await env.QUIZ_STATE.put("pending:" + chatId, JSON.stringify({ subject, topic }), { expirationTtl: 600 });
  await telegram(env, "sendMessage", {
    chat_id: chatId,
    text: "How many questions would you like?",
    reply_markup: { inline_keyboard: [
      [{ text: "5", callback_data: "count:5" }, { text: "10", callback_data: "count:10" }],
      [{ text: "15", callback_data: "count:15" }, { text: "20", callback_data: "count:20" }],
      [{ text: "25", callback_data: "count:25" }, { text: "All available", callback_data: "count:all" }]
    ]}
  });
}

async function understandQuizRequest(env, chatId, rawText) {
  if (!env.GEMINI_API_KEY) {
    await telegram(env, "sendMessage", { chat_id: chatId, text: "Try: Give me 15 difficult Physics questions from Rotational Motion." });
    return;
  }
  const prompt = 'Convert this message into quiz settings. Return ONLY JSON: {"action":"quiz|help","subject":"physics|chemistry|maths|mixed","topic":"","count":10}. Understand informal language, typos and Hinglish. Default count 10. Do not invent a topic. If not a JEE quiz, action=help. Message: ' + rawText;
  try {
    const response = await fetch("https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent", {
      method: "POST",
      headers: { "content-type": "application/json", "x-goog-api-key": env.GEMINI_API_KEY },
      body: JSON.stringify({ contents: [{ role: "user", parts: [{ text: prompt }] }], generationConfig: { temperature: 0.1, responseMimeType: "application/json", maxOutputTokens: 200 } })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error?.message || "Gemini request failed");
    const raw = data.candidates?.[0]?.content?.parts?.map(p => p.text || "").join("").trim();
    const parsed = JSON.parse(raw);
    const subject = String(parsed.subject || "").toLowerCase();
    if (parsed.action !== "quiz" || !["physics", "chemistry", "maths", "mixed"].includes(subject)) {
      await telegram(env, "sendMessage", { chat_id: chatId, text: "Try requests like:\n• 20 Physics questions\n• 10 Chemistry questions from Chemical Bonding\n• Maths quiz on Integration\n• 15 mixed JEE PYQs" });
      return;
    }
    const count = Math.max(1, Math.min(100, Number.parseInt(parsed.count, 10) || 10));
    await startQuiz(env, chatId, subject === "mixed" ? null : subject, parsed.topic || null, count);
  } catch (error) {
    console.error("AI request understanding failed", String(error));
    await telegram(env, "sendMessage", { chat_id: chatId, text: "I couldn't understand that. Try: Give me 15 Physics questions from Rotational Motion." });
  }
}

async function telegram(env, method, body) {
  const response = await fetch(`${TG}/bot${env.TELEGRAM_TOKEN}/${method}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body)
  });
  const result = await response.json();
  if (!response.ok || !result.ok) {
    console.error("Telegram API failure", method, result);
    throw new Error(`Telegram API request failed: ${method}`);
  }
  return result;
}

function validQuestion(q) {
  return q &&
    q.verified === true &&
    typeof q.source_url === "string" &&
    /^https?:\/\//i.test(q.source_url) &&
    ["physics", "chemistry", "maths"].includes(String(q.subject).toLowerCase()) &&
    typeof q.question === "string" &&
    (typeof q.topic === "string" || typeof q.chapter === "string") &&
    Array.isArray(q.options) &&
    q.options.length === 4 &&
    q.options.every(x => typeof x === "string" && x.trim()) &&
    Number.isInteger(q.answer) &&
    q.answer >= 0 && q.answer < 4;
}

function shuffled(items) {
  const a = [...items];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

async function explainWithGemini(env, q) {
  if (q.explanation && q.explanation.trim()) return q.explanation;
  if (!env.GEMINI_API_KEY) return "A verified explanation has not been added yet.";

  const prompt = [
    "Explain this JEE Main multiple-choice question step by step.",
    "Do not change the supplied answer. If information is insufficient, say so.",
    `Subject: ${q.subject}`,
    `Question: ${q.question}`,
    ...q.options.map((o, i) => `Option ${i + 1}: ${o}`),
    `Verified correct option: ${q.answer + 1}. ${q.options[q.answer]}`
  ].join("\n");

  try {
    const response = await fetch(
      "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
      {
        method: "POST",
        headers: {
          "content-type": "application/json",
          "x-goog-api-key": env.GEMINI_API_KEY
        },
        body: JSON.stringify({
          contents: [{ role: "user", parts: [{ text: prompt }] }],
          generationConfig: { temperature: 0.2, maxOutputTokens: 700 }
        })
      }
    );
    const data = await response.json();
    if (!response.ok) {
      console.error("Gemini API failure", data);
      return "Gemini could not generate an explanation right now.";
    }
    return data.candidates?.[0]?.content?.parts?.map(p => p.text || "").join("\n").trim()
      || "Explanation is unavailable.";
  } catch (error) {
    console.error("Gemini request failed", String(error));
    return "Gemini could not generate an explanation right now.";
  }
}

async function sendNext(env, chatId, state) {
  if (state.index >= state.questions.length) {
    await telegram(env, "sendMessage", {
      chat_id: chatId,
      text: `🏁 Quiz complete!\nScore: ${state.score}/${state.questions.length}\nCorrect: ${state.score}\nIncorrect: ${state.questions.length - state.score}`
    });
    await env.QUIZ_STATE.delete(`quiz:${chatId}`);
    return;
  }

  const q = state.questions[state.index];
  await env.QUIZ_STATE.put(`quiz:${chatId}`, JSON.stringify(state), { expirationTtl: 7200 });

  const keyboard = q.options.map((option, i) => [{
    text: `${i + 1}. ${option.slice(0, 55)}`,
    callback_data: `a:${state.index}:${i}`
  }]);

  const examParts = String(q.shift || "").split("·").map(part => part.trim()).filter(Boolean);
  const examLine = ["JEE MAIN", q.year, ...examParts].filter(Boolean).join(" | ");
  const safe = value => String(value ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  await telegram(env, "sendMessage", {
    chat_id: chatId,
    parse_mode: "HTML",
    disable_web_page_preview: true,
    text:
      `<b>📘 JEE MAIN ${safe(String(q.subject).toUpperCase())} — PYQ</b>\n` +
      (examLine ? `<i>${safe(examLine)}</i>\n` : "") +
      `<b>Question ${state.index + 1}/${state.questions.length}</b>\n` +
      `<b>Chapter:</b> ${safe(q.topic || q.chapter || "Not specified")}\n\n` +
      `<b>Question</b>\n${safe(q.question)}\n\n` +
      q.options.map((option, i) => `<b>${String.fromCharCode(65+i)}.</b> ${safe(option)}`).join("\n"),
    reply_markup: { inline_keyboard: keyboard }
  });
}

function normalizeTopic(value) {
  return String(value || "").toLowerCase().trim()
    .replace(/&/g, "and")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

async function startQuiz(env, chatId, subject, topic, requestedCount = 10) {
  const bank = questions.filter(validQuestion);
  const chosen = shuffled(bank.filter(q => {
    const subjectMatches = !subject || q.subject.toLowerCase() === subject;
    const storedTopic = normalizeTopic(q.topic || q.chapter);
    const topicMatches = !topic || storedTopic === normalizeTopic(topic);
    return subjectMatches && topicMatches;
  })).slice(0, Math.max(1, Math.min(100, requestedCount)));

  if (!chosen.length) {
    await telegram(env, "sendMessage", {
      chat_id: chatId,
      text: "The verified question bank is not populated yet. Questions will appear after official papers and final answer keys have been checked and added."
    });
    return;
  }

  const state = { questions: chosen, index: 0, score: 0, answered: false };
  await env.QUIZ_STATE.put(`quiz:${chatId}`, JSON.stringify(state), { expirationTtl: 7200 });
  await telegram(env, "sendMessage", {
    chat_id: chatId,
    text: `Starting your ${subject || "mixed"} JEE Main PYQ quiz${topic ? ` — ${topic}` : ""}: ${chosen.length} questions.\nChoose an option for each question.`
  });
  await sendNext(env, chatId, state);
}

async function handleMessage(env, message) {
  const chatId = message.chat.id;
  const text = (message.text || "").trim().toLowerCase().replace(/\s+/g, " ");

  if (text === "/start") {
    await showMainMenu(env, chatId, "Welcome to JEE Main PYQ Quiz Bot!\nChoose a section using the menu button beside the message box.");
  } else if (text === "/help" || text === "🆘 help") {
    await showMainMenu(env, chatId, "JEE Main Quiz Bot\n\n🎯 Mixed Quiz: random questions from all subjects\n📚 Subjects: choose Physics, Chemistry or Maths\n📖 Chapter Quiz: start a topic-wise quiz\n📊 Available Topics: see chapters currently in the verified bank\n🛑 Stop Quiz: end your current quiz");
  } else if (text === "📚 subjects") {
    await showSubjects(env, chatId);
  } else if (text === "🎯 mixed quiz" || text === "start quiz question" || text === "/quiz") {
    await askQuestionCount(env, chatId, null);
  } else if (text === "📖 chapter quiz") {
    await showTopicSubjects(env, chatId);
  } else if (text === "📊 available topics" || text === "/topics") {
    await showTopicSubjects(env, chatId);
  } else if (text === "⚡ physics" || text === "/physics") {
    await askQuestionCount(env, chatId, "physics");
  } else if (text === "🧪 chemistry" || text === "/chemistry") {
    await askQuestionCount(env, chatId, "chemistry");
  } else if (text === "📐 mathematics" || text === "/maths") {
    await askQuestionCount(env, chatId, "maths");
  } else if (text === "🛑 stop quiz" || text === "/stop") {
    await env.QUIZ_STATE.delete(`quiz:${chatId}`);
    await showMainMenu(env, chatId, "Quiz stopped. Choose another section below.");
  } else if (text.startsWith("/topic ")) {
    const parts = text.slice(7).trim().split(/\s+/);
    const subject = parts.shift();
    const topic = parts.join(" ");
    if (!["physics", "chemistry", "maths"].includes(subject) || !topic) {
      await telegram(env, "sendMessage", { chat_id: chatId, text: "Use: /topic physics rotational-motion\nSubjects: physics, chemistry, maths. Use hyphens for multi-word topics." });
    } else {
      await askQuestionCount(env, chatId, subject, topic);
    }
  } else {
    await understandQuizRequest(env, chatId, message.text || "");
  }
}

async function handleCallback(env, callback) {
  const chatId = callback.message.chat.id;
  const [action, indexText, choiceText] = String(callback.data || "").split(":");

  if (action === "count") {
    await telegram(env, "answerCallbackQuery", { callback_query_id: callback.id });
    const pending = await env.QUIZ_STATE.get("pending:" + chatId, "json");
    if (!pending) {
      await telegram(env, "sendMessage", { chat_id: chatId, text: "Please start the quiz again." });
      return;
    }
    await env.QUIZ_STATE.delete("pending:" + chatId);
    const available = questions.filter(validQuestion).filter(q =>
      (!pending.subject || q.subject.toLowerCase() === pending.subject) &&
      (!pending.topic || normalizeTopic(q.topic || q.chapter) === normalizeTopic(pending.topic))
    ).length;
    const requested = indexText === "all" ? available : Number(indexText);
    if (!Number.isInteger(requested) || requested < 1) {
      await telegram(env, "sendMessage", { chat_id: chatId, text: "No verified questions are available for that selection." });
      return;
    }
    return startQuiz(env, chatId, pending.subject, pending.topic, requested);
  }
  if (action === "subject") {
    await telegram(env, "answerCallbackQuery", { callback_query_id: callback.id });
    if (indexText === "mixed") return askQuestionCount(env, chatId, null);
    return askQuestionCount(env, chatId, indexText);
  }
  if (action === "topic-subject") {
    await telegram(env, "answerCallbackQuery", { callback_query_id: callback.id });
    return showTopics(env, chatId, indexText);
  }
  if (action === "topic") {
    await telegram(env, "answerCallbackQuery", { callback_query_id: callback.id });
    const subject = indexText;
    const topic = choiceText;
    if (!["physics", "chemistry", "maths"].includes(subject) || !topic) return;
    return askQuestionCount(env, chatId, subject, topic);
  }
  if (action !== "a") return;

  const index = Number(indexText);
  const choice = Number(choiceText);
  const key = `quiz:${chatId}`;
  const state = await env.QUIZ_STATE.get(key, "json");

  if (!state || state.index !== index || state.answered ||
      !Number.isInteger(choice) || choice < 0 || choice > 3) {
    await telegram(env, "answerCallbackQuery", {
      callback_query_id: callback.id,
      text: "This answer is no longer active."
    });
    return;
  }

  const q = state.questions[index];
  const correct = choice === q.answer;
  state.answered = true;
  if (correct) state.score++;

  await env.QUIZ_STATE.put(key, JSON.stringify(state), { expirationTtl: 7200 });
  await telegram(env, "answerCallbackQuery", {
    callback_query_id: callback.id,
    text: correct ? "Correct!" : "Not quite!"
  });

  const explanation = await explainWithGemini(env, q);
  await telegram(env, "sendMessage", {
    chat_id: chatId,
    text:
      `${correct ? "✅ Correct!" : "❌ Incorrect!"}\nCorrect answer: ${q.answer + 1}. ${q.options[q.answer]}\n\nExplanation:\n${explanation}\n\nScore: ${state.score}/${index + 1}`
  });

  state.index++;
  state.answered = false;
  await env.QUIZ_STATE.put(key, JSON.stringify(state), { expirationTtl: 7200 });
  await sendNext(env, chatId, state);
}

export default {
  async fetch(request, env) {
    if (request.method === "GET") {
      return new Response("JEE Main Telegram Quiz Bot is running.");
    }
    if (request.method !== "POST") return new Response("Method not allowed", { status: 405 });
    if (!env.TELEGRAM_TOKEN || !env.TELEGRAM_WEBHOOK_SECRET || !env.QUIZ_STATE) {
      return new Response("Bot configuration is incomplete.", { status: 500 });
    }

    const suppliedSecret = request.headers.get("X-Telegram-Bot-Api-Secret-Token");
    if (suppliedSecret !== env.TELEGRAM_WEBHOOK_SECRET) {
      return new Response("Unauthorized", { status: 401 });
    }

    let update;
    try {
      update = await request.json();
    } catch {
      return new Response("Invalid JSON", { status: 400 });
    }

    // Telegram retries webhook deliveries. Ignore an update already processed.
    if (Number.isInteger(update.update_id)) {
      const updateKey = `update:${update.update_id}`;
      if (await env.QUIZ_STATE.get(updateKey)) return new Response("OK");
      await env.QUIZ_STATE.put(updateKey, "1", { expirationTtl: 86400 });
    }

    try {
      if (update.message) await handleMessage(env, update.message);
      if (update.callback_query) await handleCallback(env, update.callback_query);
    } catch (error) {
      console.error("Update handling failed", String(error));
      // Return 200 to avoid repeatedly processing a partially handled quiz update.
    }

    return new Response("OK");
  }
};
