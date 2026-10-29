// AI Detective - browser client. All AI text is inserted with textContent (no HTML injection).
const $ = (id) => document.getElementById(id);
let state = null;
let askingSuspect = null;

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined) e.textContent = text;
  return e;
}

function toast(msg, isError = false) {
  const t = $("toast");
  t.textContent = msg;
  t.className = "toast" + (isError ? " error" : "");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => t.classList.add("hidden"), 6000);
}

async function api(path, payload = {}, loadingText = "The AI is thinking…") {
  $("loading-text").textContent = loadingText;
  $("loading").classList.remove("hidden");
  try {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    let data;
    try { data = await res.json(); } catch { throw new Error("The server sent an unreadable response."); }
    if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
    return data;
  } catch (err) {
    toast(err.message === "Failed to fetch" ? "Cannot reach the game server. Is it running?" : err.message, true);
    return null;
  } finally {
    $("loading").classList.add("hidden");
  }
}

function show(screen) {
  for (const s of ["start", "game", "end"]) $(s).classList.toggle("hidden", s !== screen);
}

function tag(ai) {
  return el("span", "tag " + (ai ? "ai" : "offline"), ai ? "AI" : "offline");
}

function render(s) {
  state = s;
  if (s.notices && s.notices.length) toast("⚠ " + s.notices.join(" "));
  if (s.over) return renderEnd(s);
  show("game");
  $("case-title").textContent = s.title;
  $("case-setting").textContent = `${s.setting} · Victim: ${s.victim.name}, ${s.victim.description}`;
  $("case-intro").textContent = s.intro;
  $("turns").textContent = s.turns_left;
  const outOfTurns = s.turns_left <= 0;

  const locs = $("locations");
  locs.replaceChildren();
  for (const l of s.locations) {
    const row = el("div", "item" + (l.searched ? " done" : ""));
    const info = el("div");
    info.append(el("b", "", l.name), el("small", "", l.description));
    const btn = el("button", "", l.searched ? "Searched" : "Search");
    btn.disabled = l.searched || outOfTurns;
    btn.onclick = async () => {
      const r = await api(`/api/${s.id}/investigate`, { location_id: l.id }, `Searching ${l.name}…`);
      if (r) render(r);
    };
    row.append(info, btn);
    locs.append(row);
  }

  const sus = $("suspects");
  sus.replaceChildren();
  for (const p of s.suspects) {
    const row = el("div", "item");
    const info = el("div");
    info.append(el("b", "", p.name), el("small", "", `${p.role} - ${p.personality}`));
    const btn = el("button", "", p.questioned ? "Question again" : "Question");
    btn.disabled = outOfTurns;
    btn.onclick = () => openAsk(p);
    row.append(info, btn);
    sus.append(row);
  }
  $("hint-btn").disabled = outOfTurns;
  if (outOfTurns) toast("Time's up! You must make your accusation now.");

  const clues = $("clues");
  clues.replaceChildren();
  if (!s.clues.length) clues.append(el("li", "muted", "No clues yet - search a location."));
  for (const c of s.clues) {
    const li = el("li");
    li.append(el("b", "", c.location + ": "), document.createTextNode(c.text));
    clues.append(li);
  }

  const log = $("log");
  log.replaceChildren();
  for (const e of [...s.log].reverse()) log.append(logEntry(e));
  if (!s.log.length) log.append(el("p", "muted", "Your investigation starts now."));
}

function logEntry(e) {
  const d = el("div", "entry");
  const who = el("div", "who", e.type === "investigate" ? `🔍 ${e.title}` : e.type === "hint" ? `💡 ${e.title}` : `🗣️ ${e.title}`);
  who.append(tag(e.ai));
  d.append(who);
  if (e.question) d.append(el("div", "q", `You: “${e.question}”`));
  d.append(el("div", "", e.text));
  return d;
}

function openAsk(p) {
  askingSuspect = p;
  $("ask-name").textContent = p.name;
  $("ask-role").textContent = `${p.role} - ${p.personality}`;
  renderAskHistory();
  $("ask-input").value = "";
  $("ask-dialog").showModal();
  $("ask-input").focus();
}

function renderAskHistory() {
  const h = $("ask-history");
  h.replaceChildren();
  const entries = state.log.filter((e) => e.type === "interrogate" && e.title === askingSuspect.name);
  if (!entries.length) h.append(el("p", "muted", "You haven't questioned this suspect yet."));
  for (const e of entries) h.append(logEntry(e));
  h.scrollTop = h.scrollHeight;
}

$("ask-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const q = $("ask-input").value.trim();
  if (!q) return toast("Type a question first.", true);
  const r = await api(`/api/${state.id}/interrogate`, { suspect_id: askingSuspect.id, question: q },
    `${askingSuspect.name} is answering…`);
  if (!r) return;
  render(r);
  $("ask-input").value = "";
  if (r.turns_left <= 0) $("ask-dialog").close(); else renderAskHistory();
});
$("ask-close").onclick = () => $("ask-dialog").close();

$("hint-btn").onclick = async () => {
  const r = await api(`/api/${state.id}/hint`, {}, "Your assistant is thinking…");
  if (r) render(r);
};

$("accuse-open").onclick = () => {
  const sel = $("accuse-suspect");
  sel.replaceChildren();
  for (const p of state.suspects) {
    const o = el("option", "", `${p.name} (${p.role})`);
    o.value = p.id;
    sel.append(o);
  }
  $("accuse-reason").value = "";
  $("accuse-dialog").showModal();
};
$("accuse-close").onclick = () => $("accuse-dialog").close();
$("accuse-form").addEventListener("submit", async (ev) => {
  ev.preventDefault();
  const reasoning = $("accuse-reason").value.trim();
  if (reasoning.length < 10) return toast("Explain your reasoning (at least a sentence).", true);
  const r = await api(`/api/${state.id}/accuse`, { suspect_id: Number($("accuse-suspect").value), reasoning },
    "The suspects gather as you reveal the truth…");
  if (!r) return;
  $("accuse-dialog").close();
  render(r);
});

function renderEnd(s) {
  const r = s.result;
  show("end");
  $("end-title").textContent = r.correct ? `✅ Case solved! ${r.accused} was the culprit.` : `❌ Wrong suspect! You accused ${r.accused}.`;
  $("end-epilogue").textContent = r.epilogue;
  $("end-feedback").textContent = `${r.feedback} (reasoning ${r.reasoning_score}/100)`;
  $("end-solution").textContent = r.solution;
  $("end-score").textContent = r.score;
  $("end-rank").textContent = r.rank;
}

$("start-btn").onclick = async () => {
  const theme = $("theme").value.trim();
  if (theme.length > 120) return toast("Keep the theme under 120 characters.", true);
  const r = await api("/api/new", { theme, difficulty: $("difficulty").value },
    "Generating a brand-new mystery… (this can take a few seconds)");
  if (r) render(r);
};
$("again-btn").onclick = () => show("start");

fetch("/api/status").then((r) => r.json()).then((s) => {
  const b = $("ai-badge");
  b.textContent = s.ai_enabled ? `AI: ${s.model}` : "Offline mode (no API key)";
  b.className = "badge " + (s.ai_enabled ? "on" : "off");
}).catch(() => { $("ai-badge").textContent = "server unreachable"; });
