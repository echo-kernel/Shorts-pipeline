import questions from "../data/questions.js";

const TG = "https://api.telegram.org";
const MAIN_MENU = {
  keyboard: [
    [{ text: "🎯 Mixed PYQ" }, { text: "🤖 AI Quiz" }],
    [{ text: "📚 Subjects" }, { text: "📖 Chapter PYQ" }],
    [{ text: "📊 Available Topics" }, { text: "📝 Full PYQ Paper" }],
    [{ text: "🆘 Help" }, { text: "🛑 Stop Quiz" }]
  ],
  resize_keyboard: true,
  is_persistent: true,
  input_field_placeholder: "Type: Create 20 difficult Physics questions on Rotation"
};

async function telegram(env, method, body) {
  const response = await fetch(TG + "/bot" + env.TELEGRAM_TOKEN + "/" + method, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body)
  });
  const result = await response.json();
  if (!response.ok || !result.ok) {
    console.error("Telegram API failure", method, result);
    throw new Error("Telegram API request failed: " + method);
  }
  return result;
}

function validQuestion(q) {
  return q && q.verified === true &&
    typeof q.source_url === "string" && /^https?:\/\//i.test(q.source_url) &&
    ["physics", "chemistry", "maths"].includes(String(q.subject).toLowerCase()) &&
    typeof q.question === "string" &&
    (typeof q.topic === "string" || typeof q.chapter === "string") &&
    Array.isArray(q.options) && q.options.length === 4 &&
    q.options.every(x => typeof x === "string" && x.trim()) &&
    Number.isInteger(q.answer) && q.answer >= 0 && q.answer < 4;
}

function normalizeTopic(value) {
  return String(value || "").toLowerCase().trim()
    .replace(/&/g, "and").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

function shuffled(items) {
  const a = [...items];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

async function showMainMenu(env, chatId, message) {
  await telegram(env, "sendMessage", {
    chat_id: chatId,
    text: message || "Choose a quiz mode below.",
    reply_markup: MAIN_MENU
  });
}

async function askQuestionCount(env, chatId, subject, topic) {
  await env.QUIZ_STATE.put("pending:" + chatId, JSON.stringify({
    subject: subject || null, topic: topic || null
  }), { expirationTtl: 600 });
  await telegram(env, "sendMessage", {
    chat_id: chatId,
    text: "How many verified PYQs do you want?",
    reply_markup: { inline_keyboard: [
      [{ text: "5", callback_data: "count:5" }, { text: "10", callback_data: "count:10" }],
      [{ text: "15", callback_data: "count:15" }, { text: "20", callback_data: "count:20" }],
      [{ text: "25", callback_data: "count:25" }, { text: "All available", callback_data: "count:all" }]
    ]}
  });
}

async function showSubjects(env, chatId) {
  await telegram(env, "sendMessage", {
    chat_id: chatId, text: "Choose a subject for PYQ practice:",
    reply_markup: { inline_keyboard: [
      [{ text: "⚡ Physics", callback_data: "subject:physics" }],
      [{ text: "🧪 Chemistry", callback_data: "subject:chemistry" }],
      [{ text: "📐 Mathematics", callback_data: "subject:maths" }],
      [{ text: "🎯 Mixed", callback_data: "subject:mixed" }]
    ]}
  });
}

async function showTopicSubjects(env, chatId) {
  await telegram(env, "sendMessage", {
    chat_id: chatId, text: "Choose a subject to browse available PYQ chapters:",
    reply_markup: { inline_keyboard: [
      [{ text: "⚡ Physics", callback_data: "topic-subject:physics" }],
      [{ text: "🧪 Chemistry", callback_data: "topic-subject:chemistry" }],
      [{ text: "📐 Mathematics", callback_data: "topic-subject:maths" }]
    ]}
  });
}

async function showTopics(env, chatId, subject) {
  const topics = [...new Map(questions.filter(validQuestion)
    .filter(q => q.subject.toLowerCase() === subject)
    .map(q => [normalizeTopic(q.topic || q.chapter), q.topic || q.chapter])).values()];
  if (!topics.length) {
    await telegram(env, "sendMessage", { chat_id: chatId, text: "No verified chapters for this subject have been added yet." });
    return;
  }
  await telegram(env, "sendMessage", {
    chat_id: chatId, text: "Select a chapter:",
    reply_markup: { inline_keyboard: topics.map(t => [{
      text: "📘 " + t, callback_data: "topic:" + subject + ":" + normalizeTopic(t)
    }]) }
  });
}

async function callGemini(env, prompt, maxTokens) {
  if (!env.GEMINI_API_KEY) throw new Error("Missing GEMINI_API_KEY secret");
  const response = await fetch(
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
    {
      method: "POST",
      headers: { "content-type": "application/json", "x-goog-api-key": env.GEMINI_API_KEY },
      body: JSON.stringify({
        contents: [{ role: "user", parts: [{ text: prompt }] }],
        generationConfig: {
          temperature: 0.2, responseMimeType: "application/json",
          maxOutputTokens: maxTokens || 8192
        }
      })
    }
  );
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.error?.message || ("HTTP " + response.status);
    throw new Error("Gemini API: " + detail);
  }
  const candidate = data.candidates?.[0];
  const raw = candidate?.content?.parts?.map(p => p.text || "").join("").trim();
  if (!raw) {
    const reason = candidate?.finishReason || data.promptFeedback?.blockReason || "empty response";
    throw new Error("Gemini returned no text (" + reason + ")");
  }
  const cleaned = raw.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, "").trim();
  try {
    return JSON.parse(cleaned);
  } catch (e) {
    const reason = candidate?.finishReason || "unknown";
    throw new Error("Gemini returned incomplete/invalid JSON (" + reason + "). Try fewer questions.");
  }
}
async function interpretRequest(env, rawText, forceAi) {
  const prompt = [
    "Interpret the user's request for a JEE Main practice test.",
    "Return only JSON with keys action, mode, subject, topic, count, difficulty, questionType.",
    'mode must be "pyq" for real past-year questions, or "ai" for newly AI-created practice questions.',
    "Use mode ai if the user says create, generate, make, custom, new questions, according to me, or asks for an AI quiz. Otherwise use pyq.",
    'subject must be physics, chemistry, maths, or mixed. topic is a concise chapter name or empty string.',
    "count must be an integer from 1 to 30. Default 10. difficulty is easy, moderate, difficult, or mixed. Default moderate.",
    'questionType can be mcq, numerical-style-mcq, or mixed. Default mcq. This bot currently supports four-option MCQs only.',
    "Understand typos, informal English and Hinglish. Do not invent a topic. If not a JEE quiz use action help.",
    "User request: " + rawText,
    "Force AI-created mode: " + (forceAi ? "yes" : "no")
  ].join("\n");
  const parsed = await callGemini(env, prompt, 500);
  if (parsed.action !== "quiz" ||
      !["physics", "chemistry", "maths", "mixed"].includes(String(parsed.subject).toLowerCase())) {
    return { action: "help" };
  }
  return {
    action: "quiz",
    mode: forceAi ? "ai" : (parsed.mode === "ai" ? "ai" : "pyq"),
    subject: String(parsed.subject).toLowerCase(),
    topic: String(parsed.topic || "").trim(),
    count: Math.max(1, Math.min(30, Number.parseInt(parsed.count, 10) || 10)),
    difficulty: ["easy", "moderate", "difficult", "mixed"].includes(String(parsed.difficulty).toLowerCase())
      ? String(parsed.difficulty).toLowerCase() : "moderate",
    questionType: String(parsed.questionType || "mcq")
  };
}

async function generateAiQuestions(env, settings, originalRequest) {
  const all = [];
  const batchSize = 3;
  for (let offset = 0; offset < settings.count; offset += batchSize) {
    const needed = Math.min(batchSize, settings.count - offset);
    const prompt = [
      "Create exactly " + needed + " JEE Main practice MCQ questions as valid JSON only.",
      'Return {"questions":[{"subject":"physics","topic":"...","question":"...","options":["A","B","C","D"],"answer":0,"explanation":"..."}]}.',
      "Subject: " + settings.subject + ". Chapter: " + (settings.topic || "balanced across the subject") + ".",
      "Difficulty: " + settings.difficulty + ". Four-option single-correct MCQ. For numerical-style requests, create calculation-heavy questions with four numeric options.",
      "Each question must be distinct, self-contained and JEE Main level. Check every calculation and answer.",
      "The answer field is a ZERO-BASED option index: 0, 1, 2, or 3.",
      "Give a concise but clear step-by-step solution in explanation.",
      "Never claim these are actual PYQs. Do not invent year, date, shift or source.",
      "Return exactly " + needed + " questions, with no markdown fences or extra text.",
      "User instructions: " + originalRequest
    ].join("\n");
    let batch = null, lastError = null;
    for (let attempt = 0; attempt < 2 && !batch; attempt++) {
      try {
        const parsed = await callGemini(env, prompt + (attempt ? "\nKeep each question and explanation concise to ensure valid complete JSON." : ""), 8192);
        if (!Array.isArray(parsed.questions)) throw new Error("Gemini response has no questions array");
        const valid = parsed.questions.map((q, i) => ({
          id: "ai-" + Date.now() + "-" + offset + "-" + i,
          subject: ["physics", "chemistry", "maths"].includes(String(q.subject || "").toLowerCase())
            ? String(q.subject).toLowerCase() : (settings.subject === "mixed" ? "physics" : settings.subject),
          topic: String(q.topic || settings.topic || "Mixed concepts"),
          question: String(q.question || ""),
          options: Array.isArray(q.options) ? q.options.map(x => String(x)) : [],
          answer: Number(q.answer),
          explanation: String(q.explanation || "")
        })).filter(q => q.question && q.options.length === 4 &&
          q.options.every(x => x.trim()) && Number.isInteger(q.answer) && q.answer >= 0 && q.answer < 4);
        if (valid.length !== needed) throw new Error("Gemini returned " + valid.length + " valid questions; needed " + needed);
        batch = valid;
      } catch (e) {
        lastError = e;
        console.error("AI question batch failed", offset, String(e));
      }
    }
    if (!batch) throw new Error("Could not generate questions " + (offset + 1) + "–" + (offset + needed) + ": " + String(lastError?.message || lastError));
    all.push(...batch);
  }
  return all;
}
async function explainWithGemini(env, q) {
  if (q.explanation && q.explanation.trim()) return q.explanation;
  const prompt = [
    "Solve this JEE Main question step by step. Do not change the verified answer.",
    "Subject: " + q.subject, "Question: " + q.question,
    ...q.options.map((o, i) => "Option " + (i + 1) + ": " + o),
    "Verified correct option: " + (q.answer + 1) + ". " + q.options[q.answer]
  ].join("\n");
  try {
    const result = await callGemini(env, prompt, 700);
    return String(result.explanation || result.solution || JSON.stringify(result));
  } catch (e) {
    console.error("Explanation generation failed", String(e));
    return "Solution could not be generated. Correct answer: " + q.options[q.answer];
  }
}

function examClock(state) {
  const elapsed = Math.max(0, Math.floor((Date.now() - state.startedAt) / 1000));
  const total = state.durationSeconds || state.questions.length * 144;
  const left = Math.max(0, total - elapsed);
  const mm = String(Math.floor(left / 60)).padStart(2, "0");
  const ss = String(left % 60).padStart(2, "0");
  return { elapsed, left, label: mm + ":" + ss };
}

async function renderQuestion(env, chatId, state, messageId) {
  const q = state.questions[state.index];
  const isAi = state.mode === "ai";
  const clock = examClock(state);
  const selected = state.answers[state.index];
  const marked = state.marked.includes(state.index);
  const safe = value => String(value ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const header = isAi ? "🤖 AI-GENERATED PRACTICE" : "📘 JEE MAIN PYQ";
  const examLine = !isAi ? ["JEE MAIN", q.year, q.shift].filter(Boolean).join(" | ") : "";
  const options = q.options.map((option, i) => [{
    text: (selected === i ? "🔘 " : "◯ ") + String.fromCharCode(65 + i) + ". " + option.slice(0, 48),
    callback_data: "pick:" + state.index + ":" + i
  }]);
  const controls = [
    [
      { text: "⬅ Previous", callback_data: "nav:prev" },
      { text: "➡ Next", callback_data: "nav:next" },
      { text: "⏭ Skip", callback_data: "nav:skip" }
    ],
    [
      { text: marked ? "★ Unmark" : "☆ Mark review", callback_data: "nav:mark" },
      { text: "📋 Submit paper", callback_data: "nav:submit" }
    ]
  ];
  const palette = state.questions.map((_, i) => {
    const icon = state.marked.includes(i) ? "🟨" : (state.answers[i] !== undefined ? "🟩" : "⬜");
    return { text: icon + (i + 1), callback_data: "nav:q" + i };
  });
  const paletteRows = [];
  for (let i = 0; i < palette.length; i += 5) paletteRows.push(palette.slice(i, i + 5));
  const text =
    "<b>" + header + "</b>\n" +
    (examLine ? "<i>" + safe(examLine) + "</i>\n" : "") +
    "<b>Question " + (state.index + 1) + "/" + state.questions.length + "</b>   ⏱ " + clock.label + "\n" +
    "<b>Chapter:</b> " + safe(q.topic || q.chapter || "Mixed") + "\n\n" +
    safe(q.question) + "\n\n" +
    q.options.map((o, i) => "<b>" + String.fromCharCode(65 + i) + ".</b> " + safe(o)).join("\n") +
    "\n\n" + (selected === undefined ? "Not answered" : "Your answer: " + String.fromCharCode(65 + selected)) +
    (marked ? "\n⭐ Marked for review" : "");
  const reply_markup = { inline_keyboard: [...options, ...controls, ...paletteRows] };
  if (messageId) {
    try {
      await telegram(env, "editMessageText", {
        chat_id: chatId, message_id: messageId, text, parse_mode: "HTML",
        reply_markup, disable_web_page_preview: true
      });
      return messageId;
    } catch (e) {
      console.error("Could not edit question message; sending new one", String(e));
    }
  }
  const sent = await telegram(env, "sendMessage", {
    chat_id: chatId, text, parse_mode: "HTML",
    reply_markup, disable_web_page_preview: true
  });
  return sent.result.message_id;
}

async function saveState(env, chatId, state) {
  await env.QUIZ_STATE.put("quiz:" + chatId, JSON.stringify(state), { expirationTtl: 10800 });
}

async function startQuiz(env, chatId, settings, originalRequest) {
  let chosen;
  if (settings.mode === "ai") {
    await telegram(env, "sendMessage", { chat_id: chatId, text: "🤖 Gemini is creating your full test. Please wait..." });
    chosen = await generateAiQuestions(env, settings, originalRequest);
  } else {
    const bank = questions.filter(validQuestion);
    const wantedTopic = normalizeTopic(settings.topic);
    chosen = shuffled(bank.filter(q => {
      const subjectOk = settings.subject === "mixed" || q.subject.toLowerCase() === settings.subject;
      const topic = normalizeTopic(q.topic || q.chapter);
      const topicOk = !wantedTopic || topic.includes(wantedTopic) || wantedTopic.includes(topic);
      return subjectOk && topicOk;
    })).slice(0, settings.count);
    if (!chosen.length) {
      await telegram(env, "sendMessage", {
        chat_id: chatId,
        text: "No verified PYQs match this selection yet. Choose 🤖 AI Quiz to generate new practice questions. The stored PYQ bank currently has only " + bank.length + " verified entries."
      });
      return;
    }
  }
  const state = {
    mode: settings.mode, questions: chosen, index: 0, answers: {}, marked: [],
    startedAt: Date.now(), durationSeconds: chosen.length * 144, messageId: null
  };
  await saveState(env, chatId, state);
  await telegram(env, "sendMessage", {
    chat_id: chatId,
    text: (settings.mode === "ai" ? "🤖 AI practice test ready." : "📘 PYQ paper ready.") +
      "\nQuestions: " + chosen.length +
      "\nTime limit: " + Math.floor(state.durationSeconds / 60) + " minutes" +
      "\nChoose an option, use Skip/Previous/Mark for Review, and submit when finished. Answers and solutions stay hidden until submission."
  });
  state.messageId = await renderQuestion(env, chatId, state);
  await saveState(env, chatId, state);
}

async function submitQuiz(env, chatId, state) {
  const key = "quiz:" + chatId;
  let score = 0, attempted = 0;
  for (let i = 0; i < state.questions.length; i++) {
    const a = state.answers[i];
    if (a !== undefined) {
      attempted++;
      if (a === state.questions[i].answer) score++;
    }
  }
  const wrong = attempted - score;
  const unanswered = state.questions.length - attempted;
  const elapsed = examClock(state).elapsed;
  await env.QUIZ_STATE.delete(key);
  await telegram(env, "sendMessage", {
    chat_id: chatId,
    text: "🏁 PAPER SUBMITTED\n\n" +
      "Score: " + score + "/" + state.questions.length +
      "\nCorrect: " + score + "\nWrong: " + wrong +
      "\nUnattempted: " + unanswered +
      "\nAccuracy: " + (attempted ? Math.round(score * 100 / attempted) : 0) + "%" +
      "\nTime taken: " + Math.floor(elapsed / 60) + "m " + (elapsed % 60) + "s" +
      "\n\n📖 Detailed solutions follow below."
  });
  for (let i = 0; i < state.questions.length; i++) {
    const q = state.questions[i];
    const chosen = state.answers[i];
    const solution = await explainWithGemini(env, q);
    const label = chosen === undefined ? "Not attempted" :
      (chosen === q.answer ? "Correct" : "Wrong");
    const heading = "Q" + (i + 1) + " — " + label +
      "\nYour answer: " + (chosen === undefined ? "—" : q.options[chosen]) +
      "\nCorrect answer: " + q.options[q.answer] +
      "\n\nSolution:\n";
    const body = heading + solution;
    for (let offset = 0; offset < body.length; offset += 3800) {
      await telegram(env, "sendMessage", { chat_id: chatId, text: body.slice(offset, offset + 3800) });
    }
  }
  await showMainMenu(env, chatId, "Test review complete. Start another paper whenever you're ready.");
}

async function handleMessage(env, message) {
  const chatId = message.chat.id;
  const raw = (message.text || "").trim();
  const text = raw.toLowerCase().replace(/\s+/g, " ");
  if (text === "/start") {
    await showMainMenu(env, chatId, "Welcome! Choose PYQ mode or create a custom AI test.");
    return;
  }
  if (text === "/help" || text === "🆘 help") {
    await showMainMenu(env, chatId,
      "JEE Main Test Bot\n\n📘 PYQ mode: verified past-year questions only.\n🤖 AI Quiz: create new questions from your own instructions.\n\nTry:\n• Create 20 difficult Physics questions from Rotation\n• Make 30 mixed JEE questions, moderate level\n• Give me 15 Chemistry PYQs from Chemical Bonding\n\nDuring a paper: select answers, Previous, Next, Skip, Mark for Review, question palette, then Submit. Solutions appear only after submission.\n\nNote: AI questions are practice questions, not official PYQs.");
    return;
  }
  if (text === "🤖 ai quiz") {
    await env.QUIZ_STATE.put("ai-prompt:" + chatId, "1", { expirationTtl: 600 });
    await telegram(env, "sendMessage", {
      chat_id: chatId,
      text: "Tell me exactly what test you want. Example:\nCreate 25 difficult Physics questions from Rotational Motion, with lengthy calculations."
    });
    return;
  }
  if (text === "📚 subjects") return showSubjects(env, chatId);
  if (text === "🎯 mixed pyq" || text === "🎯 mixed quiz" || text === "/quiz") {
    return askQuestionCount(env, chatId, "mixed", null);
  }
  if (text === "📖 chapter pyq" || text === "📖 chapter quiz" || text === "📊 available topics" || text === "/topics") {
    return showTopicSubjects(env, chatId);
  }
  if (text === "🛑 stop quiz" || text === "/stop") {
    await env.QUIZ_STATE.delete("quiz:" + chatId);
    await showMainMenu(env, chatId, "Current paper stopped.");
    return;
  }
  const forceAi = Boolean(await env.QUIZ_STATE.get("ai-prompt:" + chatId));
  if (forceAi) await env.QUIZ_STATE.delete("ai-prompt:" + chatId);
  if (["⚡ physics", "/physics"].includes(text)) return askQuestionCount(env, chatId, "physics", null);
  if (["🧪 chemistry", "/chemistry"].includes(text)) return askQuestionCount(env, chatId, "chemistry", null);
  if (["📐 mathematics", "/maths"].includes(text)) return askQuestionCount(env, chatId, "maths", null);
  if (text.startsWith("/topic ")) {
    const parts = text.slice(7).trim().split(/\s+/);
    const subject = parts.shift();
    const topic = parts.join(" ");
    if (!["physics", "chemistry", "maths"].includes(subject) || !topic) {
      await telegram(env, "sendMessage", { chat_id: chatId, text: "Use /topic physics rotational-motion" });
    } else return askQuestionCount(env, chatId, subject, topic);
    return;
  }
  try {
    const settings = await interpretRequest(env, raw, forceAi);
    if (settings.action !== "quiz") {
      await telegram(env, "sendMessage", { chat_id: chatId, text: "I couldn't identify the test settings. Tell me the subject, chapter, number of questions and difficulty, or tap 🤖 AI Quiz." });
      return;
    }
    if (settings.mode === "pyq" && forceAi) settings.mode = "ai";
    await startQuiz(env, chatId, settings, raw);
  } catch (e) {
    console.error("Quiz request failed", String(e));
    const detail = String(e?.message || e || "Unknown error").slice(0, 500);
    await telegram(env, "sendMessage", {
      chat_id: chatId,
      text: "❌ I couldn't create the test.\nReason: " + detail +
        "\n\nTry again with fewer questions, or use 🤖 AI Quiz. If this repeats, send me this exact error so I can fix it."
    });
  }
}

async function handleCallback(env, callback) {
  const chatId = callback.message.chat.id;
  const data = String(callback.data || "");
  const parts = data.split(":");
  await telegram(env, "answerCallbackQuery", { callback_query_id: callback.id });
  if (parts[0] === "count") {
    const pending = await env.QUIZ_STATE.get("pending:" + chatId, "json");
    if (!pending) return telegram(env, "sendMessage", { chat_id: chatId, text: "Please choose the PYQ section again." });
    await env.QUIZ_STATE.delete("pending:" + chatId);
    const bank = questions.filter(validQuestion);
    const available = bank.filter(q =>
      (pending.subject === "mixed" || !pending.subject || q.subject.toLowerCase() === pending.subject) &&
      (!pending.topic || normalizeTopic(q.topic || q.chapter).includes(normalizeTopic(pending.topic)))
    ).length;
    const count = parts[1] === "all" ? available : Number(parts[1]);
    return startQuiz(env, chatId, {
      mode: "pyq", subject: pending.subject || "mixed", topic: pending.topic,
      count: Math.max(1, Math.min(30, count || 1)), difficulty: "mixed"
    }, "PYQ menu selection");
  }
  if (parts[0] === "subject") {
    return askQuestionCount(env, chatId, parts[1] === "mixed" ? "mixed" : parts[1], null);
  }
  if (parts[0] === "topic-subject") return showTopics(env, chatId, parts[1]);
  if (parts[0] === "topic") return askQuestionCount(env, chatId, parts[1], parts.slice(2).join(":"));
  const state = await env.QUIZ_STATE.get("quiz:" + chatId, "json");
  if (!state) return telegram(env, "sendMessage", { chat_id: chatId, text: "No active paper. Send /start to begin." });
  if (examClock(state).left <= 0) return submitQuiz(env, chatId, state);
  if (parts[0] === "pick") {
    const index = Number(parts[1]), choice = Number(parts[2]);
    if (index !== state.index || !Number.isInteger(choice) || choice < 0 || choice > 3) return;
    state.answers[index] = choice;
  } else if (parts[0] === "nav") {
    const action = parts[1];
    if (action === "submit") {
      return telegram(env, "sendMessage", {
        chat_id: chatId, text: "Are you sure you want to submit the paper?",
        reply_markup: { inline_keyboard: [[
          { text: "✅ Confirm submit", callback_data: "confirm-submit" },
          { text: "↩ Continue test", callback_data: "cancel-submit" }
        ]] }
      });
    }
    if (action === "prev") state.index = Math.max(0, state.index - 1);
    else if (action === "next" || action === "skip") state.index = Math.min(state.questions.length - 1, state.index + 1);
    else if (action === "mark") {
      state.marked = state.marked.includes(state.index)
        ? state.marked.filter(i => i !== state.index) : [...state.marked, state.index];
    } else if (action && action[0] === "q") {
      const target = Number(action.slice(1));
      if (Number.isInteger(target) && target >= 0 && target < state.questions.length) state.index = target;
    }
  } else if (parts[0] === "confirm-submit") {
    return submitQuiz(env, chatId, state);
  } else if (parts[0] === "cancel-submit") {
    // Keep the current paper open; the next render restores the question controls.
  } else return;
  await saveState(env, chatId, state);
  state.messageId = await renderQuestion(env, chatId, state, callback.message.message_id);
  await saveState(env, chatId, state);
}

export default {
  async scheduled(event, env, ctx) {
    try {
      const page = await env.QUIZ_STATE.list({ prefix: "quiz:", limit: 100 });
      for (const item of page.keys) {
        const chatId = item.name.slice(5);
        const state = await env.QUIZ_STATE.get(item.name, "json");
        if (!state) continue;
        if (examClock(state).left <= 0) {
          await submitQuiz(env, chatId, state);
        } else if (state.messageId) {
          state.messageId = await renderQuestion(env, chatId, state, state.messageId);
          await saveState(env, chatId, state);
        }
      }
    } catch (error) {
      console.error("Scheduled exam timer failed", String(error));
    }
  },
  async fetch(request, env) {
    if (request.method === "GET") return new Response("JEE Main Telegram Quiz Bot is running.");
    if (request.method !== "POST") return new Response("Method not allowed", { status: 405 });
    if (!env.TELEGRAM_TOKEN || !env.TELEGRAM_WEBHOOK_SECRET || !env.QUIZ_STATE) {
      return new Response("Bot configuration is incomplete.", { status: 500 });
    }
    if (request.headers.get("X-Telegram-Bot-Api-Secret-Token") !== env.TELEGRAM_WEBHOOK_SECRET) {
      return new Response("Unauthorized", { status: 401 });
    }
    let update;
    try { update = await request.json(); }
    catch { return new Response("Invalid JSON", { status: 400 }); }
    if (Number.isInteger(update.update_id)) {
      const updateKey = "update:" + update.update_id;
      if (await env.QUIZ_STATE.get(updateKey)) return new Response("OK");
      await env.QUIZ_STATE.put(updateKey, "1", { expirationTtl: 86400 });
    }
    try {
      if (update.message) await handleMessage(env, update.message);
      if (update.callback_query) await handleCallback(env, update.callback_query);
    } catch (error) {
      console.error("Update handling failed", String(error));
    }
    return new Response("OK");
  }
};
