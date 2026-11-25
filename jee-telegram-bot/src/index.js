import questions from "../data/questions.js";
import { showYouTubeUploads, handleYouTubeCallback, registerGeneratedVideo } from "./youtube.js";

const TG = "https://api.telegram.org";
const MAIN_MENU = {
  keyboard: [
    [{ text: "🎯 Mixed PYQ" }, { text: "🤖 AI Quiz" }],
    [{ text: "📚 Subjects" }, { text: "📖 Chapter PYQ" }],
    [{ text: "📅 PYQ by Year" }, { text: "📝 Full Test (75Q)" }],
    [{ text: "📊 Available Topics" }, { text: "📊 Bank Coverage" }],
    [{ text: "📈 My Progress" }, { text: "🧠 Mistake Review" }],
    [{ text: "🎥 Request New Video" }],
    [{ text: "📤 YouTube Uploads" }],
    [{ text: "🆘 Help" }, { text: "🛑 Stop Quiz" }]
  ],
  resize_keyboard: true,
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
  // Keep a short list of this bot's recent messages so setup prompts can
  // be removed when the actual paper begins.
  if (method === "sendMessage" && result.result?.message_id && body.chat_id && env.QUIZ_STATE) {
    try {
      const key = "botmsgs:" + body.chat_id;
      const ids = await env.QUIZ_STATE.get(key, "json") || [];
      ids.push(result.result.message_id);
      await env.QUIZ_STATE.put(key, JSON.stringify(ids.slice(-40)), { expirationTtl: 86400 });
    } catch (e) {
      console.error("Could not track bot message", String(e));
    }
  }
  return result;
}

function validQuestion(q) {
  const common = q && q.verified === true &&
    typeof q.source_url === "string" && /^https?:\/\//i.test(q.source_url) &&
    ["physics", "chemistry", "maths"].includes(String(q.subject).toLowerCase()) &&
    typeof q.question === "string" &&
    (typeof q.topic === "string" || typeof q.chapter === "string");
  if (!common) return false;
  if (q.question_type === "numeric") return Number.isFinite(Number(q.numeric_answer));
  return Array.isArray(q.options) && q.options.length === 4 &&
    q.options.every(x => typeof x === "string" && x.trim()) &&
    Number.isInteger(q.answer) && q.answer >= 0 && q.answer < 4;
}

function isCorrectAnswer(q, value) {
  if (q.question_type === "numeric") {
    return value !== undefined && Number.isFinite(Number(value)) &&
      Math.abs(Number(value) - Number(q.numeric_answer)) <= Number(q.tolerance ?? 0);
  }
  return value === q.answer;
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


async function configureTelegramMenu(env, chatId) {
  await telegram(env, "setMyCommands", { commands: [
    { command: "start", description: "Open the JEE quiz menu" },
    { command: "sections", description: "Show all quiz sections" },
    { command: "subjects", description: "Choose Physics, Chemistry or Maths" },
    { command: "chapters", description: "Browse chapter-wise PYQs" },
    { command: "years", description: "Choose a PYQ year" },
    { command: "fullpaper", description: "Open full-paper options" },
    { command: "coverage", description: "View question-bank coverage" },
    { command: "progress", description: "View your progress" },
    { command: "mistakes", description: "Review incorrect answers" },
    { command: "help", description: "How to use the quiz bot" },
    { command: "stop", description: "Stop the current quiz" },
    { command: "video", description: "Generate an educational AI video" },
    { command: "feedback", description: "View saved video feedback" },
    { command: "youtube", description: "Upload a generated video to YouTube" }
  ]});
  await telegram(env, "setChatMenuButton", {
    chat_id: chatId,
    menu_button: { type: "commands" }
  });
}

async function showSections(env, chatId) {
  await telegram(env, "sendMessage", {
    chat_id: chatId,
    text: "📚 JEE BOT SECTIONS — choose one:",
    reply_markup: { inline_keyboard: [
      [{ text: "🎥 Request New Video", callback_data: "section:video" }],
      [{ text: "📤 YouTube Uploads", callback_data: "section:youtube" }],
      [{ text: "🎯 Mixed PYQ", callback_data: "section:mixed" }],
      [{ text: "📚 Subjects", callback_data: "section:subjects" }],
      [{ text: "📖 Chapter PYQ", callback_data: "section:chapters" }],
      [{ text: "📅 PYQ by Year", callback_data: "section:years" }],
      [{ text: "📝 Full Test (75Q)", callback_data: "section:fullpaper" }],
      [{ text: "📊 Available Topics", callback_data: "section:topics" }],
      [{ text: "📊 Bank Coverage", callback_data: "section:coverage" }],
      [{ text: "📈 My Progress", callback_data: "section:progress" }],
      [{ text: "🧠 Mistake Review", callback_data: "section:mistakes" }]
    ]}
  });
}

async function showMainMenu(env, chatId, message) {
  await telegram(env, "sendMessage", {
    chat_id: chatId,
    text: message || "Choose a quiz mode below.",
    reply_markup: MAIN_MENU
  });
}

async function askQuestionCount(env, chatId, subject, topic, year) {
  await env.QUIZ_STATE.put("pending:" + chatId, JSON.stringify({
    subject: subject || null, topic: topic || null, year: year || null
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

async function askTimingMode(env, chatId, pending) {
  await env.QUIZ_STATE.put("pending:" + chatId, JSON.stringify(pending), { expirationTtl: 600 });
  await telegram(env, "sendMessage", {
    chat_id: chatId, text: "Choose your test timing:",
    reply_markup: { inline_keyboard: [
      [{ text: "⏱ Timed test", callback_data: "timing:timed" }],
      [{ text: "♾ Timeless (no countdown)", callback_data: "timing:untimed" }]
    ]}
  });
}

async function askDuration(env, chatId) {
  await telegram(env, "sendMessage", {
    chat_id: chatId, text: "Choose the total time limit:",
    reply_markup: { inline_keyboard: [
      [{ text: "30 minutes", callback_data: "duration:30" }, { text: "60 minutes", callback_data: "duration:60" }],
      [{ text: "90 minutes", callback_data: "duration:90" }, { text: "120 minutes", callback_data: "duration:120" }],
      [{ text: "180 minutes (3 hours)", callback_data: "duration:180" }]
    ]}
  });
}
async function showFullPaperInstructions(env, chatId, pending) {
  await env.QUIZ_STATE.put("pending:" + chatId, JSON.stringify(pending), { expirationTtl: 600 });
  await telegram(env, "sendMessage", {
    chat_id: chatId,
    text: "📋 JEE MAIN FULL PAPER — INSTRUCTIONS\n\n1. This is an exam-style paper. Try to complete it in one sitting.\n2. Select one option for each MCQ. Your selected answer is saved automatically.\n3. Use Previous / Next to move between questions. Skip leaves a question unanswered.\n4. Use the question palette to jump to any question.\n5. Palette: ⬜ not visited, 🟥 visited but unanswered, 🟩 answered, 🟨 marked for review.\n6. Use Mark for Review when you want to revisit a question.\n7. Submit the paper when finished. You will be asked to confirm. Answers and solutions are shown only after submission.\n8. The timer runs from the moment the paper starts and the paper auto-submits when time ends.\n\nStart the paper now?",
    reply_markup: { inline_keyboard: [
      [{ text: "▶️ Start full paper", callback_data: "fullpaper-start" }],
      [{ text: "↩ Cancel", callback_data: "fullpaper-cancel" }]
    ]}
  });
}

async function showFullPaperOptions(env, chatId) {
  const bank = questions.filter(validQuestion);
  const groups = new Map();
  for (const q of bank) {
    if (!q.year || !q.shift) continue;
    const key = String(q.year) + "|" + String(q.shift);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(q);
  }
  const complete = [...groups.entries()].filter(([, qs]) => qs.length >= 75);
  if (!complete.length) {
    const summary = [...groups.entries()].map(([key, qs]) => key.replace("|", " ") + ": " + qs.length + "/75").join("\\n");
    await telegram(env, "sendMessage", {
      chat_id: chatId,
      text: "📝 Full PYQ Paper mode is available, but no shift in the current local bank has all 75 questions yet. I will not label a partial set as a full paper. Current coverage:\\n" + (summary || "No complete shift imported yet.")
    });
    return;
  }
  await telegram(env, "sendMessage", {
    chat_id: chatId, text: "Choose a complete JEE Main Paper 1 shift:",
    reply_markup: { inline_keyboard: complete.map(([key, qs]) => [{
      text: key.replace("|", " · ") + " (" + qs.length + " Q)",
      callback_data: "fullpaper:" + encodeURIComponent(key)
    }]) }
  });
}

async function showBankCoverage(env, chatId) {
  const bank = questions.filter(validQuestion);
  const years = [...new Set(bank.map(q=>String(q.year || "Unknown")))].sort((x,y)=>Number(y)-Number(x));
  const lines = years.map(year => {
    const subset = bank.filter(q=>String(q.year || "Unknown")===year);
    return year + " — " + subset.length + " verified entries | Physics " +
      subset.filter(q=>q.subject.toLowerCase()==="physics").length + " · Chemistry " +
      subset.filter(q=>q.subject.toLowerCase()==="chemistry").length + " · Maths " +
      subset.filter(q=>q.subject.toLowerCase()==="maths").length;
  });
  await telegram(env, "sendMessage", {
    chat_id: chatId,
    text: "📊 PYQ BANK COVERAGE\n\nVerified entries currently loaded: " + bank.length +
      "\n\n" + (lines.join("\n") || "No verified entries") +
      "\n\nCoverage is not yet complete for every JEE Main year/shift. Full-paper mode appears only when a complete 75-question shift is available."
  });
}

async function showYears(env, chatId) {
  const years = [...new Set(questions.filter(validQuestion).map(q => String(q.year || "")).filter(Boolean))].sort((a,b) => Number(b)-Number(a));
  if (!years.length) return telegram(env, "sendMessage", { chat_id: chatId, text: "No year-tagged PYQs are available yet." });
  const rows = [];
  for (let i=0;i<years.length;i+=2) {
    rows.push(years.slice(i,i+2).map(year => ({ text: "📅 " + year, callback_data: "year:" + year })));
  }
  await telegram(env, "sendMessage", { chat_id: chatId, text: "Choose the JEE Main PYQ year:", reply_markup: { inline_keyboard: rows } });
}

async function showYearSubjects(env, chatId, year) {
  const bank = questions.filter(validQuestion).filter(q => String(q.year) === String(year));
  const counts = ["physics","chemistry","maths"].map(subject => ({subject,count:bank.filter(q=>q.subject.toLowerCase()===subject).length}));
  const names = {physics:"⚡ Physics",chemistry:"🧪 Chemistry",maths:"📐 Mathematics"};
  const rows = counts.filter(x=>x.count>0).map(x=>[{text:names[x.subject]+" ("+x.count+")",callback_data:"year-subject:"+year+":"+x.subject}]);
  if (bank.length) rows.push([{text:"🎯 All subjects ("+bank.length+")",callback_data:"year-subject:"+year+":mixed"}]);
  await telegram(env, "sendMessage", {chat_id:chatId,text:"📅 "+year+" PYQs found in the current verified bank. Choose subject:",reply_markup:{inline_keyboard:rows}});
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

  // Try the configured primary model first, then stable Flash fallbacks.
  // Retry temporary overload/rate-limit errors with short backoff.
  const models = [
    env.GEMINI_MODEL || "gemini-3.8-flash",
    "gemini-2.5-flash",
    "gemini-2.0-flash"
  ].filter((m, i, a) => a.indexOf(m) === i);
  let lastError = null;

  for (const model of models) {
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        const response = await fetch(
          "https://generativelanguage.googleapis.com/v1beta/models/" + model + ":generateContent",
          {
            method: "POST",
            headers: { "content-type": "application/json", "x-goog-api-key": env.GEMINI_API_KEY },
            body: JSON.stringify({
              contents: [{ role: "user", parts: [{ text: prompt }] }],
              generationConfig: {
                responseMimeType: "application/json",
                maxOutputTokens: maxTokens || 8192
              }
            })
          }
        );
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
          const detail = data.error?.message || ("HTTP " + response.status);
          lastError = new Error("Gemini API (" + model + "): " + detail);
          const transient = response.status === 429 || response.status === 500 ||
            response.status === 502 || response.status === 503 || response.status === 504 ||
            /high demand|overload|temporar|resource exhausted|rate.?limit/i.test(detail);
          if (!transient) break;
          if (attempt === 0) await new Promise(resolve => setTimeout(resolve, 900));
          continue;
        }

        const candidate = data.candidates?.[0];
        const raw = candidate?.content?.parts?.map(p => p.text || "").join("").trim();
        if (!raw) {
          const reason = candidate?.finishReason || data.promptFeedback?.blockReason || "empty response";
          lastError = new Error("Gemini returned no text (" + reason + ")");
          break;
        }
        const cleaned = raw.replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, "").trim();
        try {
          return JSON.parse(cleaned);
        } catch (e) {
          lastError = new Error("Gemini returned incomplete/invalid JSON (" + (candidate?.finishReason || "unknown") + ")");
          break;
        }
      } catch (e) {
        lastError = e;
        if (attempt === 0) await new Promise(resolve => setTimeout(resolve, 900));
      }
    }
  }
  throw lastError || new Error("All Gemini models are temporarily unavailable");
}

function interpretRequest(rawText, forceAi) {
  const raw = String(rawText || "").trim();
  const lower = raw.toLowerCase();
  const explicitPyq = /\b(pyq|previous[- ]year|past[- ]year|previous year question)\b/.test(lower);
  const aiIntent = forceAi || (!explicitPyq && /\b(ai quiz|create|generate|make me|make a|custom|new questions|practice questions)\b/.test(lower));
  let subject = "mixed";
  if (/\b(physics|phy)\b/.test(lower)) subject = "physics";
  else if (/\b(chemistry|chem)\b/.test(lower)) subject = "chemistry";
  else if (/\b(math|maths|mathematics)\b/.test(lower)) subject = "maths";
  const countMatch = lower.match(/\b(\d{1,2})\s*(?:questions?|q(?:uestions?)?)?\b/);
  const count = Math.max(1, Math.min(30, countMatch ? Number(countMatch[1]) : 10));
  let topic = "";
  const topicMatch = raw.match(/\b(?:from|on|in|chapter(?:\s+of)?)\s+(.+?)(?=\s+(?:with|at|level|difficulty|and)\b|[,;]|$)/i);
  if (topicMatch) {
    topic = topicMatch[1].replace(/\b(jee|jee main|pyqs?|questions?)\b/ig, "").trim();
  }
  let difficulty = "moderate";
  if (/\b(easy|basic)\b/.test(lower)) difficulty = "easy";
  else if (/\b(difficult|hard|tough)\b/.test(lower)) difficulty = "difficult";
  else if (/\bmixed difficulty\b/.test(lower)) difficulty = "mixed";
  const looksLikeQuiz = /\b(jee|quiz|test|paper|questions?|pyq|practice)\b/.test(lower) || forceAi;
  if (!looksLikeQuiz) return { action: "help" };
  return {
    action: "quiz",
    mode: aiIntent ? "ai" : "pyq",
    subject,
    topic,
    count,
    difficulty,
    questionType: "mcq",
    year: (lower.match(/\b(20(?:19|20|21|22|23|24|25|26))\b/) || [])[1] || null
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
  if (state.timed === false) return { elapsed, left: Infinity, label: "Untimed" };
  const total = state.durationSeconds || state.questions.length * 144;
  const left = Math.max(0, total - elapsed);
  const mm = String(Math.floor(left / 60)).padStart(2, "0");
  const ss = String(left % 60).padStart(2, "0");
  return { elapsed, left, label: mm + ":" + ss };
}

async function renderQuestion(env, chatId, state, messageId) {
  const q = state.questions[state.index], review = state.reviewMode === true;
  const isAi = state.mode === "ai", clock = examClock(state);
  const selected = state.answers[state.index], marked = state.marked.includes(state.index);
  const safe = value => String(value ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const header = review ? "📊 JEE MAIN — PAPER REVIEW" : (isAi ? "🤖 AI-GENERATED PRACTICE" : "📘 JEE MAIN PYQ");
  const examLine = !isAi ? ["JEE MAIN", q.year, q.shift].filter(Boolean).join(" | ") : "";
  const isNumeric = q.question_type === "numeric";
  const options = isNumeric ? [] : q.options.map((option, i) => {
    let prefix = selected === i ? "🔘 " : "◯ ";
    if (review) prefix = i === q.answer ? "🟩 " : (selected === i ? "🟥 " : "▫️ ");
    return [{ text: prefix + String.fromCharCode(65 + i) + ". " + option.slice(0, 42),
      callback_data: review ? "review:noop" : "pick:" + state.index + ":" + i }];
  });
  const controls = review ? [[
    { text: "⬅ Previous", callback_data: "review:prev" },
    { text: "➡ Next", callback_data: "review:next" }
  ]] : [
    [{ text: "⬅ Previous", callback_data: "nav:prev" }, { text: "➡ Next", callback_data: "nav:next" }, { text: "⏭ Skip", callback_data: "nav:skip" }],
    [{ text: marked ? "★ Unmark" : "☆ Mark review", callback_data: "nav:mark" }, { text: "📋 Submit paper", callback_data: "nav:submit" }],
    ...(isNumeric ? [] : [[{ text: "🔎 Second-opinion check", callback_data: "verify:current" }]])
  ];
  const palettePageSize = 20;
  const palettePageCount = Math.ceil(state.questions.length / palettePageSize);
  const palettePage = Math.min(palettePageCount - 1, Math.max(0,
    Number.isInteger(state.palettePage) ? state.palettePage : Math.floor(state.index / palettePageSize)));
  state.palettePage = palettePage;
  const paletteStart = palettePage * palettePageSize;
  const palette = state.questions.slice(paletteStart, paletteStart + palettePageSize).map((_, offset) => {
    const i = paletteStart + offset;
    let icon;
    if (review) {
      const a = state.answers[i];
      icon = a === undefined ? "⬜" : (isCorrectAnswer(state.questions[i], a) ? "🟩" : "🟥");
    } else icon = state.marked.includes(i) ? "🟨" : (state.answers[i] !== undefined ? "🟩" : (state.visited?.includes(i) ? "🟥" : "⬜"));
    return { text: icon + (i + 1), callback_data: (review ? "review:q" : "nav:q") + i };
  });
  const paletteRows = [];
  for (let i = 0; i < palette.length; i += 5) paletteRows.push(palette.slice(i, i + 5));
  if (palettePageCount > 1) {
    paletteRows.push([
      ...(palettePage > 0 ? [{ text: "⬅ Q" + (paletteStart - palettePageSize + 1) + "–" + paletteStart, callback_data: "palette:page:" + (palettePage - 1) }] : []),
      { text: "Questions " + (paletteStart + 1) + "–" + Math.min(state.questions.length, paletteStart + palettePageSize), callback_data: "palette:stay" },
      ...(palettePage < palettePageCount - 1 ? [{ text: "Q" + (paletteStart + palettePageSize + 1) + "–" + Math.min(state.questions.length, paletteStart + 2 * palettePageSize) + " ➡", callback_data: "palette:page:" + (palettePage + 1) }] : [])
    ]);
  }
  const summary = review && state.summary
    ? "<b>RESULT:</b> " + state.summary.score + "/" + state.questions.length + "  |  🟩 " + state.summary.correct + "  |  🟥 " + state.summary.wrong + "  |  ⬜ " + state.summary.unanswered +
      "\n<b>Accuracy:</b> " + state.summary.accuracy + "%  •  <b>Time:</b> " + state.summary.time + "\n\n" : "";
  const yourAnswer = selected === undefined ? "Not attempted" :
    (isNumeric ? safe(selected) : String.fromCharCode(65 + selected) + ". " + safe(q.options[selected]));
  const correctAnswer = isNumeric ? safe(q.numeric_answer) :
    String.fromCharCode(65 + q.answer) + ". " + safe(q.options[q.answer]);
  const explanation = review
    ? "\n\n<b>Your answer:</b> " + yourAnswer +
      "\n<b>Correct answer:</b> 🟩 " + correctAnswer +
      "\n<b>Result:</b> " + (selected === undefined ? "⬜ Not attempted" : (isCorrectAnswer(q, selected) ? "🟩 Correct" : "🟥 Incorrect")) +
      "\n\n<b>Solution:</b>\n" + safe(q.explanation || "No explanation is available for this question.")
    : (selected === undefined ? (isNumeric ? "\n\n<i>Type your numerical answer in the chat and send it.</i>" : "\n\nNot answered") :
      (isNumeric ? "\n\nYour answer: " + safe(selected) : "\n\nYour answer: " + String.fromCharCode(65 + selected))) +
      (marked ? "\n⭐ Marked for review" : "");
  const optionsText = isNumeric ? "" :
    q.options.map((o, i) => "<b>" + String.fromCharCode(65 + i) + ".</b> " + safe(o)).join("\n") + "\n\n";
  const text = "<b>" + header + "</b>\n" + summary +
    (examLine ? "<i>" + safe(examLine) + "</i>\n" : "") +
    "<b>Question " + (state.index + 1) + "/" + state.questions.length + "</b>" + (review ? "" : "   ⏱ " + clock.label) + "\n" +
    "<b>Chapter:</b> " + safe(q.topic || q.chapter || "Mixed") + "\n\n" + safe(q.question) + "\n\n" +
    optionsText + explanation;
  const reply_markup = { inline_keyboard: [...options, ...controls, ...paletteRows,
    ...(review ? [[{ text: "🏁 Finish review", callback_data: "review:finish" }]] : [])] };
  if (messageId) {
    try {
      await telegram(env, "editMessageText", { chat_id: chatId, message_id: messageId, text, parse_mode: "HTML", reply_markup, disable_web_page_preview: true });
      return messageId;
    } catch (e) { console.error("Could not edit question message; sending new one", String(e)); }
  }
  const sent = await telegram(env, "sendMessage", { chat_id: chatId, text, parse_mode: "HTML", reply_markup, disable_web_page_preview: true });
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
    if (settings.fullPaperKey) {
      const [year, shift] = settings.fullPaperKey.split("|");
      chosen = bank.filter(q => String(q.year) === year && String(q.shift) === shift)
        .sort((a, b) => {
          const subjectOrder = { maths: 0, physics: 1, chemistry: 2 };
          const subjectDiff = (subjectOrder[a.subject] ?? 9) - (subjectOrder[b.subject] ?? 9);
          if (subjectDiff) return subjectDiff;
          const numberA = Number(String(a.id || "").match(/-q(\\d+)$/)?.[1] || 0);
          const numberB = Number(String(b.id || "").match(/-q(\\d+)$/)?.[1] || 0);
          return numberA - numberB;
        });
    } else {
      const wantedTopic = normalizeTopic(settings.topic);
      chosen = shuffled(bank.filter(q => {
      const subjectOk = settings.subject === "mixed" || q.subject.toLowerCase() === settings.subject;
      const topic = normalizeTopic(q.topic || q.chapter);
      const topicOk = !wantedTopic || topic.includes(wantedTopic) || wantedTopic.includes(topic);
      const yearOk = !settings.year || String(q.year) === String(settings.year);
      return subjectOk && topicOk && yearOk;
      })).slice(0, settings.count);
    }
    if (!chosen.length) {
      await telegram(env, "sendMessage", {
        chat_id: chatId,
        text: "No verified PYQs match this selection yet. The current bank has " + bank.length + " verified entries. Please choose another subject/chapter/year or use 🤖 AI Quiz."
      });
      await showMainMenu(env, chatId, "Choose another section to continue.");
      return;
    }
  }
  const state = {
    mode: settings.mode, questions: chosen, index: 0, answers: {}, marked: [], visited: [0],
    startedAt: Date.now(),
    timed: settings.timed !== false,
    durationSeconds: settings.timed === false ? null : (settings.durationSeconds || chosen.length * 144),
    messageId: null
  };
  // Keep the main menu and setup sections available while the paper is active.
  // Do not bulk-delete bot messages: the old tracker included the persistent
  // reply-keyboard menu, which made the whole menu disappear when a test began.

  await saveState(env, chatId, state);
  state.messageId = await renderQuestion(env, chatId, state);
  await saveState(env, chatId, state);
}

async function verifyQuestionWithGemini(env, chatId, q, questionNumber) {
  const prompt = [
    "Act as an independent JEE Main examiner. Solve this question from first principles.",
    "Do not trust or assume the supplied answer is correct. Check for ambiguity, missing data, and calculation errors.",
    'Return JSON only: {"status":"agree"|"disagree"|"ambiguous","computed_answer":0,"reason":"brief reasoning"}.',
    "The computed_answer must be the zero-based option index, or -1 if no unique option.",
    "Subject: " + q.subject + "; topic: " + (q.topic || "unspecified"),
    "Question: " + q.question,
    ...q.options.map((o,i)=>"Option "+i+": "+o),
    "Stored answer index (for comparison only): " + q.answer
  ].join("\n");
  try {
    const result = await callGemini(env, prompt, 700);
    const computed = Number(result.computed_answer);
    const status = result.status || (computed === q.answer ? "agree" : "disagree");
    const heading = status === "agree" && computed === q.answer
      ? "✅ Second check agrees with the stored answer."
      : status === "disagree" || (Number.isInteger(computed) && computed !== q.answer)
        ? "⚠️ Second check disagrees. Treat this question as needing manual review."
        : "🟨 Second check could not confirm a unique answer.";
    await telegram(env, "sendMessage", {
      chat_id: chatId,
      text: "🔎 INDEPENDENT AI CHECK — Q" + questionNumber + "\n" + heading +
        "\nStored answer: " + (q.options[q.answer] || "Unknown") +
        "\nAI-computed answer: " + (Number.isInteger(computed) && computed >= 0 && computed < 4 ? q.options[computed] : "Not confirmed") +
        "\nReason: " + String(result.reason || "No reasoning supplied").slice(0, 1200) +
        "\n\nThis is an AI second opinion, not an official NTA verification."
    });
  } catch (e) {
    await telegram(env, "sendMessage", { chat_id: chatId, text: "Second-opinion check is temporarily unavailable: " + String(e.message || e).slice(0,300) + "\nThe stored answer has not been changed." });
  }
}

async function showProgress(env, chatId) {
  const p = await env.QUIZ_STATE.get("progress:" + chatId, "json") || { papers: 0, total: 0, attempted: 0, correct: 0 };
  const accuracy = p.attempted ? Math.round(p.correct * 100 / p.attempted) : 0;
  await telegram(env, "sendMessage", {
    chat_id: chatId,
    text: "📈 YOUR JEE PROGRESS\n\nPapers submitted: " + p.papers +
      "\nQuestions seen: " + p.total +
      "\nAttempted: " + p.attempted +
      "\nCorrect: " + p.correct +
      "\nAccuracy: " + accuracy + "%" +
      "\n\nAccuracy is calculated across submitted papers on this Telegram account."
  });
}

async function showMistakes(env, chatId) {
  const mistakes = await env.QUIZ_STATE.get("mistakes:" + chatId, "json") || [];
  if (!mistakes.length) return telegram(env, "sendMessage", { chat_id: chatId, text: "🧠 No saved mistakes yet. Wrong answers from submitted papers will appear here." });
  const lines = mistakes.slice(-10).reverse().map((q,i) =>
    (i+1)+". ["+(q.year || "AI practice")+"] "+(q.subject || "")+" · "+(q.topic || "Mixed")+
    "\n"+String(q.question || "").slice(0,240)+
    "\nCorrect: "+(q.question_type === "numeric" ? q.numeric_answer : (q.options?.[q.answer] || "Not available"))
  );
  await telegram(env, "sendMessage", { chat_id: chatId, text: "🧠 RECENT MISTAKES — review these concepts\n\n"+lines.join("\n\n") });
}

async function submitQuiz(env, chatId, state) {
  if (state.reviewMode) return;
  let score = 0, attempted = 0;
  for (let i = 0; i < state.questions.length; i++) {
    const a = state.answers[i];
    if (a !== undefined) { attempted++; if (isCorrectAnswer(state.questions[i], a)) score++; }
  }
  const wrong = attempted - score, unanswered = state.questions.length - attempted;
  const elapsed = examClock(state).elapsed;
  const summary = { score, correct: score, wrong, unanswered,
    accuracy: attempted ? Math.round(score * 100 / attempted) : 0,
    time: Math.floor(elapsed / 60) + "m " + (elapsed % 60) + "s" };
  const progressKey = "progress:" + chatId;
  const progress = await env.QUIZ_STATE.get(progressKey, "json") || { papers: 0, total: 0, attempted: 0, correct: 0 };
  progress.papers++; progress.total += state.questions.length; progress.attempted += attempted; progress.correct += score;
  await env.QUIZ_STATE.put(progressKey, JSON.stringify(progress), { expirationTtl: 31536000 });
  const mistakeKey = "mistakes:" + chatId;
  const oldMistakes = await env.QUIZ_STATE.get(mistakeKey, "json") || [];
  for (let i = 0; i < state.questions.length; i++) {
    if (state.answers[i] !== undefined && !isCorrectAnswer(state.questions[i], state.answers[i])) {
      const q = state.questions[i];
      oldMistakes.push({ id:q.id, year:q.year, shift:q.shift, subject:q.subject, topic:q.topic, question:q.question, options:q.options, answer:q.answer, question_type:q.question_type, numeric_answer:q.numeric_answer, explanation:q.explanation });
    }
  }
  await env.QUIZ_STATE.put(mistakeKey, JSON.stringify(oldMistakes.slice(-50)), { expirationTtl: 31536000 });
  state.reviewMode = true; state.summary = summary; state.timed = false; state.index = 0;
  await saveState(env, chatId, state);
  state.messageId = await renderQuestion(env, chatId, state, state.messageId);
  await saveState(env, chatId, state);
}

async function understandNaturalRequest(env, raw) {
  const prompt = [
    "You are the natural-language intent engine for a JEE Main Telegram quiz bot.",
    "Understand informal English, Indian English, typos, incomplete phrases and follow-up style requests.",
    "Return JSON only with this schema:",
    '{"action":"quiz|chat|clarify","mode":"ai|pyq","subject":"physics|chemistry|maths|mixed","topic":"","count":10,"difficulty":"easy|moderate|difficult|mixed","year":null,"reply":""}',
    "If the user wants questions, a test, practice, a mock paper, PYQs, or asks to change quiz settings, choose action=quiz.",
    "Use mode=pyq ONLY when they explicitly ask for previous-year questions/PYQs; otherwise use ai.",
    "Infer subject/topic/count/difficulty/year when stated. If count is not stated use 10. If subject is not stated use mixed. Do not demand every field.",
    "Normalize subject names: mathematics/math/maths -> maths; physical science/phy -> physics.",
    "If user says 'make it harder/easier', 'same chapter', 'more questions' or similar and no prior context is supplied, choose sensible defaults and put any needed clarification in reply.",
    "If it is ordinary conversation unrelated to making or changing a quiz, choose action=chat and give a short useful reply.",
    "If genuinely impossible to know what quiz action is intended, choose action=clarify and ask only one short question.",
    "Never claim AI-created questions are official PYQs.",
    "User message: " + raw
  ].join("\n");
  const parsed = await callGemini(env, prompt, 900);
  const subject = ["physics","chemistry","maths","mixed"].includes(String(parsed.subject).toLowerCase())
    ? String(parsed.subject).toLowerCase() : "mixed";
  const mode = parsed.mode === "pyq" ? "pyq" : "ai";
  const count = Math.max(1, Math.min(30, Number.parseInt(parsed.count, 10) || 10));
  const difficulty = ["easy","moderate","difficult","mixed"].includes(String(parsed.difficulty).toLowerCase())
    ? String(parsed.difficulty).toLowerCase() : "moderate";
  const action = ["quiz","chat","clarify"].includes(parsed.action) ? parsed.action : "clarify";
  return {
    action, mode, subject,
    topic: String(parsed.topic || "").trim().slice(0,100),
    count, difficulty,
    year: /^20(?:19|20|21|22|23|24|25|26)$/.test(String(parsed.year || "")) ? String(parsed.year) : null,
    reply: String(parsed.reply || "").trim().slice(0,700)
  };
}

async function askVideoTopic(env, chatId) {
  await env.QUIZ_STATE.put("video-pending:" + chatId, "topic", { expirationTtl: 900 });
  await telegram(env, "sendMessage", {
    chat_id: chatId,
    text: "🎬 AI VIDEO GENERATOR\n\nSend the topic or story for your video.\n\nExample: The untold story of U Tirot Sing and the Khasi resistance in 1829.\n\nTarget: realistic cinematic visuals, vertical 9:16, Hindi narration and subtitles.",
    reply_markup: { inline_keyboard: [[{ text: "✖ Cancel", callback_data: "video:cancel" }]] }
  });
}

async function dispatchVideoWorkflow(env, chatId, topic) {
  if (!env.GITHUB_TOKEN) {
    await telegram(env, "sendMessage", {
      chat_id: chatId,
      text: "⚠️ Video generation is not connected yet. The bot needs the GITHUB_TOKEN Worker secret with Actions: write permission. Add it in Cloudflare Worker settings, then try again."
    });
    return;
  }
  const feedbackItems = await env.QUIZ_STATE.get("video-feedback:global", "json") || [];
  const feedbackSummary = feedbackItems.slice(-12).map(item =>
    "- " + item.rating.toUpperCase() + (item.topic ? " | video: " + item.topic : "") +
    (item.comment ? " | note: " + item.comment : "")
  ).join("\n").slice(0, 3000);
  const response = await fetch("https://api.github.com/repos/echo-kernel/Shorts-pipeline/actions/workflows/run.yml/dispatches", {
    method: "POST",
    headers: {
      "Accept": "application/vnd.github+json",
      "User-Agent": "JEE-Telegram-Quiz-Bot/1.0 (https://github.com/stonecrusher1india/Shorts-pipeline)",
      "Authorization": "Bearer " + env.GITHUB_TOKEN,
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      ref: "jee-telegram-quiz",
      inputs: { topic: topic.slice(0, 500), chat_id: String(chatId), feedback: feedbackSummary }
    })
  });
  if (response.status !== 204) {
    const detail = (await response.text()).slice(0, 500);
    console.error("Video workflow dispatch failed", response.status, detail);
    throw new Error("GitHub rejected the video job (HTTP " + response.status + "): " + (detail || "No response details") + ". Check the VIDEO_GITHUB_TOKEN secret and GitHub Actions write access.");
  }
  await telegram(env, "sendMessage", {
    chat_id: chatId,
    text: "🚀 Your AI explainer video request has been sent to GitHub Actions!\n\nTopic: " + topic.slice(0, 400) + "\nQuality: photorealistic educational explainer, vertical 9:16, Hindi narration and subtitles.\n\nI'll send the finished MP4 here when generation completes."
  });
}

async function handleMessage(env, message) {
  const chatId = message.chat.id;
  const raw = (message.text || "").trim();
  const text = raw.toLowerCase().replace(/\s+/g, " ");
  if (text === "/start") {
    await configureTelegramMenu(env, chatId);
    await showMainMenu(env, chatId, "Welcome! Choose PYQ mode or create a custom AI test.");
    return;
  }
  const pendingVideoReport = await env.QUIZ_STATE.get("video-feedback-report:" + chatId, "json");
  if (pendingVideoReport && raw && !raw.startsWith("/")) {
    const items = await env.QUIZ_STATE.get("video-feedback:global", "json") || [];
    items.push({
      rating: "report",
      topic: pendingVideoReport.topic || "",
      comment: raw.slice(0, 700),
      createdAt: new Date().toISOString()
    });
    await env.QUIZ_STATE.put("video-feedback:global", JSON.stringify(items.slice(-30)));
    await env.QUIZ_STATE.delete("video-feedback-report:" + chatId);
    await telegram(env, "sendMessage", {
      chat_id: chatId,
      text: "✅ Your report is saved and will be included in the guidance for the next video."
    });
    return;
  }
  if (text === "/youtube" || text === "📤 youtube uploads") return showYouTubeUploads(env, chatId);
  if (text === "/feedback") {
    const items = await env.QUIZ_STATE.get("video-feedback:global", "json") || [];
    const counts = items.reduce((acc, item) => {
      acc[item.rating] = (acc[item.rating] || 0) + 1;
      return acc;
    }, {});
    return telegram(env, "sendMessage", {
      chat_id: chatId,
      text: "📊 Video feedback saved: " + items.length + " recent responses.\n👍 Good: " + (counts.good || 0) +
        "\n👎 Poor: " + (counts.poor || 0) + "\n📝 Reports: " + (counts.report || 0) +
        "\n\nRecent feedback is sent to the next video-generation prompt."
    });
  }
  if (text === "/sections") return showSections(env, chatId);
  if (text === "/video" || text === "🎬 generate ai video" || text === "🎥 request new video") return askVideoTopic(env, chatId);
  if (text === "/subjects") return showSubjects(env, chatId);
  if (text === "/chapters" || text === "/topics") return showTopicSubjects(env, chatId);
  if (text === "/help" || text === "🆘 help") {
    await showMainMenu(env, chatId,
      "JEE MAIN • SMART PRACTICE\n\n📘 PYQ mode: verified past-year questions only.\n🤖 AI Quiz: create new questions from your own instructions.\n🔎 Second-opinion check: independently ask AI to solve the current question.\n📈 Progress and 🧠 mistake review are saved for your account.\n📊 Bank Coverage shows what is actually loaded.\n\nTry:\n• Create 20 difficult Physics questions from Rotation\n• Make 30 mixed JEE questions, moderate level\n• Give me 15 Chemistry PYQs from Chemical Bonding\n\nDuring a paper: select answers, Previous, Next, Skip, Mark for Review, question palette, then Submit. Solutions appear only after submission.\n\nNote: AI questions are practice questions, not official PYQs.");
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
  if (text === "📝 full test (75q)" || text === "📝 full pyq paper" || text === "/fullpaper") return showFullPaperOptions(env, chatId);
  if (text === "📅 pyq by year" || text === "/years") return showYears(env, chatId);
  if (text === "📊 bank coverage" || text === "/coverage") return showBankCoverage(env, chatId);
  if (text === "📈 my progress" || text === "/progress") return showProgress(env, chatId);
  if (text === "🧠 mistake review" || text === "/mistakes") return showMistakes(env, chatId);
  if (text === "🛑 stop quiz" || text === "/stop") {
    await env.QUIZ_STATE.delete("quiz:" + chatId);
    await showMainMenu(env, chatId, "Current paper stopped.");
    return;
  }
  const activeQuiz = await env.QUIZ_STATE.get("quiz:" + chatId, "json");
  const activeQuestion = activeQuiz?.questions?.[activeQuiz.index];
  if (activeQuestion?.question_type === "numeric" && !activeQuiz.reviewMode &&
      /^[-+]?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?$/i.test(raw.replace(/,/g, ""))) {
    const numericValue = Number(raw.replace(/,/g, ""));
    activeQuiz.answers = activeQuiz.answers || {};
    activeQuiz.answers[activeQuiz.index] = numericValue;
    await saveState(env, chatId, activeQuiz);
    activeQuiz.messageId = await renderQuestion(env, chatId, activeQuiz, activeQuiz.messageId);
    await saveState(env, chatId, activeQuiz);
    return;
  }
  const videoPending = await env.QUIZ_STATE.get("video-pending:" + chatId);
  if (videoPending === "topic" && raw) {
    await env.QUIZ_STATE.delete("video-pending:" + chatId);
    const topic = raw.trim().slice(0, 500);
    await env.QUIZ_STATE.put("video-topic:" + chatId, topic, { expirationTtl: 900 });
    await telegram(env, "sendMessage", {
      chat_id: chatId,
      text: "Choose the video quality:",
      reply_markup: { inline_keyboard: [
        [{ text: "🎬 Photorealistic cinematic (recommended)", callback_data: "video:cinematic" }],
        [{ text: "✖ Cancel", callback_data: "video:cancel" }]
      ]}
    });
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
    let settings = interpretRequest(raw, forceAi);
    if (settings.action !== "quiz") {
      // Let Gemini understand free-form requests instead of rejecting anything
      // that does not match the old fixed keyword patterns.
      settings = await understandNaturalRequest(env, raw);
      if (settings.action === "chat" || settings.action === "clarify") {
        await telegram(env, "sendMessage", {
          chat_id: chatId,
          text: settings.reply || "I can create JEE practice tests or find PYQs. Tell me what you want to practise."
        });
        return;
      }
    }
    if (settings.mode === "pyq" && forceAi) settings.mode = "ai";
    settings.originalRequest = raw;
    await askTimingMode(env, chatId, settings);
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
  if (await handleYouTubeCallback(env, callback)) return;
  if (parts[0] === "video_feedback") {
    const topic = String(callback.message.caption || "").replace(/^🎬.*?ready!?\s*/i, "").slice(0, 180);
    if (parts[1] === "report") {
      await env.QUIZ_STATE.put("video-feedback-report:" + chatId, JSON.stringify({
        topic, createdAt: new Date().toISOString()
      }), { expirationTtl: 86400 });
      return telegram(env, "sendMessage", {
        chat_id: chatId,
        text: "📝 Tell me what was wrong with this video (for example: physics error, repeated scene, disconnected scenes, poor face or narration). Your report will guide the next video."
      });
    }
    if (["good", "poor"].includes(parts[1])) {
      const items = await env.QUIZ_STATE.get("video-feedback:global", "json") || [];
      items.push({ rating: parts[1], topic, createdAt: new Date().toISOString() });
      await env.QUIZ_STATE.put("video-feedback:global", JSON.stringify(items.slice(-30)));
      return telegram(env, "sendMessage", {
        chat_id: chatId,
        text: parts[1] === "good"
          ? "👍 Thanks! I'll use this positive feedback when guiding the next video."
          : "👎 Thanks. I'll use this feedback to make the next video better. Tap 📝 Report a problem if you want to explain what went wrong."
      });
    }
    return;
  }
  if (parts[0] === "section") {
    if (parts[1] === "video") return askVideoTopic(env, chatId);
    if (parts[1] === "youtube") return showYouTubeUploads(env, chatId);
    if (parts[1] === "mixed") return askQuestionCount(env, chatId, "mixed", null);
    if (parts[1] === "subjects") return showSubjects(env, chatId);
    if (parts[1] === "chapters" || parts[1] === "topics") return showTopicSubjects(env, chatId);
    if (parts[1] === "years") return showYears(env, chatId);
    if (parts[1] === "fullpaper") return showFullPaperOptions(env, chatId);
    if (parts[1] === "coverage") return showBankCoverage(env, chatId);
    if (parts[1] === "progress") return showProgress(env, chatId);
    if (parts[1] === "mistakes") return showMistakes(env, chatId);
  }
  if (parts[0] === "count") {
    const pending = await env.QUIZ_STATE.get("pending:" + chatId, "json");
    if (!pending) return telegram(env, "sendMessage", { chat_id: chatId, text: "Please choose the PYQ section again." });
    await env.QUIZ_STATE.delete("pending:" + chatId);
    const bank = questions.filter(validQuestion);
    const available = bank.filter(q =>
      (pending.subject === "mixed" || !pending.subject || q.subject.toLowerCase() === pending.subject) &&
      (!pending.year || String(q.year) === String(pending.year)) &&
      (!pending.topic || normalizeTopic(q.topic || q.chapter).includes(normalizeTopic(pending.topic)))
    ).length;
    const count = parts[1] === "all" ? available : Number(parts[1]);
    pending.count = Math.max(1, count || 1);
    pending.mode = "pyq";
    pending.difficulty = "mixed";
    return askTimingMode(env, chatId, pending);
  }
  if (parts[0] === "timing") {
    const pending = await env.QUIZ_STATE.get("pending:" + chatId, "json");
    if (!pending) return telegram(env, "sendMessage", { chat_id: chatId, text: "Please start the quiz setup again." });
    pending.timed = parts[1] !== "untimed";
    if (pending.timed) {
      await env.QUIZ_STATE.put("pending:" + chatId, JSON.stringify(pending), { expirationTtl: 600 });
      return askDuration(env, chatId);
    }
    if (pending.fullPaperKey) return showFullPaperInstructions(env, chatId, pending);
    await env.QUIZ_STATE.delete("pending:" + chatId);
    return startQuiz(env, chatId, pending, pending.originalRequest || "PYQ menu selection");
  }
  if (parts[0] === "duration") {
    const pending = await env.QUIZ_STATE.get("pending:" + chatId, "json");
    if (!pending) return telegram(env, "sendMessage", { chat_id: chatId, text: "Please start the quiz setup again." });
    pending.timed = true;
    pending.durationSeconds = Number(parts[1]) * 60;
    if (pending.fullPaperKey) return showFullPaperInstructions(env, chatId, pending);
    await env.QUIZ_STATE.delete("pending:" + chatId);
    return startQuiz(env, chatId, pending, pending.originalRequest || "PYQ menu selection");
  }
  if (parts[0] === "fullpaper") {
    const key = decodeURIComponent(parts.slice(1).join(":"));
    const [year, shift] = key.split("|");
    const selected = questions.filter(validQuestion).filter(q => String(q.year) === year && String(q.shift) === shift);
    if (selected.length < 75) return telegram(env, "sendMessage", { chat_id: chatId, text: "This shift is not yet a complete 75-question paper." });
    return askTimingMode(env, chatId, { mode: "pyq", subject: "mixed", topic: null, count: selected.length, fullPaperKey: key, difficulty: "mixed" });
  }
  if (parts[0] === "fullpaper-start") {
    const pending = await env.QUIZ_STATE.get("pending:" + chatId, "json");
    if (!pending?.fullPaperKey) return telegram(env, "sendMessage", { chat_id: chatId, text: "Paper setup expired. Please choose the full paper again." });
    await env.QUIZ_STATE.delete("pending:" + chatId);
    return startQuiz(env, chatId, pending, "Full JEE Main PYQ paper");
  }
  if (parts[0] === "fullpaper-cancel") {
    await env.QUIZ_STATE.delete("pending:" + chatId);
    return showMainMenu(env, chatId, "Full paper cancelled. Choose another mode whenever you're ready.");
  }
  if (parts[0] === "year") return showYearSubjects(env, chatId, parts[1]);
  if (parts[0] === "year-subject") {
    const year = parts[1], subject = parts[2];
    return askQuestionCount(env, chatId, subject, null, year);
  }
  if (parts[0] === "subject") {
    return askQuestionCount(env, chatId, parts[1] === "mixed" ? "mixed" : parts[1], null);
  }
  if (parts[0] === "topic-subject") return showTopics(env, chatId, parts[1]);
  if (parts[0] === "topic") return askQuestionCount(env, chatId, parts[1], parts.slice(2).join(":"));
  if (parts[0] === "video") {
    if (parts[1] === "cancel") {
      await env.QUIZ_STATE.delete("video-pending:" + chatId);
      await env.QUIZ_STATE.delete("video-topic:" + chatId);
      return showMainMenu(env, chatId, "Video generation cancelled.");
    }
    if (parts[1] === "cinematic") {
      const topic = await env.QUIZ_STATE.get("video-topic:" + chatId);
      if (!topic) return telegram(env, "sendMessage", { chat_id: chatId, text: "Video topic expired. Tap Request New Video again." });
      await env.QUIZ_STATE.delete("video-topic:" + chatId);
      return dispatchVideoWorkflow(env, chatId, topic);
    }
  }
  const state = await env.QUIZ_STATE.get("quiz:" + chatId, "json");
  if (!state) return telegram(env, "sendMessage", { chat_id: chatId, text: "No active paper. Send /start to begin." });
  if (parts[0] === "palette") {
    if (parts[1] === "stay") return;
    const page = Number(parts[2]);
    if (Number.isInteger(page)) {
      state.palettePage = Math.max(0, Math.min(Math.ceil(state.questions.length / 20) - 1, page));
      await saveState(env, chatId, state);
      state.messageId = await renderQuestion(env, chatId, state, callback.message.message_id);
      await saveState(env, chatId, state);
    }
    return;
  }
  if (state.reviewMode) {
    if (parts[0] === "review" && parts[1] === "finish") {
      await env.QUIZ_STATE.delete("quiz:" + chatId);
      return showMainMenu(env, chatId, "Review completed. Start another paper whenever you're ready.");
    }
    if (parts[0] === "review" && parts[1] === "noop") return;
    if (parts[0] === "review") {
      const action = parts[1];
      if (action === "prev") state.index = Math.max(0, state.index - 1);
      else if (action === "next") state.index = Math.min(state.questions.length - 1, state.index + 1);
      else if (action.startsWith("q")) {
        const target = Number(action.slice(1));
        if (Number.isInteger(target) && target >= 0 && target < state.questions.length) state.index = target;
      }
      state.palettePage = Math.floor(state.index / 20);
      await saveState(env, chatId, state);
      state.messageId = await renderQuestion(env, chatId, state, callback.message.message_id);
      await saveState(env, chatId, state);
    }
    return;
  }
  if (parts[0] === "verify" && parts[1] === "current") {
    const q = state.questions[state.index];
    return verifyQuestionWithGemini(env, chatId, q, state.index + 1);
  }
  if (state.timed !== false && examClock(state).left <= 0) return submitQuiz(env, chatId, state);
  if (parts[0] === "pick") {
    const index = Number(parts[1]), choice = Number(parts[2]);
    if (index !== state.index || !Number.isInteger(choice) || choice < 0 || choice > 3) return;
    state.answers[index] = choice;
  } else if (parts[0] === "nav") {
    const action = parts[1];
    if (action === "submit") {
      return telegram(env, "editMessageText", {
        chat_id: chatId, message_id: callback.message.message_id,
        text: "📋 <b>SUBMIT PAPER?</b>\n\nAre you sure you want to finish this test? You can still return and change answers if you continue.",
        parse_mode: "HTML",
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
    state.palettePage = Math.floor(state.index / 20);
    if (!Array.isArray(state.visited)) state.visited = [0];
    if (!state.visited.includes(state.index)) state.visited.push(state.index);
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
        if (state.timed !== false && examClock(state).left <= 0) {
          await submitQuiz(env, chatId, state);
        }
        // Do not re-render the question on every cron tick. Telegram may reject
        // an edit and the fallback would create duplicate question messages.
        // The timer is enforced here; navigation refreshes the visible question.
      }
    } catch (error) {
      console.error("Scheduled exam timer failed", String(error));
    }
  },
  async fetch(request, env) {
    const requestUrl = new URL(request.url);
    if (requestUrl.pathname === "/register-video") {
      if (request.method !== "POST") return new Response("Method not allowed", { status: 405 });
      if (!env.GITHUB_TOKEN || request.headers.get("Authorization") !== "Bearer " + env.GITHUB_TOKEN) {
        return new Response("Unauthorized", { status: 401 });
      }
      try {
        const body = await request.json();
        await registerGeneratedVideo(env, body);
        return new Response("OK");
      } catch (error) {
        return new Response(String(error?.message || error), { status: 400 });
      }
    }
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
      const chatId = update.message?.chat?.id || update.callback_query?.message?.chat?.id;
      if (chatId) {
        try {
          await telegram(env, "sendMessage", {
            chat_id: chatId,
            text: "❌ I couldn't complete that action.\n" + String(error?.message || error || "Unknown error").slice(0, 700) +
              "\n\nPlease send /start and try again. Your existing answers have not intentionally been cleared."
          });
        } catch (notifyError) {
          console.error("Could not notify user about update failure", String(notifyError));
        }
      }
    }
    return new Response("OK");
  }
};
