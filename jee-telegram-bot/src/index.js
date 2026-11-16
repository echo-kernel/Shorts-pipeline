import questions from "../data/questions.js";

const TG = "https://api.telegram.org";

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

  const meta = [q.year, q.shift].filter(Boolean).join(" · ");
  await telegram(env, "sendMessage", {
    chat_id: chatId,
    text:
      `📘 JEE Main ${String(q.subject).toUpperCase()} PYQ\nQuestion ${state.index + 1}/${state.questions.length}` +
      (meta ? `\n${meta}` : "") +
      `\n\n${q.question}\n\n` +
      q.options.map((option, i) => `${i + 1}. ${option}`).join("\n") +
      `\n\nSource: ${q.source_url}`,
    reply_markup: { inline_keyboard: keyboard }
  });
}

function normalizeTopic(value) {
  return String(value || "").toLowerCase().trim()
    .replace(/&/g, "and")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

async function startQuiz(env, chatId, subject, topic) {
  const bank = questions.filter(validQuestion);
  const chosen = shuffled(bank.filter(q => {
    const subjectMatches = !subject || q.subject.toLowerCase() === subject;
    const storedTopic = normalizeTopic(q.topic || q.chapter);
    const topicMatches = !topic || storedTopic === normalizeTopic(topic);
    return subjectMatches && topicMatches;
  })).slice(0, 10);

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

  if (text === "/start" || text === "/help") {
    await telegram(env, "sendMessage", {
      chat_id: chatId,
      text: "Welcome to JEE Main PYQ Quiz Bot!\n\nSend:\nstart quiz question — mixed quiz\n/physics — Physics\n/chemistry — Chemistry\n/maths — Mathematics\n/topics — list verified topics\n/topic physics rotational-motion — topic-wise quiz\n/stop — stop your quiz"
    });
  } else if (text === "start quiz question" || text === "/quiz") {
    await startQuiz(env, chatId, null);
  } else if (text === "/topics") {
    const available = [...new Map(questions.filter(validQuestion).map(q => {
      const subject = q.subject.toLowerCase();
      const topic = q.topic || q.chapter;
      return [`${subject}:${normalizeTopic(topic)}`, { subject, topic }];
    })).values()];
    const listing = available.length
      ? available.map(x => `/topic ${x.subject} ${normalizeTopic(x.topic)} — ${x.topic}`).join("\\n")
      : "No verified topics have been added yet.";
    await telegram(env, "sendMessage", { chat_id: chatId, text: `Verified topics currently in the bank:\\n${listing}` });
  } else if (text.startsWith("/topic ")) {
    const parts = text.slice(7).trim().split(/\\s+/);
    const subject = parts.shift();
    const topic = parts.join(" ");
    if (!["physics", "chemistry", "maths"].includes(subject) || !topic) {
      await telegram(env, "sendMessage", { chat_id: chatId, text: "Use: /topic physics rotational-motion\\nSubjects: physics, chemistry, maths. Use hyphens for multi-word topics." });
    } else {
      await startQuiz(env, chatId, subject, topic);
    }
  } else if (text === "/physics") {
    await startQuiz(env, chatId, "physics");
  } else if (text === "/chemistry") {
    await startQuiz(env, chatId, "chemistry");
  } else if (text === "/maths") {
    await startQuiz(env, chatId, "maths");
  } else if (text === "/stop") {
    await env.QUIZ_STATE.delete(`quiz:${chatId}`);
    await telegram(env, "sendMessage", { chat_id: chatId, text: "Quiz stopped. Send 'start quiz question' to begin again." });
  }
}

async function handleCallback(env, callback) {
  const chatId = callback.message.chat.id;
  const [action, indexText, choiceText] = String(callback.data || "").split(":");
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
